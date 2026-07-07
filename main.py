import os
import logging
import discord
import asyncio
from discord.ext import commands
import config
from data.database import init_db
from bot.views.admin_panel import AdminPanelView
from bot.views.guild_panel import GuildPanelView
from bot.integrations.headless_adapter import HeadlessWoWAdapter
from bot.services.bridge_service import BridgeService

# Configuración de logs en archivo
if not os.path.exists(config.LOGS_DIR):
    os.makedirs(config.LOGS_DIR)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(config.LOGS_DIR, "bot.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("WoWBridgeBot")


async def check_and_apply_updates():
    """
    Verifica si hay actualizaciones disponibles y las aplica si es necesario
    
    Retorna:
        True si se aplicó actualización (bot debe reiniciarse)
        False si no hay actualización (continuar normal)
    """
    if not config.UPDATE_ENABLED:
        logger.debug("Auto-updater deshabilitado")
        return False
    
    try:
        from updater.version_manager import VersionManager
        from updater.github_client import GitHubClient
        from updater.downloader import Downloader
        from updater.applicator import Applicator
        from updater.logger import UpdaterLogger
        
        updater_logger = UpdaterLogger.get_logger()
        updater_logger.info("=" * 60)
        updater_logger.info("Verificando actualizaciones...")
        updater_logger.info("=" * 60)
        
        # Obtener versión actual
        current_version = VersionManager.get_current()
        updater_logger.info(f"Versión actual: {current_version}")
        
        # Consultar GitHub Releases
        client = GitHubClient(config.UPDATE_GITHUB_OWNER, config.UPDATE_GITHUB_REPO)
        latest_release = await client.get_latest_release()
        
        if latest_release is None:
            updater_logger.info("No se pudo obtener info de releases (GitHub puede estar fuera de servicio)")
            return False
        
        latest_version = latest_release["version"]
        updater_logger.info(f"Última versión disponible: {latest_version}")
        
        # Comparar versiones
        if not VersionManager.is_update_available(current_version, latest_version):
            updater_logger.info(f"Ya estás en la última versión ({current_version})")
            return False
        
        # ACTUALIZACIÓN DISPONIBLE
        updater_logger.warning(f"⬆️ Actualización disponible: {current_version} → {latest_version}")
        updater_logger.info(f"URL de descarga: {latest_release['download_url']}")
        
        # Paso 1: Descargar
        updater_logger.info("Descargando actualización...")
        zip_path = await Downloader.download_file(
            latest_release["download_url"],
            f"bot-{latest_version}.zip"
        )
        
        if not zip_path:
            updater_logger.error("Fallo la descarga, abortando actualización")
            return False
        
        # Paso 2: Validar descarga
        if not Downloader.validate_file(zip_path):
            updater_logger.error("Validación de descarga falló, abortando")
            return False
        
        updater_logger.info("✅ Descarga validada")
        
        # Paso 3: Extraer
        from updater.downloader import TEMP_DIR
        if not Applicator.extract_update(zip_path, TEMP_DIR):
            updater_logger.error("Extracción falló, abortando")
            return False
        
        # Paso 4: Aplicar actualización (con backup)
        updater_logger.info("Aplicando actualización...")
        if not Applicator.apply_update(TEMP_DIR, latest_version):
            updater_logger.error("Error aplicando actualización, abortando")
            return False
        
        updater_logger.info(f"✅ Actualización aplicada correctamente a v{latest_version}")
        updater_logger.info("El bot se reiniciará ahora para aplicar cambios...")
        
        # Limpiar temp
        Downloader.cleanup_temp()
        
        return True  # Señal para reiniciar
        
    except ImportError:
        logger.error("Módulo updater no encontrado")
        return False
    except Exception as e:
        logger.error(f"Error en check_and_apply_updates: {e}", exc_info=True)
        return False


class WoWBridgeBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!", 
            intents=config.get_intents(),
            help_command=None # La interfaz principal es visual, no por comandos
        )
        self.bridge_service = None

    async def setup_hook(self):
        # Inicializar la Base de Datos SQLite
        await init_db()
        logger.info("Base de datos inicializada correctamente.")
        
        # Cargar los módulos base (cogs)
        try:
            await self.load_extension("bot.cogs.admin")
            await self.load_extension("bot.cogs.bridge")
            await self.load_extension("bot.cogs.whatsapp_apps")
            logger.info("Módulos base de administración, puente y WhatsApp cargados.")
        except Exception as e:
            logger.error(f"Error cargando cogs base: {e}")

        # Cargar de forma independiente y tolerante los nuevos módulos de Gestión de Guild
        try:
            await self.load_extension("bot.cogs.guildmanagement")
            logger.info("Módulo de Gestión de Hermandad cargado correctamente.")
        except Exception as e:
            logger.error(f"Error crítico cargando cog guildmanagement: {e}")

        try:
            await self.load_extension("bot.cogs.aimoderation")
            logger.info("Módulo de Asistencia de IA cargado correctamente.")
        except Exception as e:
            logger.error(f"Error crítico cargando cog aimoderation: {e}")

        try:
            await self.load_extension("bot.cogs.agonia")
            logger.info("Módulo Agonía cargado correctamente.")
        except Exception as e:
            logger.error(f"Error crítico cargando cog agonia: {e}")

        try:
            await self.load_extension("bot.cogs.complaints_cog")
            logger.info("Módulo de reclamos cargado correctamente.")
        except Exception as e:
            logger.error(f"Error crítico cargando cog complaints_cog: {e}")

        try:
            await self.load_extension("bot.cogs.dkp_cog")
            logger.info("Módulo DKP (exportación a Discord) cargado correctamente.")
        except Exception as e:
            logger.error(f"Error crítico cargando cog dkp_cog: {e}")

        # Registrar los paneles como vistas persistentes
        # Esto permite que los botones funcionen incluso si el bot se reinicia
        self.add_view(AdminPanelView())
        self.add_view(GuildPanelView())
        from bot.views.agonia_views import AgoniaPanelView, LegacyAgoniaPanelView
        self.add_view(AgoniaPanelView())
        self.add_view(LegacyAgoniaPanelView())
        logger.info("Vistas de paneles persistentes (Admin, Hermandad y Agonía) registradas con éxito.")

        # Inicializar y arrancar Bridge Service con el adaptador Headless Nativo
        adapter = HeadlessWoWAdapter()
        self.bridge_service = BridgeService(self, adapter)
        self.bridge_service.start()
        logger.info("HeadlessWoWAdapter y BridgeService registrados e iniciados.")

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type in (discord.InteractionType.component, discord.InteractionType.modal_submit):
            logger.info(
                "Interaction recibida: type=%s custom_id=%s user=%s(%s) channel=%s data=%s",
                interaction.type,
                getattr(interaction, 'custom_id', None),
                getattr(interaction.user, 'name', None),
                getattr(interaction.user, 'id', None),
                getattr(interaction.channel, 'id', None),
                getattr(interaction, 'data', None)
            )
        # No hay un on_interaction base definido en esta versión de discord.py,
        # así que no llamamos a super().on_interaction(interaction).
        return

    async def on_ready(self):
        # NOTA: Evitamos realizar un tree.sync() automático para prevenir el re-registro
        # inadvertido de comandos de aplicación antiguos u obsoletos.
        logger.info(f"Bot conectado y listo como {self.user} (ID: {self.user.id})")
        logger.info("Modo Visual/Táctil activo. Los administradores pueden usar !setup_panel.")

if __name__ == "__main__":
    bot = WoWBridgeBot()
    
    # Verificar actualizaciones antes de iniciar el bot
    try:
        logger.info("Verificando actualizaciones...")
        update_needed = asyncio.run(check_and_apply_updates())
        
        if update_needed:
            logger.info("Actualizacion aplicada, reiniciando...")
            import subprocess
            import sys
            import platform
            
            # Determinar script de restart según SO
            if platform.system() == "Windows":
                restart_script = os.path.join(config.BASE_DIR, "scripts", "restart_bot.ps1")
                if os.path.exists(restart_script):
                    logger.info(f"Ejecutando: {restart_script}")
                    subprocess.Popen(["powershell", "-ExecutionPolicy", "Bypass", "-File", restart_script])
                else:
                    logger.warning("PowerShell script no encontrado, usando batch fallback")
                    restart_bat = os.path.join(config.BASE_DIR, "scripts", "restart_bot.bat")
                    if os.path.exists(restart_bat):
                        subprocess.Popen(restart_bat)
            else:
                logger.info("Sistema no Windows, reinicio manual requerido")
            
            sys.exit(0)
    except Exception as e:
        logger.error(f"Error verificando actualizaciones: {e}", exc_info=True)
        logger.warning("Continuando con inicio normal del bot...")
    
    # Iniciar bot
    bot.run(config.DISCORD_BOT_TOKEN)

import asyncio
import logging
from .wow_network.auth_session import AuthSession
from .wow_network.world_session import WorldSession
import config

logger = logging.getLogger("HeadlessAdapter")

class HeadlessWoWAdapter:
    """
    Orquestador de conexión Headless WoW.
    Capa de adaptación mínima para conectar el núcleo WoW con Discord.
    """
    def __init__(self):
        self.auth_session = AuthSession(config.WOW_REALMLIST)
        self.world_session = None
        self.is_running = False

    async def execute_full_login(self):
        """
        Ejecuta el flujo secuencial de login: Auth -> Realm -> World.
        """
        try:
            # 1. Auth Server
            auth_res = await self.auth_session.authenticate(config.WOW_ACCOUNT, config.WOW_PASSWORD)
            if auth_res["status"] != "AUTH_PROOF_ACCEPTED":
                logger.error(f"Fallo en Auth Server: {auth_res['details']}")
                return False

            # 2. Realm List
            realm = next((r for r in auth_res["realms"] if r["name"] == config.WOW_REALM), None)
            if not realm:
                logger.error(f"Reino {config.WOW_REALM} no encontrado.")
                return False

            # 3. World Session
            realm_id = realm.get('id', 1)
            self.world_session = WorldSession(
                realm["address"], realm["port"], 
                config.WOW_ACCOUNT, auth_res["session_key"],
                realmid=realm_id
            )
            
            if not await self.world_session.connect():
                return False

            if not await self.world_session.recv_auth_challenge():
                return False

            await self.world_session.send_auth_session()

            if not await self.world_session.recv_auth_response():
                return False

            logger.info("¡Autenticación en World Server EXITOSA!")
            chars = await self.world_session.get_char_list()
            logger.info(f"Personajes encontrados: {len(chars)}")
            
            char_name = config.WOW_CHARACTER or "Harukoo"
            target_char = next((c for c in chars if c['name'].lower() == char_name.lower()), None)
            if target_char:
                logger.info(f"Logueando con {target_char['name']}...")
                if await self.world_session.login_character(target_char['guid']):
                    logger.info("¡Login completo! Bot en el mundo.")
                    # El bot ya no se une a canales públicos (Taberna, BuscarGrupo) por solicitud del usuario
                    return True
                else:
                    logger.error("Fallo al loguear el personaje.")
                    return False
            else:
                logger.error("No se encontró al personaje 'Harukoo' en la lista.")
                return False

        except Exception as e:
            logger.error(f"Error en flujo de login: {e}")
            return False

    async def listen(self):
        """Loop principal de escucha de eventos del mundo."""
        self.is_running = True
        logger.info("Iniciando auto-login...")
        retry_delay = 30  # segundos iniciales
        max_delay = 300   # máximo 5 minutos entre reintentos

        while self.is_running:
            # Limpiar sesión anterior si existe
            if self.world_session:
                try:
                    self.world_session.connected = False
                    if self.world_session.writer:
                        self.world_session.writer.close()
                        await asyncio.wait_for(self.world_session.writer.wait_closed(), timeout=2.0)
                except Exception:
                    pass
                self.world_session = None

            success = await self.execute_full_login()
            if success:
                retry_delay = 30  # reset backoff en conexión exitosa
                try:
                    async for msg in self.world_session.listenchatevents():
                        yield msg
                except Exception as e:
                    logger.error(f"Error en loop de escucha: {e}")
            else:
                logger.warning(f"Login fallido. Reintentando en {retry_delay}s...")

            await asyncio.sleep(retry_delay)
            # Backoff exponencial: 30s → 60s → 120s → 240s → 300s (máx)
            retry_delay = min(retry_delay * 2, max_delay)

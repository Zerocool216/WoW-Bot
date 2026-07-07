import asyncio
import discord
from discord.ext import commands
import config
from bot.views.admin_panel import AdminPanelView, create_panel_embed
from bot.repositories.config_repo import ConfigRepository
import logging

logger = logging.getLogger("AdminCog")

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin():
        async def predicate(ctx):
            if ctx.author.id in config.ADMINUSERIDS or ctx.author.guild_permissions.administrator:
                return True
            await ctx.send("❌ No tienes permisos para usar este comando técnico.", delete_after=5)
            return False
        return commands.check(predicate)

    @commands.command(name="setup_panel")
    @is_admin()
    async def setup_panel(self, ctx):
        """
        Comando técnico mínimo para inicializar el panel visual persistente.
        Diseñado para ejecutarse una sola vez por un administrador.
        A partir de la ejecución, la gestión será táctil (botones).
        """
        await ctx.message.delete()
        
        current_config = await ConfigRepository.get_config()
        embed = create_panel_embed(current_config)
        view = AdminPanelView()
        
        msg = await ctx.send(embed=embed, view=view)
        
        # Guarda las referencias en DB para futura automatización (ej: actualizar el panel asíncronamente)
        await ConfigRepository.update_config({
            "panel_channel_id": ctx.channel.id,
            "panel_message_id": msg.id
        })

    @commands.command(name="sync")
    @is_admin()
    async def sync_commands(self, ctx):
        """Sincroniza los slash commands con Discord."""
        msg = await ctx.send("🔄 Sincronizando árbol de comandos con Discord... (Esto puede tardar unos segundos)")
        try:
            synced = await self.bot.tree.sync()
            await msg.edit(content=f"✅ Sincronización exitosa. **{len(synced)}** comandos/menús actualizados globalmente.\n\n*(Recuerda reiniciar tu Discord con Ctrl+R para ver los cambios)*")
        except Exception as e:
            await msg.edit(content=f"❌ Error al sincronizar: {e}")

    @commands.command(name="motd")
    @is_admin()
    async def set_motd(self, ctx, *, nuevo_motd: str):
        """Cambia el MOTD de la hermandad en WoW desde Discord.
        
        Uso: !motd Martes SR25H x3 loguear temprano
        """
        adapter = getattr(self.bot.bridgeservice, 'adapter', None)
        if not adapter or not adapter.worldsession or not adapter.worldsession.connected:
            await ctx.send("❌ El bot no está conectado a WoW en este momento. Espera a que Harukoo inicie sesión.", delete_after=15)
            return

        logger.info(f"[DISCORD-CMD] Usuario {ctx.author} ({ctx.author.id}) inició cambio de MOTD a: '{nuevo_motd}'")
        msg = await ctx.send(f"🔄 Enviando nuevo MOTD a WoW: `{nuevo_motd}`...")
        success = await adapter.worldsession.send_guild_motd(nuevo_motd)
        if success:
            logger.info("[DISCORD-CMD] CMSG_GUILD_MOTD enviado. Esperando 2s para refrescar roster...")
            # Esperar 2 segundos y pedir el roster para confirmar que el servidor aceptó el cambio
            await asyncio.sleep(2)
            await adapter.worldsession.refresh_guild_roster()
            await asyncio.sleep(1)
            
            motd_actual = getattr(adapter.worldsession, 'guild_motd', '').strip()
            last_result = adapter.worldsession.get_last_gmotd_status()
            res_code = last_result.get("result") if last_result else None
            res_name = adapter.worldsession.GUILD_RESULT_MAP.get(res_code, f"DESCONOCIDO_{res_code}") if res_code is not None else "SIN RESPUESTA"
            
            logger.info(f"[DISCORD-CMD] MOTD actual tras refresh: '{motd_actual}'. Estado server: {res_name}")

            if motd_actual.lower() == nuevo_motd.lower():
                await msg.edit(content=f"✅ **MOTD confirmado en WoW!**\n**Nuevo MOTD:** {motd_actual}")
            else:
                logger.warning(f"[DISCORD-CMD] Falló confirmación MOTD. Server: {res_name}, Cacheado: '{motd_actual}'")
                await msg.edit(content=(
                    f"⚠️ Paquete enviado, pero el servidor devuelve MOTD: `{motd_actual or 'sin cambio'}`\n"
                    f"Resultado del comando: **{res_name}**\n"
                    f"Esto indica que **Harukoo no tiene el permiso 'Editar Mensaje del Día'** en su rango.\n"
                    f"Pídele al GM que lo active en: Hermandad → Rangos → Editar MOTD ✓"
                ))
        else:
            logger.error("[DISCORD-CMD] Falló el envío del paquete CMSG_GUILD_MOTD.")
            await msg.edit(content="❌ No se pudo enviar el paquete. Comprueba la consola del bot.")



async def setup(bot):
    await bot.add_cog(AdminCog(bot))

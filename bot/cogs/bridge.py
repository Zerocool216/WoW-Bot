import asyncio
import logging
import discord
from discord.ext import commands
from bot.repositories.config_repo import ConfigRepository

logger = logging.getLogger("BridgeCog")

class BridgeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bridge_service = None # Se inyectará desde main.py
        self._discord_queue = asyncio.Queue(maxsize=10)
        self._worker_task = None

    async def start_worker(self):
        if not self._worker_task or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._discord_to_wow_worker())
            logger.info("Worker Discord -> WoW iniciado.")

    async def _discord_to_wow_worker(self):
        """Worker con rate limiting para no floodear el World Server."""
        while True:
            item = await self._discord_queue.get()
            try:
                adapter = self.bot.bridge_service.adapter
                if adapter and adapter.world_session and adapter.world_session.connected:
                    # Hacemos pop de _retry para no pasarlo a send_chat_message
                    retry_count = item.pop("_retry", 0)
                    success = await adapter.world_session.send_chat_message(**item)
                    if not success:
                        logger.warning(f"send_chat_message retornó False para: {item}")
                else:
                    retry_count = item.pop("_retry", 0)
                    if retry_count < 1:
                        item["_retry"] = retry_count + 1
                        try:
                            self._discord_queue.put_nowait(item)
                            logger.warning(f"WoW desconectado. Mensaje re-encolado (intento {retry_count+1}): {item['message'][:50]}")
                        except asyncio.QueueFull:
                            logger.error(f"Queue llena, mensaje descartado definitivamente: {item['message'][:50]}")
                    else:
                        logger.error(f"Mensaje descartado tras {retry_count} reintentos: {item['message'][:50]}")
            except Exception as e:
                logger.error(f"Error en worker Discord->WoW: {e}")
            finally:
                await asyncio.sleep(1.0) # Rate limit: 1 msg/seg
                self._discord_queue.task_done()

    @commands.command(name="login")
    async def login(self, ctx, char_name: str = "Harukoo"):
        """Inicia sesión con un personaje en WoW."""
        adapter = self.bot.bridge_service.adapter
        if adapter.world_session and adapter.world_session.connected:
            await ctx.send("⚠️ El bot ya está conectado al mundo.")
            return

        status_msg = await ctx.send("🔄 Iniciando flujo de login...")
        
        success = await adapter.execute_full_login()
        if success:
            world = adapter.world_session
            # Iniciar loops de mantenimiento si no están corriendo
            if not self._worker_task or self._worker_task.done():
                await self.start_worker()
            
            # El bridge se activa automáticamente por el adaptador.listen() 
            # pero necesitamos asegurarnos de que el canal esté configurado
            db_config = await ConfigRepository.get_config()
            self.bridge_channel_id = int(db_config.get("canal_guild_discord_id") or 0)

            embed = discord.Embed(
                title="✅ Login Exitoso",
                description=f"El bot ha entrado al mundo con **{char_name}**.",
                color=0x00FF00
            )
            embed.add_field(name="Servidor", value="NaerZone (Thalassa)", inline=True)
            embed.add_field(name="Estado", value="Online • Sesión Activa", inline=True)
            embed.set_footer(text="JudeBridge v2.0 • 3.3.5a")
            
            await status_msg.edit(content=None, embed=embed)
        else:
            await status_msg.edit(content="❌ Error en el proceso de login. Revisa los logs.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Obtener configuración
        db_config = await ConfigRepository.get_config()
        channel_ids = [
            int(db_config.get("canal_guild_discord_id") or 0)
        ]

        if message.channel.id not in channel_ids:
            return

        content = message.content.strip()
        type_map = {
            "!g": (4, "GUILD"),
            "!o": (5, "OFFICER"),
            "!y": (8, "YELL"),
            "!s": (1, "SAY"),
        }

        chat_type = 1
        type_name = "SAY"
        for prefix, (t, n) in type_map.items():
            if content.lower().startswith(prefix + " "):
                content = content[len(prefix):].strip()
                chat_type = t
                type_name = n
                break

        if not content:
            return

        if len(content) > 255:
            await message.reply("⚠️ Mensaje demasiado largo (máx 255 caracteres).")
            return

        # Encolar para envío
        wow_msg = f"[Discord] {message.author.display_name}: {content}"
        
        try:
            self._discord_queue.put_nowait({
                "message": wow_msg,
                "chat_type": chat_type
            })
            await message.add_reaction("✅")
            if not self._worker_task or self._worker_task.done():
                await self.start_worker()
        except asyncio.QueueFull:
            await message.reply("⚠️ El bot está saturado. Reintenta en unos segundos.")
            await message.add_reaction("⏳")

async def setup(bot):
    cog = BridgeCog(bot)
    await bot.add_cog(cog)

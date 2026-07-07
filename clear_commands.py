import discord
from discord.ext import commands
import config
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ClearCommands")

class CommandClearer(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def on_ready(self):
        logger.info(f"Conectado como {self.user} (ID: {self.user.id})")
        
        try:
            # 1. Limpiar comandos globales
            self.tree.clear_commands(guild=None)
            await self.tree.sync(guild=None)
            print("[OK] Comandos globales borrados")
            logger.info("Comandos globales borrados y sincronizados con éxito.")
            
            # 2. Limpiar comandos de guild específica
            guild_id = config.DISCORD_GUILD_ID
            if guild_id:
                guild_obj = discord.Object(id=guild_id)
                self.tree.clear_commands(guild=guild_obj)
                await self.tree.sync(guild=guild_obj)
                print(f"[OK] Comandos de guild {guild_id} borrados")
                logger.info(f"Comandos de guild {guild_id} borrados y sincronizados con éxito.")
            else:
                logger.warning("DISCORD_GUILD_ID no configurado en config.py, omitiendo limpieza de comandos de guild.")
                
        except Exception as e:
            logger.error(f"Error al limpiar comandos: {e}", exc_info=True)
        finally:
            logger.info("Cerrando el bot...")
            await self.close()

if __name__ == "__main__":
    if not config.DISCORD_BOT_TOKEN:
        print("❌ Error: DISCORD_BOT_TOKEN no configurado en config.py o archivo .env.")
        exit(1)
        
    bot = CommandClearer()
    bot.run(config.DISCORD_BOT_TOKEN)

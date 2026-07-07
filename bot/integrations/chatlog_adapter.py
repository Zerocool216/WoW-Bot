import logging
import asyncio
from bot.integrations.wow_adapter import WoWAdapter
from bot.services.chatlog_tail_service import ChatLogTailService
from bot.services.wow_message_parser import WoWMessageParser
from bot.repositories.config_repo import ConfigRepository

logger = logging.getLogger("ChatLogAdapter")

class ChatLogWoWAdapter(WoWAdapter):
    """
    Integración pasiva (Fase 4A): Lee el chat de WoW desde un ChatLog.txt generado por el cliente de juego.
    """
    def __init__(self):
        self.tail_service = ChatLogTailService()
        self.parser = WoWMessageParser()

    async def listen(self):
        logger.info("ChatLogWoWAdapter iniciado. Preparado para leer el archivo local.")
        
        while True:
            config = await ConfigRepository.get_config()
            if not config.get("adapter_activo", False):
                # Si el administrador pauso la lectura del disco desde el panel
                await asyncio.sleep(3)
                continue
                
            async for raw_line in self.tail_service.tail():
                parsed_msg = self.parser.parse_line(raw_line)
                if parsed_msg:
                    logger.debug(f"Mensaje extraído: [{parsed_msg.source_channel}] {parsed_msg.author}: {parsed_msg.content}")
                    yield parsed_msg
                    
            await asyncio.sleep(2) # Pausa si el tail_service termina (ej. archivo no encontrado)

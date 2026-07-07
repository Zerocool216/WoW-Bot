import asyncio
import os
import logging
from bot.repositories.config_repo import ConfigRepository

logger = logging.getLogger("ChatLogTailService")

class ChatLogTailService:
    def __init__(self):
        self._stop_event = asyncio.Event()

    async def tail(self):
        config = await ConfigRepository.get_config()
        file_path = config.get("chatlog_path", "")
        last_offset = config.get("ultimo_offset_leido", 0)

        if not file_path or not os.path.exists(file_path):
            logger.warning(f"Archivo ChatLog no encontrado en la ruta configurada: {file_path}")
            await asyncio.sleep(5)
            return

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                if last_offset == 0:
                    # Primera ejecución: ir al final para evitar spam viejo
                    f.seek(0, os.SEEK_END)
                    last_offset = f.tell()
                    await ConfigRepository.update_config({"ultimo_offset_leido": last_offset})
                    logger.info(f"Primera lectura. Empezando desde el final del archivo (offset: {last_offset})")
                else:
                    # Intento de recuperación
                    f.seek(0, os.SEEK_END)
                    current_size = f.tell()
                    
                    if last_offset > current_size:
                        # El archivo fue rotado o borrado, volvemos al inicio
                        logger.warning("El archivo de log parece haber sido truncado. Reiniciando lectura.")
                        last_offset = 0
                        f.seek(0)
                    else:
                        f.seek(last_offset)

                while not self._stop_event.is_set():
                    line = f.readline()
                    if not line:
                        await asyncio.sleep(0.2) # Evitar saturar el CPU
                        continue
                    
                    # Actualizar estado de lectura
                    new_offset = f.tell()
                    await ConfigRepository.update_config({"ultimo_offset_leido": new_offset})
                    
                    yield line

        except Exception as e:
            logger.error(f"Error técnico leyendo el log {file_path}: {e}")
            await asyncio.sleep(5)

    def stop(self):
        self._stop_event.set()

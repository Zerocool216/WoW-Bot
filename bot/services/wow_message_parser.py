import re
from typing import Optional
from bot.models.message import WoWMessage
from datetime import datetime

class WoWMessageParser:
    def __init__(self):
        # Patrón típico de ChatLog.txt en WoW 3.3.5a:
        # Mes/Dia Hora:Min:Seg.ms [Canal] [Jugador]: Mensaje
        # Ejemplo: 5/9 10:20:30.123 [Guild] [Arthas]: LFM ICC
        # Ejemplo: 5/9 10:20:35.456 [4. Taberna] [Thrall]: WTS oro
        self.pattern = re.compile(r'^\d{1,2}/\d{1,2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\[(.*?)\]\s+\[(.*?)\]:\s+(.*)$')

    def parse_line(self, line: str) -> Optional[WoWMessage]:
        match = self.pattern.match(line.strip())
        if not match:
            return None
            
        raw_channel, author, content = match.groups()
        raw_channel_lower = raw_channel.lower()
        
        # Clasificar el canal
        source_channel = None
        if "guild" in raw_channel_lower or "hermandad" in raw_channel_lower:
            source_channel = "GUILD"
        elif "taberna" in raw_channel_lower or "world" in raw_channel_lower or "mundo" in raw_channel_lower or "buscar" in raw_channel_lower:
            source_channel = "TABERNA"
            
        if not source_channel:
            return None
            
        return WoWMessage(
            source_channel=source_channel,
            author=author,
            content=content,
            timestamp=datetime.now() # Para el MVP usamos la fecha actual del sistema
        )

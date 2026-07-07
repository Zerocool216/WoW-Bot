from dataclasses import dataclass
from datetime import datetime

@dataclass
class WoWMessage:
    source_channel: str # "TABERNA" o "GUILD"
    author: str
    content: str
    timestamp: datetime

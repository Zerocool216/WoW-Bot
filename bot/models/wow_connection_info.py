from dataclasses import dataclass
from typing import Optional

@dataclass
class WoWConnectionInfo:
    state: str = "🔴 Desconectado"
    last_error: Optional[str] = None
    connected_character: Optional[str] = None

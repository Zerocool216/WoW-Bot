from abc import ABC, abstractmethod
from typing import AsyncGenerator
from bot.models.message import WoWMessage

class WoWAdapter(ABC):
    """
    Interfaz base para cualquier fuente de datos de WoW.
    Permite desacoplar el bot de Discord de la implementación real del juego (Addon, C++, Webhooks).
    """
    @abstractmethod
    async def listen(self) -> AsyncGenerator[WoWMessage, None]:
        """Generador asíncrono que emite mensajes conforme llegan del juego."""
        pass

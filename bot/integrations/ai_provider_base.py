from abc import ABC, abstractmethod
from typing import List, Dict


class AIProviderBase(ABC):
    """
    Clase abstracta base para los proveedores de Inteligencia Artificial del bot.
    Define la interfaz común que deben implementar todos los adaptadores.
    """
    @abstractmethod
    async def generate_response(self, messages: List[Dict[str, str]], system_prompt: str | None = None) -> str:
        """
        Genera una respuesta de texto de forma asíncrona a partir de una lista de mensajes
        y un system prompt opcional.
        """
        pass

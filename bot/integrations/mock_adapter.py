import asyncio
import random
from datetime import datetime
from bot.integrations.wow_adapter import WoWAdapter
from bot.models.message import WoWMessage

class MockWoWAdapter(WoWAdapter):
    """
    Proveedor simulado que genera mensajes aleatorios como si vinieran de WoW.
    Usado para la Fase 2 mientras se desarrolla la integración in-game.
    """
    def __init__(self):
        self.authors = ["Thrall", "Arthas", "Jaina", "Sylvanas", "Illidan", "Tirion"]
        self.messages = [
            "LFM ICC 25N, armados mandar link de GS por favor", 
            "Alguien tiene oro que me preste para la voladora?",
            "Venganza para Lordaeron!",
            "WTS [Saronita Primordial] x20",
            "¿A qué hora es la raid de hoy?",
            "vendo gemas epicas, manden susurro",
            "reclutando heal para 10hc, core de fin de semana"
        ]

    async def listen(self):
        while True:
            # Simula una espera aleatoria entre 10 y 30 segundos entre cada mensaje
            await asyncio.sleep(random.randint(10, 30)) 
            channel = random.choice(["TABERNA", "GUILD"])
            
            yield WoWMessage(
                source_channel=channel,
                author=random.choice(self.authors),
                content=random.choice(self.messages),
                timestamp=datetime.now()
            )

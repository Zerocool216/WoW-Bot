import re

class MessageFormatter:
    """
    Utilidad para limpiar y formatear mensajes de WoW para Discord.
    """
    
    # Mapa de códigos de WoW a Emojis
    SYMBOL_MAP = {
        r"\{rt1\}": "🌟", # Estrella
        r"\{rt2\}": "🔶", # Círculo naranja (usado como marcador)
        r"\{rt3\}": "🔷", # Diamante púrpura/azul
        r"\{rt4\}": "🔺", # Triángulo
        r"\{rt5\}": "🌙", # Luna
        r"\{rt6\}": "🟦", # Cuadrado
        r"\{rt7\}": "❌", # Cruz
        r"\{rt8\}": "💀", # Calavera
        r"\{luna\}": "🌙",
        r"\{estrella\}": "🌟",
        r"\{circulo\}": "🔶",
        r"\{diamante\}": "🔷",
        r"\{triangulo\}": "🔺",
        r"\{cuadrado\}": "🟦",
        r"\{cruz\}": "❌",
        r"\{calavera\}": "💀",
    }

    @staticmethod
    def clean_wow_links(text: str) -> str:
        """
        Limpia enlaces de objetos e hipervínculos nativos de WoW:
        Formatos: |cffa335ee|Hitem:34057...|h[Cristal abisal]|h
        """
        # 1. Limpiar códigos de color |cff... y resets |r (insensibles a mayúsculas)
        text = re.sub(r"\|[Cc][0-9A-Fa-f]{8}", "", text)
        text = re.sub(r"\|[Rr]", "", text)
        
        # 2. Reemplazar hipervínculos |H...|h[Nombre]|h con [Nombre]
        text = re.sub(r"\|H.*?\|h(.*?)\|h", r"\1", text)
        
        # 3. Limpiar enlaces de markdown antiguos si los hubiera
        text = re.sub(r"\[\[(.*?)\]\]\(.*?\)", r"[\1]", text)
        
        return text

    @classmethod
    def format_for_discord(cls, text: str) -> str:
        """
        Aplica todos los reemplazos y limpiezas.
        """
        if not text:
            return ""
            
        # Limpiar links y colores
        text = cls.clean_wow_links(text)
        
        # Reemplazar símbolos rtX y nombres por emojis
        for pattern, emoji in cls.SYMBOL_MAP.items():
            text = re.sub(pattern, emoji, text, flags=re.IGNORECASE)
            
        return text.strip()

import aiohttp
import logging
import config
from typing import List, Dict
from bot.integrations.ai_provider_base import AIProviderBase

logger = logging.getLogger("OpenAIProvider")

class OpenAIProvider(AIProviderBase):
    """
    Proveedor de IA para OpenAI.
    Realiza llamadas directas asíncronas a la API de Chat Completions.
    """
    async def generate_response(self, messages: List[Dict[str, str]], system_prompt: str | None = None) -> str:
        api_key = getattr(config, "AIAPIKEY", getattr(config, "AI_API_KEY", ""))
        model = getattr(config, "AIMODEL", getattr(config, "AI_MODEL", "gpt-4o-mini"))

        if not api_key:
            return "❌ Error: La clave API de OpenAI (AIAPIKEY) no está configurada."

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload_messages = messages.copy()
        if system_prompt:
            if not any(msg.get("role") == "system" for msg in payload_messages):
                payload_messages.insert(0, {"role": "system", "content": system_prompt})
            else:
                for i, msg in enumerate(payload_messages):
                    if msg.get("role") == "system":
                        payload_messages[i]["content"] = f"{system_prompt}\n{msg['content']}"
                        break
        
        payload = {
            "model": model if model else "gpt-4o-mini",
            "messages": payload_messages,
            "temperature": 0.7
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=20) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content'].strip()
                    else:
                        error_text = await response.text()
                        logger.error(f"Error de API OpenAI ({response.status}): {error_text}")
                        return f"❌ Error de API OpenAI ({response.status}). Consulta a los oficiales."
        except Exception as e:
            logger.error(f"Fallo de conexión con OpenAI: {e}")
            return f"❌ Fallo de conexión con el motor de IA de OpenAI: {e}"

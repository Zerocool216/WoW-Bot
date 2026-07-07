import aiohttp
import logging
import config
from typing import List, Dict
from bot.integrations.ai_provider_base import AIProviderBase

logger = logging.getLogger("GeminiProvider")


class GeminiProvider(AIProviderBase):
    """
    Proveedor de IA para Google Gemini.
    Realiza llamadas directas asíncronas a la API REST de Gemini.
    """
    async def generate_response(self, messages: List[Dict[str, str]], system_prompt: str | None = None) -> str:
        api_key = getattr(config, "AIAPIKEY", getattr(config, "AI_API_KEY", ""))
        model = getattr(config, "AIMODEL", getattr(config, "AI_MODEL", "gemini-2.5-flash"))

        if not api_key:
            return "❌ Error: La clave API de Gemini (AIAPIKEY) no está configurada."

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        # Mapear mensajes al formato oficial de Gemini
        contents = []
        extracted_system = system_prompt or ""

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                if not extracted_system:
                    extracted_system = content
                else:
                    extracted_system += f"\n{content}"
            else:
                gemini_role = "model" if role == "assistant" else "user"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": content}]
                })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7
            }
        }

        if extracted_system:
            payload["systemInstruction"] = {
                "parts": [{"text": extracted_system}]
            }

        headers = {
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=20) as response:
                    if response.status == 200:
                        data = await response.json()
                        try:
                            text = data['candidates'][0]['content']['parts'][0]['text']
                            return text.strip()
                        except (KeyError, IndexError) as parse_err:
                            logger.error(f"Error parseando respuesta de Gemini: {parse_err}. JSON: {data}")
                            return "❌ Error parseando la respuesta del servidor de IA."
                    else:
                        error_text = await response.text()
                        logger.error(f"Error de API Gemini ({response.status}): {error_text}")
                        if response.status == 400:
                            return f"❌ Error de API Gemini ({response.status}): Solicitud mal formada o modelo incompatible. Revisa AIMODEL."
                        elif response.status == 403:
                            return f"❌ Error de API Gemini ({response.status}): API Key inválida o sin permisos."
                        elif response.status == 429:
                            return f"❌ Error de API Gemini ({response.status}): Límite de cuota excedido (Rate Limit)."
                        return f"❌ Error de API Gemini ({response.status}). Consulta con los oficiales."
        except Exception as e:
            logger.error(f"Fallo de conexión con Gemini: {e}")
            return f"❌ Fallo de conexión con el motor de IA de Gemini: {e}"

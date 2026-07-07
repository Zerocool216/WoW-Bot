import logging
import discord
import config
from typing import List, Dict, Any, Optional
from bot.integrations.gemini_provider import GeminiProvider
from bot.integrations.openai_provider import OpenAIProvider
from bot.integrations.ai_provider_base import AIProviderBase

logger = logging.getLogger("AIService")


class AIService:
    """
    Servicio central de Inteligencia Artificial de la Hermandad.
    Orquesta los prompts, la lógica de negocio conductual y delega
    las llamadas de red al proveedor configurado (Gemini o OpenAI).
    """
    _provider = None

    @classmethod
    async def get_provider(cls) -> AIProviderBase:
        """Retorna e inicializa de forma diferida el proveedor de IA configurado."""
        if cls._provider is None:
            provider_name = getattr(config, "AIPROVIDER", getattr(config, "AI_PROVIDER", "gemini")).lower()
            if provider_name == "openai":
                logger.info("Inicializando proveedor de IA: OpenAI")
                cls._provider = OpenAIProvider()
            else:
                # Gemini por defecto
                logger.info("Inicializando proveedor de IA: Google Gemini")
                cls._provider = GeminiProvider()
        return cls._provider

    @classmethod
    async def is_enabled(cls) -> bool:
        """Indica si el motor de asistencia por IA está activo y configurado."""
        return getattr(config, "AIENABLED", getattr(config, "AI_ENABLED", False))

    @classmethod
    async def build_base_system_prompt(cls, rules_text: str | None, rules_source: str | None) -> str:
        """
        Construye el system prompt base general sin hardcodear datos fijos,
        inyectando la normativa de la hermandad si está disponible.
        """
        prompt = (
            "Eres un Asistente de Inteligencia Artificial para el Staff de una hermandad del juego World of Warcraft 3.3.5a.\n"
            "Tu objetivo es proveer asesoramiento conductual, ayuda con moderación y responder preguntas sobre reglas de forma precisa, objetiva y amigable.\n"
            "Tus respuestas son estrictamente informativas. NUNCA aplicas ni ejecutas sanciones automáticamente, dejando claro que la decisión final es de los oficiales.\n"
        )

        if rules_text:
            prompt += (
                f"\n=== CONTEXTO DE NORMAS DE LA HERMANDAD (Fuente: {rules_source}) ===\n"
                f"{rules_text}\n"
                "============================================================\n\n"
                "DIRECTIVAS ESTRICTAS DE RESPUESTA BASADA EN REGLAS:\n"
                "1. Si la pregunta del usuario puede responderse directamente con las normas provistas arriba, responde basándote en ellas de forma precisa.\n"
                "2. REGLA DE ORO / ALUCINACIÓN CERO: Si las reglas cargadas NO CONTIENEN información para responder la pregunta o el tema consultado, debes responder EXACTAMENTE: \"La normativa actual no especifica una regla para esta consulta.\" NUNCA inventes, asumas, deduzcas ni asocies normativas que no estén textualmente expresadas en las reglas.\n"
                "3. Opcionalmente, puedes añadir una interpretación orientativa SOLO si la marcas explícitamente y de manera destacada como no oficial (ej: \"[Interpretación No Oficial / Orientativa] ...\"). Pero la respuesta principal sobre reglas inexistentes debe apegarse a la regla de oro.\n"
                "4. Distingue entre una 'respuesta basada en las reglas oficiales' (citando o resumiendo las normas cargadas) y un 'análisis conductual orientativo' (sugerencia racional para el staff).\n"
            )
        else:
            prompt += (
                "\n⚠️ ATENCIÓN: No hay un documento oficial de reglas cargado actualmente en el sistema.\n"
                "Si te preguntan por normas, debes responder exactamente que no hay reglas oficiales cargadas en el bot y pedir amablemente al staff que configure una fuente oficial."
            )

        return prompt

    @classmethod
    async def answer_from_rules(cls, question: str, bot: discord.Client | None = None) -> str:
        """
        Responde consultas de usuarios basándose estrictamente en las reglas cargadas dinámicamente.
        """
        if bot is None:
            return (
                "⚠️ **No hay reglas oficiales cargadas en el bot.**\n"
                "Por favor, pide al staff que configure una fuente oficial de reglas."
            )

        # Cargar reglas a través del servicio
        from bot.services.rules_service import RulesService
        rules_text, source_type, source_id = await RulesService.get_rules_text(bot)

        if not rules_text or source_type == "none":
            return (
                "⚠️ **No hay reglas oficiales cargadas en el bot.**\n"
                "Por favor, configure una fuente oficial de reglas (un archivo local 'Reglas.txt' o subiéndolas al canal configurado de Discord)."
            )

        system_prompt = await cls.build_base_system_prompt(rules_text, f"{source_type} ({source_id})")

        user_content = (
            f"Consulta del usuario: \"{question}\"\n\n"
            f"Por favor, responde esta consulta basándote únicamente en el contexto de las reglas proporcionado. "
            f"DIRECTIVA DE ORO: Si las reglas no responden explícitamente a la pregunta, debes responder exactamente: "
            f"\"La normativa actual no especifica una regla para esta consulta.\"\n"
            f"No intentes inventar ni asumir ninguna regla."
        )

        ai_enabled = await cls.is_enabled()
        if not ai_enabled:
            return (
                "🤖 **[SIMULACIÓN - MODO DEMO DE IA]**\n"
                "*(La asistencia por IA real está desactivada. Configura AIAPIKEY en tu .env)*\n\n"
                f"**Consulta recibida:** \"{question}\"\n"
                f"**Fuente de reglas activa:** `{source_type}` ({source_id})\n\n"
                "El bot ha leído correctamente la normativa y está listo para responder consultas reales usando el contexto cargado."
            )

        messages = [
            {"role": "user", "content": user_content}
        ]

        provider = await cls.get_provider()
        response = await provider.generate_response(messages, system_prompt=system_prompt)

        # Mapear fuente corta
        source_friendly = {
            "file": "Archivo Local",
            "discord_attachment": "Adjunto Discord",
            "discord_pinned": "Mensajes Fijados",
            "discord_recent": "Mensajes Curados"
        }.get(source_type, source_type)

        # Agregar una breve nota indicando la fuente de forma limpia
        if "La normativa actual no especifica una regla" not in response:
            response += f"\n\n*(Respuesta basada en reglas oficiales cargadas de `{source_friendly}`)*"

        return response

    @classmethod
    async def analyze_user_behavior(cls, username: str, rankinfo: dict, notes: list[dict], bot: discord.Client | None = None) -> str:
        """
        Genera un informe analítico estructurado del comportamiento de un miembro.
        Cruza las incidencias con las reglas de la hermandad si el bot está provisto.
        """
        # Formatear el historial de notas administrativamente
        notes_str = ""
        if notes:
            for idx, note in enumerate(notes, 1):
                notes_str += f"{idx}. [{note.get('created_at', 'Desconocida')}] Por {note.get('staff_username', 'Desconocido')}: {note.get('note', '')} (Sugerido: {note.get('suggested_action', 'Ninguna')})\n"
        else:
            notes_str = "No hay ninguna nota o incidencia registrada para este miembro.\n"

        # Intentar inyectar reglas si se proporciona el cliente
        rules_text = None
        rules_source = None
        if bot:
            try:
                from bot.services.rules_service import RulesService
                rules_text, rules_source, _ = await RulesService.get_rules_text(bot)
            except Exception as e:
                logger.error(f"Error cargando reglas para análisis de comportamiento: {e}")

        system_prompt = await cls.build_base_system_prompt(rules_text, rules_source)

        user_content = (
            f"Analiza el siguiente miembro de la hermandad:\n"
            f"- Nombre de usuario: {username}\n"
            f"- Rango actual estimado: {rankinfo.get('name', 'Ninguno')} (Rango {rankinfo.get('tier', 12)} de 12)\n"
            f"- Historial de incidencias registradas por el Staff:\n{notes_str}\n"
            f"Por favor, redacta un resumen del perfil del miembro y ofrece recomendaciones conductuales y de rol en la guild basándote en la normativa de la hermandad."
        )

        ai_enabled = await cls.is_enabled()
        if not ai_enabled:
            return (
                "🤖 **[SIMULACIÓN - MODO DEMO DE IA]**\n"
                f"*(Este análisis es una plantilla estática porque la IA está desactivada)*\n\n"
                f"**Perfil de Miembro:** `{username}`\n"
                f"**Clasificación de Rango:** {rankinfo.get('name', 'Iniciado')} (Prioridad Jerárquica: {rankinfo.get('tier', 10)}/12)\n\n"
                f"**Resumen de Comportamiento:**\n"
                f"- Notas históricas analizadas: {len(notes)} incidencias.\n"
                f"- El usuario muestra un patrón de comportamiento alíneado con su rango. "
                f"Si hay incidencias registradas, el staff debe evaluar el caso de forma justa y equitativa en base a las reglas de la hermandad.\n\n"
                f"**Sugerencia del Asistente:**\n"
                f"Mantener un seguimiento pasivo en Discord. Si no hay incidencias acumuladas, es candidato para continuar progresando mediante el sistema de niveles de la guild."
            )

        messages = [
            {"role": "user", "content": user_content}
        ]

        provider = await cls.get_provider()
        return await provider.generate_response(messages, system_prompt=system_prompt)

    @classmethod
    async def suggest_sanction(cls, username: str, incident_description: str, bot: discord.Client | None = None) -> str:
        """
        Analiza una descripción de mal comportamiento escrita por el staff y sugiere una sanción proporcional.
        """
        rules_text = None
        rules_source = None
        if bot:
            try:
                from bot.services.rules_service import RulesService
                rules_text, rules_source, _ = await RulesService.get_rules_text(bot)
            except Exception as e:
                logger.error(f"Error cargando reglas para sugerencia de sanción: {e}")

        system_prompt = await cls.build_base_system_prompt(rules_text, rules_source)

        user_content = (
            f"Oficial reporta incidencia para el miembro: {username}\n"
            f"Descripción del incidente:\n\"{incident_description}\"\n\n"
            f"Por favor, redacta una sugerencia detallada basándote en la normativa de la hermandad si está disponible. Tu respuesta debe incluir:\n"
            f"1. Gravedad estimada (Leve, Moderada, Grave).\n"
            f"2. Sanción recomendada (ej: Advertencia, Muteo temporal de canales, Pérdida de DKP/EPGP, Expulsión).\n"
            f"3. Justificación racional del caso sustentada en las normas."
        )

        ai_enabled = await cls.is_enabled()
        if not ai_enabled:
            return (
                "🤖 **[SIMULACIÓN - MODO DEMO DE IA]**\n"
                f"*(Sugerencia generada mediante plantilla por falta de API Key)*\n\n"
                f"**Evaluación de Incidencia:**\n"
                f"- Miembro implicado: `{username}`\n"
                f"- Incidencia reportada: \"{incident_description}\"\n\n"
                f"**Recomendaciones Generales de Sanción:**\n"
                f"1. **Gravedad:** Moderada (Ajustable a juicio de los oficiales).\n"
                f"2. **Sanción Sugerida:** Una advertencia formal (Warn) registrada en el perfil, y un recordatorio amistoso en privado.\n"
                f"3. **Acción Ejecutiva:** Recuerda que puedes aplicar esta advertencia manualmente anotándola en el panel o usando el bot de moderación en tu canal."
            )

        messages = [
            {"role": "user", "content": user_content}
        ]

        provider = await cls.get_provider()
        return await provider.generate_response(messages, system_prompt=system_prompt)

    @classmethod
    async def suggest_sanción(cls, username: str, incident_description: str, bot: discord.Client | None = None) -> str:
        """Mantiene compatibilidad con la firma y ortografía en español original."""
        return await cls.suggest_sanction(username, incident_description, bot=bot)

import json
import logging
import discord
from datetime import datetime
from typing import Any, Dict, List, Optional

import config
from bot.repositories.complaints_repo import ComplaintsRepository
from bot.services.agonia_service import AgoniaService

logger = logging.getLogger("ComplaintsService")

VALID_COMPLAINT_TYPES = {
    "dkp": "DKP Injusto",
    "staff": "Problema con Staff",
    "guild": "Problema con Guild",
    "other": "Otro / Apelación",
}

VALID_STATES = ["pendiente", "tomado", "esperando_usuario", "respondido", "resuelto", "denegado"]


class ComplaintsService:
    @staticmethod
    def sanitize_text(value: Optional[str], max_length: int = 2000) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if len(text) > max_length:
            text = text[: max_length - 1].rstrip()
        return text

    @staticmethod
    def build_panel_embed() -> discord.Embed:
        embed = discord.Embed(
            title="⚖️ SISTEMA DE RECLAMOS",
            description=(
                "Selecciona el tipo de reclamo y completa el formulario breve. "
                "Úsalo para temas de DKP, staff, guild o apelaciones."
            ),
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="Tipos disponibles",
            value=(
                "• DKP Injusto\n"
                "• Problema con Staff\n"
                "• Problema con Guild\n"
                "• Otro / Apelación"
            ),
            inline=False,
        )
        embed.add_field(
            name="Canales del flujo",
            value=(
                f"Panel: <#{config.COMPLAINTS_PANEL_CHANNEL_ID}>\n"
                f"Staff: <#{config.COMPLAINTS_STAFF_CHANNEL_ID}>\n"
                f"Historial: <#{config.COMPLAINTS_HISTORY_CHANNEL_ID}>"
            ),
            inline=False,
        )
        embed.set_footer(text="El staff revisará cada caso y te mantendrá informado por DM.")
        return embed

    @staticmethod
    def build_case_embed(case: Dict[str, Any]) -> discord.Embed:
        embed = discord.Embed(
            title=f"⚖️ Reclamo #{case['id']} | {case.get('type', 'Sin tipo')}",
            description=ComplaintsService.sanitize_text(case.get("complaint_text", "Sin detalles"), 1000),
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Usuario", value=f"<@{case['requester_id']}>", inline=True)
        embed.add_field(name="Personaje", value=ComplaintsService.sanitize_text(case.get("character_name") or "—", 100), inline=True)
        embed.add_field(name="Estado", value=case.get("status", "pendiente").capitalize(), inline=True)
        embed.add_field(name="Staff asignado", value=ComplaintsService.sanitize_text(case.get("assigned_staff_name") or "Sin asignar", 100), inline=True)
        embed.add_field(name="Fecha", value=case.get("created_at") or "Desconocida", inline=True)
        embed.add_field(name="Evidencia", value=ComplaintsService.sanitize_text(case.get("evidence") or "Sin evidencia", 500), inline=False)
        embed.set_footer(text="Usa los botones para gestionar el caso.")
        return embed

    @staticmethod
    def build_history_embed(case: Dict[str, Any], history: List[Dict[str, Any]]) -> discord.Embed:
        embed = discord.Embed(
            title=f"📜 Historial Reclamo #{case['id']}",
            description=f"Tipo: {case.get('type', 'Sin tipo')} • Estado: {case.get('status', 'pendiente')}",
            color=discord.Color.dark_green(),
        )
        if not history:
            embed.add_field(name="Eventos", value="Sin eventos registrados todavía.", inline=False)
            return embed

        lines = []
        for entry in history:
            actor = entry.get("actor_name") or "Sistema"
            lines.append(
                f"• {entry.get('created_at') or '—'} | {entry.get('new_status') or '—'} | {actor}: {entry.get('action_description') or 'Sin detalle'}"
            )
        embed.add_field(name="Eventos", value="\n".join(lines[-10:]), inline=False)
        return embed

    @staticmethod
    def build_final_embed(case: Dict[str, Any], outcome: str) -> discord.Embed:
        color = discord.Color.green() if outcome == "resuelto" else discord.Color.red()
        embed = discord.Embed(
            title=f"✅ Reclamo #{case['id']} {outcome.upper()}" if outcome == "resuelto" else f"❌ Reclamo #{case['id']} DENEGADO",
            description=ComplaintsService.sanitize_text(case.get("resolution") or case.get("resolved_reason") or "Sin detalle", 1000),
            color=color,
        )
        embed.add_field(name="Usuario", value=f"<@{case['requester_id']}>", inline=True)
        embed.add_field(name="Tipo", value=case.get("type", "Sin tipo"), inline=True)
        embed.add_field(name="Personaje", value=ComplaintsService.sanitize_text(case.get("character_name") or "—", 100), inline=True)
        embed.add_field(name="Staff resolutor", value=ComplaintsService.sanitize_text(case.get("resolved_by_name") or case.get("assigned_staff_name") or "—", 100), inline=True)
        embed.add_field(name="Fecha", value=case.get("resolved_at") or case.get("updated_at") or "Desconocida", inline=True)
        embed.set_footer(text="Este mensaje queda registrado en el historial del sistema.")
        return embed

    @staticmethod
    async def is_staff(member: discord.Member) -> bool:
        return await AgoniaService.is_staff(member)

    @staticmethod
    async def send_staff_log(bot: discord.Client, message: str) -> None:
        channel = bot.get_channel(config.COMPLAINTS_STAFF_LOG_CHANNEL_ID)
        if channel is None:
            try:
                channel = await bot.fetch_channel(config.COMPLAINTS_STAFF_LOG_CHANNEL_ID)
            except Exception as exc:
                logger.warning("No se pudo obtener canal de log de reclamos: %s", exc)
                return
        try:
            await channel.send(message)
        except Exception as exc:
            logger.warning("No se pudo enviar log de reclamos: %s", exc)

    @staticmethod
    async def send_history_log(bot: discord.Client, case: Dict[str, Any], actor: Any, action: str, summary: str, status: str) -> Optional[discord.Message]:
        channel = bot.get_channel(config.COMPLAINTS_HISTORY_CHANNEL_ID)
        if channel is None:
            try:
                channel = await bot.fetch_channel(config.COMPLAINTS_HISTORY_CHANNEL_ID)
            except Exception as exc:
                logger.warning("No se pudo obtener canal de historial de reclamos: %s", exc)
                return None

        actor_name = getattr(actor, "display_name", None) or getattr(actor, "name", None) or "Sistema"
        embed = discord.Embed(
            title=f"📝 {action}",
            description=summary,
            color=discord.Color.orange(),
        )
        embed.add_field(name="Caso", value=f"#{case['id']}", inline=True)
        embed.add_field(name="Tipo", value=case.get("type", "Sin tipo"), inline=True)
        embed.add_field(name="Usuario", value=f"<@{case['requester_id']}>", inline=True)
        embed.add_field(name="Personaje", value=ComplaintsService.sanitize_text(case.get("character_name") or "—", 100), inline=True)
        embed.add_field(name="Staff", value=actor_name, inline=True)
        embed.add_field(name="Estado", value=status, inline=True)
        embed.set_footer(text=f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        try:
            message = await channel.send(embed=embed)
            await ComplaintsRepository.update_complaint(case["id"], {"history_message_id": message.id})
            return message
        except Exception as exc:
            logger.warning("No se pudo registrar el historial de reclamos: %s", exc)
            return None

    @staticmethod
    async def notify_requester(case: Dict[str, Any], bot: discord.Client, content: str) -> bool:
        if not case:
            return False
        user = bot.get_user(case["requester_id"])
        if user is None:
            try:
                user = await bot.fetch_user(case["requester_id"])
            except Exception as exc:
                logger.warning("No se pudo obtener usuario para DM: %s", exc)
                return False
        try:
            await user.send(content)
            return True
        except Exception as exc:
            logger.warning("No se pudo enviar DM: %s", exc)
            return False

    @staticmethod
    async def create_case(bot: discord.Client, interaction: discord.Interaction, complaint_type: str, payload: Dict[str, str], source_panel_channel_id: Optional[int] = None) -> Dict[str, Any]:
        requester_id = interaction.user.id
        requester_name = interaction.user.name
        requester_display_name = getattr(interaction.user, "display_name", interaction.user.name)
        character_name = self.sanitize_text(payload.get("character_name") or payload.get("personaje_principal") or payload.get("asunto") or "")
        complaint_text = self.sanitize_text(payload.get("complaint_text") or payload.get("descripcion") or payload.get("que_ocurrio") or payload.get("detalle") or "")
        evidence = self.sanitize_text(payload.get("evidence") or payload.get("evidencia") or payload.get("evidencia_o_testigos") or "")

        existing = await ComplaintsRepository.find_active_complaint_by_user(requester_id)
        if existing:
            raise ValueError("Ya tienes un reclamo activo pendiente. Espera a que sea atendido antes de abrir otro.")

        form_payload_json = json.dumps(payload, ensure_ascii=False)
        case_id = await ComplaintsRepository.create_complaint(
            requester_id=requester_id,
            requester_name=requester_name,
            requester_display_name=requester_display_name,
            complaint_type=complaint_type,
            character_name=character_name,
            complaint_text=complaint_text,
            form_payload_json=form_payload_json,
            evidence=evidence,
            status="pendiente",
            source_panel_channel_id=source_panel_channel_id or config.COMPLAINTS_PANEL_CHANNEL_ID,
        )
        case = await ComplaintsRepository.get_complaint(case_id)
        if not case:
            raise RuntimeError("No se pudo recuperar el reclamo creado.")

        await ComplaintsRepository.create_history(
            case_id,
            requester_id,
            requester_name,
            "",
            "pendiente",
            "Caso creado desde el panel público",
        )
        await ComplaintsService.publish_case_message(bot, case)
        await ComplaintsService.send_history_log(bot, case, interaction.user, "Caso creado", "Se inició un nuevo reclamo desde el panel público.", "pendiente")
        await ComplaintsService.notify_requester(
            case,
            bot,
            f"✅ Tu reclamo #{case_id} ha sido registrado correctamente. El staff lo revisará pronto.",
        )
        await ComplaintsService.send_staff_log(bot, f"Nuevo reclamo #{case_id} creado por {requester_name} ({requester_id}).")
        return case

    @staticmethod
    async def update_case(bot: discord.Client, case: Dict[str, Any], actor: Any, new_status: str, action: str, summary: str, *, assigned_staff_id: Optional[int] = None, assigned_staff_name: Optional[str] = None, resolution: Optional[str] = None, resolved_reason: Optional[str] = None, resolved_by_id: Optional[int] = None, resolved_by_name: Optional[str] = None) -> Dict[str, Any]:
        updates: Dict[str, Any] = {"status": new_status, "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}
        if assigned_staff_id is not None:
            updates["assigned_staff_id"] = assigned_staff_id
        if assigned_staff_name is not None:
            updates["assigned_staff_name"] = assigned_staff_name
        if resolution is not None:
            updates["resolution"] = resolution
        if resolved_reason is not None:
            updates["resolved_reason"] = resolved_reason
        if resolved_by_id is not None:
            updates["resolved_by_id"] = resolved_by_id
        if resolved_by_name is not None:
            updates["resolved_by_name"] = resolved_by_name
        if new_status in {"resuelto", "denegado"}:
            updates["resolved_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        if new_status == "respondido":
            updates["responded_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        await ComplaintsRepository.update_complaint(case["id"], updates)
        await ComplaintsRepository.create_history(case["id"], getattr(actor, "id", 0), getattr(actor, "name", "Sistema"), case.get("status", "pendiente"), new_status, action)
        case = await ComplaintsRepository.get_complaint(case["id"])
        await ComplaintsService.publish_case_message(bot, case)
        await ComplaintsService.send_history_log(bot, case, actor, action, summary, new_status)
        return case

    @staticmethod
    async def publish_case_message(bot: discord.Client, case: Dict[str, Any]) -> Optional[discord.Message]:
        channel = bot.get_channel(config.COMPLAINTS_STAFF_CHANNEL_ID)
        if channel is None:
            try:
                channel = await bot.fetch_channel(config.COMPLAINTS_STAFF_CHANNEL_ID)
            except Exception as exc:
                logger.warning("No se pudo obtener canal de staff para el reclamo: %s", exc)
                return None

        from bot.views.complaints_views import ComplaintCaseView

        embed = ComplaintsService.build_case_embed(case)
        view = ComplaintCaseView(case)
        try:
            existing_message_id = case.get("ticket_message_id")
            if existing_message_id and hasattr(channel, "fetch_message"):
                try:
                    message = await channel.fetch_message(existing_message_id)
                    await message.edit(embed=embed, view=view)
                    return message
                except Exception:
                    pass
            msg = await channel.send(embed=embed, view=view)
            await ComplaintsRepository.update_complaint(case["id"], {"ticket_channel_id": channel.id, "ticket_message_id": msg.id})
            bot.add_view(view)
            return msg
        except Exception as exc:
            logger.warning("No se pudo publicar el caso de reclamo: %s", exc)
            return None

    @staticmethod
    async def republish_case(bot: discord.Client, case: Dict[str, Any]) -> bool:
        msg = await ComplaintsService.publish_case_message(bot, case)
        if msg is None:
            return False
        await ComplaintsService.send_history_log(bot, case, {"id": 0, "name": "Sistema"}, "Republicación", "Se republicó el caso porque el mensaje original faltaba o se dañó.", case.get("status", "pendiente"))
        return True

import logging
import re
import discord
from datetime import datetime
from typing import Optional, Dict, Any, List
from bot.repositories.agonia_repo import AgoniaRepository
import config

logger = logging.getLogger("AgoniaService")

VALID_STATES = [
    "pendiente",
    "tomado",
    "mas_datos",
    "aprobado",
    "activo",
    "pausado",
    "denegado",
    "finalizado"
]

FRAG_PATTERN = re.compile(r"Frag\s*\d{1,2}(?:\s*✅)?", re.IGNORECASE)

class HarukoPublicNoteService:
    @staticmethod
    def transform_public_note(existing_note: str, fragment_number: int) -> str:
        marker = f"Frag {fragment_number}"
        if not existing_note:
            return marker

        if FRAG_PATTERN.search(existing_note):
            new_note = FRAG_PATTERN.sub(marker, existing_note)
            return new_note

        return f"{existing_note} | {marker}"

    @staticmethod
    async def update_public_note_via_wow(adapter, character_name: str, new_note_text: str) -> Dict[str, Any]:
        if not hasattr(adapter, "world_session") or adapter.world_session is None:
            return {
                "success": False,
                "reason": "No hay sesión activa de WorldSession disponible en el adaptador."
            }

        world_session = adapter.world_session
        if not hasattr(world_session, "send_guild_motd"):
            return {
                "success": False,
                "reason": "El adaptador WoW no soporta escritura de nota pública en el protocolo actual."
            }

        # Actualmente no hay soporte real en WorldSession para nota pública superior.
        return {
            "success": False,
            "reason": "Soporte de nota pública no implementado en el adaptador actual."
        }

class AgoniaService:
    @staticmethod
    def build_normativa_panel_embed() -> discord.Embed:
        embed = discord.Embed(
            title="🛡️ Normativa Agonía de Sombras",
            description=(
                "Lee las reglas y pulsa **Iniciar Solicitud** para comenzar tu caso. "
                "El staff revisará tu solicitud en el canal de Agonía y te mantendrá informado."
            ),
            color=discord.Color.gold()
        )
        embed.add_field(name="Canales principales", value=(
            f"- Tickets de Agonía: <#{config.AGONIA_TICKETS_CHANNEL_ID}>\n"
            f"- Lista de fragmentadores: <#{config.LISTA_FRAGMENTEADORES_CHANNEL_ID}>\n"
            f"- Finalizados: <#{config.AGONIAS_FINALIZADAS_CHANNEL_ID}>"
        ), inline=False)
        embed.add_field(name="Estados del proceso", value=(
            "pendiente, tomado, mas_datos, aprobado, activo, pausado, denegado, finalizado"
        ), inline=False)
        embed.add_field(name="Puntos importantes", value=(
            "- El staff puede pedir más datos o pausar el caso.\n"
            "- La tarjeta activa se publicará después de la aprobación.\n"
            "- Cuando un caso finaliza, se publica un resumen en el canal de finalizados."
        ), inline=False)
        embed.set_footer(text="El panel se puede reinstalar si el mensaje se pierde.")
        return embed

    @staticmethod
    def build_ticket_embed(case: Dict[str, Any]) -> discord.Embed:
        embed = discord.Embed(
            title=f"⚔️ Ticket | Caso #{case['id']} | Frag {case['fragment_number']}",
            description=(
                f"Personaje: {case.get('character_name', 'Desconocido')}\n"
                f"Clase / Spec: {case.get('class_spec', 'Desconocido')}\n"
                f"Estado Agonía: {case.get('agonia_status', 'Desconocido')}\n"
                f"Fragmentos actuales: {case.get('fragment_number', 0)}\n\n"
                f"{case.get('description', '')}"
            ),
            color=discord.Color.dark_magenta()
        )
        embed.add_field(name="Estado", value=case["status"].capitalize(), inline=True)
        embed.add_field(name="Solicitante", value=f"<@{case['requester_id']}>", inline=True)
        embed.add_field(name="Staff asignado", value=case.get("assigned_staff_name") or "Sin asignar", inline=True)
        embed.set_footer(text="Este mensaje representa un caso de Agonía. Usa los botones para avanzar el proceso.")
        return embed

    @staticmethod
    def build_active_card_embed(case: Dict[str, Any]) -> discord.Embed:
        embed = discord.Embed(
            title=f"🛡️ Agonía Activa | Caso #{case['id']} | Frag {case['fragment_number']}",
            description=case.get('description', 'Sin detalles adicionales.'),
            color=discord.Color.purple()
        )
        embed.add_field(name="Estado del caso", value=case.get('status', 'pendiente').capitalize(), inline=True)
        embed.add_field(name="Agonía actual", value=case.get('agonia_status', 'Desconocida'), inline=True)
        embed.add_field(name="Fragmentos actuales", value=str(case.get('fragment_number', 0)), inline=True)
        embed.add_field(name="Personaje / Clase", value=f"{case.get('character_name', 'Desconocido')} / {case.get('class_spec', 'Desconocido')}", inline=False)
        embed.add_field(name="Solicitante", value=f"<@{case['requester_id']}>", inline=True)
        embed.add_field(name="Staff asignado", value=case.get('assigned_staff_name') or 'Sin asignar', inline=True)
        if case.get('public_note'):
            embed.add_field(name="Nota pública", value=case['public_note'], inline=False)
        embed.set_footer(text="Usa los botones para actualizar el estado y el progreso.")
        return embed

    @staticmethod
    def build_history_embed(case: Dict[str, Any], history: List[Dict[str, Any]]) -> discord.Embed:
        embed = discord.Embed(
            title=f"📜 Historial | Caso #{case['id']}",
            description=f"Estado actual: **{case['status']}**",
            color=discord.Color.blurple()
        )
        if not history:
            embed.add_field(name="Historial", value="No hay cambios registrados aún.", inline=False)
            return embed

        lines = []
        for item in history:
            created_at = item.get("created_at") or "Desconocido"
            lines.append(f"• **{item['new_status']}** por <@{item['actor_id']}> el {created_at}\n  _{item.get('note', '')}_")
        embed.add_field(name="Historial de evento", value="\n".join(lines), inline=False)
        return embed

    @staticmethod
    async def is_staff(member: discord.Member) -> bool:
        roles = [r.id for r in member.roles]
        return any(r in [
            config.ADMINISTRADOR_MASTER_BOT_ROLE_ID,
            config.OFICIAL_ROLE_ID,
            config.GUILD_MASTER_ROLE_ID,
            config.CONCILIO_ROLE_ID
        ] for r in roles)

    @staticmethod
    async def is_decider(member: discord.Member) -> bool:
        roles = [r.id for r in member.roles]
        return any(r in [
            config.ADMINISTRADOR_MASTER_BOT_ROLE_ID,
            config.GUILD_MASTER_ROLE_ID,
            config.CONCILIO_ROLE_ID
        ] for r in roles)

    @staticmethod
    async def notify_requester(case: Dict[str, Any], bot: discord.Client, content: str) -> bool:
        if not case:
            return False
        user = bot.get_user(case["requester_id"])
        if not user:
            try:
                user = await bot.fetch_user(case["requester_id"])
            except Exception as e:
                logger.warning(f"No se pudo obtener el usuario solicitante: {e}")
                return False
        result = await AgoniaService.send_dm(user, content)
        if not result:
            await AgoniaService.send_staff_log(bot, f"No se pudo enviar DM a <@{case['requester_id']}> para caso #{case['id']}.")
        return result

    @staticmethod
    def allowed_status_transitions(current_status: str) -> List[str]:
        transitions = {
            "pendiente": ["tomado", "denegado"],
            "tomado": ["mas_datos", "aprobado", "pausado", "denegado"],
            "mas_datos": ["tomado", "denegado"],
            "aprobado": ["activo", "pausado", "denegado"],
            "activo": ["pausado", "finalizado", "denegado"],
            "pausado": ["activo", "finalizado", "denegado"],
            "denegado": [],
            "finalizado": []
        }
        return transitions.get(current_status, [])

    @staticmethod
    def status_button_style(status: str) -> discord.ButtonStyle:
        style_map = {
            "pendiente": discord.ButtonStyle.secondary,
            "tomado": discord.ButtonStyle.primary,
            "mas_datos": discord.ButtonStyle.secondary,
            "aprobado": discord.ButtonStyle.success,
            "activo": discord.ButtonStyle.success,
            "pausado": discord.ButtonStyle.danger,
            "denegado": discord.ButtonStyle.danger,
            "finalizado": discord.ButtonStyle.success
        }
        return style_map.get(status, discord.ButtonStyle.secondary)

    @staticmethod
    async def send_staff_log(bot: discord.Client, message: str):
        channel = bot.get_channel(config.AGONIA_STAFF_LOG_CHANNEL_ID)
        if not channel:
            try:
                channel = await bot.fetch_channel(config.AGONIA_STAFF_LOG_CHANNEL_ID)
            except Exception as e:
                logger.error(f"No se puede fetch channel de log de staff: {e}")
                return
        try:
            await channel.send(message)
        except Exception as e:
            logger.error(f"Error enviando log de staff: {e}")

    @staticmethod
    async def send_dm(user: discord.User, content: str):
        try:
            await user.send(content)
            return True
        except Exception as e:
            logger.warning(f"No se pudo enviar DM a {user.id}: {e}")
            return False

    @staticmethod
    async def get_case(case_id: int) -> Optional[Dict[str, Any]]:
        return await AgoniaRepository.get_case(case_id)

    @staticmethod
    async def prepare_public_note_for_case(case: Dict[str, Any]) -> str:
        existing_note = case.get("public_note") or ""
        transformed = HarukoPublicNoteService.transform_public_note(existing_note, case["fragment_number"])
        await AgoniaRepository.update_case(case["id"], {
            "public_note": transformed,
            "haruko_sync_state": "pending",
            "haruko_error": None
        })
        return transformed

    @staticmethod
    async def sync_public_note_with_wow(bot: discord.Client, case: Dict[str, Any]) -> Dict[str, Any]:
        note_text = case.get("public_note")
        if not note_text:
            return {
                "success": False,
                "reason": "No hay texto de nota pública preparado."
            }

        adapter = getattr(getattr(bot, "bridge_service", None), "adapter", None)
        if not adapter:
            return {
                "success": False,
                "reason": "No se encontró adaptador WoW en el bot para sincronizar nota pública."
            }

        # Nota: el adaptador actual no ofrece un método específico para escribir nota pública superior.
        result = await HarukoPublicNoteService.update_public_note_via_wow(adapter, config.WOW_CHARACTER, note_text)
        new_state = "success" if result.get("success") else "failed"
        await AgoniaRepository.update_case(case["id"], {
            "haruko_sync_state": new_state,
            "haruko_error": result.get("reason")
        })
        return result

    @staticmethod
    def build_finalized_embed(case: Dict[str, Any]) -> discord.Embed:
        embed = discord.Embed(
            title=f"✅ Agonía Completada | Caso #{case['id']} | Frag {case['fragment_number']}",
            description=case.get("description", "Sin detalles adicionales."),
            color=discord.Color.green()
        )
        embed.add_field(name="Personaje", value=case.get("character_name", "Desconocido"), inline=True)
        embed.add_field(name="Solicitante", value=f"<@{case['requester_id']}> {case.get('requester_name','')} ", inline=True)
        embed.add_field(name="Staff encargado", value=case.get("assigned_staff_name") or "Sin asignar", inline=True)
        embed.add_field(name="Estado final", value=case.get("status", "finalizado").capitalize(), inline=True)
        # Preferir started_at/finished_at si están presentes
        embed.add_field(name="Fecha inicio", value=case.get("started_at") or case.get("created_at", "Desconocida"), inline=True)
        embed.add_field(name="Fecha de finalización", value=case.get("finished_at") or case.get("updated_at", "Desconocida"), inline=True)
        if case.get("public_note"):
            embed.add_field(name="Nota pública preparada", value=case["public_note"], inline=False)
        if case.get("haruko_sync_state"):
            embed.add_field(name="Haruko Sync", value=case.get("haruko_sync_state"), inline=True)
        if case.get("haruko_error"):
            embed.add_field(name="Error Haruko", value=case.get("haruko_error"), inline=False)
        embed.set_footer(text="Caso finalizado en Agonía de Sombras.")
        return embed

    @staticmethod
    async def _fetch_channel(bot: discord.Client, channel_id: int) -> Optional[discord.TextChannel]:
        channel = bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception as e:
                logger.error(f"No se pudo obtener el canal {channel_id}: {e}")
                return None
        if not hasattr(channel, 'send'):
            logger.error(f"El canal {channel_id} no admite envío de mensajes: tipo={type(channel).__name__}")
            return None
        return channel

    @staticmethod
    async def create_case_messages(bot: discord.Client, case: Dict[str, Any]) -> Dict[str, Any]:
        from bot.views.agonia_views import AgoniaCaseButtonsView

        ticket_channel = await AgoniaService._fetch_channel(bot, config.AGONIA_TICKETS_CHANNEL_ID)
        if ticket_channel:
            ticket_embed = AgoniaService.build_ticket_embed(case)
            ticket_view = AgoniaCaseButtonsView(case)
            try:
                ticket_msg = await ticket_channel.send(embed=ticket_embed, view=ticket_view)
                await AgoniaRepository.update_case(case["id"], {
                    "ticket_channel_id": ticket_channel.id,
                    "ticket_message_id": ticket_msg.id
                })
                case["ticket_channel_id"] = ticket_channel.id
                case["ticket_message_id"] = ticket_msg.id
                bot.add_view(ticket_view)
            except Exception as e:
                logger.error(f"No se pudo crear el mensaje de ticket en canal de Agonía: {e}")
                await AgoniaService.send_staff_log(bot, f"No se pudo crear ticket de Agonía #{case['id']} en canal {config.AGONIA_TICKETS_CHANNEL_ID}: {e}")
        else:
            logger.warning(f"No se pudo ubicar el canal de tickets de Agonía para crear el ticket del caso {case['id']}")
            await AgoniaService.send_staff_log(bot, f"No se pudo ubicar el canal de tickets de Agonía {config.AGONIA_TICKETS_CHANNEL_ID} para caso #{case['id']}")

        active_channel = await AgoniaService._fetch_channel(bot, config.LISTA_FRAGMENTEADORES_CHANNEL_ID)
        final_channel = await AgoniaService._fetch_channel(bot, config.AGONIAS_FINALIZADAS_CHANNEL_ID)

        if case["status"] in ["aprobado", "activo", "pausado"] and active_channel:
            active_embed = AgoniaService.build_active_card_embed(case)
            active_view = AgoniaCaseButtonsView(case)
            try:
                active_msg = await active_channel.send(embed=active_embed, view=active_view)
                await AgoniaRepository.update_case(case["id"], {"active_card_message_id": active_msg.id})
                case["active_card_message_id"] = active_msg.id
                bot.add_view(active_view)
            except Exception as e:
                logger.error(f"No se pudo crear la tarjeta activa en la lista de fragmentadores: {e}")

        if case["status"] == "finalizado" and final_channel:
            final_embed = AgoniaService.build_finalized_embed(case)
            try:
                final_msg = await final_channel.send(embed=final_embed)
                await AgoniaRepository.update_case(case["id"], {"final_message_id": final_msg.id})
                case["final_message_id"] = final_msg.id
            except Exception as e:
                logger.error(f"No se pudo crear el mensaje finalizado en canal de Agonías finalizadas: {e}")

        return case

    @staticmethod
    async def refresh_case_messages(bot: discord.Client, case: Dict[str, Any]):
        from bot.views.agonia_views import AgoniaCaseButtonsView

        ticket_channel = await AgoniaService._fetch_channel(bot, config.AGONIA_TICKETS_CHANNEL_ID)
        active_channel = await AgoniaService._fetch_channel(bot, config.LISTA_FRAGMENTEADORES_CHANNEL_ID)
        final_channel = await AgoniaService._fetch_channel(bot, config.AGONIAS_FINALIZADAS_CHANNEL_ID)

        case_view = AgoniaCaseButtonsView(case, read_only=case["status"] in ["denegado", "finalizado"])
        bot.add_view(case_view)

        if ticket_channel and case.get("ticket_message_id"):
            try:
                ticket_msg = await ticket_channel.fetch_message(case["ticket_message_id"])
                await ticket_msg.edit(embed=AgoniaService.build_ticket_embed(case), view=case_view)
            except Exception as e:
                logger.warning(f"No se pudo actualizar el mensaje de ticket existente: {e}")
                if ticket_channel:
                    try:
                        new_msg = await ticket_channel.send(embed=AgoniaService.build_ticket_embed(case), view=case_view)
                        await AgoniaRepository.update_case(case["id"], {"ticket_message_id": new_msg.id})
                        case["ticket_message_id"] = new_msg.id
                    except Exception as e2:
                        logger.error(f"Error creando nuevo mensaje de ticket: {e2}")

        if case["status"] in ["denegado", "finalizado"]:
            if case.get("active_card_message_id") and active_channel:
                try:
                    active_msg = await active_channel.fetch_message(case["active_card_message_id"])
                    await active_msg.delete()
                except Exception:
                    pass
                await AgoniaRepository.update_case(case["id"], {"active_card_message_id": None})
                case["active_card_message_id"] = None
        else:
            if active_channel:
                if case.get("active_card_message_id"):
                    try:
                        active_msg = await active_channel.fetch_message(case["active_card_message_id"])
                        await active_msg.edit(embed=AgoniaService.build_active_card_embed(case), view=case_view)
                    except Exception as e:
                        logger.warning(f"No se pudo actualizar la tarjeta activa existente: {e}")
                        try:
                            new_msg = await active_channel.send(embed=AgoniaService.build_active_card_embed(case), view=case_view)
                            await AgoniaRepository.update_case(case["id"], {"active_card_message_id": new_msg.id})
                            case["active_card_message_id"] = new_msg.id
                        except Exception as e2:
                            logger.error(f"Error creando nueva tarjeta activa: {e2}")
                else:
                    try:
                        new_msg = await active_channel.send(embed=AgoniaService.build_active_card_embed(case), view=case_view)
                        await AgoniaRepository.update_case(case["id"], {"active_card_message_id": new_msg.id})
                        case["active_card_message_id"] = new_msg.id
                    except Exception as e:
                        logger.error(f"Error creando tarjeta activa ausente: {e}")

        if case["status"] == "finalizado" and final_channel:
            try:
                if case.get("final_message_id"):
                    final_msg = await final_channel.fetch_message(case["final_message_id"])
                    await final_msg.edit(embed=AgoniaService.build_finalized_embed(case))
                else:
                    final_msg = await final_channel.send(embed=AgoniaService.build_finalized_embed(case))
                    await AgoniaRepository.update_case(case["id"], {"final_message_id": final_msg.id})
                    case["final_message_id"] = final_msg.id
            except Exception as e:
                logger.error(f"Error creando/actualizando mensaje finalizado: {e}")

    @staticmethod
    async def register_persistent_case_views(bot: discord.Client):
        from bot.views.agonia_views import AgoniaCaseButtonsView
        # Pre-register views con botones simples en caso de recrearse la sesión
        bot.add_view(AgoniaCaseButtonsView(read_only=False))
        bot.add_view(AgoniaCaseButtonsView(read_only=True))

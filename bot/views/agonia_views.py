import logging
import re
import discord
from datetime import datetime
from typing import Optional, Dict, Any
from discord import app_commands
from bot.repositories.agonia_repo import AgoniaRepository
from bot.services.agonia_service import AgoniaService
import config

logger = logging.getLogger("AgoniaViews")

CASE_ID_PATTERN = re.compile(r"#(\d+)")

def _build_agonia_rules_embed() -> discord.Embed:
    """Construye el embed con las reglas de Agonía de Sombras."""
    embed = discord.Embed(
        title="🛡️ Normativa: Agonía de Sombras",
        description="Normativa Oficial de Fragmentadores\n\n**Lee atentamente antes de continuar:**",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="🧭 Requisitos de Elegibilidad",
        value=(
            "Para ingresar y permanecer en la Lista de Fragmentadores, deberás cumplir obligatoriamente con:\n\n"
            "• **Antigüedad**: Mínimo 3 meses en la guild, sin sanciones ni conductas que perjudiquen.\n"
            "• **Personajes activos**: Al menos 5 personajes activos en la guild.\n"
            "• **Aporte demostrable**: Asistencia regular, apoyo en raids, participación en actividades internas."
        ),
        inline=False
    )
    embed.add_field(
        name="⚔️ Rendimiento y Rol",
        value=(
            "• Mantener desempeño destacado y consistente con tu personaje.\n"
            "• Será evaluado rigurosamente por GMs y oficiales.\n"
            "• Deficiencias detectadas resultarán en suspensión inmediata sin derecho a reclamo.\n"
            "• Mínimo 3 raids en rol crítico (tanque o healer)."
        ),
        inline=False
    )
    embed.add_field(
        name="🛡️ Obligaciones del Fragmentador",
        value="El personaje fragmentador está obligado a proporcionar festines en cada raid donde reciba fragmentos, sin excepciones.",
        inline=False
    )
    embed.add_field(
        name="⚠️ Pérdida de Prioridad y Eliminación",
        value="Sin actividad en 2 raids consecutivos = eliminación automática de la lista. Medida definitiva, no negociable, no reversible.",
        inline=False
    )
    embed.add_field(
        name="📌 Fundamento de la Normativa",
        value="Esta normativa combate el abandono de responsabilidades sin aviso previo. Protege a jugadores activos y el ritmo de avance de la guild.",
        inline=False
    )
    embed.add_field(
        name="✨ Disposición Final",
        value="La fragmentación es un **privilegio, no un derecho**. Solo se otorga a quienes demuestren compromiso constante, responsabilidad, rendimiento adecuado y respeto colectivo.",
        inline=False
    )
    embed.set_footer(text="Si cumples los requisitos, pulsa 'Siguiente' para continuar con tu solicitud.")
    return embed

class AgoniaRulesView(discord.ui.View):
    """Vista que muestra las reglas y permite continuar al formulario."""
    def __init__(self):
        super().__init__(timeout=300)  # 5 minutos

    @discord.ui.button(label="Siguiente", style=discord.ButtonStyle.success, custom_id="agonia_rules_next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Abre el formulario de solicitud."""
        try:
            await interaction.response.send_modal(AgoniaRequestModal())
        except Exception as e:
            logger.exception("Error al abrir el modal de solicitud después de reglas")
            await interaction.response.send_message(
                "❌ Error al abrir el formulario. Intenta de nuevo.",
                ephemeral=True
            )

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.danger, custom_id="agonia_rules_cancel")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancela la solicitud."""
        await interaction.response.defer()
        await interaction.delete_original_response()

async def _handle_agony_request_start(interaction: discord.Interaction):
    logger.info(
        "Agonía solicitud iniciada por %s (%s) en canal %s",
        getattr(interaction.user, 'name', None),
        getattr(interaction.user, 'id', None),
        getattr(interaction.channel, 'id', None)
    )
    try:
        embed = _build_agonia_rules_embed()
        view = AgoniaRulesView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(
            "Embed de reglas enviado correctamente a %s (%s)",
            getattr(interaction.user, 'name', None),
            getattr(interaction.user, 'id', None)
        )
    except Exception as e:
        logger.exception("Error al abrir las reglas de solicitud de Agonía")
        try:
            await interaction.response.send_message(
                "❌ Error interno al abrir el panel de solicitud. Intenta de nuevo o reinicia el bot.",
                ephemeral=True
            )
        except Exception:
            logger.exception("Fallo adicional al enviar el mensaje de error después de un error en las reglas de Agonía")

class AgoniaPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Iniciar Solicitud", style=discord.ButtonStyle.success, custom_id="agonia_panel_start_request")
    async def start_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.debug(
            "Agonía panel botón start_request activado: user=%s id=%s channel=%s custom_id=%s",
            getattr(interaction.user, 'name', None),
            getattr(interaction.user, 'id', None),
            getattr(interaction.channel, 'id', None),
            getattr(button, 'custom_id', None)
        )
        await _handle_agony_request_start(interaction)

    @discord.ui.button(label="AGONIA MANUAL", style=discord.ButtonStyle.danger, custom_id="agonia_panel_agoniamanual")
    async def manual_complete(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Restringir acceso a staff/deciders
        if not (await AgoniaService.is_staff(interaction.user) or await AgoniaService.is_decider(interaction.user)):
            return await interaction.response.send_message("❌ No tienes permisos para registrar manualmente una Agonía.", ephemeral=True)

        # Abre un modal sencillo para registrar una agonía ya completada (mínimo campos)
        try:
            await interaction.response.send_modal(MinimalManualCompleteModal())
        except Exception:
            logger.exception("Error al abrir el modal de registro manual de Agonía")
            try:
                await interaction.response.send_message("❌ No se pudo abrir el modal de registro manual.", ephemeral=True)
            except Exception:
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        interaction_data = getattr(interaction, 'data', None)
        custom_id = None
        if isinstance(interaction_data, dict):
            custom_id = interaction_data.get('custom_id')

        logger.exception(
            "Error en la vista persistente de Agonía: interaction_id=%s custom_id=%s channel=%s user=%s id=%s",
            getattr(interaction, 'id', None),
            custom_id,
            getattr(interaction.channel, 'id', None),
            getattr(interaction.user, 'name', None),
            getattr(interaction.user, 'id', None),
            exc_info=error
        )
        try:
            await interaction.response.send_message(
                "❌ Error interno en el panel de Agonía.",
                ephemeral=True
            )
        except Exception:
            logger.exception("Fallo al intentar responder desde on_error en la vista de Agonía")

class LegacyAgoniaPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(self.LegacyStartRequestButton())

    class LegacyStartRequestButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Iniciar Solicitud", style=discord.ButtonStyle.success, custom_id="agonia_panel:start_request")

        async def callback(self, interaction: discord.Interaction):
            await _handle_agony_request_start(interaction)

class AgoniaCaseButtonsView(discord.ui.View):
    def __init__(self, case: Optional[Dict[str, Any]] = None, read_only: bool = False):
        super().__init__(timeout=None)
        self.case = case or {}
        self.read_only = read_only

        if read_only:
            self.add_item(self.RepublishButton())
            return

        self.add_item(self.TakeCaseButton())
        self.add_item(self.RequestMoreDataButton())
        self.add_item(self.ApproveButton())
        self.add_item(self.UpdateProgressButton())
        self.add_item(self.RemindDMButton())
        self.add_item(self.PauseButton())
        self.add_item(self.DenyButton())
        self.add_item(self.FinalizeButton())
        self.add_item(self.RepublishButton())

    @staticmethod
    def _extract_case_id(interaction: discord.Interaction) -> Optional[int]:
        if not interaction.message or not interaction.message.embeds:
            return None
        title = interaction.message.embeds[0].title or ""
        match = CASE_ID_PATTERN.search(title)
        return int(match.group(1)) if match else None

    class TakeCaseButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Tomar caso", style=discord.ButtonStyle.primary, custom_id="agonia_take_case")

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            case_id = AgoniaCaseButtonsView._extract_case_id(interaction)
            if not case_id:
                return await interaction.followup.send("No se pudo determinar el ID del caso.", ephemeral=True)

            case = await AgoniaRepository.get_case(case_id)
            if not case:
                return await interaction.followup.send("No se encontró el caso.", ephemeral=True)

            if not await AgoniaService.is_staff(interaction.user):
                return await interaction.followup.send("❌ No tienes permisos para tomar este caso.", ephemeral=True)

            await AgoniaRepository.create_history(case_id, interaction.user.id, interaction.user.name, case["status"], "tomado", "Caso tomado por staff")
            await AgoniaRepository.update_case(case_id, {
                "status": "tomado",
                "assigned_staff_id": interaction.user.id,
                "assigned_staff_name": interaction.user.name
            })
            case = await AgoniaRepository.get_case(case_id)
            await AgoniaService.send_staff_log(interaction.client, f"Caso #{case_id} tomado por {interaction.user.name}.")
            await AgoniaService.notify_requester(case, interaction.client, f"Tu caso #{case_id} ha sido tomado por {interaction.user.name}. Próximamente te informaremos sobre el siguiente paso.")
            await AgoniaService.refresh_case_messages(interaction.client, case)
            await interaction.followup.send(f"✅ Caso #{case_id} marcado como **tomado**.", ephemeral=True)

    class RequestMoreDataButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Pedir más datos", style=discord.ButtonStyle.secondary, custom_id="agonia_more_data")

        async def callback(self, interaction: discord.Interaction):
            if not await AgoniaService.is_staff(interaction.user):
                return await interaction.response.send_message("❌ No tienes permisos para pedir más datos.", ephemeral=True)
            case_id = AgoniaCaseButtonsView._extract_case_id(interaction)
            if not case_id:
                return await interaction.response.send_message("No se pudo determinar el ID del caso.", ephemeral=True)
            await interaction.response.send_modal(AgoniaMoreDataModal(case_id))

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.exception("Error en la vista de botones de Agonía")
        try:
            await interaction.response.send_message(
                "❌ Error interno en los botones de Agonía.",
                ephemeral=True
            )
        except Exception:
            pass

    class ApproveButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Aprobar", style=discord.ButtonStyle.success, custom_id="agonia_approve")

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            case_id = AgoniaCaseButtonsView._extract_case_id(interaction)
            if not case_id:
                return await interaction.followup.send("No se pudo determinar el ID del caso.", ephemeral=True)

            case = await AgoniaRepository.get_case(case_id)
            if not case:
                return await interaction.followup.send("No se encontró el caso.", ephemeral=True)

            if not await AgoniaService.is_decider(interaction.user):
                return await interaction.followup.send("❌ Solo Guild Master, Concilio o Admin Master BOT pueden aprobar.", ephemeral=True)

            await AgoniaRepository.create_history(case_id, interaction.user.id, interaction.user.name, case["status"], "aprobado", "Aprobado por staff")
            await AgoniaRepository.update_case(case_id, {
                "status": "aprobado",
                "assigned_staff_id": interaction.user.id,
                "assigned_staff_name": interaction.user.name,
                "approved_by_user_id": interaction.user.id,
                "approved_by_name": interaction.user.name,
                "started_at": datetime.utcnow().isoformat(sep=" ", timespec="seconds")
            })
            case = await AgoniaRepository.get_case(case_id)
            await AgoniaService.prepare_public_note_for_case(case)
            await AgoniaService.send_staff_log(interaction.client, f"Caso #{case_id} aprobado por {interaction.user.name}.")
            await AgoniaService.notify_requester(case, interaction.client, f"✅ Tu caso #{case_id} fue aprobado. Pronto aparecerá en la lista de fragmentadores.")
            await AgoniaService.refresh_case_messages(interaction.client, case)
            await interaction.followup.send(f"✅ Caso #{case_id} marcado como **aprobado**.", ephemeral=True)

    class PauseButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Pausar", style=discord.ButtonStyle.danger, custom_id="agonia_pause")

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            case_id = AgoniaCaseButtonsView._extract_case_id(interaction)
            if not case_id:
                return await interaction.followup.send("No se pudo determinar el ID del caso.", ephemeral=True)
            case = await AgoniaRepository.get_case(case_id)
            if not case:
                return await interaction.followup.send("No se encontró el caso.", ephemeral=True)
            if not await AgoniaService.is_staff(interaction.user):
                return await interaction.followup.send("❌ No tienes permisos para pausar el caso.", ephemeral=True)
            await AgoniaRepository.create_history(case_id, interaction.user.id, interaction.user.name, case["status"], "pausado", "Caso pausado")
            await AgoniaRepository.update_case(case_id, {"status": "pausado", "assigned_staff_id": interaction.user.id, "assigned_staff_name": interaction.user.name})
            case = await AgoniaRepository.get_case(case_id)
            await AgoniaService.notify_requester(case, interaction.client, f"⚠️ Tu caso #{case_id} ha sido pausado. El staff lo reanudará cuando haya novedades.")
            await AgoniaService.send_staff_log(interaction.client, f"Caso #{case_id} pausado por {interaction.user.name}.")
            await AgoniaService.refresh_case_messages(interaction.client, case)
            await interaction.followup.send(f"✅ Caso #{case_id} pausado.", ephemeral=True)

    class DenyButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Denegar", style=discord.ButtonStyle.danger, custom_id="agonia_deny")

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            case_id = AgoniaCaseButtonsView._extract_case_id(interaction)
            if not case_id:
                return await interaction.followup.send("No se pudo determinar el ID del caso.", ephemeral=True)
            case = await AgoniaRepository.get_case(case_id)
            if not case:
                return await interaction.followup.send("No se encontró el caso.", ephemeral=True)
            if not await AgoniaService.is_decider(interaction.user):
                return await interaction.followup.send("❌ Solo Guild Master, Concilio o Admin Master BOT pueden denegar.", ephemeral=True)
            await AgoniaRepository.create_history(case_id, interaction.user.id, interaction.user.name, case["status"], "denegado", "Caso denegado")
            await AgoniaRepository.update_case(case_id, {"status": "denegado", "assigned_staff_id": interaction.user.id, "assigned_staff_name": interaction.user.name})
            case = await AgoniaRepository.get_case(case_id)
            await AgoniaService.notify_requester(case, interaction.client, f"❌ Tu caso #{case_id} ha sido denegado.")
            await AgoniaService.send_staff_log(interaction.client, f"Caso #{case_id} denegado por {interaction.user.name}.")
            await AgoniaService.refresh_case_messages(interaction.client, case)
            await interaction.followup.send(f"✅ Caso #{case_id} denegado.", ephemeral=True)

    class FinalizeButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Finalizar", style=discord.ButtonStyle.green, custom_id="agonia_finalize")

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            case_id = AgoniaCaseButtonsView._extract_case_id(interaction)
            if not case_id:
                return await interaction.followup.send("No se pudo determinar el ID del caso.", ephemeral=True)
            case = await AgoniaRepository.get_case(case_id)
            if not case:
                return await interaction.followup.send("No se encontró el caso.", ephemeral=True)
            if not await AgoniaService.is_decider(interaction.user):
                return await interaction.followup.send("❌ Solo Guild Master, Concilio o Admin Master BOT pueden finalizar.", ephemeral=True)
            await AgoniaRepository.create_history(case_id, interaction.user.id, interaction.user.name, case["status"], "finalizado", "Caso finalizado")
            await AgoniaRepository.update_case(case_id, {
                "status": "finalizado",
                "assigned_staff_id": interaction.user.id,
                "assigned_staff_name": interaction.user.name,
                "finished_at": datetime.utcnow().isoformat(sep=" ", timespec="seconds")
            })
            case = await AgoniaRepository.get_case(case_id)
            await AgoniaService.notify_requester(case, interaction.client, f"✅ Tu caso #{case_id} ha sido finalizado.")
            await AgoniaService.send_staff_log(interaction.client, f"Caso #{case_id} finalizado por {interaction.user.name}.")
            await AgoniaService.refresh_case_messages(interaction.client, case)
            await interaction.followup.send(f"✅ Caso #{case_id} finalizado.", ephemeral=True)

    class UpdateProgressButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Actualizar Progreso", style=discord.ButtonStyle.primary, custom_id="agonia_update_progress")

        async def callback(self, interaction: discord.Interaction):
            if not await AgoniaService.is_staff(interaction.user):
                return await interaction.response.send_message("❌ No tienes permisos para actualizar el progreso.", ephemeral=True)
            case_id = AgoniaCaseButtonsView._extract_case_id(interaction)
            if not case_id:
                return await interaction.response.send_message("No se pudo determinar el ID del caso.", ephemeral=True)
            await interaction.response.send_modal(AgoniaProgressModal(case_id))

    class RemindDMButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Recordar (DM)", style=discord.ButtonStyle.secondary, custom_id="agonia_remind_dm")

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            case_id = AgoniaCaseButtonsView._extract_case_id(interaction)
            if not case_id:
                return await interaction.followup.send("No se pudo determinar el ID del caso.", ephemeral=True)
            case = await AgoniaRepository.get_case(case_id)
            if not case:
                return await interaction.followup.send("No se encontró el caso.", ephemeral=True)
            message = (
                f"Hola <@{case['requester_id']}>, el staff te recuerda que debes actualizar tu caso de Agonía #{case_id}. "
                "Por favor responde en Discord con tu progreso o usa el botón de actualizar."
            )
            success = await AgoniaService.notify_requester(case, interaction.client, message)
            if success:
                await interaction.followup.send("✅ Recordatorio enviado por DM.", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ No se pudo enviar el DM de recordatorio. El flujo continúa.", ephemeral=True)

    class RepublishButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Republicar", style=discord.ButtonStyle.secondary, custom_id="agonia_republish")

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            case_id = AgoniaCaseButtonsView._extract_case_id(interaction)
            if not case_id:
                return await interaction.followup.send("No se pudo determinar el ID del caso.", ephemeral=True)
            case = await AgoniaRepository.get_case(case_id)
            if not case:
                return await interaction.followup.send("No se encontró el caso.", ephemeral=True)
            await AgoniaService.refresh_case_messages(interaction.client, case)
            await interaction.followup.send("✅ Mensajes del caso actualizados.", ephemeral=True)

class AgoniaRequestModal(discord.ui.Modal, title="Solicitud Agonía de Sombras"):
    character_name = discord.ui.TextInput(
        label="Nombre del personaje principal",
        placeholder="Ej. Harukoo",
        required=True,
        max_length=100
    )
    class_spec = discord.ui.TextInput(
        label="Clase / Spec principal",
        placeholder="Ej. Sacerdote Sombra",
        required=True,
        max_length=100
    )
    agonia_status = discord.ui.TextInput(
        label="Estado actual de la Agonía",
        placeholder="No iniciada / En misiones / Recojo de fragmentos / Finalizada",
        required=True,
        max_length=50
    )
    fragment_number = discord.ui.TextInput(
        label="Fragmentos actuales",
        placeholder="0 si no aplica",
        required=True,
        max_length=3
    )
    summary_details = discord.ui.TextInput(
        label="Detalles adicionales",
        style=discord.TextStyle.paragraph,
        placeholder=(
            "Incluye main/alteres, disponibilidad, Shadow's Edge, antigüedad, evidencia y compromiso."
        ),
        required=False,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        status_input = self.agonia_status.value.strip()
        status_mapping = {
            "no iniciada": "No iniciada",
            "no iniciado": "No iniciada",
            "en misiones": "En misiones",
            "faltan misiones": "En misiones",
            "misiones": "En misiones",
            "recojo de fragmentos": "Recojo de fragmentos",
            "recoleccion de fragmentos": "Recojo de fragmentos",
            "recojo fragmentos": "Recojo de fragmentos",
            "finalizada": "Finalizada",
            "finalizado": "Finalizada"
        }
        status = status_mapping.get(status_input.lower())
        valid_states = ["No iniciada", "En misiones", "Recojo de fragmentos", "Finalizada"]
        if status is None:
            return await interaction.response.send_message(
                f"Estado inválido. Usa uno de: {', '.join(valid_states)}.", ephemeral=True
            )

        logger.info(
            "Agonía solicitud enviada: user=%s input_status=%s normalized_status=%s",
            getattr(interaction.user, 'name', None),
            status_input,
            status
        )

        try:
            fragment_value = int(self.fragment_number.value.strip())
        except ValueError:
            return await interaction.response.send_message("El campo Fragmentos actuales debe ser un número entero.", ephemeral=True)

        if status == "Recojo de fragmentos" and not (0 <= fragment_value <= 50):
            return await interaction.response.send_message("Los fragmentos actuales deben estar entre 0 y 50.", ephemeral=True)

        if status != "Recojo de fragmentos":
            fragment_value = 0

        existing_active = await AgoniaRepository.find_active_case(interaction.user.id, self.character_name.value.strip())
        if existing_active:
            return await interaction.response.send_message(
                "Ya tienes una solicitud activa o un personaje ya en proceso. Espera a que se cierre o contacta a staff.",
                ephemeral=True
            )

        if await AgoniaRepository.has_finalized_case_for_character(self.character_name.value.strip()):
            return await interaction.response.send_message(
                "Este personaje ya tiene una Agonía finalizada. Contacta a staff para abrir un nuevo caso manualmente.",
                ephemeral=True
            )

        case_id = await AgoniaRepository.create_case(
            requester_id=interaction.user.id,
            requester_name=interaction.user.name,
            character_name=self.character_name.value.strip(),
            class_spec=self.class_spec.value.strip(),
            mains_alters="No especificado",
            availability="No especificado",
            agonia_status=status,
            fragment_number=fragment_value,
            has_shadows_edge=0,
            guild_seniority="No especificado",
            evidence_notes=self.summary_details.value.strip(),
            commitment_text=self.summary_details.value.strip(),
            description=(
                f"Estado: {status}\n"
                f"Fragmentos actuales: {fragment_value}\n"
                f"Detalles: {self.summary_details.value.strip()}"
            )
        )

        case = await AgoniaRepository.get_case(case_id)
        await AgoniaRepository.create_history(case_id, interaction.user.id, interaction.user.name, "", "pendiente", "Solicitud creada")
        await AgoniaService.create_case_messages(interaction.client, case)
        await AgoniaService.send_staff_log(interaction.client, f"Nuevo caso Agonía #{case_id} creado por {interaction.user.name}.")
        await AgoniaService.notify_requester(case, interaction.client, f"✅ Tu solicitud de Agonía #{case_id} ha sido recibida. El staff revisará tu caso.")
        await interaction.response.send_message(f"✅ Tu solicitud ha sido creada como caso #{case_id}.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.exception("Error dentro del modal de solicitud de Agonía")
        try:
            await interaction.response.send_message("❌ Error al procesar la solicitud de Agonía.", ephemeral=True)
        except Exception:
            pass

class AgoniaMoreDataModal(discord.ui.Modal, title="Pedir más datos - Agonía"):
    def __init__(self, case_id: int):
        super().__init__()
        self.case_id = case_id

    reason = discord.ui.TextInput(
        label="Observación a enviar al solicitante",
        style=discord.TextStyle.paragraph,
        placeholder="Pide más información o evidencia...",
        required=True,
        max_length=1024
    )

    async def on_submit(self, interaction: discord.Interaction):
        case_id = self.case_id
        case = await AgoniaRepository.get_case(case_id)
        if not case:
            return await interaction.response.send_message("No se encontró el caso.", ephemeral=True)

        await AgoniaRepository.create_history(case_id, interaction.user.id, interaction.user.name, case["status"], "mas_datos", self.reason.value.strip())
        await AgoniaRepository.update_case(case_id, {
            "status": "mas_datos",
            "assigned_staff_id": interaction.user.id,
            "assigned_staff_name": interaction.user.name
        })
        case = await AgoniaRepository.get_case(case_id)
        await AgoniaService.notify_requester(case, interaction.client, (
            f"⚠️ El staff ha solicitado más datos para tu caso #{case_id}:\n{self.reason.value.strip()}"
        ))
        await AgoniaService.send_staff_log(interaction.client, f"Caso #{case_id} pasó a mas_datos por {interaction.user.name}.")
        await AgoniaService.refresh_case_messages(interaction.client, case)
        await interaction.response.send_message("✅ Solicitud de más datos enviada.", ephemeral=True)

class AgoniaProgressModal(discord.ui.Modal, title="Actualizar Progreso Agonía"):
    def __init__(self, case_id: int):
        super().__init__()
        self.case_id = case_id

    agonia_status = discord.ui.TextInput(
        label="Estado actual de la Agonía",
        placeholder="No iniciada / En misiones / Recojo de fragmentos / Finalizada",
        required=True,
        max_length=50
    )
    fragment_number = discord.ui.TextInput(
        label="Fragmentos actuales",
        placeholder="Ej. 12",
        required=True,
        max_length=3
    )
    progress_notes = discord.ui.TextInput(
        label="Observación opcional",
        style=discord.TextStyle.paragraph,
        placeholder="Detalles de progreso o mensaje al staff...",
        required=False,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        case_id = self.case_id
        case = await AgoniaRepository.get_case(case_id)
        if not case:
            return await interaction.response.send_message("No se encontró el caso.", ephemeral=True)

        status = self.agonia_status.value.strip()
        valid_states = ["No iniciada", "En misiones", "Recojo de fragmentos", "Finalizada"]
        if status not in valid_states:
            return await interaction.response.send_message(
                f"Estado inválido. Usa uno de: {', '.join(valid_states)}.", ephemeral=True
            )

        try:
            fragment_value = int(self.fragment_number.value.strip())
        except ValueError:
            return await interaction.response.send_message("El campo Fragmentos actuales debe ser un número entero.", ephemeral=True)

        if status == "Recojo de fragmentos" and not (0 <= fragment_value <= 50):
            return await interaction.response.send_message("Los fragmentos actuales deben estar entre 0 y 50.", ephemeral=True)

        if status != "Recojo de fragmentos":
            fragment_value = case.get("fragment_number", 0)

        await AgoniaRepository.create_progress_log(
            case_id,
            interaction.user.id,
            interaction.user.name,
            case.get("agonia_status", ""),
            status,
            fragment_value,
            self.progress_notes.value.strip()
        )

        updates = {
            "agonia_status": status,
            "fragment_number": fragment_value
        }
        if self.progress_notes.value.strip():
            updates["description"] = f"{case.get('description', '')}\n\nActualización: {self.progress_notes.value.strip()}"

        await AgoniaRepository.update_case(case_id, updates)
        case = await AgoniaRepository.get_case(case_id)
        if fragment_value > 0:
            await AgoniaService.prepare_public_note_for_case(case)
        await AgoniaService.send_staff_log(interaction.client, f"Progreso actualizado en caso #{case_id} por {interaction.user.name}.")
        await AgoniaService.refresh_case_messages(interaction.client, case)
        await interaction.response.send_message("✅ Progreso actualizado correctamente.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("❌ Error al actualizar el progreso.", ephemeral=True)


class MinimalManualCompleteModal(discord.ui.Modal, title="Registrar Agonía Completada (Manual)"):
    character_name = discord.ui.TextInput(
        label="Nombre del personaje",
        placeholder="Ej. Harukoo",
        required=True,
        max_length=100
    )
    discord_user = discord.ui.TextInput(
        label="Usuario de Discord (mención o nombre)",
        placeholder="Menciona al usuario o escribe su nombre (ej. @Usuario o 123456789012345678)",
        required=True,
        max_length=100
    )
    finished_at = discord.ui.TextInput(
        label="Fecha de finalización (opcional)",
        placeholder="DD/MM/YYYY o YYYY-MM-DD (dejar vacío = ahora)",
        required=False,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Normalizar requester id si viene en formato de mención o ID numérico
        requester_text = self.discord_user.value.strip()
        m = re.search(r"<(?:@!?)?(\d{17,20})>", requester_text)
        if m:
            requester_id = int(m.group(1))
        else:
            # intentar si el usuario escribió solo un ID numérico
            m2 = re.search(r"^(\d{17,20})$", requester_text)
            if m2:
                requester_id = int(m2.group(1))
            else:
                # No es mención ni ID -> requerir formato correcto
                return await interaction.response.send_message(
                    "Por favor proporciona una mención de Discord o un ID numérico válido en el campo 'Usuario de Discord'.", ephemeral=True
                )

        char_name = self.character_name.value.strip()
        finished_raw = self.finished_at.value.strip()

        # Intentar parsear fecha en formatos comunes
        finished_val = None
        if finished_raw:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M"):
                try:
                    finished_val = datetime.strptime(finished_raw, fmt).isoformat(sep=' ', timespec='seconds')
                    break
                except Exception:
                    continue
            if not finished_val:
                # Guardar tal cual si no parsea
                finished_val = finished_raw
        else:
            finished_val = datetime.utcnow().isoformat(sep=' ', timespec='seconds')

        # Crear caso directamente como finalizado
        case_id = await AgoniaRepository.create_case(
            requester_id=requester_id,
            requester_name=str(requester_id),
            character_name=char_name,
            class_spec="Manual",
            mains_alters="Manual",
            availability="Manual",
            agonia_status="Finalizada",
            fragment_number=0,
            has_shadows_edge=0,
            guild_seniority="Manual",
            evidence_notes="Registro manual de agonía completada",
            commitment_text="",
            description=f"Registro manual: personaje={char_name} usuario_id={requester_id} finalizado={finished_val}",
            status="finalizado"
        )

        await AgoniaRepository.create_history(case_id, interaction.user.id, interaction.user.name, "", "finalizado", "Registro manual completado")
        if finished_val:
            await AgoniaRepository.update_case(case_id, {"finished_at": finished_val})

        case = await AgoniaRepository.get_case(case_id)
        # Crear mensajes y recuperar el caso actualizado
        case = await AgoniaService.create_case_messages(interaction.client, case)
        await AgoniaService.send_staff_log(interaction.client, f"Caso #{case_id} registrado manualmente como finalizado por {interaction.user.name}.")

        # Preparar embed para DM con enlace al mensaje final si existe
        dm_sent = False
        try:
            user_obj = await interaction.client.fetch_user(requester_id)
            dm_embed = discord.Embed(
                title="✅ Agonía registrada como finalizada",
                description=f"Tu Agonía para **{char_name}** ha sido registrada manualmente como finalizada. Caso #{case_id}.",
                color=discord.Color.green()
            )
            final_msg_id = case.get("final_message_id")
            final_channel_id = config.AGONIAS_FINALIZADAS_CHANNEL_ID
            if final_msg_id and config.DISCORD_GUILD_ID:
                msg_url = f"https://discord.com/channels/{config.DISCORD_GUILD_ID}/{final_channel_id}/{final_msg_id}"
                dm_embed.add_field(name="Ver resumen en Discord", value=f"[Abrir mensaje finalizado]({msg_url})", inline=False)
            try:
                await user_obj.send(embed=dm_embed)
                dm_sent = True
            except Exception:
                dm_sent = False
        except Exception:
            dm_sent = False

        # Registrar resultado del intento de DM en el historial
        if dm_sent:
            await AgoniaRepository.create_history(case_id, interaction.user.id, interaction.user.name, "finalizado", "finalizado", "DM enviado al solicitante")
        else:
            await AgoniaRepository.create_history(case_id, interaction.user.id, interaction.user.name, "finalizado", "finalizado", "No se pudo enviar DM al solicitante")

        await interaction.response.send_message(f"✅ Caso finalizado registrado como #{case_id}. DM enviado: {dm_sent}", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.exception("Error en modal manual de finalizado")
        try:
            await interaction.response.send_message("❌ Error al procesar el registro manual.", ephemeral=True)
        except Exception:
            pass

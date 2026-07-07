import logging
import discord
from typing import Any, Dict, Optional

import config
from bot.repositories.complaints_repo import ComplaintsRepository
from bot.services.complaints_service import ComplaintsService, VALID_COMPLAINT_TYPES

logger = logging.getLogger("ComplaintsViews")


class ComplaintPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ComplaintTypeSelect())


class ComplaintTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="DKP Injusto", value="dkp", description="Errores en puntos o asistencia."),
            discord.SelectOption(label="Problema con Staff", value="staff", description="Reclamo contra un oficial o staff."),
            discord.SelectOption(label="Problema con Guild", value="guild", description="Conflictos entre miembros o normas."),
            discord.SelectOption(label="Otro / Apelación", value="other", description="Otros asuntos serios o apelaciones."),
        ]
        super().__init__(placeholder="Selecciona el tipo de reclamo", options=options, custom_id="complaints_type_select")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ComplaintModal(self.values[0]))


class ComplaintModal(discord.ui.Modal):
    def __init__(self, complaint_type: str):
        self.complaint_type = complaint_type
        super().__init__(title="Nuevo reclamo")
        self.fields = self._build_fields()

    def _build_fields(self):
        schema = {
            "dkp": [
                ("character_name", "Nombre del personaje", 2, 80),
                ("raid_or_event", "Raid o evento", 2, 120),
                ("dkp_amount", "DKP reclamado", 1, 40),
                ("what_happened", "Qué ocurrió", 10, 1000),
                ("evidence", "Evidencia", 3, 1000),
            ],
            "staff": [
                ("staff_name", "Staff involucrado", 2, 80),
                ("what_happened", "Qué ocurrió", 10, 1000),
                ("context", "Cuándo o en qué contexto", 5, 400),
                ("evidence", "Evidencia o testigos", 3, 1000),
            ],
            "guild": [
                ("main_character", "Personaje principal", 2, 80),
                ("members_involved", "Miembros involucrados", 2, 200),
                ("what_happened", "Qué problema hubo", 10, 1000),
                ("expected_solution", "Qué solución esperas", 5, 400),
            ],
            "other": [
                ("subject", "Asunto", 2, 120),
                ("main_character", "Personaje principal", 2, 80),
                ("description", "Descripción", 10, 1000),
                ("evidence", "Evidencia o referencia", 3, 1000),
            ],
        }
        fields = []
        for field_name, label, min_len, max_len in schema[self.complaint_type]:
            item = discord.ui.TextInput(label=label, required=True, min_length=min_len, max_length=max_len, custom_id=f"complaint_{field_name}")
            fields.append(item)
            self.add_item(item)
        return fields

    async def on_submit(self, interaction: discord.Interaction):
        payload = {}
        for item in self.children:
            if isinstance(item, discord.ui.TextInput):
                payload[item.custom_id.replace("complaint_", "")] = item.value.strip()
        try:
            case = await ComplaintsService.create_case(
                interaction.client,
                interaction,
                VALID_COMPLAINT_TYPES.get(self.complaint_type, self.complaint_type),
                payload,
                source_panel_channel_id=interaction.channel_id,
            )
            await interaction.response.send_message(f"✅ Reclamo #{case['id']} registrado correctamente. El staff lo revisará pronto.", ephemeral=True)
        except ValueError as exc:
            await interaction.response.send_message(f"⚠️ {exc}", ephemeral=True)
        except Exception as exc:
            logger.exception("Error creando reclamo")
            await interaction.response.send_message("❌ No se pudo crear el reclamo. Intenta de nuevo más tarde.", ephemeral=True)


class ComplaintCaseView(discord.ui.View):
    def __init__(self, case: Optional[Dict[str, Any]] = None, read_only: bool = False):
        super().__init__(timeout=None)
        self.case = case or {}
        if read_only:
            self.add_item(self.RepublishButton())
            return
        self.add_item(self.TakeCaseButton())
        self.add_item(self.RequestMoreDataButton())
        self.add_item(self.RespondButton())
        self.add_item(self.ResolveButton())
        self.add_item(self.DenyButton())
        self.add_item(self.RepublishButton())

    @staticmethod
    def _extract_case_id(interaction: discord.Interaction) -> Optional[int]:
        title = interaction.message.embeds[0].title if interaction.message and interaction.message.embeds else ""
        if "#" in title:
            try:
                return int(title.split("#", 1)[1].split("|", 1)[0].strip())
            except Exception:
                return None
        return None

    class TakeCaseButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Tomar caso", style=discord.ButtonStyle.primary, custom_id="complaints_take")

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            case_id = ComplaintCaseView._extract_case_id(interaction)
            if not case_id:
                return await interaction.followup.send("No se pudo identificar el caso.", ephemeral=True)
            case = await ComplaintsRepository.get_complaint(case_id)
            if not case:
                return await interaction.followup.send("No se encontró el caso.", ephemeral=True)
            if not await ComplaintsService.is_staff(interaction.user):
                return await interaction.followup.send("❌ No tienes permisos para tomar este caso.", ephemeral=True)
            case = await ComplaintsService.update_case(
                interaction.client,
                case,
                interaction.user,
                "tomado",
                "Caso tomado por staff",
                f"El caso fue tomado por {interaction.user.display_name}.",
                assigned_staff_id=interaction.user.id,
                assigned_staff_name=interaction.user.display_name,
            )
            await ComplaintsService.send_staff_log(interaction.client, f"Reclamo #{case_id} tomado por {interaction.user.display_name}.")
            await ComplaintsService.notify_requester(case, interaction.client, f"✅ Tu reclamo #{case_id} ha sido tomado por {interaction.user.display_name}.")
            await interaction.followup.send(f"✅ Reclamo #{case_id} marcado como tomado.", ephemeral=True)

    class RequestMoreDataButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Pedir más datos", style=discord.ButtonStyle.secondary, custom_id="complaints_more_data")

        async def callback(self, interaction: discord.Interaction):
            if not await ComplaintsService.is_staff(interaction.user):
                return await interaction.response.send_message("❌ No tienes permisos para pedir más datos.", ephemeral=True)
            case_id = ComplaintCaseView._extract_case_id(interaction)
            if not case_id:
                return await interaction.response.send_message("No se pudo identificar el caso.", ephemeral=True)
            await interaction.response.send_modal(ComplaintStaffModal(case_id, "more_data"))

    class RespondButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Responder", style=discord.ButtonStyle.primary, custom_id="complaints_respond")

        async def callback(self, interaction: discord.Interaction):
            if not await ComplaintsService.is_staff(interaction.user):
                return await interaction.response.send_message("❌ No tienes permisos para responder.", ephemeral=True)
            case_id = ComplaintCaseView._extract_case_id(interaction)
            if not case_id:
                return await interaction.response.send_message("No se pudo identificar el caso.", ephemeral=True)
            await interaction.response.send_modal(ComplaintStaffModal(case_id, "respond"))

    class ResolveButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Resolver", style=discord.ButtonStyle.success, custom_id="complaints_resolve")

        async def callback(self, interaction: discord.Interaction):
            if not await ComplaintsService.is_staff(interaction.user):
                return await interaction.response.send_message("❌ No tienes permisos para resolver.", ephemeral=True)
            case_id = ComplaintCaseView._extract_case_id(interaction)
            if not case_id:
                return await interaction.response.send_message("No se pudo identificar el caso.", ephemeral=True)
            await interaction.response.send_modal(ComplaintStaffModal(case_id, "resolve"))

    class DenyButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Denegar", style=discord.ButtonStyle.danger, custom_id="complaints_deny")

        async def callback(self, interaction: discord.Interaction):
            if not await ComplaintsService.is_staff(interaction.user):
                return await interaction.response.send_message("❌ No tienes permisos para denegar.", ephemeral=True)
            case_id = ComplaintCaseView._extract_case_id(interaction)
            if not case_id:
                return await interaction.response.send_message("No se pudo identificar el caso.", ephemeral=True)
            await interaction.response.send_modal(ComplaintStaffModal(case_id, "deny"))

    class RepublishButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Republicar", style=discord.ButtonStyle.secondary, custom_id="complaints_republish")

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            case_id = ComplaintCaseView._extract_case_id(interaction)
            if not case_id:
                return await interaction.followup.send("No se pudo identificar el caso.", ephemeral=True)
            case = await ComplaintsRepository.get_complaint(case_id)
            if not case:
                return await interaction.followup.send("No se encontró el caso.", ephemeral=True)
            success = await ComplaintsService.republish_case(interaction.client, case)
            if success:
                await interaction.followup.send(f"✅ Reclamo #{case_id} republicado.", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ No se pudo republicar el caso.", ephemeral=True)


class ComplaintStaffModal(discord.ui.Modal):
    def __init__(self, case_id: int, mode: str):
        self.case_id = case_id
        self.mode = mode
        super().__init__(title="Acción de staff")
        self.message = discord.ui.TextInput(label="Mensaje o motivo", required=True, min_length=5, max_length=1000, custom_id="staff_message")
        self.add_item(self.message)

    async def on_submit(self, interaction: discord.Interaction):
        case = await ComplaintsRepository.get_complaint(self.case_id)
        if not case:
            return await interaction.response.send_message("No se encontró el caso.", ephemeral=True)
        if self.mode == "more_data":
            case = await ComplaintsService.update_case(
                interaction.client,
                case,
                interaction.user,
                "esperando_usuario",
                "Se solicitó más información",
                self.message.value.strip(),
            )
            await ComplaintsService.notify_requester(case, interaction.client, f"ℹ️ El staff necesita más datos sobre tu reclamo #{self.case_id}: {self.message.value.strip()}")
            await interaction.response.send_message(f"✅ Se solicitó más información para el reclamo #{self.case_id}.", ephemeral=True)
        elif self.mode == "respond":
            case = await ComplaintsService.update_case(
                interaction.client,
                case,
                interaction.user,
                "respondido",
                "Respuesta enviada por staff",
                self.message.value.strip(),
            )
            await ComplaintsService.notify_requester(case, interaction.client, f"📝 El staff respondió tu reclamo #{self.case_id}: {self.message.value.strip()}")
            await interaction.response.send_message(f"✅ Respuesta registrada para el reclamo #{self.case_id}.", ephemeral=True)
        elif self.mode == "resolve":
            case = await ComplaintsService.update_case(
                interaction.client,
                case,
                interaction.user,
                "resuelto",
                "Caso resuelto favorablemente",
                self.message.value.strip(),
                resolved_by_id=interaction.user.id,
                resolved_by_name=interaction.user.display_name,
                resolution=self.message.value.strip(),
            )
            await ComplaintsService.notify_requester(case, interaction.client, f"✅ Tu reclamo #{self.case_id} ha sido resuelto favorablemente.")
            await ComplaintsService.send_staff_log(interaction.client, f"Reclamo #{self.case_id} resuelto por {interaction.user.display_name}.")
            await ComplaintsService.send_history_log(interaction.client, case, interaction.user, "Resolución", self.message.value.strip(), "resuelto")
            await interaction.response.send_message(f"✅ Reclamo #{self.case_id} marcado como resuelto.", ephemeral=True)
        elif self.mode == "deny":
            case = await ComplaintsService.update_case(
                interaction.client,
                case,
                interaction.user,
                "denegado",
                "Caso denegado",
                self.message.value.strip(),
                resolved_by_id=interaction.user.id,
                resolved_by_name=interaction.user.display_name,
                resolved_reason=self.message.value.strip(),
            )
            await ComplaintsService.notify_requester(case, interaction.client, f"❌ Tu reclamo #{self.case_id} ha sido denegado.")
            await ComplaintsService.send_staff_log(interaction.client, f"Reclamo #{self.case_id} denegado por {interaction.user.display_name}.")
            final_embed = ComplaintsService.build_final_embed(case, "denegado")
            channel = interaction.client.get_channel(config.COMPLAINTS_HISTORY_CHANNEL_ID)
            if channel is None:
                try:
                    channel = await interaction.client.fetch_channel(config.COMPLAINTS_HISTORY_CHANNEL_ID)
                except Exception:
                    channel = None
            if channel is not None:
                await channel.send(embed=final_embed)
            await interaction.response.send_message(f"✅ Reclamo #{self.case_id} marcado como denegado.", ephemeral=True)

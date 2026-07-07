import discord
from discord.ext import commands
from discord import app_commands
import config
from bot.services.aiservice import AIService
from bot.repositories.memberrepo import MemberRepository

class AISuggestionModal(discord.ui.Modal, title="Asistente de Sanciones IA"):
    incident_input = discord.ui.TextInput(
        label="Descripción detallada de la falta",
        style=discord.TextStyle.paragraph,
        placeholder="Ej: El usuario insultó reiteradamente en el canal de chat de banda durante el raid de ICC y se desconectó de Discord.",
        required=True,
        max_length=500
    )

    def __init__(self, target_member: discord.Member):
        super().__init__()
        self.member = target_member

    async def on_submit(self, interaction: discord.Interaction):
        ai_enabled = await AIService.is_enabled()
        if not ai_enabled:
            await interaction.response.send_message(
                "⚠️ **Asistencia de IA Desactivada:** No se pudo procesar la llamada de la IA. Por favor, configura una `AIAPIKEY` válida en tu archivo `.env`.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        
        incident_description = self.incident_input.value
        suggestion = await AIService.suggest_sanción(self.member.name, incident_description, interaction.client)
        
        embed = discord.Embed(
            title=f"🧠 Sugerencia de Sanción IA: {self.member.display_name}",
            description=suggestion,
            color=discord.Color.dark_magenta()
        )
        embed.set_footer(text="Asesoría Cognitiva • Cero automatización en base a políticas de seguridad")

        class CommitNoteView(discord.ui.View):
            def __init__(self, target, note_text, suggested_txt, staff_member):
                super().__init__(timeout=120)
                self.target = target
                self.note_text = note_text
                self.suggested_txt = suggested_txt
                self.staff = staff_member

            @discord.ui.button(label="📌 Archivar en Historial de Miembro", style=discord.ButtonStyle.success, custom_id="ai_moderation:btn_commit_note")
            async def btn_commit(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                await btn_interaction.response.defer(ephemeral=True)
                
                parsed_action = "Advertencia / Advertido"
                if "gravedad: grave" in self.suggested_txt.lower() or "gravedad estimada: grave" in self.suggested_txt.lower():
                    parsed_action = "Mute / Suspensión Temporal"
                elif "expulsión" in self.suggested_txt.lower() or "ban" in self.suggested_txt.lower():
                    parsed_action = "Propuesta de Expulsión"

                await MemberRepository.add_staff_note(
                    user_id=self.target.id,
                    username=self.target.name,
                    staff_id=self.staff.id,
                    staff_username=self.staff.name,
                    note=self.note_text,
                    suggested_action=parsed_action
                )
                
                button.disabled = True
                button.label = "✅ Incidencia Archivada"
                await btn_interaction.edit_original_response(view=self)
                await btn_interaction.followup.send("✅ La incidencia y sugerencia del caso se han guardado con éxito en el historial del miembro.", ephemeral=True)

        view = CommitNoteView(self.member, incident_description, suggestion, interaction.user)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message(f"❌ Ocurrió un fallo en el modal interactivo: {error}", ephemeral=True)


class AIModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ai-review-user", description="Analiza el comportamiento e historial de un usuario usando inteligencia artificial.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def ai_review_user(self, interaction: discord.Interaction, member: discord.Member):
        ai_enabled = await AIService.is_enabled()
        if not ai_enabled:
            await interaction.response.send_message(
                "⚠️ **Asistencia de IA Desactivada:** No se pudo procesar la solicitud. Un administrador debe configurar la `AIAPIKEY` en el archivo `.env` para habilitar el motor de análisis.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        rank_info = MemberRepository.get_guild_rank_for_member(member.roles) or {"name": "Iniciado", "tier": 10}
        notes = await MemberRepository.get_staff_notes(member.id)

        analysis = await AIService.analyze_user_behavior(member.name, rank_info, notes, interaction.client)

        embed = discord.Embed(
            title=f"🧠 Diagnóstico Cognitivo IA: {member.display_name}",
            description=analysis,
            color=discord.Color.dark_magenta()
        )
        embed.set_footer(text="Asistente de IA de Hermandad • Información estrictamente orientativa")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @ai_review_user.error
    async def ai_review_user_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("❌ No tienes permisos de `Gestionar Mensajes` (Staff) para invocar análisis por IA.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Ocurrió un error al procesar el comando: {error}", ephemeral=True)

    @app_commands.command(name="ai-suggest-action", description="Abre un asistente táctil para evaluar un incidente de mal comportamiento y sugerir sanciones.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def ai_suggest_action(self, interaction: discord.Interaction, member: discord.Member):
        ai_enabled = await AIService.is_enabled()
        if not ai_enabled:
            await interaction.response.send_message(
                "⚠️ **Asistencia de IA Desactivada:** El asistente conductual requiere una `AIAPIKEY` activa en tu archivo `.env`.",
                ephemeral=True
            )
            return

        modal = AISuggestionModal(member)
        await interaction.response.send_modal(modal)

    @ai_suggest_action.error
    async def ai_suggest_action_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("❌ No tienes permisos de `Gestionar Mensajes` (Staff) para abrir el modal conductual.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Ocurrió un error al procesar el comando: {error}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AIModerationCog(bot))

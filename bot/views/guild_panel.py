import discord
import config
from bot.repositories.member_repo import MemberRepository

class GuildPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _show_ranks_tab(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("❌ Este panel debe usarse en un servidor.", ephemeral=True)
            return

        # Calcular distribución de rangos leyendo los miembros en tiempo real
        # Asegurarse de que el bot tiene cargados los miembros (intents.members)
        rank_counts = {rank: 0 for rank in config.GUILD_RANK_ROLES}
        
        # Filtrar bots
        human_members = [m for m in guild.members if not m.bot]
        
        for member in human_members:
            rank_info = MemberRepository.get_guild_rank_for_member(member.roles)
            if rank_info:
                rank_counts[rank_info["name"]] += 1

        embed = discord.Embed(
            title="📊 Distribución de Rangos en la Hermandad",
            description="Estadísticas de progresión leídas en tiempo real según niveles y roles del servidor.",
            color=discord.Color.blurple()
        )
        
        total_ranked = sum(rank_counts.values())
        embed.add_field(name="👥 Total Miembros Clasificados", value=f"**{total_ranked}** jugadores", inline=False)

        # Iconos de rango para presentación visual premium
        icons = ["👑", "⚔️", "🛡️", "🧙‍♂️", "🎯", "👟", "🔥", "📣", "🔨", "🌱", "🎭", "💀"]
        
        description_lines = []
        for index, rank_name in enumerate(config.GUILD_RANK_ROLES):
            count = rank_counts[rank_name]
            icon = icons[index] if index < len(icons) else "🔹"
            
            # Generar barra de progreso visual sencilla
            percentage = (count / total_ranked * 100) if total_ranked > 0 else 0
            bar_length = int(percentage / 10)
            bar = "▰" * bar_length + "▱" * (10 - bar_length)
            
            description_lines.append(
                f"{icon} **Rango {index+1}: {rank_name}** • {count} miembros\n`{bar}` ({percentage:.1f}%)"
            )
            
        embed.description = "\n\n".join(description_lines)
        embed.set_footer(text="WoW Bridge • Integración Arcane Levels • Hito 2")
        
        await interaction.edit_original_response(embed=embed, view=self)

    async def _show_members_tab(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Consultar últimos cambios de rango registrados en BD
        recent_changes = await MemberRepository.get_recent_rank_changes(limit=5)
        
        embed = discord.Embed(
            title="👥 Historial de Progresión y Rangos",
            description="Historial reciente de ascensos y cambios de jerarquía registrados.",
            color=discord.Color.green()
        )
        
        if recent_changes:
            lines = []
            for change in recent_changes:
                lines.append(
                    f"🔹 **{change['username']}**\n"
                    f"  ↳ De `{change['previous_rank']}` a `{change['new_rank']}`\n"
                    f"  *Registrado por {change['changed_by']} el {change['changed_at']}*"
                )
            embed.add_field(name="📈 Últimos Cambios de Rango", value="\n\n".join(lines), inline=False)
        else:
            embed.add_field(
                name="📈 Últimos Cambios de Rango", 
                value="No hay registros recientes de cambios de rango en la base de datos local.", 
                inline=False
            )
            
        embed.set_footer(text="WoW Bridge • Log de Progresión Activa")
        await interaction.edit_original_response(embed=embed, view=self)

    async def _show_ai_tab(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Consultar notas recientes del staff
        recent_notes = await MemberRepository.get_recent_notes(limit=3)
        
        embed = discord.Embed(
            title="🤖 Módulo de Asistencia IA y Moderación",
            description="Resumen analítico y estadísticas de incidencias registradas por el Staff.",
            color=discord.Color.dark_magenta()
        )
        
        # Status de IA
        ia_status = "🟢 Activa e Integrada (OpenAI)" if config.AI_ENABLED else "🔴 Desactivada (Falta API Key)"
        embed.add_field(name="Estado del Asistente Cognitivo", value=f"**{ia_status}**", inline=False)
        
        if recent_notes:
            lines = []
            for note in recent_notes:
                lines.append(
                    f"📌 **Miembro:** `{note['username']}`\n"
                    f"  *Reporte:* {note['note']}\n"
                    f"  *Sugerencia IA:* `{note['suggested_action']}`\n"
                    f"  *Tomado por {note['staff_username']} el {note['created_at']}*"
                )
            embed.add_field(name="📝 Últimos Casos en Revisión", value="\n\n".join(lines), inline=False)
        else:
            embed.add_field(
                name="📝 Últimos Casos en Revisión", 
                value="No hay ninguna incidencia ni reporte en el historial de moderación.", 
                inline=False
            )
            
        embed.add_field(
            name="💡 Nota de Privacidad y Seguridad", 
            value="Este bot NO realiza acciones directas (Mutes o Bans). Las notas se procesan bajo estricto anonimato de datos privados. Toda sanción debe aplicarse a través del bot Wick o Carl-bot.",
            inline=False
        )
        
        embed.set_footer(text="WoW Bridge • Asistencia Cognitiva")
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="📊 Distribución de Rangos", style=discord.ButtonStyle.primary, custom_id="guild_panel:btn_ranks", row=0)
    async def btn_ranks(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._show_ranks_tab(interaction)

    @discord.ui.button(label="👥 Progresión Reciente", style=discord.ButtonStyle.success, custom_id="guild_panel:btn_members", row=0)
    async def btn_members(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._show_members_tab(interaction)

    @discord.ui.button(label="🤖 Asistencia IA Staff", style=discord.ButtonStyle.secondary, custom_id="guild_panel:btn_ai", row=0)
    async def btn_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._show_ai_tab(interaction)

def create_guild_panel_embed() -> discord.Embed:
    """
    Crea el embed de bienvenida inicial para el panel de gestión de guild.
    """
    embed = discord.Embed(
        title="🛡️ Panel de Gestión de Hermandad & Comunidad",
        description=(
            "Bienvenido al centro de operaciones táctil del Staff.\n\n"
            "Usa los botones de abajo para navegar entre las pestañas informativas y las estadísticas de la guild.\n\n"
            "⚠️ **Aviso de Seguridad:** Este panel contiene datos internos del staff y debe mantenerse exclusivamente en canales restringidos."
        ),
        color=discord.Color.blurple()
    )
    embed.add_field(name="📈 Progresión por Niveles", value="Sincronización automática de rangos basada en la actividad de Arcane.", inline=True)
    embed.add_field(name="🧠 Asistencia IA", value="Análisis conductual y sugerencia de sanciones de forma objetiva.", inline=True)
    embed.set_footer(text="WoW Bridge v2.0 • Gestión Premium")
    return embed

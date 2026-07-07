import logging
import discord
from discord.ext import commands
from discord import app_commands

import config
from bot.views.complaints_views import ComplaintPanelView, ComplaintTypeSelect
from bot.services.complaints_service import ComplaintsService
from bot.repositories.complaints_repo import ComplaintsRepository

logger = logging.getLogger("ComplaintsCog")


class ComplaintsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Registra las vistas persistentes del sistema de reclamos al cargar el cog."""
        panel_view = ComplaintPanelView()
        self.bot.add_view(panel_view)
        logger.info("Vistas persistentes de reclamos registradas.")

    def _build_panel_embed(self) -> discord.Embed:
        return ComplaintsService.build_panel_embed()

    @app_commands.command(name="complaints_panel", description="Publica el panel de reclamos en el canal actual.")
    async def complaints_panel(self, interaction: discord.Interaction):
        try:
            embed = self._build_panel_embed()
            view = ComplaintPanelView()
            self.bot.add_view(view)
            await interaction.response.send_message(embed=embed, view=view)
            logger.info(f"Panel de reclamos publicado por {interaction.user} en {interaction.channel}")
        except Exception as exc:
            logger.exception("Error publicando el panel de reclamos")
            await interaction.response.send_message(f"❌ Error: {exc}", ephemeral=True)

    @commands.command(name="complaints_panel")
    @commands.has_permissions(manage_messages=True)
    async def complaints_panel_text(self, ctx: commands.Context):
        try:
            embed = self._build_panel_embed()
            view = ComplaintPanelView()
            self.bot.add_view(view)
            await ctx.send(embed=embed, view=view)
            logger.info(f"Panel de reclamos publicado por {ctx.author} en {ctx.channel}")
        except Exception as exc:
            logger.exception("Error publicando el panel de reclamos")
            await ctx.send(f"❌ Error: {exc}")

    @app_commands.command(name="complaints_recreate_panel", description="Publica de nuevo el panel de reclamos en el canal configurado.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def complaints_recreate_panel(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            channel = self.bot.get_channel(config.COMPLAINTS_PANEL_CHANNEL_ID)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(config.COMPLAINTS_PANEL_CHANNEL_ID)
                except Exception as exc:
                    return await interaction.followup.send(f"❌ No se pudo encontrar el canal de reclamos: {exc}", ephemeral=True)
            embed = self._build_panel_embed()
            view = ComplaintPanelView()
            self.bot.add_view(view)
            msg = await channel.send(embed=embed, view=view)
            logger.info(f"Panel de reclamos recreado en {channel} por {interaction.user}. Mensaje ID: {msg.id}")
            await interaction.followup.send(f"✅ Panel publicado en <#{channel.id}>. Mensaje ID: {msg.id}", ephemeral=True)
        except Exception as exc:
            logger.exception("Error recreando el panel de reclamos")
            await interaction.followup.send(f"❌ No se pudo publicar el panel: {exc}", ephemeral=True)

    @app_commands.command(name="complaints_list", description="Lista los reclamos activos.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def complaints_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cases = await ComplaintsRepository.list_active_complaints(limit=20)
        if not cases:
            return await interaction.followup.send("No hay reclamos activos.", ephemeral=True)
        lines = [f"#{case['id']} • {case['type']} • {case['status']} • <@{case['requester_id']}>" for case in cases]
        embed = discord.Embed(title="📋 Reclamos activos", description="\n".join(lines), color=discord.Color.blue())
        await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.command(name="complaints_rebuild")
    @commands.has_permissions(manage_messages=True)
    async def complaints_rebuild(self, ctx: commands.Context):
        cases = await ComplaintsRepository.list_all_complaints(limit=50)
        for case in cases:
            await ComplaintsService.publish_case_message(self.bot, case)
        await ctx.send(f"✅ Reprocesados {len(cases)} reclamos.")


async def setup(bot):
    await bot.add_cog(ComplaintsCog(bot))

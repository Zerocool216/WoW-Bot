import discord
from discord.ext import commands
from discord import app_commands
import config
from bot.views.agonia_views import AgoniaPanelView
from bot.repositories.agonia_repo import AgoniaRepository
from bot.services.agonia_service import AgoniaService

class AgoniaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await AgoniaService.register_persistent_case_views(self.bot)

    def is_staff(self):
        async def predicate(interaction: discord.Interaction) -> bool:
            member = interaction.user
            if isinstance(member, discord.Member):
                if await AgoniaService.is_staff(member):
                    return True
            await interaction.response.send_message("❌ No tienes permisos de staff para ejecutar este comando.", ephemeral=True)
            return False
        return app_commands.check(predicate)

    def _build_agonia_panel_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🛡️ Agonía de Sombras",
            description=(
                "Pulsa **Iniciar Solicitud** para crear un nuevo caso en el canal de Agonía.\n"
                "Todos los casos se registran en <#{}> y son gestionados por staff autorizado."
            ).format(config.AGONIA_TICKETS_CHANNEL_ID),
            color=discord.Color.gold()
        )
        embed.add_field(name="Canal de casos", value=f"<#{config.AGONIA_TICKETS_CHANNEL_ID}>", inline=False)
        embed.add_field(name="Canal de activos", value=f"<#{config.LISTA_FRAGMENTEADORES_CHANNEL_ID}>", inline=False)
        embed.add_field(name="Canal finalizado", value=f"<#{config.AGONIAS_FINALIZADAS_CHANNEL_ID}>", inline=False)
        embed.set_footer(text="Solo staff autorizado puede mover el estado de cada caso.")
        return embed

    def _build_agonia_normativa_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🛡️ Normativa: Agonía de Sombras",
            description="Normativa Oficial de Fragmentadores",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="🧭 Requisitos de Elegibilidad",
            value=(
                "Para ingresar y permanecer en la Lista de Fragmentadores, el jugador deberá cumplir obligatoriamente con los siguientes criterios:\n\n"
                "Antigüedad comprobable mínima de tres (3) meses dentro de la guild, sin historial de sanciones ni conductas que perjudiquen el progreso colectivo.\n\n"
                "Contar con al menos cinco (5) personajes activos dentro de la guild.\n\n"
                "Presentar un aporte demostrable y constante, ya sea mediante asistencia regular, apoyo en raids, participación en actividades internas o contribuciones que reflejen compromiso real con la guild."
            ),
            inline=False
        )
        embed.add_field(
            name="⚔️ Rendimiento y Rol",
            value=(
                "Mantener un desempeño destacado y consistente con el personaje que se desea fragmentar.\n\n"
                "El rendimiento será evaluado rigurosamente por GMs y oficiales, y cualquier deficiencia detectada podrá resultar en la suspensión inmediata del proceso, sin derecho a reclamo.\n\n"
                "Cumplir al menos tres (3) raids desempeñando roles críticos para la estabilidad del grupo, específicamente tanque o healer."
            ),
            inline=False
        )
        embed.add_field(
            name="🛡️ Obligaciones del Fragmentador",
            value=(
                "El personaje fragmentador estará obligado a proporcionar festines en cada raid en la que le corresponda recibir fragmentos, sin excepciones."
            ),
            inline=False
        )
        embed.add_field(
            name="⚠️ Pérdida de Prioridad y Eliminación",
            value=(
                "Todo jugador que no registre actividad durante dos (2) raids consecutivas será eliminado automáticamente de la lista de fragmentación.\n\n"
                "Esta medida es definitiva, no negociable, no reversible y no sujeta a justificaciones posteriores."
            ),
            inline=False
        )
        embed.add_field(
            name="📌 Fundamento de la Normativa",
            value=(
                "Esta normativa se implementa debido a la reiterada conducta de ciertos jugadores que abandonan sus responsabilidades por periodos prolongados sin aviso previo y posteriormente exigen retomar el proceso de fragmentación, generando retrasos injustificables, perjudicando a los jugadores activos y comprometiendo el ritmo de avance de la guild."
            ),
            inline=False
        )
        embed.add_field(
            name="✨ Disposición Final",
            value=(
                "El proceso de fragmentación es un privilegio, no un derecho.\n\n"
                "Solo será otorgado y mantenido para aquellos jugadores que demuestren compromiso constante, responsabilidad, rendimiento adecuado y respeto por el esfuerzo colectivo.\n\n"
                "El desconocimiento o desacuerdo con esta normativa no exime de su cumplimiento ni de las sanciones correspondientes."
            ),
            inline=False
        )
        embed.add_field(
            name="📥 Cómo iniciar",
            value="Pulsa 'Iniciar Solicitud' para comenzar.",
            inline=False
        )
        return embed

    async def _get_normativa_channel(self):
        channel = self.bot.get_channel(config.NORMATIVA_AGONIA_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(config.NORMATIVA_AGONIA_CHANNEL_ID)
            except Exception:
                channel = None
        return channel

    async def _cleanup_previous_normativa_panel_messages(self, channel):
        def _is_old_panel(message: discord.Message):
            if message.author.id != self.bot.user.id:
                return False
            if message.embeds:
                for embed in message.embeds:
                    if embed.title == "🛡️ Normativa: Agonía de Sombras":
                        return True
            if message.components:
                for row in message.components:
                    for component in getattr(row, 'children', []):
                        if getattr(component, 'custom_id', None) in ("agonia_panel_start_request", "agonia_panel:start_request"):
                            return True
            return False

        await channel.purge(limit=100, check=_is_old_panel)

    async def _send_panel_to_channel(self, channel, embed: discord.Embed = None):
        embed = embed or self._build_agonia_panel_embed()
        view = AgoniaPanelView()
        return await channel.send(embed=embed, view=view)

    @app_commands.command(name="agonia_panel", description="Publica el panel de Agonía de Sombras en el canal actual.")
    async def agonia_panel(self, interaction: discord.Interaction):
        embed = self._build_agonia_panel_embed()
        view = AgoniaPanelView()
        await interaction.response.send_message(embed=embed, view=view)

    @commands.command(name="agonia_panel")
    async def agonia_panel_text(self, ctx: commands.Context):
        embed = self._build_agonia_panel_embed()
        view = AgoniaPanelView()
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="agonia_recreate_panel", description="Publica de nuevo el panel de Agonía en el canal de normativa de Agonía.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def agonia_recreate_panel(self, interaction: discord.Interaction):
        canal_normativa = await self._get_normativa_channel()
        if canal_normativa is None:
            return await interaction.response.send_message(
                "❌ No se encontró el canal de normativa de Agonía.",
                ephemeral=True
            )

        try:
            await self._cleanup_previous_normativa_panel_messages(canal_normativa)
            await self._send_panel_to_channel(canal_normativa, embed=self._build_agonia_normativa_embed())
        except Exception as e:
            await interaction.response.send_message(
                f"❌ No se pudo publicar el panel en {canal_normativa.mention}: {e}",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Panel recreado en {canal_normativa.mention}.",
            ephemeral=True
        )

    @commands.command(name="agonia_recreate_panel")
    @commands.has_permissions(manage_messages=True)
    async def agonia_recreate_panel_text(self, ctx: commands.Context):
        canal_normativa = await self._get_normativa_channel()
        if canal_normativa is None:
            return await ctx.send("❌ No se encontró el canal de normativa de Agonía.")

        try:
            await self._cleanup_previous_normativa_panel_messages(canal_normativa)
            await self._send_panel_to_channel(canal_normativa, embed=self._build_agonia_normativa_embed())
        except Exception as e:
            return await ctx.send(f"❌ No se pudo publicar el panel en {canal_normativa.mention}: {e}")

        await ctx.send(f"✅ Panel recreado en {canal_normativa.mention}.")

    @app_commands.command(name="agonia_list_active", description="Lista los casos activos de Agonía de Sombras.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def agonia_list_active(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cases = await AgoniaRepository.list_active_cases()
        if not cases:
            return await interaction.followup.send("No hay casos activos en este momento.", ephemeral=True)

        lines = []
        for case in cases[:20]:
            lines.append(f"#{case['id']} • Frag {case['fragment_number']} • {case['status']} • <@{case['requester_id']}>")
        embed = discord.Embed(
            title="📋 Casos activos de Agonía",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="agonia_rebuild", description="Reconstruye los mensajes de todos los casos activos y finalizados.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def agonia_rebuild(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cases = await AgoniaRepository.list_all_cases(limit=100)
        updated = 0
        for case in cases:
            try:
                await AgoniaService.refresh_case_messages(self.bot, case)
                updated += 1
            except Exception as e:
                await AgoniaService.send_staff_log(self.bot, f"Error reconstruiendo caso #{case['id']}: {e}")
        await interaction.followup.send(f"✅ Reconstruidos {updated} casos (hasta 100).", ephemeral=True)

    @app_commands.command(name="agonia_manual_add", description="Registra manualmente una Agonía ya obtenida por la guild.")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(
        character_name="Nombre del personaje",
        class_spec="Clase / spec del personaje",
        agonia_status="Estado actual de la Agonía",
        fragment_number="Cantidad de fragmentos actuales",
        status="Estado del caso",
        requester="Usuario solicitante opcional",
        notes="Detalles adicionales"
    )
    async def agonia_manual_add(
        self,
        interaction: discord.Interaction,
        character_name: str,
        class_spec: str,
        agonia_status: str,
        fragment_number: int,
        status: str,
        requester: discord.User = None,
        notes: str = ""
    ):
        status_choices = ["pendiente", "tomado", "mas_datos", "aprobado", "activo", "pausado", "denegado", "finalizado"]
        if status not in status_choices:
            return await interaction.response.send_message(
                f"Estado de caso inválido. Usa uno de: {', '.join(status_choices)}.", ephemeral=True
            )

        requester_id = requester.id if requester else 0
        requester_name = requester.name if requester else "Manual"

        case_id = await AgoniaRepository.create_case(
            requester_id=requester_id,
            requester_name=requester_name,
            character_name=character_name.strip(),
            class_spec=class_spec.strip(),
            mains_alters="Manual",
            availability="Manual",
            agonia_status=agonia_status.strip(),
            fragment_number=fragment_number,
            has_shadows_edge=0,
            guild_seniority="Manual",
            evidence_notes=notes.strip(),
            commitment_text=notes.strip(),
            description=(
                f"Manual entry: {notes.strip()}"
            ),
            status=status
        )

        case = await AgoniaRepository.get_case(case_id)
        await AgoniaRepository.create_history(case_id, interaction.user.id, interaction.user.name, "", status, "Caso manual creado")
        await AgoniaService.create_case_messages(self.bot, case)
        await AgoniaService.send_staff_log(self.bot, f"Caso manual de Agonía #{case_id} creado por {interaction.user.name}. Estado: {status}.")
        if requester:
            await AgoniaService.notify_requester(case, self.bot, f"✅ Tu caso manual de Agonía #{case_id} ha sido registrado. Estado actual: {status}.")

        await interaction.response.send_message(
            f"✅ Caso manual registrado como #{case_id}. Estado: {status}.",
            ephemeral=True
        )

    @commands.command(name="agonia_finalize", description="Forzar finalización de un caso por ID.")
    @app_commands.describe(case_id="ID del caso de Agonía")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def agonia_finalize(self, interaction: discord.Interaction, case_id: int):
        await interaction.response.defer(ephemeral=True)
        case = await AgoniaRepository.get_case(case_id)
        if not case:
            return await interaction.followup.send(f"❌ Caso #{case_id} no encontrado.", ephemeral=True)
        await AgoniaRepository.create_history(case_id, interaction.user.id, interaction.user.name, case['status'], 'finalizado', 'Forzar finalización por staff')
        await AgoniaRepository.update_case(case_id, {'status': 'finalizado', 'assigned_staff_id': interaction.user.id, 'assigned_staff_name': interaction.user.name})
        case = await AgoniaRepository.get_case(case_id)
        await AgoniaService.send_staff_log(self.bot, f"Caso #{case_id} forzado a finalizado por {interaction.user.name}.")
        await AgoniaService.refresh_case_messages(self.bot, case)
        await interaction.followup.send(f"✅ Caso #{case_id} forzado a **finalizado**.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AgoniaCog(bot))


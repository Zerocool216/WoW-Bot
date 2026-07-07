import discord
from discord.ext import commands
from discord import app_commands
import config
from bot.views.guild_panel import GuildPanelView, create_guild_panel_embed
from bot.repositories.memberrepo import MemberRepository
from bot.services.aiservice import AIService

class GuildManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Registrar la aplicación contextual (clic derecho sobre usuario)
        self.ctx_menu = app_commands.ContextMenu(
            name="Ver ficha de miembro",
            callback=self.view_member_profile
        )
        self.ctx_menu.on_error = self.view_member_profile_error
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        # Desregistrar la aplicación contextual al recargar
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @app_commands.command(name="guild-panel", description="Envía el panel interactivo táctil para la gestión de la hermandad.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def guild_panel(self, interaction: discord.Interaction):
        """
        Slash command para inicializar el panel táctil en canales de staff.
        """
        if "staff" not in interaction.channel.name.lower() and "oficial" not in interaction.channel.name.lower() and "admin" not in interaction.channel.name.lower():
            await interaction.response.send_message(
                "⚠️ **Aviso de Seguridad:** Por razones de privacidad, se recomienda inicializar este panel únicamente en canales restringidos de staff o administración.",
                ephemeral=True
            )
            
        embed = create_guild_panel_embed()
        view = GuildPanelView()
        await interaction.response.send_message(embed=embed, view=view)

    @guild_panel.error
    async def guild_panel_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("❌ No tienes permisos de `Gestionar Servidor` para ejecutar este comando administrativo.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Ocurrió un error al procesar el comando: {error}", ephemeral=True)

    @app_commands.checks.has_permissions(manage_messages=True)
    async def view_member_profile(self, interaction: discord.Interaction, member: discord.Member):
        """
        Callback para el Menú Contextual (Clic derecho sobre usuario -> Apps -> Ver ficha de miembro).
        """
        await interaction.response.defer(ephemeral=True)
        
        rank_info = MemberRepository.get_guild_rank_for_member(member.roles)
        rank_name = rank_info["name"] if rank_info else "Ninguno"
        rank_tier = rank_info["tier"] if rank_info else 12

        notes = await MemberRepository.get_staff_notes(member.id)
        
        embed = discord.Embed(
            title=f"👤 Ficha de Miembro: {member.display_name}",
            description=f"Análisis administrativo de comportamiento de `{member.name}`.",
            color=discord.Color.blue()
        )
        
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID de Discord", value=f"`{member.id}`", inline=True)
        
        joined_time = f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Desconocido"
        embed.add_field(name="Antigüedad", value=joined_time, inline=True)
        embed.add_field(name="Rango Oficial", value=f"**{rank_name}** *(Tier {rank_tier}/12)*", inline=False)
        
        if notes:
            note_lines = []
            for n in notes[:3]:
                note_lines.append(
                    f"• *{n['created_at']}* por {n['staff_username']}: {n['note']} *(Sugerencia IA: {n['suggested_action']})*"
                )
            embed.add_field(name=f"📝 Historial de Incidencias ({len(notes)})", value="\n".join(note_lines), inline=False)
        else:
            embed.add_field(name="📝 Historial de Incidencias", value="Este miembro está libre de reportes o anotaciones conductuales.", inline=False)

        class IAMemberReviewView(discord.ui.View):
            def __init__(self, target_member, target_rank_info, target_notes):
                super().__init__(timeout=60)
                self.member = target_member
                self.rank_info = target_rank_info
                self.notes = target_notes

            @discord.ui.button(label="🧠 Analizar con IA", style=discord.ButtonStyle.primary, custom_id="guild_panel:member_ai_review")
            async def btn_ai_review(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                ai_enabled = await AIService.is_enabled()
                if not ai_enabled:
                    await btn_interaction.response.send_message(
                        "⚠️ **Asistencia de IA Desactivada:** Falta configurar una `AIAPIKEY` válida en el archivo `.env`.",
                        ephemeral=True
                    )
                    return

                await btn_interaction.response.defer(ephemeral=True)
                analysis = await AIService.analyze_user_behavior(self.member.name, self.rank_info, self.notes, btn_interaction.client)
                
                ai_embed = discord.Embed(
                    title=f"🧠 Reporte Cognitivo de IA: {self.member.display_name}",
                    description=analysis,
                    color=discord.Color.dark_magenta()
                )
                ai_embed.set_footer(text="Asistente de IA de Hermandad • Información estrictamente orientativa")
                await btn_interaction.followup.send(embed=ai_embed, ephemeral=True)

        view = IAMemberReviewView(member, rank_info or {"name": "Ninguno", "tier": 12}, notes)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def view_member_profile_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("❌ No tienes permisos de `Gestionar Mensajes` (Staff) para ver fichas técnicas de miembros.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Ocurrió un error al procesar la aplicación contextual: {error}", ephemeral=True)

    # =============================================
    # COMANDOS DE REGLAS DINÁMICAS DE IA
    # =============================================

    @app_commands.command(name="ai-rules-source", description="Muestra el estado de la caché y la fuente de reglas activa de la IA.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def ai_rules_source(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from bot.services.rulesservice import RulesService
        
        await RulesService.get_rules_text(interaction.client)
        info = RulesService.get_cache_info()
        
        source_emoji = {
            "file": "📁 Archivo Local",
            "discord_attachment": "📎 Adjunto de Discord",
            "discord_pinned": "📌 Mensajes Fijados",
            "discord_recent": "💬 Mensajes Curados",
            "none": "❌ Ninguno (Sin Reglas)"
        }.get(info["source_type"], info["source_type"])
        
        embed = discord.Embed(
            title="📋 Estado y Origen de Reglas de IA",
            color=discord.Color.blue()
        )
        embed.add_field(name="Fuente Activa", value=f"**{source_emoji}**", inline=True)
        embed.add_field(name="Identificador", value=f"`{info['source_identifier']}`", inline=False)
        embed.add_field(name="Longitud de Contenido", value=f"{info['content_length']} caracteres", inline=True)
        embed.add_field(name="Hash (MD5)", value=f"`{info['content_hash']}`" if info['content_hash'] else "N/A", inline=True)
        embed.add_field(name="Última Carga", value=f"{info['last_loaded_str']}", inline=True)
        
        ttl_desc = f"{info['ttl_remaining']}s restantes" if info['ttl_remaining'] > 0 else "Expirado / Por recargar"
        embed.add_field(name="Caché TTL", value=ttl_desc, inline=True)
        
        class ReloadRulesView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                
            @discord.ui.button(label="🔄 Recargar Caché", style=discord.ButtonStyle.danger)
            async def btn_reload(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                await btn_interaction.response.defer(ephemeral=True)
                RulesService.invalidate_cache()
                await RulesService.get_rules_text(btn_interaction.client)
                new_info = RulesService.get_cache_info()
                
                new_source = {
                    "file": "📁 Archivo Local",
                    "discord_attachment": "📎 Adjunto de Discord",
                    "discord_pinned": "📌 Mensajes Fijados",
                    "discord_recent": "💬 Mensajes Curados",
                    "none": "❌ Ninguno"
                }.get(new_info["source_type"], new_info["source_type"])
                
                new_embed = discord.Embed(
                    title="📋 Reglas de IA (Recargado)",
                    color=discord.Color.green()
                )
                new_embed.add_field(name="Fuente Activa", value=f"**{new_source}**", inline=True)
                new_embed.add_field(name="Identificador", value=f"`{new_info['source_identifier']}`", inline=False)
                new_embed.add_field(name="Longitud", value=f"{new_info['content_length']} caracteres", inline=True)
                new_embed.add_field(name="Hash (MD5)", value=f"`{new_info['content_hash']}`" if new_info['content_hash'] else "N/A", inline=True)
                
                button.disabled = True
                button.label = "✅ Recargada"
                await btn_interaction.edit_original_response(embed=new_embed, view=self)
                
        await interaction.followup.send(embed=embed, view=ReloadRulesView(), ephemeral=True)

    @ai_rules_source.error
    async def ai_rules_source_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("❌ No tienes permisos de `Gestionar Mensajes` (Staff) para ver el origen de reglas.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)

    @app_commands.command(name="ai-rules-reload", description="Fuerza la invalidación de la caché de reglas y relee la fuente activa.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def ai_rules_reload(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from bot.services.rulesservice import RulesService
        
        RulesService.invalidate_cache()
        text, source, ident = await RulesService.get_rules_text(interaction.client)
        
        embed = discord.Embed(
            title="🔄 Caché de Reglas Recargada",
            description=f"**Fuente:** `{source}`\n**Identificador:** `{ident}`\n**Longitud:** {len(text)} caracteres.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @ai_rules_reload.error
    async def ai_rules_reload_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("❌ No tienes permisos de `Gestionar Mensajes` (Staff) para recargar las reglas.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)

    @app_commands.command(name="ai-rules-test", description="Ejecuta un diagnóstico completo del sistema de carga de reglas y permisos.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def ai_rules_test(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from bot.services.rulesservice import RulesService
        import os
        import aiohttp
        
        embed = discord.Embed(
            title="🔍 Diagnóstico de Reglas Dinámicas de IA",
            description="Probando secuencialmente todas las estrategias de carga...",
            color=discord.Color.orange()
        )
        
        # Test 1: Permisos del canal de Discord
        channel_id = getattr(config, "RULES_CHANNEL_ID", 1492560647068844212)
        channel = interaction.client.get_channel(channel_id)
        if not channel:
            try:
                channel = await interaction.client.fetch_channel(channel_id)
            except Exception:
                channel = None
                
        has_view = has_history = False
        if channel and isinstance(channel, discord.TextChannel):
            me = channel.guild.me
            perms = channel.permissions_for(me)
            has_view = perms.read_messages
            has_history = perms.read_message_history
            
            perms_list = []
            perms_list.append("✅ Ver Canal" if has_view else "❌ Ver Canal")
            perms_list.append("✅ Leer Historial" if has_history else "❌ Leer Historial")
            
            embed.add_field(
                name="1. Canal de Discord & Permisos",
                value=f"Canal: #{channel.name} (`{channel_id}`)\n{', '.join(perms_list)}",
                inline=False
            )
        else:
            embed.add_field(
                name="1. Canal de Discord & Permisos",
                value=f"❌ No accesible. ID: `{channel_id}`.",
                inline=False
            )
            
        # Test 2: Archivo local
        file_path = getattr(config, "RULES_FILE_PATH", "Reglas.txt")
        file_exists = os.path.exists(file_path)
        file_size = os.path.getsize(file_path) if (file_exists and os.path.isfile(file_path)) else 0
        
        if file_exists and file_size > 0:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    char_count = len(f.read().strip())
                embed.add_field(
                    name="2. Archivo Local",
                    value=f"✅ `{file_path}` — {file_size} bytes ({char_count} chars)",
                    inline=False
                )
            except Exception as e:
                embed.add_field(name="2. Archivo Local", value=f"❌ Error: {e}", inline=False)
        else:
            embed.add_field(name="2. Archivo Local", value=f"⚠️ No encontrado o vacío: `{file_path}`", inline=False)
            
        if channel and has_view and has_history:
            # Test 3: Adjunto
            adjunto_found = False
            adjunto_name = ""
            adjunto_len = 0
            try:
                async for msg in channel.history(limit=50):
                    for att in msg.attachments:
                        if att.filename.endswith(('.txt', '.md')):
                            adjunto_found = True
                            adjunto_name = att.filename
                            async with aiohttp.ClientSession() as session:
                                async with session.get(att.url) as resp:
                                    if resp.status == 200:
                                        t = await resp.text(encoding='utf-8', errors='ignore')
                                        adjunto_len = len(t.strip())
                            break
                    if adjunto_found:
                        break
                if adjunto_found:
                    embed.add_field(name="3. Adjunto en Canal", value=f"✅ `{adjunto_name}` — {adjunto_len} chars", inline=False)
                else:
                    embed.add_field(name="3. Adjunto en Canal", value="❌ Ningún `.txt`/`.md` encontrado", inline=False)
            except Exception as e:
                embed.add_field(name="3. Adjunto en Canal", value=f"❌ Error: {e}", inline=False)
                
            # Test 4: Fijados
            try:
                pins = await channel.pins()
                pinned_texts = [p.content for p in pins if p.content.strip() and not p.author.bot]
                if pinned_texts:
                    combined_len = len("\n\n".join(pinned_texts))
                    embed.add_field(name="4. Mensajes Fijados", value=f"✅ {len(pinned_texts)} mensajes — {combined_len} chars", inline=False)
                else:
                    embed.add_field(name="4. Mensajes Fijados", value="❌ Sin mensajes fijados válidos", inline=False)
            except Exception as e:
                embed.add_field(name="4. Mensajes Fijados", value=f"❌ Error: {e}", inline=False)
                
            # Test 5: Curados
            try:
                curated = []
                async for msg in channel.history(limit=50):
                    if msg.author.bot or not msg.content.strip():
                        continue
                    c = msg.content.strip()
                    if c.startswith(('!', '/', '$', '?')) or len(c) < 15:
                        continue
                    curated.append(c)
                    if len(curated) >= 20:
                        break
                if curated:
                    combined_len = len("\n\n".join(curated))
                    embed.add_field(name="5. Mensajes Curados", value=f"✅ {len(curated)} mensajes — {combined_len} chars", inline=False)
                else:
                    embed.add_field(name="5. Mensajes Curados", value="❌ Sin mensajes válidos", inline=False)
            except Exception as e:
                embed.add_field(name="5. Mensajes Curados", value=f"❌ Error: {e}", inline=False)
        else:
            embed.add_field(name="Estrategias Discord", value="❌ Saltadas (canal inaccesible o sin permisos)", inline=False)
            
        # Resolución final
        RulesService.invalidate_cache()
        rules_text, resolved_source, resolved_id = await RulesService.get_rules_text(interaction.client)
        source_emoji = {
            "file": "📁 Archivo Local",
            "discord_attachment": "📎 Adjunto",
            "discord_pinned": "📌 Fijados",
            "discord_recent": "💬 Curados",
            "none": "❌ Ninguno"
        }.get(resolved_source, resolved_source)
        
        embed.add_field(
            name="🏁 Resolución Final (AUTO)",
            value=f"**{source_emoji}** — `{resolved_id}`\n{len(rules_text)} caracteres cargados.",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @ai_rules_test.error
    async def ai_rules_test_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("❌ No tienes permisos de `Gestionar Mensajes` (Staff) para diagnosticar las reglas.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)

    @app_commands.command(name="ai-ask-rules", description="Pregunta a la IA sobre las reglas de la hermandad (DKP, loot, convivencia).")
    async def ai_ask_rules(self, interaction: discord.Interaction, pregunta: str):
        """Comando abierto para resolver dudas normativas mediante IA."""
        ai_enabled = await AIService.is_enabled()
        if not ai_enabled:
            await interaction.response.send_message(
                "⚠️ **Asistencia de IA Desactivada:** Configura `AIAPIKEY` en el archivo `.env`.",
                ephemeral=True
            )
            return
            
        await interaction.response.defer(ephemeral=False)
        respuesta = await AIService.answer_from_rules(pregunta, bot=interaction.client)
        
        embed = discord.Embed(
            title="❓ Consulta Normativa",
            description=f"**Pregunta:**\n\"{pregunta}\"\n\n**Respuesta:**\n{respuesta}",
            color=discord.Color.dark_magenta()
        )
        embed.set_footer(text="Asistente de IA de Hermandad • Consulta de reglas")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(GuildManagementCog(bot))

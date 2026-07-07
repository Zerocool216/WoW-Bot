import os
import discord
import config
from bot.repositories.config_repo import ConfigRepository
from bot.views.whatsapp_modal import WhatsAppConfigModal

class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _update_panel(self, interaction: discord.Interaction):
        current_config = await ConfigRepository.get_config()
        embed = create_panel_embed(current_config)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Selecciona Canal para Hermandad...",
        custom_id="admin_panel:select_guild",
        row=0
    )
    async def select_guild(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        channel = select.values[0]
        await ConfigRepository.update_config({"canal_guild_discord_id": channel.id})
        await self._update_panel(interaction)

    @discord.ui.button(label="Fase 5: Entrar al Mundo (Harukoo)", style=discord.ButtonStyle.success, custom_id="admin_panel:test_auth", row=2)
    async def btn_test_auth(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        # Recuperamos la instancia del adapter desde el cliente de discord
        adapter = interaction.client.bridge_service.adapter
        
        if hasattr(adapter, 'execute_test_handshake'):
            result = await adapter.execute_test_handshake()
            
            embed = discord.Embed(title="📊 Resultado Sesión de Mundo (Fase 5)", color=discord.Color.green() if "SUCCESS" in result['status'] else discord.Color.red())
            embed.add_field(name="Host Probado", value=f"`{config.WOW_REALMLIST}`", inline=False)
            embed.add_field(name="Estado Final", value=f"**{result['status']}**", inline=False)
            embed.add_field(name="Detalles", value=f"```{result['details']}```", inline=False)
            
            if 'hex_preview' in result:
                embed.add_field(name="Hex Preview (Primeros bytes)", value=f"`{result['hex_preview']}`", inline=False)
                
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Actualizamos el panel visual general (no efímero)
            msg = await interaction.original_response()
            if msg:
                current_config = await ConfigRepository.get_config()
                panel_embed = create_panel_embed(current_config)
                await msg.edit(embed=panel_embed, view=self)
        else:
            await interaction.followup.send("El adaptador actual no soporta pruebas directas.", ephemeral=True)

    @discord.ui.button(label="Detalles de Estado", style=discord.ButtonStyle.primary, custom_id="admin_panel:network_details", row=2)
    async def btn_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_config = await ConfigRepository.get_config()
        error = current_config.get("wow_last_error")
        state = current_config.get("wow_connection_state")
        
        detail_msg = f"**Información Real del Headless Client:**\n"
        detail_msg += f"- **Auth Server (NaerZone)**: `{config.WOW_REALMLIST}:3724`\n"
        # Enmascaramos la cuenta por seguridad (ej: USUARIO -> U****O)
        acc = config.WOW_ACCOUNT
        acc_masked = f"{acc[0]}****{acc[-1]}" if len(acc) > 2 else "****"
        detail_msg += f"- **Reino Objetivo**: `{config.WOW_REALM}`\n"
        detail_msg += f"- **Cuenta**: `{acc_masked}` (Contraseña jamás expuesta)\n"
        detail_msg += f"- **Estado**: `{state}`\n"
        detail_msg += f"- **Último Resultado Técnico**: `{error if error else 'Ninguno'}`\n"
        
        await interaction.response.send_message(detail_msg, ephemeral=True)

    @discord.ui.button(label="Ver Logs", style=discord.ButtonStyle.secondary, custom_id="admin_panel:logs", row=3)
    async def btn_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        log_path = os.path.join(config.LOGS_DIR, "bot.log")
        if not os.path.exists(log_path):
            await interaction.response.send_message("No hay archivo de logs todavía.", ephemeral=True)
            return
            
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            last_lines = "".join(lines[-15:])
            
        embed = discord.Embed(title="📄 Logs (Buscando Evidencia TCP)", description=f"```log\n{last_lines}\n```", color=discord.Color.dark_grey())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Actualizar", style=discord.ButtonStyle.secondary, custom_id="admin_panel:refresh", row=3)
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_panel(interaction)

    @discord.ui.button(label="📋 Publicar Reglas", style=discord.ButtonStyle.danger, custom_id="admin_panel:publish_rules", row=4)
    async def btn_publish_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        RULES_CHANNEL_ID = 1473420213021048916
        IMAGE_PATH = os.path.join(os.path.dirname(config.__file__), "Reglas.jpeg")

        if not os.path.exists(IMAGE_PATH):
            await interaction.followup.send(
                f"❌ No se encontró el archivo `Reglas.jpeg` en la carpeta del bot.\nRuta buscada: `{IMAGE_PATH}`",
                ephemeral=True
            )
            return

        try:
            channel = interaction.client.get_channel(RULES_CHANNEL_ID)
            if not channel:
                channel = await interaction.client.fetch_channel(RULES_CHANNEL_ID)

            existing_id = await ConfigRepository.get_rules_message_id()

            file = discord.File(IMAGE_PATH, filename="Reglas.jpeg")

            if existing_id:
                try:
                    old_msg = await channel.fetch_message(existing_id)
                    await old_msg.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass  # Ya no existe, continuamos

            # Publicar nuevo mensaje con la imagen
            new_msg = await channel.send(file=file)
            await ConfigRepository.set_rules_message_id(new_msg.id)

            await interaction.followup.send(
                f"✅ **Reglas publicadas correctamente** en <#{RULES_CHANNEL_ID}>.\n"
                f"ID del mensaje guardado. La próxima vez que pulses el botón, se borrará el actual y se publicará la nueva versión.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Error al publicar reglas: `{e}`", ephemeral=True)

    @discord.ui.button(label="AGONIA MANUAL", style=discord.ButtonStyle.danger, custom_id="admin_panel:agonia_manual", row=4)
    async def btn_agonia_manual(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Solo staff puede usar este botón en el panel admin
        member = interaction.user
        if not isinstance(member, discord.Member) or not (member.guild_permissions.administrator or member.id in config.ADMINUSERIDS):
            return await interaction.response.send_message("❌ No tienes permisos para usar AGONIA MANUAL.", ephemeral=True)

        # Abrir el modal de registro manual de Agonía
        from bot.views.agonia_views import MinimalManualCompleteModal
        await interaction.response.send_modal(MinimalManualCompleteModal())

    @discord.ui.button(label="📱 Gestionar WhatsApp", style=discord.ButtonStyle.primary, custom_id="admin_panel:manage_whatsapp", row=4)
    async def btn_manage_whatsapp(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = await ConfigRepository.get_whatsapp_config()
        current_invite = cfg.get("whatsapp_invite_url", "")
        current_qr = cfg.get("whatsapp_qr_url", "")

        modal = WhatsAppConfigModal(current_invite=current_invite, current_qr=current_qr)
        await interaction.response.send_modal(modal)

def create_panel_embed(current_config: dict) -> discord.Embed:
    embed = discord.Embed(
        title="🛡️ WoW Bridge Control Panel (Fase 5)",
        description="Integración Nativa TCP - NaerZone: Thalassa.",
        color=discord.Color.blurple()
    )
    
    # Estados de red
    wow_state = current_config.get("wow_connection_state", "🔴 Desconectado")
    
    # Regla de Honestidad Técnica
    if "Mundo" in wow_state:
        if "Harukoo" in wow_state:
            wow_state = f"🟢 {wow_state}"
        else:
            wow_state = f"🟡 {wow_state}"
    elif "ACCEPTED" in wow_state:
        wow_state = "🟡 Autenticación Aceptada (Entrando al Mundo...)"
        
    embed.add_field(name="Estado Red WoW", value=f"**{wow_state}**", inline=False)
    embed.add_field(name="Personaje Objetivo", value=f"`{config.WOW_CHARACTER}`", inline=True)
    embed.add_field(name="Servidor Objetivo", value=f"NaerZone (`{config.WOW_REALMLIST}`)", inline=True)
    embed.add_field(name="Reino Configurado", value=f"`{config.WOW_REALM}`", inline=True)
    embed.add_field(name="Transparencia Técnica", value="El bot NO simula. El botón 'Probar TCP' enviará bytes reales al host y mostrará la respuesta.", inline=False)
    
    # Estado de WhatsApp
    wa_url = current_config.get("whatsapp_invite_url")
    if wa_url:
        wa_status = f"✅ Configurado (Canal: <#{current_config.get('whatsapp_channel_id')}\u200b>)"
    else:
        wa_status = "⚠️ No configurado"
    embed.add_field(name="Módulo WhatsApp", value=wa_status, inline=True)

    # Estado de Reglas
    rules_msg_id = current_config.get("rules_message_id")
    rules_status = f"✅ Publicadas (msg: `{rules_msg_id}`)" if rules_msg_id else "⚠️ No publicadas aún"
    embed.add_field(name="📋 Reglas (imagen)", value=rules_status, inline=True)

    embed.set_footer(text="Bot de hermandad - 3.3.5a | NaerZone - Thalassa | Hito 1: Auth Handshake")
    return embed

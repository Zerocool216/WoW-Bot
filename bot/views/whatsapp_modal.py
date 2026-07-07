import discord
import logging
from bot.repositories.config_repo import ConfigRepository
from bot.utils.whatsapp_embed import build_whatsapp_embed

logger = logging.getLogger("WhatsAppModal")

class WhatsAppSyncView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🚀 Publicar / Sincronizar WhatsApp", style=discord.ButtonStyle.success, custom_id="whatsapp_sync_btn")
    async def btn_sync(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        try:
            config = await ConfigRepository.get_whatsapp_config()
            invite_url = config.get("whatsapp_invite_url")
            qr_url = config.get("whatsapp_qr_url")
            channel_id = config.get("whatsapp_channel_id")
            message_id = config.get("whatsapp_message_id")
            
            if not invite_url or not channel_id:
                await interaction.followup.send("⚠️ Falta configurar el enlace de invitación o el canal.", ephemeral=True)
                return
                
            channel = interaction.client.get_channel(int(channel_id))
            if not channel:
                await interaction.followup.send("❌ No se encontró el canal configurado.", ephemeral=True)
                return

            embed = build_whatsapp_embed(invite_url, qr_url)

            # Intentar editar el mensaje existente
            if message_id:
                try:
                    msg = await channel.fetch_message(int(message_id))
                    await msg.edit(embed=embed)
                    await interaction.followup.send("✅ Sección de WhatsApp actualizada con éxito (Mensaje editado).", ephemeral=True)
                    return
                except discord.NotFound:
                    # El mensaje fue borrado, crearemos uno nuevo
                    pass
                except Exception as e:
                    logger.error(f"Error editando mensaje de WhatsApp: {e}")
                    # Continuar y publicar uno nuevo como fallback

            # Publicar nuevo si no existe o falló la edición
            new_msg = await channel.send(embed=embed)
            await ConfigRepository.set_whatsapp_message_id(new_msg.id)
            await interaction.followup.send("✅ Sección de WhatsApp publicada con éxito (Nuevo mensaje).", ephemeral=True)

        except Exception as e:
            logger.error(f"Error en sincronización de WhatsApp: {e}")
            await interaction.followup.send("❌ Ocurrió un error al sincronizar WhatsApp.", ephemeral=True)

class WhatsAppConfigModal(discord.ui.Modal, title="Configurar WhatsApp"):
    invite_input = discord.ui.TextInput(
        label="Enlace del Grupo WhatsApp",
        placeholder="https://chat.whatsapp.com/...",
        required=True,
        max_length=200
    )
    
    qr_input = discord.ui.TextInput(
        label="URL de Imagen del Código QR",
        placeholder="https://ejemplo.com/qr.png",
        required=False,
        max_length=500
    )

    def __init__(self, current_invite: str = "", current_qr: str = ""):
        super().__init__()
        self.invite_input.default = current_invite
        self.qr_input.default = current_qr

    async def on_submit(self, interaction: discord.Interaction):
        invite_val = self.invite_input.value.strip()
        qr_val = self.qr_input.value.strip()

        if not invite_val.startswith("https://chat.whatsapp.com/"):
            await interaction.response.send_message("❌ El enlace debe comenzar con 'https://chat.whatsapp.com/'.", ephemeral=True)
            return

        try:
            config = await ConfigRepository.get_whatsapp_config()
            channel_id = config.get("whatsapp_channel_id", 1480229242079023124)
            
            await ConfigRepository.set_whatsapp_config(invite_val, qr_val, channel_id)
            
            view = WhatsAppSyncView()
            await interaction.response.send_message("✅ Configuración guardada. Usa el botón abajo para sincronizar al canal.", view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error guardando config de WhatsApp: {e}")
            await interaction.response.send_message("❌ Ocurrió un error al guardar.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Error en Modal WhatsApp: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Ocurrió un error inesperado.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Ocurrió un error inesperado.", ephemeral=True)

import discord
from datetime import datetime

def build_whatsapp_embed(invite_url: str, qr_url: str | None = None, shared_by: discord.Member | discord.User | None = None) -> discord.Embed:
    """Construye el embed premium oficial del sistema de WhatsApp."""
    
    # Color principal: verde oficial de WhatsApp
    embed = discord.Embed(
        title="📱 ÚNETE AL GRUPO DE WHATSAPP",
        url=invite_url if invite_url else None,
        description="¡Únete a nuestra comunidad en WhatsApp para estar al día de raids, notificaciones importantes y convivencia diaria!",
        color=0x25D366,
        timestamp=datetime.utcnow()
    )

    embed.set_author(name="MVP Guild System · NaerZone")

    # Fields
    embed.add_field(name="🗡️ Raids & Progresión", value="Avisos en tiempo real.", inline=True)
    embed.add_field(name="🔔 Notificaciones VIP", value="Coordinación rápida para eventos.", inline=True)
    embed.add_field(name="💬 Comunidad Daily", value="Charla activa y soporte del Staff.", inline=False)
    
    embed.add_field(name="🌐 Enlace Directo", value=f"[Hacer clic para unirse]({invite_url})" if invite_url else "Enlace no configurado", inline=False)

    # Imagen QR si existe
    if qr_url:
        embed.set_image(url=qr_url)
        
    # Footer
    footer_text = "MVP Guild System · Escanea el QR o usa el enlace superior"
    embed.set_footer(text=footer_text)
    
    # Si fue compartido por alguien
    if shared_by:
        embed.add_field(name="✨ Compartido por:", value=shared_by.mention, inline=False)

    return embed

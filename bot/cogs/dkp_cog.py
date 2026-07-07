import asyncio
import json
import logging
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

logger = logging.getLogger("DkpCog")

# Canal de Discord donde se publican los rankings de DKP
DKP_CHANNEL_ID = 1475500628922073269

# Tiempo máximo (segundos) para recibir todos los chunks antes de descartar
CHUNK_TIMEOUT = 300.0

# Colores por clase WoW para el embed
CLASS_COLORS = {
    "WARRIOR":     0xC69B3A,
    "PALADIN":     0xF58CBA,
    "HUNTER":      0xABD473,
    "ROGUE":       0xFFF569,
    "PRIEST":      0xFFFFFF,
    "DEATHKNIGHT": 0xC41E3A,
    "SHAMAN":      0x0070DE,
    "MAGE":        0x40C7EB,
    "WARLOCK":     0x8787ED,
    "DRUID":       0xFF7D0A,
}

# Emojis de posición para el ranking
RANK_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


class DkpCog(commands.Cog):
    """
    Recibe el ranking de DKP enviado por el addon MRT via susurros (whisper chunks)
    y lo publica como un Embed visual en el canal de Discord configurado.

    Protocolo de mensajes esperado (enviados por el addon DKP.lua):
      DKP_START:{total_chunks}:{guild_name}:{fecha}
      DKP_CHUNK:{index}:{json_fragment}
      DKP_CHUNK:{index}:{json_fragment}
      ...
      DKP_END
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Buffer de sesiones activas: { sender_name: { "total": int, "chunks": dict, "meta": dict, "task": Task } }
        self._sessions: dict = {}

    # ──────────────────────────────────────────────────────────────
    # Punto de entrada público: llamado desde bridge_service.py
    # ──────────────────────────────────────────────────────────────
    async def receive_wow_message(self, msg: dict) -> bool:
        """
        Procesa un evento de chat de WoW. Retorna True si el mensaje fue consumido
        por el protocolo DKP (para que bridge_service no lo retransmita a otros canales).
        """
        if msg.get("type") != "WHISPER":
            return False

        sender = msg.get("sender", "")
        content = msg.get("message", "").strip()

        if not content.startswith("DKP_"):
            return False

        logger.info(f"[DKP-COG] Mensaje DKP recibido de '{sender}': {content[:80]}")

        if content.startswith("DKP_START:"):
            await self._handle_start(sender, content)
            return True

        if content.startswith("DKP_CHUNK:"):
            await self._handle_chunk(sender, content)
            return True

        if content == "DKP_END":
            await self._handle_end(sender)
            return True

        return False

    # ──────────────────────────────────────────────────────────────
    # Handlers del protocolo
    # ──────────────────────────────────────────────────────────────
    async def _handle_start(self, sender: str, content: str):
        """Inicia una nueva sesión de recepción."""
        # Cancelar sesión previa si existía
        if sender in self._sessions and self._sessions[sender].get("task"):
            self._sessions[sender]["task"].cancel()

        # Parsear: DKP_START:{total}:{guild}:{fecha}
        parts = content.split(":", 3)
        total  = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        guild  = parts[2] if len(parts) > 2 else "Guild"
        fecha  = parts[3] if len(parts) > 3 else datetime.now().strftime("%d/%m/%Y %H:%M")

        self._sessions[sender] = {
            "total":  total,
            "chunks": {},
            "meta":   {"guild": guild, "fecha": fecha, "sender": sender},
            "task":   None,
        }

        # Timer de seguridad: si no llega DKP_END en tiempo, limpiar
        async def _timeout():
            await asyncio.sleep(CHUNK_TIMEOUT)
            if sender in self._sessions:
                logger.warning(f"[DKP-COG] Timeout esperando chunks de '{sender}'. Sesión descartada.")
                del self._sessions[sender]

        self._sessions[sender]["task"] = asyncio.create_task(_timeout())
        logger.info(f"[DKP-COG] Sesión iniciada de '{sender}': {total} chunks esperados. Guild={guild}")

    async def _handle_chunk(self, sender: str, content: str):
        """Acumula un chunk de JSON."""
        if sender not in self._sessions:
            logger.warning(f"[DKP-COG] Chunk recibido de '{sender}' sin sesión activa. Ignorando.")
            return

        # Parsear: DKP_CHUNK:{index}:{datos}
        colon1 = content.index(":", 4)          # después de "DKP_"
        colon2 = content.index(":", colon1 + 1)
        idx  = int(content[colon1 + 1:colon2])
        data = content[colon2 + 1:]

        self._sessions[sender]["chunks"][idx] = data
        received = len(self._sessions[sender]["chunks"])
        total    = self._sessions[sender]["total"]
        logger.info(
            f"[DKP-COG] Chunk {idx}/{total} recibido de '{sender}' (len={len(data)}, prefix={data[:20]!r}, suffix={data[-20:]!r})"
        )
        if received != total:
            logger.debug(
                f"[DKP-COG] Estado actual de chunks para '{sender}': recibidos={received}, esperado={total}, indices={sorted(self._sessions[sender]['chunks'].keys())}"
            )

    async def _handle_end(self, sender: str):
        """Reconstruye el JSON y publica el embed."""
        if sender not in self._sessions:
            logger.warning(f"[DKP-COG] DKP_END recibido de '{sender}' sin sesión activa.")
            return

        session = self._sessions.pop(sender)
        if session.get("task"):
            session["task"].cancel()

        chunks  = session["chunks"]
        total   = session["total"]
        meta    = session["meta"]

        received = len(chunks)
        missing = [i for i in range(1, total + 1) if i not in chunks]
        logger.info(
            f"[DKP-COG] DKP_END de '{sender}': received={received}, expected={total}, missing={missing}"
        )

        # Reconstruir el JSON ordenando los chunks por índice
        json_str = "".join(chunks[i] for i in sorted(chunks.keys()))
        logger.info(f"[DKP-COG] JSON reconstruido ({len(json_str)} chars, {received}/{total} chunks).")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"[DKP-COG] Error parseando JSON de '{sender}': {e}")
            logger.error(f"[DKP-COG] JSON recibido (primeros 500 chars): {json_str[:500]}")
            logger.error(
                f"[DKP-COG] Detalle de chunks recibidos: {sorted(chunks.keys())}, sizes={{{', '.join(f'{k}:{len(v)}' for k,v in chunks.items())}}}"
            )
            return

        await self._publish_embed(data, meta)

    # ──────────────────────────────────────────────────────────────
    # Publicación del Embed en Discord
    # ──────────────────────────────────────────────────────────────
    async def _publish_embed(self, data: list, meta: dict):
        """Formatea y publica el ranking de DKP en Discord coincidiendo con el diseño premium."""
        channel = self.bot.get_channel(DKP_CHANNEL_ID)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(DKP_CHANNEL_ID)
            except Exception as e:
                logger.error(f"[DKP-COG] No se pudo obtener el canal {DKP_CHANNEL_ID}: {e}")
                return

        # Ordenar por DKP descendente
        data.sort(key=lambda x: x.get("dkp", 0), reverse=True)
        
        # Publicar todos los players con DKP > 0 (excluir ceros).
        # Antes el bot limitaba a Top 80; ahora respetamos el pedido de publicar a todos
        # los jugadores con DKP positivo.
        top_data = []
        for entry in data:
            try:
                dkp_val = float(entry.get("dkp", 0))
            except Exception:
                dkp_val = 0
            if dkp_val > 0:
                top_data.append(entry)

        fecha = meta.get("fecha", datetime.now().strftime("%d/%m/%Y %H:%M"))

        # Construir líneas del ranking
        lines = []
        for pos, entry in enumerate(top_data, start=1):
            name  = entry.get("name", "?")
            
            # Formatear el dkp asegurando que sea un número sin decimales si es entero, 
            # pero el addon ahora manda .00. Lo convertimos a float y formateamos.
            try:
                dkp_val = float(entry.get("dkp", 0))
                # Mostrar sin decimales si es entero para ahorrar espacio visual, o con decimales si los tiene
                if dkp_val.is_integer():
                    dkp_str = f"{int(dkp_val)}"
                else:
                    dkp_str = f"{dkp_val:.2f}"
            except:
                dkp_str = str(entry.get("dkp", 0))

            medal = RANK_MEDALS.get(pos, "")
            medal_str = f"{medal} " if medal else ""
            
            # Formato: 1. 🥇 ◾ Nombre ▸ ` 1000 ` pts
            lines.append(f"**{pos}.** {medal_str}◾ **{name}** ▸ `{dkp_str}` **pts**")

        logger.info(f"[DKP-COG] Built {len(lines)} DKP lines for embed.")
        if len(lines) >= 45:
            sample_lines = lines[0:45]
        else:
            sample_lines = lines
        logger.debug(f"[DKP-COG] First 45 lines:\n" + "\n".join(sample_lines))

        if len(lines) >= 42:
            sample_40 = lines[35:42]
            logger.info(
                "[DKP-COG] Preview lines 36-42 before send:\n" + \
                "\n".join(f"{36 + idx}. {line}" for idx, line in enumerate(sample_40))
            )

        if not lines:
            embed = discord.Embed(
                title="📈 TABLA REGISTRO DKP",
                description="*No hay datos de DKP para mostrar.*",
                color=0x2b2d31
            )
            await channel.send(embed=embed)
            return

        # Discord Embed Description limit is 4096.
        # Split the ranking into fixed 40-line embeds to preserve numbering boundaries.
        CHUNK_SIZE = 40
        embeds = []

        def make_embed(chunk_lines, is_first):
            if is_first:
                title = f"📈 TABLA REGISTRO DKP — {len(top_data)} jugadores"
                desc = f"Actualizado: `{fecha}`\n\n---\n**Jugadores y Saldo Actual**\n"
            else:
                title = "📈 TABLA REGISTRO DKP (Cont.)"
                desc = f"Actualizado: `{fecha}`\n\n---\n**Continuación**\n"

            desc += "\n".join(chunk_lines)

            embed = discord.Embed(
                title=title,
                description=desc,
                color=0x2b2d31
            )
            return embed

        for i in range(0, len(lines), CHUNK_SIZE):
            chunk_lines = lines[i:i + CHUNK_SIZE]
            embed = make_embed(chunk_lines, is_first=(i == 0))
            start_line = i + 1
            end_line = i + len(chunk_lines)
            logger.debug(f"[DKP-COG] Embed chunk #{len(embeds) + 1}: lines {start_line}-{end_line}")
            if start_line == 1 and end_line == 40:
                logger.info("[DKP-COG] First embed ends at line 40 as expected.")
            if start_line == 41:
                logger.info("[DKP-COG] Second embed begins at line 41 as expected.")
            embeds.append(embed)

        for emb in embeds:
            if emb is embeds[-1]:
                emb.set_footer(text=f"MVP Guild System • Mostrando jugadores con DKP > 0")

        try:
            # Enviar todos los embeds (puede ser 1 o 2 normalmente para 80 personas)
            for emb in embeds:
                await channel.send(embed=emb)
            logger.info(f"[DKP-COG] Ranking publicado en #{channel.name} con {len(top_data)} jugadores (Top 80).")
        except Exception as e:
            logger.error(f"[DKP-COG] Error publicando embed: {e}")

    # ──────────────────────────────────────────────────────────────
    # Comando slash manual /dkp (útil para publicar sin estar en juego)
    # ──────────────────────────────────────────────────────────────
    @app_commands.command(name="dkp", description="Muestra el último ranking DKP recibido del addon.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def slash_dkp(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "ℹ️ Para publicar el ranking, usa el botón **Exportar a Discord** en el panel de Gestión DKP del addon MVP Raid Tools en el juego.",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(DkpCog(bot))

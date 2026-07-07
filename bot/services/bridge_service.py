import asyncio
import logging
import discord
import config
from bot.integrations.wow_adapter import WoWAdapter
from bot.repositories.config_repo import ConfigRepository

from bot.utils.formatter import MessageFormatter

logger = logging.getLogger("BridgeService")

class BridgeService:
    def __init__(self, bot: discord.Client, adapter: WoWAdapter):
        self.bot = bot
        self.adapter = adapter
        self.task = None
        self.gmotd_task = None

    def start(self):
        if not self.task or self.task.done():
            self.task = self.bot.loop.create_task(self._run())
            logger.info("Bridge Service loop iniciado.")
        if not self.gmotd_task or self.gmotd_task.done():
            self.gmotd_task = self.bot.loop.create_task(self._gmotd_scheduler_loop())
            logger.info("Scheduler de mensaje diario de guild (GMOTD) iniciado.")

    def stop(self):
        if self.task and not self.task.done():
            self.task.cancel()
            logger.info("Bridge Service loop detenido.")
        if self.gmotd_task and not self.gmotd_task.done():
            self.gmotd_task.cancel()
            logger.info("Scheduler de mensaje diario de guild (GMOTD) detenido.")

    async def _run(self):
        try:
            async for msg in self.adapter.listen():
                await self._process_message(msg)
        except asyncio.CancelledError:
            logger.info("Escucha del adaptador (Bridge Service) cancelada explícitamente.")
        except Exception as e:
            logger.error(f"Error grave en el Bridge Service: {e}")

    async def _process_message(self, chat_event):
        """Procesa un evento de chat de WoW y lo publica en Discord con formato premium."""
        logger.info(f"[DEBUG-BRIDGE] Invocado _process_message con chat_event: {chat_event}")

        # ── Interceptar mensajes del protocolo DKP (whispers de DKP_*) ──────────
        if chat_event.get("type") == "WHISPER" and chat_event.get("message", "").startswith("DKP_"):
            dkp_cog = self.bot.cogs.get("DkpCog")
            if dkp_cog:
                consumed = await dkp_cog.receive_wow_message(chat_event)
                if consumed:
                    return  # No retransmitir a otros canales

        # 1. Validar configuración activa
        db_config = await ConfigRepository.get_config()
        if not db_config.get("adapter_activo", False):
            logger.info("[DEBUG-BRIDGE] El adaptador de puente no está activo en base de datos. Descartando mensaje.")
            return 

        # 2. Formatear y Limpiar Mensaje
        raw_message = chat_event.get("message", "")
        clean_message = MessageFormatter.format_for_discord(raw_message)
        
        if not clean_message:
            logger.info(f"[DEBUG-BRIDGE] Mensaje limpio vacío o inválido: '{raw_message}'")
            return

        # 3. Determinar Canal Destino y Prefijo
        target_channel_id = None
        msg_type = chat_event["type"]
        prefix = ""
        
        if msg_type == "GUILD":
            if db_config.get("bridge_guild_activo", 1):
                target_channel_id = db_config.get("canal_guild_discord_id")
                prefix = "🛡️ - [Guild]"
        elif msg_type == "OFFICER":
            if db_config.get("bridge_guild_activo", 1):
                target_channel_id = db_config.get("canal_guild_discord_id")
                prefix = "🔑 - [Oficiales]"

        if not target_channel_id:
            logger.info(f"[DEBUG-BRIDGE] Transmisión desactivada o canal no configurado para msg_type {msg_type}")
            return

        # 4. Enviar Mensaje Formateado
        channel_id_int = int(target_channel_id)
        logger.info(f"[DEBUG-BRIDGE] Buscando canal ID: {channel_id_int}")
        channel = self.bot.get_channel(channel_id_int)
        if not channel:
            logger.info(f"[DEBUG-BRIDGE] Canal {channel_id_int} no encontrado en cache. Intentando fetch asíncrono...")
            try:
                channel = await self.bot.fetch_channel(channel_id_int)
            except Exception as fe:
                logger.error(f"[DEBUG-BRIDGE] Error en fetch_channel para {channel_id_int}: {fe}")
                
        if channel:
            sender = chat_event.get("sender", "Desconocido")
            final_content = f"{prefix} [{sender}]: {clean_message}"
            
            try:
                await channel.send(final_content)
                logger.info(f"Chat {msg_type} enviado a #{channel.name}: {final_content}")
            except Exception as e:
                logger.error(f"Error enviando a Discord: {e}")
        else:
            logger.warning(f"Canal ID {target_channel_id} no accesible por ningún método.")

    async def _gmotd_scheduler_loop(self):
        """
        Gestiona el MOTD de hermandad con recordatorios progresivos e inteligentes.

        - Al arrancar, lee de BD el último MOTD enviado → NO reenvía si es el mismo.
        - Detecta cambios en vivo (o por reinicio con MOTD distinto) y anuncia.
        - Si el MOTD contiene una hora de raid, manda recordatorios crecientes
          según la cercanía: cada hora (ventana 3h-1h), cada 10 min (ventana 1h-0).
        - Una vez pasada la hora de raid, silencia recordatorios hasta nuevo MOTD.
        """
        GMOTD_CHANNEL_ID = 1092909849127419956
        from datetime import datetime, timedelta, timezone
        import re, random

        await asyncio.sleep(15)  # Espera inicial para que discord.py termine on_ready

        # ─── Cargar estado persistido desde BD (sobrevive reinicios) ───
        try:
            _last_motd_text = await ConfigRepository.get_last_gmotd_sent()
            _last_reminder_type, _last_reminder_time_str = await ConfigRepository.get_last_reminder_info()
        except Exception as e:
            logger.error(f"GMOTD: Error cargando last_gmotd_sent o recordatorios desde BD: {e}. Asumiendo vacío.")
            _last_motd_text = ""
            _last_reminder_type = None
            _last_reminder_time_str = None

        logger.info(f"GMOTD: Último MOTD persistido en BD: '{_last_motd_text[:80] if _last_motd_text else '(vacío)'}'")
        logger.info(f"GMOTD: Último recordatorio persistido: Tipo={_last_reminder_type}, Hora={_last_reminder_time_str}")

        if _last_motd_text:
            has_time = re.search(r'\b([0-1]?[0-9]|2[0-3])[:.hH]([0-5][0-9])\b', _last_motd_text)
            if not has_time:
                logger.warning(f"⚠️ GMOTD: El MOTD persistido '{_last_motd_text}' NO contiene ninguna hora de raid legible (ej: 22:30). Las alertas de cuenta regresiva están inactivas.")
            else:
                logger.info(f"📅 GMOTD: Hora de raid detectada en el MOTD persistido: {has_time.group(0)}. Alertas activas.")

        _raid_finished        = False   # True una vez que la hora de raid ya pasó

        # NaerZone → España (UTC+2 en verano, ajustar a +1 en invierno)
        tz_server = timezone(timedelta(hours=2))

        # ─── Mensajes variados por ventana de tiempo ────────────────────
        MSGS_3H = [
            "⚔️ **¡Recordatorio!** La raid de hoy empieza en **~{t}**. ¡Prepara tus frascos y comida!",
            "🛡️ **¡Atención raiders!** Quedan **~{t}** para la raid. ¡Ve reparando y preparando consumibles!",
            "🗡️ **La cuenta regresiva ha comenzado.** Raid en **~{t}**. ¡No llegues tarde!",
        ]
        MSGS_2H = [
            "🔥 **¡Dos horas para la raid!** Ve calentando motores, {t} y empieza el show.",
            "⏳ **Quedan ~{t} para el pull.** Asegúrate de estar en la raid con tiempo de sobra.",
            "🧪 **~{t} para la raid.** ¡Frascos, comida y encantamientos listos o fuera del grupo! 😤",
        ]
        MSGS_1H = [
            "🚨 **¡UNA HORA para el pull!** Todos al canal de voz, {t} y empieza la carnicería.",
            "⚡ **¡Solo queda {t}!** ¡Loguea ya si no lo has hecho! La raid NO espera.",
            "🎯 **{t} para la raid.** ¡Última llamada para conseguir consumibles!",
        ]
        MSGS_30M = [
            "🔔 **¡{t} para el pull!** ¡Todos al canal de voz AHORA! ¡Invitaciones abiertas!",
            "🏃 **¡Date prisa! Quedan {t}!** Si no estás listo, te quedas fuera 😤",
            "🎺 **¡{t} y arrancamos!** Formad en la entrada. ¡Sin excusas!",
        ]
        MSGS_10M = [
            "🔴 **¡{t} MINUTOS PARA EL PULL!** ¡LOGUEA YA O PIERDES EL SPOT!",
            "💀 **¡{t} minutos!** Si no estás dentro en {t} minutos… adiós loot 👋",
            "⚠️ **¡ALERTA! ¡{t} minutos!** ¡TODO EL MUNDO AL CANAL!",
        ]

        def pick(pool: list, t_str: str) -> str:
            return random.choice(pool).format(t=t_str)

        def fmt_time(delta_secs: float) -> str:
            """Formatea segundos restantes en texto legible."""
            total = int(delta_secs)
            h, m = divmod(total // 60, 60)
            if h > 0 and m > 0:
                return f"{h}h {m}min"
            elif h > 0:
                return f"{h} hora{'s' if h > 1 else ''}"
            else:
                return f"{m} minuto{'s' if m != 1 else ''}"

        while True:
            try:
                now_server = datetime.now(tz_server)

                # ─── Obtener MOTD actual ───────────────────────────────
                motd = ""
                if self.adapter.world_session:
                    motd = getattr(self.adapter.world_session, 'guild_motd', '').strip()

                if not motd:
                    await asyncio.sleep(20)
                    continue

                # ─── Obtener canal ─────────────────────────────────────
                channel = self.bot.get_channel(GMOTD_CHANNEL_ID)
                if not channel:
                    try:
                        channel = await self.bot.fetch_channel(GMOTD_CHANNEL_ID)
                    except Exception as fe:
                        logger.error(f"GMOTD: No se pudo obtener el canal {GMOTD_CHANNEL_ID}: {fe}")
                        await asyncio.sleep(60)
                        continue

                bot_member = channel.guild.get_member(self.bot.user.id)
                if bot_member and not channel.permissions_for(bot_member).send_messages:
                    await asyncio.sleep(60)
                    continue

                # ─── 1. Detectar cambio de MOTD ───────────────────────
                if motd != _last_motd_text:
                    if _last_motd_text == "":
                        # Primera vez que arranca el bot con este MOTD
                        mensaje = f'@everyone "{motd}"'
                    else:
                        mensaje = f'🔔 **El Mensaje del Día ha sido actualizado:**\n@everyone "{motd}"'

                    await channel.send(mensaje)
                    logger.info(f"✅ GMOTD enviado/actualizado: {motd[:100]}")

                    # Persistir en BD para sobrevivir reinicios
                    _last_motd_text = motd
                    await ConfigRepository.set_last_gmotd_sent(motd)

                    # Validar si contiene hora
                    has_time = re.search(r'\b([0-1]?[0-9]|2[0-3])[:.hH]([0-5][0-9])\b', motd)
                    if not has_time:
                        logger.warning(f"⚠️ El MOTD '{motd}' NO contiene ninguna hora de raid legible (ej: 22:30). Las alertas de cuenta regresiva no se activarán.")
                    else:
                        logger.info(f"📅 Hora de raid detectada en el MOTD: {has_time.group(0)}. Alertas activas.")

                    # Reiniciar contadores de recordatorio en memoria y BD
                    _last_reminder_type = None
                    _last_reminder_time_str = None
                    await ConfigRepository.set_last_reminder_info(None, None)
                    _raid_finished        = False

                    await asyncio.sleep(5)

                # ─── 2. Extraer hora de raid ───────────────────────────
                # Acepta: 22:30, 22.30, 22h30, 22H30
                time_match = re.search(r'\b([0-1]?[0-9]|2[0-3])[:.hH]([0-5][0-9])\b', motd)

                if time_match and not _raid_finished:
                    hour   = int(time_match.group(1))
                    minute = int(time_match.group(2))

                    # Soporte AM/PM por si acaso
                    if re.search(r'\b(pm|p\.m\.)\b', motd, re.IGNORECASE) and hour < 12:
                        hour += 12

                    raid_time = now_server.replace(hour=hour, minute=minute, second=0, microsecond=0)

                    # Si pasó hace más de 30 min → raid terminada, silenciar
                    elapsed = (now_server - raid_time).total_seconds()
                    if elapsed > 1800:
                        if not _raid_finished:
                            logger.info(f"GMOTD: Hora de raid {hour:02d}:{minute:02d} ya pasó. Silenciando recordatorios.")
                            _raid_finished = True
                        await asyncio.sleep(20)
                        continue

                    # Si todavía no llegó la hora, calcular delta
                    if raid_time < now_server:
                        # La hora es para hoy y ya pasó (menos de 30 min) → seguimos contando
                        delta_secs = 0.0
                    else:
                        delta_secs = (raid_time - now_server).total_seconds()

                    delta_h = delta_secs / 3600.0

                    # Determinar el tipo de recordatorio correspondiente al tiempo restante
                    current_type = None
                    interval = 0
                    msg_pool = None

                    if 2.0 < delta_h <= 3.0:
                        current_type = "3h"
                        interval = 3500  # ~1 hora
                        msg_pool = MSGS_3H
                    elif 1.0 < delta_h <= 2.0:
                        current_type = "2h"
                        interval = 3500  # ~1 hora
                        msg_pool = MSGS_2H
                    elif 0.5 < delta_h <= 1.0:
                        current_type = "1h"
                        interval = 1700  # ~30 min
                        msg_pool = MSGS_1H
                    elif (10 / 60) < delta_h <= 0.5:
                        current_type = "30m"
                        interval = 590   # ~10 min
                        msg_pool = MSGS_30M
                    elif 0.0 < delta_h <= (10 / 60):
                        current_type = "10m"
                        interval = 590   # ~10 min
                        msg_pool = MSGS_10M

                    # Enviar recordatorio si corresponde
                    if current_type and msg_pool:
                        should_send = False
                        
                        # Si es un tipo diferente de recordatorio al último enviado, se manda inmediatamente
                        if _last_reminder_type != current_type:
                            should_send = True
                        else:
                            # Si es el mismo tipo, comprobamos si ya pasó el intervalo
                            if _last_reminder_time_str:
                                try:
                                    last_time = datetime.fromisoformat(_last_reminder_time_str)
                                    # Asegurar que last_time tiene zona horaria
                                    if last_time.tzinfo is None:
                                        last_time = last_time.replace(tzinfo=tz_server)
                                    time_passed = (now_server - last_time).total_seconds()
                                    if time_passed >= interval:
                                        should_send = True
                                except Exception as parse_err:
                                    logger.error(f"GMOTD: Error al parsear last_reminder_time '{_last_reminder_time_str}': {parse_err}")
                                    should_send = True
                            else:
                                should_send = True

                        if should_send:
                            # Formatear el tiempo a mostrar
                            t_str = fmt_time(delta_secs) if current_type != "10m" else str(max(1, int(delta_secs / 60)))
                            mensaje_recordatorio = pick(msg_pool, t_str)
                            
                            await channel.send(mensaje_recordatorio)
                            logger.info(f"📢 Recordatorio enviado [{current_type}]: {mensaje_recordatorio}")

                            # Actualizar memoria y persistir en la base de datos
                            _last_reminder_type = current_type
                            _last_reminder_time_str = now_server.isoformat()
                            await ConfigRepository.set_last_reminder_info(current_type, _last_reminder_time_str)

                await asyncio.sleep(20)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en _gmotd_scheduler_loop: {e}", exc_info=True)
                await asyncio.sleep(60)


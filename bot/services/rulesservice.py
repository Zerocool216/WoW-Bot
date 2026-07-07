import os
import time
import hashlib
import logging
import aiohttp
import discord
import config
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger("RulesService")

class RulesService:
    """
    Servicio desacoplado encargado de gestionar, cargar y cachear
    las reglas y normativas de la hermandad desde múltiples fuentes.
    """
    _cache = {
        "source_type": "none",
        "source_identifier": "",
        "last_loaded_at": 0.0,
        "content_hash": "",
        "content_length": 0,
        "text": ""
    }
    
    CACHE_TTL = 300

    @classmethod
    def invalidate_cache(cls):
        """Invalida inmediatamente la caché de reglas para forzar una nueva lectura."""
        cls._cache = {
            "source_type": "none",
            "source_identifier": "",
            "last_loaded_at": 0.0,
            "content_hash": "",
            "content_length": 0,
            "text": ""
        }
        logger.info("Caché de reglas invalidada manualmente.")

    @classmethod
    async def get_rules_text(cls, bot: discord.Client) -> Tuple[str, str, str]:
        """
        Retorna las reglas activas de la hermandad respetando el orden de prioridades,
        y hace uso de la caché con TTL si está vigente.
        """
        now = time.time()
        
        if cls._cache["text"] and (now - cls._cache["last_loaded_at"] < cls.CACHE_TTL):
            logger.debug("Retornando reglas desde caché de memoria vigente.")
            return cls._cache["text"], cls._cache["source_type"], cls._cache["source_identifier"]
        
        source_type = getattr(config, "RULES_SOURCE_TYPE", "auto").lower()
        rules_file_path = getattr(config, "RULES_FILE_PATH", "Reglas.txt")
        rules_channel_id = getattr(config, "RULES_CHANNEL_ID", 1492560647068844212)
        rules_max_chars = getattr(config, "RULES_MAX_CHARS", 30000)
        
        text = ""
        resolved_source_type = "none"
        resolved_identifier = ""
        
        if source_type == "none":
            logger.info("La carga de reglas por IA está explícitamente desactivada (RULES_SOURCE_TYPE = none)")
            text = ""
            resolved_source_type = "none"
            resolved_identifier = "Configurado como none"
            
        elif source_type == "file":
            text, path = await cls.get_rules_from_file(rules_file_path)
            if text:
                resolved_source_type = "file"
                resolved_identifier = path
            else:
                resolved_source_type = "none"
                resolved_identifier = f"Archivo no encontrado o vacío: {rules_file_path}"
                
        elif source_type == "discord":
            text, details = await cls.get_rules_from_channel(bot, rules_channel_id)
            if text:
                resolved_source_type = details.get("type", "discord")
                resolved_identifier = details.get("identifier", str(rules_channel_id))
            else:
                resolved_source_type = "none"
                resolved_identifier = f"Fallo al leer canal de Discord ID {rules_channel_id}"
                
        elif source_type == "auto":
            # Prioridad 1: Archivo local válido
            logger.info("Modo 'auto' activo. Intentando prioridad 1: Archivo local...")
            text, path = await cls.get_rules_from_file(rules_file_path)
            if text:
                resolved_source_type = "file"
                resolved_identifier = path
                logger.info(f"Cargadas reglas con éxito de archivo local: {path}")
            else:
                # Prioridad 2: Discord Channel
                logger.info("Archivo local no válido. Intentando prioridades de Discord...")
                text, details = await cls.get_rules_from_channel(bot, rules_channel_id)
                if text:
                    resolved_source_type = details.get("type", "discord")
                    resolved_identifier = details.get("identifier", str(rules_channel_id))
                    logger.info(f"Cargadas reglas con éxito desde Discord ({resolved_source_type}): {resolved_identifier}")
                else:
                    logger.warning("No se pudo cargar reglas desde ninguna fuente en modo 'auto'.")
                    resolved_source_type = "none"
                    resolved_identifier = "Ninguna fuente válida disponible en modo auto"
                    text = ""
        else:
            logger.error(f"RULES_SOURCE_TYPE inválido: '{source_type}'. Usando none.")
            resolved_source_type = "none"
            resolved_identifier = f"Tipo de fuente inválido: {source_type}"
            text = ""

        # Aplicar truncado inteligente si excede el límite
        original_length = len(text)
        text = cls._smart_truncate(text, rules_max_chars)
        
        if len(text) < original_length:
            logger.warning(f"Las reglas excedieron el límite de {rules_max_chars} caracteres. Truncado inteligente aplicado.")
            
        # Calcular Hash
        content_hash = hashlib.md5(text.encode('utf-8', errors='ignore')).hexdigest() if text else ""
        
        # Guardar en Caché
        cls._cache = {
            "source_type": resolved_source_type,
            "source_identifier": resolved_identifier,
            "last_loaded_at": now,
            "content_hash": content_hash,
            "content_length": len(text),
            "text": text
        }
        
        return text, resolved_source_type, resolved_identifier

    @classmethod
    async def get_rules_from_file(cls, path: str) -> Tuple[str, str]:
        """Intenta leer reglas desde un archivo local."""
        if not path:
            return "", ""
        
        base_dir = getattr(config, "BASEDIR", getattr(config, "BASE_DIR", ""))
        try:
            if os.path.exists(path) and os.path.isfile(path):
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().strip()
                    if content:
                        return content, os.path.abspath(path)
            
            if not os.path.isabs(path) and base_dir:
                alt_path = os.path.join(base_dir, path)
                if os.path.exists(alt_path) and os.path.isfile(alt_path):
                    with open(alt_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read().strip()
                        if content:
                            return content, os.path.abspath(alt_path)
        except Exception as e:
            logger.error(f"Error leyendo archivo local de reglas '{path}': {e}")
        return "", ""

    @classmethod
    async def get_rules_from_channel(cls, bot: discord.Client, channel_id: int) -> Tuple[str, Dict[str, Any]]:
        """
        Intenta leer las reglas desde un canal de Discord por ID.
        Verifica permisos de acceso real e implementa tres estrategias secuenciales:
        1. Archivo adjunto .txt/.md más reciente.
        2. Mensajes fijados en el canal.
        3. Mensajes curados recientes (últimos 20).
        """
        if not channel_id:
            return "", {}
        if not bot.is_ready():
            logger.warning("El cliente de Discord no está listo. Saltando lectura de canal.")
            return "", {}
            
        try:
            channel = bot.get_channel(channel_id)
            if not channel:
                channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            logger.error(f"No se pudo encontrar o acceder al canal {channel_id}: {e}")
            return "", {}
            
        if not channel or not isinstance(channel, discord.TextChannel):
            logger.error(f"El canal {channel_id} no es un canal de texto válido o no está accesible.")
            return "", {}
            
        # 1. Validación estricta de permisos
        me = channel.guild.me
        permissions = channel.permissions_for(me)
        if not permissions.read_messages or not permissions.read_message_history:
            logger.error(f"El bot carece de permisos de lectura de mensajes o historial en el canal: {channel.name} (ID: {channel_id})")
            return "", {}
            
        # Estrategia A: Buscar archivo adjunto .txt o .md más reciente en los últimos 50 mensajes
        try:
            async for msg in channel.history(limit=50):
                for attachment in msg.attachments:
                    if attachment.filename.endswith(('.txt', '.md')):
                        logger.info(f"Encontrado archivo adjunto de reglas: {attachment.filename} en el mensaje {msg.id}")
                        async with aiohttp.ClientSession() as session:
                            async with session.get(attachment.url) as resp:
                                if resp.status == 200:
                                    text = await resp.text(encoding='utf-8', errors='ignore')
                                    text = text.strip()
                                    if text:
                                        return text, {
                                            "type": "discord_attachment",
                                            "identifier": f"Adjunto '{attachment.filename}' del canal #{channel.name} (Subido por {msg.author.name})"
                                        }
        except Exception as e:
            logger.error(f"Error buscando/descargando adjunto del canal {channel_id}: {e}")
            
        # Estrategia B: Mensajes fijados (pinned)
        try:
            pins = await channel.pins()
            if pins:
                logger.info(f"Leyendo mensajes fijados en #{channel.name}")
                pins = sorted(pins, key=lambda m: m.created_at)
                pinned_contents = []
                for p in pins:
                    content = p.content.strip()
                    if content and not p.author.bot:
                        pinned_contents.append(content)
                
                combined_pins = "\n\n".join(pinned_contents)
                if combined_pins:
                    return combined_pins, {
                        "type": "discord_pinned",
                        "identifier": f"Mensajes fijados en #{channel.name} (Total: {len(pinned_contents)})"
                    }
        except Exception as e:
            logger.error(f"Error leyendo mensajes fijados del canal {channel_id}: {e}")
            
        # Estrategia C: Últimos mensajes curados del canal (últimos 20 ordenados por calidad y luego cronológicamente)
        try:
            messages_to_consider = []
            async for msg in channel.history(limit=50):
                if msg.author.bot:
                    continue
                content = msg.content.strip()
                if not content:
                    continue
                if content.startswith(('!', '/', '$', '?', '.', '- ')):
                    continue
                if len(content) < 15:
                    continue
                
                score = 0
                is_staff = False
                
                guild_ranks = getattr(config, "GUILDRANKROLES", getattr(config, "GUILD_RANK_ROLES", []))
                if isinstance(msg.author, discord.Member):
                    is_staff = (
                        msg.author.guild_permissions.manage_messages or 
                        msg.author.guild_permissions.administrator or
                        any(role.name in guild_ranks[:4] for role in msg.author.roles)
                    )
                if is_staff:
                    score += 15
                
                format_characters = ('✦', '▸', '『', '』', '•', '➢', '*', '#', '[', ']')
                if any(char in content for char in format_characters):
                    score += 8
                
                if '\n' in content:
                    score += 5
                    
                messages_to_consider.append((msg, content, score))
                
            if messages_to_consider:
                messages_to_consider.sort(key=lambda x: x[2], reverse=True)
                selected = messages_to_consider[:20]
                selected.sort(key=lambda x: x[0].created_at)
                
                curated_texts = [item[1] for item in selected]
                combined_curated = "\n\n".join(curated_texts)
                
                logger.info(f"Cargados mensajes curados inteligentes de #{channel.name} (Seleccionados: {len(curated_texts)})")
                return combined_curated, {
                    "type": "discord_recent",
                    "identifier": f"Mensajes curados en #{channel.name} (Filtrados por calidad y staff)"
                }
        except Exception as e:
            logger.error(f"Error curando mensajes de texto de #{channel.name}: {e}")
            
        return "", {}

    @classmethod
    def _smart_truncate(cls, text: str, max_chars: int) -> str:
        """Truncado inteligente respetando límites de tamaño y saltos de párrafo."""
        if not text or len(text) <= max_chars:
            return text
        truncated = text[:max_chars]
        last_newline = truncated.rfind('\n')
        if last_newline != -1 and last_newline > (max_chars * 0.75):
            truncated = truncated[:last_newline]
        return truncated + "\n\n⚠️ *[Reglas de hermandad extensas: El texto fue truncado inteligentemente por límite de contexto de la IA]*"

    @classmethod
    def get_cache_info(cls) -> Dict[str, Any]:
        """Retorna información detallada de la caché actual para diagnóstico."""
        last_loaded = cls._cache["last_loaded_at"]
        age = round(time.time() - last_loaded) if last_loaded > 0 else -1
        ttl_rem = round(cls.CACHE_TTL - age) if last_loaded > 0 else 0
        
        return {
            "source_type": cls._cache["source_type"],
            "source_identifier": cls._cache["source_identifier"],
            "last_loaded_at": last_loaded,
            "last_loaded_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_loaded)) if last_loaded > 0 else "Nunca",
            "content_hash": cls._cache["content_hash"],
            "content_length": cls._cache["content_length"],
            "age_seconds": age,
            "ttl_remaining": ttl_rem
        }

import os
import discord
from dotenv import load_dotenv

load_dotenv()

# Variables de entorno
DISCORD_BOT_TOKEN = os.getenv("TOKEN") or os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORDBOTTOKEN")
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID") or os.getenv("DISCORDGUILDID") or 0)

# Lista de IDs de administradores
_admin_ids_str = os.getenv("ADMIN_USER_IDS") or os.getenv("ADMINUSERIDS") or ""
ADMIN_USER_IDS = [int(x.strip()) for x in _admin_ids_str.split(",") if x.strip().isdigit()]

LOG_LEVEL = os.getenv("LOG_LEVEL") or os.getenv("LOGLEVEL") or "INFO"

WOW_REALMLIST = os.getenv("WOW_REALMLIST") or os.getenv("WOWREALMLIST") or "comunidad.naerzone.com"
WOW_REALM = os.getenv("WOW_REALM") or os.getenv("WOWREALM") or "Thalassa"
WOW_ACCOUNT = os.getenv("WOW_ACCOUNT") or os.getenv("WOWACCOUNT") or ""
WOW_PASSWORD = os.getenv("WOW_PASSWORD") or os.getenv("WOWPASSWORD") or ""
WOW_CHARACTER = os.getenv("WOW_CHARACTER") or os.getenv("WOWCHARACTER") or ""
WOW_SERVER_TIMEZONE_OFFSET = int(os.getenv("WOW_SERVER_TIMEZONE_OFFSET") or os.getenv("WOWSERVERTIMEZONEOFFSET") or 2)


# Variables de IA para Comunidad
# Prioridad de lectura: AIAPIKEY > GEMINI_API_KEY > AI_API_KEY
AI_PROVIDER = os.getenv("AIPROVIDER") or os.getenv("AI_PROVIDER", "gemini")
AI_API_KEY = os.getenv("AIAPIKEY") or os.getenv("GEMINI_API_KEY") or os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AIMODEL") or os.getenv("AI_MODEL", "gemini-2.5-flash")

_ai_enabled_env = os.getenv("AIENABLED") or os.getenv("AI_ENABLED")
if _ai_enabled_env is not None:
    AI_ENABLED = _ai_enabled_env.lower() in ("true", "1", "yes")
else:
    AI_ENABLED = bool(AI_API_KEY.strip()) if AI_API_KEY else False

# Alias sin guión bajo para compatibilidad con código que use config.AIPROVIDER, etc.
AIPROVIDER = AI_PROVIDER
AIAPIKEY = AI_API_KEY
AIMODEL = AI_MODEL
AIENABLED = AI_ENABLED

# Variables de Reglas Dinámicas de Guild
RULES_SOURCE_TYPE = os.getenv("RULES_SOURCE_TYPE", "auto")
RULES_FILE_PATH = os.getenv("RULES_FILE_PATH", "Reglas.txt")
RULES_CHANNEL_ID = int(os.getenv("RULES_CHANNEL_ID", 1492560647068844212))
RULES_MAX_CHARS = int(os.getenv("RULES_MAX_CHARS", 30000))

# Canales Agonía de Sombras
NORMATIVA_AGONIA_CHANNEL_ID = int(os.getenv("NORMATIVA_AGONIA_CHANNEL_ID", 1478117271737208995))
LISTA_FRAGMENTEADORES_CHANNEL_ID = int(os.getenv("LISTA_FRAGMENTEADORES_CHANNEL_ID", 1520941982732783759))
AGONIAS_FINALIZADAS_CHANNEL_ID = int(os.getenv("AGONIAS_FINALIZADAS_CHANNEL_ID", 1520942238526476318))
AGONIA_TICKETS_CHANNEL_ID = int(os.getenv("AGONIA_TICKETS_CHANNEL_ID", 1519444494276235384))
AGONIA_STAFF_LOG_CHANNEL_ID = int(os.getenv("AGONIA_STAFF_LOG_CHANNEL_ID", 1519444816675475607))

# Canales del sistema de reclamos
COMPLAINTS_PANEL_CHANNEL_ID = int(os.getenv("COMPLAINTS_PANEL_CHANNEL_ID", 1478048058733367448))
COMPLAINTS_STAFF_CHANNEL_ID = int(os.getenv("COMPLAINTS_STAFF_CHANNEL_ID", 1519444816675475607))
COMPLAINTS_HISTORY_CHANNEL_ID = int(os.getenv("COMPLAINTS_HISTORY_CHANNEL_ID", 1473784922282922045))
COMPLAINTS_STAFF_LOG_CHANNEL_ID = int(os.getenv("COMPLAINTS_STAFF_LOG_CHANNEL_ID", 1519444816675475607))

# Roles permitidos para Agonía de Sombras
ADMINISTRADOR_MASTER_BOT_ROLE_ID = int(os.getenv("ADMINISTRADOR_MASTER_BOT_ROLE_ID", 1474146683834335349))
OFICIAL_ROLE_ID = int(os.getenv("OFICIAL_ROLE_ID", 1475171574943318037))
GUILD_MASTER_ROLE_ID = int(os.getenv("GUILD_MASTER_ROLE_ID", 1473784918256652509))
CONCILIO_ROLE_ID = int(os.getenv("CONCILIO_ROLE_ID", 1475171573353676983))


# Rangos oficiales de la Hermandad (de mayor a menor jerarquía)
GUILD_RANK_ROLES = [
    "Leyenda",          # Rango 1
    "Maestro",          # Rango 2
    "Oficial",          # Rango 3
    "Veterano",         # Rango 4
    "Raider Principal", # Rango 5
    "Raider",           # Rango 6
    "Raider PUG",       # Rango 7
    "Miembro",          # Rango 8
    "Recluta",          # Rango 9
    "Iniciado",         # Rango 10
    "Alter",            # Rango 11
    "Prueba"            # Rango 12
]

# Alias sin guión bajo
GUILDRANKROLES = GUILD_RANK_ROLES

# Rutas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASEDIR = BASE_DIR
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "bridge.db")
DBPATH = DB_PATH
LOGS_DIR = os.path.join(BASE_DIR, "logs")
LOGSDIR = LOGS_DIR

# ============= AUTO-UPDATE CONFIGURATION =============
# Activar/desactivar sistema de auto-actualización
UPDATE_ENABLED = os.getenv("UPDATE_ENABLED", "true").lower() in ("true", "1", "yes")

# Intervalo de verificación de actualizaciones (en horas)
UPDATE_CHECK_INTERVAL_HOURS = int(os.getenv("UPDATE_CHECK_INTERVAL_HOURS", 6))

# Configuración de repositorio GitHub
UPDATE_GITHUB_OWNER = os.getenv("UPDATE_GITHUB_OWNER", "judecalles")
UPDATE_GITHUB_REPO = os.getenv("UPDATE_GITHUB_REPO", "WoW-Bridge-Bot")

# Permitir instalar versiones prerelease/beta
UPDATE_ALLOW_PRERELEASE = os.getenv("UPDATE_ALLOW_PRERELEASE", "false").lower() in ("true", "1", "yes")

# Timeout para solicitudes a GitHub (en segundos)
UPDATE_TIMEOUT_SECONDS = int(os.getenv("UPDATE_TIMEOUT_SECONDS", 30))

# Cuántos backups anteriores mantener
UPDATE_BACKUP_COUNT = int(os.getenv("UPDATE_BACKUP_COUNT", 2))

# Directorio para archivos temporales de actualización
UPDATE_TEMP_DIR = os.path.join(DATA_DIR, "update_temp")

# ====================================================

# Alias de token y guild
DISCORDBOTTOKEN = DISCORD_BOT_TOKEN
DISCORDGUILDID = DISCORD_GUILD_ID
ADMINUSERIDS = ADMIN_USER_IDS
LOGLEVEL = LOG_LEVEL

def get_intents() -> discord.Intents:
    """
    Retorna los intents configurados para el bot.
    - guilds: Necesario para que el bot conozca los canales y roles del servidor.
    - messages: Necesario para leer y enviar mensajes en canales.
    - message_content: Intent Privilegiado. Obligatorio para leer el contenido.
    """
    intents = discord.Intents.default()
    intents.message_content = True
    return intents

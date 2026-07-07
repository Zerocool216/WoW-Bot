import re
import random
import sys
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ─── Configuración de Prueba ───
motds_to_test = [
    "MIÉRCOLES SR 25 H X4. (Sin hora - no debería mandar alertas)",
    "MIÉRCOLES SR 25 H X4 - Raid 22:30 (Con hora legible)",
    "Raid a las 23h45 - Traer potis (Con hora format H)",
    "ICC 10 H - Pull 20.15 (Con hora formato punto)",
]

MSGS_3H = [
    "🗡️ La cuenta regresiva ha comenzado. Raid en ~{t}. ¡No llegues tarde!"
]
MSGS_2H = [
    "🧪 ~{t} para la raid. ¡Frascos, comida y encantamientos listos o fuera del grupo! 😤"
]
MSGS_1H = [
    "🚨 ¡UNA HORA para el pull! Todos al canal de voz..."
]
MSGS_30M = [
    "🏃 ¡Date prisa! Quedan {t}! Si no estás listo, te quedas fuera 😤"
]
MSGS_10M = [
    "💀 ¡{t} minutos! Si no estás dentro en {t} minutos… adiós loot 👋"
]

def pick(pool: list, t_str: str) -> str:
    return random.choice(pool).format(t=t_str)

def fmt_time(delta_secs: float) -> str:
    total = int(delta_secs)
    h, m = divmod(total // 60, 60)
    if h > 0 and m > 0:
        return f"{h}h {m}min"
    elif h > 0:
        return f"{h} hora{'s' if h > 1 else ''}"
    else:
        return f"{m} minuto{'s' if m != 1 else ''}"

tz_server = timezone(timedelta(hours=2))
now_server = datetime.now(tz_server)

print("=== INICIANDO SIMULACIÓN DE PARSEO Y RECORDATORIOS ===")
print(f"Hora actual simulada (Server): {now_server.strftime('%H:%M:%S')}\n")

for motd in motds_to_test:
    print(f"Probando MOTD: '{motd}'")
    time_match = re.search(r'\b([0-1]?[0-9]|2[0-3])[:.hH]([0-5][0-9])\b', motd)
    
    if not time_match:
        print("  ❌ [Resultado] No se detectó hora de raid. Alertas desactivadas.\n")
        continue
        
    hour = int(time_match.group(1))
    minute = int(time_match.group(2))
    
    # Simular hora de raid hoy
    raid_time = now_server.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # Calcular diferencia
    delta_secs = (raid_time - now_server).total_seconds()
    delta_h = delta_secs / 3600.0
    
    print(f"  ✅ [Resultado] Hora detectada: {hour:02d}:{minute:02d}")
    print(f"  Diferencia: {delta_h:.2f} horas ({int(delta_secs)} segundos)")
    
    # Determinar qué alerta tocaría
    current_type = None
    msg_pool = None
    
    if 2.0 < delta_h <= 3.0:
        current_type = "3h"
        msg_pool = MSGS_3H
    elif 1.0 < delta_h <= 2.0:
        current_type = "2h"
        msg_pool = MSGS_2H
    elif 0.5 < delta_h <= 1.0:
        current_type = "1h"
        msg_pool = MSGS_1H
    elif (10 / 60) < delta_h <= 0.5:
        current_type = "30m"
        msg_pool = MSGS_30M
    elif 0.0 < delta_h <= (10 / 60):
        current_type = "10m"
        msg_pool = MSGS_10M
    else:
        print("  ⚠️ [Resultado] Fuera de las ventanas de alerta (o ya pasó).\n")
        continue
        
    t_str = fmt_time(delta_secs) if current_type != "10m" else str(max(1, int(delta_secs / 60)))
    msg = pick(msg_pool, t_str)
    print(f"  📢 [Alerta enviada - Tipo {current_type}]: {msg}\n")

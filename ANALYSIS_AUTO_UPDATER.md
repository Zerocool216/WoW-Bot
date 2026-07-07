# Auto-Update System Analysis & Design - BOT MVP 1.0.2

## 1. VIABILIDAD & ANÁLISIS DEL PROYECTO

### Proyecto Actual
- **Tipo**: Discord.py bot (async, modular con cogs)
- **Entry point**: `main.py` (clase `WoWBridgeBot`)
- **Config**: `config.py` (variables de entorno con dotenv)
- **Estructura**: `bot/cogs` (modular), `data/` (BD SQLite), `logs/`
- **Windows-First**: Ya tiene `.bat` launchers (`Iniciar-Bot.bat`)

### Estado de Actualización
- **Actualmente**: Sin versionado centralizado
- **Problema**: Si se quiere update en caliente, archivos quedan bloqueados por proceso
- **Solución**: Usar patrón Launcher + Updater externo

---

## 2. ESTRATEGIA ELEGIDA: OPCIÓN B (Launcher + Updater Externo)

### ¿Por qué Opción B?

| Aspecto | A (Externo) | **B (Launcher+Updater)** | C (Batch) | D (In-process) |
|--------|-----------|----------------------|----------|--------------|
| Seguridad | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| No requiere Git | ✓ | ✓ | ✓ | ✓ |
| Rollback | Parcial | ✓ | Parcial | ✗ |
| Windows native | ✓ | ✓⭐ | ✓ | ✗ |
| Multiplataforma | ✓ | ✓ | ✗ | ✗ |
| Atomicidad | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ✗ |
| Complejidad | Media | Media | Baja | Alta |

**Selección**: **OPCIÓN B** porque:
1. ✅ Reinicia sin romper instalación
2. ✅ Archivos no bloqueados (proceso externo hace cambios)
3. ✅ Rollback seguro (backup + validación)
4. ✅ Logs detallados de cada paso
5. ✅ GitHub Releases (no git pull)
6. ✅ Sem-versioning (v1.0.2 → v1.0.3)
7. ✅ Multiplataforma future-proof

---

## 3. ARQUITECTURA DE SOLUCIÓN

### Diagrama de Flujo
```
[1. Bot Launcher (main.py)]
        ↓
[2. Verificar Version]
        ↓
    ¿Actualización disponible?
    /                          \
  SÍ                            NO
  ↓                             ↓
[3. Descargar]         [4. Iniciar Bot Normal]
  ↓                     (async event loop)
[4. Validar]
  ↓
[5. Backup actual]
  ↓
[6. Aplicar (extract)]
  ↓
[7. Restart con script PS1]
```

### Estructura de Archivos Nueva
```
G:\Bot MVP\
├── main.py (MODIFICADO: Launcher)
├── config.py (MODIFICADO: Add updater config)
├── version.json (NUEVO: {"version":"1.0.2","release_date":"2026-07-07"})
│
├── updater/ (NUEVO: Módulo updater)
│   ├── __init__.py
│   ├── version_manager.py (lectura/comparación de versiones)
│   ├── github_client.py (consulta GitHub Releases API)
│   ├── downloader.py (descarga con validación)
│   ├── applicator.py (aplicar update: backup, extract, replace)
│   └── logger.py (logs separados para updater)
│
├── scripts/ (NUEVO: Scripts de reinicio)
│   ├── restart_bot.ps1 (PowerShell - PRIMARY)
│   ├── restart_bot.bat (Batch - FALLBACK)
│   └── apply_update.ps1 (auxiliar)
│
├── bot/
│   ├── cogs/
│   ├── services/
│   ├── views/
│   ├── repositories/
│   ├── integrations/
│   └── ...
│
├── data/
│   ├── bridge.db
│   ├── database.py
│   ├── versions.json ← versionado local
│   └── update_logs/ (NUEVO: logs de actualización)
│
├── logs/
│   ├── bot.log
│   └── updater.log (NUEVO)
│
└── .env (ya existe)
```

---

## 4. COMPONENTES A IMPLEMENTAR

### 4.1. Versionado Local (`data/versions.json`)
```json
{
  "current": "1.0.2",
  "release_date": "2026-07-07T00:00:00Z",
  "previous": "1.0.1",
  "check_time": "2026-07-07T15:30:45Z"
}
```

### 4.2. Configuración Updater (config.py)
```python
# Auto-Update Configuration
UPDATE_ENABLED = True
UPDATE_CHECK_INTERVAL_HOURS = 6
UPDATE_GITHUB_OWNER = "tu-username"  # Ej: judecalles
UPDATE_GITHUB_REPO = "WoW-Bridge-Bot"  # Nombre del repo
UPDATE_ALLOW_PRERELEASE = False
UPDATE_BACKUP_COUNT = 2  # Guardar 2 versiones anteriores
UPDATE_TIMEOUT_SECONDS = 30
```

### 4.3. Módulos Updater
1. **version_manager.py**: Lectura/comparación semver
2. **github_client.py**: API v3 de GitHub (latest release)
3. **downloader.py**: HTTP descarga + validación MD5
4. **applicator.py**: Backup + extract + atomic replace
5. **logger.py**: Logs separados del bot

### 4.4. Scripts Reinicio (Windows)
- **restart_bot.ps1**: Script PowerShell que:
  - Mata proceso bot anterior
  - Extrae update de temp
  - Reemplaza archivos
  - Reinicia bot con main.py
- **restart_bot.bat**: Fallback si PS1 no ejecuta

### 4.5. Punto de Entrada Modificado (main.py)
```python
async def main():
    # 1. Verificar actualización
    await check_updates()
    # 2. Si hay update → descargar, aplicar, reiniciar
    # 3. Si no → continuar normal
    # 4. Iniciar bot
```

---

## 5. FLUJO DETALLADO DE ACTUALIZACIÓN

### Caso 1: Sin Actualización
```
Bot inicia
  ↓
version_manager.get_current() = "1.0.2"
  ↓
github_client.get_latest_release() = "1.0.2"
  ↓
Compare: 1.0.2 == 1.0.2 ✓
  ↓
Bot continúa normal (sin delay)
```

### Caso 2: Hay Actualización
```
Bot inicia
  ↓
version_manager.get_current() = "1.0.2"
  ↓
github_client.get_latest_release() = "1.0.3" ← Update disponible
  ↓
Log: "Actualización disponible: 1.0.2 → 1.0.3"
  ↓
downloader.download("https://github.com/.../releases/download/.../WoW-Bridge-Bot-1.0.3.zip")
  ↓
Validar MD5: ✓
  ↓
applicator.backup_current() → data/backups/bot-1.0.2.zip
  ↓
applicator.extract_and_replace() → reemplaza archivos
  ↓
version_manager.update_version("1.0.3")
  ↓
Ejecutar restart_bot.ps1
  ↓
Proceso actual muere gracefully
  ↓
Script PS1 termina old process
  ↓
Script PS1 ejecuta: python main.py
  ↓
Nueva instancia inicia con v1.0.3
```

### Caso 3: Error en Actualización
```
Bot inicia
  ↓
Descargar update...
  ↓
❌ Error: Timeout o conexión fallida
  ↓
Log error a logs/updater.log
  ↓
NO reemplazar nada ← instalación intacta
  ↓
Bot continúa con v1.0.2
  ↓
Próximo check: en 6 horas
```

---

## 6. LISTA EXACTA DE ARCHIVOS A CREAR/MODIFICAR

### CREAR (Nuevos)
1. `data/versions.json`
2. `updater/__init__.py`
3. `updater/version_manager.py`
4. `updater/github_client.py`
5. `updater/downloader.py`
6. `updater/applicator.py`
7. `updater/logger.py`
8. `scripts/restart_bot.ps1`
9. `scripts/restart_bot.bat`
10. `data/update_logs/.gitkeep`

### MODIFICAR (Existentes)
1. `config.py` ← agregar UPDATE_* variables
2. `main.py` ← agregar lógica de verificación + launcher
3. `.env.example` ← documentar nuevas vars (opcional)

### NO MODIFICAR
- Bot cogs, services, repositories
- Base de datos schema
- Integraciones existentes

---

## 7. CONFIGURACIÓN REQUERIDA

En `.env` (agregar estas variables opcionales):
```bash
# Auto-Update Configuration
UPDATE_ENABLED=true
UPDATE_CHECK_INTERVAL_HOURS=6
UPDATE_GITHUB_OWNER=judecalles
UPDATE_GITHUB_REPO=WoW-Bridge-Bot
UPDATE_ALLOW_PRERELEASE=false
UPDATE_TIMEOUT_SECONDS=30
```

Si `.env` no tiene estas, se usan defaults sensatos en `config.py`.

---

## 8. FLUJO DE PUBLICACIÓN EN GITHUB

### Paso 1: Incrementar Versión
En `data/versions.json`:
```bash
# ANTES: "1.0.1"
# DESPUÉS: "1.0.2"
```

### Paso 2: Commit & Tag
```bash
git add -A
git commit -m "v1.0.2: Agregar sistema de reclamos + auto-updater"
git tag v1.0.2
git push origin main
git push origin v1.0.2
```

### Paso 3: Crear Release en GitHub
1. Ir a: https://github.com/judecalles/WoW-Bridge-Bot/releases
2. Click "Draft a new release"
3. Tag: `v1.0.2`
4. Title: `v1.0.2 - Sistema de Reclamos & Auto-Updater`
5. Description:
   ```markdown
   ## Cambios
   - ✨ Sistema de reclamos completo (panel, modales, staff actions)
   - 🔄 Auto-updater robusto para múltiples instalaciones
   - 🐛 Fixes en UI y validaciones

   ## Notas de Instalación
   Si ya tienes v1.0.1 instalado:
   - El bot se actualizará automáticamente en el próximo reinicio
   - Se creará backup en data/backups/bot-1.0.1.zip
   ```
6. Attach asset: `WoW-Bridge-Bot-1.0.2.zip` (comprimido sin carpeta padre)
7. Click "Publish release"

### Asset Correcto
El ZIP debe contener:
```
bot/
updater/
data/
scripts/
config.py
main.py
requirements.txt
version.json
... (otros archivos)
```

**NO incluir**:
- `.env` (confidencial)
- `logs/` (locales)
- `bridge.db` (producción)
- `__pycache__/`
- `.venv/`

---

## 9. PASOS DE PRUEBA LOCAL

### Test 1: Versionado
```bash
cd G:\Bot MVP
python -c "from updater.version_manager import VersionManager; print(VersionManager.get_current())"
# Output: 1.0.2 ✓
```

### Test 2: GitHub Client
```bash
python -c "
import asyncio
from updater.github_client import GitHubClient
async def test():
    client = GitHubClient('judecalles', 'WoW-Bridge-Bot')
    release = await client.get_latest_release()
    print(release)
asyncio.run(test())
"
```

### Test 3: Comparación de Versiones
```bash
python -c "
from updater.version_manager import VersionManager
print(VersionManager.compare('1.0.2', '1.0.3'))  # Output: -1 (1.0.3 es más nueva)
print(VersionManager.compare('1.0.3', '1.0.3'))  # Output: 0 (igual)
"
```

### Test 4: Restart Script (Simulado)
```bash
# NOTA: No ejecutar si bot está activo; solo verificar sintaxis
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser -Force
& "G:\Bot MVP\scripts\restart_bot.ps1" -Verbose
```

### Test 5: Full Update (Dev)
```bash
# 1. Cambiar versión manual en data/versions.json a "1.0.0"
# 2. Crear release de prueba en GitHub (draft)
# 3. Ejecutar bot
# 4. Observar logs en logs/updater.log
# 5. Verificar que descarga y aplica
```

---

## 10. RIESGOS Y LIMITACIONES

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|--------|-----------|
| GitHub API rate limit | Baja | Bajo | Check cada 6h, rate limit 60/h |
| Descarga corrupta | Baja | Medio | Validación MD5 + reintento |
| Falla PS1 en Windows | Baja | Medio | Fallback a .bat |
| Archivo en uso bloqueado | Media | Bajo | Reinicio limpio via script externo |
| .env expuesto | Muy baja | Alto | Documentar NO incluir en ZIP |
| Rollback incompleto | Muy baja | Bajo | Guardar backup, fácil revertir manual |

---

## 11. RECOMENDACIONES DESPLIEGUE EN INSTALACIONES EXISTENTES

### Para Bot ya en Producción
1. **Versión 1.0.1 → 1.0.2**:
   - Usuario solo hace: reiniciar bot
   - Auto-update lo hace el resto
   - ✓ Transparente, sin intervención

2. **Primera Ejecución de Versión nueva**:
   - Si `data/versions.json` no existe: crear con versión actual
   - Si existe: comparar y proceder normalmente

3. **Migraciones de BD**:
   - Incluir en `requirements.txt` cambios necesarios
   - Script de migración en `data/database.py` (ya tienes async `init_db()`)
   - Updater ejecuta `pip install -r requirements.txt` antes de restart

4. **Backward Compatibility**:
   - Mantener soporte 2 versiones atrás
   - Deprecate features, no elimines sin aviso

---

## 12. CONSIDERACIONES DE SEGURIDAD

✅ **QUÉ SÍ HACEMOS**:
- Solo descargar de GitHub Releases (URL verificada)
- Validar MD5/SHA256 (si GitHub proporciona)
- Extraer a carpeta temp aislada
- Nunca ejecutar código remoto arbitrario
- Logs detallados de qué se reemplazó

❌ **QUÉ NO HACEMOS**:
- No descargar de URLs arbitrarias
- No ejecutar scripts `.ps1` desconocidos
- No exposición de tokens (público repo)
- No modificar `.env` automáticamente

---

## 13. RESUMEN TÉCNICO

| Componente | Tecnología | Status |
|-----------|-----------|--------|
| Versionado | JSON local | Simple, versátil |
| GitHub API | REST v3, sin token | Robusto |
| Descarga | `aiohttp` (async) | Ya en requirements |
| Extracción | `zipfile` standard | Portable |
| Restart | PowerShell + batch | Windows native |
| Logging | Python logging | Separado, auditabl |

---

## 14. PRÓXIMOS PASOS

1. ✅ Implementar `updater/` módulo
2. ✅ Crear scripts de restart
3. ✅ Modificar `main.py` 
4. ✅ Agregar `data/versions.json`
5. ✅ Documentar release workflow
6. ✅ Hacer release v1.0.2 en GitHub
7. ⏳ Probar full cycle: update → restart
8. ⏳ Desplegar en prod

---

**Versión de Documento**: 1.0  
**Fecha**: 2026-07-07  
**Estado**: Listo para Implementación

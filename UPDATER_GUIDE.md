# WoW Bridge Bot - Auto-Updater Implementation Guide

**Versión del Bot**: 1.0.2  
**Versión del Documento**: 1.0  
**Fecha**: 2026-07-07  
**Estado**: Listo para Producción

## 📋 TABLA DE CONTENIDOS

1. [Resumen de Implementación](#resumen)
2. [Archivos Creados y Modificados](#archivos)
3. [Configuración Requerida](#configuración)
4. [Guía de Pruebas Locales](#pruebas)
5. [Flujo de Publicación en GitHub](#github)
6. [Primeros Pasos en Producción](#producción)
7. [Troubleshooting](#troubleshooting)

---

## 📦 RESUMEN DE IMPLEMENTACIÓN {#resumen}

El sistema de auto-actualización está **completamente implementado** y listo para usar. 

### Características:
- ✅ Verificación automática de nuevas versiones en GitHub Releases
- ✅ Descarga segura con validación de integridad (ZIP)
- ✅ Backup automático de versión actual
- ✅ Actualización atómica sin corromper instalación
- ✅ Reinicio automático del bot
- ✅ Rollback manual si es necesario
- ✅ Logs detallados en `logs/updater.log`
- ✅ Sin dependencia de Git en máquinas cliente

### Compatibilidad:
- **SO Primario**: Windows (scripts PowerShell + batch)
- **Futuro**: Arquitectura preparada para Linux/macOS

---

## 📁 ARCHIVOS CREADOS Y MODIFICADOS {#archivos}

### NUEVOS (Crear desde 0)

| Archivo | Propósito |
|---------|----------|
| `updater/__init__.py` | Package initialization y exports |
| `updater/version_manager.py` | Gestión de versionado semántico |
| `updater/github_client.py` | Cliente GitHub Releases API |
| `updater/downloader.py` | Descarga y validación de assets |
| `updater/applicator.py` | Aplicación segura de actualizaciones |
| `updater/logger.py` | Sistema de logging dedicado |
| `scripts/restart_bot.ps1` | Script PowerShell para restart |
| `scripts/restart_bot.bat` | Script Batch fallback |
| `data/versions.json` | Metadata de versión local |

### MODIFICADOS

| Archivo | Cambios |
|---------|---------|
| `config.py` | + 8 variables `UPDATE_*` |
| `main.py` | + `check_and_apply_updates()` function + launcher logic |

---

## ⚙️ CONFIGURACIÓN REQUERIDA {#configuración}

### En `.env` (Opcional - Usando valores por defecto)

```bash
# Habilitar/deshabilitar auto-updater
UPDATE_ENABLED=true

# Cada cuántas horas verificar actualizaciones
UPDATE_CHECK_INTERVAL_HOURS=6

# Repositorio GitHub
UPDATE_GITHUB_OWNER=judecalles
UPDATE_GITHUB_REPO=WoW-Bridge-Bot

# Permitir versiones prerelease
UPDATE_ALLOW_PRERELEASE=false

# Timeout para solicitudes HTTP
UPDATE_TIMEOUT_SECONDS=30

# Cuántos backups mantener
UPDATE_BACKUP_COUNT=2
```

### Valores por Defecto (si no están en `.env`)

```python
# En config.py:
UPDATE_ENABLED = true
UPDATE_CHECK_INTERVAL_HOURS = 6
UPDATE_GITHUB_OWNER = "judecalles"
UPDATE_GITHUB_REPO = "WoW-Bridge-Bot"
UPDATE_ALLOW_PRERELEASE = false
UPDATE_TIMEOUT_SECONDS = 30
UPDATE_BACKUP_COUNT = 2
```

**Nota**: Con estos valores, el bot verificará actualizaciones cada 6 horas. Puedes ajustar en `.env` si lo necesitas.

---

## 🧪 GUÍA DE PRUEBAS LOCALES {#pruebas}

### Test 1: Verificar Versionado

```bash
cd "G:\Bot MVP"
.\.venv\Scripts\python.exe -c "
from updater.version_manager import VersionManager
print('Versión actual:', VersionManager.get_current())
print('Archivo versions.json existe:', VersionManager.get_all())
"
```

**Salida esperada**:
```
Versión actual: 1.0.2
Archivo versions.json existe: {'current': '1.0.2', 'release_date': '2026-07-07T...', ...}
```

### Test 2: Verificar GitHub Client

```bash
cd "G:\Bot MVP"
.\.venv\Scripts\python.exe -c "
import asyncio
from updater.github_client import GitHubClient

async def test():
    client = GitHubClient('judecalles', 'WoW-Bridge-Bot')
    release = await client.get_latest_release()
    if release:
        print('✅ Conexión OK')
        print(f'Última release: {release[\"version\"]}')
    else:
        print('⚠️ No se pudo obtener release (GitHub puede estar inaccesible)')

asyncio.run(test())
"
```

**Salida esperada**:
```
✅ Conexión OK
Última release: 1.0.2
```

### Test 3: Prueba de Versioning (Comparación)

```bash
cd "G:\Bot MVP"
.\.venv\Scripts\python.exe -c "
from updater.version_manager import VersionManager

# Test comparación
print('1.0.2 vs 1.0.3:', VersionManager.compare('1.0.2', '1.0.3'))  # -1 (1.0.3 es más nueva)
print('1.0.3 vs 1.0.2:', VersionManager.compare('1.0.3', '1.0.2'))  # 1  (1.0.3 es más antigua)
print('1.0.2 vs 1.0.2:', VersionManager.compare('1.0.2', '1.0.2'))  # 0  (igual)

# Test actualización disponible
print('¿Hay update de 1.0.2 a 1.0.3?:', VersionManager.is_update_available('1.0.2', '1.0.3'))  # True
"
```

**Salida esperada**:
```
1.0.2 vs 1.0.3: -1
1.0.3 vs 1.0.2: 1
1.0.2 vs 1.0.2: 0
¿Hay update de 1.0.2 a 1.0.3?: True
```

### Test 4: Validar Scripts de Restart

**PowerShell**:
```bash
# Solo verificar sintaxis (NO ejecutar si bot está activo)
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser -Force
& "G:\Bot MVP\scripts\restart_bot.ps1" -Verbose
```

**Batch**:
```bash
# Solo verificar sintaxis
"G:\Bot MVP\scripts\restart_bot.bat" --help
```

### Test 5: Prueba Full del Updater (SIN descargar)

```bash
# 1. Cambiar versión manual
cd "G:\Bot MVP"
$json = Get-Content data/versions.json | ConvertFrom-Json
$json.current = "1.0.0"  # Versión falsa para simular que hay update
$json | ConvertTo-Json | Set-Content data/versions.json

# 2. Iniciar bot (verá que hay update disponible pero no lo descargará sin release real)
.\.venv\Scripts\python.exe main.py

# 3. Ver logs
Get-Content logs/updater.log -Tail 20
```

---

## 📤 FLUJO DE PUBLICACIÓN EN GITHUB {#github}

### Paso 1: Preparar el Código

```bash
cd G:\Bot MVP

# Asegurarse que todo está commit
git add -A
git status  # Verificar que no hay cambios pendientes
```

### Paso 2: Crear Release en GitHub

#### Opción A: Via GitHub Web UI (Recomendado)

1. Ir a: https://github.com/judecalles/WoW-Bridge-Bot/releases
2. Click en "Draft a new release"
3. **Tag version**: `v1.0.2`
4. **Release title**: `v1.0.2 - Sistema de Reclamos & Auto-Updater`
5. **Description**:

```markdown
## ✨ Nuevas Características

- 🎯 Sistema completo de reclamos (panel, modales dinámicos, staff actions)
- 🔄 Auto-updater robusto para múltiples instalaciones
- 📊 Logs detallados de actualizaciones

## 🐛 Fixes

- Correcciones menores en UI

## 🚀 Instalación

### Si es la PRIMERA vez (1.0.2 nuevo):
1. Descargar `WoW-Bridge-Bot-1.0.2.zip`
2. Extraer en tu instalación
3. Ejecutar bot normalmente

### Si ya tienes versión anterior:
- El bot se actualizará **automáticamente** en el próximo reinicio
- Se crea backup en `data/backups/bot-1.0.1.zip`

## ⚡ Notas Técnicas

- Actualización atómica: no corrompe archivos activos
- Respaldos automáticos de versión anterior
- Logs completos en `logs/updater.log`
- Sin requiere Git en máquinas cliente

## 📝 Changelog

- **1.0.2**: Auto-updater + sistema de reclamos
- **1.0.1**: Base del bot
```

6. Attach asset: `WoW-Bridge-Bot-1.0.2.zip`
   - Crear ZIP desde carpeta del bot (sin carpeta padre)
   - Incluir: `bot/`, `updater/`, `scripts/`, `data/`, `config.py`, `main.py`, `requirements.txt`, `version.json`
   - NO incluir: `.env`, `logs/`, `.venv/`, `__pycache__/`, `.git/`

7. Click "Publish release"

#### Opción B: Via CLI

```bash
cd G:\Bot MVP

# Crear tag
git tag v1.0.2
git push origin v1.0.2

# Crear release via GitHub CLI (si está instalado)
gh release create v1.0.2 \
  --title "v1.0.2 - Sistema de Reclamos & Auto-Updater" \
  --body "Ver descripción en GitHub" \
  WoW-Bridge-Bot-1.0.2.zip
```

### Paso 3: Crear ZIP para Release

```bash
# En PowerShell, desde la carpeta del bot:
$exclude = @(".env", ".venv", ".git", "logs", "data\update_temp", "__pycache__", "*.pyc")
Compress-Archive -Path * -DestinationPath "WoW-Bridge-Bot-1.0.2.zip" -Exclude $exclude
```

### Paso 4: Verificar Release

Ir a: https://github.com/judecalles/WoW-Bridge-Bot/releases/tag/v1.0.2
- Ver que el asset ZIP está disponible
- Copiar URL de descarga del asset

---

## 🚀 PRIMEROS PASOS EN PRODUCCIÓN {#producción}

### Para Instalaciones Existentes (v1.0.1 → v1.0.2)

**Usuario solo necesita**:
1. Reiniciar el bot
2. Esperar 30 segundos a que descargue y aplique actualización
3. Bot se reinicia automáticamente con v1.0.2

**En background**:
- Bot detecta que hay v1.0.2 disponible
- Descarga ZIP desde GitHub
- Valida integridad
- Crea backup de v1.0.1
- Extrae archivos nuevos
- Actualiza `versions.json`
- Reinicia el bot
- Logs en `logs/updater.log`

### Para Nuevas Instalaciones (v1.0.2)

1. Descargar `WoW-Bridge-Bot-1.0.2.zip`
2. Extraer
3. Configurar `.env`
4. Ejecutar: `python main.py`
5. Bot inicia normalmente (ya está en v1.0.2)

### Desactivar Auto-Updates (si es necesario)

En `.env`:
```bash
UPDATE_ENABLED=false
```

O modificar `config.py`:
```python
UPDATE_ENABLED = False
```

---

## 🔍 MONITOREO Y LOGS

### Ver Logs de Actualización

```bash
# Última 20 líneas
Get-Content "G:\Bot MVP\logs\updater.log" -Tail 20

# Todo el log
Get-Content "G:\Bot MVP\logs\updater.log"

# En tiempo real
Get-Content "G:\Bot MVP\logs\updater.log" -Wait
```

### Estructura de Logs

```
2026-07-07 16:30:45 - Updater - INFO - ============================================================
2026-07-07 16:30:45 - Updater - INFO - Verificando actualizaciones...
2026-07-07 16:30:45 - Updater - INFO - ============================================================
2026-07-07 16:30:45 - Updater - INFO - Versión actual: 1.0.2
2026-07-07 16:30:50 - Updater - INFO - Última versión disponible: 1.0.2
2026-07-07 16:30:50 - Updater - INFO - Ya estás en la última versión (1.0.2)
```

---

## 🆘 TROUBLESHOOTING {#troubleshooting}

### Problema: "Conectando a GitHub falla"

**Causa**: GitHub inaccesible, sin internet, o firewall bloqueando.

**Solución**:
```bash
# Verificar conexión
ping github.com

# Verificar que puedes acceder a API
curl https://api.github.com/repos/judecalles/WoW-Bridge-Bot/releases/latest
```

Bot **continuará funcionando** normalmente sin actualización.

### Problema: "ZIP descargado está corrupto"

**Causa**: Descarga incompleta o archivo en GitHub corrupto.

**Solución**:
```bash
# El bot detectará corrupción y NO aplicará cambios
# Ver logs: logs/updater.log
# Próximo reinicio intentará de nuevo
```

### Problema: "Error al aplicar actualización"

**Causa**: Problema durante reemplazo de archivos.

**Solución**:
```bash
# 1. Ver qué falló
Get-Content logs/updater.log | Select-String "Error"

# 2. Verificar espacio en disco
Get-PSDrive C | Select-Object Used,Free

# 3. Reinstalar manualmente desde release anterior
# Si todo falla, eliminar bot y reinstalar desde ZIP
```

### Problema: "Scripts PowerShell no ejecutan"

**Causa**: Política de ejecución de PowerShell.

**Solución**:
```bash
# Ejecutar PowerShell como Admin y permitir scripts
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser -Force

# Verificar que funcionan
& "G:\Bot MVP\scripts\restart_bot.ps1" -Verbose
```

### Problema: "Versión no actualiza después de reiniciar"

**Causa**: Posiblemente los archivos no se reemplazaron correctamente.

**Solución**:
```bash
# 1. Verificar versión actual
cat "G:\Bot MVP\data\versions.json"

# 2. Ver logs de updater
Get-Content "G:\Bot MVP\logs\updater.log" -Tail 30

# 3. Reinstalar manualmente si es necesario
# Descargar ZIP de release y extraer
```

### Problema: "Rollback a versión anterior"

**Si actualizaste y hay problemas**:

```bash
# 1. Detener bot
# 2. Restaurar desde backup
$backup = "G:\Bot MVP\data\backups\bot-1.0.1.zip"
Expand-Archive -Path $backup -DestinationPath "G:\Bot MVP" -Force

# 3. Actualizar versions.json
$json = Get-Content "G:\Bot MVP\data\versions.json" | ConvertFrom-Json
$json.current = "1.0.1"
$json | ConvertTo-Json | Set-Content "G:\Bot MVP\data\versions.json"

# 4. Reiniciar bot
python "G:\Bot MVP\main.py"
```

---

## 📋 CHECKLIST PRE-RELEASE

- [ ] Modificar `data/versions.json` a versión correcta (ej: `1.0.2`)
- [ ] Actualizar `CHANGELOG.md` (si existe)
- [ ] Verificar que `requirements.txt` está actualizado
- [ ] Probar que updater detecta correctamente la nueva versión
- [ ] Crear ZIP para release (sin `.env`, `.venv`, etc)
- [ ] Crear release en GitHub con tag `v1.0.2`
- [ ] Adjuntar ZIP a release
- [ ] Probar que descarga funciona
- [ ] Verificar que puedes restaurar desde backup
- [ ] Documentar en `RELEASE_NOTES.md`

---

## 🔐 SEGURIDAD

### Lo que NO hace el updater:

- ❌ Ejecutar código remoto arbitrario
- ❌ Modificar `.env` automáticamente
- ❌ Descargar de URLs no verificadas
- ❌ Necesitar tokens de GitHub (repos públicos)
- ❌ Sobrescribir backups existentes

### Lo que SÍ hace:

- ✅ Descarga SOLO de GitHub Releases
- ✅ Valida integridad de ZIP
- ✅ Crea backup antes de aplicar
- ✅ Logs detallados de cada paso
- ✅ Rollback seguro si hay error

---

## 📞 SOPORTE

Si tienes problemas:

1. Ver logs en `logs/updater.log`
2. Verificar conexión a GitHub
3. Asegurar espacio en disco
4. Reinstalar desde backup si es necesario
5. Contactar a administrador

---

**Documento**: `UPDATER_GUIDE.md`  
**Versión**: 1.0  
**Última actualización**: 2026-07-07

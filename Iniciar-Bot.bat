@echo off
title Sistema de Gestion WoW Bot - NaerZone

echo ==========================================
echo        SISTEMA DE GESTION WOW BOT
echo ==========================================
echo.

:: 1) VERIFICACION DE .env
if not exist ".env" (
    echo [INFO] No se encontro el archivo .env
    echo [INFO] Copiando .env.example a .env...
    copy .env.example .env >nul
    echo.
    echo =================================================================
    echo                      SE CREO .env AUTOMATICAMENTE
    echo =================================================================
    echo Debes abrir el archivo .env y rellenar estas variables
    echo obligatorias antes de continuar arrancando el bot:
    echo.
    echo - DISCORDBOTTOKEN
    echo - DISCORDGUILDID
    echo - AIAPIKEY
    echo - AIPROVIDER
    echo - AIMODEL
    echo - AIENABLED
    echo.
    echo Opcionales de Reglas:
    echo - RULES_SOURCE_TYPE
    echo - RULES_FILE_PATH
    echo - RULES_CHANNEL_ID
    echo.
    echo Ejemplo:
    echo DISCORDBOTTOKEN=tu_token_de_discord
    echo AIPROVIDER=gemini
    echo AIAPIKEY=tu_api_key_de_gemini
    echo AIMODEL=gemini-2.5-flash
    echo AIENABLED=true
    echo.
    echo IMPORTANTE:
    echo .env.example = plantilla de ejemplo
    echo .env = archivo real que usa el bot
    echo.
    pause
    exit /b
)

:: 2) VALIDACION DE VARIABLES CLAVE EN .env
set "BOT_TOKEN="
set "AI_KEY="
set "AI_ENABLED=false"

for /f "usebackq eol=# tokens=1* delims==" %%a in (".env") do (
    if /i "%%a"=="DISCORDBOTTOKEN" set "BOT_TOKEN=%%b"
    if /i "%%a"=="AIAPIKEY" set "AI_KEY=%%b"
    if /i "%%a"=="AIENABLED" set "AI_ENABLED=%%b"
)

:: Limpiar espacios si los hubiera
if defined BOT_TOKEN set "BOT_TOKEN=%BOT_TOKEN: =%"
if defined AI_KEY set "AI_KEY=%AI_KEY: =%"
if defined AI_ENABLED set "AI_ENABLED=%AI_ENABLED: =%"

if not defined BOT_TOKEN (
    echo.
    echo [ERROR] Falta configurar el token de Discord.
    echo El token de Discord va en .env en DISCORDBOTTOKEN=...
    pause
    exit /b
)

if /i "%AI_ENABLED%"=="true" (
    if not defined AI_KEY (
        echo.
        echo [ERROR] La IA esta activada ^(AIENABLED=true^) pero falta la API key.
        echo La API key de IA va en .env en AIAPIKEY=...
        echo El proveedor va en .env en AIPROVIDER=gemini ^(o openai^)
        echo El modelo va en .env en AIMODEL=...
        pause
        exit /b
    )
)

echo [INFO] Iniciando el entorno virtual y el bot...

:: Verificar si existe el entorno virtual
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [WARNING] No se encontro el entorno virtual .venv. Ejecutando con el Python del sistema.
)

:: Cerrar cualquier otra instancia del bot activa para evitar conflictos de multiconexión
echo [INFO] Limpiando procesos antiguos en segundo plano...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | Where-Object { $_.CommandLine -like '*main.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

:: Configurar base de datos para activar Guild (Taberna desactivada)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sqlite3, config; conn = sqlite3.connect(config.DB_PATH); conn.execute('UPDATE bridge_config SET bridge_taberna_activo = 0, bridge_guild_activo = 1'); conn.commit()" >nul 2>&1
)

:: Ejecutar el bot utilizando el python del entorno virtual explícitamente para mayor seguridad
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    python main.py
)

:: Si el bot se cierra por un error, pausa para que el usuario pueda leerlo
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] El bot se detuvo inesperadamente con el codigo de error %ERRORLEVEL%.
    pause
) else (
    echo.
    echo [INFO] El bot se ha cerrado correctamente.
    timeout /t 3 >nul
)

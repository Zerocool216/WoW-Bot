@echo off
REM Restart Bot Script (Batch) - Windows Fallback
REM Uso: restart_bot.bat
REM Objetivo: Detener el proceso anterior del bot y reiniciar uno nuevo
REM Esta es una version basica si PowerShell no esta disponible

setlocal enabledelayedexpansion

REM Configuración
set BotDir=%~dp0..
set MainPy=%BotDir%\main.py
set VenvDir=%BotDir%\.venv
set PythonExe=%VenvDir%\Scripts\python.exe

echo.
echo ================================================
echo     WoW Bridge Bot - Restart Script (Batch)
echo ================================================
echo.

REM Verificar que existe main.py
if not exist "%MainPy%" (
    echo [ERROR] No se encontro main.py en %MainPy%
    exit /b 1
)

REM Verificar que existe venv
if not exist "%PythonExe%" (
    echo [ERROR] Venv no encontrado en %VenvDir%
    exit /b 1
)

echo [INFO] Directorio bot: %BotDir%
echo [INFO] Python: %PythonExe%
echo.

REM Paso 1: Detener procesos python que ejecuten main.py
echo [INFO] Buscando procesos bot anteriores...
for /f "tokens=2" %%A in ('tasklist ^| find /i "python.exe"') do (
    echo [INFO] Deteniendo python.exe...
    taskkill /PID %%A /T /F >nul 2>&1
)

REM Esperar a limpiar recursos
echo [INFO] Limpiando recursos...
timeout /t 1 /nobreak >nul

REM Paso 2: Reiniciar bot
echo [INFO] Iniciando nuevo proceso bot...
cd /d "%BotDir%"
start "" "%PythonExe%" "%MainPy%"

if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCCESS] Bot reiniciado exitosamente
    exit /b 0
) else (
    echo.
    echo [ERROR] Error al reiniciar bot
    exit /b 1
)

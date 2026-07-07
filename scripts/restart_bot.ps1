# Restart Bot Script (PowerShell) - Windows
# Uso: .\restart_bot.ps1 [-Verbose]
# Objetivo: Detener el proceso anterior del bot y reiniciar uno nuevo

param(
    [switch]$Verbose = $false
)

# Configuración
$BotDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$MainPyScript = Join-Path $BotDirectory "main.py"
$VenvPath = Join-Path $BotDirectory ".venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
$BotProcessName = "python"

# Funciones auxiliares
function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$Timestamp] [$Level] $Message"
}

function Wait-ProcessStop {
    param(
        [int]$TimeoutSeconds = 10
    )
    $StartTime = Get-Date
    $Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
    
    while ((Get-Date) - $StartTime -lt $Timeout) {
        $Process = Get-Process $BotProcessName -ErrorAction SilentlyContinue | 
                   Where-Object { $_.CommandLine -like "*main.py*" } |
                   Select-Object -First 1
        
        if ($null -eq $Process) {
            Write-Log "Proceso bot detenido correctamente" "SUCCESS"
            return $true
        }
        
        Start-Sleep -Milliseconds 500
    }
    
    Write-Log "Timeout esperando que el proceso se detenga" "WARNING"
    return $false
}

# ============= INICIO DEL SCRIPT =============

Write-Log "================================================"
Write-Log "    WoW Bridge Bot - Restart Script (PowerShell)"
Write-Log "================================================"

# Verificar que existe el archivo main.py
if (-not (Test-Path $MainPyScript)) {
    Write-Log "ERROR: No se encontró main.py en $MainPyScript" "ERROR"
    exit 1
}

# Verificar que existe venv
if (-not (Test-Path $PythonExe)) {
    Write-Log "ERROR: Venv no encontrado en $VenvPath" "ERROR"
    exit 1
}

Write-Log "Directorio bot: $BotDirectory" "DEBUG"
Write-Log "Python executable: $PythonExe" "DEBUG"

# Paso 1: Detener proceso anterior
Write-Log "Buscando procesos bot anteriores..."
$ExistingProcess = Get-Process $BotProcessName -ErrorAction SilentlyContinue | 
                   Where-Object { $_.CommandLine -like "*main.py*" } |
                   Select-Object -First 1

if ($null -ne $ExistingProcess) {
    Write-Log "Proceso bot encontrado (PID: $($ExistingProcess.Id))" "INFO"
    Write-Log "Intentando detener gracefully..." "INFO"
    
    # Enviar señal de terminación graceful
    try {
        $ExistingProcess.CloseMainWindow() | Out-Null
        $Stopped = Wait-ProcessStop -TimeoutSeconds 10
        
        if (-not $Stopped) {
            Write-Log "Forzando terminación del proceso" "WARNING"
            Stop-Process -Id $ExistingProcess.Id -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 1000
        }
    } catch {
        Write-Log "Error deteniendo proceso: $_" "ERROR"
        exit 1
    }
} else {
    Write-Log "No hay proceso bot activo" "INFO"
}

# Paso 2: Esperar un segundo para limpiar recursos
Write-Log "Limpiando recursos..." "INFO"
Start-Sleep -Seconds 1

# Paso 3: Reiniciar bot
Write-Log "Iniciando nuevo proceso bot..." "INFO"

try {
    $ProcessInfo = New-Object System.Diagnostics.ProcessStartInfo
    $ProcessInfo.FileName = $PythonExe
    $ProcessInfo.Arguments = $MainPyScript
    $ProcessInfo.WorkingDirectory = $BotDirectory
    $ProcessInfo.UseShellExecute = $true
    $ProcessInfo.CreateNoWindow = $false
    $ProcessInfo.WindowStyle = 'Normal'
    
    $NewProcess = [System.Diagnostics.Process]::Start($ProcessInfo)
    
    if ($null -ne $NewProcess) {
        Write-Log "✅ Bot reiniciado exitosamente (PID: $($NewProcess.Id))" "SUCCESS"
        Write-Log "Espera a que el bot se conecte a Discord..." "INFO"
        exit 0
    } else {
        Write-Log "❌ Error: No se pudo crear nuevo proceso" "ERROR"
        exit 1
    }
} catch {
    Write-Log "❌ Error iniciando bot: $_" "ERROR"
    exit 1
}

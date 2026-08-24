@echo off
setlocal EnableDelayedExpansion

REM ==========================================================
REM  start_pcs_ic.bat
REM  Starts the PCS/IC Trade Decisioning Tool (Flask app) if it
REM  is not already running. Safe to run at logon, startup, or
REM  on a schedule — safe to fire more than once, too.
REM  Paths are relative to this file — no hardcoded user dirs.
REM
REM  Detection is PID-file based, NOT port-based. This mirrors
REM  the summer-os project's start script, where port-based
REM  detection turned out to be a false-positive trap (Tailscale
REM  permanently bound to that app's port). Nothing on this
REM  machine is known to squat on port 5057 (this app's default
REM  port, see FLASK_PORT in .env) the same way, but there is no
REM  downside to using the same proven, self-contained mechanism
REM  here too instead of trusting that assumption to hold forever.
REM
REM  PYTHON_EXE points at the project's own virtual environment
REM  (.venv\Scripts\python.exe), which has every package in
REM  requirements.txt installed (confirmed, including lxml — see
REM  README.md's Installation section). It is never a hardcoded
REM  machine-specific path.
REM ==========================================================

REM ── Configuration ─────────────────────────────────────────
set PROJECT_DIR=%~dp0
set PROJECT_DIR=%PROJECT_DIR:~0,-1%
set PYTHON_EXE=%PROJECT_DIR%\.venv\Scripts\python.exe
set LOG_DIR=%PROJECT_DIR%\logs
set LOG_FILE=%LOG_DIR%\pcs_ic_start.log
set PID_FILE=%PROJECT_DIR%\pcs_ic.pid
set LAUNCH_SCRIPT=%~dp0pcs_ic_launch.ps1

REM ── Ensure logs directory exists ───────────────────────────
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

call :log "===== PCS/IC Trade Tool Start Script ====="
call :log "Project dir : %PROJECT_DIR%"
call :log "Python      : %PYTHON_EXE%"

REM ── Verify Python executable ───────────────────────────────
if not exist "%PYTHON_EXE%" (
    call :log "ERROR: Python not found at %PYTHON_EXE%"
    call :log "Update PYTHON_EXE at the top of this script, or recreate .venv:"
    call :log "  cd /d %PROJECT_DIR% && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt"
    exit /b 1
)

REM ── Check if app is already running, via our own PID file ──
if exist "%PID_FILE%" (
    set /p EXISTING_PID=<"%PID_FILE%"
    tasklist /FI "PID eq !EXISTING_PID!" /FI "IMAGENAME eq python.exe" /NH 2>nul | findstr /I "python.exe" >nul
    if !ERRORLEVEL! equ 0 (
        call :log "PCS/IC Trade Tool is already running (PID !EXISTING_PID!) — nothing to do."
        exit /b 0
    ) else (
        call :log "Found stale PID file (PID !EXISTING_PID! is not a running python.exe) — removing it."
        del "%PID_FILE%" >nul 2>&1
    )
)

REM ── Change to project directory ────────────────────────────
cd /d "%PROJECT_DIR%"
if errorlevel 1 (
    call :log "ERROR: Could not cd to %PROJECT_DIR%"
    exit /b 1
)

REM ── Launch app via PowerShell (no console window, output is
REM     actually captured, and we get the real PID back) ───────
call :log "Starting PCS/IC Trade Tool (python app.py) ..."
set NEW_PID=
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%LAUNCH_SCRIPT%" -PythonExe "%PYTHON_EXE%" -ProjectDir "%PROJECT_DIR%" -LogDir "%LOG_DIR%"`) do set NEW_PID=%%P

if not defined NEW_PID (
    call :log "ERROR: Failed to launch PCS/IC Trade Tool — no PID returned."
    call :log "Check that PowerShell execution is not blocked, and check %LOG_DIR%\pcs_ic_app_err.log"
    exit /b 1
)

echo !NEW_PID!> "%PID_FILE%"
call :log "Launched PCS/IC Trade Tool — PID !NEW_PID! (recorded in pcs_ic.pid)"

REM ── Give it 3 seconds, then confirm the process is still alive ──
timeout /t 3 /nobreak >nul
tasklist /FI "PID eq !NEW_PID!" /FI "IMAGENAME eq python.exe" /NH 2>nul | findstr /I "python.exe" >nul
if !ERRORLEVEL! equ 0 (
    call :log "PCS/IC Trade Tool started successfully (PID !NEW_PID!) — http://localhost:5057"
    call :log "===== Start Script Done ====="
    exit /b 0
) else (
    call :log "WARNING: PID !NEW_PID! is no longer running — app likely crashed on startup."
    call :log "Check %LOG_DIR%\pcs_ic_app_err.log and %LOG_DIR%\pcs_ic_app.log for errors."
    del "%PID_FILE%" >nul 2>&1
    call :log "===== Start Script Done ====="
    exit /b 1
)


:log
set MSG=%~1
echo [%date% %time%] %MSG%
echo [%date% %time%] %MSG%>> "%LOG_FILE%"
exit /b

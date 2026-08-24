@echo off
setlocal EnableDelayedExpansion

REM ==========================================================
REM  stop_pcs_ic.bat
REM  Stops the PCS/IC Trade Decisioning Tool using the PID
REM  recorded by start_pcs_ic.bat (pcs_ic.pid).
REM
REM  Not port-based, for the same reason start_pcs_ic.bat isn't:
REM  reading our own PID file guarantees this only ever kills the
REM  exact process we started, never whatever else happens to be
REM  on port 5057. Safe to run even if the app is not running.
REM
REM  No Task Scheduler trigger calls this script by default — this
REM  tool has no natural "should stop now" moment the way a kid's
REM  screen-time app does. It's here purely for manual use (e.g.
REM  restarting after a code change) or if you decide to add a
REM  scheduled stop later.
REM ==========================================================

REM ── Configuration ─────────────────────────────────────────
set PROJECT_DIR=%~dp0
set PROJECT_DIR=%PROJECT_DIR:~0,-1%
set LOG_DIR=%PROJECT_DIR%\logs
set LOG_FILE=%LOG_DIR%\pcs_ic_stop.log
set PID_FILE=%PROJECT_DIR%\pcs_ic.pid

REM ── Ensure logs directory exists ───────────────────────────
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

call :log "===== PCS/IC Trade Tool Stop Script ====="

if not exist "%PID_FILE%" (
    call :log "No pcs_ic.pid file found — nothing to stop."
    call :log "===== Stop Script Done ====="
    exit /b 0
)

set /p TARGET_PID=<"%PID_FILE%"

if not defined TARGET_PID (
    call :log "ERROR: pcs_ic.pid is empty — removing it."
    del "%PID_FILE%" >nul 2>&1
    call :log "===== Stop Script Done ====="
    exit /b 1
)

REM ── Confirm the PID is actually a python.exe before killing ──
REM  (guards against a stale/reused PID pointing at an unrelated process)
tasklist /FI "PID eq %TARGET_PID%" /FI "IMAGENAME eq python.exe" /NH 2>nul | findstr /I "python.exe" >nul
if %ERRORLEVEL% neq 0 (
    call :log "PID %TARGET_PID% is not a running python.exe — already stopped. Removing stale pid file."
    del "%PID_FILE%" >nul 2>&1
    call :log "===== Stop Script Done ====="
    exit /b 0
)

call :log "Stopping PCS/IC Trade Tool — PID %TARGET_PID%"

REM ── Kill the Flask process only ────────────────────────────
REM  /F = force  /T = include child processes
taskkill /PID %TARGET_PID% /F /T >nul 2>&1

if %ERRORLEVEL% equ 0 (
    call :log "Successfully stopped PCS/IC Trade Tool (PID %TARGET_PID%)."
    del "%PID_FILE%" >nul 2>&1
) else (
    call :log "ERROR: taskkill failed for PID %TARGET_PID% (exit code %ERRORLEVEL%)."
    call :log "Try running this script as Administrator."
    exit /b 1
)

call :log "===== Stop Script Done ====="
exit /b 0


:log
set MSG=%~1
echo [%date% %time%] %MSG%
echo [%date% %time%] %MSG%>> "%LOG_FILE%"
exit /b

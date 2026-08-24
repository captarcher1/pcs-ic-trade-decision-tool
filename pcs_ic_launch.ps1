# ==========================================================
#  pcs_ic_launch.ps1
#  Launches app.py detached, with no visible console window,
#  and with stdout/stderr properly redirected to log files.
#  Prints the new process's PID to stdout so the calling batch
#  file (start_pcs_ic.bat) can record it.
#
#  Why this exists: cmd's "start" command cannot reliably both
#  (a) suppress the console window and (b) capture output, and
#  it has no built-in way to hand back the PID it just created.
#  PowerShell's Start-Process -PassThru does all three reliably.
#
#  (Same pattern as summer-os's summer_os_launch.ps1 — kept
#  identical on purpose so both projects are easy to maintain
#  side by side.)
# ==========================================================

param(
    [Parameter(Mandatory = $true)][string]$PythonExe,
    [Parameter(Mandatory = $true)][string]$ProjectDir,
    [Parameter(Mandatory = $true)][string]$LogDir
)

$stdOutLog = Join-Path $LogDir "pcs_ic_app.log"
$stdErrLog = Join-Path $LogDir "pcs_ic_app_err.log"

$proc = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList "app.py" `
    -WorkingDirectory $ProjectDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdOutLog `
    -RedirectStandardError $stdErrLog `
    -PassThru

Write-Output $proc.Id

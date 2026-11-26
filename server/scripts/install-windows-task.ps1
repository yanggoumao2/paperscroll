<#
  Run the PaperScroll server in the background on Windows: a scheduled task that starts at logon
  (no console window) and restarts it if it crashes. Run once from PowerShell (no admin needed):
    powershell -ExecutionPolicy Bypass -File server\scripts\install-windows-task.ps1
  Remove with:  Unregister-ScheduledTask -TaskName 'PaperScroll Server' -Confirm:$false
#>
$ErrorActionPreference = 'Stop'
$server = Split-Path $PSScriptRoot -Parent
$pyw = Join-Path $server '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $pyw)) { throw "No virtual environment yet: run 'uv sync' in $server first." }
$action = New-ScheduledTaskAction -Execute $pyw -Argument 'run.py' -WorkingDirectory $server
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
  -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName 'PaperScroll Server' -Action $action -Trigger $trigger -Settings $settings `
  -Description 'PaperScroll arXiv feed server' -Force | Out-Null
Start-ScheduledTask -TaskName 'PaperScroll Server'
"Installed and started. Open http://127.0.0.1:8765 in a browser (first start downloads ~470 MB of model and papers)."

# Register / update the Windows scheduled task for the weekly charging-UP leaderboard.
# Runs independently of any Claude session - only Windows Task Scheduler is involved.
#
# Usage (plain PowerShell, no admin needed):
#   powershell -NoProfile -ExecutionPolicy Bypass -File register_weekly_task.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File register_weekly_task.ps1 -At "2026-08-24T11:40:00"
#   powershell -NoProfile -ExecutionPolicy Bypass -File register_weekly_task.ps1 -Weekly
#   powershell -NoProfile -ExecutionPolicy Bypass -File register_weekly_task.ps1 -Unregister
#
# NOTE: keep this file ASCII-only and saved with a UTF-8 BOM. PowerShell 5.1 decodes
# BOM-less files using the system codepage (GBK here), which mangles non-ASCII text and
# can swallow line breaks.

param(
    [string]$TaskName = 'ChargingUP-WeeklyRank',
    [string]$At = '',
    [switch]$Weekly,
    [switch]$Unregister
)

$ErrorActionPreference = 'Stop'
$base = 'C:\Users\dengyuting02\WorkBuddy\20260514140206'
$launcher = Join-Path $base 'auto_weekly_update.cmd'

if ($Unregister) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task: $TaskName"
    exit 0
}

if (-not (Test-Path $launcher)) { throw "Launcher not found: $launcher" }

# No -At given: start at the NEXT Monday 11:40. Never default to a past timestamp -
# StartWhenAvailable would treat it as a missed trigger and fire an immediate catch-up run.
if ([string]::IsNullOrWhiteSpace($At)) {
    $runAt = (Get-Date).Date.AddHours(11).AddMinutes(40)
    while ($runAt.DayOfWeek -ne 'Monday' -or $runAt -le (Get-Date)) {
        $runAt = $runAt.AddDays(1)
    }
    Write-Host ("No -At given, using next Monday: {0:yyyy-MM-dd HH:mm}" -f $runAt)
} else {
    $runAt = [datetime]::Parse($At)
}
$action = New-ScheduledTaskAction -Execute $launcher -WorkingDirectory $base

if ($Weekly) {
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $runAt
} else {
    $trigger = New-ScheduledTaskTrigger -Once -At $runAt
}

# StartWhenAvailable : if the PC was off/asleep at the trigger time, run as soon as possible
#                      after it comes back (this is what covers the "PC was shut down" case).
# WakeToRun          : wake the machine from sleep to run. Useless on a full shutdown -
#                      StartWhenAvailable is the fallback there.
# ExecutionTimeLimit : phase 1 alone can take ~60 min on a slow cluster; 4h is a safe cap.
$settingsParams = @{
    StartWhenAvailable        = $true
    WakeToRun                 = $true
    AllowStartIfOnBatteries   = $true
    DontStopIfGoingOnBatteries = $true
    MultipleInstances         = 'IgnoreNew'
    ExecutionTimeLimit        = (New-TimeSpan -Hours 4)
}
$settings = New-ScheduledTaskSettingsSet @settingsParams

# LogonType Interactive: run as the logged-on user so that `git push` can read the GitHub
# credential from Windows Credential Manager. A "run whether user is logged on or not"
# principal (Password/S4U) cannot reach the credential store, so the push would fail.
$principalParams = @{
    UserId    = "$env:USERDOMAIN\$env:USERNAME"
    LogonType = 'Interactive'
    RunLevel  = 'Limited'
}
$principal = New-ScheduledTaskPrincipal @principalParams

$registerParams = @{
    TaskName    = $TaskName
    Action      = $action
    Trigger     = $trigger
    Settings    = $settings
    Principal   = $principal
    Description = 'Weekly charging-UP leaderboard: adhoc queries -> board count -> LLM summaries -> hot topics -> dashboard -> commit & push. Logs: log\auto_weekly_*.log'
    Force       = $true
}
Register-ScheduledTask @registerParams | Out-Null

Write-Host "Registered scheduled task: $TaskName"
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State | Format-Table -AutoSize
Get-ScheduledTaskInfo -TaskName $TaskName |
    Select-Object NextRunTime, LastRunTime, LastTaskResult | Format-List

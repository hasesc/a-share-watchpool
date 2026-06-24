param(
  [string]$Root = "",
  [string]$TaskPrefix = "CodexAShareWatchpool",
  [ValidateSet("light", "full")]
  [string]$Mode = "light",
  [string]$Python = "python",
  [string]$Source = "auto",
  [switch]$KeepLegacy
)

# Resolve paths relative to this script's location
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $ScriptDir "run_daily_pipeline.ps1"

# Default Root to workspace/ directory next to scripts/
if (-not $Root) {
  $Root = Join-Path (Split-Path -Parent $ScriptDir) "workspace"
}
$Pwsh = "powershell.exe"
$LegacyTasksToDelete = @("$TaskPrefix-1630-ReviewFill")

if ($Mode -eq "light") {
  $Tasks = @(
    @{ Name = "$TaskPrefix-0840-PreMarket"; Time = "08:40"; Stage = "pre_market" },
    @{ Name = "$TaskPrefix-0935-MorningConfirm"; Time = "09:35"; Stage = "morning_confirm" },
    @{ Name = "$TaskPrefix-1445-LateConfirm"; Time = "14:45"; Stage = "late_confirm" },
    @{ Name = "$TaskPrefix-1506-PostClose"; Time = "15:06"; Stage = "post_close" },
    @{ Name = "$TaskPrefix-1510-ReviewFill"; Time = "15:10"; Stage = "review_fill" }
  )
  if (-not $KeepLegacy) {
    $LegacyTasksToDelete += @(
      "$TaskPrefix-1430-PreScreen",
      "$TaskPrefix-1452-LateConfirm"
    )
  }
} else {
  $Tasks = @(
    @{ Name = "$TaskPrefix-0840-PreMarket"; Time = "08:40"; Stage = "pre_market" },
    @{ Name = "$TaskPrefix-0935-MorningConfirm"; Time = "09:35"; Stage = "morning_confirm" },
    @{ Name = "$TaskPrefix-1430-PreScreen"; Time = "14:30"; Stage = "pre_screen" },
    @{ Name = "$TaskPrefix-1445-LateConfirm"; Time = "14:45"; Stage = "late_confirm" },
    @{ Name = "$TaskPrefix-1506-PostClose"; Time = "15:06"; Stage = "post_close" },
    @{ Name = "$TaskPrefix-1510-ReviewFill"; Time = "15:10"; Stage = "review_fill" }
  )
}

foreach ($Task in $Tasks) {
  $Action = "$Pwsh -NoProfile -ExecutionPolicy Bypass -File `"$Script`" -Stage $($Task.Stage) -Root `"$Root`" -Python `"$Python`" -Source $Source"
  schtasks.exe /Create /F /TN $Task.Name /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST $Task.Time /TR $Action | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to create task $($Task.Name). Run this script from an elevated PowerShell session."
  }
}

foreach ($LegacyTask in $LegacyTasksToDelete) {
  schtasks.exe /Delete /F /TN $LegacyTask 2>$null | Out-Null
}

Write-Host "Installed $($Tasks.Count) weekday $Mode tasks. Non-trading days are filtered inside run_daily_pipeline.ps1."

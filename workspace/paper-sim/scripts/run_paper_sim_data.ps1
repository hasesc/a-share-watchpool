param(
  [string]$Root = "",
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

# Resolve the repo root (3 levels up from paper-sim/scripts/)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $ScriptDir))
$Pipeline = Join-Path $RepoRoot "scripts\run_daily_pipeline.ps1"

# Default Root to workspace/ next to scripts/
if (-not $Root) {
  $Root = Join-Path $RepoRoot "workspace"
}

$Pwsh = "powershell.exe"

& $Pwsh -NoProfile -ExecutionPolicy Bypass -File $Pipeline -Stage late_confirm -Root $Root -Python $Python -Source auto

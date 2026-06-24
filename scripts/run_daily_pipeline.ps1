param(
  [ValidateSet("pre_market", "pre_screen", "morning_confirm", "late_confirm", "post_close", "review_fill", "health", "audit")]
  [string]$Stage = "post_close",
  [string]$Root = "",
  [string]$Python = "python",
  [string]$Source = "auto",
  [string]$Proxy = "",
  [int]$SeedLimit = 80,
  [int]$HistoryLimit = 30,
  [int]$RiskLimit = 40
)

$ErrorActionPreference = "Stop"
# Resolve the scripts directory (where this .ps1 lives)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Skill = $ScriptDir

# If -Root was not supplied, default to the workspace/ directory next to scripts/
if (-not $Root) {
  $Root = Join-Path (Split-Path -Parent $ScriptDir) "workspace"
}
if (-not (Test-Path $Python)) {
  $Python = "python"
}
$Date = Get-Date -Format "yyyyMMdd"
$RunDir = Join-Path $Root "data\watchpool\$Date`_$Stage"
$Reports = Join-Path $Root "reports"
New-Item -ItemType Directory -Force -Path $Reports | Out-Null
$HealthReports = Join-Path $Reports "health\$Date"
$DashboardReports = Join-Path $Reports "dashboard"
New-Item -ItemType Directory -Force -Path $HealthReports | Out-Null
New-Item -ItemType Directory -Force -Path $DashboardReports | Out-Null

function Set-PipelineProxy {
  param([string]$ProxyValue)

  if (-not $ProxyValue) {
    $ProxyValue = $env:HTTPS_PROXY
  }
  if (-not $ProxyValue) {
    $ProxyValue = $env:HTTP_PROXY
  }
  if (-not $ProxyValue) {
    try {
      $winHttp = netsh winhttp show proxy
      $proxyLine = $winHttp | Where-Object { $_ -match "Proxy Server\(s\)\s*:\s*(.+)$" } | Select-Object -First 1
      if ($proxyLine -and $Matches[1]) {
        $candidate = $Matches[1].Trim()
        if ($candidate -and $candidate -notmatch "Direct access") {
          if ($candidate -notmatch "^https?://") {
            $candidate = "http://$candidate"
          }
          $ProxyValue = $candidate
        }
      }
    } catch {
      Write-Host "Proxy auto-detect skipped: $($_.Exception.Message)"
    }
  }

  if ($ProxyValue) {
    $env:HTTP_PROXY = $ProxyValue
    $env:HTTPS_PROXY = $ProxyValue
    $env:ALL_PROXY = $ProxyValue
    if (-not $env:NO_PROXY) {
      $env:NO_PROXY = "localhost,127.0.0.1"
    }
    Write-Host "Using proxy for Python data sources: $ProxyValue"
  }
}

function Write-PipelineError {
  param(
    [string]$Path,
    [string]$StageName,
    [object]$ErrorRecord
  )
  $payload = [ordered]@{
    generated_at = (Get-Date).ToString("s")
    stage = $StageName
    error = $ErrorRecord.Exception.Message
    detail = $ErrorRecord.Exception.ToString()
  }
  $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding UTF8
}

Set-PipelineProxy -ProxyValue $Proxy

function Get-CandidateCodes {
  param(
    [string]$CandidatePath,
    [int]$Limit
  )
  if (-not (Test-Path $CandidatePath)) {
    return @()
  }
  $rows = Import-Csv -LiteralPath $CandidatePath
  $codes = @()
  foreach ($row in $rows) {
    $code = $row.code
    if (-not $code) {
      $code = $row.symbol
    }
    if ($code) {
      $codes += $code.ToString().Trim()
    }
    if ($codes.Count -ge $Limit) {
      break
    }
  }
  return $codes
}

if ($Stage -ne "health") {
  New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
  $SessionPath = Join-Path $RunDir "trade_session_direct.json"
  & $Python "$Skill\scripts\collect_public_data.py" calendar --output $SessionPath
  $Session = Get-Content -LiteralPath $SessionPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($Session.session -eq "non_trading_day" -and $Stage -notin @("review_fill", "audit")) {
    Write-Host "Non-trading day. Skip $Stage."
    exit 0
  }
}

if ($Stage -in @("pre_market", "pre_screen", "morning_confirm", "late_confirm", "post_close")) {
  $StageError = $null
  try {
    & $Python "$Skill\scripts\collect_public_data.py" snapshot --output-dir $RunDir --source $Source --seed-limit $SeedLimit
    $CandidatePath = Join-Path $RunDir "candidate_seed.csv"
    $SnapshotPath = Join-Path $RunDir "all_a_share_snapshot.csv"
    $HistoryCodes = Get-CandidateCodes -CandidatePath $CandidatePath -Limit $HistoryLimit
    if ($Stage -eq "pre_market" -and $HistoryCodes.Count -gt 0) {
      $begin = (Get-Date).AddDays(-45).ToString("yyyyMMdd")
      $end = Get-Date -Format "yyyyMMdd"
      & $Python "$Skill\scripts\collect_public_data.py" history --codes ($HistoryCodes -join ",") --begin $begin --end $end --output-dir $RunDir
    }
    $RiskCodes = @()
    if ($Stage -eq "pre_market" -or $Stage -eq "pre_screen" -or $Stage -eq "post_close" -or $Stage -eq "morning_confirm") {
      $RiskCodes = Get-CandidateCodes -CandidatePath $CandidatePath -Limit $RiskLimit
      
      # Inject candidate codes from today's pre-market report so all groups (short, medium, long term) are evaluated
      $PreMarketJsonPath = Join-Path $Reports "daily\$Date\pre_market_top5.json"
      if (-not (Test-Path $PreMarketJsonPath)) {
        $PreMarketJsonPath = Join-Path $Reports "latest\pre_market_top5.json"
      }
      if (Test-Path $PreMarketJsonPath) {
        try {
          $PreMarketJson = Get-Content -LiteralPath $PreMarketJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
          foreach ($key in @("tradable_candidates", "premarket_inference_candidates", "research_leads")) {
            if ($PreMarketJson.$key) {
              foreach ($item in $PreMarketJson.$key) {
                if ($item.code) {
                  $c = $item.code.ToString().Trim()
                  if ($RiskCodes -notcontains $c) {
                    $RiskCodes += $c
                  }
                }
              }
            }
          }
        } catch {
          Write-Host "Failed to parse pre_market_top5.json: $($_.Exception.Message)"
        }
      }
    } elseif ($Stage -eq "late_confirm") {
      $HoldingCodes = @()
      $StatePath = Join-Path $Root "paper-sim\data\state.json"
      if (Test-Path $StatePath) {
        try {
          $StateJson = Get-Content -LiteralPath $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json
          if ($StateJson.positions) {
            $HoldingCodes = $StateJson.positions.PSObject.Properties.Name
          }
        } catch {
          Write-Host "Failed to parse state.json: $($_.Exception.Message)"
        }
      }
      
      $AllUniqueCodes = @()
      foreach ($c in $HoldingCodes) {
        if ($c -and $AllUniqueCodes -notcontains $c) {
          $AllUniqueCodes += $c
        }
      }
      $RiskCodes = $AllUniqueCodes
      Write-Host "Late confirm stage: Checking only hold codes to optimize speed (Count: $($RiskCodes.Count)): $($RiskCodes -join ',')"
    } else {
      $RiskCodes = Get-CandidateCodes -CandidatePath $CandidatePath -Limit $RiskLimit
    }

    if ($RiskCodes.Count -gt 0 -and (Test-Path $SnapshotPath)) {
      & $Python "$Skill\scripts\check_execution_quality.py" --snapshot $SnapshotPath --codes ($RiskCodes -join ",") --output (Join-Path $RunDir "execution_quality.json") --csv-output (Join-Path $RunDir "execution_quality.csv")
      & $Python "$Skill\scripts\check_risk_events.py" --codes ($RiskCodes -join ",") --output (Join-Path $RunDir "risk_events.json") --csv-output (Join-Path $RunDir "risk_events.csv")
    }
    $PolicyNewsScript = Join-Path $Root "scripts\collect_policy_news.py"
    if ($Stage -eq "pre_market" -and (Test-Path $PolicyNewsScript)) {
      & $Python $PolicyNewsScript --run-dir $RunDir --output (Join-Path $RunDir "policy_news.json") --date $Date
    }
  } catch {
    $StageError = $_
    Write-Host "Stage $Stage failed: $($_.Exception.Message)"
    Write-PipelineError -Path (Join-Path $RunDir "pipeline_error.json") -StageName $Stage -ErrorRecord $_
  }
  try {
    $MonitorArgs = @(
      "$Skill\scripts\monitor_data_health.py",
      "--snapshot-dir", $RunDir,
      "--output", (Join-Path $RunDir "data_health.json"),
      "--html-output", (Join-Path $HealthReports "$Stage`_data_health.html")
    )
    $RiskJsonPath = Join-Path $RunDir "risk_events.json"
    $ExecutionJsonPath = Join-Path $RunDir "execution_quality.json"
    if (Test-Path $RiskJsonPath) {
      $MonitorArgs += @("--risk-json", $RiskJsonPath)
    }
    if (Test-Path $ExecutionJsonPath) {
      $MonitorArgs += @("--execution-json", $ExecutionJsonPath)
    }
    & $Python @MonitorArgs
  } catch {
    Write-Host "Data-health monitor failed: $($_.Exception.Message)"
    if (-not $StageError) {
      $StageError = $_
    }
  }
  if ($StageError) {
    exit 1
  }
  if ($Stage -eq "pre_market") {
    $LightReportScript = Join-Path $Root "scripts\render_watchpool_light.py"
    if (Test-Path $LightReportScript) {
      & $Python $LightReportScript --root $Root pre-market
    } else {
      Write-Host "Light report script not found: $LightReportScript"
    }
  }
  if ($Stage -eq "morning_confirm" -or $Stage -eq "late_confirm") {
    $SimulatorScript = Join-Path $Root "paper-sim\scripts\paper_sim_portfolio.py"
    if (Test-Path $SimulatorScript) {
      Write-Host "Running paper simulator for stage $Stage..."
      & $Python $SimulatorScript --project-root $Root --sim-root (Join-Path $Root "paper-sim") decide --stage $Stage --date $Date
    } else {
      Write-Host "Paper simulator script not found: $SimulatorScript"
    }
    # After late_confirm, auto-generate asset update report from latest sim data
    if ($Stage -eq "late_confirm") {
      $AssetReportScript = Join-Path $Root "paper-sim\scripts\gen_asset_report.py"
      if (Test-Path $AssetReportScript) {
        Write-Host "Generating asset update report..."
        & $Python $AssetReportScript
      }
    }
  }
}

if ($Stage -eq "review_fill") {
  $DbPath = Join-Path $Root "data\watchpool\watchpool.sqlite"
  $logs = Get-ChildItem -Path $Root -Filter "watchpool_validation_log*.csv" | Where-Object { $_.Name -notlike "*filled*" }
  foreach ($log in $logs) {
    $out = Join-Path $Root ($log.BaseName + "_filled.csv")
    & $Python "$Skill\scripts\fill_review_outcomes.py" --input $log.FullName --output $out --as-of (Get-Date -Format "yyyy-MM-dd") --auto-benchmark
    & $Python "$Skill\scripts\watchpool_db.py" import-log --db $DbPath --csv $out
  }
  & $Python "$Skill\scripts\watchpool_db.py" dashboard --db $DbPath --output (Join-Path $DashboardReports "watchpool_dashboard.html")
  & $Python "$Skill\scripts\audit_strategy.py" --db $DbPath --output (Join-Path $DashboardReports "strategy_audit.json") --html-output (Join-Path $DashboardReports "strategy_audit.html")
  $LightReportScript = Join-Path $Root "scripts\render_watchpool_light.py"
  if (Test-Path $LightReportScript) {
    & $Python $LightReportScript --root $Root post-close
  } else {
    Write-Host "Light report script not found: $LightReportScript"
  }
}

if ($Stage -eq "health") {
  $latest = Get-ChildItem -Path (Join-Path $Root "data\watchpool") -Directory |
    Where-Object { $_.Name -notlike "*_health" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if ($null -ne $latest) {
    & $Python "$Skill\scripts\monitor_data_health.py" --snapshot-dir $latest.FullName --output (Join-Path $latest.FullName "data_health.json") --html-output (Join-Path $HealthReports "latest_data_health.html")
  }
}

if ($Stage -eq "audit") {
  $DbPath = Join-Path $Root "data\watchpool\watchpool.sqlite"
  & $Python "$Skill\scripts\audit_strategy.py" --db $DbPath --output (Join-Path $DashboardReports "strategy_audit.json") --html-output (Join-Path $DashboardReports "strategy_audit.html")
  $LightReportScript = Join-Path $Root "scripts\render_watchpool_light.py"
  if (Test-Path $LightReportScript) {
    & $Python $LightReportScript --root $Root post-close
  } else {
    Write-Host "Light report script not found: $LightReportScript"
  }
}



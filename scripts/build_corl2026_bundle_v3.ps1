param(
    [string]$InputRoot = "D:\codex\grasp-benchmark\artifacts\runs",
    [string]$OutputDir = "D:\codex\grasp-benchmark\artifacts\reports\corl_paper_bundle_v3_latest",
    [string]$OfficialTrackBReference = "D:\codex\grasp-benchmark\artifacts\official_sim\20260402_231726_em14_full\summary.json",
    [int]$MinCalTrials = 30,
    [int]$MinStressTrials = 30,
    [int]$MinNativeTrials = 30
)

$ErrorActionPreference = "Stop"

function Get-LatestRunId {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Pattern,
        [int]$MinTrials = 1,
        [string]$ExcludePattern = ""
    )
    $candidates = Get-ChildItem $InputRoot -Directory -Filter $Pattern | Sort-Object LastWriteTime -Descending
    $eligible = foreach ($candidate in $candidates) {
        if ($ExcludePattern -and $candidate.Name -like $ExcludePattern) {
            continue
        }
        $resultsPath = Join-Path $candidate.FullName "results.csv"
        if (-not (Test-Path $resultsPath)) {
            continue
        }
        $trialCount = 0
        $summaryPath = Join-Path $candidate.FullName "summary.json"
        if (Test-Path $summaryPath) {
            try {
                $summary = Get-Content $summaryPath -Raw | ConvertFrom-Json
                if ($summary.trial_count) {
                    $trialCount = [int]$summary.trial_count
                }
            } catch {
            }
        }
        if ($trialCount -le 0) {
            $lineCount = (Get-Content $resultsPath | Measure-Object -Line).Lines
            $trialCount = [Math]::Max(0, $lineCount - 1)
        }
        if ($trialCount -lt $MinTrials) {
            continue
        }
        $candidate
    }
    if (-not $eligible) {
        return $null
    }
    return $eligible[0].Name
}

function Get-LatestAuditSummary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Prefix
    )
    $auditRoot = "D:\codex\grasp-benchmark\artifacts\audits"
    $candidates = Get-ChildItem $auditRoot -Directory |
        Where-Object { $_.Name -like "$Prefix*" -and (Test-Path (Join-Path $_.FullName "summary.json")) } |
        Sort-Object LastWriteTime -Descending
    if (-not $candidates) {
        return $null
    }
    return (Join-Path $candidates[0].FullName "summary.json")
}

$calRuns = @(
    Get-LatestRunId -Pattern "*graspvla_track_a_cal_v3_shared_sim" -MinTrials $MinCalTrials
    Get-LatestRunId -Pattern "*cgn_track_a_cal_v3_shared_sim" -MinTrials $MinCalTrials
) | Where-Object { $_ }

$stressRuns = @(
    Get-LatestRunId -Pattern "*graspvla_track_a_stress_v3_shared_sim" -MinTrials $MinStressTrials
    Get-LatestRunId -Pattern "*cgn_track_a_stress_v3_shared_sim" -MinTrials $MinStressTrials
) | Where-Object { $_ }

$nativeRuns = @(
    Get-LatestRunId -Pattern "*cgn_track_b_cgn_native_v1*" -MinTrials $MinNativeTrials -ExcludePattern "*single_scene*"
) | Where-Object { $_ }

$protocolSummary = Get-LatestAuditSummary -Prefix "*_graspvla_protocol_and_transfer_suite_v1"
if (-not $protocolSummary) {
    $protocolSummary = Get-LatestAuditSummary -Prefix "*_graspvla_protocol_probe_v2"
}
$cgnBottleneckSummary = Get-LatestAuditSummary -Prefix "*_cgn_bottleneck_v1"
$alignmentSummary = Get-LatestAuditSummary -Prefix "*_graspvla_official_alignment"

$args = @(
    "-m", "grasp_benchmark.report.paper_bundle",
    "--input", $InputRoot,
    "--output-dir", $OutputDir,
    "--execution-mode", "shared_track_a_sim",
    "--track-b-reference", $OfficialTrackBReference
)

if ($calRuns.Count -gt 0) {
    $args += @("--track-a-cal-parent-run-id", ($calRuns -join ","))
} else {
    $args += @("--track-a-cal-parent-run-id", "__none__")
}
if ($stressRuns.Count -gt 0) {
    $args += @("--track-a-stress-parent-run-id", ($stressRuns -join ","))
} else {
    $args += @("--track-a-stress-parent-run-id", "__none__")
}
if ($nativeRuns.Count -gt 0) {
    $args += @("--track-b-native-parent-run-id", ($nativeRuns -join ","))
} else {
    $args += @("--track-b-native-parent-run-id", "__none__")
}
if ($protocolSummary) {
    $args += @("--protocol-probe-summary", $protocolSummary)
}
if ($cgnBottleneckSummary) {
    $args += @("--cgn-bottleneck-summary", $cgnBottleneckSummary)
}
if ($alignmentSummary) {
    $args += @("--alignment-summary", $alignmentSummary)
}

Write-Host "Building CoRL v3 paper bundle..." -ForegroundColor Cyan
Write-Host "Track A-Cal runs: $($calRuns -join ', ')" -ForegroundColor DarkGray
Write-Host "Track A-Stress runs: $($stressRuns -join ', ')" -ForegroundColor DarkGray
Write-Host "Track B native appendix runs: $($nativeRuns -join ', ')" -ForegroundColor DarkGray
if ($protocolSummary) { Write-Host "Protocol summary: $protocolSummary" -ForegroundColor DarkGray }
if ($cgnBottleneckSummary) { Write-Host "CGN bottleneck summary: $cgnBottleneckSummary" -ForegroundColor DarkGray }
if ($alignmentSummary) { Write-Host "Alignment summary: $alignmentSummary" -ForegroundColor DarkGray }

$env:PYTHONPATH = "D:\codex\grasp-benchmark\src"
python @args
if ($LASTEXITCODE -ne 0) {
    throw "paper_bundle.py exited with code $LASTEXITCODE"
}
if (-not (Test-Path $OutputDir)) {
    throw "Expected bundle output directory was not created: $OutputDir"
}

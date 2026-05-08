param(
    [string]$InputRoot = "",
    [string]$OutputDir = "",
    [string]$OfficialTrackBReference = "",
    [int]$MinCalTrials = 30,
    [int]$MinStressTrials = 30,
    [int]$MinInstructionTrials = 20,
    [int]$MinSim2RealTrials = 20,
    [int]$MinPhase2Trials = 12,
    [int]$MinNativeTrials = 30
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot

if (-not $InputRoot) {
    $InputRoot = Join-Path $repoRoot "artifacts\runs"
}
if (-not $OutputDir) {
    $OutputDir = Join-Path $repoRoot "artifacts\reports\corl_paper_bundle_v3_latest"
}
if (-not $OfficialTrackBReference) {
    $OfficialTrackBReference = Join-Path $repoRoot "artifacts\official_sim\20260402_231726_lakeshore_full\summary.json"
}

function Get-LatestRunId {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Pattern,
        [int]$MinTrials = 1,
        [string]$ExcludePattern = ""
    )
    if (-not (Test-Path $InputRoot)) {
        return $null
    }
    function Get-RunTrialCount {
        param(
            [Parameter(Mandatory = $true)]
            [System.IO.DirectoryInfo]$Candidate
        )
        $summaryPath = Join-Path $Candidate.FullName "summary.json"
        if (Test-Path $summaryPath) {
            try {
                $summary = Get-Content $summaryPath -Raw | ConvertFrom-Json
                if ($summary.trial_count) {
                    return [int]$summary.trial_count
                }
            } catch {
            }
        }
        $resultsPath = Join-Path $Candidate.FullName "results.csv"
        if (Test-Path $resultsPath) {
            $lineCount = (Get-Content $resultsPath | Measure-Object -Line).Lines
            return [Math]::Max(0, $lineCount - 1)
        }
        $trialCount = 0
        $shardsRoot = Join-Path $Candidate.FullName "shards"
        if (Test-Path $shardsRoot) {
            $shardResults = Get-ChildItem $shardsRoot -Recurse -Filter "results.csv"
            foreach ($path in $shardResults) {
                $lineCount = (Get-Content $path.FullName | Measure-Object -Line).Lines
                $trialCount += [Math]::Max(0, $lineCount - 1)
            }
        }
        return $trialCount
    }

    $candidates = Get-ChildItem $InputRoot -Directory -Filter $Pattern | Sort-Object LastWriteTime -Descending
    $eligible = foreach ($candidate in $candidates) {
        if ($ExcludePattern -and $candidate.Name -like $ExcludePattern) {
            continue
        }
        $trialCount = Get-RunTrialCount -Candidate $candidate
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
    $auditRoot = Join-Path $repoRoot "artifacts\audits"
    if (-not (Test-Path $auditRoot)) {
        return $null
    }
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
    Get-LatestRunId -Pattern "*graspvla_track_a_stress_v4_shared_sim" -MinTrials $MinStressTrials
    Get-LatestRunId -Pattern "*cgn_track_a_stress_v4_shared_sim" -MinTrials $MinStressTrials
) | Where-Object { $_ }

$instructionRuns = @(
    Get-LatestRunId -Pattern "*graspvla_instruction_robustness_v2_shared_sim" -MinTrials $MinInstructionTrials
    Get-LatestRunId -Pattern "*cgn_instruction_robustness_v2_shared_sim" -MinTrials $MinInstructionTrials
) | Where-Object { $_ }

$sim2realRuns = @(
    Get-LatestRunId -Pattern "*graspvla_sim2real_proxy_v2_shared_sim" -MinTrials $MinSim2RealTrials
    Get-LatestRunId -Pattern "*cgn_sim2real_proxy_v2_shared_sim" -MinTrials $MinSim2RealTrials
) | Where-Object { $_ }

$phase2Runs = @(
    Get-LatestRunId -Pattern "*graspvla_phase2_pilot_v1_shared_sim" -MinTrials $MinPhase2Trials
    Get-LatestRunId -Pattern "*cgn_phase2_pilot_v1_shared_sim" -MinTrials $MinPhase2Trials
) | Where-Object { $_ }

$nativeRuns = @(
    Get-LatestRunId -Pattern "*cgn_track_b_cgn_official_depth_segmap_v1*" -MinTrials $MinNativeTrials -ExcludePattern "*single_scene*"
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
if ($instructionRuns.Count -gt 0) {
    $args += @("--instruction-parent-run-id", ($instructionRuns -join ","))
} else {
    $args += @("--instruction-parent-run-id", "__none__")
}
if ($sim2realRuns.Count -gt 0) {
    $args += @("--sim2real-parent-run-id", ($sim2realRuns -join ","))
} else {
    $args += @("--sim2real-parent-run-id", "__none__")
}
if ($phase2Runs.Count -gt 0) {
    $args += @("--phase2-parent-run-id", ($phase2Runs -join ","))
} else {
    $args += @("--phase2-parent-run-id", "__none__")
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
Write-Host "Main Shared Grasping Benchmark runs: $($calRuns -join ', ')" -ForegroundColor DarkGray
Write-Host "Hard Shared Grasping Stress Test runs: $($stressRuns -join ', ')" -ForegroundColor DarkGray
Write-Host "Instruction Robustness runs: $($instructionRuns -join ', ')" -ForegroundColor DarkGray
Write-Host "Sim-to-Real Proxy runs: $($sim2realRuns -join ', ')" -ForegroundColor DarkGray
Write-Host "Task-Oriented Grasping Pilot runs: $($phase2Runs -join ', ')" -ForegroundColor DarkGray
Write-Host "Track B native appendix runs: $($nativeRuns -join ', ')" -ForegroundColor DarkGray
if ($protocolSummary) { Write-Host "Protocol summary: $protocolSummary" -ForegroundColor DarkGray }
if ($cgnBottleneckSummary) { Write-Host "CGN bottleneck summary: $cgnBottleneckSummary" -ForegroundColor DarkGray }
if ($alignmentSummary) { Write-Host "Alignment summary: $alignmentSummary" -ForegroundColor DarkGray }

$env:PYTHONPATH = Join-Path $repoRoot "src"
python @args
if ($LASTEXITCODE -ne 0) {
    throw "paper_bundle.py exited with code $LASTEXITCODE"
}
if (-not (Test-Path $OutputDir)) {
    throw "Expected bundle output directory was not created: $OutputDir"
}

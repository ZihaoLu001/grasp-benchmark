param(
    [Parameter(Mandatory = $true)]
    [string]$TrackACalParentRunIds,
    [Parameter(Mandatory = $true)]
    [string]$TrackAStressParentRunIds,
    [Parameter(Mandatory = $true)]
    [string]$InstructionParentRunIds,
    [Parameter(Mandatory = $true)]
    [string]$Sim2RealParentRunIds,
    [Parameter(Mandatory = $true)]
    [string]$Phase2ParentRunIds,
    [Parameter(Mandatory = $true)]
    [string]$TrackBNativeParentRunIds,
    [string]$InputRoot = "",
    [string]$OutputDir = "",
    [string]$OfficialTrackBReference = "",
    [string]$ProtocolProbeSummary = "",
    [string]$CgnBottleneckSummary = "",
    [string]$AlignmentSummary = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot

if (-not $InputRoot) {
    $InputRoot = Join-Path $repoRoot "artifacts\runs"
}
if (-not $OutputDir) {
    $OutputDir = Join-Path $repoRoot "artifacts\reports\corl2026_submission_bundle_latest"
}
if (-not $OfficialTrackBReference) {
    $OfficialTrackBReference = Join-Path $repoRoot "artifacts\official_sim\20260402_231726_em14_full\summary.json"
}

$args = @(
    "-m", "grasp_benchmark.report.paper_bundle",
    "--input", $InputRoot,
    "--output-dir", $OutputDir,
    "--execution-mode", "shared_track_a_sim",
    "--submission-mode",
    "--track-a-cal-parent-run-id", $TrackACalParentRunIds,
    "--track-a-stress-parent-run-id", $TrackAStressParentRunIds,
    "--instruction-parent-run-id", $InstructionParentRunIds,
    "--sim2real-parent-run-id", $Sim2RealParentRunIds,
    "--phase2-parent-run-id", $Phase2ParentRunIds,
    "--track-b-native-parent-run-id", $TrackBNativeParentRunIds,
    "--track-b-reference", $OfficialTrackBReference
)

if ($ProtocolProbeSummary) {
    $args += @("--protocol-probe-summary", $ProtocolProbeSummary)
}
if ($CgnBottleneckSummary) {
    $args += @("--cgn-bottleneck-summary", $CgnBottleneckSummary)
}
if ($AlignmentSummary) {
    $args += @("--alignment-summary", $AlignmentSummary)
}

Write-Host "Building CoRL 2026 submission bundle..." -ForegroundColor Cyan
Write-Host "Main Shared Grasping Benchmark: $TrackACalParentRunIds" -ForegroundColor DarkGray
Write-Host "Hard Shared Grasping Stress Test: $TrackAStressParentRunIds" -ForegroundColor DarkGray
Write-Host "Instruction Robustness: $InstructionParentRunIds" -ForegroundColor DarkGray
Write-Host "Sim-to-Real Proxy: $Sim2RealParentRunIds" -ForegroundColor DarkGray
Write-Host "Task-Oriented Grasping Pilot: $Phase2ParentRunIds" -ForegroundColor DarkGray
Write-Host "CGN Native-Reference Appendix: $TrackBNativeParentRunIds" -ForegroundColor DarkGray
if ($ProtocolProbeSummary) { Write-Host "Protocol probe: $ProtocolProbeSummary" -ForegroundColor DarkGray }
if ($CgnBottleneckSummary) { Write-Host "CGN bottleneck: $CgnBottleneckSummary" -ForegroundColor DarkGray }
if ($AlignmentSummary) { Write-Host "Alignment summary: $AlignmentSummary" -ForegroundColor DarkGray }

$env:PYTHONPATH = Join-Path $repoRoot "src"
python @args
if ($LASTEXITCODE -ne 0) {
    throw "paper_bundle.py exited with code $LASTEXITCODE"
}
if (-not (Test-Path $OutputDir)) {
    throw "Expected bundle output directory was not created: $OutputDir"
}

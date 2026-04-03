param(
    [string]$Input = "artifacts\\runs",
    [string]$OutputDir = "artifacts\\reports\\latest",
    [string]$TrackBReference = "artifacts\\official_sim\\20260402_231726_em14_full\\summary.json",
    [string]$TrackAStressReference = "artifacts\\reports\\track_a_compare_graspvla_cgn_v2_latest\\report.json",
    [string]$DiagnosticReport = "artifacts\\diagnostics\\20260403_175506_graspvla_track_a_diagnostics\\report.md"
)

$args = @("-m", "grasp_benchmark.report.aggregate", "--input", $Input, "--output-dir", $OutputDir)
if (Test-Path $TrackBReference) {
    $args += @("--track-b-reference", $TrackBReference)
}
if (Test-Path $TrackAStressReference) {
    $args += @("--track-a-stress-reference", $TrackAStressReference)
}
if (Test-Path $DiagnosticReport) {
    $args += @("--diagnostic-report", $DiagnosticReport)
}
python @args

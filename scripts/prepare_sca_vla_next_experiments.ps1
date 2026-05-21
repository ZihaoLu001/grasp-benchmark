param(
    [string]$Config = "configs\sca_vla\next_experiments.yaml",
    [string]$OutputDir = "",
    [string]$Suites = "",
    [switch]$NoSeqRl,
    [switch]$NoOfflineCollect,
    [switch]$NoPolicyAnchor,
    [switch]$NoCheckpointPrep
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $repoRoot "src"

$argsList = @(
    "-m", "grasp_benchmark.vla_continual.prepare_next_experiments",
    "--config", (Join-Path $repoRoot $Config)
)

if ($OutputDir -ne "") {
    $argsList += @("--output-dir", $OutputDir)
}
if ($Suites -ne "") {
    $argsList += @("--suites", $Suites)
}
if ($NoSeqRl) {
    $argsList += "--no-seq-rl"
}
if ($NoOfflineCollect) {
    $argsList += "--no-offline-collect"
}
if ($NoPolicyAnchor) {
    $argsList += "--no-policy-anchor"
}
if ($NoCheckpointPrep) {
    $argsList += "--no-checkpoint-prep"
}

python @argsList

param(
    [Parameter(Mandatory = $true)][string]$Method,
    [string]$TaskSet = "track_a_cal_v3",
    [string]$Node = "",
    [string]$ClusterConfig = "",
    [switch]$DryRun,
    [switch]$SmokeOnly
)

$args = @("-m", "grasp_benchmark.run.sim", "--method", $Method, "--task-set", $TaskSet)
if ($Node) {
    $args += @("--node", $Node)
}
if ($ClusterConfig) {
    $args += @("--cluster-config", $ClusterConfig)
}
if ($DryRun) {
    $args += "--dry-run"
}
if ($SmokeOnly) {
    $args += "--smoke-only"
}
python @args

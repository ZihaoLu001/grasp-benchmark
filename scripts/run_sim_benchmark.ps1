param(
    [Parameter(Mandatory = $true)][string]$Method,
    [string]$TaskSet = "track_a_cal_v1",
    [switch]$DryRun,
    [switch]$SmokeOnly
)

$args = @("-m", "grasp_benchmark.run.sim", "--method", $Method, "--task-set", $TaskSet)
if ($DryRun) {
    $args += "--dry-run"
}
if ($SmokeOnly) {
    $args += "--smoke-only"
}
python @args

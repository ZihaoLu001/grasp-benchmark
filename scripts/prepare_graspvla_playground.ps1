param(
    [string]$Node = "em14",
    [switch]$BootstrapEnv
)

$args = @("-m", "grasp_benchmark.prepare_graspvla_playground", "--node", $Node)
if ($BootstrapEnv) {
    $args += "--bootstrap-env"
}

python @args

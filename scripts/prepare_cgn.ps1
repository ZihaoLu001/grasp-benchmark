param(
    [string]$Node = "em14",
    [switch]$BootstrapLegacyEnv,
    [switch]$CompileTfOps
)

$args = @("-m", "grasp_benchmark.prepare_cgn", "--node", $Node)
if ($BootstrapLegacyEnv) {
    $args += "--bootstrap-legacy-env"
}
if ($CompileTfOps) {
    $args += "--compile-tf-ops"
}
python @args

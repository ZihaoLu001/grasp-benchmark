param(
    [Parameter(Mandatory = $true)][string]$Method,
    [string]$Node = "",
    [switch]$IncludePlayground,
    [switch]$DryRun
)

$args = @("-m", "grasp_benchmark.install_remote", "--method", $Method)
if ($Node) {
    $args += @("--node", $Node)
}
if ($IncludePlayground) {
    $args += "--include-playground"
}
if ($DryRun) {
    $args += "--dry-run"
}
python @args

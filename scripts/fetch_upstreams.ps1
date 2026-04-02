param(
    [string]$Only = "",
    [switch]$Update
)

$args = @("-m", "grasp_benchmark.fetch_upstreams")
if ($Only) {
    $args += @("--only", $Only)
}
if ($Update) {
    $args += "--update"
}
python @args


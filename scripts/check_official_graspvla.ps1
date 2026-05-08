param(
    [string]$Node = "lakeshore",
    [string]$ServerHost = "127.0.0.1",
    [int]$Port = 6666,
    [int]$Timeout = 5,
    [switch]$SkipOfflineTest
)

$args = @("-m", "grasp_benchmark.official_graspvla_checks", "--node", $Node, "--host", $ServerHost, "--port", $Port, "--timeout", $Timeout)
if ($SkipOfflineTest) {
    $args += "--skip-offline-test"
}

python @args

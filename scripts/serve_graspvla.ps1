param(
    [string]$Node = "em14",
    [switch]$DownloadModel
)

$args = @("-m", "grasp_benchmark.serve.graspvla", "--node", $Node)
if ($DownloadModel) {
    $args += "--download-model"
}
python @args


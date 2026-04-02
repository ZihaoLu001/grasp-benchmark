param(
    [string]$Node = "em14",
    [switch]$DownloadModel,
    [switch]$InstallDeps,
    [switch]$IncludePlayground,
    [switch]$SkipValidate
)

$args = @("-m", "grasp_benchmark.serve.graspvla", "--node", $Node)
if ($DownloadModel) {
    $args += "--download-model"
}
if ($InstallDeps) {
    $args += "--install-deps"
}
if ($IncludePlayground) {
    $args += "--include-playground"
}
if ($SkipValidate) {
    $args += "--skip-validate"
}
python @args

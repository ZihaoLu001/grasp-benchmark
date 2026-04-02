param(
    [string]$Node = "em14",
    [string]$RemoteRoot = "/datasets/ss/current/zihao/grasp-benchmark",
    [string]$MiniforgeRoot = "/datasets/ss/current/zihao/miniforge3",
    [string]$CondaEnvsDir = "/datasets/ss/current/zihao/conda/envs",
    [string]$CondaPkgsDir = "/datasets/ss/current/zihao/conda/pkgs"
)

$repoRoot = Split-Path $PSScriptRoot -Parent
$archivePath = Join-Path $env:TEMP "grasp-benchmark-bootstrap.tar"
$remoteArchive = "/tmp/grasp-benchmark-bootstrap.tar"

git -C $repoRoot archive --format=tar -o $archivePath HEAD
scp $archivePath "${Node}:$remoteArchive"
ssh $Node "rm -rf '$RemoteRoot' && mkdir -p '$RemoteRoot' && tar -xf '$remoteArchive' -C '$RemoteRoot'"
ssh $Node "bash '$RemoteRoot/cluster/install_miniforge.sh' '$MiniforgeRoot' '$CondaEnvsDir' '$CondaPkgsDir'"
ssh $Node "bash '$RemoteRoot/cluster/create_envs.sh' '$MiniforgeRoot' '$RemoteRoot' '$CondaEnvsDir'"
Remove-Item -LiteralPath $archivePath -ErrorAction SilentlyContinue

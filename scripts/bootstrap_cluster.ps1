param(
    [string]$Node = "em14",
    [string]$RemoteRoot = "/datasets/ss/current/zihao/grasp-benchmark",
    [string]$MiniforgeRoot = "/datasets/ss/current/zihao/miniforge3",
    [string]$CondaEnvsDir = "/datasets/ss/current/zihao/conda/envs",
    [string]$CondaPkgsDir = "/datasets/ss/current/zihao/conda/pkgs"
)

$repoRoot = Split-Path $PSScriptRoot -Parent
$archivePath = Join-Path $env:TEMP "grasp-benchmark-bootstrap.tar"
$metadataPath = Join-Path $env:TEMP "grasp-benchmark-sync.json"
$remoteArchive = "/tmp/grasp-benchmark-bootstrap.tar"
$remoteMetadata = "/tmp/grasp-benchmark-sync.json"

$commit = (git -C $repoRoot rev-parse HEAD).Trim()
$branch = (git -C $repoRoot rev-parse --abbrev-ref HEAD).Trim()
$metadata = @{
    repository = "ZihaoLu001/grasp-benchmark"
    commit = $commit
    branch = $branch
    synced_at = (Get-Date).ToUniversalTime().ToString("o")
    sync_source = "git_archive"
}
$metadata | ConvertTo-Json | Set-Content -Path $metadataPath -Encoding utf8

git -C $repoRoot archive --format=tar -o $archivePath HEAD
scp $archivePath "${Node}:$remoteArchive"
scp $metadataPath "${Node}:$remoteMetadata"

$remoteSync = @"
set -euo pipefail
tmp_dir="\$(mktemp -d /tmp/grasp-benchmark-sync.XXXXXX)"
trap 'rm -rf "\${tmp_dir}"' EXIT
mkdir -p "$RemoteRoot"
tar -xf "$remoteArchive" -C "\${tmp_dir}"
mkdir -p "$RemoteRoot/artifacts" "$RemoteRoot/third_party" "$RemoteRoot/cluster"
cp -a "\${tmp_dir}/." "$RemoteRoot/"
cp "$remoteMetadata" "$RemoteRoot/.grasp-benchmark-sync.json"
"@

$remoteSync | ssh $Node /bin/bash
ssh $Node "bash '$RemoteRoot/cluster/install_miniforge.sh' '$MiniforgeRoot' '$CondaEnvsDir' '$CondaPkgsDir'"
ssh $Node "bash '$RemoteRoot/cluster/create_envs.sh' '$MiniforgeRoot' '$RemoteRoot' '$CondaEnvsDir'"

Remove-Item -LiteralPath $archivePath -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $metadataPath -ErrorAction SilentlyContinue

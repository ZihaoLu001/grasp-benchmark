param(
    [string]$Node = "em14",
    [string]$ClusterConfig = "default",
    [string]$RemoteRoot = "/datasets/ss/current/zihao/grasp-benchmark",
    [string]$MiniforgeRoot = "/datasets/ss/current/zihao/miniforge3",
    [string]$CondaEnvsDir = "/datasets/ss/current/zihao/conda/envs",
    [string]$CondaPkgsDir = "/datasets/ss/current/zihao/conda/pkgs",
    [switch]$SkipEnvRefresh
)

$repoRoot = Split-Path $PSScriptRoot -Parent
if ($ClusterConfig) {
    $clusterJson = @'
import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[2])
sys.path.insert(0, str(repo_root / "src"))
from grasp_benchmark.config import load_cluster_config

config = load_cluster_config(sys.argv[1])
print(json.dumps(config))
'@ | python - $ClusterConfig $repoRoot
    $cluster = $clusterJson | ConvertFrom-Json
    $RemoteRoot = $cluster.remote_root
    $MiniforgeRoot = $cluster.miniforge_root
    $CondaEnvsDir = $cluster.conda_envs_dir
    $CondaPkgsDir = $cluster.conda_pkgs_dir
}
$syncToken = [guid]::NewGuid().ToString("N")
$archivePath = Join-Path $env:TEMP "grasp-benchmark-bootstrap-$syncToken.tar"
$metadataPath = Join-Path $env:TEMP "grasp-benchmark-sync-$syncToken.json"
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
$metadataJson = $metadata | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($metadataPath, $metadataJson, [System.Text.UTF8Encoding]::new($false))

git -C $repoRoot archive --format=tar -o $archivePath HEAD
scp $archivePath "${Node}:$remoteArchive"
scp $metadataPath "${Node}:$remoteMetadata"

$remoteSync = @'
set -euo pipefail
tmp_dir="$(mktemp -d /tmp/grasp-benchmark-sync.XXXXXX)"
trap 'rm -rf "${{tmp_dir}}"' EXIT
mkdir -p "{0}"
tar -xf "{1}" -C "${{tmp_dir}}"
mkdir -p "{0}/artifacts" "{0}/third_party" "{0}/cluster"
cp -a "${{tmp_dir}}/." "{0}/"
cp "{2}" "{0}/.grasp-benchmark-sync.json"
'@ -f $RemoteRoot, $remoteArchive, $remoteMetadata

$remoteSyncBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(($remoteSync -replace "`r`n", "`n")))
ssh $Node "printf '%s' '$remoteSyncBase64' | base64 -d | /bin/bash"
if (-not $SkipEnvRefresh) {
    ssh $Node "bash '$RemoteRoot/cluster/install_miniforge.sh' '$MiniforgeRoot' '$CondaEnvsDir' '$CondaPkgsDir'"
    ssh $Node "bash '$RemoteRoot/cluster/create_envs.sh' '$MiniforgeRoot' '$RemoteRoot' '$CondaEnvsDir'"
}

Remove-Item -LiteralPath $archivePath -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $metadataPath -ErrorAction SilentlyContinue

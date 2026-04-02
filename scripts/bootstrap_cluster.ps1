param(
    [string]$Node = "em14",
    [string]$RepoUrl = "git@github.com:ZihaoLu001/grasp-benchmark.git",
    [string]$RemoteRoot = "/datasets/ss/current/zihao/grasp-benchmark"
)

$scriptPath = Join-Path $PSScriptRoot "..\\cluster\\bootstrap_project.sh"
$script = Get-Content -Raw $scriptPath
$script | ssh $Node "/bin/bash -s -- $RepoUrl $RemoteRoot"


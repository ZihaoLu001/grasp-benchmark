param(
    [string]$Node = "em14",
    [string]$SensorConfig = "track_a_dual_realsense",
    [switch]$SkipBootstrap,
    [switch]$SkipServerValidate,
    [switch]$SkipProtocolAudit
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot

function Invoke-Step {
    param(
        [string]$Label,
        [scriptblock]$Action
    )
    Write-Host ""
    Write-Host "==> $Label" -ForegroundColor Cyan
    & $Action
}

if (-not $SkipBootstrap) {
    Invoke-Step -Label "Sync repo and env bootstrap on $Node" -Action {
        & "$repoRoot\scripts\bootstrap_cluster.ps1" -Node $Node
    }
}

if (-not $SkipServerValidate) {
    Invoke-Step -Label "Validate remote GraspVLA server on $Node" -Action {
        @'
from grasp_benchmark.config import load_named_config
from grasp_benchmark.serve.graspvla import _validate_remote_server

cluster_config = load_named_config("cluster", "default")
method_config = load_named_config("methods", "graspvla")
ok, payload = _validate_remote_server(
    host="__NODE__",
    cluster_config=cluster_config,
    method_config=method_config,
    port=int(method_config["server"]["port"]),
    timeout_s=5,
    retries=3,
    retry_sleep_s=2,
)
print({"ok": ok, "payload": payload})
if not ok:
    raise SystemExit(1)
'@.Replace("__NODE__", $Node) | python -
    }
}

Invoke-Step -Label "Run GraspVLA Track A-Cal v3" -Action {
    python -m grasp_benchmark.run.sim `
        --method graspvla `
        --task-set track_a_cal_v3 `
        --sensor-config $SensorConfig `
        --available-nodes "$repoRoot\artifacts\preflight\available_nodes.json" `
        --node $Node
}

Invoke-Step -Label "Run GraspVLA Track A-Stress v3" -Action {
    python -m grasp_benchmark.run.sim `
        --method graspvla `
        --task-set track_a_stress_v3 `
        --sensor-config $SensorConfig `
        --available-nodes "$repoRoot\artifacts\preflight\available_nodes.json" `
        --node $Node
}

if (-not $SkipProtocolAudit) {
    Invoke-Step -Label "Run GraspVLA protocol-and-transfer suite v1" -Action {
        python -m grasp_benchmark.audit.graspvla_protocol_and_transfer_suite_v1 `
            --node $Node `
            --sensor-config $SensorConfig
    }
}

Write-Host ""
Write-Host "CoRL 2026 GraspVLA simulator suite completed." -ForegroundColor Green

# GraspVLA Official Runbook

## Goal

This runbook is the shortest path from our current cluster setup to something we can show in a meeting:

- the official GraspVLA model server is up
- the official validation entrypoint returns a valid response
- the official offline test can produce a visualization
- our benchmark wrapper can compare GraspVLA against modular baselines on the same Track A interface

## Public Repositories

- `third_party/upstreams/GraspVLA`
  Model server and offline test.
- `third_party/upstreams/GraspVLA-playground`
  Simulation playground, LIBERO evaluation, and `validate_server.py`.
- `third_party/upstreams/GraspVLA-real-world-controller`
  Franka plus dual-camera real-world client.

## Current Cluster Status

- Primary node for GraspVLA server: `em14`
- Remote project root:
  `/datasets/ss/current/zihao/grasp-benchmark`
- Shared Miniforge root:
  `/datasets/ss/current/zihao/miniforge3`
- Core environment:
  `/datasets/ss/current/zihao/conda/envs/gb-core`
- Latest synced commit should match `.grasp-benchmark-sync.json`

## Official Server Commands

From the remote node:

```bash
source /datasets/ss/current/zihao/miniforge3/etc/profile.d/conda.sh
conda activate /datasets/ss/current/zihao/conda/envs/gb-core
cd /datasets/ss/current/zihao/grasp-benchmark/third_party/upstreams/GraspVLA
python -u -m vla_network.scripts.serve \
  --path /path/to/model.safetensors \
  --port 6666 \
  --compile
```

## Official Validation Entry Points

### Playground validation

```bash
source /datasets/ss/current/zihao/miniforge3/etc/profile.d/conda.sh
conda activate /datasets/ss/current/zihao/conda/envs/gb-core
cd /datasets/ss/current/zihao/grasp-benchmark/third_party/upstreams/GraspVLA-playground
python validate_server.py --host 127.0.0.1 --port 6666 --timeout 5
```

### Offline test from the main repo

```bash
source /datasets/ss/current/zihao/miniforge3/etc/profile.d/conda.sh
conda activate /datasets/ss/current/zihao/conda/envs/gb-core
cd /datasets/ss/current/zihao/grasp-benchmark/third_party/upstreams/GraspVLA
MPLBACKEND=Agg python -u -m vla_network.scripts.offline_test --port 6666
```

This writes a visualization under `third_party/upstreams/GraspVLA/visualization/`.

## Benchmark Entry Points

### GraspVLA smoke

```powershell
python -m grasp_benchmark.run.sim --method graspvla --task-set track_a_v1 --node em14 --max-trials 1
```

### Contact-GraspNet smoke

```powershell
python -m grasp_benchmark.prepare_cgn --node em14
python -m grasp_benchmark.run.sim --method cgn --task-set track_a_v1 --node em14 --max-trials 1
```

### AnyGrasp readiness

```powershell
python -m grasp_benchmark.prepare_anygrasp --node em14
python -m grasp_benchmark.run.sim --method anygrasp --task-set track_a_v1 --node em14 --max-trials 1
```

If AnyGrasp still fails, check whether `license/licenseCfg.json` is present under:

`/datasets/ss/current/zihao/grasp-benchmark/third_party/upstreams/anygrasp_sdk/grasp_detection/license/`

## What We Have Confirmed So Far

- GraspVLA model server is live on `em14:6666`.
- Official `validate_server.py` succeeds.
- Official `offline_test.py` succeeds and produces a visualization artifact.
- GraspVLA benchmark smoke succeeds.
- Contact-GraspNet legacy runtime and checkpoint are ready, and smoke succeeds.
- AnyGrasp setup is ready up to the license boundary.

## Latest Verified Artifact

- Local artifact:
  `artifacts/official/20260402_194109_em14_graspvla_checks/summary.json`
- Visualization:
  `artifacts/official/20260402_194109_em14_graspvla_checks/offline_test_visualization.png`

## Next Week Plan

- Move from one-trial smoke runs to a small Track A batch for GraspVLA and Contact-GraspNet.
- Fetch the AnyGrasp license and complete the third baseline.
- Start packaging plots and failure videos for the benchmark meeting.

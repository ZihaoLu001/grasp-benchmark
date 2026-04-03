# GraspVLA Official Runbook

## Goal

This runbook is the shortest path from our current cluster setup to something we can show in a meeting:

- the official GraspVLA model server is up
- the official validation entrypoint returns a valid response
- the official offline test can produce a visualization
- our benchmark wrapper can compare GraspVLA against modular baselines on the same Track A interface

Important reporting rule:

- official GraspVLA simulation artifacts are `Track B / native best-case`
- benchmark-wrapper Track A runs are the only artifacts that should support the final fairness claim

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
- Official simulation environment:
  `/datasets/ss/current/zihao/conda/envs/gb-graspvla-sim`
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

This path is the shared Track A benchmark wrapper, not the official method-native simulation runner.

### Dedicated official simulation environment

```powershell
python -m grasp_benchmark.prepare_graspvla_playground --node em14 --bootstrap-env
```

### Official playground plus LIBERO complete batch

```powershell
python -m grasp_benchmark.official_graspvla_sim --node em14 --mode full --playground-trials 10 --libero-trial-num 50 --max-tasks-per-benchmark 10 --benchmarks libero_object,libero_10,libero_goal --parallel-env-num 5
```

This is the batch that matches the public release defaults most closely:

- playground: `10` random-scene trials
- LIBERO: `50` trials per task
- task cap: up to `10` tasks per benchmark suite
- suites: `libero_object`, `libero_10`, `libero_goal`
- parallel workers: `5`

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
- Official `playground.py` succeeds in the dedicated `gb-graspvla-sim` environment.
- Official full simulation batch succeeds with `playground=10`, `LIBERO=50 trials/task`, and `5` parallel workers.
- The fetched complete batch contains `10` playground videos and `1200` LIBERO videos.
- Official statistics for the complete batch are:
  - `libero_object: 482/500 = 0.964`
  - `libero_10: 325/350 = 0.929`
  - `libero_goal: 336/350 = 0.960`
- The official full simulation artifact should be tagged as `track_b_native`.
- Shared benchmark-wrapper runs under `artifacts/runs/...` should be tagged as `track_a`.
- The lower denominators for `libero_10` and `libero_goal` are expected in this public release:
  - `libero_10` only exposes `7` tasks in `libero_suite_task_map.py`
  - `libero_goal` includes `3` tasks whose instruction resolves to `invalid`, so the official runner skips them
- GraspVLA benchmark smoke succeeds.
- Contact-GraspNet legacy runtime and checkpoint are ready, and smoke succeeds.
- AnyGrasp setup is ready up to the license boundary.

## Latest Verified Artifact

- Local artifact:
  `artifacts/official/20260402_211510_em14_graspvla_checks/summary.json`
- Visualization:
  `artifacts/official/20260402_194109_em14_graspvla_checks/offline_test_visualization.png`
- Official simulation artifact:
  `artifacts/official_sim/20260402_231726_em14_full/summary.json`
- Human-readable report:
  `docs/reports/graspvla_official_sim_complete_20260402.md`
- Setting freeze note:
  `docs/reports/benchmark_setting_freeze_v1_20260402.md`

## Next Week Plan

- Use the complete official GraspVLA batch as the anchor when aligning modular baselines.
- Mirror the same remote artifact structure for the first modular baseline.
- Fetch the AnyGrasp license and complete the third baseline.
- Start packaging plots and failure videos for the benchmark meeting.

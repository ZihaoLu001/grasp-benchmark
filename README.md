# grasp-benchmark

`grasp-benchmark` is a benchmark and protocol-audit scaffold for comparing end-to-end and modular grasping systems under a frozen shared-perception, shared-embodiment setup.

## Current Status

As of **April 12, 2026**, the **simulator-side benchmark packet is complete for all currently runnable baselines**:

- `Track A-Cal v2` shared benchmark
- `Track A-Stress v2` shared stress appendix
- `GraspVLA` official-alignment audit
- `GraspVLA protocol_probe_v2`
- `CGN bottleneck_v1`
- `CGN` native appendix
- paper-ready summary/statistics bundle

The remaining gaps are **external blockers**, not missing simulator execution:

- `AnyGrasp`: waiting for a new node-matched license
- real-world pilot: waiting for robot/camera time
- `Phase 2 constraint / affordance grasping`: intentionally deferred

## Latest Results

The current advisor-facing entry points are:

- Latest complete benchmark summary:
  [benchmark_results_latest_20260412_zh.md](D:/codex/grasp-benchmark/docs/reports/benchmark_results_latest_20260412_zh.md)
- Completion matrix:
  [corl_completion_matrix_20260412_zh.md](D:/codex/grasp-benchmark/docs/reports/corl_completion_matrix_20260412_zh.md)
- Verified simulator note:
  [corl_simulator_verified_results_20260412_zh.md](D:/codex/grasp-benchmark/docs/reports/corl_simulator_verified_results_20260412_zh.md)
- Paper-ready report:
  [paper_ready_report.md](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/paper_ready_report.md)
- Paper-ready summary CSV:
  [paper_summary.csv](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/paper_summary.csv)
- Teacher summary:
  [teacher_summary_zh_clean.md](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/teacher_summary_zh_clean.md)

## Headline Numbers

Current frozen simulator numbers:

- `Track A-Cal v2`
  - `GraspVLA`: `59 / 60`
  - `CGN full modular`: `0 / 60`
- `Track A-Stress v2`
  - `GraspVLA`: `62 / 64`
  - `CGN full modular`: `0 / 64`
- `Track B native reference`
  - official `GraspVLA playground`: `8 / 10`
  - official `GraspVLA libero_10`: `325 / 350`
  - official `GraspVLA libero_goal`: `336 / 350`
  - official `GraspVLA libero_object`: `482 / 500`
- `Track B native appendix`
  - `CGN`: `1 / 84`

## Repo Layout

- `src/grasp_benchmark/`: Python package and CLIs
- `configs/`: task, scene, sensor, method, and cluster YAML
- `cluster/`: remote bootstrap and environment scripts
- `scripts/`: local convenience wrappers
- `docs/reports/`: current advisor-facing reports plus archive
- `artifacts/`: generated run/audit/report outputs (ignored by git)
- `third_party/upstreams/`: upstream repos cloned locally/remotely (ignored by git)

## Quick Start

1. Install the package:

```powershell
python -m pip install -e .
```

2. Run cluster preflight:

```powershell
python -m grasp_benchmark.preflight --pool em,rll
```

3. Fetch upstream repos:

```powershell
python -m grasp_benchmark.fetch_upstreams
```

4. Launch or validate the GraspVLA server:

```powershell
python -m grasp_benchmark.serve.graspvla --node em14 --download-model
```

5. Dispatch simulator benchmark runs:

```powershell
python -m grasp_benchmark.run.sim --method graspvla --task-set track_a_cal_v2 --node em14
python -m grasp_benchmark.run.sim --method cgn --task-set track_a_cal_v2 --matrix
```

6. Build the paper-ready bundle:

```powershell
python -m grasp_benchmark.report.paper_bundle --input artifacts\\runs
```

## Notes

- `Track A-Cal v2` is the only headline fair benchmark table.
- `Track A-Stress v2` is appendix-only.
- `Track B` remains native-reference only.
- Historical milestone reports are preserved under `docs/reports/archive/202604/`.

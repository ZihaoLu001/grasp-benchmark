# AnyGrasp Insertion Status (2026-04-07)

## Summary

The AnyGrasp license bundle from `D:\VLA\license_ZihaoLu` has been installed on `em14` and the node-bound feature id matches the benchmark runtime.

Current status:

- `license_ready = true`
- `checkpoint_present = false`
- final headline insertion is **blocked only by the missing official detection checkpoint**

## What Was Completed

- Installed the license bundle into:
  - `third_party/upstreams/anygrasp_sdk/grasp_detection/license/`
  - `third_party/upstreams/anygrasp_sdk/grasp_tracking/license/`
- Revalidated the SDK on `em14`
- Built the remaining runtime dependencies in `gb-anygrasp`:
  - `MinkowskiEngine`
  - `pointnet2`
- Patched the AnyGrasp lane so NumPy compatibility aliases are set before shared-sim imports

## Readiness Artifact

Latest readiness artifact:

- `artifacts/anygrasp/20260407_053004_em14.json`

Key fields:

- `feature_id = 7797173549007423731`
- `import_status = 0`
- `license_ready = true`
- `checkpoint_present = false`

## Smoke Result

Latest decision-complete smoke:

- `artifacts/runs/20260407_002837_anygrasp_track_a_cal_v1_shared_sim_smoke_v3/results.csv`

The two-scene smoke now fails cleanly at:

- `failure_stage = model_assets`
- `failure_reason = Missing AnyGrasp checkpoint: /datasets/ss/current/zihao/grasp-benchmark/third_party/upstreams/anygrasp_sdk/grasp_detection/log/checkpoint_detection.tar`

This means the benchmark protocol, license wiring, and AnyGrasp runtime bootstrap are no longer the blockers.

## Interpretation

The remaining issue is not a benchmark-design problem.

It is also not a license-validation problem.

It is an official AnyGrasp asset packaging issue: the public SDK requires `checkpoint_detection.tar`, and upstream issue comments indicate that this checkpoint is normally provided together with the license bundle.

## Next Step

Once `checkpoint_detection.tar` is available, the remaining execution is straightforward:

1. copy the checkpoint into
   `third_party/upstreams/anygrasp_sdk/grasp_detection/log/`
2. rerun the two-scene smoke on `em14`
3. run the full frozen `track_a_cal_v1` batch
4. regenerate the final three-method fairness report:
   - `GraspVLA`
   - `CGN full modular`
   - `AnyGrasp full modular`

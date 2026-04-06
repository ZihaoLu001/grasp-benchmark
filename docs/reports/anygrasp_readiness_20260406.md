# AnyGrasp Readiness Note (2026-04-06)

## Status

`AnyGrasp` is now in a clean **license-only blocked** state for the frozen `Track A-Cal` benchmark.

## Ready Components

- upstream checkout:
  `third_party/upstreams/anygrasp_sdk`
- benchmark method tier:
  `anygrasp_full_modular`
- shared observation contract:
  `rgb_front + depth_front + intrinsics_front + extrinsics_front + proprio + instruction`
- `GroundingDINO` integration
- shared segmentation / mask filtering
- shared planner integration
- report labeling and taxonomy wiring

## Current Blocker

- missing runtime license config / bundle
- latest readiness artifact:
  `artifacts/anygrasp/20260406_105544_em14.json`

Key fields from the latest probe:

- `feature_id = 7797173549007423731`
- `import_status = 0`
- `license_ready = false`

## Interpretation

This means the benchmark does **not** need another protocol change before inserting `AnyGrasp`.

Once the license bundle is placed under the expected SDK license directory, the remaining work is:

1. rerun a `2`-trial smoke on `em14`
2. run the full `track_a_cal_v1` batch on the unchanged shared leaderboard
3. regenerate the headline fairness report with:
   - `GraspVLA`
   - `CGN full modular`
   - `AnyGrasp full modular`

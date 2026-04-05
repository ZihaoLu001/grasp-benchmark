# GraspVLA Boundary And Factor Breakdown (2026-04-05)

## Headline

- The original "official native high, shared benchmark all-zero" story is no longer the right summary.
- The latest formal shared calibration run is now `15/15`, so the old `Track A-Cal = 0/15` result should be treated as a stale implementation-era artifact, not the current benchmark state.
- The current official-alignment status is `reproducibility-limited parity`, which means the wrapper is close to the public release and the remaining uncertainty is now much smaller than before.

## Evidence

- Official native reference:
  - [summary.json](D:/codex/grasp-benchmark/artifacts/official_sim/20260402_231726_em14_full/summary.json)
- Full official-alignment attribution audit:
  - [report.md](D:/codex/grasp-benchmark/artifacts/audits/20260404_223758_graspvla_official_alignment/report.md)
  - [success_delta.csv](D:/codex/grasp-benchmark/artifacts/audits/20260404_223758_graspvla_official_alignment/success_delta.csv)
- Scene-edit compatibility probe:
  - [scene_edit_compatibility_probe_20260405_summary.csv](D:/codex/grasp-benchmark/artifacts/audits/scene_edit_compatibility_probe_20260405_summary.csv)
- Goal-only official-aligned audit for clean scene-edit measurement:
  - [report.md](D:/codex/grasp-benchmark/artifacts/audits/20260405_021725_graspvla_official_alignment/report.md)
  - [success_delta.csv](D:/codex/grasp-benchmark/artifacts/audits/20260405_021725_graspvla_official_alignment/success_delta.csv)
- Latest formal Track A-Cal run:
  - [results.csv](D:/codex/grasp-benchmark/artifacts/runs/20260405_001205_graspvla_track_a_cal_v1_shared_sim/results.csv)
  - [report.md](D:/codex/grasp-benchmark/artifacts/reports/track_a_cal_graspvla_refresh_20260405/report.md)

## What Changed The Result The Most

### Full official subset

| Factor | Transition | Delta | Interpretation |
| --- | --- | --- | --- |
| `extended finger -> shared gripper` | `V1 -> V2` | `-0.0166` | Very small |
| `env done -> lift >= 15 cm and hold >= 2 s` | `V2 -> V3` | `-0.3167` | Largest cleanly measured drop |
| `official scene edits removed` | `V3 -> V4` | not cleanly measurable | Basket-linked tasks become incompatible in the public release |

This is the key point: **the `2 cm` gripper extension is not the main reason** for the earlier gap.  
The biggest cleanly measured factor on the full official subset is the stricter shared success rule.

### Scene-edit-compatible subset (`libero_goal`)

To isolate scene edits on tasks that do not depend on basket removal, I reran the audit on the official `libero_goal` subset only.

| Factor | Transition | Delta | Interpretation |
| --- | --- | --- | --- |
| `extended finger -> shared gripper` | `V1 -> V2` | `+0.0500` | Small-to-moderate and not harmful here |
| `env done -> lift >= 15 cm and hold >= 2 s` | `V2 -> V3` | `-0.0500` | Moderate |
| `official scene edits -> no method-specific scene edits` | `V3 -> V4` | `-0.0500` | Moderate on this compatible subset |

This gives a cleaner interpretation:

- On tasks that are already runnable without official scene edits, the scene-edit effect is **real but modest**.
- On basket-linked tasks, the scene-edit effect is **not just a performance change**; it is a **compatibility gate** in the current public release.

## Why `V4` Failed On The Full Official Subset

The compatibility probe shows that the selected basket-related official tasks are fully tied to the official `process_initial_state` logic:

- `libero_object` task `0` and `1`: `0/10` raw-state compatible, `10/10` processed-state compatible
- `libero_10` task `0` and `1`: `0/10` raw-state compatible, `10/10` processed-state compatible
- `libero_goal` task `1` and `2`: `10/10` raw-state compatible, `10/10` processed-state compatible

So the current public release boundary is:

- `libero_goal` selected tasks can be used to measure scene-edit performance deltas directly.
- The selected `libero_object` and `libero_10` basket tasks cannot be used for a clean no-scene-edit ablation without regenerating compatible init states or redefining the overlap subset.

## What This Means For The Benchmark

- `Track B` still tells us the native upper bound of the public GraspVLA release.
- `official_aligned` now tells us the wrapper is close enough that the remaining uncertainty is no longer the main story.
- `Track A-Cal` should still be treated carefully, but the current shared calibration scenes are clearly runnable because the latest formal result is `15/15`.

## Practical Conclusion

- If the question is "Was the huge drop mainly caused by the `2 cm` finger extension?" the answer is **no**.
- If the question is "Did the stricter shared success rule matter?" the answer is **yes, substantially**.
- If the question is "Did official scene edits matter?" the answer is **yes**, but in two different ways:
  - on `libero_goal` they create a modest performance delta
  - on basket-linked official tasks they are a release-boundary compatibility requirement
- If the question is "Were the old shared all-zero results proving the benchmark scenes were impossible?" the answer is **no**. The latest formal `Track A-Cal` run is `15/15`.

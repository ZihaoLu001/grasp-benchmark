# GraspVLA Factor Attribution Update

## Headline

- The earlier `Track A-Cal = 0/15` result is no longer representative of the current runner.
- The latest formal shared-benchmark run is `15/15` for `GraspVLA` under `track_a_cal_v1`.
- The official-alignment audit is now at `reproducibility-limited parity`, not a hard wrapper failure.

## Evidence

- Official native reference remains strong:
  - [summary.json](D:/codex/grasp-benchmark/artifacts/official_sim/20260402_231726_em14_full/summary.json)
- Latest official-alignment factor audit:
  - [report.md](D:/codex/grasp-benchmark/artifacts/audits/20260404_223758_graspvla_official_alignment/report.md)
  - [comparison_summary.csv](D:/codex/grasp-benchmark/artifacts/audits/20260404_223758_graspvla_official_alignment/comparison_summary.csv)
  - [success_delta.csv](D:/codex/grasp-benchmark/artifacts/audits/20260404_223758_graspvla_official_alignment/success_delta.csv)
- Latest formal Track A-Cal run:
  - [results.csv](D:/codex/grasp-benchmark/artifacts/runs/20260405_001205_graspvla_track_a_cal_v1_shared_sim/results.csv)
  - [report.md](D:/codex/grasp-benchmark/artifacts/reports/track_a_cal_graspvla_refresh_20260405/report.md)

## Measured Factor Effects

| Factor | Transition | Result |
| --- | --- | --- |
| `2 cm extended finger -> plain shared gripper` | `V1 -> V2` | Success rate changes from `0.9833` to `0.9667` (`-0.0166`). This is a very small effect. |
| `official env_done -> shared lift>=15 cm + hold 2 s` | `V2 -> V3` | Success rate changes from `0.9667` to `0.6500` (`-0.3167`). This is the largest cleanly measured effect. |
| `official scene edits removed` | `V3 -> V4` | Not cleanly measurable yet. The public LIBERO subset and official init-state processing are entangled: `V4` currently fails with a state-length mismatch instead of producing a valid like-for-like score. |
| `official subset -> Track A-Cal shared distribution` | `V4 -> V5` | This is no longer evidence of a catastrophic drop. The latest formal Track A-Cal run is `15/15`, so the current shared calibration scenes themselves are not the source of the old all-zero result. |

## Interpretation

- The **2 cm gripper extension is not the main reason** for the earlier gap.
- The **shared success rule is a real and important factor**. It lowers success by about `31.67` percentage points on the official-aligned subset.
- The **official scene-edit effect is still unresolved** because the public release currently ties some official tasks to `process_initial_state` logic such as basket removal. We need a clean no-scene-edit subset or regenerated compatible init states to isolate this factor.
- The earlier **`Track A-Cal = 0/15` was mostly an implementation-era artifact**, not the stable result of the current shared benchmark. The current formal shared run shows `15/15`.

## Practical Conclusion

- If the question is “was the huge drop mainly caused by the `2 cm` gripper change?”, the answer is **no**.
- If the question is “did the stricter benchmark success criterion matter?”, the answer is **yes, a lot**.
- If the question is “were the earlier all-zero shared results telling us the benchmark scenes were impossible?”, the answer is **no**. The latest `Track A-Cal` run shows they are very runnable for the current GraspVLA stack.
- The next clean technical task is to isolate the **scene-edit effect** by making `V4_no_method_specific_scene_edits` runnable on an official-aligned subset without state-length mismatch.

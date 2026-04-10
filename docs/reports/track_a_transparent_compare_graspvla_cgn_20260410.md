# Track A Transparent Compare Report (2026-04-10)

## Scope

- This report covers only the shared transparent-object subset under the frozen benchmark shared protocol.
- Reporting role:
  - not the `Track A-Cal` headline table
  - not `Track B`
  - a focused transparent-slice compare used to clarify method behavior on transparent proxy assets

Shared protocol kept fixed:

- same dual fixed cameras
- same shared gripper
- same workspace
- same blocking control
- same success rule: `lift >= 15 cm` and `hold >= 2 s`
- same `3-attempt` budget

## Runs

- `GraspVLA`
  - parent run: `20260409_232700_graspvla_track_a_v2_transparent_shared_sim`
  - artifact: `D:\codex\grasp-benchmark\artifacts\runs\20260409_232700_graspvla_track_a_v2_transparent_shared_sim\results.csv`
- `CGN full modular`
  - source batch: `20260409_235000_cgn_track_a_v2_transparent_shared_sim`
  - clean reruns:
    - `20260410_020500_cgn_track_a_v2_transparent_scene3_shared_sim`
    - `20260410_004500_cgn_track_a_v2_transparent_scene4_shared_sim`
- `AnyGrasp`
  - not runnable on the current node with the supplied bundle because the license feature id does not match current hardware

## Headline Result

| method | trials | successes | success_rate | mean_attempts | mean_inference_ms |
| --- | --- | --- | --- | --- | --- |
| GraspVLA | 4 | 4 | 1.0 | 1.0 | 408.6251 |
| CGN full modular | 4 | 0 | 0.0 | 3.0 | 4197.7749 |

## Per-Scene Result

| scene | object | GraspVLA | CGN full modular | note |
| --- | --- | --- | --- | --- |
| `arbitrary_grasping_transparent__transparent__001` | `clear_plastic_cup` | success, `lift=20.0384 cm` | fail, `lift=1.0008 cm` | CGN produced proposals but did not satisfy shared lift/hold rule |
| `arbitrary_grasping_transparent__transparent__002` | `glass_bottle` | success, `lift=15.1924 cm` | fail, `lift=1.1253 cm` | same pattern |
| `arbitrary_grasping_transparent__transparent__003` | `wine_glass` | success, `lift=15.4043 cm` | fail, `lift=-1.8161 cm` | dedicated rerun used for final row |
| `arbitrary_grasping_transparent__transparent__004` | `acrylic_box` | success, `lift=15.2272 cm` | fail, `lift=1.1048 cm` | dedicated rerun used for final row |

## What Happened In The Interrupted CGN Batch

- The original 4-scene CGN transparent batch did not crash at setup time.
- It completed all three attempts for scenes `001` and `002`.
- It started scene `003`, then hit the wall-clock timeout before a final `results.csv` could be written for the whole batch.
- The failure mode is therefore:
  - not `dependency_setup`
  - not `grounding_error`
  - mostly `task_failure` after the modular stack already produced detections and grasp proposals

## Interpretation

- On this transparent shared subset, the current public `GraspVLA` release is strong: `4/4`.
- The current `CGN full modular` lane is not failing because it cannot see anything at all.
- Instead, it is failing later in the chain:
  - target isolation and proposal can happen
  - but the fixed shared execution path does not convert those proposals into a successful transparent pickup under the shared success rule
- This is exactly why the transparent subset is useful in the benchmark:
  - it separates “proposal exists” from “shared benchmark success is actually achieved”

## AnyGrasp Status For Transparent Compare

- The transparent 3-method table is still blocked operationally.
- The supplied bundle at `D:\VLA\license_ZihaoLu` contains feature id `7797173549007423731`.
- The current `em14` machine reports feature id `10649709207478896037`.
- As a result, the SDK fails before inference with:
  - `feature id doesn't match the hardware`
- Until a refreshed license is issued for the current target node, transparent AnyGrasp runs cannot be added to this table.

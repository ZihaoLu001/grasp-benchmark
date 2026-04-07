# AnyGrasp Insertion Complete (2026-04-07)

## Final Status

- Node-bound license installed on `em14`
- Official checkpoints installed
- Runtime dependencies built successfully
- Shared benchmark adapter operational
- Final `Track A-Cal` run completed on `em14`

## Operational Milestones

1. Installed license bundle from `D:\VLA\license_ZihaoLu`
2. Matched feature id `7797173549007423731` on `em14`
3. Built `MinkowskiEngine`
4. Built `pointnet2`
5. Downloaded and installed:
   - `checkpoint_detection.tar`
   - `checkpoint_tracking.tar`
6. Revalidated readiness with:
   - `import_status = 0`
   - `license_ready = true`
   - `checkpoint_present = true`
7. Fixed AnyGrasp adapter behavior so null proposals are reported as `grasp_proposal`
8. Reran the full frozen `Track A-Cal` benchmark

## Final Benchmark Outcome

- `AnyGrasp full modular`: `0/15`

Failure breakdown:
- `11` x `grasp_proposal`
- `2` x `grounding_error: carrot`
- `2` x `grounding_error: power drill`

Primary artifacts:
- readiness: `D:\codex\grasp-benchmark\artifacts\anygrasp\20260407_053602_em14.json`
- final run: `D:\codex\grasp-benchmark\artifacts\runs\20260407_062119_anygrasp_track_a_cal_v1_shared_sim\results.csv`
- final headline report: `D:\codex\grasp-benchmark\artifacts\reports\track_a_cal_compare_graspvla_cgn_anygrasp_latest\report.md`

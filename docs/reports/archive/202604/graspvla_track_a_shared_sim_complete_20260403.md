# GraspVLA Track A Shared-Sim Report

## Batch Summary

- Reporting role: `Track A / shared benchmark`
- Node: `em14`
- Execution mode: `shared_track_a_sim`
- Server: `127.0.0.1:6666`
- Task set: `track_a_v1`
- Command:

```powershell
python -m grasp_benchmark.run.sim --method graspvla --task-set track_a_v1 --node em14 --execution-mode shared_track_a_sim
```

- Local artifact root:
  `artifacts/runs/20260403_051928_graspvla_track_a_v1_shared_sim`
- Aggregate report root:
  `artifacts/reports/graspvla_track_a_real_latest`
- Summary CSV:
  `artifacts/reports/graspvla_track_a_real_latest/summary.csv`
- Teacher summary:
  `artifacts/reports/graspvla_track_a_real_latest/teacher_summary_zh.md`

## Results

### Track A Shared Benchmark

- `language_conditioned_single_target_pick: 0/25 = 0.000`
- `arbitrary_grasping_transparent: 0/4 = 0.000`
- Overall:
  `0/29 = 0.000`

### By Condition

- `basic: 0/5 = 0.000`
- `lighting: 0/5 = 0.000`
- `background: 0/5 = 0.000`
- `distractors: 0/5 = 0.000`
- `height: 0/5 = 0.000`
- `transparent: 0/4 = 0.000`

### Efficiency

- `language_conditioned_single_target_pick` mean inference latency:
  `453.422 ms`
- `arbitrary_grasping_transparent` mean inference latency:
  `445.7128 ms`
- `language_conditioned_single_target_pick` mean cycle time:
  `146.7363 s`
- `arbitrary_grasping_transparent` mean cycle time:
  `188.9989 s`

## Failure Taxonomy

- All `29/29` trials ended as:
  `task_failure / Shared success criterion was not met within the Track A step budget.`
- No setup, dependency, or scene-import failures remain in the final batch.

## Interpretation

- This is the first complete `Track A` GraspVLA result under the shared benchmark setting.
- These numbers are not comparable to the earlier official GraspVLA simulation table without qualification, because the official run is `Track B / native reference`.
- The current evidence is that GraspVLA can run end-to-end under the shared wrapper, but it does not solve the current `Track A v1` shared-sim scenes under the frozen `lift >= 15 cm` and `hold >= 2 s` rule.

## Track B Reference Reminder

- Official native reference remains:
  `docs/reports/graspvla_official_sim_complete_20260402.md`
- Latest official summary artifact:
  `artifacts/official_sim/20260402_231726_em14_full/summary.json`
- Native reference numbers:
  - `playground: 8/10 = 0.800`
  - `libero_object: 482/500 = 0.964`
  - `libero_10: 325/350 = 0.929`
  - `libero_goal: 336/350 = 0.960`

## Supporting Artifacts

- Track A aggregate markdown:
  `artifacts/reports/graspvla_track_a_real_latest/report.md`
- Track A summary JSON:
  `artifacts/reports/graspvla_track_a_real_latest/report.json`
- Track A condition table:
  `artifacts/reports/graspvla_track_a_real_latest/by_condition.csv`
- Track A failure taxonomy:
  `artifacts/reports/graspvla_track_a_real_latest/failure_taxonomy.csv`

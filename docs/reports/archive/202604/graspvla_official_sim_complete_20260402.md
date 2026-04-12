# GraspVLA Official Complete Simulation Report

## Batch Summary

- Reporting role: `Track B / native best-case reference`
- Node: `em14`
- Server: `127.0.0.1:6666`
- Mode: `full`
- Command:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_official_graspvla_sim.ps1 -Node em14 -Mode full -PlaygroundTrials 10 -LiberoTrialNum 50 -MaxTasksPerBenchmark 10 -Benchmarks libero_object,libero_10,libero_goal -ParallelEnvNum 5
```

- Local artifact root:
  `artifacts/official_sim/20260402_231726_em14_full`
- Summary JSON:
  `artifacts/official_sim/20260402_231726_em14_full/summary.json`
- Approximate wall-clock runtime:
  `2h 08m`

## Results

### Playground

- Trials: `10`
- Successes: `8`
- Failures: `2`
- Success rate: `0.800`
- Video directory:
  `artifacts/official_sim/20260402_231726_em14_full/playground_data/videos`

### LIBERO

- `libero_object: 482/500 = 0.964`
- `libero_10: 325/350 = 0.929`
- `libero_goal: 336/350 = 0.960`
- Overall across fetched LIBERO videos:
  `1143/1200 = 0.953`
- Statistics file:
  `artifacts/official_sim/20260402_231726_em14_full/libero_statistics.txt`
- Video directory:
  `artifacts/official_sim/20260402_231726_em14_full/libero_data/videos`

## Important Notes

- This artifact is a method-native GraspVLA reference and should not be merged into Track A benchmark summaries.
- The `libero_10` denominator is `350`, not `500`, because this public release currently exposes `7` tasks for `libero_10` in `third_party/upstreams/GraspVLA-playground/libero/libero/benchmark/libero_suite_task_map.py`.
- The `libero_goal` denominator is also `350` because task ids `0`, `5`, and `7` resolve to `Instruction: invalid` in the official runner and are skipped.
- This means the run is complete with respect to the currently released public simulation stack, not incomplete.

## Supporting Artifacts

- Official validation summary:
  `artifacts/official/20260402_211510_em14_graspvla_checks/summary.json`
- Official offline visualization:
  `artifacts/official/20260402_194109_em14_graspvla_checks/offline_test_visualization.png`
- Worker logs:
  `artifacts/official_sim/20260402_231726_em14_full/libero_worker_0_stdout.txt`
  through
  `artifacts/official_sim/20260402_231726_em14_full/libero_worker_4_stdout.txt`

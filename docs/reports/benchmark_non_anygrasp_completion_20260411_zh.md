# Benchmark 非 AnyGrasp 部分完成说明（2026-04-11）

## 范围

- 这份说明总结的是：在不等新的 AnyGrasp license 的前提下，benchmark 里还能正式做完的 simulation 评测，现在已经基本做完了。
- benchmark 协议没有改。
- 只是把此前还没收口的非 AnyGrasp 部分补成了完整版本。

## 现在已经完成的部分

### 1. `Track A-Cal` 主榜单

冻结主榜单还是：

- `GraspVLA`: `14/15`
- `CGN full modular`: `0/15`
- `AnyGrasp full modular`: 旧 artifact 还在，但当前 AnyGrasp 线现在被新的 license mismatch 卡住

主产物：

- [report.md](D:/codex/grasp-benchmark/artifacts/reports/track_a_cal_compare_graspvla_cgn_anygrasp_latest/report.md)

### 2. 透明物体 shared 子集

已经完成的方法：

- `GraspVLA`: `4/4`
- `CGN full modular`: `0/4`

主产物：

- [report.md](D:/codex/grasp-benchmark/artifacts/reports/track_a_transparent_compare_graspvla_cgn_latest/report.md)

### 3. `Track A-Stress` 的完整非 AnyGrasp 压力测试

这是这次新补完的关键部分。

新版完整 `track_a_v2` 结果：

- `GraspVLA / language_conditioned_single_target_pick`: `23/25`
- `GraspVLA / arbitrary_grasping_transparent`: `4/4`
- `GraspVLA / arbitrary_grasping_common_opaque`: `5/5`
- `GraspVLA total`: `32/34`

- `CGN full modular / language_conditioned_single_target_pick`: `0/25`
- `CGN full modular / arbitrary_grasping_transparent`: `0/4`
- `CGN full modular / arbitrary_grasping_common_opaque`: `0/5`
- `CGN full modular total`: `0/34`

主产物：

- [report.md](D:/codex/grasp-benchmark/artifacts/reports/track_a_stress_compare_graspvla_cgn_latest/report.md)

## 当前最重要的解释

- 之前那份历史 `Track A-Stress` 里 `GraspVLA = 0/34`，已经不能代表当前 repo 的真实状态了。
- 在修好 shared simulation lane 之后，`GraspVLA` 现在在完整冻结的 `track_a_v2` stress 套件上是强的。
- `GraspVLA` 当前最明显的薄弱点主要在 `distractors` 条件：
  - `3/5`
- `CGN full modular` 在同一套 shared stress 协议下仍然是 `0/34`。
- `CGN` 的主要失败模式有两类：
  - 一部分是 `GroundingDINO` 在语言场景里没找到目标，尤其是 `power drill`
  - 另一大部分是已经有 proposal / execution 之后，最后还是落在 `task_failure`

## 一个重要的工程说明

- 我也试了把 `CGN` 放到 `rll_6000_1/2` 上 cross-node 跑。
- 那两台暴露的是 CUDA 扩展兼容性问题：
  - `CUDA error: no kernel image is available for execution on the device`
- 所以这次正式 `CGN track_a_v2` 完整结果最后是改在 `em14` 上用多 GPU 分片跑完的。

## 现在还剩什么

到这一步之后，真正还没完成的 benchmark 项只剩：

1. `AnyGrasp` 的 transparent 子集和最终 stress 插入
2. real-world pilot 正式 benchmark 数字
3. Phase 2 constraint / affordance grasping
4. modular `Track B` native best-case 参考轨

也就是说，simulation 主线现在除了 AnyGrasp 这条被 license 卡住的线之外，已经基本收口了。

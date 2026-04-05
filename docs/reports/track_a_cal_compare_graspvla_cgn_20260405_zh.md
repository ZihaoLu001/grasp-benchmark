# Track A-Cal 正式对比报告（2026-04-05）

## 范围

- 这是 benchmark v1.1 主榜单 `Track A-Cal` 的正式共享仿真对比。
- 方法：`GraspVLA` 与 `Contact-GraspNet`。
- 任务集：`track_a_cal_v1`。
- `Track A-Stress` 继续保留为历史 `track_a_v2` 压力测试附录。
- `Track B` 继续保留为官方 native reference，不参与公平主结论。

## 本次正式运行

- `GraspVLA`：`20260405_053120_graspvla_track_a_cal_v1_shared_sim`
- `CGN`：`20260405_090826_cgn_track_a_cal_v1_shared_sim`
- `CGN` 分片节点：
  - `pabrtxl1 / rll_6000_1 / gpu0`
  - `pabrtxl2 / rll_6000_2 / gpu0`

## 主结论

- `GraspVLA`：`14/15`
- `CGN`：`0/15`
- 这是第一版真正拉开差距的 `Track A-Cal` 正式结果，说明当前共享 benchmark 主榜单已经具备区分度。

## 分任务结果

- `GraspVLA / language_conditioned_single_target_pick`：`10/10`
- `GraspVLA / arbitrary_grasping_common_opaque`：`4/5`
- `CGN / language_conditioned_single_target_pick`：`0/10`
- `CGN / arbitrary_grasping_common_opaque`：`0/5`

## 失败类型

- `GraspVLA`：`1` 个 `task_failure`
- `CGN`：`14` 个 `task_failure`
- `CGN`：`1` 个 `grasp_proposal`

## 解读

- 当前主榜单已经可以回答第一层 benchmark 问题：
  - 在共享感知与共享 embodiment 下，`GraspVLA` 目前明显优于这版最基础的 `CGN` baseline。
- 但这还不是 modular pipeline 的最终上限。
  - 这次 `CGN` 仍然是最原始的共享输入版本：
    - front depth point cloud
    - 原始 `Contact-GraspNet` proposal
    - shared action conversion
    - 没有 segmentation
    - 没有 detector filtering
- 所以下一步最合理的方向不是改 benchmark 协议，而是：
  - 保持 `Track A-Cal` 不变
  - 继续把 modular baseline 做完整
  - `AnyGrasp` license 到位后再接入同一主榜单

## 关键产物

- 正式汇总报告：
  `artifacts/reports/track_a_cal_compare_graspvla_cgn_latest/report.md`
- 老师版中文页：
  `artifacts/reports/track_a_cal_compare_graspvla_cgn_latest/teacher_summary_zh_clean.md`
- failure taxonomy：
  `artifacts/reports/track_a_cal_compare_graspvla_cgn_latest/failure_taxonomy.csv`
- `Track A-Stress` 参考：
  `artifacts/reports/track_a_compare_graspvla_cgn_v2_latest/report.md`
- `Track B` 官方 native reference：
  `artifacts/official_sim/20260402_231726_em14_full/summary.json`

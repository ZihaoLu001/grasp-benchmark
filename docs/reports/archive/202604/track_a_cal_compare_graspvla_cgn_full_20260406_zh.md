# Track A-Cal 完整模块化对比报告（2026-04-06）

## 范围

- 这是 benchmark v1.1 当前主榜单 `Track A-Cal` 的正式共享 setting 仿真对比。
- 当前进入主榜单的两条方法是：
  - `GraspVLA`
  - `Contact-GraspNet + Segmentation + Grounding DINO + shared motion planner`
- 任务集固定为 `track_a_cal_v1`
- `Track A-Stress` 继续只作为附录压力测试。
- `Track B` 继续只作为官方 native reference。
- `AnyGrasp` 这次还没有进主榜单，因为公开 SDK 已经就绪，但 license 还没到。

## 本次正式运行

- `GraspVLA`：`20260405_053120_graspvla_track_a_cal_v1_shared_sim`
- `CGN full modular`：`20260406_115112_cgn_track_a_cal_v1_shared_sim`
- `CGN` 这次完整批次只跑在 `em14`，并且只使用 `em14` 的 `0-7` 号 GPU，没有再混入 `rll_6000_1/2`。

## 主结论

- `GraspVLA`：`14/15`
- `CGN full modular`：`0/15`

这次和之前最重要的区别是：`CGN` 不再是早期那个 raw/interim baseline，而是真正按 benchmark 文档组装起来的完整模块化链路：

- shared observation
- `GroundingDINO` 目标定位
- depth mask / segmentation
- 目标物体点云
- `Contact-GraspNet` proposal
- shared motion planner
- shared success rule

## 分任务结果

- `GraspVLA / language_conditioned_single_target_pick`：`10/10`
- `GraspVLA / arbitrary_grasping_common_opaque`：`4/5`
- `CGN full modular / language_conditioned_single_target_pick`：`0/10`
- `CGN full modular / arbitrary_grasping_common_opaque`：`0/5`

## 失败类型

- `GraspVLA`：`1` 个 `task_failure`
- `CGN full modular`：`11` 个 `task_failure`
- `CGN full modular`：`4` 个 `grounding_error`

目前 `CGN` 在语言任务上最明显的问题不是 planner，而是 detector 先没有把目标框稳住，尤其是 `carrot` 和 `power drill`。拿到 proposal 之后，剩下的大部分失败则是固定执行计划没有满足共享成功判定。

## 解释口径

- 这张表比之前的 `GraspVLA 14/15 vs raw-CGN 0/15` 更公平，因为 modular 一侧已经不再是半成品。
- 在当前冻结的共享协议下：
  - 同一机器人 embodiment
  - 同一相机
  - 同一 workspace
  - 同一 attempt budget
  - 同一 success rule
  - 不允许 method-specific scene edits
  `GraspVLA` 目前明显强于这条公开的完整 `CGN` 模块化链路。
- 但这还不是最终的 “end-to-end vs modular” 总结，因为真正的最终主表还少最后一条：
  - `AnyGrasp + Grounding DINO + shared motion planner`

## AnyGrasp 当前状态

- 公开 SDK 已经 clone 到项目中。
- `em14` 上 import probe 已经能通过。
- 当前唯一 blocker 是 license bundle / `licenseCfg.json` 还没收到。
- readiness artifact：
  `artifacts/anygrasp/20260406_105544_em14.json`

## 关键产物

- 正式汇总报告：
  `artifacts/reports/track_a_cal_compare_graspvla_cgn_full_latest/report.md`
- 老师版中文页：
  `artifacts/reports/track_a_cal_compare_graspvla_cgn_full_latest/teacher_summary_zh_clean.md`
- failure taxonomy：
  `artifacts/reports/track_a_cal_compare_graspvla_cgn_full_latest/failure_taxonomy.csv`
- `Track A-Stress` 附录：
  `artifacts/reports/track_a_compare_graspvla_cgn_v2_latest/report.md`
- `Track B` 官方 native reference：
  `artifacts/official_sim/20260402_231726_em14_full/summary.json`
- AnyGrasp readiness：
  `artifacts/anygrasp/20260406_105544_em14.json`

# Track A-Cal 三方法公平比较总结（2026-04-07）

## 范围

- 这份结果对应当前冻结的 `Track A-Cal` 主榜单。
- benchmark 协议没有改：
  - `track_a_cal_v1`
  - 共享 gripper / 共享相机 / 共享 workspace
  - blocking control
  - 成功定义 `lift >= 15 cm` 且 `hold >= 2 s`
  - 每个 trial 最多 `3` 次尝试
- `Track A-Stress` 和 `Track B` 继续只作为附录层，不参与主公平结论。

## 主榜单结果

- `GraspVLA`: `14/15`
- `CGN full modular`: `0/15`
- `AnyGrasp full modular`: `0/15`

正式汇总产物：
- `D:\codex\grasp-benchmark\artifacts\reports\track_a_cal_compare_graspvla_cgn_anygrasp_latest\report.md`
- `D:\codex\grasp-benchmark\artifacts\reports\track_a_cal_compare_graspvla_cgn_anygrasp_latest\summary.csv`
- `D:\codex\grasp-benchmark\artifacts\reports\track_a_cal_compare_graspvla_cgn_anygrasp_latest\teacher_summary_zh_clean.md`

对应 parent run：
- `GraspVLA`: `20260405_053120_graspvla_track_a_cal_v1_shared_sim`
- `CGN full modular`: `20260406_115112_cgn_track_a_cal_v1_shared_sim`
- `AnyGrasp full modular`: `20260407_062119_anygrasp_track_a_cal_v1_shared_sim`

## 分任务结果

- `GraspVLA / language_conditioned_single_target_pick`: `10/10`
- `GraspVLA / arbitrary_grasping_common_opaque`: `4/5`
- `CGN full modular / language_conditioned_single_target_pick`: `0/10`
- `CGN full modular / arbitrary_grasping_common_opaque`: `0/5`
- `AnyGrasp full modular / language_conditioned_single_target_pick`: `0/10`
- `AnyGrasp full modular / arbitrary_grasping_common_opaque`: `0/5`

## 失败模式

- `GraspVLA`
  - `1` 个 `task_failure`
- `CGN full modular`
  - `11` 个 `task_failure`
  - `2` 个 `grounding_error: carrot`
  - `2` 个 `grounding_error: power drill`
- `AnyGrasp full modular`
  - `11` 个 `grasp_proposal: AnyGrasp returned no grasp group for the current masked observation`
  - `2` 个 `grounding_error: carrot`
  - `2` 个 `grounding_error: power drill`

## 当前可解释结论

- 在当前冻结的 shared leaderboard 上，`GraspVLA` 明显强于两条已经补完整的 modular baseline。
- 这次主榜单已经不再依赖 raw / interim modular 结果，而是：
  - `GraspVLA`
  - `CGN full modular`
  - `AnyGrasp full modular`
  三者在同一协议下直接比较。
- 两条 modular baseline 的主要瓶颈不同：
  - `CGN` 更常见的是 proposal 之后没有完成成功抓取。
  - `AnyGrasp` 更常见的是经过 object mask 后直接没有产出有效 grasp group。
- `Track B` 里 GraspVLA 的官方 native reference 仍然更高，但它只作为原生部署参考，不和这张公平主榜单混算。

## AnyGrasp 插入状态

- `em14` 上的 license、checkpoint、环境都已经装齐并通过 readiness。
- 最后插入 AnyGrasp 时做了几件必要修复：
  - 从你提供的 Google Drive 资源安装官方 detection / tracking checkpoint
  - 在 `gb-anygrasp` 里补齐 `MinkowskiEngine` 和 `pointnet2`
  - 修正 `None` grasp group，避免被误记成 `scene_execution`
  - 修正失败场景的 latency 统计，保证 `inference_ms` 不是假的 `0`

关键产物：
- readiness: `D:\codex\grasp-benchmark\artifacts\anygrasp\20260407_053602_em14.json`
- 正式 run: `D:\codex\grasp-benchmark\artifacts\runs\20260407_062119_anygrasp_track_a_cal_v1_shared_sim\results.csv`


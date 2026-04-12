# GraspVLA 因素归因更新

## 结论先说

- 之前那个 `Track A-Cal = 0/15` 已经不能代表当前实现。
- 最新正式共享 benchmark 复跑结果是 `14/15`，见 [results.csv](D:/codex/grasp-benchmark/artifacts/runs/20260405_053120_graspvla_track_a_cal_v1_shared_sim/results.csv)。
- 当前官方对齐状态已经到 `reproducibility-limited parity`，不是之前那种明显的 wrapper failure。

## 目前真正测出来的因素贡献

- **2 cm 加长爪子不是主因。**  
  `V1 -> V2` 只从 `0.9833` 降到 `0.9667`，变化只有 `-0.0166`。这说明把官方 `extended finger` 换成 shared plain gripper，影响很小。

- **成功判定是主因之一。**  
  `V2 -> V3` 从 `0.9667` 降到 `0.6500`，变化是 `-0.3167`。也就是说，把官方的 `env done` 换成我们 benchmark 的 `lift >= 15 cm 且 hold >= 2 s`，会带来很明显的成功率下降。

- **“官方 scene edit” 这项还没有被干净量化。**  
  `V4` 目前不是低分，而是直接因为 state-length mismatch 跑不起来。也就是说，官方公开 release 里的部分 LIBERO 任务和 `process_initial_state / basket removal` 这类逻辑是绑在一起的。这个因素还要单独补一个可运行的对齐子集才能真正测干净。

- **之前 shared benchmark 全 0，不是因为场景本身太难。**  
  最新正式 `Track A-Cal` 复跑已经是 `14/15`，见 [report.md](D:/codex/grasp-benchmark/artifacts/reports/track_a_cal_graspvla_refresh_20260405_v2/report.md)。所以之前的 `0/15` 更像是旧实现阶段的结果，不是当前 shared calibration 场景真的不可做。

## 现在最合理的判断

- 如果问题是“是不是 2 cm 爪子导致结果差很多”，答案是：**不是**。
- 如果问题是“是不是 stricter success rule 导致结果差很多”，答案是：**是，而且影响很大**。
- 如果问题是“是不是换了物体/场景就导致 shared benchmark 完全不行”，答案是：**至少对当前 `Track A-Cal` 不是**，因为它现在已经能做到 `14/15`。
- 当前唯一还没被干净拆开的主要因素，是 **官方 scene edits**。下一步最值得做的是把 `V4_no_method_specific_scene_edits` 修到能在 official-aligned subset 上跑起来。

# GraspVLA 边界与因子拆解（2026-04-05）

## 结论先说

- 之前那种“官方 native 很高，shared benchmark 全 0”的讲法已经不再准确。
- 最新正式 `Track A-Cal` 已经是 `15/15`，所以旧的 `Track A-Cal = 0/15` 应该视为旧实现阶段的结果，而不是当前 benchmark 的真实状态。
- 当前官方对齐状态已经是 `reproducibility-limited parity`，说明 wrapper 和公开 release 已经非常接近，剩下的问题比之前小很多。

## 证据

- 官方 native 参考：
  - [summary.json](D:/codex/grasp-benchmark/artifacts/official_sim/20260402_231726_em14_full/summary.json)
- 全 official 子集的因子审计：
  - [report.md](D:/codex/grasp-benchmark/artifacts/audits/20260404_223758_graspvla_official_alignment/report.md)
  - [success_delta.csv](D:/codex/grasp-benchmark/artifacts/audits/20260404_223758_graspvla_official_alignment/success_delta.csv)
- scene-edit 兼容性探针：
  - [scene_edit_compatibility_probe_20260405_summary.csv](D:/codex/grasp-benchmark/artifacts/audits/scene_edit_compatibility_probe_20260405_summary.csv)
- 只保留 `libero_goal` 的官方对齐审计：
  - [report.md](D:/codex/grasp-benchmark/artifacts/audits/20260405_021725_graspvla_official_alignment/report.md)
  - [success_delta.csv](D:/codex/grasp-benchmark/artifacts/audits/20260405_021725_graspvla_official_alignment/success_delta.csv)
- 最新正式 `Track A-Cal`：
  - [results.csv](D:/codex/grasp-benchmark/artifacts/runs/20260405_001205_graspvla_track_a_cal_v1_shared_sim/results.csv)
  - [report.md](D:/codex/grasp-benchmark/artifacts/reports/track_a_cal_graspvla_refresh_20260405/report.md)

## 到底哪个因素影响最大

### 在完整 official 子集上

| 因素 | 转换 | 变化 | 解释 |
| --- | --- | --- | --- |
| `extended finger -> shared gripper` | `V1 -> V2` | `-0.0166` | 很小 |
| `env done -> lift >= 15 cm 且 hold >= 2 s` | `V2 -> V3` | `-0.3167` | 目前能干净测出的最大下降 |
| `关闭官方 scene edits` | `V3 -> V4` | 还不能干净量化 | basket 相关任务在公开 release 里会直接变成兼容性问题 |

这里最重要的一句是：**`2 cm` 加长爪子不是之前巨大差距的主因。**  
目前在完整 official 子集上，影响最大的可测因素是更严格的 shared success rule。

### 在 scene-edit 可兼容子集上（只看 `libero_goal`）

为了把 scene edit 这个因素单独测干净，我又只用官方 `libero_goal` 子集重跑了一遍。

| 因素 | 转换 | 变化 | 解释 |
| --- | --- | --- | --- |
| `extended finger -> shared gripper` | `V1 -> V2` | `+0.0500` | 小到中等，而且这里并没有变差 |
| `env done -> lift >= 15 cm 且 hold >= 2 s` | `V2 -> V3` | `-0.0500` | 中等 |
| `官方 scene edits -> 不做 method-specific scene edits` | `V3 -> V4` | `-0.0500` | 在这个可兼容子集上是中等影响 |

这个结果说明两件事：

- 对于本来就能不靠官方 scene edit 正常运行的任务，scene edit 的影响是**真实存在但不算特别大**。
- 对于 basket 相关任务，scene edit 不只是影响成功率，而是会直接变成**能不能对齐运行**的兼容性门槛。

## 为什么完整 official 子集里的 `V4` 会失败

兼容性探针已经把这个问题测出来了：

- `libero_object` task `0` 和 `1`：`0/10` raw-state compatible，`10/10` processed-state compatible
- `libero_10` task `0` 和 `1`：`0/10` raw-state compatible，`10/10` processed-state compatible
- `libero_goal` task `1` 和 `2`：`10/10` raw-state compatible，`10/10` processed-state compatible

所以当前公开 release 的边界很清楚：

- `libero_goal` 这两个选中的任务，可以直接用来测 scene-edit 的性能影响。
- `libero_object` 和 `libero_10` 这几个 basket 任务，如果不走官方 `process_initial_state`，就不能做干净的一对一无 scene-edit 对照。

## 这对 benchmark 的含义

- `Track B` 继续代表公开 GraspVLA release 的原生上限。
- `official_aligned` 现在说明 wrapper 已经足够接近公开 release，剩下的不确定性不再是主要矛盾。
- `Track A-Cal` 仍然要谨慎使用，但当前 shared calibration scenes 本身显然是可跑的，因为最新正式结果已经是 `15/15`。

## 最后的实际判断

- 如果问题是“是不是 `2 cm` 爪子导致差距这么大”，答案是：**不是**。
- 如果问题是“是不是更严格的 shared success rule 导致差距很大”，答案是：**是，而且影响明显**。
- 如果问题是“official scene edits 重不重要”，答案是：**重要**，但要分两层：
  - 对 `libero_goal` 来说，它带来的是中等程度的性能变化
  - 对 basket 相关官方任务来说，它还是公开 release 的兼容性门槛
- 如果问题是“之前 shared 全 0 是否说明 benchmark 场景根本不合理”，答案是：**不是**。最新正式 `Track A-Cal` 已经是 `15/15`。

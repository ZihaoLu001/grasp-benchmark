# Benchmark 完整结果文档（2026-04-11）

## 0. 阅读说明

这份文档把当前仓库里已经跑出的 benchmark 结果按同一口径整理成一份完整版本，目的是避免下面几类数字被混在一起：

- `Track A-Cal` 主公平榜单
- `Track A-Stress` 共享压力测试
- `Track B` 官方 native reference
- transparent 子集专项对比
- GraspVLA 官方对齐 / 边界诊断

当前统一口径是：

- `Track A-Cal` 才是主公平结论
- `Track A-Stress` 是共享协议下的压力测试附录
- `Track B` 只代表官方原生部署参考，不参与公平主结论

## 1. 当前完成状态

截至 `2026-04-11`，benchmark 中已经完成的主要 simulation 结果包括：

- `Track A-Cal` 三方法主榜单
- `Track A-Stress` 的非 `AnyGrasp` 完整结果
- transparent shared 子集的 `GraspVLA vs CGN` 对比
- `GraspVLA` 官方 `Track B` native simulation reference
- `GraspVLA` 官方对齐审计与边界 / 因子归因

当前仍未完成的部分是：

1. `AnyGrasp` transparent 子集与 stress 插入
2. real-world pilot 正式 benchmark 数字
3. Phase 2 constraint / affordance grasping
4. modular `Track B` native best-case references

其中最直接的阻塞是：

- 当前 `AnyGrasp` license 和现在 `em14` 的 machine feature id 不匹配，所以新的 AnyGrasp simulation 不能继续正式插入

## 2. Track A-Cal 主公平榜单

### 2.1 任务定义

`Track A-Cal` 用的是冻结的 `track_a_cal_v1`，目标是做共享协议下的主公平表。

协议固定为：

- 同一套双固定相机
- 同一 shared gripper
- 同一 workspace
- 同一 blocking control
- 成功判定：`lift >= 15 cm` 且 `hold >= 2 s`
- 每个 trial 最多 `3` 次尝试

任务包括：

1. `language_conditioned_single_target_pick`
2. `arbitrary_grasping_common_opaque`

### 2.2 主结果

主报告：

- `D:/codex/grasp-benchmark/artifacts/reports/track_a_cal_compare_graspvla_cgn_anygrasp_latest/report.md`

汇总结果如下：

| method | method_tier | task | trials | success_rate | mean_spl | mean_attempts | mean_inference_ms | mean_cycle_time_s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `graspvla` | `graspvla_official` | `language_conditioned_single_target_pick` | `10` | `1.0` | `1.0` | `1.0` | `236.2949` | `11.4128` |
| `graspvla` | `graspvla_official` | `arbitrary_grasping_common_opaque` | `5` | `0.8` | `0.5667` | `2.0` | `243.7593` | `50.6528` |
| `cgn` | `cgn_full_modular` | `language_conditioned_single_target_pick` | `10` | `0.0` | `0.0` | `3.0` | `2055.8215` | `511.0761` |
| `cgn` | `cgn_full_modular` | `arbitrary_grasping_common_opaque` | `5` | `0.0` | `0.0` | `3.0` | `4243.1942` | `885.1093` |
| `anygrasp` | `anygrasp_full_modular` | `language_conditioned_single_target_pick` | `10` | `0.0` | `0.0` | `3.0` | `1897.8013` | `23.5386` |
| `anygrasp` | `anygrasp_full_modular` | `arbitrary_grasping_common_opaque` | `5` | `0.0` | `0.0` | `3.0` | `1869.7237` | `22.4482` |

如果按方法汇总成最直观的主榜单：

- `GraspVLA`: `14/15`
- `CGN full modular`: `0/15`
- `AnyGrasp full modular`: `0/15`

### 2.3 按 condition 拆分

`Track A-Cal` 的 condition 结果如下：

| method | task | condition | trials | success_rate | mean_attempts |
| --- | --- | --- | --- | --- | --- |
| `graspvla` | `language_conditioned_single_target_pick` | `basic` | `5` | `1.0` | `1.0` |
| `graspvla` | `language_conditioned_single_target_pick` | `distractors_light` | `5` | `1.0` | `1.0` |
| `graspvla` | `arbitrary_grasping_common_opaque` | `opaque_basic` | `5` | `0.8` | `2.0` |
| `cgn` | `language_conditioned_single_target_pick` | `basic` | `5` | `0.0` | `3.0` |
| `cgn` | `language_conditioned_single_target_pick` | `distractors_light` | `5` | `0.0` | `3.0` |
| `cgn` | `arbitrary_grasping_common_opaque` | `opaque_basic` | `5` | `0.0` | `3.0` |
| `anygrasp` | `language_conditioned_single_target_pick` | `basic` | `5` | `0.0` | `3.0` |
| `anygrasp` | `language_conditioned_single_target_pick` | `distractors_light` | `5` | `0.0` | `3.0` |
| `anygrasp` | `arbitrary_grasping_common_opaque` | `opaque_basic` | `5` | `0.0` | `3.0` |

### 2.4 失败模式

主榜单 failure taxonomy：

- `GraspVLA`
  - `task_failure`: `1`
- `CGN full modular`
  - `grounding_error: carrot`: `2`
  - `grounding_error: power drill`: `2`
  - `task_failure`: `11`
- `AnyGrasp full modular`
  - `grounding_error: carrot`: `2`
  - `grounding_error: power drill`: `2`
  - `grasp_proposal: no grasp group`: `11`

### 2.5 主榜单解释

当前主榜单能支持的结论是：

- 在冻结的共享 calibration 协议下，`GraspVLA` 明显强于当前已接好的两条 modular baseline
- `CGN` 和 `AnyGrasp` 不是同一种失败：
  - `CGN` 更多是找到目标或拿到 proposal 后，最后仍然落在 `task_failure`
  - `AnyGrasp` 更多是 masked observation 后直接没有有效 grasp group

## 3. Track A-Stress 共享压力测试

### 3.1 任务定义

`Track A-Stress` 当前使用冻结的 `track_a_v2`，包括：

1. `language_conditioned_single_target_pick`
   - `basic`
   - `lighting`
   - `background`
   - `distractors`
   - `height`
2. `arbitrary_grasping_transparent`
3. `arbitrary_grasping_common_opaque`

总 trial 数：

- `25 + 4 + 5 = 34`

### 3.2 当前正式结果

当前正式 stress 报告：

- `D:/codex/grasp-benchmark/artifacts/reports/track_a_stress_compare_graspvla_cgn_latest/report.md`

汇总如下：

| method | method_tier | task | trials | successes | success_rate | mean_attempts | mean_inference_ms | mean_cycle_time_s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `graspvla` | `graspvla_official` | `language_conditioned_single_target_pick` | `25` | `23` | `0.92` | `1.28` | `401.6482` | `34.6461` |
| `graspvla` | `graspvla_official` | `arbitrary_grasping_transparent` | `4` | `4` | `1.0` | `1.5` | `407.0621` | `56.4412` |
| `graspvla` | `graspvla_official` | `arbitrary_grasping_common_opaque` | `5` | `5` | `1.0` | `1.2` | `406.8874` | `40.0354` |
| `cgn` | `cgn_full_modular` | `language_conditioned_single_target_pick` | `25` | `0` | `0.0` | `3.0` | `4465.0122` | `652.3304` |
| `cgn` | `cgn_full_modular` | `arbitrary_grasping_transparent` | `4` | `0` | `0.0` | `3.0` | `3609.4545` | `1039.7376` |
| `cgn` | `cgn_full_modular` | `arbitrary_grasping_common_opaque` | `5` | `0` | `0.0` | `3.0` | `3125.8620` | `862.4596` |

如果按方法总数来读：

- `GraspVLA total`: `32/34`
- `CGN full modular total`: `0/34`

### 3.3 按 condition 拆分

stress 条件拆分里，`GraspVLA` 的语言任务结果是：

| condition | trials | successes | success_rate | mean_attempts |
| --- | --- | --- | --- | --- |
| `basic` | `5` | `5` | `1.0` | `1.0` |
| `lighting` | `5` | `5` | `1.0` | `1.0` |
| `background` | `5` | `5` | `1.0` | `1.0` |
| `distractors` | `5` | `3` | `0.6` | `2.0` |
| `height` | `5` | `5` | `1.0` | `1.4` |

同时：

- `arbitrary_grasping_transparent`: `4/4`
- `arbitrary_grasping_common_opaque`: `5/5`

`CGN` 在所有这些条件下当前都是 `0`。

### 3.4 失败模式

stress failure taxonomy：

- `GraspVLA`
  - `task_failure`: `2`
- `CGN full modular`
  - `grounding_error: mustard bottle`: `1`
  - `grounding_error: power drill`: `5`
  - `task_failure`: `28`

### 3.5 当前 stress 口径的重要更新

这里最重要的一点是：

- 历史早期 artifact 里曾经出现过 `GraspVLA = 0/34`
- 那已经不是当前 shared simulation lane 的真实状态
- 在修好 shared runner 之后，当前正式 `track_a_v2` stress 结果是 `GraspVLA = 32/34`

所以以后不能再把历史 `0/34` 当作当前 stress 主结论。

## 4. Transparent shared 子集专项结果

### 4.1 结果定位

transparent 子集不是 `Track A-Cal` 主榜单，也不是 `Track B`。  
它的作用是单独看透明 proxy assets 上的方法差异。

当前报告：

- `D:/codex/grasp-benchmark/artifacts/reports/track_a_transparent_compare_graspvla_cgn_latest/report.md`

### 4.2 汇总结果

| method | task | trials | successes | success_rate | mean_attempts | mean_inference_ms | mean_lift_cm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `graspvla` | `arbitrary_grasping_transparent` | `4` | `4` | `1.0` | `1.0` | `408.6251` | `16.4656` |
| `cgn` | `arbitrary_grasping_transparent` | `4` | `0` | `0.0` | `3.0` | `4197.7748` | `0.3537` |

### 4.3 分场景结果

| scene | object | GraspVLA | CGN | 说明 |
| --- | --- | --- | --- | --- |
| `transparent__001` | `clear_plastic_cup` | `1/1`, `lift=20.0384 cm` | `0/3`, `lift=1.0008 cm` | CGN 有 proposal，但没有满足 success rule |
| `transparent__002` | `glass_bottle` | `1/1`, `lift=15.1924 cm` | `0/3`, `lift=1.1253 cm` | 模式相同 |
| `transparent__003` | `wine_glass` | `1/1`, `lift=15.4043 cm` | `0/3`, `lift=-1.8161 cm` | CGN 行来自单场景补跑 |
| `transparent__004` | `acrylic_box` | `1/1`, `lift=15.2272 cm` | `0/3`, `lift=1.1048 cm` | CGN 行来自单场景补跑 |

### 4.4 结果解释

transparent 子集最有用的地方在于，它能把：

- “有没有 detection / proposal”
- 和
- “最后有没有真正达到 benchmark 成功标准”

分开看。

当前 `CGN` 在 transparent 上不是纯 setup 崩溃，而是：

- 前面 pipeline 可以跑
- 但最终没有把 proposal 转成满足共享成功标准的 pickup

## 5. Track B 官方 native reference

### 5.1 定位

`Track B` 不是公平主榜单。  
它只代表官方 `GraspVLA` release 在作者原生部署协议下的表现上限。

对应 artifact：

- `D:/codex/grasp-benchmark/artifacts/official_sim/20260402_231726_em14_full/summary.json`

### 5.2 官方 native 结果

| benchmark | trials | successes | success_rate |
| --- | --- | --- | --- |
| `playground` | `10` | `8` | `0.8` |
| `libero_10` | `350` | `325` | `0.929` |
| `libero_goal` | `350` | `336` | `0.960` |
| `libero_object` | `500` | `482` | `0.964` |

### 5.3 当前应如何理解

`Track B` 说明的是：

- 官方 release 在作者原生相机 / gripper / scene edit / success semantics 下可以达到什么上限

它**不能**直接拿来当 shared benchmark 的公平结论。

## 6. GraspVLA 官方对齐、边界与因子归因

### 6.1 当前对齐状态

对齐审计报告：

- `D:/codex/grasp-benchmark/artifacts/audits/20260404_223758_graspvla_official_alignment/report.md`

当前结论是：

- `parity_status = reproducibility-limited parity`

也就是：

- 我们 wrapper 和官方公开 release 已经足够接近
- 剩余 mismatch 数量已经和官方自己重复跑的漂移处于同量级

比较摘要：

| comparison | expected_trials | mismatches |
| --- | --- | --- |
| `V0_official_runner vs V0_repeat_official_runner` | `65` | `3` |
| `V0_official_runner vs V1_wrapper_official_parity` | `65` | `3` |

### 6.2 因子归因

从 `success_delta.csv` 看，主要因子变化是：

| transition | factor | success_rate_delta | interpretation |
| --- | --- | --- | --- |
| `V1 -> V2` | `gripper_effect` | `-0.0166` | 几乎没有影响 |
| `V2 -> V3` | `success_rule_effect` | `-0.3167` | 明显影响 |
| `V3 -> V4` | `scene_edit_effect` | `-0.6500` | 强候选瓶颈，但伴随分布变化 |

如果只看可兼容的 `libero_goal` 子集，scene edit effect 会收缩到中等量级：

| transition | factor | success_rate_delta |
| --- | --- | --- |
| `V1 -> V2` | `gripper_effect` | `+0.05` |
| `V2 -> V3` | `success_rule_effect` | `-0.05` |
| `V3 -> V4` | `scene_edit_effect` | `-0.05` |

### 6.3 当前可用的解释

这部分当前最稳的结论是：

1. `2 cm extended finger` 不是之前巨大差距的主因
2. shared success rule 的确会明显拉低分数
3. scene edit 对 basket 相关任务不仅影响性能，还会影响任务兼容性
4. 当前 `GraspVLA` 的 shared 协议主弱点更像是：
   - shared protocol / distribution gap
   - 尤其是更复杂 clutter / distractors 条件

## 7. 当前最典型的弱点和强项

### 7.1 GraspVLA

当前最明显的强项：

- `Track A-Cal` 语言抓取：`10/10`
- `Track A-Stress` transparent：`4/4`
- `Track A-Stress` common opaque arbitrary：`5/5`

当前最明显的弱点：

- `Track A-Stress / language_conditioned_single_target_pick / distractors`: `3/5`

也就是说，在当前 repo 这套 benchmark 下，`GraspVLA` 最敏感的不是 transparent，而是更强的 clutter / distractors 语言场景。

### 7.2 CGN full modular

当前最明显的问题不是单一一个 setup bug，而是两层问题叠加：

1. 语言任务里有 `GroundingDINO` 目标定位 miss
   - 当前最明显的是 `power drill`
2. 大多数剩余场景里，即使 pipeline 能往后跑，最后仍然落在 `task_failure`

### 7.3 AnyGrasp

当前已保留的主榜单结果是：

- `Track A-Cal`: `0/15`

但新一轮 AnyGrasp 插入目前被 license 阻塞：

- 旧 license 对应旧的 `em14 feature id`
- 当前 `em14` 的 feature id 已变化

因此当前 AnyGrasp 不能继续补 transparent 或 stress。

## 8. 还没完成的 benchmark 部分

截至当前，仍未完成的是：

1. `AnyGrasp` transparent 子集
2. `AnyGrasp` stress 插入
3. real-world pilot 正式 benchmark 数字
4. Phase 2 constraint / affordance grasping
5. modular `Track B` native best-case references

## 9. 一句话总总结

如果把当前 benchmark 的所有已完成部分合并成一句话：

- `GraspVLA` 在当前冻结的 shared benchmark 里，主榜单 `Track A-Cal = 14/15`，完整 non-AnyGrasp stress `Track A-Stress = 32/34`，transparent 子集 `4/4`
- `CGN full modular` 在当前 shared protocol 下主榜单 `0/15`，stress `0/34`，transparent `0/4`
- `AnyGrasp` 的历史主榜单结果是 `0/15`，但当前新评测被 license 阻塞
- 官方 `Track B` native reference 仍然很高，但它只作为原生上限参考，不参与公平主结论

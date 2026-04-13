# Benchmark 最新权威结果总汇（2026-04-13）

## 作用说明

这份文件是当前仓库里**唯一一份建议直接给导师/合作方看的 benchmark 总汇**。

本文件只纳入两类结果：

- 已完成并冻结的 **canonical benchmark runs**
- 已完成并冻结的 **protocol / official-reference 审计结果**

本文件**不纳入**以下内容：

- 已知带 bug 的历史 run
- 仅 smoke 的 appendix run
- 仍在执行中的 rerun
- 尚未完成的 AnyGrasp / 真机 / Phase 2 后续扩展

换句话说，下面的数字是当前最稳、最干净、最适合作为汇报口径的一版。

## 当前纳入本版总汇的 canonical artifacts

| 类别 | 方法 | task set / 审计 | parent run / artifact |
| --- | --- | --- | --- |
| 主公平榜单 | GraspVLA | `track_a_cal_v3` | `20260413_101557_graspvla_track_a_cal_v3_shared_sim` |
| 主公平榜单 | CGN shared | `track_a_cal_v3` | `20260413_093449_cgn_track_a_cal_v3_shared_sim` |
| hardest-slice appendix | GraspVLA | `track_a_stress_v4` | `20260413_043355_graspvla_track_a_stress_v4_shared_sim` |
| hardest-slice appendix | CGN shared | `track_a_stress_v4` | `20260413_093449_cgn_track_a_stress_v4_shared_sim` |
| instruction robustness | GraspVLA | `instruction_robustness_v2` | `20260413_121126_graspvla_instruction_robustness_v2_shared_sim` |
| instruction robustness | CGN shared | `instruction_robustness_v2` | `20260413_093449_cgn_instruction_robustness_v2_shared_sim` |
| task-oriented extension | GraspVLA | `phase2_pilot_v1` | `20260413_023012_graspvla_phase2_pilot_v1_shared_sim` |
| task-oriented extension | CGN shared | `phase2_pilot_v1` | `20260413_064416_cgn_phase2_pilot_v1_shared_sim` |
| 官方对齐审计 | GraspVLA | official alignment | `20260405_042741_graspvla_official_alignment` |
| 协议敏感性审计 | GraspVLA | `protocol_probe_v2` | `20260412_080241_graspvla_protocol_probe_v2` |
| 官方 native reference | GraspVLA | official Track B | `artifacts/official_sim/20260402_231726_em14_full/summary.json` |

## 不纳入本版总汇的结果

下面这些结果当前**不进入本版正式总表**：

1. `GraspVLA sim2real_proxy_v2`
原因：clean rerun 已启动，但最新 canonical run 还没完整落完。

2. `CGN track_b_cgn_native_v2`
原因：新的全量 native-like appendix 仍在执行，当前只有旧 smoke `0/2`，不适合作为最终结论。

3. `CGN bottleneck_v2`
原因：新的全量 bottleneck audit 已启动，但当前还没完全冻结；旧的 `1` scene smoke 不应混入最终结论。

4. `AnyGrasp`
原因：缺新的 node-matched license。

## 一页结论

当前最稳的结论是：

1. **公开发布的 GraspVLA native 数字不能直接当作 fair benchmark claim。**
2. **在冻结 shared protocol 下，当前 public GraspVLA 在 simulator 里显著强于当前 public CGN shared lane。**
3. **CGN 的低分不是单一 bug，也不只是 detector 问题；shared lane 下主要掉在 scene execution / grasp proposal / task completion 这几层。**
4. **GraspVLA 对双视角高度敏感，但在当前 shared protocol 下对 hardest slices 仍然表现稳定。**
5. **当前尚未冻结的主要缺口是 `sim2real_proxy_v2` clean canonical、CGN native-like appendix 全量，以及 CGN bottleneck_v2 全量。**

## 1. Track A-Cal v3：唯一 headline fair table

协议固定为：

- 双固定视角
- shared gripper
- shared workspace
- blocking control
- `lift >= 15 cm`
- `hold >= 2 s`
- 每个 trial 最多 `3` 次尝试

### 1.1 总体结果

| 方法 | successes / trials | success rate |
| --- | --- | --- |
| GraspVLA | `88 / 90` | `97.78%` |
| CGN shared | `0 / 90` | `0.00%` |

### 1.2 按条件拆分

| 方法 | condition | successes / trials |
| --- | --- | --- |
| GraspVLA | `basic` | `30 / 30` |
| GraspVLA | `distractors_light` | `30 / 30` |
| GraspVLA | `opaque_basic` | `28 / 30` |
| CGN shared | `basic` | `0 / 30` |
| CGN shared | `distractors_light` | `0 / 30` |
| CGN shared | `opaque_basic` | `0 / 30` |

### 1.3 失败形态

GraspVLA：

- `success = 88`
- `task_failure = 2`

CGN shared：

- `scene_execution = 75`
- `task_failure = 13`
- `grounding_error = 2`

结论：

- GraspVLA 在主公平榜单上接近满分，但不是绝对 `90 / 90`
- CGN shared 当前不是“偶尔失败”，而是在主榜单上系统性为 `0 / 90`

## 2. Track A-Stress v4：hardest-slice appendix

### 2.1 总体结果

| 方法 | successes / trials | success rate |
| --- | --- | --- |
| GraspVLA | `160 / 168` | `95.24%` |
| CGN shared | `0 / 168` | `0.00%` |

### 2.2 按 hardest slices 拆分

| 方法 | condition | successes / trials |
| --- | --- | --- |
| GraspVLA | `distractors_heavy` | `39 / 40` |
| GraspVLA | `occlusion_bank` | `40 / 40` |
| GraspVLA | `opaque_clutter` | `38 / 40` |
| GraspVLA | `transparent_pose_bank` | `43 / 48` |
| CGN shared | `distractors_heavy` | `0 / 40` |
| CGN shared | `occlusion_bank` | `0 / 40` |
| CGN shared | `opaque_clutter` | `0 / 40` |
| CGN shared | `transparent_pose_bank` | `0 / 48` |

### 2.3 失败形态

GraspVLA：

- `success = 160`
- `task_failure = 8`

CGN shared：

- `scene_execution = 145`
- `grasp_proposal = 11`
- `task_failure = 7`
- `grounding_error = 3`
- `legacy_runtime = 2`

结论：

- GraspVLA 在 hardest slices 下仍然维持高成功率
- 它最明显的掉点出现在 `transparent_pose_bank` 与 `opaque_clutter`
- CGN shared 在 hardest slices 下仍为 `0 / 168`

## 3. Instruction Robustness v2

### 3.1 总体结果

| 方法 | successes / trials | success rate |
| --- | --- | --- |
| GraspVLA | `38 / 40` | `95.00%` |
| CGN shared | `0 / 40` | `0.00%` |

### 3.2 按 instruction family 拆分

| 方法 | instruction family | successes / trials |
| --- | --- | --- |
| GraspVLA | `canonical` | `10 / 10` |
| GraspVLA | `lexical_paraphrase` | `10 / 10` |
| GraspVLA | `distractor_aware_disambiguation` | `10 / 10` |
| GraspVLA | `compositional_paraphrase` | `8 / 10` |
| CGN shared | `canonical` | `0 / 10` |
| CGN shared | `lexical_paraphrase` | `0 / 10` |
| CGN shared | `compositional_paraphrase` | `0 / 10` |
| CGN shared | `distractor_aware_disambiguation` | `0 / 10` |

### 3.3 失败说明

GraspVLA 的两个失败都发生在 `compositional_paraphrase`：

- `banana / distractors_light`
- `power_drill / basic`

而且它们都不是系统故障，而是：

- `grounding_success = 1`
- `proposal_nonempty = 1`
- `plan_success = 1`
- 但 `lift_only_success = 0`
- 因而最终落成正常 `task_failure`

结论：

- 在当前 prompt 改写套件下，GraspVLA 的主要脆弱点不是 lexical 改写，而是更组合式的表述
- 这是一类真实的语义到执行 gap，而不是环境崩溃

## 4. Phase 2 Pilot v1：task-oriented extension

### 4.1 总体结果

| 方法 | successes / trials | success rate |
| --- | --- | --- |
| GraspVLA | `23 / 24` | `95.83%` |
| CGN shared | `0 / 24` | `0.00%` |

### 4.2 按任务拆分

| 方法 | task | successes / trials |
| --- | --- | --- |
| GraspVLA | `mug_handle_grasp` | `8 / 8` |
| GraspVLA | `avoid_inside_cup` | `8 / 8` |
| GraspVLA | `power_drill_handle_grasp` | `7 / 8` |
| CGN shared | `mug_handle_grasp` | `0 / 8` |
| CGN shared | `avoid_inside_cup` | `0 / 8` |
| CGN shared | `power_drill_handle_grasp` | `0 / 8` |

### 4.3 失败形态

GraspVLA：

- `task_failure = 1`

CGN shared：

- `grasp_proposal = 16`
- `task_failure = 8`

结论：

- GraspVLA 已经不仅在“抓起来”这一层表现好，在当前小型 affordance extension 里也能稳定过大多数场景
- CGN shared 在这类 part-sensitive task 上依然没有建立有效 baseline

## 5. 官方对齐与协议敏感性审计

### 5.1 GraspVLA 官方对齐审计

当前官方对齐结论是：

- `status = reproducibility-limited parity`

也就是：

- wrapper 和官方 release 的差异已经不高于官方自己重复运行时的漂移

关键数字：

| 比较 | mismatch |
| --- | --- |
| `V0_official_runner vs V0_repeat_official_runner` | `1 / 20` |
| `V0_official_runner vs V1_wrapper_official_parity` | `1 / 20` |

这说明：

- 当前 shared benchmark 里的差距主要不是“wrapper 明显接错了”
- 更大来源是 protocol / distribution shift

### 5.2 Protocol Probe v2

| variant | successes / trials | 说明 |
| --- | --- | --- |
| `P0_shared_baseline` | `24 / 24` | 当前 shared baseline |
| `P1_front_only_duplicate` | `14 / 24` | 去掉双视角，明显下降 |
| `P2_attempt_budget_1` | `20 / 24` | 预算从 3 次降到 1 次 |
| `P3_relaxed_success` | `24 / 24` | 放宽成功定义 |
| `P4_camera_jitter_low` | `24 / 24` | 轻微外参扰动 |

最关键结论：

- **双视角最敏感**
- `front-only duplicate` 会把成功率从 `24 / 24` 直接拉到 `14 / 24`
- 轻微 camera jitter 对当前 shared baseline 影响不大

## 6. 官方 Track B Native Reference

这部分不是 fair benchmark，只是 GraspVLA 官方原生栈的参考上限。

### 6.1 Playground

| benchmark | successes / trials |
| --- | --- |
| `playground` | `8 / 10` |

### 6.2 LIBERO

| benchmark | successes / trials | success rate |
| --- | --- | --- |
| `libero_object` | `482 / 500` | `96.4%` |
| `libero_10` | `325 / 350` | `92.9%` |
| `libero_goal` | `336 / 350` | `96.0%` |

解释口径应固定为：

- 这是 GraspVLA 官方 native / method-favored reference
- 不能与 shared fair table 混算

## 7. 关于 CGN：当前能稳到哪一步

当前最稳的说法是：

1. 我们确实直接使用了官方 `Contact-GraspNet` proposal 模块
2. 但整个 baseline 仍然是一个 **repo-owned modular assembly**
3. 因此当前结果能支持的是：
   - public CGN under our frozen benchmark protocol 很弱
   - 低分不只来自 detector
   - 但不能直接夸大成“官方 canonical CGN full system 在任何设置下都一样差”

从已冻结结果看，CGN shared 的主要失败分布是：

- `scene_execution`
- `grasp_proposal`
- `task_failure`
- 少量 `grounding_error`

这和我们前面的诊断是一致的：

- 不是单一 detector 问题
- 不是只因为成功定义太严
- 更大瓶颈在 proposal / planner / execution contract 这一层

## 8. 当前尚未冻结、因此未纳入本版总表的条目

### 8.1 GraspVLA `sim2real_proxy_v2`

clean rerun 已经启动：

- `20260413_122605_graspvla_sim2real_proxy_v2_shared_sim`

当前已确认：

- 旧的 style-key bug 已修
- 旧的 runtime category registration bug 已修
- 远端 episode 失败已不再是 `AssertionError` / `KeyError`

但因为 run 仍未完整结束，**本版总汇不写入最终 success/trial 数字**。

### 8.2 CGN native-like appendix

新的全量 run 已启动：

- `20260413_121126_cgn_track_b_cgn_native_v2_shared_sim`

但尚未冻结，因此不纳入本版正式总表。

### 8.3 CGN bottleneck v2

新的全量 audit 已启动：

- `20260413_121126_cgn_bottleneck_v2`

但尚未冻结，因此本版只保留概念性结论，不写新数值。

## 9. 本版汇报时最建议的 6 句话

1. 当前 fair shared benchmark 的 headline table 是 `Track A-Cal v3`，结果是 `GraspVLA 88/90`，`CGN shared 0/90`。
2. hardest slices 的 `Track A-Stress v4` 里，GraspVLA 仍是 `160/168`，CGN shared 仍是 `0/168`。
3. 语言鲁棒性套件 `instruction_robustness_v2` 里，GraspVLA 是 `38/40`，主要掉在 compositional paraphrase。
4. 小型 affordance extension `phase2_pilot_v1` 里，GraspVLA 是 `23/24`，CGN shared 仍是 `0/24`。
5. 官方对齐审计表明当前 wrapper 已到 `reproducibility-limited parity`，shared benchmark 的差距主要不是代码接错，而是 protocol / distribution shift。
6. 当前尚未冻结的主要条目是 `sim2real_proxy_v2` clean rerun、CGN native-like appendix 全量和 CGN bottleneck_v2 全量，因此它们没有写进这一版最终总表。


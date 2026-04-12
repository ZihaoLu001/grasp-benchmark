# CoRL 仿真阶段已核实结果总览（2026-04-12）

## 1. 这份文档的口径

这份文档只总结已经完成、已经复核、并且可以直接用于导师/合作方讨论的 **simulator** 结果。

我在写这份文档时额外做了三件核查：

1. 重新检查了 `GraspVLA` 与 `CGN` 的完整 `Track A-Cal v2` / `Track A-Stress v2` 产物覆盖，确认不是 smoke 或 mock。
2. 把 `CGN native appendix` 中唯一一次 `OOM` 的场景单独在独占 GPU 上重跑，确认它本身仍然失败，因此 native lane 的低分不是由那次集群资源噪声“抹黑”出来的。
3. 修复了 `paper_bundle` 的配对统计 bug：此前统计只按 `scene_recipe_id` 配对，会把 `v2` 任务集的 replicate 误判成重复覆盖；现在已经改成按 `scene_recipe_id + replicate_index + seed` 配对，统计表才是可信的。

## 2. 当前真正完成了哪些 benchmark 部分

已经完成并核实的部分：

- `Track A-Cal v2` shared benchmark
- `Track A-Stress v2` shared stress appendix
- `GraspVLA protocol_probe_v2`
- `CGN bottleneck_v1`
- `GraspVLA official alignment audit`
- `Track B` 的官方 `GraspVLA native reference`
- `track_b_cgn_native_v1` 的 `CGN native appendix`

还没有完成的部分：

- `AnyGrasp`：缺新的 node-matched license
- real-world pilot
- `Phase 2 constraint / affordance grasping`

## 3. 主公平榜单：Track A-Cal v2

`Track A-Cal v2` 是当前唯一的主公平榜单。它固定了：

- 双固定视角
- shared gripper
- shared workspace
- blocking control
- `lift >= 15 cm` 且 `hold >= 2 s`
- 每个 trial 最多 3 次尝试

### 3.1 总体 headline

| Method | Task Group | Success |
| --- | --- | --- |
| GraspVLA | overall | `59 / 60` |
| CGN full modular | overall | `0 / 60` |

更细分的结果：

| Method | Task | Success |
| --- | --- | --- |
| GraspVLA | language-conditioned single-target pick | `40 / 40` |
| GraspVLA | arbitrary common opaque grasping | `19 / 20` |
| CGN full modular | language-conditioned single-target pick | `0 / 40` |
| CGN full modular | arbitrary common opaque grasping | `0 / 20` |

配对统计：

- paired scenes: `60`
- `GraspVLA vs CGN` 的 exact McNemar test: `p = 0.0`
- paired bootstrap success-rate delta: `[-1.0, -0.95]`

也就是说，在这 60 个严格配对的 shared scenes 上，`GraspVLA` 对 `CGN shared` 的优势是压倒性的，不是统计噪声。

### 3.2 按 condition 拆分

| Method | Condition | Success |
| --- | --- | --- |
| GraspVLA | `basic` | `20 / 20` |
| GraspVLA | `distractors_light` | `20 / 20` |
| GraspVLA | `opaque_basic` | `19 / 20` |
| CGN full modular | `basic` | `0 / 20` |
| CGN full modular | `distractors_light` | `0 / 20` |
| CGN full modular | `opaque_basic` | `0 / 20` |

### 3.3 失败类型

`CGN full modular` 在 `Track A-Cal v2` 的失败并不是单一原因：

- `grounding_error / carrot`: `8`
- `grounding_error / power drill`: `8`
- `task_failure / exhausted fixed execution plan`: `44`

这说明它一部分失败来自 open-vocabulary grounding，但更大一部分失败发生在“已经开始执行之后仍然达不到 shared success”的阶段。

`GraspVLA` 在 `Track A-Cal v2` 只有 `1` 个 `task_failure`。

## 4. Stress appendix：Track A-Stress v2

`Track A-Stress v2` 不再作为 headline table，而是 shared protocol 下的压力测试 appendix。

### 4.1 总体结果

| Method | Task Group | Success |
| --- | --- | --- |
| GraspVLA | overall | `62 / 64` |
| CGN full modular | overall | `0 / 64` |

更细分的结果：

| Method | Task | Success |
| --- | --- | --- |
| GraspVLA | language / distractors_heavy | `19 / 20` |
| GraspVLA | arbitrary common opaque / opaque_clutter | `20 / 20` |
| GraspVLA | arbitrary transparent / transparent_pose_bank | `23 / 24` |
| CGN full modular | language / distractors_heavy | `0 / 20` |
| CGN full modular | arbitrary common opaque / opaque_clutter | `0 / 20` |
| CGN full modular | arbitrary transparent / transparent_pose_bank | `0 / 24` |

这说明当前公开 `GraspVLA` 在我们冻结的 shared stress protocol 下，依然非常强；而当前公开 `CGN` 共享线在 opaque、transparent、language 三个 stress slice 上都没有过 shared success。

## 5. GraspVLA protocol audit

### 5.1 官方对齐审计

当前官方对齐审计的结论是：

- `parity_status = reproducibility-limited parity`

也就是：

- 官方 `V0` 自己重复跑会有少量漂移
- 我们 wrapper 的 `V1` 与官方 `V0` 的 mismatch 数量已经没有比官方自重复漂移更差

因此现在不能把 `Track A` 的结果归因成“wrapper 坏了”。

### 5.2 protocol_probe_v2

`protocol_probe_v2` 固定在 24 个 episode 上，只测 `GraspVLA` 的协议敏感性。

结果如下：

| Variant | Success |
| --- | --- | --- |
| `P0_shared_baseline` | `24 / 24` |
| `P1_front_only_duplicate` | `14 / 24` |
| `P2_attempt_budget_1` | `20 / 24` |
| `P3_relaxed_success` | `24 / 24` |
| `P4_camera_jitter_low` | `24 / 24` |

factor delta：

- `view_mode_effect`: `-0.4167`
- `attempt_budget_effect`: `-0.1667`
- `success_rule_effect`: `0.0`
- `camera_jitter_effect`: `0.0`

按 condition 看，最大的 drop 出现在：

- `transparent_pose_bank`: `1.0 -> 0.0`（dual-view 变 front-only）

这说明：

1. `GraspVLA` 当前 shared simulator 表现强，不是因为 success rule 放宽了。
2. `GraspVLA` 的一个真实边界是 **多视角依赖**，尤其对 transparent slice 非常明显。

## 6. CGN bottleneck_v1：为什么 modular 这么差

这是当前最关键的一组诊断，因为它直接回答“CGN shared 0 分到底是不是 detector 没配好”。

### 6.1 四个版本的正式结果

| Variant | Meaning | Success |
| --- | --- | --- |
| `D0_shared_cgn` | 当前 shared modular pipeline | `0 / 24` |
| `D1_oracle_grounding` | 用 simulator GT mask 替代 detector + segmentation | `0 / 24` |
| `D2_oracle_grasp` | 保留 GT mask，并把 proposal 换成 simple top-down centroid grasp | `0 / 24` |
| `D3_relaxed_success_rescore` | 对 `D0` 结果按 relaxed success 重新打分 | `1 / 24` |

success delta：

- `D0 -> D1 grounding_segmentation_effect`: `+0.0000`
- `D1 -> D2 grasp_proposal_effect`: `+0.0000`
- `D0 -> D3 strict_success_semantics_effect`: `+0.0417`

### 6.2 这组结果真正说明了什么

首先，它说明 **问题不只在 detector**。

因为即使把 detector 和 depth-mask filtering 全部换成 simulator GT mask，`D1` 仍然是 `0 / 24`。

其次，它说明 **严格 success rule 不是主因**。

`D3` 只把 `D0` 从 `0 / 24` 提高到 `1 / 24`，说明 shared success semantics 只解释了很小一部分差距。

第三，它说明 **proposal / execution 这一段仍然有严重问题**，但这里必须谨慎表述：

- `D2` 不是“真正的物理 oracle”，而是一个 **simple top-down centroid grasp**。
- 所以 `D2 = 0 / 24` 不能被表述成“proposal 完全不重要”。
- 它更准确的含义是：**即使用一个非常简单、没有 detector 的 top-down 替代抓取姿态，也无法把当前 shared lane 救成可用系统。**

### 6.3 进一步看 payload：planner / grasp-pose 兼容性问题很明显

我额外统计了 debug payload 中送进 planner 的 `target_base z`：

| Variant | Debug files | `target_base z < 0` |
| --- | --- | --- |
| `D0_shared_cgn` | `48` | `21` |
| `D1_oracle_grounding` | `71` | `37` |
| `track_b_cgn_native_v1` | `913` | `417` |

这很关键，因为 `target_base z < 0` 意味着很多 CGN 产生的抓取位姿在送进当前 shared planner 后，目标点已经落到桌面以下或极其接近桌面以下，这非常像 **grasp pose / coordinate transform / planner execution contract** 的兼容性问题。

与此对应，`D2_oracle_grasp` 里 `target_base z < 0` 的数量是：

- `0 / 72`

也就是说，simple oracle top-down grasp 至少解决了“很多 proposal 目标点在桌面以下”这个问题。

但是即便如此，`D2` 仍然没有达到正式 success：

- `max lift = 8.1105 cm`
- `>= 1 cm` 的 trial 数：`12 / 24`
- `>= 5 cm` 的 trial 数：`4 / 24`
- `>= 10 cm` 的 trial 数：`0 / 24`

所以更谨慎的结论是：

1. `CGN shared` 的失败不是只靠 detector 就能解释。
2. `CGN` 输出的 grasp pose 与我们当前 shared planner / controller contract 之间确实存在兼容性问题。
3. 即便换成一个更“安全”的 simple top-down 替代抓取姿态，系统也只恢复到了“偶尔能抬一点点”的程度，离 shared benchmark 的成功标准仍然差得很远。

### 6.4 一个很容易误解、但必须说清楚的细节

`D0` 里有一条 episode 的 `lift_cm = 16.1265`，但最终仍然失败，因为：

- `hold_s = 0.2`

这说明它确实有过一次“抓起来但立刻没稳住”的近成功案例，但这只是 `24` 条中的 `1` 条，而且 `D3 relaxed success` 也只把整体提到了 `1 / 24`。所以我们不能把 shared modular 的总体失败解释成“只是 hold 规则太苛刻”。

## 7. CGN native appendix：不是只有 shared lane 差

为了回答“是不是 shared lane 把 modular baseline 弄残了”，我还跑了 `track_b_cgn_native_v1`。

这个 native appendix 做了这些放宽：

- `front + side` depth 融合
- native multi-view object isolation
- top-k grasp retry
- per-attempt replanning

而且我已经修复了之前 `native_multiview_fusion` 没真正生效的 runtime bug，并从 debug payload 确认它真的进入了：

- `point_cloud_mode = front_plus_side_fused_in_front_frame`

### 7.1 native appendix 结果

| Method | Success |
| --- | --- |
| `CGN native appendix` | `1 / 84` |

分解如下：

| Task | Success |
| --- | --- |
| language-conditioned single-target pick | `0 / 40` |
| arbitrary common opaque | `1 / 20` |
| arbitrary transparent | `0 / 24` |

唯一成功的 scene 是：

- `arbitrary_grasping_common_opaque__opaque_basic__005__r02`
- object: `watermelon`

### 7.2 OOM 不是最后结论的来源

原始 matrix run 里有 1 个 scene 因为多卡并发导致 `OOM`。我后来把它单独拿出来，在独占 GPU 上重跑：

- scene: `arbitrary_grasping_common_opaque__opaque_basic__002__r03`
- object: `ceramic_bowl`

结果是：

- 仍然失败，但这次是正常的 `task_failure`
- 因此 native appendix 的低分 **不是由那次 OOM 偶发噪声造成的**

## 8. 为什么 modular grasping systems 看起来这么差

这是这轮检查最需要谨慎回答的问题。

### 8.1 能明确说的

目前我们能明确说：

1. **当前 shared CGN 的低分不是一个 setup bug 造成的。**
   - 不是 smoke/mock
   - 不是 shared runner 没跑起来
   - 不是统计表读错
   - 不是那次 OOM 把 native appendix 错杀

2. **它也不是单纯 detector 的问题。**
   - `D1 oracle grounding = 0 / 24`

3. **严格 success rule 只解释很小一部分差距。**
   - `D3 relaxed success rescore = 1 / 24`

4. **CGN proposal / planner / execution contract 这一层有真实兼容性问题。**
   - 大量 `target_base z < 0`
   - 这在 shared bottleneck 和 native appendix 里都出现

5. **native lane 也没有把它救回来。**
   - 在真正启用 `front + side` depth 融合以后，`CGN native appendix` 还是只有 `1 / 84`

### 8.2 不能过度说的

但我们现在 **不能** 直接说：

- “所有 modular grasping systems 都很差”
- “GraspVLA 全面优于所有 modular methods”
- “CGN 的核心模型本身一无是处”

原因很简单：这轮正式 modular baseline 是 `CGN`，不是论文主文里的 `AnyGrasp`；而 `CGN` 与 `AnyGrasp` 的工程路线、输入形式、公开 SDK 完整度都不一样。

## 9. 和官方论文、官方 GitHub 对上的结论

我重新对了官方论文和官方 repo，结论如下。

### 9.1 GraspVLA 官方 release 的设置本来就和 fair shared lane 不一样

官方补充材料明确写到：

- 他们为了 LIBERO 对齐训练设置，调整了 camera configuration
- 去掉了一些任务中的 basket
- 把 gripper 延长了 `2 cm`
- 这些改动只给他们自己的模型使用

此外，官方 playground 代码里也明确写了：

- `camera_names = ["front_view", "side_view"]`
- `camera_heights = 256`
- `camera_widths = 256`
- `control_freq = 5`
- basket removal 逻辑在 `benchmark_runner.py`
- 默认 robot config 是 `franka_with_extended_finger`

因此，`Track B` 和 `Track A` 本来就不该混在一起解释。

### 9.2 GraspVLA 论文对 AnyGrasp 的比较，并不是我们现在这条 CGN shared lane

官方论文 Table 3 比的是：

- `AnyGrasp + Grounding DINO + motion planner`
- 语言任务里是用 `Grounding DINO` 出 2D box，再过滤 grasp candidates
- 传感器是末端 `RealSense D435i`
- transparent test set 是 `5` 个物体、每个 `6` 个 pose，也就是 `30` 个 trial

这和我们当前：

- `固定双相机 shared rig`
- `CGN`
- `GT mask / detector / shared planner`

不是同一条 baseline lane。

所以我们现在对 modular 的结论必须写成：

> 在当前冻结的 shared benchmark protocol 下，当前公开 `CGN` modular lane 明显弱于当前公开 `GraspVLA`。

而不是：

> 官方论文里的所有 modular baseline 都会在这个 setting 下全灭。

### 9.3 Contact-GraspNet 官方 README 本来也强调 segmentation / local regions / filter grasps

官方 `Contact-GraspNet` README 里明确建议：

- object-wise grasp 要配 segmentation
- 用 `--local_regions`
- 用 `--filter_grasps`

这说明 object-centric modular pipeline 的确需要很强的 preprocessing。

我们这边并没有忽略这一点：

- shared lane 有 detector + depth mask filtering
- native lane 也有更强的 object isolation 和 multi-view fusion

但即便如此，当前公开 CGN 线路仍然很差。这进一步说明：**现在的问题不是“我们完全没给 modular baseline 该有的前处理”，而是即使用了这类前处理，当前 CGN lane 仍然没有和 shared controller 契合起来。**

## 10. 当前最稳的结论

### 10.1 可以对导师/合作方直接说的

1. `GraspVLA` 在当前冻结的 shared simulator 主榜单 `Track A-Cal v2` 上很强：`59 / 60`。
2. `GraspVLA` 在 `Track A-Stress v2` 上也很强：`62 / 64`。
3. `GraspVLA` 的 shared 表现高，不是因为统计 bug、mock artifact、success rule 放宽、或者 wrapper 坏了。
4. 当前公开 `CGN` modular lane 在 shared 和 native appendix 下都很弱，而且这不是单一 detector bug 能解释的。
5. `CGN` 当前最大的可疑瓶颈在 `grasp pose / planner / controller contract`，不是只在感知层。

### 10.2 必须保留保守措辞的

1. 当前 modular lane 的负面结论，应该限定在 **public CGN under this benchmark protocol**。
2. `AnyGrasp` 还不能进入 submission-grade headline compare，因为新 license 还没到。
3. 现在还不能把这篇 paper 写成“all modular systems collapse under fair evaluation”；更准确的 framing 仍然应当是：
   - `shared benchmark + protocol audit`
   - 以及一个对当前 public CGN lane 的强负面结果和瓶颈归因

## 11. 关键 artifact 索引

### 主榜单 / stress / paper bundle

- `artifacts/runs/20260412_051837_graspvla_track_a_cal_v2_shared_sim/results.csv`
- `artifacts/runs/20260412_051837_cgn_track_a_cal_v2_shared_sim/`
- `artifacts/runs/20260412_065542_graspvla_track_a_stress_v2_shared_sim/results.csv`
- `artifacts/runs/20260412_065542_cgn_track_a_stress_v2_shared_sim/`
- `artifacts/reports/corl_paper_bundle_20260412_full/paper_ready_report.md`
- `artifacts/reports/corl_paper_bundle_20260412_full/paper_summary.csv`
- `artifacts/reports/corl_paper_bundle_20260412_full/paper_stats.json`

### CGN native appendix

- `artifacts/runs/20260412_085614_cgn_track_b_cgn_native_v1_shared_sim/`
- `artifacts/runs/20260412_oom_rerun_track_b_cgn_native_v1_single_scene/results.csv`

### Audit

- `artifacts/audits/20260412_080241_graspvla_protocol_probe_v2/summary.csv`
- `artifacts/audits/20260412_080241_graspvla_protocol_probe_v2/factor_delta_vs_baseline.csv`
- `artifacts/audits/20260412_101317_cgn_bottleneck_v1/report.md`
- `artifacts/audits/20260412_101317_cgn_bottleneck_v1/summary.csv`
- `artifacts/audits/20260405_042741_graspvla_official_alignment/report.json`

### 官方 native 参考

- `artifacts/official_sim/20260402_231726_em14_full/summary.json`

## 12. 官方来源（这轮重新核对过）

- GraspVLA paper: <https://openreview.net/pdf?id=zEC8TOXDkH>
- GraspVLA official repo: <https://github.com/PKU-EPIC/GraspVLA>
- GraspVLA official playground: <https://github.com/MiYanDoris/GraspVLA-playground>
- AnyGrasp SDK: <https://github.com/graspnet/anygrasp_sdk>
- Contact-GraspNet: <https://github.com/NVlabs/contact_graspnet>

本地 upstream 核对点：

- `third_party/upstreams/GraspVLA-playground/agent.py`
- `third_party/upstreams/GraspVLA-playground/benchmark_runner.py`
- `third_party/upstreams/contact_graspnet/README.md`


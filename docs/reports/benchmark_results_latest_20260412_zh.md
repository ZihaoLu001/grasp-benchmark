# 最新完整版 Benchmark 结果汇总（2026-04-12）

## 1. 当前结果是否已经完整出来

如果只看**当前可严谨执行、且不依赖外部新资源**的 benchmark 部分，那么答案是：

**是，simulation 侧已经完整出来了。**

已经完整完成并纳入当前正式汇总的部分：

- `Track A-Cal v2` shared benchmark
- `Track A-Stress v2` shared stress appendix
- `GraspVLA` official alignment audit
- `GraspVLA protocol_probe_v2`
- `CGN bottleneck_v1`
- `CGN native appendix`
- paper-ready statistics bundle

当前还没有结果的部分，不是因为 simulator 里漏跑了，而是**外部阻塞**：

- `AnyGrasp`：缺新的 node-matched license
- real-world pilot：缺真机实验时间
- `Phase 2 constraint / affordance grasping`：当前阶段后置

## 2. 当前最重要的结论

这轮 benchmark 现在最稳的主结论是：

1. **公开发布的 GraspVLA 官方 native 数字不能直接当 fair benchmark claim。**
2. 在冻结 shared protocol 下，当前 public `GraspVLA` 在 simulator 中显著强于当前 public `CGN` lane。
3. `CGN` 的低分不是单一 bug，也不只是 detector 问题；shared lane、oracle grounding、relaxed success、native appendix 都已经单独检查过。
4. 目前真正没完成的是 `AnyGrasp`、真机 pilot、和 `Phase 2`，不是 simulator 主 benchmark 缺实验。

## 3. 主公平榜单：Track A-Cal v2

`Track A-Cal v2` 是当前唯一的 headline fair table。

固定协议：

- 双固定视角
- shared gripper
- shared workspace
- blocking control
- `lift >= 15 cm`
- `hold >= 2 s`
- 每个 trial 最多 `3` 次尝试

### 3.1 总体结果

| 方法 | task group | 成功数 |
| --- | --- | --- |
| GraspVLA | overall | `59 / 60` |
| CGN full modular | overall | `0 / 60` |

### 3.2 按任务拆分

| 方法 | 任务 | 成功数 |
| --- | --- | --- |
| GraspVLA | language-conditioned single-target pick | `40 / 40` |
| GraspVLA | arbitrary common opaque grasping | `19 / 20` |
| CGN full modular | language-conditioned single-target pick | `0 / 40` |
| CGN full modular | arbitrary common opaque grasping | `0 / 20` |

### 3.3 统计

- paired scenes: `60`
- exact McNemar: `p = 0.0`
- paired bootstrap success-rate delta: `[-1.0, -0.95]`

这说明 `GraspVLA` 相比当前 `CGN` shared lane 的优势不是噪声。

## 4. Stress appendix：Track A-Stress v2

`Track A-Stress v2` 不再作为 headline table，而是 appendix。

### 4.1 总体结果

| 方法 | task group | 成功数 |
| --- | --- | --- |
| GraspVLA | overall | `62 / 64` |
| CGN full modular | overall | `0 / 64` |

### 4.2 按 hardest slices 拆分

| 方法 | 任务 | 成功数 |
| --- | --- | --- |
| GraspVLA | language / distractors_heavy | `19 / 20` |
| GraspVLA | arbitrary common opaque / opaque_clutter | `20 / 20` |
| GraspVLA | arbitrary transparent / transparent_pose_bank | `23 / 24` |
| CGN full modular | language / distractors_heavy | `0 / 20` |
| CGN full modular | arbitrary common opaque / opaque_clutter | `0 / 20` |
| CGN full modular | arbitrary transparent / transparent_pose_bank | `0 / 24` |

## 5. Track B：native 参考层

### 5.1 官方 GraspVLA native reference

| benchmark | 成功数 |
| --- | --- |
| playground | `8 / 10` |
| libero_10 | `325 / 350` |
| libero_goal | `336 / 350` |
| libero_object | `482 / 500` |

这一层只用来说明官方公开 release 在 native setup 下的上限，不和 fair main table 混算。

### 5.2 CGN native appendix

为了回答“是不是 shared lane 把 modular baseline 弄残了”，我们补了 `CGN native appendix`。

结果：

| 方法 | task group | 成功数 |
| --- | --- | --- |
| CGN native appendix | overall | `1 / 84` |

按任务拆分：

| 任务 | 成功数 |
| --- | --- |
| language-conditioned single-target pick | `0 / 40` |
| arbitrary common opaque | `1 / 20` |
| arbitrary transparent | `0 / 24` |

唯一成功样本来自：

- `arbitrary_grasping_common_opaque__opaque_basic__005__r02`
- object: `watermelon`

## 6. Protocol audit：GraspVLA 的边界与敏感性

### 6.1 官方对齐

当前官方对齐状态是：

- `reproducibility-limited parity`

含义是：

- 官方自己重复运行会有小幅漂移
- 我们 wrapper 与官方 release 的 mismatch 已经不比官方自漂移更差

因此当前 `Track A` 结果不能归因成“wrapper 坏了”。

### 6.2 protocol_probe_v2

| variant | 成功数 |
| --- | --- |
| `P0_shared_baseline` | `24 / 24` |
| `P1_front_only_duplicate` | `14 / 24` |
| `P2_attempt_budget_1` | `20 / 24` |
| `P3_relaxed_success` | `24 / 24` |
| `P4_camera_jitter_low` | `24 / 24` |

主要观察：

- 最大单因素掉点来自去掉 side-view
- 在 transparent subset 上，`front_only_duplicate` 从 `8 / 8` 直接掉到 `0 / 8`
- 当前 shared success rule 并不是 GraspVLA 高分的主要原因

更谨慎的表述是：

**GraspVLA 在当前 shared simulator 里非常强，但它对双视角依赖很明显，尤其在 transparent slice 上。**

## 7. CGN bottleneck：为什么 modular 这么差

这是当前最需要谨慎解释的一部分。

### 7.1 四个正式诊断版本

| variant | 含义 | 成功数 |
| --- | --- | --- |
| `D0_shared_cgn` | 当前 shared modular pipeline | `0 / 24` |
| `D1_oracle_grounding` | 用 simulator GT mask 替换 detector + segmentation | `0 / 24` |
| `D2_oracle_grasp` | 保留 GT mask，并把 proposal 换成 simple top-down centroid grasp | `0 / 24` |
| `D3_relaxed_success_rescore` | 对 `D0` 按 relaxed success 重打分 | `1 / 24` |

### 7.2 这组实验说明了什么

可以比较确定地说：

1. **不是单纯 detector 问题。**
   因为 `D1` 仍然是 `0 / 24`。

2. **不是单纯 success rule 太严。**
   因为 relaxed 后也只到 `1 / 24`。

3. **proposal / planner / execution contract 这一层存在真实问题。**
   当前 debug payload 里有大量 `target_base z < 0` 的样本，说明送进 planner 的抓取目标位姿经常已经不合理。

但也必须避免过度解读：

- `D2` 不是完整物理 oracle，只是一个 simple top-down centroid 替代抓取姿态
- 所以不能把当前结果直接写成“CGN 的核心模型完全无效”

最安全的说法是：

**当前 public CGN lane 的低分不是单个 bug，也不是只换个 GT bbox 就能救回来，而是 perception、grasp pose 到 planner contract、以及 task completion 一起叠出来的。**

## 8. 为什么现在不能直接说“所有 modular grasping systems 都不行”

这点必须跟导师和合作方说清楚。

当前我们正式跑通并做完 shared + native + bottleneck 审计的 modular baseline 是：

- `CGN`

但这不等于：

- 所有 modular grasping systems
- 也不等于官方论文主文中的 `AnyGrasp`

所以现在可以 claim 的是：

- 在**当前冻结 shared benchmark protocol** 下，public `GraspVLA` 显著强于**当前 public `CGN` lane**

现在不应该 claim 的是：

- “所有 modular 方法都比 end-to-end 差”
- “GraspVLA 全面优于任何 modular system”

## 9. 当前还没完成的部分

### 9.1 AnyGrasp

当前旧 license 与现在节点 feature id 不匹配，因此 AnyGrasp 暂时不再进入 submission-grade 主结论。

状态文档：

- [anygrasp_license_mismatch_20260410.md](D:/codex/grasp-benchmark/docs/reports/anygrasp_license_mismatch_20260410.md)

### 9.2 Real-world pilot

目前仍是 readiness / checklist 阶段，没有正式 paired benchmark 结果。

### 9.3 Phase 2

`constraint / affordance grasping` 仍后置，没有纳入当前这轮 simulator 主结果。

## 10. 当前最适合给导师看的文件

如果导师只看三份，我建议直接看：

1. [benchmark_results_latest_20260412_zh.md](D:/codex/grasp-benchmark/docs/reports/benchmark_results_latest_20260412_zh.md)
2. [corl_completion_matrix_20260412_zh.md](D:/codex/grasp-benchmark/docs/reports/corl_completion_matrix_20260412_zh.md)
3. [paper_ready_report.md](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/paper_ready_report.md)

如果要看协议边界和 modular 诊断，再加：

4. [graspvla_protocol_probe_v2_20260412_zh.md](D:/codex/grasp-benchmark/docs/reports/graspvla_protocol_probe_v2_20260412_zh.md)
5. [cgn_bottleneck_v1_20260412_zh.md](D:/codex/grasp-benchmark/docs/reports/cgn_bottleneck_v1_20260412_zh.md)

## 11. 一句话总括

**当前 benchmark 的 simulator 版已经完整跑到 submission-grade：主榜单、stress appendix、protocol audit、modular bottleneck、native appendix 都齐了；还没完成的只剩 AnyGrasp license、真机 pilot、和 Phase 2。**

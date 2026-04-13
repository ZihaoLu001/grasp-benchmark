# CoRL 2026 Submission Hardening 说明

## 当前定位

当前 `grasp-benchmark` 已经不再是早期 pilot 版。

我们已经有：

- `Track A-Cal v3` 主公平榜单
- `Track A-Stress v4` hardest-slice appendix
- `GraspVLA official alignment / protocol audit`
- `CGN shared / native-like / bottleneck` 三层 modular 证据链
- `instruction robustness`、`sim-to-real proxy`、`Phase 2 pilot` 三类补强套件

因此，论文主 framing 应稳定为：

- `shared benchmark + protocol audit`
- 而不是单纯 scoreboard
- 也不是单纯复现 GraspVLA release

## 为什么还要继续补 benchmark

即使当前 simulator 结果已经很强，投稿 CoRL 2026 时 reviewer 仍然大概率会追问四类问题：

1. 主榜单之外，语言鲁棒性是否单独测过？
2. simulator 里的分布偏移是否对真实部署具有解释力？
3. modular baseline 的低分到底是感知、proposal，还是 execution contract 问题？
4. 除了“抓起来”，有没有至少一个 task-oriented / affordance 抓取 extension？

这些问题不是额外加分项，而是决定这篇工作更像“成熟 benchmark paper”还是“强结果的项目总结”。

## 与近期工作的对齐

### 1. CoRL 2026 本身强调 robotics focus 和可审稿证据

CoRL 2026 官方征稿页与作者说明都强调：

- 论文要有清晰的 robot learning / robotics focus
- benchmark / dataset work 也需要明确的机器人问题定义和实证支撑
- initial submission 仍然是主文 8 页，附录可选，但 reviewer 不承诺看 appendix

来源：

- [CoRL 2026 Contributions](https://2026.corl.org/contributions)
- [CoRL 2026 Instruction for Authors](https://2026.corl.org/contributions/instruction-for-authors)

这意味着 submission 主文里必须把 benchmark 的核心设计和关键证据讲圆，不能把所有重要解释都压到 appendix。

### 2. 语言鲁棒性已经成为 VLA benchmark 的显式缺口

[LIBERO-Para](https://arxiv.org/abs/2603.28301) 的核心观点之一，是现有 manipulation benchmark 容易把 instruction 当成固定字符串，而忽略 paraphrase、组合式表达和 disambiguation 对策略的真实影响。

因此，当前新增的 `instruction_robustness_v2` 是必要补强，而不是锦上添花：

- `canonical`
- `lexical_paraphrase`
- `compositional_paraphrase`
- `distractor_aware_disambiguation`

这让论文可以回答：

- GraspVLA 的语义能力是否只在单一 prompt 模板下成立？
- clutter 条件下的语言歧义会不会显著改变排序？

### 3. simulator-only 论文必须补 transfer-readiness，而不只是更多 sim 分数

[SIMPLER](https://simpler-env.github.io/) 明确说明：

- simulation evaluation 可以成为 real-world evaluation 的可扩展 proxy
- 但前提是显式分析 control / visual shift，并报告对真实行为的预测能力

这正是 `sim2real_proxy_v2` 的意义：

- `camera_jitter`
- `rgb_lighting_background`
- `depth_noise_bias`
- `friction_material_shift`

而且要分 `low / medium` severity，而不是只做单一扰动。

### 4. hardest slices 不能只保留小样本 transparent / clutter

近期抓取 benchmark 明确在往 harder clutter / occlusion 方向走：

- [GraspClutter6D](https://arxiv.org/abs/2504.06866)
- [TARGO](https://targo-benchmark.github.io/)

它们共同指向一个事实：

- light clutter 或单目标 tabletop setting 已经不够区分方法
- occlusion level、target ambiguity、transparent / clutter 条件才是真正高信息量 slice

这就是为什么 submission 版应该优先引用 `Track A-Stress v4`，而不是继续堆 easy opaque 成功率。

### 5. evaluator 不能只有 binary success

近期 evaluation 工作更强调“知道哪里坏了”，而不是只给一个成功率：

- [AutoEval](https://arxiv.org/abs/2503.24278)
- [ManipArena](https://arxiv.org/abs/2603.28545)

这和我们当前 submission 版的 stage metrics 是一致的：

- `grounding_success`
- `mask_nonempty`
- `proposal_nonempty`
- `plan_success`
- `lift_only_success`
- `hold_success`
- `slip_after_lift`
- `collision_count`
- `wrong_object`
- `wrong_part`

这组指标的意义是：让论文能解释“为什么 modular lane 低”，而不是只说“它低”。

### 6. task-oriented extension 最少也要有一个小而硬的 section

像 [AffordGrasp](https://arxiv.org/abs/2503.00778) 这类工作说明，抓取 benchmark 如果想对 task-oriented grasping 有发言权，至少要有：

- part-sensitive grasp
- affordance-sensitive grasp
- instruction-conditioned target part selection

因此 `phase2_pilot_v1` 的角色不是扩 scope，而是提供一个最小但有说服力的 extension：

- `mug_handle_grasp`
- `avoid_inside_cup`
- `power_drill_handle_grasp`

## 当前 submission 版最合理的论文结构

按当前项目状态，最稳的 CoRL 2026 simulator-first 结构应当是：

1. `Track A-Cal v3` headline fair table
2. `Track A-Stress v4` hardest-slice appendix
3. `instruction_robustness_v2`
4. `sim2real_proxy_v2`
5. `CGN bottleneck + native-like appendix`
6. `Track B official GraspVLA reference`
7. `Phase 2 pilot`

这套结构能让论文清楚回答四个问题：

1. 在冻结 shared protocol 下，谁更强？
2. hardest slices 下，谁更脆弱？
3. simulator 里的 shift 能否形成 transfer-readiness 证据？
4. modular lane 的差距主要掉在哪个 stage？

## 当前仍然不能夸大的地方

为了保证导师汇报和投稿口径都足够稳，下面这些结论仍然不能写得过头：

- 不能把 `CGN` 的低分扩大成“所有 modular grasping systems 都不行”
- 不能把 `CGN native-like appendix` 说成“官方 canonical CGN full system”
- 不能在 `AnyGrasp` 新 license 到位前把它写进 submission 主表
- 不能把 simulator 结果伪装成已经完成的 real-world benchmark

最稳的写法仍然是：

- public GraspVLA 在当前冻结 shared benchmark protocol 下显著强于当前 public CGN lane
- 这个差距不只来自 protocol，也不只来自 detector，而是可被 stage metrics 和 bottleneck audit 分解
- 当前论文是 simulator-first benchmark + protocol-audit paper，real-world pilot 仍是后续 gate

## 下一步执行优先级

在当前 submission hardening 阶段，优先级应固定为：

1. 冻结 clean canonical runs
2. 构建 submission bundle
3. 更新老师汇报页和论文主表
4. 再决定 real-world pilot 的时间窗口

如果 real-world pilot 在冻结前仍无法完成，论文仍可以 simulator-first 口径投稿，但必须在 limitations 里明确说明：

- real-world pilot 尚未完成
- 当前 evidence 主要来自 shared benchmark、protocol audit 和 transfer-readiness suite


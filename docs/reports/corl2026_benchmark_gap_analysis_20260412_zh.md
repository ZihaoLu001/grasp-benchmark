# CoRL 2026 Benchmark Gap Analysis 与补实验建议（Simulator First）

## 1. 这份文档的用途

这份文档不是重复当前结果，而是回答一个更重要的问题：

**如果目标是把当前项目推进到一篇更像 CoRL 主会 benchmark / protocol-audit 论文的标准，我们还缺哪些评测，哪些必须补，哪些可以后置。**

当前仓库里已经有一条很强的 simulator 主线：

- `Track A-Cal v2`: `GraspVLA 59/60` vs `CGN shared 0/60`
- `Track A-Stress v2`: `GraspVLA 62/64` vs `CGN shared 0/64`
- `GraspVLA` official alignment audit: `reproducibility-limited parity`
- `GraspVLA protocol_probe_v2`
- `CGN bottleneck_v1`
- `CGN native appendix`: `1/84`

这些结果已经足够支撑一篇像样的 **shared benchmark + protocol audit** 论文主干。但如果目标是按更高标准冲 CoRL，reviewer 仍然大概率会追问 coverage、native lane completeness、transfer evidence、以及 task breadth。

## 2. 相关论文和会议口径告诉我们什么

### 2.1 CoRL 对 simulator-only 论文的要求并不低

CoRL 官方 call for papers 明确写过：如果论文没有 real-robot 实验，也没有现成真实实验数据支撑，就应该提供 **extensive experimentation in simulation**，并清楚解释为什么作者相信这些结果能转移到真实机器人上，甚至提到可以考虑多个 simulator 或更强的 transfer 论证。  
来源：[CoRL Call for Papers](https://2020.corl.org/author-information/call-for-papers)

这意味着：**光有一张主表还不够**。如果真机暂时还没上，就需要把 simulator 里的 coverage、robustness、protocol sensitivity、以及 sim-to-real proxy 证据做得更扎实。

### 2.2 GraspVLA 原论文本身就在提醒我们：协议细节很敏感

GraspVLA 论文和其公开 release 已经说明：

- multi-view 对它影响很大
- 官方 LIBERO 评测带有 camera / scene edit / gripper 相关的协议细节
- 与 AnyGrasp 的对比使用的是 native-like baseline 组合，而不是任意 modular lane

来源：

- [GraspVLA paper](https://openreview.net/pdf?id=zEC8TOXDkH)
- [GraspVLA playground](https://github.com/MiYanDoris/GraspVLA-playground)

这说明论文 framing 必须继续坚持三层：

- `Track A-Cal`: fair shared benchmark
- `Track A-Stress`: shared stress appendix
- `Track B`: native reference

这条结构是对的，不需要推翻。

### 2.3 相关 grasp benchmark 论文强调的，不只是 success rate

近期 benchmark 论文和 grasping papers 反复出现几个共同点：

- **transparent / clutter / occlusion** 是高信息增量 slice
- benchmark 不应只给 overall success
- 应该报告更细的 pre-grasp / execution / hold 稳定性指标
- object split / generalization split 很重要

能直接支持这些结论的公开工作包括：

- [GRAB: A Systematic Real-World Grasping Benchmark](https://arxiv.org/abs/2602.18835)  
  强调 benchmark 不应只看 success rate，而要加入 pre-grasp conditions 和更细粒度 graspability metrics。
- [AffordGrasp](https://arxiv.org/abs/2503.00778)  
  强调 cluttered open-vocabulary task-oriented grasping、implicit instruction、part / affordance 级别任务的重要性。
- [Contact-GraspNet official README](https://github.com/NVlabs/contact_graspnet)  
  明确 object-wise grasp 建议配 segmentation、`local_regions`、`filter_grasps`。

## 3. 当前 benchmark 已经做得好的地方

这些部分已经达到 submission-grade simulator 水平，不是当前的主要短板：

1. **shared benchmark 协议冻结得很干净**  
   相机、gripper、workspace、success rule、attempt budget、logging schema 都已经固定。

2. **GraspVLA 的 official alignment audit 已经足够强**  
   我们已经证明当前 wrapper 与官方 release 的偏差没有明显超过官方自身重复运行漂移。

3. **统计层已经不是空白**  
   当前主表已经有 `95% Wilson CI`、paired bootstrap、exact McNemar。

4. **CGN 不是只跑了一个临时 debug 版本**  
   shared lane、bottleneck oracle、native appendix 都已经独立跑过。

## 4. 如果按 CoRL 高标准看，当前还缺什么

下面这些是我认为 reviewer 最可能追问、而且最值得补的地方。

### 4.1 缺更强的 hardest-slice coverage

虽然 `track_a_cal_v2` 已经扩到 `60` 个 paired trials，`track_a_stress_v2` 也到了 `64`，但 hardest slices 还可以更扎实：

- transparent 当前是 `24` 个 trial，不错，但更像“接近 benchmark 规模”，还没完全到 reviewer 最舒服的量级
- language clutter 现在只有 `distractors_light` 和 `distractors_heavy` 两档
- occlusion 还没有单独成组

**建议补法**

- transparent 扩到 `30-32` 个 paired trials  
  目标是接近论文里常见的 `5 objects x 6 pose` 量级；如果当前资产只能稳定支持 4 个透明 proxy，也可以做 `4 objects x 8 variants = 32`
- 新增 `occlusion_bank`
- 把 clutter 做成三档：`light / medium / heavy`

### 4.2 缺 generalization split

当前 `Track A-Cal v2` 仍然主要围绕 5 个 native opaque assets 的 deterministic variants 展开。它足够做 protocol-fair compare，但还不够像一个“benchmark paper”的 generalization section。

**建议补法**

新增一个 simulator-only 的 generalization track，分三层：

- `seen_native`: 当前 5 个主物体的多 seed / 多 scene
- `near_ood`: 相似几何或相似语义但不同实例
- `far_ood`: 语义长尾、材质变化、同类不同外观

最重要的是：这个 split 不应该只换名字，而要保证 scene recipe、asset identity、以及 instruction phrasing 真正不同。

### 4.3 缺 sim-to-real proxy robustness suite

如果真机暂时来不及，CoRL reviewer 会自然追问：

**为什么这些 simulator 排名会转移到 real robot？**

当前虽然已有 `protocol_probe_v2`，但它主要还是 GraspVLA 的 protocol sensitivity，不是系统的 transfer-readiness suite。

**建议补法**

新增 `sim2real_proxy_v1`，固定 5 组扰动：

- camera extrinsic jitter
- RGB lighting / background shift
- depth bias / dropout / noise
- friction / contact perturbation
- reflective / transparent material variants

这个套件不一定要很大，但至少要形成一张“排名在合理扰动下是否稳定”的表。

### 4.4 缺更细的 pre-grasp / execution metrics

现在我们有 success、SPL、attempts、latency、cycle time、failure taxonomy。对一般项目已经不错，但 benchmark paper 还可以再细一层。

**建议补法**

主表外再加一张 stage-level metrics 表：

- target grounding success rate
- valid target mask rate
- non-empty proposal rate
- executable-plan rate
- lift-only success rate
- stable-hold success rate
- collision rate
- slip-after-lift rate

这组指标会极大提升论文解释力，尤其对 modular baseline 很重要。

### 4.5 缺更完整的 modular native lane

当前我们已经补了 `CGN native appendix`，这是很重要的一步，但仍然不完整：

- `AnyGrasp` native lane 还没回来
- `CGN native` 现在更准确的表述是 `native-like appendix`，而不是 official end-to-end replication

**建议补法**

- 一旦 AnyGrasp license 恢复，优先补 `AnyGrasp native reference`
- 对 `CGN native` 保持诚实表述：它是 repo-owned best-case lane，不是官方 canonical full system

### 4.6 缺约束/affordance的小型 Phase 2 pilot

这不是当前最急，但如果 aiming at stronger CoRL framing，它会显著抬高论文上限。

**建议补法**

不要立刻做完整 Phase 2，只做一个小而硬的 pilot：

- `mug_handle_grasp`
- `do_not_touch_inside_cup`
- `rare_vocab_tool_pick`

每类 8-12 个 paired trials 即可，目标不是做新大表，而是作为 “task-oriented extension” section。

## 5. 建议新增的实验层级

如果要把当前 benchmark 从 “strong simulator benchmark” 推到 “更像 CoRL 主会 benchmark paper”，我建议补下面 5 个实验层。

### 5.1 Layer A: Headline shared benchmark 扩容

保留 `Track A-Cal v2`，但建议新增 `Track A-Cal v3`：

- `language/basic`: `5 objects x 6 variants = 30`
- `language/distractors_light`: `30`
- `arbitrary_common_opaque/opaque_basic`: `30`

总计：`90` paired trials

目的：

- 提升 sample size
- 让 headline fair table 更像 benchmark paper，而不是 pilot leaderboard

### 5.2 Layer B: Hardest-slice appendix 扩容

保留 `Track A-Stress v2`，再做 `Track A-Stress v3`：

- `language/distractors_heavy`: `30`
- `language/occlusion_bank`: `20`
- `arbitrary_common_opaque/opaque_clutter`: `30`
- `arbitrary_transparent/transparent_pose_bank`: `32`

总计：`112` trials

目的：

- 让 hardest slices 真正达到可发表规模
- 把 clutter / occlusion / transparent 三块分清楚

### 5.3 Layer C: Protocol sensitivity / transfer-readiness

新增 `protocol_and_transfer_suite_v1`：

- dual-view vs front-only
- attempts `1` vs `3`
- `10 cm / 1 s` vs `15 cm / 2 s`
- camera jitter
- depth noise
- friction perturbation

建议只测：

- `GraspVLA`
- `CGN shared`

目的：

- 回答“排名是否稳”
- 给 simulator-only 论文提供更强的 transfer 论据

### 5.4 Layer D: Modular bottleneck 深化

在现有 `cgn_bottleneck_v1` 上再补 2 个 oracle：

- `oracle_execution_rescore`: 只看是否 lift 到阈值，不要求 planner 完整闭环
- `oracle_affine_alignment`: 对 proposal pose 做简单 upright / top-down 对齐再送 planner

目的：

- 更精确地区分 proposal pose 问题和 planner/controller contract 问题

### 5.5 Layer E: Task-oriented pilot

新增 `phase2_pilot_v1`：

- handle grasp
- contact constraint
- rare vocabulary

目的：

- 让论文不只是一篇 opaque / transparent grasp benchmark
- 但规模要小，避免 scope 失控

## 6. 投稿前我建议的优先级

如果按产出比排序，我会建议：

1. **先补 hardest slices coverage**  
   transparent、occlusion、distractors/clutter 扩容
2. **再补 sim-to-real proxy robustness suite**  
   camera / depth / friction / material perturbations
3. **继续保留并加强 modular native lane**  
   AnyGrasp 恢复后优先补 native
4. **最后再做小型 Phase 2 pilot**

一句话就是：

**coverage > transfer-readiness > native completeness > affordance pilot**

## 7. 哪些是投稿前必须完成，哪些可以后置

### 投稿前建议必须完成

- `Track A-Cal` 扩到至少 `90` paired trials
- transparent 扩到至少 `30+`
- clutter / occlusion 补成独立 hardest slices
- transfer-readiness suite
- `AnyGrasp` 或至少一条更完整的 modular native lane
- 一份更细粒度的 stage-level metrics 表

### 可以放到 rebuttal / camera-ready / future work

- 完整 real-world 大表
- 全量 Phase 2 benchmark
- 更大 object inventory
- 第二 simulator

### 如果真机时间能拿到，最该补哪一组真机

如果 simulator 先冻结，再拿少量真机时间，我建议优先做：

- `language/basic`
- `language/distractors_heavy`
- `arbitrary_transparent`

每类做 `8-10` 个 paired trials，总量 `20-30` 即可。

## 8. 对当前项目最现实的 framing 建议

如果现在就投稿，最稳的 framing 仍然是：

**A Fair Shared-Protocol Benchmark and Protocol-Audit of End-to-End vs Modular Grasping**

而不是：

**A universal conclusion that end-to-end grasping dominates modular grasping**

因为当前我们真正完整跑通、完整审计、完整解释的 modular baseline 主要还是 `CGN`，`AnyGrasp` 还没回到 submission-grade compare。

## 9. 当前项目与 CoRL 标准之间的差距，一句话总结

当前项目已经有足够强的 simulator 主干，可以写成一篇很像样的 benchmark / protocol-audit paper；  
但如果目标是更稳地冲 CoRL 主会，下一步最值得补的不是继续堆 easy slices，而是：

- **扩 transparent / clutter / occlusion hardest slices**
- **补 transfer-readiness robustness suite**
- **补完整 modular native lane**
- **补 stage-level metrics**

## 10. 建议直接执行的下一轮 simulator 任务

如果只做一轮最有价值的补实验，我建议按这个顺序：

1. `track_a_stress_v3`  
   透明、遮挡、重 clutter 扩容
2. `protocol_and_transfer_suite_v1`  
   camera / depth / friction / material 扰动
3. `track_a_cal_v3`  
   主公平表扩到 `90` paired trials
4. `phase2_pilot_v1`  
   只做 handle / contact-constraint / rare-vocab 三类

---

## Sources

- [CoRL Call for Papers](https://2020.corl.org/author-information/call-for-papers)
- [GraspVLA paper](https://openreview.net/pdf?id=zEC8TOXDkH)
- [GraspVLA playground](https://github.com/MiYanDoris/GraspVLA-playground)
- [Contact-GraspNet repository](https://github.com/NVlabs/contact_graspnet)
- [GRAB: A Systematic Real-World Grasping Benchmark](https://arxiv.org/abs/2602.18835)
- [AffordGrasp](https://arxiv.org/abs/2503.00778)

# GraspVLA 边界探针实验（2026-04-06）

## 先说结论

- 当前正式 `Track A-Cal` 主榜单参考结果仍然是 `14/15`。
- 在新的 `28` 个 trial 的边界探针套件上，双视角 GraspVLA 跑到了 `27/28 = 0.9643`。
- 在同一套件上，把输入改成 `front_only_duplicate` 单视角代理后，结果是 `28/28 = 1.0000`。
- 平均推理延迟仍在和主 benchmark 接近的范围内：双视角约 `289.6 ms`，单视角代理约 `299.7 ms`。

## 什么情况下效果很好

这轮 probe 里，GraspVLA 在下面这些设置下都很稳：

- `language_conditioned_single_target_pick`: `14/15`
- `language_paraphrase_grab`: `3/3`
- `language_paraphrase_lift`: `3/3`
- `language_paraphrase_pickup`: `3/3`
- `arbitrary_grasping_transparent`: `4/4`

也就是说，在这版 compact probe 上，它对下面这些变化都没有明显掉点：

- 基础 opaque 抓取
- lighting 变化
- distractor 干扰
- 轻度 height 扰动
- 简单的指令改写，比如 `grab`、`lift`、`pick ... up`
- 当前这版透明物体代理子集

## 目前观察到的软边界

双视角 run 里唯一失败的样本是：

- `language_conditioned_single_target_pick__background__003`
- 目标物体：`power_drill`
- 条件：`background`
- 最终结果：`3` 次尝试后失败，最终 lift 只有 `-0.1796 cm`

所以这轮实验里，最弱的一格是：

- `language_conditioned_single_target_pick / background = 2/3 = 0.6667`

但要注意，这个 scene 在 `front_only_duplicate` 代理实验里反而成功了，而且是第 `2` 次尝试就成功，lift 到了 `28.8605 cm`。  
这说明目前更稳的解释不是“background 一定是硬边界”，而是：

- 这里是一个**局部不稳定热点**
- 还不能直接下结论说它是 public release 的稳定失败边界

## 这轮实验没有暴露出的边界

这版 probe **没有**把下面这些因素测成明显失败边界：

- transparent objects
- 简单语言改写
- 去掉 side camera 的 `front_only_duplicate` 单视角代理

这不等于这些因素永远不重要。它只说明：**在当前这套较小、较贴近 released distribution 的 probe 里，它们还没有把性能拉垮。**

## 需要特别说明的限制

- `front_only_duplicate` 只是**单视角代理实验**，不是重新训练过的单视角 checkpoint。它只是把 front image 复制到两个 RGB 输入槽里，因为公开 server 仍然要求两路 RGB。
- 这里的 transparent 子集用的是 benchmark 里的 shared transparent proxy assets，不是论文里完整的真实世界透明物体评测。
- 这轮 probe 规模还是比较小：总共 `28` 个 trial，语言任务只用 `3` 个 native opaque 对象，transparent 只测了 `4` 个代理场景。所以它适合“探边界”，但还不够支撑对所有泛化能力下很强结论。

## 当前最稳的口径

基于这轮实验，现在最稳的说法是：

- GraspVLA 在当前 public release 下，对 shared calibration track 和 released-distribution-like probe 都很强。
- 当前最早暴露出来的弱点，是**背景变化下的语言条件抓取**，尤其是 `power_drill` 这个 scene。
- 这轮实验**没有**把 transparent 或简单 instruction paraphrase 测成主要瓶颈。

## 证据文件

- 审计目录：[20260406_231349_graspvla_boundary_probes](/D:/codex/grasp-benchmark/artifacts/audits/20260406_231349_graspvla_boundary_probes)
- 总表：[summary.csv](/D:/codex/grasp-benchmark/artifacts/audits/20260406_231349_graspvla_boundary_probes/summary.csv)
- 条件切分：[condition_summary.csv](/D:/codex/grasp-benchmark/artifacts/audits/20260406_231349_graspvla_boundary_probes/condition_summary.csv)
- 视角差值：[view_delta.csv](/D:/codex/grasp-benchmark/artifacts/audits/20260406_231349_graspvla_boundary_probes/view_delta.csv)
- 唯一失败样本：[language_conditioned_single_target_pick__background__003_attempt03.json](/D:/codex/grasp-benchmark/artifacts/audits/20260406_231349_graspvla_boundary_probes/boundary_dual_view/episodes/language_conditioned_single_target_pick__background__003_attempt03.json)

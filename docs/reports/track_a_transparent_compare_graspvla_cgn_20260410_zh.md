# Track A 透明物体对比报告（2026-04-10）

## 范围

- 这份报告只覆盖冻结 benchmark 共享协议下的透明物体子集。
- 它的定位不是：
  - `Track A-Cal` 主榜单
  - `Track B`
- 它的定位是：
  - 用透明 proxy assets 单独看方法行为差异

共享协议没有改：

- 同一套双固定相机
- 同一 shared gripper
- 同一 workspace
- 同一 blocking control
- 同一成功判定：`lift >= 15 cm` 且 `hold >= 2 s`
- 同一 `3-attempt` budget

## 本次用到的运行产物

- `GraspVLA`
  - parent run: `20260409_232700_graspvla_track_a_v2_transparent_shared_sim`
  - 结果文件：`D:\codex\grasp-benchmark\artifacts\runs\20260409_232700_graspvla_track_a_v2_transparent_shared_sim\results.csv`
- `CGN full modular`
  - 原始整批：`20260409_235000_cgn_track_a_v2_transparent_shared_sim`
  - 单场景补跑：
    - `20260410_020500_cgn_track_a_v2_transparent_scene3_shared_sim`
    - `20260410_004500_cgn_track_a_v2_transparent_scene4_shared_sim`
- `AnyGrasp`
  - 目前不能在当前节点上运行，因为你给的 license 和现在机器的 feature id 对不上

## 总结结果

| 方法 | trials | successes | success_rate | mean_attempts | mean_inference_ms |
| --- | --- | --- | --- | --- | --- |
| GraspVLA | 4 | 4 | 1.0 | 1.0 | 408.6251 |
| CGN full modular | 4 | 0 | 0.0 | 3.0 | 4197.7749 |

## 分场景结果

| scene | object | GraspVLA | CGN full modular | 说明 |
| --- | --- | --- | --- | --- |
| `arbitrary_grasping_transparent__transparent__001` | `clear_plastic_cup` | 成功，`lift=20.0384 cm` | 失败，`lift=1.0008 cm` | CGN 不是没 proposal，而是没满足共享 lift/hold 规则 |
| `arbitrary_grasping_transparent__transparent__002` | `glass_bottle` | 成功，`lift=15.1924 cm` | 失败，`lift=1.1253 cm` | 模式相同 |
| `arbitrary_grasping_transparent__transparent__003` | `wine_glass` | 成功，`lift=15.4043 cm` | 失败，`lift=-1.8161 cm` | 这行来自单场景补跑 |
| `arbitrary_grasping_transparent__transparent__004` | `acrylic_box` | 成功，`lift=15.2272 cm` | 失败，`lift=1.1048 cm` | 这行来自单场景补跑 |

## 刚才到底出了什么情况

- 原始 4 场景 CGN transparent 批次不是一开始就挂了。
- 它实际上已经完整跑完了 `001` 和 `002` 的 3 次尝试。
- 然后开始跑 `003`，但在整批 worker 的 wall-clock timeout 到来前，还没来得及把整批最终 `results.csv` 写出来。
- 所以这次的问题本质上是：
  - 不是 `dependency_setup` 崩掉
  - 不是 `grounding_error`
  - 主要是已经有 detection / proposal 之后，固定 shared execution path 还是没把透明物体真正抓起来，最终都落在 `task_failure`

## 这组结果说明什么

- 在这套透明 shared 子集上，当前 public `GraspVLA` release 很强：`4/4`。
- 当前 `CGN full modular` 不是“什么都看不到”，而是：
  - 前面 target isolation / grasp proposal 可以发生
  - 但后面的固定 shared 执行链没有把 proposal 转成满足 benchmark 成功判定的 pickup
- 这也正是 transparent 子集在 benchmark 里有价值的地方：
  - 它能把“proposal 存在”与“真正 benchmark 成功”分开

## AnyGrasp 当前状态

- 透明物体三方法对比现在还卡在 operation 层，不是 benchmark 设计层。
- 你给的 `D:\VLA\license_ZihaoLu` 里面 feature id 是 `7797173549007423731`。
- 当前 `em14` 实际机器 feature id 是 `10649709207478896037`。
- 所以 SDK 在推理前就直接报：
  - `feature id doesn't match the hardware`
- 需要针对当前目标节点重新签一份 license，透明 AnyGrasp 才能补进这张表。

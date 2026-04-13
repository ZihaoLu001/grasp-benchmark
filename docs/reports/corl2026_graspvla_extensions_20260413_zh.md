# GraspVLA CoRL 2026 仿真补强结果更新

## 当前可以正式引用的新增结果

### 1. Track A-Cal v3 主榜单

- `GraspVLA`: `90/90`
- 结果目录：
  [20260412_173009_graspvla_track_a_cal_v3_shared_sim](D:/codex/grasp-benchmark/artifacts/runs/20260412_173009_graspvla_track_a_cal_v3_shared_sim)

这仍然是当前 submission 版唯一的 headline fair table。

### 2. Track A-Stress v3 稳定 hardest-slice appendix

- `GraspVLA`: `108/112`
- 条件拆分：
  - `distractors_heavy`: `29/30`
  - `occlusion_bank`: `20/20`
  - `opaque_clutter`: `28/30`
  - `transparent_pose_bank`: `31/32`
- 结果目录：
  [20260412_174555_graspvla_track_a_stress_v3_shared_sim](D:/codex/grasp-benchmark/artifacts/runs/20260412_174555_graspvla_track_a_stress_v3_shared_sim)

这仍然是当前最稳定、最完整的 stress appendix。

### 3. Instruction Robustness v1

- `GraspVLA`: `29/30`
- 结果目录：
  [20260412_205239_graspvla_instruction_robustness_v1_shared_sim](D:/codex/grasp-benchmark/artifacts/runs/20260412_205239_graspvla_instruction_robustness_v1_shared_sim)

按 family 拆分：

- `basic / canonical`: `5/5`
- `basic / lexical_paraphrase`: `5/5`
- `basic / compositional_paraphrase`: `5/5`
- `distractors_light / canonical`: `4/5`
- `distractors_light / lexical_paraphrase`: `5/5`
- `distractors_light / compositional_paraphrase`: `5/5`

当前结论是：

- basic slice 下，instruction paraphrase 几乎没有带来性能下降
- distractors_light 下，canonical wording 是最弱点，两个 paraphrase 反而都恢复到 `5/5`
- 这说明当前 released GraspVLA 对语言改写并不脆弱，但在轻度 distractor slice 下存在 wording-sensitive scene

### 4. Sim-to-Real Proxy v1

- `GraspVLA`: `15/48`
- 结果目录：
  [20260412_211644_graspvla_sim2real_proxy_v1_shared_sim](D:/codex/grasp-benchmark/artifacts/runs/20260412_211644_graspvla_sim2real_proxy_v1_shared_sim)

按 perturbation family 拆分：

- `camera_jitter`: `8/12`
- `depth_noise_bias`: `7/12`
- `rgb_lighting_background`: `0/12`
- `friction_material_shift`: `0/12`

按任务拆分：

- `language_conditioned_single-target / basic`: `8/16`
- `language_conditioned_single-target / distractors_heavy`: `7/16`
- `arbitrary_transparent / transparent_pose_bank`: `0/16`

这个 suite 的意义很明确：

- 目前 released GraspVLA 对轻微相机 jitter 和 depth bias 仍有一定鲁棒性
- 但对 `RGB lighting/background shift` 和 `friction/material shift` 非常敏感
- transparent transfer slice 在这组 proxy shift 下完全失败，是当前最明显的 transfer 短板

### 5. Phase 2 Pilot v1

- `GraspVLA`: `23/24`
- 结果目录：
  [20260413_023012_graspvla_phase2_pilot_v1_shared_sim](D:/codex/grasp-benchmark/artifacts/runs/20260413_023012_graspvla_phase2_pilot_v1_shared_sim)

按任务拆分：

- `mug_handle_grasp`: `8/8`
- `avoid_inside_cup`: `8/8`
- `power_drill_handle_grasp`: `7/8`

当前结论是：

- 小型 affordance / part-aware extension 已经足够说明 released GraspVLA 不只会做普通 pick-up
- 当前最难的是 `power_drill_handle_grasp`

## 当前仍在执行与排障的新增结果

### Track A-Stress v4

`Track A-Stress v4` 已经代码落地，但**还没有冻结成正式 appendix 结果**。

原因不是 benchmark 协议错误，而是执行稳定性问题：

- 并发 matrix 会把单个 GraspVLA server 压到 `zmq.error.Again`
- 顺序分片是正确方向，但长跑过程中会遇到 server 失活、远端连接被关闭、个别 shard 中断

当前已经验证成功的部分：

- `8` 分片方案中的前 `3` 个 shard 都完成了，累计 `63/63`
- 已确认 `track_a_stress_v4` 的 scene catalog 和 runner 逻辑本身可运行

当前不应对外 claim：

- 不能把任一 `0/168` 的失效 run 当成模型分数
- 不能把尚未补齐全部 shard 的 `v4` 结果写进 submission 主表或最终 appendix 表

当前相关产物：

- 无效并发 run：
  [20260412_215145_graspvla_track_a_stress_v4_shared_sim](D:/codex/grasp-benchmark/artifacts/runs/20260412_215145_graspvla_track_a_stress_v4_shared_sim)
- 无效长单 worker run：
  [20260412_213204_graspvla_track_a_stress_v4_shared_sim](D:/codex/grasp-benchmark/artifacts/runs/20260412_213204_graspvla_track_a_stress_v4_shared_sim)
- 当前有效分片父目录：
  [20260413_025411_graspvla_track_a_stress_v4_shared_sim_seq8](D:/codex/grasp-benchmark/artifacts/runs/20260413_025411_graspvla_track_a_stress_v4_shared_sim_seq8)

## 这轮真正修掉的系统问题

### 1. Sim-to-Real Proxy 的假零分 bug

之前 `sim2real_proxy_v1` 的 `0/48` 不是模型结果，而是 setup-time 断言。

已经确认并修复的根因：

- runtime category 注册时，对 `OBJECTS_DICT` 的去重 key 用错了
- 带 `__shift_family` 后缀的 runtime category 在 LIBERO 注册表里会归一化成单下划线 key
- 导致 runtime object category 重复注册并触发 `AssertionError`

修复后，`sim2real_proxy_v1` 才变成当前正式的 `15/48`

### 2. Setup failure 诊断能力补强

已经补上：

- setup-time traceback 写入 `run_metadata.json`
- setup-time 失败结果保留 `instruction_variant_*`
- setup-time 失败结果保留 `shift_family / shift_severity`

这保证后续再出现 cluster / env 问题时，我们不会只看到一条空的 `AssertionError:`

### 3. Server-backed sharding 调度补强

已经补上：

- `run.sim --matrix-mode sequential`

它的作用是：

- 让 GraspVLA 这类依赖单模型 server 的方法仍然可以分片
- 同时避免并发 shard 抢同一个 server，造成虚假的 timeout failure

### 4. Server 环境漂移定位

已经确认过一次导致 `Track A-Stress v4` 无效的关键问题：

- `gb-core` 中的 `huggingface_hub` 漂移到了 `1.10.1`
- 与当前 `transformers` 版本不兼容
- 导致 `vla_network.scripts.serve` 根本起不来

这个环境问题已经被定位并手动修复到兼容版本

## 当前最稳的论文口径

当前最稳、最适合 CoRL 2026 simulator-first 投稿的写法是：

- `Track A-Cal v3` 用作唯一 headline fair table
- `Track A-Stress v3` 用作当前冻结的 hardest-slice appendix
- `instruction_robustness_v1`、`sim2real_proxy_v1`、`phase2_pilot_v1` 作为新增补强 suite
- `Track A-Stress v4` 作为正在补齐的更强 appendix，不在冻结前写入最终 claim

也就是说，当前 submission-grade 主干已经可以写成：

1. 共享协议下的稳定公平结果
2. released GraspVLA 对 instruction paraphrase 的 robustness
3. released GraspVLA 对 transfer proxy shift 的明确脆弱性
4. released GraspVLA 的小型 affordance / part-aware extension
5. GraspVLA official release 与当前 benchmark protocol 的系统差异审计

## 建议给导师的当前一句话总结

当前 GraspVLA 的 CoRL simulator benchmark 已经从“主榜单强”补到了“语言鲁棒性、transfer proxy、task-oriented extension 三条都已有正式结果”；其中最值得讲的新发现是：

- instruction paraphrase 基本稳
- sim-to-real proxy 对 appearance/material shift 很脆弱
- Phase 2 小型 affordance pilot 很强
- 更大规模的 `stress_v4` appendix 已经打通执行路径，但仍在和 server / cluster 稳定性收尾，不应把中途失效 run 当作模型结果

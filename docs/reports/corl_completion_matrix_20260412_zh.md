# CoRL 2026 仿真阶段完成矩阵（2026-04-12）

## 结论先行

按当前这轮 CoRL simulator-only checklist 来看，**所有可以在现有仿真环境中严谨完成、且不依赖新 license / 真机时间的核心项都已经补齐了**。

已经完成并进入 submission-grade bundle 的部分包括：

- `Track A-Cal v2` 主公平榜单
- `Track A-Stress v2` stress appendix
- `GraspVLA protocol_probe_v2`
- `CGN bottleneck_v1`
- `CGN native appendix`
- `95% CI + exact McNemar + paired bootstrap`
- `paper_ready_report.md / paper_summary.csv / paper_stats.json / teacher_summary_zh.md`

当前没有完成的部分，不是 simulator 内部缺实验，而是**外部阻塞项**：

- `AnyGrasp`：缺与当前节点匹配的新 license
- real-world pilot：缺机器人和相机实验时间
- `Phase 2 constraint / affordance grasping`：按阶段设计仍后置

## 1. CoRL simulator checklist 对照

| 项目 | 当前状态 | 证据 |
| --- | --- | --- |
| 把主公平榜单从 pilot 扩到 paper 级 paired trial 数 | 已完成 | [track_a_cal_v2.yaml](D:/codex/grasp-benchmark/configs/tasks/track_a_cal_v2.yaml), [paper_ready_report.md](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/paper_ready_report.md) |
| 扩 hardest slices（distractors / clutter / transparent） | 已完成 | [track_a_stress_v2.yaml](D:/codex/grasp-benchmark/configs/tasks/track_a_stress_v2.yaml), [paper_ready_report.md](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/paper_ready_report.md) |
| transparent 从 one-off 4 场景扩成 benchmark slice | 已完成 | [track_a_stress_v2.yaml](D:/codex/grasp-benchmark/configs/tasks/track_a_stress_v2.yaml), [paper_ready_report.md](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/paper_ready_report.md) |
| protocol sensitivity / audit | 已完成 | [graspvla_protocol_probe_v2.py](D:/codex/grasp-benchmark/src/grasp_benchmark/audit/graspvla_protocol_probe_v2.py), [summary.csv](D:/codex/grasp-benchmark/artifacts/audits/20260412_080241_graspvla_protocol_probe_v2/summary.csv) |
| oracle / bottleneck 诊断 | 已完成 | [cgn_bottleneck_v1.py](D:/codex/grasp-benchmark/src/grasp_benchmark/audit/cgn_bottleneck_v1.py), [report.md](D:/codex/grasp-benchmark/artifacts/audits/20260412_101317_cgn_bottleneck_v1/report.md) |
| modular native / best-case reference lane | 已完成（CGN） | [track_b_cgn_native_v1.yaml](D:/codex/grasp-benchmark/configs/tasks/track_b_cgn_native_v1.yaml), [paper_ready_report.md](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/paper_ready_report.md) |
| 主表统计层（CI / paired significance / bootstrap） | 已完成 | [stats.py](D:/codex/grasp-benchmark/src/grasp_benchmark/report/stats.py), [paper_summary.csv](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/paper_summary.csv), [paper_stats.json](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/paper_stats.json) |
| paper-ready simulator bundle | 已完成 | [paper_ready_report.md](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/paper_ready_report.md), [teacher_summary_zh_clean.md](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/teacher_summary_zh_clean.md) |
| AnyGrasp 主表插入 | 外部阻塞 | 缺新的 node-matched license；见 [anygrasp_license_mismatch_20260410.md](D:/codex/grasp-benchmark/docs/reports/anygrasp_license_mismatch_20260410.md) |
| real-world pilot | 外部阻塞 | 需要真机时间；当前只到 readiness / checklist |
| `Phase 2 constraint / affordance grasping` | 阶段后置 | 当前阶段目标仍是把 simulator 主 benchmark 和 audit 冻结 |

## 2. 当前 submission-grade simulator 结果

### 2.1 主公平榜单：Track A-Cal v2

- `GraspVLA`: `59 / 60`
- `CGN full modular`: `0 / 60`

证据：

- [paper_ready_report.md](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/paper_ready_report.md)
- [paper_summary.csv](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/paper_summary.csv)

### 2.2 Stress appendix：Track A-Stress v2

- `GraspVLA`: `62 / 64`
- `CGN full modular`: `0 / 64`

证据：

- [paper_ready_report.md](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/paper_ready_report.md)

### 2.3 Native appendix

- 官方 `Track B` `GraspVLA native reference`：保留原生官方上限
- `CGN native appendix`: `1 / 84`

证据：

- [paper_ready_report.md](D:/codex/grasp-benchmark/artifacts/reports/corl_paper_bundle_20260412_full/paper_ready_report.md)
- [results.csv](D:/codex/grasp-benchmark/artifacts/runs/20260412_oom_rerun_track_b_cgn_native_v1_single_scene/results.csv)

### 2.4 Protocol audit

- `GraspVLA` 官方对齐状态：`reproducibility-limited parity`
- `protocol_probe_v2` 最大单因素掉点来自双视角去掉 side view

证据：

- [report.json](D:/codex/grasp-benchmark/artifacts/audits/20260405_042741_graspvla_official_alignment/report.json)
- [summary.csv](D:/codex/grasp-benchmark/artifacts/audits/20260412_080241_graspvla_protocol_probe_v2/summary.csv)

### 2.5 CGN bottleneck

- `D0_shared_cgn = 0 / 24`
- `D1_oracle_grounding = 0 / 24`
- `D2_oracle_grasp = 0 / 24`
- `D3_relaxed_success_rescore = 1 / 24`

证据：

- [report.md](D:/codex/grasp-benchmark/artifacts/audits/20260412_101317_cgn_bottleneck_v1/report.md)

## 3. 为什么这份矩阵里没有再额外加一层 simulator 新套件

这轮没有再额外新造一个 simulator appendix 的原因不是“做不动”，而是**当前 CoRL simulator checklist 里真正缺的项已经补齐**：

- 主榜单规模已经从 pilot 扩成 `60` paired trials
- transparent / distractor / clutter hardest slices 已经扩成正式 appendix
- native lane 已经不再缺 `CGN`
- protocol sensitivity 和 oracle bottleneck 都已经有正式结果
- 统计层和 paper bundle 也已经接好

在这个节点上，再新增一套完全新的 simulator suite，更像是**继续扩 scope**，而不是补“缺失的必要项”。对导师和合作者来说，先把当前 simulator 版结论冻结清楚，比继续横向加新套件更稳。

## 4. 当前对导师/合作者最安全的口径

可以直接这样说：

1. `shared benchmark + protocol audit` 这条 simulator 主线已经补齐到 submission-grade。
2. 当前 public `GraspVLA` 在冻结 shared protocol 下显著强于当前 public `CGN` lane。
3. `CGN` 的低分不是单一 bug、也不是单纯 detector 问题；native lane、oracle grounding、relaxed success 都已经单独检查过。
4. 还没完成的不是 simulator 缺实验，而是 `AnyGrasp license`、real-world pilot、和 `Phase 2` 的阶段后置问题。

## 5. 下一步只剩两类工作

### 5.1 外部阻塞解除后立即继续

- `AnyGrasp` 新 license 到位后，插入主公平表和 native lane
- 真机时间到位后，做小而干净的 paired real-world pilot

### 5.2 当前不建议继续扩的方向

- 现在不建议在 simulator 里继续横向加新的 benchmark 套件
- 现在不建议把 `Phase 2` 提前到 `Phase 1` 前面
- 现在不建议重写 success rule 或 shared protocol

因为这三类动作会让 submission 版 framing 从“补齐缺口”变成“继续扩 scope”，反而增加不确定性

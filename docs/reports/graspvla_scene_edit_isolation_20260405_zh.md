# GraspVLA scene-edit 因子隔离结论

- 这次已经把 `scene edit` 分成两层讲清楚了。
- 在可兼容子集上，`V3 -> V4` 的 success rate 变化是 `+0.0000`，几乎没有可测影响。
- 但在 basket 相关官方任务上，scene edit 不是单纯影响分数，而是公开 release 的兼容性门槛。
- 最新正式 `Track A-Cal` 复跑是 `14/15`，所以 shared calibration 不该再按旧的全 0 口径描述。

## 该怎么对外解释

- `2 cm` 加长爪子不是主因。
- 更严格的 shared success rule 是目前最大的单一可测因素。
- `scene edit` 重要，但要分两层：
- 对 `libero_goal` 这类兼容任务来说，它当前几乎没有可测的性能变化。
- 对 basket 相关官方任务来说，它还是公开 release 的兼容性边界。

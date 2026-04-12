# CGN bottleneck v1 总结

- 当前 shared CGN 基线 `D0` 的结果是 `0/24`。
- `D0 -> D1` 量化的是 detector / segmentation 误差，success-rate 变化是 `+0.0000`。
- `D1 -> D2` 量化的是 grasp proposal 误差，success-rate 变化是 `+0.0000`。
- `D0 -> D3` 量化的是 strict success semantics，success-rate 变化是 `+0.0417`。
- 即使把 perception 和 grasp proposal 都做成 oracle，`D2` 也只有 `0/24`，说明剩余瓶颈还在 planner / execution / shared control mismatch 这一层。

## 论文口径

- 这组实验不是为了替 CGN 提分，而是为了把 shared-lane 的低分拆解成可解释的阶段性瓶颈。
- 论文里它进入 modular bottleneck section，用来支持“CGN shared-lane gap 既有真实方法差异，也有可量化的 pipeline bottleneck”这个主张。

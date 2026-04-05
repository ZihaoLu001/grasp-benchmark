# GraspVLA success rule 因子拆解

- 这次把 `shared success rule` 拆成了更细的三层。
- `env_done -> lift10_hold1` 的变化是 `-0.0500`。
- `lift10_hold1 -> lift15_hold1` 的变化是 `+0.0000`。
- `lift15_hold1 -> lift15_hold10` 的变化是 `+0.0500`。
- 在这个可兼容子集上，三个 success-rule 子项的量级都比较小，而且已经接近单次运行噪声，不适合把某一个子项单独讲成决定性主因。

# GraspVLA protocol probe v2 总结

- 当前正式 `Track A-Cal` 参考仍然是 `14/15`。
- 在固定的 `protocol_probe_v2` 套件上，共享基线 `P0_shared_baseline` 的结果是 `24/24`。
- 这组 probe 只改四类协议因素：视角、attempt budget、success rule、轻微标定扰动。
- 当前掉得最厉害的单因子版本是 `P1_front_only_duplicate`，结果是 `14/24`。
- 相对共享基线，最大的 success-rate drop 出现在 `P1_front_only_duplicate / arbitrary_grasping_transparent / transparent_pose_bank`，差值是 `-1.0`。

## 解读口径

- 这不是新的 benchmark 主榜单，而是 protocol sensitivity audit。
- 它的作用是回答：在不改方法权重的前提下，协议变化会不会改变 GraspVLA 的表现边界。
- 后续论文里这部分进入 audit section，不替代 `Track A-Cal` 主公平表。

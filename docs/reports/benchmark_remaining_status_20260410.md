# Benchmark 剩余工作状态（2026-04-10）

## 已经完成的主干

- `Track B` 官方 `GraspVLA` native simulation 参考结果
- `GraspVLA` 官方对齐审计与边界/瓶颈报告
- `Track A-Cal` 主榜单：
  - `GraspVLA`
  - `CGN full modular`
  - `AnyGrasp full modular`
  的第一版公平比较
- `GraspVLA` 透明物体 shared transparent 子集结果
- `CGN` 透明物体 shared transparent 子集结果

## 还没有完整跑完的 benchmark 文档项

1. `AnyGrasp` 透明物体 shared transparent 子集
   - 当前不是 benchmark 设计问题
   - 当前是 license 和现机器 feature id 不匹配

2. `Track A-Stress` 的完整三方法正式汇总
   - 现在有历史 `GraspVLA/CGN` 压力测试参考
   - 但还没有在最终 modular 栈齐备后做成一版完整三方法正式 stress compare

3. real-world pilot
   - 目前还是 readiness / checklist 状态
   - 还没有形成可汇总的正式真机 benchmark 结果

4. Phase 2 constraint / affordance grasping
   - 例如 handle grasp、rare vocabulary、dense sequence
   - 这部分还没有进入正式执行

5. `Track B` modular native best-case references
   - 当前只有 `GraspVLA` 官方 native reference 是完整的
   - `CGN` / `AnyGrasp` 的 native best-case 参考还没有单独建轨跑完

## 如果按当前文档优先级继续，下一步顺序应该是

1. 先补齐 `AnyGrasp` 当前节点可用的 license
2. 跑完透明物体三方法 shared compare
3. 在不改协议的前提下，补齐 `Track A-Stress` 的最终三方法附录
4. 再决定是真机 pilot 先上，还是直接进入 constraint / affordance 阶段

## 当前一句话判断

- benchmark 主结构已经成立了，不需要推翻
- 现在剩下的主要不是“再想方案”，而是把文档里还缺的执行层逐项补齐

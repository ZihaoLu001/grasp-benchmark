# GraspVLA 公开 release 的能力边界与当前 benchmark 瓶颈

- 当前官方边界结论：`reproducibility-limited parity`。
- 当前主要瓶颈：`shared protocol / distribution gap`。

## 1. 官方 release 当前可稳定支持什么

- `Track B` 官方 native LIBERO/playground 结果可以继续当作公开 release 的原生上限参考，但它不能直接当 shared benchmark 主结论。
- 当前官方对齐子集已经可以稳定跑完，不再有 setup-level blocker。

## 2. 哪些结果只能算 reproducibility-limited

- 当前 `official_aligned subset parity` 应标成 `reproducibility-limited parity`：wrapper 剩余 mismatch 数已经和官方自重复漂移同量级。
- 这轮 `V0a vs V0b` mismatch 为 `3`，`V0a vs V1` mismatch 为 `3`，scene overlap 为 `libero_10__task001__seed005, libero_object__task000__seed003`。

## 3. 哪些 benchmark 结论现在还不能 claim

- 当前 `Track A-Cal` 仍应保留为 provisional，不能拿它直接写成公开 release 在 shared benchmark 下的最终公平结论。
- 在边界澄清完成前，不继续扩 `Track A-Cal`、不继续做 CGN / AnyGrasp 的 headline compare，也不重新设计 success rule。

## 4. 下一步如果要把 Track A 变成可区分 leaderboard，最先该改哪里

- 当前证据更支持先审计 shared protocol 和 released distribution 的对齐，而不是继续怀疑 wrapper 大面积实现错误。

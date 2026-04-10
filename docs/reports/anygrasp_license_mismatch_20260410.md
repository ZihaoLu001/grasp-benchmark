# AnyGrasp License Mismatch Note (2026-04-10)

## Current State

- Supplied local bundle: `D:\VLA\license_ZihaoLu`
- Bundle feature id from `licenseCfg.json`: `7797173549007423731`
- Current `em14` feature id from `license_checker -f`: `10649709207478896037`

Because these ids differ, the current bundle is not valid for the current `em14` machine.

## Observed Runtime Failure

The transparent AnyGrasp run fails before inference with:

- `[FlexivLic] feature id doesn't match the hardware`
- `license passed: False, state: FvrLicenseState.FAILED`

Observed artifact:

- `D:\codex\grasp-benchmark\artifacts\runs\20260409_204341_anygrasp_track_a_v2_transparent_shared_sim\dispatch_stdout.txt`

## Checked Nodes

The previously supplied feature id `7797173549007423731` does not match the nodes we checked:

- `em1`: `10159178958886958230`
- `em3`: `12193295863119209048`
- `em4`: `6666689148041259140`
- `em5`: `9606870544893379858`
- `em6`: `12045452811963641714`
- `em7`: `4376997548859734985`
- `em8`: `15352484936899108131`
- `em9`: `1507615300508215528`
- `em10`: `14500187000273788300`
- `em11`: `4037181983834573186`
- `em12`: `6766731488993056642`
- `em14`: `10649709207478896037`
- `rll_6000_1`: `425548687823975133`
- `rll_6000_2`: `16790495674936142921`

`em2` and `em13` were not reachable at scan time.

## Benchmark Impact

- Historical `Track A-Cal` AnyGrasp artifacts remain preserved as historical results.
- New AnyGrasp execution on the current `em14` setup is blocked until a refreshed license is issued for the current target node.
- The transparent 3-method fairness table is therefore still pending only this operational fix.

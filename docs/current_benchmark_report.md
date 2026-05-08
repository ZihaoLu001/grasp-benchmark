# Current Benchmark Report

Last updated: 2026-05-07.

This is the only detailed report intended to live in the GitHub repository. Generated run artifacts, historical notes, draft reports, slide decks, and intermediate audits should stay outside the tracked documentation surface unless they are folded into this file.

## Scope

`grasp-benchmark` compares grasping systems under two evidence layers:

- `Track A`: shared-protocol fair comparison. Cameras, gripper, workspace, controller semantics, attempt budget, and the lift-and-hold success rule are fixed across methods.
- `Track B`: native-release reference. These numbers are engineering references and are not used for head-to-head fair-comparison claims.

The May 5, 2026 PDF draft is pre-H100-rerun for CGN. Do not share it as-is without revising the CGN tables and text. The current CGN numbers below are from the patched H100 rerun after the post-lift-hold planner fix.

## Current Claim Boundary

- Main fair-comparison claim: Main Shared Grasping Benchmark (`track_a_cal_v3`).
- Supporting diagnostics: Hard Shared Grasping Stress Test (`track_a_stress_v4`), Instruction Robustness Check (`instruction_robustness_v2`), Task-Oriented Grasping Pilot (`phase2_pilot_v1`), and GraspVLA protocol sensitivity probes.
- `AnyGrasp` is excluded from current comparative claims until a fresh node-matched license is available.
- Real-world pilot experiments are not yet complete.
- `Track B` remains native-reference only.

## Headline Results

| suite | GraspVLA | CGN shared lane | interpretation |
| --- | ---: | ---: | --- |
| Main Shared Grasping Benchmark (`track_a_cal_v3`) | `88 / 90` | `25 / 90` (`27.78%`) | headline fair table |
| Hard Shared Grasping Stress Test (`track_a_stress_v4`) | `160 / 168` | `20 / 168` (`11.90%`) | hardest-slice appendix |
| Instruction Robustness Check (`instruction_robustness_v2`) | `38 / 40` | `8 / 40` (`20.00%`) | prompt/paraphrase diagnostic |
| Task-Oriented Grasping Pilot (`phase2_pilot_v1`) | `23 / 24` | `0 / 24` (`0.00%`) | small task-oriented extension |

Patched CGN rerun status:

- Lakeshore jobs `364545-364563` all completed with `ExitCode=0:0`.
- Main Shared Grasping Benchmark (`track_a_cal_v3`) completed all four CGN shards at `25 / 90` (`27.78%`).
- Hard Shared Grasping Stress Test (`track_a_stress_v4`) completed all four CGN shards at `20 / 168` (`11.90%`).
- Instruction Robustness Check (`instruction_robustness_v2`) completed all four CGN shards at `8 / 40` (`20.00%`).
- Task-Oriented Grasping Pilot (`phase2_pilot_v1`) completed all four CGN shards at `0 / 24` (`0.00%`).
- Machine-readable tracked evidence: `configs/results/cgn_h100_posthold_20260507.json`.
- The canonical patched suites recorded zero wrong-object successes.

Historical pre-patch H100 successes are kept only as diagnostic context. They all came from arbitrary opaque watermelon:

- `track_a_cal_v3`: `watermelon / opaque_basic / r02`, attempt 1, lift `31.5338 cm`, hold `2.0 s`
- `track_a_stress_v4`: `watermelon / opaque_clutter / r06`, attempt 2, lift `47.0583 cm`, hold `2.0 s`
- `track_a_stress_v4`: `watermelon / opaque_clutter / r07`, attempt 2, lift `31.5338 cm`, hold `2.0 s`

## Contact-GraspNet / CGN Interpretation

In this repository, `cgn` means the benchmark-owned `CGN shared lane`, not a bare Contact-GraspNet native release:

1. Language-target tasks use `GroundingDINO` to localize the requested target.
2. Depth segmentation builds a mask and constrained point cloud.
3. Contact-GraspNet generates grasp proposals from the constrained point cloud.
4. The shared benchmark planner/controller converts proposals into actions.
5. Success is measured by the frozen Track A `15 cm / 2 s` lift-and-hold rule.

For arbitrary-object tasks, the lane first tries catalog-label GroundingDINO and then falls back to foreground-depth segmentation. `oracle_gt` is diagnostic only.

Older `0/N` CGN results were real pre-rerun shared-lane evidence, but they must not be described as official Contact-GraspNet native-system performance and do not establish that official Contact-GraspNet capability is zero. After the Lakeshore H100 runtime migration and post-lift-hold planner patch, the correct collaborator-facing wording is:

> CGN shared lane is nonzero under the frozen shared protocol, and the previous near-zero table was affected by a benchmark integration issue. The pre-patch May 7 H100 rerun produced `1/90`, `2/168`, `0/40`, and `0/24`. After the post-lift-hold planner patch, the completed H100 rerun is `25/90`, `20/168`, `8/40`, and `0/24`. Remaining failures are split across GroundingDINO misses, zero Contact-GraspNet proposals, pose/control conversion, and strict lift-hold success semantics.

## CGN Implementation Audit

May 7 audit conclusion: the low CGN success rate should not be interpreted as official Contact-GraspNet native capability. The H100 runtime can produce proposals, but the benchmark-owned shared lane still has implementation-contract risks between proposal, planning, control, and success accounting.

Confirmed implementation issue now fixed in code:

- The shared modular planner previously ended the attempt immediately after the lift trajectory. Because Track A success requires `15 cm` lift and `10` control steps (`2 s` at `5 Hz`) of hold, this could fail episodes that had already lifted the object but had not held it long enough. `planner.post_lift_hold_steps: 12` has been added for CGN so the gripper stays closed after lift.
- Planner orientation interpolation now uses SO(3) relative rotation chunks instead of subtracting Euler vectors and treating the result as repeated relative rotations.
- CGN candidate filtering now validates `gripper_opening_m` against the Franka gripper opening range before planning, so impossible-width proposals are skipped rather than executed.

High-risk items that still require targeted ablation:

- Contact-GraspNet's upstream pose convention is not simply "object contact point as target pose." The upstream implementation builds the grasp translation as contact point plus half width along the gripper base axis minus gripper depth along the approach axis. The shared planner now has an explicit `grasp_frame_to_tcp_matrix`; it is currently identity and labeled `explicit_identity_shared_lane_not_native_calibration`, so a native CGN-gripper-frame to Franka TCP/tool-frame calibration remains required before any official-CGN-style claim.
- The runner records `contact_point_cam` and `gripper_opening_m`; width range filtering is now enforced, but the shared `Action` contract still uses binary open/close commands rather than continuous gripper-width commands.
- GroundingDINO plus depth-band masking is fragile for language scenes and transparent/fallback cases; the H100 rerun still has many `grounding_error` and `grasp_proposal` failures.
- The camera image/depth/mask flip path and real robosuite camera extrinsics need a geometry smoke test with a known 3D point, not only identity-matrix unit tests.

Post-fix H100 diagnostic:

- `1/90`, `2/168`, `0/40`, and `0/24` are valid records of the May 7 pre-patch shared-lane run.
- They should be described as "pre-patch CGN shared-lane diagnostics," not as final Contact-GraspNet capability.
- A targeted patched H100 rerun of `oracle_gt + real CGN` on `cgn_bottleneck_v2` completed successfully as `20260507_cgn_posthold_oracle_gt_real_cgn_h100`: `3 / 12` successes, all with `hold_s = 2.0`.
- The diagnostic successes were `ceramic_bowl / basic` (`15.3344 cm`), `banana / distractors_heavy` (`17.6541 cm`, with `wrong_object = 1`), and `power_drill / distractors_heavy` (`16.4609 cm`). That wrong-object flag belongs to the bottleneck diagnostic only, not to the canonical patched suite table.
- The full patched CGN rerun batch completed as Slurm jobs `364545-364563`; manifest path:

```text
/projects/cs_yifan16_chi/zlu31/grasp-benchmark/artifacts/slurm/cgn_posthold_full_20260507_01/manifest.tsv
```

Practical claim boundary after this audit:

- The post-hold diagnostic confirms that at least part of the low CGN score was a shared planner/controller timing bug.
- The patched CGN results can be used as the current benchmark-owned CGN shared-lane table, with the explicit caveat that this is not official Contact-GraspNet native-system performance.

## CGN Native-Reference Appendix

The official-filtering native-reference appendix completed on Lakeshore after commit `a92cdf70b883a6686bc3ad71b522060671cfb535`.

Result:

- `track_b_cgn_native_v2`: `39 / 138` (`28.26%`)
- language-conditioned single-target pick: `20 / 60`
- arbitrary opaque grasping: `19 / 30`
- transparent-object grasping: `0 / 48`
- wrong-object successes: `0`

Slurm/evidence status:

- GPU shards `364696-364699` all completed with `ExitCode=0:0` on `ghi2-002`.
- CPU finalizer `364723` completed with `ExitCode=0:0` on `a-001`.
- Finalizer output:

```text
/projects/cs_yifan16_chi/zlu31/grasp-benchmark/artifacts/slurm/cgn_native_official_20260507_a92cdf7/final_summary.json
/projects/cs_yifan16_chi/zlu31/grasp-benchmark/artifacts/slurm/cgn_native_official_20260507_a92cdf7/final_summary.md
```

Tracked evidence:

```text
configs/results/cgn_native_reference_h100_20260507.json
```

Official-filtering contract checked by trace evidence:

- raw fused point cloud input with `segment_ids`
- Contact-GraspNet `pc_segments`
- `local_regions=True`
- `filter_grasps=True`
- TensorFlow GPU visibility

The finalizer checked `939` saved debug payloads; all `939` confirmed local region/filter grasp usage and TensorFlow GPU visibility. This is a stronger engineering reference than the shared-lane result, but it is still not an official Contact-GraspNet native-system score because the benchmark planner/controller and success rule remain benchmark-owned.

## Lakeshore / H100 Status

Lakeshore is a Slurm cluster. The login node is for file management, editing, and job submission; GPU experiments must run through `srun`, `sbatch`, or `salloc`.

Project files, conda environments, package caches, and artifacts are pinned under:

```text
/projects/cs_yifan16_chi/zlu31
```

The current H100-compatible CGN runtime is:

```text
env:        /projects/cs_yifan16_chi/zlu31/conda_envs/gb-cgn-tf212
python:     3.10
tensorflow: 2.12.0
cuda:       11.8
cudnn:      8.6
custom ops: sm_80/sm_86/sm_89/sm_90 + compute_90 PTX
```

The saved H100 probe records `NVIDIA H100 NVL`, completed TensorFlow matmul, completed PointNet++ sampling, and raw Contact-GraspNet returned `47` grasps in about 21.2 seconds. Current Slurm feature labels may not be a reliable substitute for that saved allocation/probe artifact.

The valid pre-patch Lakeshore rerun batch was `364039-364062`; all jobs completed with `ExitCode=0:0`. The full patched Lakeshore rerun batch was `364545-364563`; all jobs completed with `ExitCode=0:0`. The first attempted batch, `364009-364032`, failed immediately because `set -u` conflicted with the conda activation hook and did not produce valid experiment evidence.

Remote evidence paths:

```text
/projects/cs_yifan16_chi/zlu31/grasp-benchmark/artifacts/slurm/cgn_posthold_full_20260507_01/manifest.tsv
/projects/cs_yifan16_chi/zlu31/grasp-benchmark/artifacts/runs/20260507_posthold_cgn_*
```

Tracked local evidence:

```text
configs/results/cgn_h100_posthold_20260507.json
configs/results/cgn_native_reference_h100_20260507.json
```

## Failure Breakdown

Patched May 7 CGN shared-lane failures:

- `track_a_cal_v3`: `task_failure = 29`, `grounding_error = 24`, `grasp_proposal = 12`
- `track_a_stress_v4`: `task_failure = 68`, `grounding_error = 32`, `grasp_proposal = 48`
- `instruction_robustness_v2`: `grounding_error = 16`, `task_failure = 8`, `grasp_proposal = 8`
- `phase2_pilot_v1`: `grasp_proposal = 16`, `task_failure = 8`

The two most repeated grounding failures are `power drill` and `carrot`; both should be checked before attributing all remaining failures to Contact-GraspNet proposal quality.

`cgn_bottleneck_v2` diagnostics:

| variant | trials | successes | max lift | failure distribution |
| --- | ---: | ---: | ---: | --- |
| full CGN | 12 | 0 | `0.0818 cm` | task_failure 4, grounding_error 4, grasp_proposal 4 |
| `oracle_gt + real CGN` | 12 | 0 | `18.5624 cm` | grasp_proposal 7, task_failure 5 |
| `oracle_gt + real CGN`, post-hold patch | 12 | 3 | `17.6541 cm` | grasp_proposal 7, task_failure 2 |
| `oracle_gt + topdown_centroid` | 12 | 0 | `9.9936 cm` | task_failure 7, planner_failure 5 |

Banana targeted diagnostics show that partial lift is possible, but the controller does not reliably sustain the official success rule:

- real CGN trace: `0`, lift `0.0 cm`
- oracle topdown trace: `0`, lift `7.9696 cm`
- oracle topdown, `5 cm` threshold and 2-step hold: `1`, lift `7.9696 cm`
- oracle topdown, `8 cm` threshold and 1-step hold: `0`, lift `7.9696 cm`

## Reproduction Pointers

Local tests:

```powershell
$env:PYTHONPATH = (Resolve-Path "src").Path
python -m pytest tests -q
```

Lakeshore preflight:

```powershell
python -m grasp_benchmark.preflight --cluster-config lakeshore --pool lakeshore --output artifacts/preflight/lakeshore_available_nodes.json
```

Prepare or revalidate H100-compatible Contact-GraspNet:

```powershell
python -m grasp_benchmark.prepare_cgn --node lakeshore --cluster-config lakeshore --bootstrap-legacy-env --compile-tf-ops
```

Dry-run a Lakeshore CGN job:

```powershell
python -m grasp_benchmark.run.sim --cluster-config lakeshore --method cgn --task-set cgn_bottleneck_v2 --node lakeshore --available-nodes artifacts/preflight/lakeshore_available_nodes.json --dry-run
```

## Recommended Collaborator Wording

Use this concise wording in email or meetings:

> We rechecked the CGN lane because the earlier all-zero result looked suspicious. In this repository, CGN is a benchmark-owned shared modular lane: GroundingDINO localization, depth masking, Contact-GraspNet proposals, and the shared planner/controller under a frozen `15 cm / 2 s` success rule. The old `0/N` result was pre-rerun shared-lane evidence and should not be presented as official Contact-GraspNet native performance. After migrating the Lakeshore runtime to TensorFlow 2.12 / CUDA 11.8 / cuDNN 8.6, raw Contact-GraspNet proposal generation works on the H100-probed setup. The May 7 pre-patch rerun was nonzero but still weak: `1/90`, `2/168`, `0/40`, and `0/24`. We then found and patched a shared planner timing bug: the CGN plan ended immediately after lift, before the required hold window. The full patched H100 rerun completed successfully and now gives `25/90`, `20/168`, `8/40`, and `0/24`. This is the current benchmark-owned CGN shared-lane result, not an official Contact-GraspNet native-system result.

For native-reference context only, we also completed the official-filtering CGN appendix on `track_b_cgn_native_v2`: `39/138` with all four GPU shards completed and `939/939` debug traces confirming `pc_segments`, `local_regions=True`, `filter_grasps=True`, and TensorFlow GPU visibility. This appendix should be described as engineering context, not as a fair shared-protocol headline result.

# Policy-Anchored VLA Experiment Scaffold

This directory configures the next continual VLA comparison using explicit policy anchoring, the fixed offline pilot results, and the online RL reference code under `third_party/continual-vla-rl`.

## Position

The experiment should not claim that offline BC, SCA, or OPD is the same training protocol as online RL. The clean comparison is:

- **Online reference:** Seq-RL + LoRA from `continual-vla-rl`, which updates from the current policy's own rollouts.
- **Offline baselines:** Seq BC/OFT, action-level SCA, teacher distillation, and seen-task anchoring.
- **Point baseline:** Policy-Anchored Imitation, which preserves previous-policy actions at old/anchor samples.
- **Main method:** Behavioral Field Anchoring, which also preserves the previous policy's local action-field geometry around old/anchor samples.
- **VLA-OPD-style proxy:** `opd_rollout_distill`, a continuous OpenVLA-OFT approximation that first collects previous-policy teacher targets on policy-induced rollout states, then distills those targets during the next offline task update.
- **Question:** how much of online RL's support-preserving behavior can be recovered without paying the online interaction cost?

The official `irpn-lab/VLA-OPD` repository is included as `third_party/vla-opd`, but at the pinned revision it only contains the project page and marks training code as "Coming Soon". Any `opd_rollout_distill` result should therefore be reported as an internal continuous-action proxy, not as an official VLA-OPD reproduction.

## Generate Lakeshore Jobs

From the repository root:

```powershell
.\scripts\prepare_sca_vla_next_experiments.ps1
```

This creates:

```text
artifacts/sca_vla_next/<timestamp>/
  manifest.json
  commands/
    dry_run_policy_anchor_smoke.sh
    submit_policy_anchor_smoke.sh
    submit_policy_anchor_full.sh
    dry_run_behavior_field_anchor_smoke.sh
    submit_behavior_field_anchor_smoke.sh
    submit_behavior_field_anchor_full.sh
    submit_opd_rollout_distill_smoke.sh
    submit_opd_rollout_distill_full.sh
    prepare_seq_rl_checkpoints.sh
  jobs/
    sca-vla-seq-rl-ref-libero-spatial.sbatch
    sca-vla-offline-collect-libero-spatial.sbatch
    sca-vla-seq-rl-ref-libero-object.sbatch
    sca-vla-offline-collect-libero-object.sbatch
```

To generate only the official online reference scripts:

```powershell
.\scripts\prepare_sca_vla_next_experiments.ps1 -NoOfflineCollect -NoPolicyAnchor
```

To generate only one suite:

```powershell
.\scripts\prepare_sca_vla_next_experiments.ps1 -Suites libero_spatial
```

## What To Run First

1. Generate the jobs.
2. Sync this repo to Lakeshore so `third_party/continual-vla-rl` is available under `/projects/cs_yifan16_chi/zlu31/grasp-benchmark/third_party/continual-vla-rl`.
3. Apply the `policy_anchor` patch to the active OpenVLA-OFT/SCA cluster checkout.
4. Run `commands/dry_run_policy_anchor_smoke.sh` on Lakeshore.
5. Run `commands/submit_behavior_field_anchor_smoke.sh`; only submit the full chain after the smoke produces non-degenerate `current_frac` metrics, finite BFA field diagnostics, and eval JSON.
6. Run the `opd_rollout_distill` smoke as a VLA-OPD-style diagnostic. It should produce an `opd_rollout_cache.pt` for stages after 0 plus `opd/loss` and `opd/target_teacher_drift` training metrics.
7. Collect offline summaries from the fixed pilot root:
   `/projects/cs_yifan16_chi/zlu31/sca-vla/artifacts/continual_oft_fixed_pilot`
8. Prepare Seq-RL checkpoints with `commands/prepare_seq_rl_checkpoints.sh`, then run only a one-task Seq-RL smoke before any full online reference job.

## Minimum Table

| Suite | Offline Seq | Action SCA | Teacher Distill | Anchor Replay | Point Anchor | Behavioral Field Anchor | Seq-RL Reference | Interaction Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| LIBERO-Spatial | TBD | TBD | TBD | TBD | TBD | TBD | TBD | env rollouts for OPD proxy and Seq-RL |
| LIBERO-Object | TBD | TBD | TBD | TBD | TBD | TBD | TBD | env rollouts for OPD proxy and Seq-RL |

## Diagnostics

The next code pass should add result readers for:

- previous-policy action drift vs forgetting
- behavioral field drift vs forgetting
- rollout drift from previous teacher
- distill current/old mask sanity
- LoRA effective rank / SVD
- memory size and online interaction cost

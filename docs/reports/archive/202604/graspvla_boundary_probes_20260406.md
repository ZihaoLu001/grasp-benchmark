# GraspVLA Boundary Probes (2026-04-06)

## Headline

- Latest formal `Track A-Cal` reference remains `14/15`.
- On the dedicated 28-trial boundary suite, dual-view GraspVLA reached `27/28 = 0.9643`.
- On the same suite with the `front_only_duplicate` proxy, GraspVLA reached `28/28 = 1.0000`.
- Mean inference time stayed in the same range as the rest of the benchmark: about `289.6 ms` for dual-view and `299.7 ms` for the front-only proxy.

## What Worked Well

- `language_conditioned_single_target_pick`: `14/15`
- `language_paraphrase_grab`: `3/3`
- `language_paraphrase_lift`: `3/3`
- `language_paraphrase_pickup`: `3/3`
- `arbitrary_grasping_transparent`: `4/4`

On this probe, GraspVLA stayed strong under:

- basic opaque picks
- lighting changes
- distractors
- modest height offsets
- simple verb paraphrases such as `grab`, `lift`, and `pick ... up`
- the current transparent-object proxy subset

## Observed Soft Boundary

The only failure in the dual-view run was:

- `language_conditioned_single_target_pick__background__003`
- object: `power_drill`
- condition: `background`
- result: failed after `3` attempts, final lift `-0.1796 cm`

This makes `language_conditioned_single_target_pick / background` the weakest slice in the current probe at `2/3 = 0.6667`.

However, the same scene succeeded under the `front_only_duplicate` proxy in `2` attempts with lift `28.8605 cm`. That means the current evidence supports the interpretation:

- this is a **local instability hotspot**
- not yet a hard, repeatable failure boundary for the public release

## What This Probe Does Not Show As a Boundary

This specific probe did **not** surface the following as clear failure boundaries:

- transparent objects
- simple instruction paraphrases
- removal of the side camera via the `front_only_duplicate` proxy

That does **not** prove those factors never matter. It only means they did not degrade performance on this compact released-distribution-like probe.

## Important Caveats

- `front_only_duplicate` is a **view-ablation proxy**, not a retrained single-view checkpoint. It duplicates the front image into both RGB slots because the released GraspVLA server expects two RGB inputs.
- The transparent-object subset here uses the benchmark's shared transparent proxy assets, not the full real-world transparent evaluation from the paper.
- The current probe is still compact: `28` trials, `3` opaque native objects for language conditions, and `4` transparent proxy scenes. It is good for boundary detection, but not enough to make sweeping claims about all forms of generalization.

## Practical Interpretation

For the current public release, the most defensible boundary statement is:

- GraspVLA is **stable and strong** on the shared calibration track and on a compact released-distribution-like probe.
- Its first visible weakness on this probe is **background-shifted language-conditioned grasping**, especially for the `power_drill` scene.
- The strongest failure boundary is **not** transparent objects or simple wording changes on this specific suite.

## Evidence

- Audit root: [20260406_231349_graspvla_boundary_probes](/D:/codex/grasp-benchmark/artifacts/audits/20260406_231349_graspvla_boundary_probes)
- Summary: [summary.csv](/D:/codex/grasp-benchmark/artifacts/audits/20260406_231349_graspvla_boundary_probes/summary.csv)
- Condition breakdown: [condition_summary.csv](/D:/codex/grasp-benchmark/artifacts/audits/20260406_231349_graspvla_boundary_probes/condition_summary.csv)
- View delta: [view_delta.csv](/D:/codex/grasp-benchmark/artifacts/audits/20260406_231349_graspvla_boundary_probes/view_delta.csv)
- Failed episode: [language_conditioned_single_target_pick__background__003_attempt03.json](/D:/codex/grasp-benchmark/artifacts/audits/20260406_231349_graspvla_boundary_probes/boundary_dual_view/episodes/language_conditioned_single_target_pick__background__003_attempt03.json)

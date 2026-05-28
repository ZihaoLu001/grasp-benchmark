# Third-Party Research Code

This directory holds external repositories used only as references or experiment baselines.

## `continual-vla-rl`

- Repository: <https://github.com/UT-Austin-RobIn/continual-vla-rl>
- Local path: `third_party/continual-vla-rl`
- Purpose: reference implementation for the online Seq-RL + LoRA continual VLA baseline from *Simple Recipe Works: Vision-Language-Action Models are Natural Continual Learners with Reinforcement Learning*.
- Current local commit when added: `dc1b1c8a7fb630c8d9aaf349376ae5a49b575b4e`

Project code should treat this as read-only. Add wrappers, configs, and analysis utilities in this repository instead of patching the third-party checkout directly.

## `vla-opd`

- Repository: <https://github.com/irpn-lab/VLA-OPD>
- Local path: `third_party/vla-opd`
- Purpose: reference project page for *VLA-OPD: Bridging Offline SFT and Online RL for Vision-Language-Action Models via On-Policy Distillation*.
- Current local commit when added: `b34eda8a1a7c84222a778a52205b791c65d2ed3e`
- Status at this commit: project page only; training code is marked "Code (Coming Soon)".

Because official training code is not available at this revision, any cluster experiment named `opd_rollout_distill` or `vla_opd_style` is our internal continuous OpenVLA-OFT proxy. Report it separately from official VLA-OPD.

# grasp-benchmark

`grasp-benchmark` is a benchmark scaffold for fair comparison between end-to-end and modular grasping systems under a shared-perception, shared-embodiment setup.

## Scope

- Track A only for the first release.
- Three baselines: `GraspVLA`, `AnyGrasp + Grounding DINO + motion planner`, and `Contact-GraspNet + segmentation + Grounding DINO + motion planner`.
- Two task clusters: `language-conditioned single-target pick` and `transparent arbitrary grasping`.
- Simulation first, then a small `Franka + dual RealSense + blocking` real-world pilot.

## Layout

- `src/grasp_benchmark/`: Python package and CLIs
- `configs/`: benchmark, sensor, method, and cluster YAML
- `cluster/`: remote bootstrap and environment scripts
- `scripts/`: local convenience wrappers
- `artifacts/`: generated manifests, preflight reports, runs, and reports
- `third_party/upstreams/`: upstream repos cloned by `fetch_upstreams`

## Quick Start

1. Install the package in editable mode:

```powershell
python -m pip install -e .
```

2. Run cluster preflight:

```powershell
python -m grasp_benchmark.preflight --pool em,rll
```

3. Clone upstream repos:

```powershell
python -m grasp_benchmark.fetch_upstreams
```

4. Bootstrap the shared remote environment:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_cluster.ps1 -Node em14
```

5. Install method-specific remote dependencies:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_remote_deps.ps1 -Method graspvla -Node em14
```

For AnyGrasp, install the public Python stack and then capture the feature id needed for license registration:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_remote_deps.ps1 -Method anygrasp -Node em14
python -m grasp_benchmark.prepare_anygrasp --node em14
```

For Contact-GraspNet, install the shared detector stack and then probe or bootstrap the legacy TensorFlow 2.2 runtime:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_remote_deps.ps1 -Method cgn -Node em14
python -m grasp_benchmark.prepare_cgn --node em14 --bootstrap-legacy-env
```

6. Launch the GraspVLA model server:

```powershell
python -m grasp_benchmark.serve.graspvla --node em14 --download-model
```

7. Generate a simulation dispatch manifest:

```powershell
python -m grasp_benchmark.run.sim --method graspvla --task-set track_a_v1 --dry-run
```

8. Run a small integration batch and fetch results back to `artifacts/runs/...`:

```powershell
python -m grasp_benchmark.run.sim --method graspvla --task-set track_a_v1 --node em14 --max-trials 2
```

9. Aggregate result files:

```powershell
python -m grasp_benchmark.report.aggregate --input artifacts\runs
```

## Notes

- The project uses `src/` layout, so `python -m grasp_benchmark...` requires `pip install -e .`.
- The generated `available_nodes.json` is the source of truth for dispatch selection.
- Remote environments are rooted at `/datasets/ss/current/zihao/miniforge3`, with env packages stored under `/datasets/ss/current/zihao/conda`.
- Archive-based cluster sync now preserves remote `artifacts/` and `third_party/upstreams/` directories and writes `.grasp-benchmark-sync.json` for commit provenance.
- `run.worker` now executes an integration-fixture backend that writes benchmark-shaped `results.csv` plus per-attempt artifacts under `episodes/`. This is the common adapter/logging layer that will later be swapped under real simulation or robot controllers.
- `python -m grasp_benchmark.install_remote --method anygrasp` now installs GroundingDINO in CPU-only mode and prepares the version-matched SDK binaries, but AnyGrasp still needs MinkowskiEngine and a real license file.
- `python -m grasp_benchmark.prepare_anygrasp --node em14` writes an artifact with the machine feature id plus current import/license status to help the license request flow.
- `python -m grasp_benchmark.install_remote --method cgn` installs shared detector dependencies only; `python -m grasp_benchmark.prepare_cgn --node em14 --bootstrap-legacy-env` prepares and probes the separate legacy TensorFlow runtime that Contact-GraspNet still needs.

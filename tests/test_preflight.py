from __future__ import annotations

import unittest

from grasp_benchmark.preflight import _build_probe_script, _parse_probe_output
from grasp_benchmark.shell import CommandResult


class PreflightTest(unittest.TestCase):
    def test_nvidia_smi_error_is_not_recorded_as_gpu(self) -> None:
        probe = _parse_probe_output(
            host="lakeshore",
            pool="lakeshore",
            cluster_config={
                "required_bins": ["git", "python3"],
                "optional_bins": ["nvidia-smi"],
                "known_failures": {},
                "known_warnings": {},
            },
            result=CommandResult(
                args=["ssh", "lakeshore"],
                returncode=0,
                stdout="\n".join(
                    [
                        "__GB_HOSTNAME__=login001-lakeshore",
                        "__GB_BIN__=git:1",
                        "__GB_BIN__=python3:1",
                        "__GB_BIN__=nvidia-smi:1",
                        "__GB_REMOTE_ROOT__=1",
                        "__GB_MINIFORGE__=1",
                        "__GB_GPU_ERROR__=NVIDIA-SMI has failed because it could not communicate with the NVIDIA driver.",
                    ]
                ),
                stderr="",
            ),
        )

        self.assertEqual(probe.gpu_names, [])
        self.assertEqual(probe.gpu_error[:10], "NVIDIA-SMI")
        self.assertIn("gpu_not_reported", probe.warnings)
        self.assertTrue(any(note.startswith("nvidia_smi_error:") for note in probe.notes))

    def test_probe_script_loads_lakeshore_slurm_before_binary_checks(self) -> None:
        script = _build_probe_script(
            {
                "project_disk_probe": "/projects/cs_yifan16_chi/zlu31",
                "remote_root": "/projects/cs_yifan16_chi/zlu31/grasp-benchmark",
                "miniforge_root": "/projects/cs_yifan16_chi/zlu31/miniforge3",
                "required_bins": ["srun", "sinfo"],
                "optional_bins": [],
                "source_files": ["/etc/profile.d/modules.sh"],
                "module_loads": ["slurm/lakeshore/23.02.4"],
                "scheduler": {
                    "type": "slurm",
                    "account": "cs_yifan16_chi",
                    "partition": "batch_gpu2",
                    "gres": "gpu:1",
                    "matrix_slots": 4,
                },
            }
        )

        self.assertLess(script.index('/etc/profile.d/modules.sh'), script.index('__GB_BIN__=srun'))
        self.assertLess(script.index('module load "slurm/lakeshore/23.02.4"'), script.index('__GB_BIN__=sinfo'))
        self.assertIn("__GB_SLURM_PARTITION_INFO__", script)
        self.assertIn("__GB_GPU__=slurm:batch_gpu2:gpu:1:slot3", script)

    def test_slurm_partition_probe_counts_as_gpu_backed(self) -> None:
        probe = _parse_probe_output(
            host="lakeshore",
            pool="lakeshore",
            cluster_config={
                "required_bins": ["git", "python3", "srun", "sinfo"],
                "optional_bins": ["nvidia-smi"],
                "known_failures": {},
                "known_warnings": {"lakeshore": "login_node_no_visible_gpu_use_slurm_allocation"},
            },
            result=CommandResult(
                args=["ssh", "lakeshore"],
                returncode=0,
                stdout="\n".join(
                    [
                        "__GB_HOSTNAME__=login001-lakeshore",
                        "__GB_BIN__=git:1",
                        "__GB_BIN__=python3:1",
                        "__GB_BIN__=srun:1",
                        "__GB_BIN__=sinfo:1",
                        "__GB_BIN__=nvidia-smi:1",
                        "__GB_REMOTE_ROOT__=1",
                        "__GB_MINIFORGE__=1",
                        "__GB_SCHEDULER__=slurm",
                        "__GB_SLURM_ACCOUNT__=cs_yifan16_chi",
                        "__GB_SLURM_PARTITION__=batch_gpu2",
                        "__GB_SLURM_GRES__=gpu:1",
                        "__GB_SLURM_PARTITION_STATUS__=0",
                        "__GB_SLURM_PARTITION_INFO__=gpu:4(S:0-1)|mix|ghi2-002",
                        "__GB_GPU__=slurm:batch_gpu2:gpu:1:slot0",
                        "__GB_GPU_ERROR__=NVIDIA-SMI has failed because it could not communicate with the NVIDIA driver.",
                    ]
                ),
                stderr="",
            ),
        )

        self.assertEqual(probe.gpu_names, ["slurm:batch_gpu2:gpu:1:slot0"])
        self.assertEqual(probe.scheduler["type"], "slurm")
        self.assertEqual(probe.scheduler["partition"], "batch_gpu2")
        self.assertIn("configured_warning:login_node_no_visible_gpu_use_slurm_allocation", probe.warnings)


if __name__ == "__main__":
    unittest.main()

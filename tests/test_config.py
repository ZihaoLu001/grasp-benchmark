from __future__ import annotations

import unittest

from grasp_benchmark.config import load_named_config


class ConfigTest(unittest.TestCase):
    def test_cluster_config_contains_expected_keys(self) -> None:
        config = load_named_config("cluster", "default")
        self.assertIn("remote_root", config)
        self.assertIn("pool_hosts", config)
        self.assertIn("default_graspvla_node", config)


if __name__ == "__main__":
    unittest.main()


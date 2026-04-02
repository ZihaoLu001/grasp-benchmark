from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from grasp_benchmark.provenance import load_sync_metadata, resolve_commit, sync_metadata_path


class ProvenanceTest(unittest.TestCase):
    def test_load_sync_metadata_reads_archive_sync_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            sync_metadata_path(project_root).write_text(
                json.dumps({"commit": "deadbeef", "branch": "main"}),
                encoding="utf-8",
            )
            metadata = load_sync_metadata(project_root)
            self.assertEqual(metadata["commit"], "deadbeef")

    def test_resolve_commit_falls_back_to_sync_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            sync_metadata_path(project_root).write_text(
                json.dumps({"commit": "cafebabe"}),
                encoding="utf-8",
            )
            self.assertEqual(resolve_commit(project_root), "cafebabe")


if __name__ == "__main__":
    unittest.main()

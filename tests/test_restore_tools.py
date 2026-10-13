import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import restore_backup
import verify_restore


class RestoreToolTests(unittest.TestCase):
    def test_restore_rejects_path_traversal_keys(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            with self.assertRaisesRegex(ValueError, "escapes restore directory"):
                restore_backup._safe_destination(root, "recovery/run/../outside.txt", "recovery/run/")

    def test_hash_verification_reports_matching_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source"
            restored = Path(temporary_directory) / "restored"
            source.mkdir()
            restored.mkdir()
            (source / "nested").mkdir()
            (restored / "nested").mkdir()
            (source / "nested" / "record.txt").write_text("same content", encoding="utf-8")
            (restored / "nested" / "record.txt").write_text("same content", encoding="utf-8")

            result = verify_restore.verify(source, restored)

            self.assertTrue(result["passed"])
            self.assertEqual(result["files_checked"], 1)
            self.assertEqual(result["results"][0]["status"], "match")

    def test_hash_verification_fails_for_missing_and_changed_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source"
            restored = Path(temporary_directory) / "restored"
            source.mkdir()
            restored.mkdir()
            (source / "changed.txt").write_text("before", encoding="utf-8")
            (restored / "changed.txt").write_text("after", encoding="utf-8")
            (source / "missing.txt").write_text("present only in source", encoding="utf-8")
            (restored / "extra.txt").write_text("present only in restore", encoding="utf-8")

            result = verify_restore.verify(source, restored)

            self.assertFalse(result["passed"])
            self.assertEqual(
                {item["status"] for item in result["results"]},
                {"hash_mismatch", "missing_in_restore", "extra_in_restore"},
            )


if __name__ == "__main__":
    unittest.main()
import tempfile
import unittest
from pathlib import Path

from pla_mmo.seed_manager import SeedManager
from pla_mmo.settings import SettingsStore


class SeedManagerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.seed_path = self.root / "latest_seed.txt"
        self.seed_path.write_text("123456789\n", encoding="utf-8")
        self.store = SettingsStore(self.root / "data" / "settings.json")
        self.store.update({"seed_source_mode": "file", "seed_file_path": str(self.seed_path)})
        self.manager = SeedManager(self.store)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_reload_requires_confirmation_for_changed_seed(self):
        self.seed_path.write_text("987654321\n", encoding="utf-8")
        result = self.manager.reload()
        self.assertTrue(result["needs_confirmation"])
        self.assertEqual(result["previous_seed"], "123456789")
        self.assertEqual(result["candidate_seed"], "987654321")
        self.assertEqual(self.manager.current_seed, "123456789")

    def test_changed_file_during_confirmation_is_not_silently_applied(self):
        self.seed_path.write_text("222222222\n", encoding="utf-8")
        first = self.manager.reload()
        self.seed_path.write_text("333333333\n", encoding="utf-8")
        second = self.manager.reload(confirm=True, expected_seed=first["candidate_seed"])
        self.assertTrue(second["needs_confirmation"])
        self.assertEqual(second["candidate_seed"], "333333333")
        self.assertEqual(self.manager.current_seed, "123456789")

        final = self.manager.reload(confirm=True, expected_seed=second["candidate_seed"])
        self.assertEqual(final["current_seed"], "333333333")
        self.assertEqual(self.manager.current_seed, "333333333")

    def test_cancel_pending_seed_clears_candidate_and_keeps_current(self):
        self.seed_path.write_text("987654321\n", encoding="utf-8")
        self.manager.reload()
        result = self.manager.cancel_pending()
        self.assertIsNone(result["pending_seed"])
        self.assertEqual(result["current_seed"], "123456789")
        self.assertEqual(result["status"], "已保留当前 Seed")

    def test_failed_reload_keeps_last_valid_seed_and_clears_pending(self):
        self.seed_path.write_text("987654321\n", encoding="utf-8")
        self.manager.reload()
        self.seed_path.write_text("", encoding="utf-8")
        result = self.manager.reload(confirm=True, expected_seed="987654321")
        self.assertFalse(result["ok"])
        self.assertEqual(result["current_seed"], "123456789")
        self.assertIsNone(result["pending_seed"])
        self.assertEqual(result["status"], "读取失败")

    def test_seed_validation_errors_are_not_reported_as_success(self):
        invalid_manual = self.manager.set_manual_seed("not-a-seed")
        self.assertFalse(invalid_manual["ok"])
        self.assertIn("纯十进制", invalid_manual["error"])

        invalid_file = self.manager.select_file(str(self.root / "wrong.csv"))
        self.assertFalse(invalid_file["ok"])
        self.assertIn(".txt", invalid_file["error"])

    def test_reload_rejects_manual_source_with_failure_status(self):
        self.manager.set_manual_seed("123456789", confirm=True)
        result = self.manager.reload()
        self.assertFalse(result["ok"])
        self.assertIn("手动输入", result["error"])

    def test_manual_seed_changes_source_only_when_applied(self):
        result = self.manager.set_manual_seed("111111111")
        self.assertTrue(result["needs_confirmation"])
        self.assertEqual(self.store.public_view()["seed_source_mode"], "file")
        applied = self.manager.set_manual_seed("111111111", confirm=True)
        self.assertEqual(applied["current_seed"], "111111111")
        self.assertEqual(self.store.public_view()["seed_source_mode"], "manual")


if __name__ == "__main__":
    unittest.main()

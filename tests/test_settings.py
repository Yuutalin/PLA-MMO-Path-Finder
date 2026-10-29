import json
import tempfile
import threading
import unittest
from pathlib import Path

from pla_mmo.settings import SettingsStore


class SettingsTests(unittest.TestCase):
    def test_appearance_preferences_are_persisted_and_validated(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary) / "settings.json")
            initial = store.public_view()
            self.assertEqual(initial["appearance_theme"], "forest")
            self.assertEqual(initial["appearance_mode"], "light")
            self.assertFalse(initial["appearance_preferences_saved"])

            store.update({"appearance_theme": "ocean", "appearance_mode": "dark"})
            saved = store.public_view()
            self.assertEqual(saved["appearance_theme"], "ocean")
            self.assertEqual(saved["appearance_mode"], "dark")
            self.assertTrue(saved["appearance_preferences_saved"])

            with self.assertRaises(ValueError):
                store.update({"appearance_theme": "not-a-theme"})
            with self.assertRaises(ValueError):
                store.update({"appearance_mode": "night"})

    def test_default_research_level_is_saved_and_validated(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary) / "settings.json")
            self.assertEqual(store.public_view()["default_research_level"], "level10")
            self.assertTrue(store.public_view()["default_shiny_charm"])
            saved = store.update({"default_research_level": "perfect", "default_shiny_charm": False})
            self.assertEqual(saved["default_research_level"], "perfect")
            self.assertEqual(store.public_view()["default_research_level"], "perfect")
            self.assertFalse(store.public_view()["default_shiny_charm"])
            with self.assertRaises(ValueError):
                store.update({"default_research_level": "bad-value"})

    def test_per_species_research_levels_are_saved_and_validated(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary) / "settings.json")
            saved = store.update({
                "default_research_level": "level10",
                "pokemon_research_levels": {"Abra": "base", "Kadabra": "perfect"},
            })
            self.assertEqual(saved["pokemon_research_levels"], {"Abra": "base", "Kadabra": "perfect"})
            self.assertEqual(store.public_view()["pokemon_research_levels"]["Kadabra"], "perfect")
            with self.assertRaisesRegex(ValueError, "研究等级无效"):
                store.update({"pokemon_research_levels": {"Abra": "not-a-level"}})

    def test_invalid_species_level_map_is_normalized_on_load(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            path.write_text(json.dumps({
                "pokemon_research_levels": {
                    "Abra": "base",
                    "Kadabra": "invalid",
                    "": "perfect",
                }
            }), encoding="utf-8")
            settings = SettingsStore(path).public_view()
            self.assertEqual(settings["pokemon_research_levels"], {"Abra": "base"})

    def test_last_known_good_backup_is_created_before_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            store = SettingsStore(path)
            store.update({"appearance_theme": "ocean"})
            store.update({"appearance_mode": "dark"})

            backup = path.with_name("settings.backup.json")
            self.assertTrue(backup.is_file())
            backup_data = json.loads(backup.read_text(encoding="utf-8"))
            self.assertEqual(backup_data["appearance_theme"], "ocean")
            self.assertEqual(backup_data["appearance_mode"], "light")

    def test_corrupt_primary_config_is_preserved_and_recovers_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            store = SettingsStore(path)
            store.update({"appearance_theme": "ocean"})
            store.update({"appearance_mode": "dark"})
            path.write_text('{"appearance_theme": ', encoding="utf-8")

            recovered = store.public_view()
            self.assertEqual(recovered["appearance_theme"], "ocean")
            self.assertEqual(recovered["appearance_mode"], "light")
            self.assertTrue(list(Path(temporary).glob("settings.corrupt-*.json")))
            self.assertTrue(store.diagnostics()["recovered_from_backup"])
            self.assertTrue(store.backup_path.is_file())

    def test_settings_updates_are_serialized_and_leave_valid_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            store = SettingsStore(path)
            errors = []

            def update(index):
                try:
                    store.update({"appearance_theme": ["forest", "ocean", "snow", "lavender", "amber"][index % 5]})
                except Exception as exc:  # surfaced below with a useful assertion
                    errors.append(exc)

            threads = [threading.Thread(target=update, args=(i,)) for i in range(24)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            self.assertIn(json.loads(path.read_text(encoding="utf-8"))["appearance_theme"], {
                "forest", "ocean", "snow", "lavender", "amber"
            })
            self.assertFalse(list(Path(temporary).glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()

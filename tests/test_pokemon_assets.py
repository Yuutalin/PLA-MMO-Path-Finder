import base64
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pla_mmo.pokemon_assets as assets_module
from pla_mmo.pokemon_assets import PokemonAssetManager, SPRITE_NAME_RE

ROOT = Path(__file__).resolve().parents[1]


class PokemonAssetManagerTests(unittest.TestCase):
    def make_manager(self, temp):
        temp_root = Path(temp)
        resources = temp_root / "offline_engine" / "static" / "resources"
        resources.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "offline_engine" / "static" / "resources" / "pokedex.json", resources / "pokedex.json")
        shutil.copy2(ROOT / "offline_engine" / "static" / "resources" / "hisuidex.txt", resources / "hisuidex.txt")
        with patch.object(assets_module, "POKEDEX_PATH", resources / "pokedex.json"), patch.object(assets_module, "HISUIDEX_PATH", resources / "hisuidex.txt"):
            manager = PokemonAssetManager(temp_root, temp_root / "data")
        return manager

    def test_manifest_contains_hisui_dex_normal_and_shiny_names(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.make_manager(temp)
            self.assertGreater(len(manager._entries), 484)
            self.assertIn("c_712.png", manager._entries)
            self.assertIn("c_712s.png", manager._entries)
            self.assertIn("c_215.png", manager._entries)
            self.assertIn("c_215s.png", manager._entries)
            self.assertIn("c_724-1.png", manager._entries)
            self.assertIn("c_724-1s.png", manager._entries)
            self.assertIn("c_25f.png", manager._entries)
            self.assertIn("c_25fs.png", manager._entries)
            self.assertIn("c_449f.png", manager._entries)
            self.assertIn("c_450fs.png", manager._entries)


    def test_manifest_includes_female_basculegion_form(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.make_manager(temp)
            self.assertIn("c_902-1.png", manager._entries)
            self.assertIn("c_902-1s.png", manager._entries)
            self.assertTrue(manager._entries["c_902-1.png"]["female"])
            with patch.object(manager, "_form_urls", return_value={"female": ["https://example.test/basculegion-female.png"]}):
                sources = manager._source_urls(manager._entries["c_902-1.png"])
            self.assertEqual(sources[0], "https://example.test/basculegion-female.png")

    def test_custom_assets_are_counted_and_take_priority(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.make_manager(temp)
            target = manager.custom_dir / "c_712.png"
            target.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"))
            status = manager.status()
            self.assertEqual(status["custom"], 1)
            self.assertEqual(status["available"], 1)
            self.assertFalse(status["complete"])

    def test_user_custom_assets_are_preferred_and_legacy_assets_remain_readable(self):
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC")
        with tempfile.TemporaryDirectory() as temp:
            manager = self.make_manager(temp)
            legacy = manager.legacy_custom_dir / "c_712.png"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_bytes(png)
            self.assertEqual(manager.resolve_asset("custom", "c_712.png"), legacy)
            user_custom = manager.custom_dir / "c_712.png"
            user_custom.write_bytes(png)
            self.assertEqual(manager.resolve_asset("custom", "c_712.png"), user_custom)
            self.assertIsNone(manager.resolve_asset("custom", "../c_712.png"))
            self.assertIsNone(manager.resolve_asset("unknown", "c_712.png"))

    def test_skip_choice_persists_and_disables_startup_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.make_manager(temp)
            status = manager.set_choice("skip")
            self.assertEqual(status["choice"], "skip")
            self.assertFalse(status["prompt_required"])
            self.assertTrue(Path(temp, "data", "pokemon-assets-state.json").is_file())

    def test_interrupted_download_requires_confirmation_again_on_next_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "pokemon-assets-state.json").write_text(
                '{"choice": "download"}', encoding="utf-8"
            )
            manager = self.make_manager(temp)
            status = manager.status()
            self.assertIsNone(status["choice"])
            self.assertTrue(status["prompt_required"])
            saved = (data_dir / "pokemon-assets-state.json").read_text(encoding="utf-8")
            self.assertIn('"choice": null', saved)

    def test_sprite_filename_validation_rejects_paths(self):
        self.assertTrue(SPRITE_NAME_RE.fullmatch("c_712s.png"))
        self.assertTrue(SPRITE_NAME_RE.fullmatch("c_25fs.png"))
        self.assertTrue(SPRITE_NAME_RE.fullmatch("c_712-1fs.png"))
        self.assertFalse(SPRITE_NAME_RE.fullmatch("../c_712.png"))
        self.assertFalse(SPRITE_NAME_RE.fullmatch("c_712.png/evil"))

    def test_hisuian_form_slug_is_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.make_manager(temp)
            slug = manager._pokemon_slug({"species": "Growlithe", "form_name": "Hisuian"})
            self.assertEqual(slug, "growlithe-hisui")
            striped = manager._pokemon_slug({"species": "Basculin", "form_name": "White-Striped"})
            self.assertEqual(striped, "basculin-white-striped")

    def test_home_artwork_is_preferred_with_official_art_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.make_manager(temp)
            sources = manager._source_urls({"national": 712, "form_id": "0", "shiny": True})
            self.assertIn("/other/home/shiny/712.png", sources[0])
            self.assertIn("/other/official-artwork/shiny/712.png", sources[1])

    def test_missing_form_endpoint_falls_back_to_matching_shiny_base_art(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.make_manager(temp)
            with patch.object(manager, "_form_urls", side_effect=RuntimeError("missing form")):
                sources = manager._source_urls({"national": 712, "form_id": "1", "shiny": True})
            self.assertTrue(any("home/shiny/712.png" in source for source in sources))
            self.assertTrue(any("official-artwork/shiny/712.png" in source for source in sources))

    def test_female_sprite_uses_gender_art_when_available_and_base_fallback_otherwise(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = self.make_manager(temp)
            with patch.object(manager, "_form_urls", return_value={"female_shiny": ["https://example.test/female-shiny.png"]}):
                sources = manager._source_urls({"national": 25, "form_id": "0", "female": True, "shiny": True})
            self.assertEqual(sources[0], "https://example.test/female-shiny.png")


if __name__ == "__main__":
    unittest.main()

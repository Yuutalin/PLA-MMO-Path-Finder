import unittest
import importlib
import sys
import tempfile
from pathlib import Path

from pla_mmo.local_engine import _matches_filter, _walk_results, _strip_html, translate_species_name


class LocalEngineAdapterTests(unittest.TestCase):

    def test_all_candidate_species_names_are_localized_and_sprites_resolve(self):
        import json
        from pla_mmo.local_engine import sprite_for_species, PROJECT_ROOT
        path = PROJECT_ROOT / "offline_engine" / "static" / "resources" / "seedhashes.json"
        candidates = json.loads(path.read_text(encoding="utf-8-sig"))
        for item in candidates:
            species = item.get("species", "")
            if not species:
                continue
            localized = translate_species_name(species)
            self.assertNotEqual(localized, species, f"未翻译名称：{species}")
        self.assertEqual(translate_species_name("Growlithe-1"), "洗翠卡蒂狗")
        self.assertEqual(translate_species_name("MimeJr."), "魔尼尼")
        self.assertEqual(sprite_for_species("Alpha Growlithe-1"), "c_58-1.png")
        self.assertEqual(sprite_for_species("MimeJr."), "c_439.png")

    def test_status_reports_missing_z3_dependency(self):
        from unittest.mock import patch
        from pla_mmo.local_engine import LocalMMOEngine
        def fake_import(name):
            if name == "z3":
                raise ModuleNotFoundError("No module named 'z3'")
            if name == "usb":
                raise ModuleNotFoundError("No module named 'usb'")
            return __import__(name)
        with patch("pla_mmo.local_engine.importlib.import_module", side_effect=fake_import):
            status = LocalMMOEngine().status()
        self.assertTrue(any("z3-solver 不可用" in item for item in status["missing"]))
        self.assertTrue(any("pyusb 不可用" in item for item in status["missing"]))
        self.assertFalse(status["dependencies"]["z3_solver"])
        self.assertFalse(status["dependencies"]["pyusb"])


    def test_local_engine_converts_legacy_flat_research_to_upstream_schema(self):
        from unittest.mock import patch
        from pla_mmo.local_engine import LocalMMOEngine

        engine = LocalMMOEngine()
        fake_module = type("FakeModule", (), {})()
        captured = {}
        def fake_check(*args):
            captured["research"] = args[1]
            return {}
        fake_module.check_mmo_from_seed = fake_check
        with patch.object(engine, "status", return_value={"installed": True}), \
             patch.object(engine, "_resolve_table_hash", side_effect=["ABC", ""]), \
             patch("pla_mmo.local_engine.importlib.import_module", return_value=fake_module):
            engine.calculate_mmo_path("1", {
                "research": {"Bidoof": 1}, "frencounter": "ABC", "brencounter": "",
                "isbonus": False, "frspawns": 8, "brspawns": 6, "isnormal": False,
            })
        self.assertEqual(captured["research"], {
            "shinycharm": False, "rolls": {"Bidoof": 1}
        })

    def test_local_engine_preserves_already_nested_upstream_research(self):
        from unittest.mock import patch
        from pla_mmo.local_engine import LocalMMOEngine

        engine = LocalMMOEngine()
        fake_module = type("FakeModule", (), {})()
        captured = {}
        expected = {"shinycharm": True, "rolls": {"Bidoof": 3, "Starly": 1}}
        def fake_check(*args):
            captured["research"] = args[1]
            return {}
        fake_module.check_mmo_from_seed = fake_check
        with patch.object(engine, "status", return_value={"installed": True}), \
             patch.object(engine, "_resolve_table_hash", side_effect=["ABC", ""]), \
             patch("pla_mmo.local_engine.importlib.import_module", return_value=fake_module):
            engine.calculate_mmo_path("1", {
                "research": expected, "shiny_charm": True,
                "frencounter": "ABC", "brencounter": "",
                "isbonus": False, "frspawns": 8, "brspawns": 6, "isnormal": False,
            })
        self.assertEqual(captured["research"], expected)

    def test_old_engine_manifest_is_not_reported_as_verified(self):
        import json
        from types import SimpleNamespace
        from unittest.mock import patch
        import pla_mmo.local_engine as local_engine_module

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "offline_engine"
            (root / "pla").mkdir(parents=True)
            (root / "app").mkdir(parents=True)
            resources = root / "static" / "resources"
            resources.mkdir(parents=True)
            (root / "pla" / "checkmmo.py").write_text("", encoding="utf-8")
            (root / "app" / "__init__.py").write_text("RESOURCE_PATH = ''", encoding="utf-8")
            for filename in ("mmo_es.json", "mmopaths.json", "nonbonuspaths.json", "seedhashes.json"):
                (resources / filename).write_text("{}", encoding="utf-8")
            manifest = root / "engine_manifest.json"
            manifest.write_text(json.dumps({"app_version": "0.3.0"}), encoding="utf-8")
            marker = root / "engine_install_ok.txt"
            marker.write_text("old success marker", encoding="utf-8")

            def fake_import(name):
                if name == "z3":
                    return SimpleNamespace(get_version_string=lambda: "test")
                if name == "usb":
                    return SimpleNamespace()
                raise ModuleNotFoundError(name)

            with patch.object(local_engine_module, "ENGINE_ROOT", root), \
                 patch.object(local_engine_module, "RESOURCE_ROOT", resources), \
                 patch.object(local_engine_module, "MANIFEST_PATH", manifest), \
                 patch.object(local_engine_module, "ENGINE_OK_PATH", marker), \
                 patch.object(local_engine_module, "SEEDHASHES_PATH", resources / "seedhashes.json"), \
                 patch.object(local_engine_module.importlib, "import_module", side_effect=fake_import):
                status = local_engine_module.LocalMMOEngine().status()

            self.assertTrue(status["installed"])
            self.assertFalse(status["verified"])
            self.assertIn("当前程序要求 0.3.6", status["message"])

    def test_walk_results_flattens_nested_original_result_tree(self):
        tree = {
            "first-round": {
                "seed-a": {
                    "species": "Bidoof",
                    "shiny": True,
                    "index": "Path: D1",
                }
            },
            "bonus-round": {
                "path-1": {
                    "seed-b": {
                        "species": "Starly",
                        "shiny": False,
                        "index": "Path: D2",
                    }
                }
            },
        }
        results = list(_walk_results(tree))
        self.assertEqual(len(results), 2)
        self.assertEqual({x["species"] for x in results}, {"Bidoof", "Starly"})

    def test_filter_shiny_and_square_shiny(self):
        item = {"shiny": True, "square": False, "alpha": False, "ivs": [31, 31, 31, 31, 31, 31]}
        self.assertTrue(_matches_filter(item, "is_shiny"))
        self.assertFalse(_matches_filter(item, "is_square_shiny"))

    def test_filter_alpha_and_perfect_ivs(self):
        item = {"shiny": False, "square": False, "alpha": True, "ivs": [31, 31, 31, 31, 31, 31]}
        self.assertTrue(_matches_filter(item, "is_alpha"))
        self.assertTrue(_matches_filter(item, "is_perfect"))

    def test_zero_attack_speed_filters(self):
        item = {"shiny": False, "square": False, "alpha": False, "ivs": [31, 0, 31, 31, 31, 0]}
        self.assertTrue(_matches_filter(item, "no_attack"))
        self.assertTrue(_matches_filter(item, "no_speed"))
        self.assertTrue(_matches_filter(item, "has_no_speed_no_attack"))
        self.assertTrue(_matches_filter(item, "has_no_speed_no_attack_4iv"))


    def test_local_engine_adapter_has_no_remote_client_dependency(self):
        import inspect
        from pla_mmo.local_engine import LocalMMOEngine
        source = inspect.getsource(LocalMMOEngine.calculate_mmo_path)
        self.assertNotIn("urlopen", source)
        self.assertNotIn("RemoteCheckerClient", source)


    def test_chinese_species_translation_and_alpha_prefix(self):
        self.assertEqual(translate_species_name("Abra"), "凯西")
        self.assertEqual(translate_species_name("Alpha Kadabra"), "头目勇基拉")
        self.assertEqual(translate_species_name("Hisuian Growlithe"), "洗翠卡蒂狗")

    def test_upstream_relative_import_uses_nested_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / "offline_engine"
            (base / "app").mkdir(parents=True)
            (base / "pla").mkdir(parents=True)
            (base / "__init__.py").write_text("", encoding="utf-8")
            (base / "app" / "__init__.py").write_text("RESOURCE_PATH = 'fixture-resource-path'\n", encoding="utf-8")
            (base / "pla" / "__init__.py").write_text("", encoding="utf-8")
            (base / "pla" / "checkmmo.py").write_text(
                "from ..app import RESOURCE_PATH\ndef check_mmo_from_seed(*args):\n    return RESOURCE_PATH\n",
                encoding="utf-8",
            )
            sys.path.insert(0, temporary)
            try:
                for name in list(sys.modules):
                    if name == "offline_engine" or name.startswith("offline_engine."):
                        del sys.modules[name]
                module = importlib.import_module("offline_engine.pla.checkmmo")
                self.assertEqual(module.check_mmo_from_seed(), "fixture-resource-path")
            finally:
                for name in list(sys.modules):
                    if name == "offline_engine" or name.startswith("offline_engine."):
                        del sys.modules[name]
                if temporary in sys.path:
                    sys.path.remove(temporary)

    def test_html_is_removed_from_paths(self):
        self.assertEqual(_strip_html("<span>Path: D1</span>&nbsp;+ Bonus"), "Path: D1 + Bonus")


if __name__ == "__main__":
    unittest.main()

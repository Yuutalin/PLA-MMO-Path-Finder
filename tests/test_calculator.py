import unittest
from pla_mmo.calculator import build_calculation_params


class CalculatorTests(unittest.TestCase):
    def base_body(self):
        return {
            "isnormal": False,
            "frspawns": 8,
            "frencounter": "101",
            "fr_species": "Bidoof",
            "fr_research_level": "level10",
            "isbonus": False,
            "brspawns": 6,
            "brencounter": "",
            "br_species": "",
            "br_research_level": "",
            "shiny_charm": False,
            "filter": "is_shiny",
        }

    def test_builds_first_round_payload_without_inventing_bonus_species(self):
        params = build_calculation_params(self.base_body())
        self.assertEqual(params["research"], {"shinycharm": False, "rolls": {"Bidoof": 1}})
        self.assertFalse(params["isbonus"])
        self.assertEqual(params["brencounter"], "")

    def test_requires_research_level_for_selected_species(self):
        body = self.base_body()
        body["fr_research_level"] = ""
        with self.assertRaises(ValueError):
            build_calculation_params(body)

    def test_shiny_charm_rejects_species_below_research_level_10(self):
        body = self.base_body()
        body["shiny_charm"] = True
        body["fr_research_level"] = "base"
        with self.assertRaises(ValueError):
            build_calculation_params(body)

    def test_bonus_round_requires_second_species_and_research(self):
        body = self.base_body()
        body.update({
            "isbonus": True,
            "brencounter": "202",
            "br_species": "Starly",
            "br_research_level": "perfect",
        })
        params = build_calculation_params(body)
        self.assertEqual(params["research"], {"shinycharm": False, "rolls": {"Bidoof": 1, "Starly": 3}})
        self.assertEqual(params["brencounter"], "202")

    def test_shiny_charm_is_passed_as_upstream_flag_not_double_counted(self):
        body = self.base_body()
        body["shiny_charm"] = True
        params = build_calculation_params(body)
        self.assertEqual(params["research"], {"shinycharm": True, "rolls": {"Bidoof": 1}})

    def test_alpha_species_uses_same_pokedex_research_key(self):
        body = self.base_body()
        body.update({
            "isbonus": True,
            "brencounter": "202",
            "br_species": "Alpha Bidoof",
            "br_research_level": "level10",
        })
        params = build_calculation_params(body)
        self.assertEqual(params["research"], {"shinycharm": False, "rolls": {"Bidoof": 1}})

    def test_same_species_cannot_have_conflicting_research_levels(self):
        body = self.base_body()
        body.update({
            "isbonus": True,
            "brencounter": "202",
            "br_species": "Alpha Bidoof",
            "br_research_level": "perfect",
        })
        with self.assertRaisesRegex(ValueError, "同一宝可梦"):
            build_calculation_params(body)

    def test_settings_choose_research_level_by_species_and_share_same_species_level(self):
        body = self.base_body()
        body.update({
            "fr_species": "Alpha Abra",
            "isbonus": True,
            "brencounter": "202",
            "br_species": "Kadabra",
        })
        settings = {
            "default_research_level": "level10",
            "default_shiny_charm": False,
            "pokemon_research_levels": {"Abra": "base", "Kadabra": "perfect"},
        }
        params = build_calculation_params(body, settings)
        self.assertEqual(params["research"]["rolls"], {"Abra": 0, "Kadabra": 3})
        self.assertEqual(params["research_levels"], {"Abra": "base", "Kadabra": "perfect"})
        self.assertFalse(params["shiny_charm"])

    def test_settings_level_is_same_for_same_species_across_both_rounds(self):
        body = self.base_body()
        body.update({
            "isbonus": True,
            "brencounter": "202",
            "br_species": "Alpha Bidoof",
        })
        settings = {
            "default_research_level": "level10",
            "default_shiny_charm": False,
            "pokemon_research_levels": {"Bidoof": "perfect"},
        }
        params = build_calculation_params(body, settings)
        self.assertEqual(params["research"]["rolls"], {"Bidoof": 3})
        self.assertEqual(params["research_levels"], {"Bidoof": "perfect"})

    def test_form_uses_base_species_level_when_no_separate_dex_entry_exists(self):
        body = self.base_body()
        body["fr_species"] = "Sneasel-1"
        settings = {
            "default_research_level": "level10",
            "default_shiny_charm": False,
            "pokemon_research_levels": {"Sneasel": "perfect"},
        }
        params = build_calculation_params(body, settings)
        self.assertEqual(params["research"]["rolls"], {"Sneasel-1": 3})
        self.assertEqual(params["research_levels"], {"Sneasel-1": "perfect"})


if __name__ == "__main__":
    unittest.main()

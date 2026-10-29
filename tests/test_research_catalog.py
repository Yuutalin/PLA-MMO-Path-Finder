import unittest

from pla_mmo.local_engine import LocalMMOEngine


class ResearchCatalogTests(unittest.TestCase):
    def test_catalog_follows_hisui_dex_order_and_contains_evolution_lines(self):
        catalog = LocalMMOEngine().load_research_catalog()
        species = catalog["species"]
        self.assertEqual(catalog["total"], len(species))
        self.assertGreaterEqual(len(species), 240)
        self.assertEqual(species[0]["species"], "Rowlet")
        self.assertEqual(species[1]["species"], "Dartrix")
        self.assertEqual(species[2]["species"], "Decidueye-1")
        self.assertEqual(species[57]["species"], "Abra")
        self.assertEqual(species[58]["species"], "Kadabra")
        self.assertTrue(all(entry["label"] for entry in species))
        self.assertTrue(all(entry["dex_number"] for entry in species))

    def test_catalog_localizes_hisui_forms(self):
        catalog = LocalMMOEngine().load_research_catalog()
        by_id = {entry["species"]: entry for entry in catalog["species"]}
        self.assertEqual(by_id["Decidueye-1"]["label"], "洗翠狙射树枭")
        self.assertEqual(by_id["Basculin-2"]["label"], "白条纹野蛮鲈鱼")


if __name__ == "__main__":
    unittest.main()

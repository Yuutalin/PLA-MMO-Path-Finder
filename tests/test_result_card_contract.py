import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ResultCardContractTests(unittest.TestCase):
    def test_result_view_script_loads_before_app(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertLess(html.index("result_view.js"), html.index("app.js"))

    def test_result_card_uses_editorial_summary_and_timeline(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "product.css").read_text(encoding="utf-8")
        self.assertIn('"result-summary-grid"', js)
        self.assertIn('"第一轮路径"', js)
        self.assertIn('"重新访问 · 剩余数量"', js)
        self.assertIn('"第二轮目标位置"', js)
        self.assertIn('"operation-timeline"', js)
        self.assertIn('"result-hero"', js)
        self.assertIn('"pokemon-art-frame"', js)
        self.assertIn('resultResearchContext(item, params)', js)
        self.assertIn('.result-summary-grid {', css)
        self.assertIn('.operation-timeline::before', css)
        self.assertIn('.result-card.result-card-editorial', css)

    def test_alternative_routes_do_not_trigger_multi_shiny_badge(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        view = (ROOT / "static" / "result_view.js").read_text(encoding="utf-8")
        self.assertIn("const multiPath = routeSummary.hasMultiple;", js)
        self.assertNotIn("dupes.length > 0", js)
        self.assertIn("`dupes` describes alternative routes", view)
        self.assertIn("第二轮初始生成", view)
        self.assertNotIn("同一目标的其他可达路径", js)
        self.assertNotIn("operations.dupes.length", js)

    def test_result_card_contains_required_chinese_fields_and_tags(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        for label in ("闪光", "方块闪", "头目", "同时闪光：", "性格", "性别", "闪光判定", "个体值"):
            self.assertIn(label, js)
        for tag in ("status-6v", "status-5v", "status-4v", "route-detail-button"):
            self.assertIn(tag, js + (ROOT / "static" / "style.css").read_text(encoding="utf-8"))
        view = (ROOT / "static" / "result_view.js").read_text(encoding="utf-8")
        for label in ("第一轮路径", "重新访问", "第二轮路径"):
            self.assertIn(label, view)

    def test_default_path_filter_checks_actual_boolean_value(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('card.dataset.defaultPath = hasDefaultPath ? "true" : "false";', js)
        self.assertIn('if (defaultOnly && card.dataset.defaultPath !== "true") show = false;', js)

    def test_detailed_steps_render_chain_operations_with_counts(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        view = (ROOT / "static" / "result_view.js").read_text(encoding="utf-8")
        self.assertIn("operations.chainOperations.forEach", js)
        self.assertIn("operation-count", js)
        self.assertIn("chainOperations", view)
        self.assertIn("cumulative", view)
        self.assertIn("revisitMarkers", view)
        self.assertIn("不是需要清除的宝可梦数量", view)
        self.assertIn("operation-target-event", js)
        self.assertIn('setResultDetailsOpen(detailsPanel, detailsButton, detailButtonLabel, shouldOpen)', js)


    def test_pokemon_info_precedes_route_summary_and_details_follow_routes(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        info = js.index('const infoHeading = appendTextElement(card, "div", "result-section-heading result-info-heading")')
        meta = js.index('const extra = appendTextElement(card, "div", "result-meta-strip")', info)
        path = js.index('const pathHeading = appendTextElement(card, "div", "result-section-heading result-path-heading")', meta)
        summary = js.index('const summaryWrap = appendTextElement(card, "div", "result-route-overview")', path)
        details = js.index('const detailHeading = appendTextElement(card, "div", "result-detail-heading")', summary)
        self.assertLess(info, meta)
        self.assertLess(meta, path)
        self.assertLess(path, summary)
        self.assertLess(summary, details)

    def test_research_level_uses_backend_research_levels_map(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("const levels = params?.research_levels;", js)
        self.assertIn("researchLevelForSpecies(params, params.fr_species, \"fr\")", js)
        self.assertIn("researchLevelForSpecies(params, params.br_species, \"br\")", js)
        self.assertIn('perfect: "完美研究"', js)

    def test_metadata_and_detail_heading_use_closed_theme_aware_cards(self):
        css = (ROOT / "static" / "themes.css").read_text(encoding="utf-8")
        self.assertIn("body[data-theme] .result-meta-strip", css)
        self.assertIn("border: 1px solid var(--border) !important;", css)
        self.assertIn("body[data-theme] .result-detail-heading", css)
        self.assertIn("border-radius: 12px !important;", css)



if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendRegressionTests(unittest.TestCase):
    def test_v073_result_cards_and_result_metadata_use_lightweight_entrance_motion(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "themes.css").read_text(encoding="utf-8")
        self.assertIn("function replayUiEntrance(node", js)
        self.assertIn('"result-card result-card-editorial result-card-entering"', js)
        self.assertIn("Math.min(index * 36, 180)", js)
        self.assertIn('replayUiEntrance($("result-count"))', js)
        self.assertIn("@keyframes plaResultCardEnter", css)
        self.assertIn("@keyframes plaResultSectionEnter", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIn("animation: none !important;", css[css.rfind("@media (prefers-reduced-motion: reduce)"):])

    def test_v065_pokemon_settings_use_single_column_and_compact_bulk_controls(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "static" / "themes.css").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('class="pokemon-settings-layout"', html)
        self.assertNotIn('class="pokemon-settings-sidebar"', html)
        self.assertNotIn('class="pokemon-settings-main"', html)
        self.assertLess(html.index('class="settings-block pokemon-general-settings"'), html.index('class="settings-block pokemon-bulk-settings"'))
        self.assertLess(html.index('class="settings-block pokemon-bulk-settings"'), html.index('class="settings-block pokemon-research-settings"'))
        self.assertIn('grid-template-columns: minmax(0, 1fr);', css)
        self.assertIn('display: flex;', css[css.index('body[data-theme] .pokemon-bulk-levels'):css.index('body[data-theme] .pokemon-bulk-level {')])
        self.assertIn('min-height: 34px;', css[css.index('body[data-theme] .pokemon-bulk-level {'):css.index('body[data-theme] .pokemon-bulk-level:hover')])
        self.assertIn('function updateResearchCount(visibleCount = null)', js)
        self.assertIn('updateResearchCount();', js)

    def test_v072_pokemon_research_list_uses_outer_settings_scroll(self):
        css = (ROOT / "static" / "themes.css").read_text(encoding="utf-8")
        tail = css[css.index("/* v0.7.2 — single settings scroll surface"):]
        self.assertIn("max-height: none !important;", tail)
        self.assertIn("overflow: visible !important;", tail)
        self.assertIn("overscroll-behavior: auto !important;", tail)
        self.assertIn("overflow-y: auto", css[css.index("body[data-theme] .settings-tab-content"):css.index("body[data-theme] .settings-tab-panel[hidden]")])

    def test_v072_tutorial_is_always_visible_and_about_credit_is_structured(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        help_panel = html[html.index('id="settings-tab-help"'):html.index('id="seed-confirm-modal"')]
        self.assertNotIn("<details class=\"panel tutorial-panel\">", help_panel)
        self.assertNotIn("<summary>使用教程", help_panel)
        self.assertIn('class="tutorial-heading"', help_panel)
        self.assertIn('class="about-meta-grid"', help_panel)
        self.assertIn('class="about-credit"', help_panel)
        self.assertIn("选择 Seed 来源", help_panel)
        self.assertIn("计算筛选条件", help_panel)

    def test_v063_settings_backup_and_seed_confirmation_guard_are_present(self):
        settings = (ROOT / "pla_mmo" / "settings.py").read_text(encoding="utf-8")
        manager = (ROOT / "pla_mmo" / "seed_manager.py").read_text(encoding="utf-8")
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("last-known-good backup", settings)
        self.assertIn("os.replace(temp, self.path)", settings)
        self.assertIn("expected_seed", manager)
        self.assertIn("/api/seed/cancel-pending", app)
        self.assertIn("expected_seed: result.candidate_seed", js)

    def test_v0622_persists_appearance_in_settings_and_applies_native_icon(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        settings = (ROOT / "pla_mmo" / "settings.py").read_text(encoding="utf-8")
        self.assertIn('data-appearance-saved=', html)
        self.assertIn('appearance_preferences_saved', settings)
        self.assertIn('api("/api/settings"', js)
        self.assertIn('_apply_windows_app_icon', app)
        self.assertIn('static" / "app.ico', app)
        self.assertNotIn('"icon":', app)
        self.assertNotIn('webview.create_window(\n        window_title,\n        url,\n        icon=', app)

    def test_product_ui_defaults_and_sticky_layout_are_present(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="pokemon-shiny-charm" type="checkbox" checked disabled', html)
        self.assertIn('data-research-bulk="level10" aria-pressed="true" disabled', html)
        self.assertIn('id="pokemon-research-list"', html)
        self.assertIn('id="result-settings-summary"', html)
        self.assertNotIn('id="fr-research"', html)
        self.assertNotIn('id="br-research"', html)
        self.assertNotIn('id="shiny-charm"', html)
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("const initiallyOpen = false;", js)
        self.assertIn("search-select-option-art", js)
        self.assertIn('api("/api/pokemon-catalog"', js)
        self.assertIn("renderCalculationSettingsSummary(params)", js)
        css = (ROOT / "static" / "product.css").read_text(encoding="utf-8")
        self.assertIn(".site-header {", css)
        self.assertIn("position: sticky;", css)
        self.assertIn(".revisit-instruction-list", css)

    def test_v052_fixes_sidebar_footer_and_progress_overlap(self):
        css = (ROOT / "static" / "product.css").read_text(encoding="utf-8")
        self.assertIn("body:has(#pokemon-assets-global-progress:not(.hidden)) .sidebar", css)
        self.assertIn("#calculate-form .form-footer", css)
        self.assertIn("width: 100%;", css)
        self.assertIn("position: relative;", css)

    def test_v052_compact_result_actions_and_search_field_without_selected_art(self):
        css = (ROOT / "static" / "product.css").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn(".search-select-selected-art-wrap", css)
        self.assertIn("display: none !important;", css)
        self.assertIn("result-detail-actions", js)
        self.assertIn('copy.textContent = "复制路径"', js)
        self.assertIn('detailActions.appendChild(copy)', js)
        self.assertIn('querySelectorAll(".pokemon-art-caption")', js)
        self.assertIn(".operation-section > .revisit-method-note", css)

    def test_pokemon_name_translation_covers_internal_form_ids(self):
        import json
        from pla_mmo.local_engine import translate_species_name, PROJECT_ROOT
        names = json.loads((PROJECT_ROOT / "offline_engine" / "static" / "resources" / "seedhashes.json").read_text(encoding="utf-8-sig"))
        for item in names:
            species = item.get("species", "")
            if species:
                self.assertNotEqual(translate_species_name(species), species, f"Untranslated: {species}")


    def test_v051_fixed_header_scrollable_sidebar_and_icon_fallback(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="form-scroll-region"', html)
        self.assertIn('class="form-footer"', html)
        self.assertIn("v='0.7.3'", html)
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("search-select-option-art-wrap", js)
        self.assertIn("appendCatalogOnlyMatches", js)
        self.assertIn("retryMissingSpriteImages", js)
        self.assertIn("const initiallyOpen = false;", js)
        css = (ROOT / "static" / "product.css").read_text(encoding="utf-8")
        self.assertIn("position: fixed !important", css)
        self.assertIn("overflow-y: auto", css)
        self.assertIn(".form-footer", css)

    def test_v055_desktop_results_are_explicitly_placed_in_second_grid_column(self):
        css = (ROOT / "static" / "product.css").read_text(encoding="utf-8")
        self.assertIn("#test-view.workspace > .results-column", css)
        self.assertIn("grid-column: 2;", css)
        self.assertIn("grid-template-columns: 300px minmax(0, 1fr) !important;", css)
        self.assertIn("@media (max-width: 820px)", css)

    def test_v055_disables_expensive_backdrop_blur_on_fixed_and_modal_layers(self):
        css = (ROOT / "static" / "product.css").read_text(encoding="utf-8")
        self.assertIn(".settings-modal-backdrop {", css)
        self.assertIn("backdrop-filter: none !important;", css)
        self.assertIn("-webkit-backdrop-filter: none !important;", css)
        self.assertIn("background: rgba(22, 31, 24, .48);", css)

    def test_unknown_internal_form_is_localized_instead_of_leaking_english(self):
        from pla_mmo.local_engine import translate_species_name
        self.assertEqual(translate_species_name("Mothim-2"), "绅士蛾（特殊形态）")
        self.assertEqual(translate_species_name("Basculegion-1"), "幽尾玄鱼（雌性形态）")


    def test_basculegion_is_present_as_a_bonus_candidate_for_basculin(self):
        import json
        resource = ROOT / "offline_engine" / "static" / "resources" / "seedhashes.json"
        entries = json.loads(resource.read_text(encoding="utf-8-sig"))
        basculin = next(item for item in entries if item.get("species") == "Basculin-2" and item.get("parent_id") == "0")
        basculegion = next(item for item in entries if item.get("species") == "Basculegion" and item.get("parent_id") != "-1")
        self.assertEqual(basculegion["parent_id"], basculin["hash"])
        # It should be discoverable in the catalog search, but not selectable as a first-wave candidate.
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("appendCatalogOnlyMatches", js)
        self.assertIn("当前轮次不可选", js)

    def test_v057_startup_requests_are_independent_and_bounded(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("timeoutMs = 45000", js)
        self.assertIn('api("/api/species", { timeoutMs: 12000 })', js)
        self.assertIn("await Promise.allSettled(startupTasks)", js)
        self.assertIn("候选数据不可用", js)

    def test_v057_settings_launcher_and_dark_header_are_explicit(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "product.css").read_text(encoding="utf-8")
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertIn('querySelectorAll("[data-open-settings]")', js)
        self.assertIn('modal.style.display = "grid"', js)
        self.assertIn('body.dark-mode .site-header {', css)
        self.assertIn('--page-bg: #191b20;', css)
        self.assertIn("v='0.7.3'", html)

    def test_v070_build_tools_are_grouped_and_author_is_visible(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        build = (ROOT / "build_tools" / "build.py").read_text(encoding="utf-8")
        build_bat = (ROOT / "build_tools" / "build.bat").read_text(encoding="utf-8")
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("君粒&GPT", app)
        self.assertIn("author_name", html)
        self.assertIn("/user-assets/custom/${filename}", js)
        self.assertIn("logo.icon", build)
        self.assertIn("default_app.ico", build)
        self.assertIn("便携版", build)
        self.assertIn("安装版", build)
        self.assertIn("build_tools", build_bat)
        self.assertTrue((ROOT / "build_tools" / "installer.iss").is_file())

    def test_build_installer_recovers_when_chinese_language_file_is_missing(self):
        build = (ROOT / "build_tools" / "build.py").read_text(encoding="utf-8")
        installer = (ROOT / "build_tools" / "installer.iss").read_text(encoding="utf-8")
        self.assertIn("ensure_chinese_language_file", build)
        self.assertIn("INNO_CHINESE_TRANSLATION_URL", build)
        self.assertIn("compiler:Default.isl", build)
        self.assertIn("{#SetupLanguageFile}", installer)
        self.assertIn("{#SetupLanguageName}", installer)

    def test_build_batch_avoids_problematic_unicode_command_echo(self):
        build_bat = (ROOT / "build_tools" / "build.bat").read_text(encoding="utf-8")
        self.assertIn("Source mode does not need compilation", build_bat)
        self.assertNotIn("普通运行不需要编译：使用项目根目录", build_bat)

    def test_history_page_and_navigation_are_removed(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn('id="history-view"', html)
        self.assertNotIn('id="history-list"', html)
        self.assertNotIn("计算历史", html)
        self.assertNotIn("loadHistory", js)
        self.assertNotIn("showHistoryDetail", js)
        self.assertNotIn("/api/history", js)
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("HistoryStore", app)
        self.assertNotIn("history_store", app)
        self.assertFalse((ROOT / "pla_mmo" / "history.py").exists())

    def test_settings_are_rendered_in_a_modal_not_as_a_page(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="open-settings"', html)
        self.assertIn('id="settings-modal" class="settings-modal-backdrop hidden"', html)
        self.assertIn('role="dialog" aria-modal="true"', html)
        self.assertIn('id="close-settings"', html)
        self.assertIn('event.target === $("settings-modal")', js)
        self.assertIn('event.key === "Escape"', js)
        self.assertNotIn('data-view-link=', html)
        self.assertNotIn('activateView', js)

    def test_windows_launchers_have_no_utf8_bom(self):
        for name in ("start.bat", "start_dev.bat", "prepare_offline_engine.bat", "build_tools/build.bat"):
            data = (ROOT / name).read_bytes()
            self.assertFalse(data.startswith(b"\\xef\\xbb\\xbf"), name)

    def test_windows_launchers_use_crlf_line_endings(self):
        for name in ("start.bat", "start_dev.bat", "prepare_offline_engine.bat", "build_tools/build.bat"):
            data = (ROOT / name).read_bytes()
            self.assertIn(b"\r\n", data, name)
            self.assertEqual(data.count(b"\n"), data.count(b"\r\n"), name)

    def test_launchers_revalidate_old_engine_manifest(self):
        for name in ("start.bat", "start_dev.bat"):
            content = (ROOT / name).read_text(encoding="ascii")
            self.assertIn('findstr /C:"0.3.6"', content)

    def test_requirements_declare_z3_solver(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("z3-solver", requirements)
        self.assertIn("pyusb", requirements)

    def test_tutorial_is_in_settings_not_home(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        home = html[html.index('id="test-view"'):html.index('id="settings-view"')]
        settings = html[html.index('id="settings-modal"'):html.index('id="toast"')]
        self.assertNotIn("使用教程", home)
        self.assertIn("使用教程", settings)
        self.assertNotIn('<details class="panel tutorial-panel">', settings)
        self.assertIn('class="panel tutorial-panel"', settings)

    def test_calculator_uses_upstream_nested_rolls_schema(self):
        source = (ROOT / "pla_mmo" / "calculator.py").read_text(encoding="utf-8")
        self.assertIn('"rolls": species_rolls', source)
        self.assertNotIn('research[second_key] =', source)

    def test_installer_smoke_tests_use_upstream_nested_rolls(self):
        source = (ROOT / "tools" / "prepare_offline_engine.py").read_text(encoding="utf-8")
        self.assertEqual(source.count('"rolls": {smoke_species: 1}'), 2)

    def test_diagnostics_are_visible_in_source(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertIn("复制完整诊断报告", html)
        self.assertIn("runtime_errors.log", html)

    def test_home_uses_one_appearance_dropdown_and_keeps_legacy_engine_flags_hidden(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        home = html[html.index('id="test-view"'):html.index('id="settings-view"')]
        self.assertIn('id="appearance"', home)
        for option in ("普通大量出现", "大大量出现", "大大量出现两波"):
            self.assertIn(option, home)
        self.assertIn('id="isnormal" class="legacy-state-input"', home)
        self.assertIn('id="isbonus" class="legacy-state-input"', home)
        self.assertNotIn('启用第二轮（奖励轮）', home)
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('$("appearance").addEventListener("change", () => syncAppearanceMode(true));', js)
        self.assertIn('$("isnormal").checked = mode === "normal";', js)
        self.assertIn('$("isbonus").checked = mode === "mmo_bonus";', js)

    def test_editorial_ui_is_integrated_into_real_result_rendering(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "product.css").read_text(encoding="utf-8")
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertIn('"result-summary-grid"', js)
        self.assertIn('"result-detail-heading"', js)
        self.assertIn('"pokemon-art-frame"', js)
        self.assertIn('.result-card.result-card-editorial', css)
        self.assertIn('.result-summary-grid {', css)
        self.assertIn('id="pokemon-assets-prompt"', html)
        self.assertIn('id="download-pokemon-assets"', html)
        self.assertIn('id="pokemon-assets-global-progress"', html)
        self.assertIn('"pokemon-assets-global-progress"', js)



    def test_v058_themes_persist_and_dark_mode_has_settings_control(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        theme_css = (ROOT / "static" / "themes.css").read_text(encoding="utf-8")
        for theme in ("forest", "ocean", "snow", "lavender", "amber"):
            self.assertIn(f'data-theme-choice="{theme}"', html)
            self.assertIn(f'body[data-theme="{theme}"]', theme_css)
            self.assertIn(f'body.dark-mode[data-theme="{theme}"]', theme_css)
        self.assertIn('id="appearance-dark-mode"', html)
        self.assertIn('persistAppearance("pla-mmo-theme", theme)', js)
        self.assertIn('persistAppearance("pla-mmo-mode", enabled ? "dark" : "light")', js)
        self.assertIn("prefers-reduced-motion: reduce", theme_css)
        self.assertIn("themes.css", html)

    def test_v058_theme_layer_does_not_override_fixed_calculate_button_layout(self):
        theme_css = (ROOT / "static" / "themes.css").read_text(encoding="utf-8")
        self.assertNotIn("#calculate-form .form-footer {\n  position:", theme_css)
        self.assertNotIn(".form-footer {\n  position:", theme_css)
        product_css = (ROOT / "static" / "product.css").read_text(encoding="utf-8")
        self.assertIn("#calculate-form .form-footer", product_css)
        self.assertIn("position: relative;", product_css)
        self.assertIn(".form-scroll-region", product_css)


    def test_v061_seed_confirmation_is_theme_aware_and_not_browser_native(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        theme_css = (ROOT / "static" / "themes.css").read_text(encoding="utf-8")
        self.assertIn('id="seed-confirm-modal"', html)
        self.assertIn('id="seed-confirm-current"', html)
        self.assertIn('id="seed-confirm-candidate"', html)
        self.assertIn("showSeedConfirmation(", js)
        self.assertNotIn("window.confirm(", js)
        self.assertIn(".seed-confirm-dialog", theme_css)
        self.assertIn("var(--surface-solid)", theme_css)
        self.assertIn("var(--accent)", theme_css)

    def test_v061_result_rank_is_part_of_pokemon_title(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('`${displayName} #${index + 1}`', js)
        self.assertNotIn('`结果 ${String(index + 1).padStart(2, "0")}`', js)

    def test_v061_refresh_automatically_selects_txt_source(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('JSON.stringify({ seed_source_mode: "file", seed_file_path: path })', js)
        self.assertIn('api("/api/seed/reload"', js)
        self.assertIn('input.checked = input.value === data.source_mode;', js)
        self.assertIn('已从 TXT 文件重新读取 Seed，并切换为自动读取。', js)

    def test_v070_normal_launcher_uses_native_webview_and_cleans_local_server(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        launcher = (ROOT / "start.bat").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn('desktop_mode = _desktop_mode_enabled()', app)
        self.assertIn('def _desktop_mode_enabled()', app)
        self.assertIn('webview.start(gui="edgechromium"', app)
        self.assertIn('webview.create_window(', app)
        self.assertNotIn('window_options["icon"]', app)
        self.assertNotIn('"icon": str(icon_path)', app)
        self.assertIn('pywebview.create_window() has no cross-backend ``icon`` argument.', app)
        self.assertIn('set "PLA_DESKTOP=1"', launcher)
        self.assertIn('import flask, usb, z3, webview', launcher)
        self.assertIn('pywebview', requirements)
        self.assertIn('WEBVIEW2_USER_DATA_FOLDER', app)
        self.assertIn('if not "%APP_EXIT%"=="0" (', launcher)
        self.assertIn('    pause\n) else (', launcher)
        self.assertIn('make_server("127.0.0.1", port, app, threaded=True)', app)
        self.assertIn('server.shutdown()', app)
        self.assertIn('server.server_close()', app)
        self.assertIn('server_thread.join(timeout=5)', app)

    def test_v062_image_download_never_silently_resumes_and_requires_consent(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        manager = (ROOT / "pla_mmo" / "pokemon_assets.py").read_text(encoding="utf-8")
        self.assertIn('showPokemonAssetPrompt("manual")', js)
        self.assertNotIn('if (!manualCheck && data.choice === "download"', js)
        self.assertIn('self._state.get("choice") == "download" and self._entries and self._missing_files()', manager)
        self.assertIn('self._state["choice"] = None', manager)

    def test_v062_header_divider_is_single_and_progress_does_not_cover_results(self):
        css = (ROOT / "static" / "product.css").read_text(encoding="utf-8")
        self.assertIn('.site-header {\n  border-bottom: 0 !important;', css)
        self.assertIn('border-bottom: 1px solid var(--theme-header-border, var(--border)) !important;', css)
        self.assertIn('body:has(#pokemon-assets-global-progress:not(.hidden)) .app-shell', css)
        self.assertIn('padding-top: calc(var(--product-header-height) + 78px) !important;', css)
        self.assertIn('z-index: 400 !important; /* Download consent must sit above the Settings dialog. */', css)

    def test_settings_are_split_into_clear_category_tabs(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "themes.css").read_text(encoding="utf-8")
        for key in ("appearance", "seed", "pokemon", "resources", "help"):
            self.assertIn(f'data-settings-tab="{key}"', html)
            self.assertIn(f'data-settings-panel="{key}"', html)
        self.assertIn("activateSettingsTab", js)
        self.assertIn("settings-tab-content", css)
        self.assertIn("var(--surface-2)", css)



class UIInteractionPolishTests(unittest.TestCase):
    def test_settings_dialog_has_stable_height_and_internal_scrolling(self):
        css = (ROOT / "static" / "themes.css").read_text(encoding="utf-8")
        self.assertIn("height: min(780px, calc(100dvh - 36px)) !important;", css)
        self.assertIn("overflow-y: auto !important;", css)
        self.assertIn("settings-modal-backdrop.is-closing", css)
        self.assertIn("settings-dialog-out", css)

    def test_settings_modal_uses_same_animated_close_path_for_all_dismissals(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function finishSettingsModalClose(modal)", js)
        self.assertIn('modal.classList.add("is-closing")', js)
        self.assertIn('if (event.target === $("settings-modal")) closeSettingsModal();', js)
        self.assertIn('$("close-settings").addEventListener("click", closeSettingsModal);', js)
        self.assertIn('if (event.key === "Escape" && !$("settings-modal").classList.contains("hidden"))', js)

    def test_pokemon_selector_and_quantity_fields_have_matching_feedback(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "themes.css").read_text(encoding="utf-8")
        self.assertIn('list.classList.add("is-opening")', js)
        self.assertIn('list.classList.add("is-closing")', js)
        self.assertIn('field.classList.add("selection-updated")', js)
        self.assertIn(".field.selection-updated .search-select-control", css)
        self.assertIn(".field.selection-updated > select", css)

    def test_result_details_animate_and_arrow_is_centered(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "themes.css").read_text(encoding="utf-8")
        self.assertIn("function setResultDetailsOpen(panel, button, label, shouldOpen)", js)
        self.assertIn('setResultDetailsOpen(detailsPanel, detailsButton, detailButtonLabel, shouldOpen)', js)
        self.assertIn("body[data-theme] .route-detail-arrow", css)
        self.assertIn("align-items: center;", css[css.index("body[data-theme] .route-detail-arrow"):css.index("body[data-theme] .route-detail-button.is-open")])
        self.assertIn("prefers-reduced-motion: reduce", css)


if __name__ == "__main__":
    unittest.main()


class ResultTimelineVisualRegressionTests(unittest.TestCase):
    def test_operation_phases_have_closed_theme_aware_borders(self):
        css = (ROOT / "static" / "themes.css").read_text(encoding="utf-8")
        self.assertIn("body[data-theme] .operation-section {", css)
        self.assertIn("border: 1px solid var(--border) !important;", css)
        self.assertIn("border-radius: 13px !important;", css)
        self.assertIn("body[data-theme] .operation-section.operation-target-event", css)
        self.assertIn("body[data-theme] .operation-timeline::before", css)

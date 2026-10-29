## v0.7.3 — 计算结果渐进显示与交互过渡优化

- 计算完成后，结果卡片采用轻微位移与透明度过渡，并按顺序渐进显示宝可梦信息、属性、路径概要和详细步骤，减少整块内容瞬间出现的突兀感。
- 结果数量、Seed／群体摘要、研究等级与闪耀护符摘要、计算状态消息和 Toast 提示在更新时增加轻量反馈动画。
- 空结果状态使用与结果卡片一致的进入过渡；重复计算时可重新触发动画。
- 为主题相关的卡片、路径标签和摘要补充轻量颜色／边框过渡；遵守系统「减少动态效果」设置。
- 动画仅使用透明度与位移，不使用高斯模糊；不修改 RNG 算法、Seed 读取、路径计算或结果排序。
- 更新应用版本、静态资源缓存版本、构建工具与安装包版本至 v0.7.3。
- 整理公开发布文档：补充完整 README、新手手册、上游代码与图片来源说明、五张 GitHub 截图占位图及发布辅助脚本；不涉及应用运行逻辑改动。

## v0.7.2 — 设置滚动与帮助页面重整

- 宝可梦研究等级列表取消内部独立滚动条，所有图鉴项目随设置内容区域一起滚动，避免双滚动条。
- 「帮助与诊断」中的使用教程改为默认完整展示，不再需要点击折叠标题；重写为适配当前 Seed 来源、群体类型、研究等级、护符、结果筛选、图片资源和诊断流程的教程。
- 重做「关于本程序」信息区，作者、版本、运行方式与本地隐私说明采用独立信息块布局，修复文字拥挤和对齐不清的问题。
- 更新应用、静态资源缓存、Windows 构建工具与版本文档至 v0.7.2；不修改计算引擎与 RNG 路径逻辑。

## v0.7.1 — 设置布局与交互动画精修
- 设置中心采用稳定的响应式固定高度；分类内容在窗口内部滚动，切换分类时不再让整个窗口忽高忽低。
- 设置窗口打开、点击关闭按钮、点击遮罩空白处和按 Escape 关闭时使用同一套淡入／淡出与轻微位移动画。
- 宝可梦搜索候选列表增加开合过渡；第一／第二轮数量与宝可梦选择统一使用轻微选中反馈。
- 「查看详细」路径步骤改为高度、透明度与位移动画展开／收起；箭头固定盒子居中并旋转，不再因字符基线产生错位。
- 为原生 details 内容增加轻量展开动效；遵守系统「减少动态效果」偏好。
- 更新 HTML 静态资源缓存版本与 Windows 文件版本号至 0.7.1。
- 不修改 Seed 校验、路径计算、研究等级映射、图片下载策略或本地计算引擎。
- 构建工具继续支持便携版（EXE + 资源目录 + ZIP）、安装版和同时构建两种版本；此源码包未包含在非 Windows 环境中生成的 Windows EXE。

## v0.7.0 — One-click Windows build tools and portable/installable releases
- Fixed the build-blocking regression test that still asserted the pre-v0.7.0 desktop-mode expression; it now checks the current `_desktop_mode_enabled()` helper.
- Replaced the desktop window's background `app.run()` server with a stoppable Werkzeug server. Closing the WebView or encountering a startup error now triggers server shutdown, socket closure, and a bounded thread join so the local port is released.
- Added a regression test for local-server cleanup after the native window closes.
- Updated the source launcher so it pauses only after an error; a normal close no longer leaves the launcher command window waiting for a keypress.
- Fixed packaged EXE startup mode: PyInstaller-frozen builds now open a native pywebview/WebView2 window by default instead of launching the default browser. Source development mode remains browser-based unless `PLA_DESKTOP=1` is set.
- Added a regression test for frozen-build and source-run window selection.
- Fixed the Windows asset-route regression test by explicitly closing streamed Flask responses before temporary test-directory cleanup; the test uses a tiny generated fixture image and does not require downloading Pokémon artwork.

- Added `build_tools/` to keep all build-only scripts, the optional custom icon, the default icon, build dependencies, installer script, reports, temporary cache, and generated packages out of the project root.
- Added `build_tools/build.bat` and `build_tools/build.py`: a guided build menu can produce a portable onedir ZIP, an Inno Setup installer, or both. The normal source workflow remains available through the root `start.bat` and does not require compiling an EXE.
- The build tool creates an isolated `build_tools/.venv`, installs missing build/runtime packages from the declared requirements, checks required local RNG files, attempts to repair a missing engine using the existing preparation script, and runs regression tests before release builds.
- Optional `build_tools/logo.icon` is converted to a Windows ICO when valid; when missing or invalid, the tool falls back to `build_tools/default_app.ico` (copied from the existing app logo). The chosen icon is used for the EXE, native window, installer, and shortcuts.
- Added version/company metadata, author identity `君粒&GPT`, a build report, persistent build logs, a companion source archive, and a Chinese installer script. Failed builds do not intentionally replace the previous successful portable bundle.
- Separated immutable bundled resources from writable user data paths for frozen builds. Settings, logs, downloaded sprites, and custom sprites live under the current Windows user's local application data directory; legacy `static/pokemon/custom` and `static/pokemon/cache` images remain readable in source mode.
- Kept the existing Seed workflow, research-level settings, five themes, dark mode, image-download consent, and RNG calculation algorithm. No new gameplay feature was added.
- Windows native WebView2 startup and actual PyInstaller output still require a Windows machine for final smoke testing; this source package does not claim a prebuilt EXE has been verified in this non-Windows build environment.

## v0.6.5：设置中心纵向布局与稳定性精修

- 将「宝可梦设置」改为单列纵向排列：通用设置、统一设置研究等级、逐只宝可梦研究等级依次呈现，取消左右分栏。
- 批量研究等级按钮缩小并改为紧凑横向排列，窄窗口下自动换行；补齐键盘焦点样式并保留主题色。
- 修正逐只设置研究等级后列表计数文案：无搜索时显示总数，有搜索时显示筛选数量，避免每次修改都错误显示为“显示 N / N”。
- 更新应用版本、静态资源缓存版本与构建报告，避免桌面 WebView 继续使用旧版 CSS/HTML。
- 回归验证 Seed 来源切换、设置备份恢复、五套主题／夜间模式、图片下载再次确认、研究等级映射与结果卡片边框；这些流程保持原有逻辑，不做无关重写。
- 不修改 RNG 核心算法、Seed 校验规则、图片资源下载策略或桌面窗口启动机制。

## v0.6.4：宝可梦研究等级统一管理与结果参数摘要

- 新增完整洗翠图鉴研究等级设置，按图鉴顺序显示进化链相邻的宝可梦，并提供中文／英文搜索、图片缩略图与逐只等级选择。
- 支持一键将全部宝可梦统一设为基础、研究等级 10 或完美研究；批量设置会清除单独覆盖，单独设置会自动保存。
- 将闪耀护符状态移动到「宝可梦设置」的通用设置中；主页不再重复显示研究等级下拉框或护符复选框。
- 每次计算完成后，在结果区顶部显示本次实际使用的第一轮／第二轮宝可梦研究等级与闪耀护符状态；结果卡片不再重复显示研究等级。
- 计算引擎按宝可梦内部物种／形态 ID 读取各自研究等级；同一物种在两轮出现时自动共用同一个等级，避免出现两个不同的等级设置。
- 设置文件新增 `pokemon_research_levels`，兼容旧版全局默认研究等级与闪耀护符配置；保留原子写入与备份恢复机制。
- 不修改 RNG 核心算法、Seed 读取逻辑、图片下载确认流程、五套主题或桌面窗口启动方式。

## v0.6.3 — Stability, settings recovery, and Seed confirmation safeguards

- Serialize settings access and write settings atomically, with a last-known-good `settings.backup.json` backup.
- Preserve malformed settings files for diagnosis and recover from a valid backup where possible; normalize invalid legacy settings values.
- Fix Seed error responses where snapshot data could overwrite `ok: false`, causing invalid or empty TXT reads to be reported as successful.
- Guard against a TXT Seed changing while the confirmation dialog is open; canceling confirmation clears the pending candidate without changing the active Seed.
- Include settings and backup status in the diagnostic report.
- No RNG algorithm, calculation parameters, result schema, theme design, desktop-window behavior, or image-download consent changes.

## v0.6.2.2 — Window icon and persistent appearance

- Apply the bundled mountain `.ico` to the native Windows WebView2 window after it is shown; also expose it as the page favicon.
- Persist the selected palette and light/dark mode in the app's `settings.json` instead of relying only on WebView localStorage.
- Migrate appearance preferences from the previous localStorage-only release on first launch.
- No changes to Seed handling, asset downloads, or RNG calculations.

# Changelog

## v0.6.2.1 — Startup hotfix

- Fixed desktop startup crash caused by passing unsupported `icon` keyword to `pywebview.create_window()`. The window now uses only supported API arguments.
- No changes to Seed handling, image-download consent, local engine, or RNG calculation logic.

## v0.6.2 — Standalone desktop window, explicit image-download consent, and header alignment

- The normal Windows launcher now opens a native desktop window backed by Microsoft Edge WebView2 instead of launching the user's default browser.
- WebView2 uses an app-specific profile under the local application data directory, separate from normal Edge/Chrome browsing data; static resource query versions are bumped to v0.6.2 to avoid stale assets after updates.
- Image downloads always require an explicit click in the themed confirmation dialog. The app no longer silently resumes an interrupted download on startup; if files remain missing after a restart, the user is asked again.
- Removed the competing outer header divider so the top navigation has one aligned bottom line. The fixed image-download progress banner now reserves space above results instead of overlapping the result heading.
- Kept the bundled `static/app.ico` asset, while avoiding unsupported icon arguments in the pywebview window API. The existing local Flask/RNG engine and calculations remain unchanged.

## v0.6.1 — Themed Seed confirmation, title ordering, and source switching

- Replaced native browser Seed-change confirmation prompts with a theme-aware dialog that follows all five palettes and dark mode.
- Appended the visible result rank (`#1`, `#2`, ...) directly to the Pokémon title using the same typography.
- Made the refresh control automatically switch to the configured TXT-file source, save the source mode, and reload the file Seed; a missing path directs the user to Seed settings.
- Kept manual Seed application on manual source mode and synchronized source-mode controls with the backend state.
- Left RNG calculations and result payloads unchanged.

## v0.6.0 — Result hierarchy, research levels, and categorized settings

- Put Pokémon attributes above route summaries; detailed operations remain below route summaries.
- Close and unify borders around Pokémon metadata, route summary headings, detail headings, and simultaneous-route panels across all themes and dark mode.
- Fix research-level labels by reading the calculation payload's `research_levels` map, with species/form normalization for Alpha entries.
- Reorganize Settings into Appearance, Seed Source, Pokémon Settings, Image Assets, and Help & Diagnostics tabs.
- Route the Seed settings shortcut and diagnostics shortcut to their relevant settings categories.
- Preserve Seed handling, species candidates, RNG algorithms, calculation parameters, and the fixed sidebar calculation button.

## v0.5.9
- Removed the non-standard visible “same target's other reachable paths” panel. Raw engine `dupes` metadata remains available in the raw result data and does not affect shiny counts or calculations.
- Fixed operation timeline sections to use closed, theme-aware rounded borders with consistent spacing across all five palettes and their dark modes.
- Kept target-event cards distinct using each palette's gold tokens; removed the timeline connector that visually crossed card boundaries.
- No RNG engine, Seed handling, path calculation, or input parameter changes.

## v0.5.8
- Added five selectable palettes in Settings: Forest Green, Ocean Blue, Pure Snow, Lavender, and Warm Amber.
- Added a tuned dark palette for each theme; theme and light/dark mode preferences persist locally across launches.
- Added subtle transitions for theme colors, controls, modal entry, and hover/focus feedback. Animations respect `prefers-reduced-motion` and do not delay calculations.
- Added a lightweight `themes.css` layer after the existing product styles. The existing sidebar scrolling and bottom calculate-button positioning rules are intentionally unchanged.
- RNG engine, Seed handling, candidate loading, calculation logic, and calculation parameter schema are unchanged.


## v0.5.7
- Fixed the root cause of repeated old UI appearing after updates: the launcher and app now select an available loopback port starting at 5000. If an older process still owns 5000, the new build opens on 5001 (or the next free port) instead of silently opening the old instance.
- The Windows launcher prints the exact URL it selected.
- Settings launch buttons now have direct click handlers.
- Candidate-list failures now leave the loading state, show the error, and offer a retry button. Startup setup errors no longer prevent the independent API requests from running.
- Added explicit neutral charcoal header/theme overrides and updated static cache keys to v0.5.7.
- No RNG calculation algorithm or calculation parameter schema changes.

## v0.5.6
- Startup requests run independently with bounded timeouts.
- Settings modal activation and neutral charcoal night theme adjustments.

# Build Tools — PLA MMO Path Finder v0.7.3

作者：**君粒&GPT**

所有构建专用文件都集中在此目录，避免项目根目录继续堆积编译脚本、图标和临时文件。

## 使用方式

1. 在 Windows 10/11 上双击 `build.bat`。
2. 首次运行会创建 `.venv` 并安装 `../requirements.txt` 与 `requirements-build.txt` 中缺少的依赖。
3. 若未检测到 Python 3.10+，脚本会询问是否从 `python.org` 下载官方 Python 3.12.10 安装程序，并先验证数字签名。
4. 选择 `1` 编译便携版、`2` 编译安装版、`3` 同时编译两种版本。
5. 产物在 `output/`，报告和日志在 `reports/`。

源码版仍可通过项目根目录的 `start.bat` 运行，不需要先编译 EXE。源码运行仍需要 Python 和项目依赖；编译后的 EXE 不要求目标电脑安装 Python。

## 图标规则

- 可选自定义图标：把文件放在 `build_tools/logo.icon`。
- 内容可以是有效 ICO，或 Pillow 可读取的 PNG/JPEG 图像；构建器根据内容转换为 Windows ICO。
- 不存在或无法读取时，自动使用 `default_app.ico`（项目原有默认山峰 Logo 的副本）。
- 自定义图标只用于本次构建的暂存资源，不会覆盖 `../static/app.ico`。

## 输出与保护

- `output/PLA-MMO-Path-Finder-v0.7.3-portable.zip`
- `output/PLA-MMO-Path-Finder-v0.7.3-setup.exe`
- `output/PLA-MMO-Path-Finder-v0.7.3-source.zip`
- `reports/build.log` 与 `reports/build_report.txt`

编译会先检查必要资源并运行 Python 自动化测试；测试失败时停止正式构建。清理缓存菜单只删除 `.work/`，不会删除成功产物、源码、用户配置或图片资源。

安装版需要 Inno Setup。找不到时，构建器会先尝试 winget；若不可用，会从 Inno Setup 官方站点下载安装程序，并在打开安装向导后等待你完成安装。

打包后的桌面窗口依赖 Microsoft Edge WebView2 Runtime。构建器会保留清晰的错误日志；如果目标电脑没有该运行时，需要先安装微软官方 WebView2 Runtime。

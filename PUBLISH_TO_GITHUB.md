# 发布到 GitHub（新手操作）

本压缩包已经包含项目源码、README、许可证说明、构建工具和五张截图占位图。**不需要先运行软件或编译 EXE 才能发布源码仓库。**

## 推荐方式：使用附带的一键推送脚本

### 第一步：在 GitHub 创建空仓库

1. 登录 GitHub，打开 <https://github.com/new>。
2. Repository name 可以填写 `PLA-MMO-Path-Finder`。
3. 选择 Public（公开）或 Private（私有）。
4. 为避免首次推送冲突，创建时不要勾选添加 README、`.gitignore` 或 License（本压缩包已经有这些文件）。
5. 创建仓库后，复制仓库的 HTTPS 地址，例如 `https://github.com/你的用户名/PLA-MMO-Path-Finder.git`。

### 第二步：推送项目

1. 完整解压本压缩包。
2. 确认解压后的项目根目录中能看到 `README.md`、`app.py`、`start.bat` 和 `build_tools` 文件夹。
3. 如果电脑还没有 Git for Windows，请先从 <https://git-scm.com/download/win> 安装 Git。
4. 双击项目根目录中的 `发布到GitHub.bat`。
5. 粘贴第一步复制的仓库 HTTPS 地址，并按提示完成提交作者信息（如果 Git 尚未配置）。
6. GitHub 登录／凭据管理器出现授权提示时，按屏幕提示完成授权。成功后，刷新 GitHub 仓库页面即可看到文件。

脚本会初始化本地 Git 仓库、提交当前文件并推送到 `main` 分支。它不会上传项目目录之外的文件，也不会把 GitHub 密码写进脚本。

## 不使用脚本

也可以使用 GitHub Desktop：安装 <https://desktop.github.com/>，选择 **Add an Existing Repository**，指定解压后的项目目录，然后选择 **Publish repository**。

由于项目文件数量超过普通手动逐个上传的便利范围，建议使用 Git 或 GitHub Desktop，而不是在网页里一个文件一个文件地上传。

## 发布前建议检查

- [ ] 将 `docs/screenshots/` 下五张占位 PNG 替换成真实界面截图。
- [ ] 确认截图不含个人文件路径、用户名、私有 Seed 或其他隐私信息。
- [ ] 检查 `README.md` 中的项目说明、图片来源、上游项目和许可证信息。
- [ ] 确认没有把个人 Seed 文件、运行日志、下载的图片缓存或构建产物提交到仓库。
- [ ] 阅读 `LICENSE` 和 `LICENSES.md`，确认自己理解 GPL-3.0 对公开分发的要求。

## 如需发布 EXE

源码仓库发布后，在 Windows 电脑上运行 `build_tools\\build.bat`，生成便携版或安装版。随后在 GitHub 仓库打开 **Releases → Draft a new release**，上传构建输出中的便携版 ZIP 和／或安装程序。不要把 EXE 当成源码仓库的必需文件；源码和发行二进制可以分开维护。

## 可直接使用的仓库介绍与 Topics

**Repository description（仓库简介）：**

`本地运行的《宝可梦传说 阿尔宙斯》MMO 闪光路径计算器，支持 Seed、研究等级、闪耀护符、主题切换和 Windows 桌面打包。`

**建议 Topics：**

`pokemon-legends-arceus` · `pokemon` · `rng` · `shiny-hunting` · `python` · `flask` · `pywebview`

## GitHub Release 文案

创建 `v0.7.3` Release 时，可以直接复制 [`docs/GITHUB_RELEASE_NOTES_v0.7.3.md`](docs/GITHUB_RELEASE_NOTES_v0.7.3.md) 中的内容。若只发布源码仓库，不需要创建 Release 或上传 EXE。

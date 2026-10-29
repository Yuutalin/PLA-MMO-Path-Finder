# 第三方组件、数据与素材来源

**项目作者：君粒&GPT**  
**项目许可证：GNU GPL v3.0**（完整文本见 [`LICENSE`](LICENSE)）

本文件用于记录仓库中已知的第三方代码、运行依赖与可选图片来源。各上游项目及素材仍受其自身版权、许可证和使用条件约束。

## 1. 本地 RNG 计算引擎

- 项目：[capitalism-sudo/pla-multi-checker-web](https://github.com/capitalism-sudo/pla-multi-checker-web)
- 用途：提供 MMO RNG 路径计算相关代码与数据资源。本项目在本地准备并调用所需模块，不通过上游网站 API 计算结果。
- 许可证：GPL-3.0。
- 许可证副本：[`offline_engine/UPSTREAM_LICENSE_GPL-3.0.txt`](offline_engine/UPSTREAM_LICENSE_GPL-3.0.txt)。首次引擎准备流程也会记录上游来源与版本信息。

## 2. 可选宝可梦图片

- [PokeAPI/sprites](https://github.com/PokeAPI/sprites)
- [PokeAPI](https://pokeapi.co/)

仓库不默认打包完整宝可梦图片集。用户在应用内明确确认后，图片资源管理器会尝试下载可用图片并缓存到本机。部分形态可能没有对应图片。

宝可梦名称、角色形象、游戏素材和商标归 Nintendo、The Pokémon Company、GAME FREAK、Creatures Inc. 及相应权利人所有。图片在公开仓库中可访问，并不自动代表可以不受限制地复制或再分发。分发包含图片缓存的发行包前，请自行核实相关权利与许可。

## 3. 主要 Python 依赖

运行依赖范围记录在 [`requirements.txt`](requirements.txt)，构建依赖记录在 [`build_tools/requirements-build.txt`](build_tools/requirements-build.txt)。主要依赖包括：

- [Flask](https://github.com/pallets/flask)
- [pywebview](https://github.com/r0x0r/pywebview)
- [z3-solver / Z3](https://github.com/Z3Prover/z3)
- [PyUSB](https://github.com/pyusb/pyusb)

每个依赖均保留其自身的许可证与版权声明；具体条款以对应上游仓库和发行包为准。

## 4. 项目界面与图标

仓库内的山峰图形用于本项目界面、favicon 和 Windows 窗口图标，不是宝可梦官方标识。GitHub README 中的五张截图目前为占位图，发布者可替换为自己截取的真实界面截图。请勿在截图中泄露个人路径、用户名、私有 Seed 或其他敏感信息。

## 5. 发行注意事项

- 分发包含 GPL-3.0 上游引擎的源码或二进制时，应保留许可证文本和相关版权声明，并遵守 GPL-3.0 对源码提供、修改说明等适用要求。
- 不要把未经核实授权的宝可梦图片缓存直接提交到公开仓库或放入发行包。
- 任何依赖的许可证更新或上游数据源变化，都应在正式发行前再次核查。

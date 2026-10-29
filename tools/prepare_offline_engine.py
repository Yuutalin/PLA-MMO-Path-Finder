from __future__ import annotations

import json
import os
import importlib.util
import subprocess
import traceback
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = PROJECT_ROOT / "offline_engine"
REPO_ZIP_URLS = (
    "https://codeload.github.com/capitalism-sudo/pla-multi-checker-web/zip/refs/heads/main",
    "https://github.com/capitalism-sudo/pla-multi-checker-web/archive/refs/heads/main.zip",
)
SEEDHASHES_URL = "https://fifamvp.pythonanywhere.com/static/resources/seedhashes.json"


def log(message: str) -> None:
    print(message, flush=True)
    try:
        with (PROJECT_ROOT / "offline_engine_setup.log").open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
    except OSError:
        pass


def ensure_runtime_dependencies() -> None:
    """Install app/runtime requirements with the exact interpreter running this script."""
    missing = []
    for module_name, package_name in (("flask", "Flask"), ("usb", "pyusb"), ("z3", "z3-solver")):
        try:
            available = importlib.util.find_spec(module_name) is not None
        except (ImportError, ValueError):
            available = False
        if not available:
            missing.append(package_name)

    import_error = None
    try:
        import flask  # noqa: F401
        import usb  # noqa: F401
        import z3  # noqa: F401
    except Exception as exc:
        import_error = exc

    if missing or import_error is not None:
        requirements = PROJECT_ROOT / "requirements.txt"
        if missing:
            log("检测到缺少 Python 依赖：" + "、".join(missing))
        if import_error is not None:
            log(f"依赖模块存在但导入失败：{type(import_error).__name__}: {import_error}")
        log(f"使用当前解释器修复依赖：{sys.executable}")
        command = [
            sys.executable, "-m", "pip", "install",
            "--disable-pip-version-check",
        ]
        if import_error is not None:
            command.append("--force-reinstall")
        command.extend(["-r", str(requirements)])
        process = subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if process.stdout is not None:
            for line in process.stdout:
                log("pip: " + line.rstrip())
        code = process.wait()
        if code != 0:
            raise RuntimeError(
                f"Python 依赖安装失败（退出码 {code}）。请查看 requirements.txt 和 offline_engine_setup.log。"
            )

    try:
        import flask  # noqa: F401
        import usb  # noqa: F401
        import z3
        z3_version = z3.get_version_string()
    except Exception as exc:
        raise RuntimeError(
            f"依赖安装后仍无法导入 Flask/pyusb/z3：{type(exc).__name__}: {exc}"
        ) from exc
    log(f"Python 依赖检查通过：Flask、pyusb 可导入；z3-solver {z3_version} 可导入。")


def download(url: str, destination: Path, label: str) -> bool:
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "PLA-MMO-Path-Finder/0.3.6", "Accept": "*/*"},
        )
        with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as out:
            total = response.headers.get("Content-Length")
            total_bytes = int(total) if total and total.isdigit() else 0
            downloaded = 0
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
        if not destination.is_file() or destination.stat().st_size < 100:
            raise RuntimeError("下载内容为空或过小")
        log(f"{label}下载完成：{destination.stat().st_size:,} bytes")
        return True
    except Exception as exc:
        log(f"{label}下载失败：{url} ({type(exc).__name__}: {exc})")
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def find_source(extracted: Path) -> Path:
    for candidate in extracted.rglob("checkmmo.py"):
        if candidate.parent.name == "pla" and (candidate.parent.parent / "static" / "resources").is_dir():
            return candidate.parent.parent
    raise RuntimeError("下载包内找不到 pla/checkmmo.py 或 static/resources。")


def normalize_candidates(raw):
    if isinstance(raw, dict):
        if isinstance(raw.get("species"), list):
            raw = raw["species"]
        else:
            raw = list(raw.values())
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if item.get("species") is None or item.get("hash") is None:
            continue
        result.append({
            "species": str(item["species"]),
            "label": str(item.get("label") or item["species"]),
            "hash": str(item["hash"]),
            "parent_id": str(item.get("parent_id", "")),
        })
    return result


def make_fallback_candidates(encounter_path: Path) -> list[dict]:
    try:
        tables = json.loads(encounter_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise RuntimeError(f"无法读取 mmo_es.json 以生成候选列表：{exc}") from exc
    if not isinstance(tables, dict) or not tables:
        raise RuntimeError("mmo_es.json 不是有效的遭遇表字典。")

    result = []
    for table_hash, slots in tables.items():
        if not isinstance(slots, list) or not slots:
            continue
        first = next((slot for slot in slots if isinstance(slot, dict) and slot.get("name")), None)
        species = str(first.get("name")) if first else "未知宝可梦"
        label = f"{species}（遭遇表 {str(table_hash)[:10]}）"
        # Duplicate entries allow the existing UI's ordinary/normal mode switch
        # to show all tables. Bonus-table parent relationships are explicitly
        # marked incomplete and the UI will show all tables with a warning.
        for parent_id in ("0", "-1"):
            result.append({
                "species": species,
                "label": label,
                "hash": str(table_hash),
                "parent_id": parent_id,
            })
    if not result:
        raise RuntimeError("无法从 mmo_es.json 生成任何有效的候选遭遇表。")
    return result


def main(source_arg: str | None = None) -> int:
    log("=" * 68)
    log("PLA MMO 闪光路径助手：准备本地 RNG 引擎")
    log("首次准备需要联网下载一次公开源码和资源；安装完成后计算不请求远程 API。")
    log("本地 Seed 和设置不会被覆盖。")

    # Never leave an old success marker behind if a repair attempt fails.
    try:
        (ENGINE_ROOT / "engine_install_ok.txt").unlink(missing_ok=True)
    except OSError:
        pass

    temp_root = Path(tempfile.mkdtemp(prefix="pla-mmo-engine-"))
    try:
        ensure_runtime_dependencies()
        if source_arg:
            source = Path(source_arg).resolve()
        elif all((ENGINE_ROOT / "pla" / name).is_file() for name in ("checkmmo.py",)) and all(
            (ENGINE_ROOT / "static" / "resources" / name).is_file()
            for name in ("mmo_es.json", "mmopaths.json", "nonbonuspaths.json")
        ):
            # A previous installation may have downloaded all upstream assets but
            # failed its smoke test. Stage those local files before replacing the
            # engine folder, so the repair does not needlessly download 18 MB again.
            source = temp_root / "existing_source"
            source.mkdir(parents=True)
            shutil.copytree(ENGINE_ROOT / "pla", source / "pla", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            shutil.copytree(ENGINE_ROOT / "static" / "resources", source / "static" / "resources", dirs_exist_ok=True)
            old_license = ENGINE_ROOT / "UPSTREAM_LICENSE_GPL-3.0.txt"
            if old_license.is_file():
                shutil.copy2(old_license, source / "LICENSE")
            log("发现已有源码和本地资源，将复用它们进行修复，不重新下载源码包。")
        else:
            zip_path = temp_root / "upstream.zip"
            downloaded = False
            for url in REPO_ZIP_URLS:
                if download(url, zip_path, "原版源码包"):
                    downloaded = True
                    break
            if not downloaded:
                raise RuntimeError(
                    "无法下载原版源码包。请检查网络后重试；也可以在能联网的电脑上运行此脚本完成一次安装。"
                )
            extract_root = temp_root / "extracted"
            extract_root.mkdir()
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(extract_root)
            source = find_source(extract_root)

        if not (source / "pla" / "checkmmo.py").is_file():
            raise RuntimeError(f"来源目录不是有效的原版源码：{source}")
        resource_source = source / "static" / "resources"
        for name in ("mmo_es.json", "mmopaths.json", "nonbonuspaths.json"):
            if not (resource_source / name).is_file():
                raise RuntimeError(f"原版源码缺少必要资源：static/resources/{name}")

        seedhashes_source = resource_source / "seedhashes.json"
        candidate_source = "upstream_bundle"
        candidate_mapping_complete = False
        normalized_candidates = []
        if seedhashes_source.is_file():
            try:
                normalized_candidates = normalize_candidates(
                    json.loads(seedhashes_source.read_text(encoding="utf-8-sig"))
                )
            except (OSError, json.JSONDecodeError):
                normalized_candidates = []
            if normalized_candidates:
                candidate_mapping_complete = all(item["parent_id"] != "" for item in normalized_candidates)
            else:
                seedhashes_source = Path("__missing_seedhashes__")
        if not seedhashes_source.is_file():
            seedhashes_download = temp_root / "seedhashes.json"
            if download(SEEDHASHES_URL, seedhashes_download, "宝可梦候选映射"):
                try:
                    candidate_data = json.loads(seedhashes_download.read_text(encoding="utf-8-sig"))
                    normalized_candidates = normalize_candidates(candidate_data)
                    if normalized_candidates:
                        seedhashes_source = seedhashes_download
                        candidate_source = "official_seedhashes_resource"
                        candidate_mapping_complete = all(item["parent_id"] != "" for item in normalized_candidates)
                except (OSError, json.JSONDecodeError):
                    log("候选映射文件不是有效 JSON，将尝试从本地遭遇表生成候选列表。")
            if not seedhashes_source.is_file():
                candidate_source = "generated_from_local_encounter_tables"
                candidate_mapping_complete = False

        if ENGINE_ROOT.exists():
            shutil.rmtree(ENGINE_ROOT)
        (ENGINE_ROOT / "app").mkdir(parents=True)
        (ENGINE_ROOT / "static").mkdir(parents=True)
        shutil.copytree(source / "pla", ENGINE_ROOT / "pla", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(resource_source, ENGINE_ROOT / "static" / "resources", dirs_exist_ok=True)

        # Import only the MMO calculation module, not the upstream website app.
        (ENGINE_ROOT / "__init__.py").write_text(
            '"""Vendored local subset of PLA MMO Checker."""\n', encoding="utf-8"
        )
        (ENGINE_ROOT / "pla" / "__init__.py").write_text(
            '"""Local MMO calculation entry point."""\nfrom .checkmmo import check_mmo_from_seed\n',
            encoding="utf-8",
        )
        (ENGINE_ROOT / "app" / "__init__.py").write_text(
            "from pathlib import Path\nimport os\nRESOURCE_PATH = str(Path(__file__).resolve().parents[1] / 'static') + os.sep\n",
            encoding="utf-8",
        )

        if seedhashes_source.is_file():
            shutil.copy2(seedhashes_source, ENGINE_ROOT / "static" / "resources" / "seedhashes.json")
        else:
            candidates = make_fallback_candidates(ENGINE_ROOT / "static" / "resources" / "mmo_es.json")
            (ENGINE_ROOT / "static" / "resources" / "seedhashes.json").write_text(
                json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        license_path = source / "LICENSE"
        if license_path.is_file():
            shutil.copy2(license_path, ENGINE_ROOT / "UPSTREAM_LICENSE_GPL-3.0.txt")

        manifest = {
            "app_version": "0.3.6",
            "python_version": sys.version.split()[0],
            "z3_solver_version": __import__("z3").get_version_string(),
            "upstream_repository": "https://github.com/capitalism-sudo/pla-multi-checker-web",
            "upstream_branch": "main",
            "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "candidate_mapping_complete": candidate_mapping_complete,
            "candidate_source": candidate_source,
            "license": "GPL-3.0",
            "offline_calculation": True,
        }
        (ENGINE_ROOT / "engine_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # A smoke test that actually imports the local engine and calculates one
        # small first-round case. If this fails, setup is not reported as complete.
        # Keep PROJECT_ROOT on sys.path and import the engine as
        # offline_engine.pla.checkmmo so upstream relative imports remain valid.
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        from pla_mmo.local_engine import LocalMMOEngine

        engine = LocalMMOEngine()
        status = engine.status()
        if not status["installed"]:
            raise RuntimeError("本地引擎文件检查失败：" + "; ".join(status["missing"]))
        candidates = engine.load_species()["species"]
        tables = engine._load_encounter_tables()
        valid = next((item for item in candidates if item["hash"] in tables), None)
        if valid is None:
            # The candidate list may use an equivalent 0x-prefixed hash.
            valid = next((item for item in candidates if item["hash"].lower().removeprefix("0x") in
                          {str(key).lower().removeprefix("0x") for key in tables}), None)
        if valid is None:
            raise RuntimeError("候选列表中的哈希与本地遭遇表不匹配。")
        # Upstream research keys use the Pokédex species name, not an Alpha label.
        smoke_species = str(valid["species"]).strip()
        if smoke_species.casefold().startswith("alpha "):
            smoke_species = smoke_species[6:].strip()
        smoke = engine.calculate_mmo_path("1", {
            "filter": "is_shiny",
            "research": {"shinycharm": False, "rolls": {smoke_species: 1}},
            "shiny_charm": False,
            "frencounter": valid["hash"],
            "brencounter": "",
            "isbonus": False,
            "frspawns": 8,
            "brspawns": 6,
            "isnormal": False,
        })
        if not isinstance(smoke.get("results"), list):
            raise RuntimeError("本地引擎冒烟测试未返回结果列表。")
        log(f"无闪耀护符的本地计算冒烟测试通过；测试表：{valid['label']}；返回 {len(smoke['results'])} 条匹配结果。")
        charm_smoke = engine.calculate_mmo_path("1", {
            "filter": "is_shiny",
            "research": {"shinycharm": True, "rolls": {smoke_species: 1}},
            "shiny_charm": True,
            "frencounter": valid["hash"],
            "brencounter": "",
            "isbonus": False,
            "frspawns": 8,
            "brspawns": 6,
            "isnormal": False,
        })
        if not isinstance(charm_smoke.get("results"), list):
            raise RuntimeError("闪耀护符开启时的本地引擎测试未返回结果列表。")
        log(f"开启闪耀护符的本地计算冒烟测试通过；返回 {len(charm_smoke['results'])} 条匹配结果。")
        (ENGINE_ROOT / "engine_install_ok.txt").write_text(
            "Local RNG smoke test passed\n", encoding="utf-8"
        )
        log("本地 RNG 引擎安装完成。以后计算路径不再请求远程计算 API。")
        if not candidate_mapping_complete:
            log("提示：原版第一轮/奖励轮候选对应关系数据未取得，已生成备用候选表；界面会显示警告。")
        return 0
    except Exception as exc:
        try:
            (ENGINE_ROOT / "engine_install_ok.txt").unlink(missing_ok=True)
        except OSError:
            pass
        log(f"本地引擎安装或冒烟测试失败：{type(exc).__name__}: {exc}")
        log(traceback.format_exc())
        log("请将 offline_engine_setup.log 复制给开发者；不要只截取最后一行错误。")
        return 1
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(main(arg))

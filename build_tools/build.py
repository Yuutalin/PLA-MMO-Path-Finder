from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

VERSION = "0.7.3"
AUTHOR = "君粒&GPT"
APP_NAME = "PLA MMO Path Finder"
EXE_NAME = f"{APP_NAME}.exe"
INNO_SETUP_URL = "https://jrsoftware.org/download.php/is.exe"
INNO_CHINESE_TRANSLATION_URL = "https://raw.githubusercontent.com/jrsoftware/issrc/refs/heads/main/Files/Languages/ChineseSimplified.isl"

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
WORK_DIR = TOOLS_DIR / ".work"
OUTPUT_DIR = TOOLS_DIR / "output"
REPORTS_DIR = TOOLS_DIR / "reports"
LOG_PATH = REPORTS_DIR / "build.log"
REPORT_PATH = REPORTS_DIR / "build_report.txt"
VENV_DIR = TOOLS_DIR / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"

ENGINE_REQUIRED = (
    Path("offline_engine/pla/checkmmo.py"),
    Path("offline_engine/static/resources/mmo_es.json"),
    Path("offline_engine/static/resources/mmopaths.json"),
    Path("offline_engine/static/resources/nonbonuspaths.json"),
    Path("offline_engine/static/resources/seedhashes.json"),
    Path("offline_engine/static/resources/pokedex.json"),
    Path("offline_engine/static/resources/hisuidex.txt"),
    Path("offline_engine/engine_manifest.json"),
    Path("offline_engine/engine_install_ok.txt"),
    Path("offline_engine/UPSTREAM_LICENSE_GPL-3.0.txt"),
)


def log(message: str = "") -> None:
    print(message, flush=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
    except OSError:
        pass


def run_stream(command: list[str], *, cwd: Path = ROOT, check: bool = False) -> int:
    log("$ " + subprocess.list2cmdline([str(x) for x in command]))
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(
        [str(x) for x in command],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip("\r\n")
        print(line, flush=True)
        try:
            with LOG_PATH.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass
    code = process.wait()
    log(f"[EXIT] {code}")
    if check and code:
        raise RuntimeError(f"命令执行失败，退出代码 {code}。完整输出见 {LOG_PATH}")
    return code


def ensure_python_version() -> None:
    if sys.version_info < (3, 10):
        raise RuntimeError(
            f"当前 Python 为 {sys.version.split()[0]}；构建需要 Python 3.10 或更高版本。"
        )


def is_build_venv() -> bool:
    try:
        return Path(sys.prefix).resolve() == VENV_DIR.resolve()
    except OSError:
        return False


def bootstrap_build_environment() -> int:
    """Create an isolated build venv and install runtime/build dependencies."""
    ensure_python_version()
    if not VENV_PYTHON.is_file():
        if VENV_DIR.exists():
            shutil.rmtree(VENV_DIR, ignore_errors=True)
        log("[SETUP] 创建独立编译环境：build_tools/.venv")
        run_stream([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    requirements = [ROOT / "requirements.txt", TOOLS_DIR / "requirements-build.txt"]
    for path in requirements:
        if not path.is_file():
            raise RuntimeError(f"缺少依赖清单：{path}")
    log("[SETUP] 检查并自动安装缺少的运行／编译依赖。")
    run_stream([
        str(VENV_PYTHON), "-m", "pip", "install", "--disable-pip-version-check",
        "-r", str(requirements[0]), "-r", str(requirements[1]),
    ], check=True)
    return subprocess.call([str(VENV_PYTHON), str(Path(__file__).resolve()), "--in-build-venv"], cwd=str(ROOT))


def _engine_manifest_valid() -> bool:
    manifest_path = ROOT / "offline_engine" / "engine_manifest.json"
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return str(data.get("app_version", "")) == "0.3.6"
    except (OSError, json.JSONDecodeError, AttributeError):
        return False


def ensure_engine_ready() -> None:
    missing = [str(path) for path in ENGINE_REQUIRED if not (ROOT / path).is_file()]
    if missing or not _engine_manifest_valid():
        log("[SETUP] 本地 RNG 引擎资源不完整或版本标记异常，尝试自动准备／修复。")
        log("[SETUP] 这一步可能需要联网下载上游公开源码与数据。")
        prep = ROOT / "tools" / "prepare_offline_engine.py"
        if not prep.is_file():
            raise RuntimeError("本地 RNG 引擎缺少必要文件，且找不到 tools/prepare_offline_engine.py，无法自动修复。")
        run_stream([str(VENV_PYTHON), "-u", str(prep)], check=True)
        missing = [str(path) for path in ENGINE_REQUIRED if not (ROOT / path).is_file()]
        if missing or not _engine_manifest_valid():
            raise RuntimeError("本地 RNG 引擎自动准备后仍不完整：\n" + "\n".join(missing))
    log("[CHECK] 本地 RNG 引擎必需文件与版本标记齐全。")


def check_imports() -> None:
    command = [
        str(VENV_PYTHON), "-c",
        "import flask, usb, z3, webview, PyInstaller, PIL; "
        "print('Flask', flask.__version__ if hasattr(flask, '__version__') else 'installed'); "
        "print('z3-solver', z3.get_version_string()); "
        "print('pywebview', getattr(webview, '__version__', 'installed')); "
        "print('PyInstaller', PyInstaller.__version__); print('Pillow', PIL.__version__)",
    ]
    run_stream(command, check=True)


def required_source_check() -> list[str]:
    required = [
        ROOT / "app.py", ROOT / "requirements.txt", ROOT / "templates" / "index.html",
        ROOT / "static" / "app.js", ROOT / "static" / "result_view.js",
        ROOT / "static" / "style.css", ROOT / "static" / "product.css",
        ROOT / "static" / "themes.css", ROOT / "pla_mmo" / "species_zh.json",
        ROOT / "build_tools" / "installer.iss", ROOT / "build_tools" / "default_app.ico",
    ]
    return [str(path.relative_to(ROOT)) for path in required if not path.is_file()]


def check_environment(repair: bool = True) -> bool:
    log("\n[CHECK] 构建环境与项目文件检查")
    log(f"项目：{ROOT}")
    log(f"版本：{VERSION}；作者：{AUTHOR}")
    log(f"Python：{sys.version.split()[0]}")
    check_imports()
    missing = required_source_check()
    if missing:
        raise RuntimeError("项目文件缺失：\n" + "\n".join(missing))
    if repair:
        ensure_engine_ready()
    else:
        engine_missing = [str(path) for path in ENGINE_REQUIRED if not (ROOT / path).is_file()]
        if engine_missing:
            raise RuntimeError("本地 RNG 引擎缺少：\n" + "\n".join(engine_missing))
    log("[PASS] Python 依赖、项目文件和必要资源检查通过。")
    return True


def run_regression_tests() -> None:
    log("\n[TEST] 运行 Python 自动化回归测试；失败时将停止正式构建。")
    run_stream([str(VENV_PYTHON), "-m", "unittest", "discover", "-s", "tests", "-v"], check=True)
    node = shutil.which("node")
    if node:
        for script in ("static/app.js", "static/result_view.js", "tests/test_result_view.js", "tests/test_research_level_ui.js"):
            command = [node, "--check", script] if script.startswith("static/") else [node, script]
            run_stream(command, check=True)
        log("[PASS] JavaScript 语法与专项测试通过。")
    else:
        log("[WARN] 未安装 Node.js，跳过独立 JavaScript 语法检查；Node.js 不是应用运行依赖。")


def selected_icon() -> Path:
    """Convert build_tools/logo.icon to a Windows ICO; fall back to bundled default."""
    custom = TOOLS_DIR / "logo.icon"
    output = WORK_DIR / "selected_app.ico"
    output.parent.mkdir(parents=True, exist_ok=True)
    if custom.is_file():
        try:
            from PIL import Image
            with Image.open(custom) as source:
                image = source.convert("RGBA")
                image.save(output, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            log(f"[ICON] 使用自定义图标：{custom}")
            return output
        except Exception as exc:
            log(f"[WARN] logo.icon 存在但无法转换（{type(exc).__name__}: {exc}），回退到默认图标。")
    fallback = TOOLS_DIR / "default_app.ico"
    if not fallback.is_file():
        fallback = ROOT / "static" / "app.ico"
    if not fallback.is_file():
        raise RuntimeError("自定义 logo.icon 无效，且默认图标也缺失。")
    shutil.copy2(fallback, output)
    log(f"[ICON] 使用默认图标：{fallback}")
    return output


def _copy_ignore(directory: str, names: list[str]) -> set[str]:
    path = Path(directory)
    ignored = {name for name in names if name in {"__pycache__", ".DS_Store"} or name.endswith((".pyc", ".pyo", ".tmp", ".log"))}
    try:
        relative = path.relative_to(ROOT / "static" / "pokemon")
    except ValueError:
        relative = None
    if relative and relative.parts and relative.parts[0] in {"cache", "custom"}:
        # User artwork is personal/optional and must not be redistributed in a build.
        ignored.update(name for name in names if Path(name).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
    return ignored


def create_source_archive(destination: Path) -> None:
    """Create a clean source archive without build outputs, logs, or user artwork."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_destination = destination.with_suffix(destination.suffix + ".tmp")
    prefix = f"PLA-MMO-Path-Finder-v{VERSION}-source"
    ignored_dirs = {".git", ".venv", ".pytest_cache", "__pycache__", ".work", "output", "dist", "build"}
    ignored_files = {"startup.log", "startup-dev.log", "runtime_errors.log", "offline_engine_setup.log"}
    with zipfile.ZipFile(temp_destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for current, dirs, files in os.walk(ROOT):
            current_path = Path(current)
            dirs[:] = [name for name in dirs if name not in ignored_dirs]
            if current_path == ROOT / "build_tools":
                dirs[:] = [name for name in dirs if name != "reports"]
            if current_path == ROOT / "static" / "pokemon" / "cache" or current_path == ROOT / "static" / "pokemon" / "custom":
                files[:] = [name for name in files if Path(name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}]
            for name in files:
                path = current_path / name
                rel = path.relative_to(ROOT)
                if name in ignored_files or name.endswith((".pyc", ".pyo", ".tmp", ".log")):
                    continue
                if rel.parts and rel.parts[0] == "build_tools" and len(rel.parts) > 1 and rel.parts[1] == "output":
                    continue
                if path.suffix.lower() == ".zip" and rel.parts[0] != "build_tools":
                    continue
                archive.write(path, Path(prefix) / rel)
    temp_destination.replace(destination)
    log(f"[SOURCE] 源码包已生成：{destination}")


def stage_runtime_bundle(icon_path: Path, source_archive: Path) -> Path:
    stage = WORK_DIR / "stage"
    if stage.exists():
        shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True, exist_ok=True)
    for folder in ("static", "templates", "offline_engine"):
        shutil.copytree(ROOT / folder, stage / folder, ignore=_copy_ignore)
    shutil.copy2(icon_path, stage / "static" / "app.ico")
    shutil.copy2(ROOT / "pla_mmo" / "species_zh.json", stage / "species_zh.json")
    # The source code and GPL license travel with the release rather than being
    # hidden inside an executable-only package.
    shutil.copy2(ROOT / "LICENSES.md", stage / "LICENSES.md")
    shutil.copy2(ROOT / "README.md", stage / "README.txt")
    licenses_dir = stage / "licenses"
    licenses_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_archive, licenses_dir / source_archive.name)
    notice = (
        "Source code notice\n"
        f"Author: {AUTHOR}\n"
        f"Version: {VERSION}\n"
        "The corresponding project source is included in this folder. See LICENSES.md and "
        "offline_engine/UPSTREAM_LICENSE_GPL-3.0.txt for applicable third-party notices.\n"
    )
    (licenses_dir / "SOURCE_CODE_NOTICE.txt").write_text(notice, encoding="utf-8")
    return stage


def write_version_info(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers=(0, 7, 1, 0), prodvers=(0, 7, 1, 0), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('080404B0', [
      StringStruct('CompanyName', '{AUTHOR}'),
      StringStruct('FileDescription', 'PLA MMO 闪光路径助手'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', '{APP_NAME}'),
      StringStruct('OriginalFilename', '{EXE_NAME}'),
      StringStruct('ProductName', '{APP_NAME}'),
      StringStruct('ProductVersion', '{VERSION}'),
      StringStruct('LegalCopyright', 'Copyright (C) {AUTHOR}'),
    ])]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
'''
    destination.write_text(content, encoding="utf-8")


def build_pyinstaller(icon_path: Path, stage: Path) -> Path:
    dist_root = WORK_DIR / "dist"
    work_path = WORK_DIR / "pyinstaller-work"
    spec_path = WORK_DIR / "spec"
    for path in (dist_root, work_path, spec_path):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)
    version_info = WORK_DIR / "version_info.txt"
    write_version_info(version_info)
    data_args: list[str] = []
    for source, target in (
        (stage / "static", "static"),
        (stage / "templates", "templates"),
        (stage / "offline_engine", "offline_engine"),
        (stage / "species_zh.json", "pla_mmo"),
        (stage / "LICENSES.md", "."),
        (stage / "README.txt", "."),
        (stage / "licenses", "licenses"),
    ):
        data_args.extend(["--add-data", f"{source};{target}"])
    command = [
        str(VENV_PYTHON), "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", APP_NAME,
        "--contents-directory", ".",
        "--distpath", str(dist_root),
        "--workpath", str(work_path),
        "--specpath", str(spec_path),
        "--icon", str(icon_path),
        "--version-file", str(version_info),
        "--paths", str(ROOT),
        "--collect-all", "z3",
        "--collect-all", "webview",
        "--collect-all", "usb",
        "--collect-submodules", "offline_engine",
        "--collect-submodules", "pla_mmo",
        "--hidden-import", "webview.platforms.edgechromium",
        "--hidden-import", "tkinter.filedialog",
        *data_args,
        str(ROOT / "app.py"),
    ]
    run_stream(command, check=True)
    built_dir = dist_root / APP_NAME
    exe = built_dir / EXE_NAME
    if not exe.is_file():
        raise RuntimeError(f"PyInstaller 未生成预期 EXE：{exe}")
    for required in ("static", "templates", "offline_engine", "licenses", "LICENSES.md", "README.txt"):
        if not (built_dir / required).exists():
            raise RuntimeError(f"编译结果缺少资源：{required}")
    log("[PASS] EXE 与配套资源目录已生成并通过完整性检查。")
    return built_dir


def publish_bundle(built_dir: Path) -> Path:
    portable_root = OUTPUT_DIR / "portable"
    portable_root.mkdir(parents=True, exist_ok=True)
    target = portable_root / APP_NAME
    staged_target = portable_root / f".{APP_NAME}.new"
    backup_target = portable_root / f".{APP_NAME}.previous"
    for path in (staged_target, backup_target):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
    shutil.copytree(built_dir, staged_target)
    if target.exists():
        target.rename(backup_target)
    try:
        staged_target.rename(target)
    except Exception:
        if backup_target.exists() and not target.exists():
            backup_target.rename(target)
        raise
    if backup_target.exists():
        shutil.rmtree(backup_target, ignore_errors=True)
    return target


def zip_directory(source_dir: Path, destination: Path, arc_root: str) -> None:
    temp = destination.with_suffix(destination.suffix + ".tmp")
    with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in source_dir.rglob("*"):
            if path.is_file():
                archive.write(path, Path(arc_root) / path.relative_to(source_dir))
    with zipfile.ZipFile(temp, "r") as archive:
        bad = archive.testzip()
        if bad:
            temp.unlink(missing_ok=True)
            raise RuntimeError(f"ZIP 校验失败：{bad}")
    temp.replace(destination)


def build_portable_package() -> Path:
    icon = selected_icon()
    source_archive_work = WORK_DIR / f"PLA-MMO-Path-Finder-v{VERSION}-source.zip"
    create_source_archive(source_archive_work)
    stage = stage_runtime_bundle(icon, source_archive_work)
    built_dir = build_pyinstaller(icon, stage)
    target = publish_bundle(built_dir)
    output_zip = OUTPUT_DIR / f"PLA-MMO-Path-Finder-v{VERSION}-portable.zip"
    zip_directory(target, output_zip, f"PLA-MMO-Path-Finder-v{VERSION}-portable")
    source_final = OUTPUT_DIR / f"PLA-MMO-Path-Finder-v{VERSION}-source.zip"
    shutil.copy2(source_archive_work, source_final)
    log(f"[SUCCESS] 便携版 ZIP：{output_zip}")
    log(f"[SOURCE] 配套源码 ZIP：{source_final}")
    return target


def find_iscc() -> Path | None:
    candidates: list[Path] = []
    in_path = shutil.which("ISCC.exe") or shutil.which("ISCC")
    if in_path:
        candidates.append(Path(in_path))
    for env_name in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(env_name)
        if base:
            candidates.extend([
                Path(base) / "Inno Setup 6" / "ISCC.exe",
                Path(base) / "Programs" / "Inno Setup 6" / "ISCC.exe",
            ])
    candidates.append(WORK_DIR / "Inno Setup 6" / "ISCC.exe")
    return next((path for path in candidates if path.is_file()), None)


def ensure_inno_setup() -> Path:
    iscc = find_iscc()
    if iscc:
        return iscc
    log("[SETUP] 未找到 Inno Setup 编译器，尝试通过 winget 安装。")
    winget = shutil.which("winget")
    if winget:
        result = subprocess.run([
            winget, "install", "--id", "JRSoftware.InnoSetup", "--exact", "--scope", "user",
            "--accept-package-agreements", "--accept-source-agreements",
        ], cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in (result.stdout or "").splitlines():
            log(line)
        iscc = find_iscc()
        if iscc:
            return iscc
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    installer = WORK_DIR / "innosetup-installer.exe"
    log("[SETUP] winget 未能完成安装；从 Inno Setup 官方网站下载安装程序。")
    request = urllib.request.Request(INNO_SETUP_URL, headers={"User-Agent": f"PLA-MMO-Path-Finder/{VERSION}"})
    with urllib.request.urlopen(request, timeout=90) as response, installer.open("wb") as output:
        shutil.copyfileobj(response, output)
    if not installer.is_file() or installer.stat().st_size < 100_000:
        raise RuntimeError("Inno Setup 官方安装程序下载失败或文件过小。")
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell:
        installer_ps_path = str(installer).replace("'", "''")
        signature_command = (
            f"$s=Get-AuthenticodeSignature -LiteralPath '{installer_ps_path}'; "
            "if ($s.Status -ne 'Valid') { Write-Error ('签名校验失败：' + $s.Status); exit 2 }; "
            "Write-Output $s.SignerCertificate.Subject"
        )
        check = subprocess.run([
            powershell, "-NoProfile", "-Command", signature_command,
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in (check.stdout or "").splitlines():
            log(line)
        if check.returncode:
            raise RuntimeError("Inno Setup 安装程序数字签名验证失败，已停止执行。")
    log("已下载官方 Inno Setup 安装程序。将打开安装向导；安装完成后请返回此窗口继续。")
    subprocess.run([str(installer)], check=False)
    iscc = find_iscc()
    if not iscc:
        raise RuntimeError("Inno Setup 安装后仍找不到 ISCC.exe。请确认安装完成，再重新选择安装版编译。")
    return iscc


def ensure_chinese_language_file(iscc: Path) -> Path | None:
    """Find or download Inno Setup's official Simplified Chinese translation.

    Some Inno Setup installations omit optional translation files. Keep the
    installer build self-healing and use the built-in English messages as a
    last resort rather than aborting the entire build.
    """
    candidates = [
        iscc.parent / "Languages" / "ChineseSimplified.isl",
        TOOLS_DIR / "languages" / "ChineseSimplified.isl",
        WORK_DIR / "languages" / "ChineseSimplified.isl",
    ]
    for candidate in candidates:
        try:
            data = candidate.read_bytes()
        except OSError:
            continue
        if b"[LangOptions]" in data and b"[Messages]" in data and b"LanguageID=$0804" in data:
            log(f"[PASS] 使用简体中文安装语言文件：{candidate}")
            return candidate
        log(f"[WARN] 忽略无效的安装语言文件：{candidate}")

    destination = WORK_DIR / "languages" / "ChineseSimplified.isl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(".isl.download")
    try:
        log("[SETUP] 当前 Inno Setup 缺少简体中文语言文件，尝试下载官方翻译。")
        request = urllib.request.Request(
            INNO_CHINESE_TRANSLATION_URL,
            headers={"User-Agent": f"PLA-MMO-Path-Finder/{VERSION}"},
        )
        with urllib.request.urlopen(request, timeout=30) as response, temp.open("wb") as output:
            shutil.copyfileobj(response, output)
        data = temp.read_bytes()
        if len(data) < 5_000 or b"[LangOptions]" not in data or b"[Messages]" not in data or b"LanguageID=$0804" not in data:
            raise ValueError("下载的语言文件内容不完整或格式不正确。")
        temp.replace(destination)
        log(f"[PASS] 已缓存官方简体中文安装语言文件：{destination}")
        return destination
    except Exception as exc:
        temp.unlink(missing_ok=True)
        log(f"[WARN] 无法获取简体中文安装语言文件：{exc}")
        log("[WARN] 将使用 Inno Setup 内置英文安装界面继续编译，不再因此中断。")
        return None


def build_installer(bundle_dir: Path) -> Path:
    iscc = ensure_inno_setup()
    icon = selected_icon()
    output = OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    script = TOOLS_DIR / "installer.iss"
    language_file = ensure_chinese_language_file(iscc)
    if language_file is None:
        setup_language_file = "compiler:Default.isl"
        setup_language_name = "english"
    else:
        setup_language_file = str(language_file)
        setup_language_name = "chinesesimp"
    command = [
        str(iscc),
        f"/DAppVersion={VERSION}",
        f"/DSourceDir={bundle_dir}",
        f"/DOutputDir={output}",
        f"/DAppIcon={icon}",
        f"/DSetupLanguageFile={setup_language_file}",
        f"/DSetupLanguageName={setup_language_name}",
        str(script),
    ]
    run_stream(command, check=True)
    installer = output / f"PLA-MMO-Path-Finder-v{VERSION}-setup.exe"
    if not installer.is_file() or installer.stat().st_size < 100_000:
        raise RuntimeError(f"安装程序未生成或文件异常：{installer}")
    log(f"[SUCCESS] 安装版：{installer}")
    return installer


def write_report(result: str, output_type: str = "none", notes: Iterable[str] = ()) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    details = [
        f"PLA MMO Path Finder v{VERSION} — Build Report",
        f"Author: {AUTHOR}",
        f"Time: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Platform: {sys.platform}",
        f"Python: {sys.version.replace(chr(10), ' ')}",
        f"Build type: {output_type}",
        f"Result: {result}",
        f"Project root: {ROOT}",
        f"Output directory: {OUTPUT_DIR}",
        "",
        "Notes:",
        *[f"- {note}" for note in notes],
        "",
        f"Log: {LOG_PATH}",
    ]
    REPORT_PATH.write_text("\n".join(details) + "\n", encoding="utf-8")


def clean_build_cache() -> None:
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR, ignore_errors=True)
    log("[CLEAN] 已清理 build_tools/.work 中的临时编译缓存。")
    log("[KEEP] 保留 .venv、release 输出、源码、用户配置与图片资源。")


def open_output_folder() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    os.startfile(str(OUTPUT_DIR))  # type: ignore[attr-defined]


def perform_build(kind: str) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    log("\n" + "=" * 70)
    log(f"开始构建：{kind}；版本 v{VERSION}；作者 {AUTHOR}")
    log("=" * 70)
    try:
        check_environment(repair=True)
        run_regression_tests()
        bundle_dir = build_portable_package()
        if kind in {"installer", "both"}:
            build_installer(bundle_dir)
        write_report("SUCCESS", kind, ["Python regression tests passed.", "Windows GUI runtime still needs a real Windows smoke test."])
        log("\n[PASS] 构建流程完成。")
        log(f"输出目录：{OUTPUT_DIR}")
        log(f"构建报告：{REPORT_PATH}")
    except Exception as exc:
        write_report("FAILED", kind, [f"{type(exc).__name__}: {exc}", "Previous successful output packages are preserved when possible."])
        log(f"\n[ERROR] {type(exc).__name__}: {exc}")
        log(f"完整日志：{LOG_PATH}")
        raise


def menu() -> int:
    while True:
        print("\n" + "=" * 56)
        print(f"{APP_NAME} v{VERSION} · 构建工具")
        print(f"作者：{AUTHOR}")
        print("编译脚本、图标和构建缓存均集中在 build_tools 文件夹。")
        print("普通源码运行无需编译：请使用项目根目录的 start.bat。")
        print("-" * 56)
        print("1. 编译便携版（EXE + 资源目录 + ZIP）")
        print("2. 编译安装版（Setup.exe）")
        print("3. 同时编译便携版和安装版")
        print("4. 检查环境与必要资源（缺失引擎文件会尝试修复）")
        print("5. 清理临时编译缓存（不删除成功产物）")
        print("6. 打开输出目录")
        print("0. 退出")
        choice = input("请选择 [0-6]：").strip()
        try:
            if choice == "1":
                perform_build("portable")
            elif choice == "2":
                perform_build("installer")
            elif choice == "3":
                perform_build("both")
            elif choice == "4":
                check_environment(repair=True)
                write_report("CHECK PASSED", "environment-check", ["Required files and dependencies are available."])
                log("[PASS] 环境检查完成。")
            elif choice == "5":
                clean_build_cache()
            elif choice == "6":
                open_output_folder()
            elif choice == "0":
                return 0
            else:
                print("无效选项，请输入 0–6。")
        except Exception as exc:
            print(f"\n[FAILED] {exc}")
            print(f"请查看完整日志：{LOG_PATH}")
            input("按 Enter 返回菜单……")


def main() -> int:
    if os.name != "nt":
        print("[ERROR] 此构建器用于生成 Windows EXE，请在 Windows 10/11 上运行 build_tools\\build.bat。")
        return 2
    if not is_build_venv():
        try:
            return bootstrap_build_environment()
        except Exception as exc:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            log(f"[ERROR] 无法准备独立构建环境：{type(exc).__name__}: {exc}")
            log(f"日志：{LOG_PATH}")
            return 2
    ensure_python_version()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    log("\n" + "=" * 70)
    log(f"Build tool launched: v{VERSION}; author {AUTHOR}; Python {sys.version.split()[0]}")
    return menu()


if __name__ == "__main__":
    raise SystemExit(main())

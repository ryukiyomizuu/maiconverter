#!/usr/bin/env python3
"""
setup.py — First-time setup for Maimai's AIO Conversion
Run this once before using maimai.py to verify / install all required tools.
"""

import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SETUP_DONE = ROOT / ".setup_done"

# ── colour helpers (no third-party deps) ─────────────────────────────────────

WINDOWS = os.name == "nt"

def _c(code, text):
    if WINDOWS:
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass
    return f"\033[{code}m{text}\033[0m"

OK   = lambda t: _c("32", t)
WARN = lambda t: _c("33", t)
ERR  = lambda t: _c("31", t)
BOLD = lambda t: _c("1",  t)
DIM  = lambda t: _c("2",  t)

# ── tool manifest ─────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "maiforge.exe",
        "label": "maiforge  (database / chart compiler)",
        "candidates": [
            ROOT / "maiforge"            / "maiforge.exe",
            ROOT / "maioconverter-custom" / "dist" / "win-x64" / "maiforge.exe",
        ],
        "auto": False,
        "note": "Already bundled in the maiforge/ folder.",
    },
    {
        "name": "ffmpeg.exe",
        "label": "ffmpeg    (audio / video encoding)",
        "candidates": [ROOT / "ffmpeg" / "ffmpeg.exe"],
        "auto": True,
        "download_url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        "extract": None,   # patched below after function definitions
        "note": "Auto-download from github.com/BtbN/FFmpeg-Builds",
    },
    {
        "name": "vgmstream-cli.exe",
        "label": "vgmstream (audio stream decoding)",
        "candidates": [ROOT / "vgmstream-win64" / "vgmstream-cli.exe"],
        "auto": True,
        "download_url": "https://github.com/vgmstream/vgmstream/releases/latest/download/vgmstream-win.zip",
        "extract": None,   # patched below after function definitions
        "note": "Auto-download from github.com/vgmstream/vgmstream",
    },
    {
        "name": "flac.exe",
        "label": "flac      (lossless audio encoder)",
        "candidates": [ROOT / "flac" / "flac.exe"],
        "auto": False,
        "note": (
            "Download from https://github.com/xiph/flac/releases\n"
            "              Place flac.exe inside the  flac/  folder."
        ),
    },
    {
        "name": "crid_mod.exe",
        "label": "crid      (USM video decrypter)",
        "candidates": [
            ROOT / "crid" / "crid_mod.exe",
            ROOT / "crid" / "crid.exe",
        ],
        "auto": False,
        "note": (
            "Download from https://github.com/kokarare1212/CRID-usm-Decrypter\n"
            "              Place crid_mod.exe (or crid.exe) inside the  crid/  folder."
        ),
    },
    {
        "name": "AssetStudio.CLI.exe",
        "label": "AssetStudio CLI (Unity asset extractor)",
        "candidates": [ROOT / "assetstudiocli" / "AssetStudio.CLI.exe"],
        "auto": False,
        "note": (
            "Download from https://github.com/Perfare/AssetStudio\n"
            "              Place AssetStudio.CLI.exe inside the  assetstudiocli/  folder."
        ),
    },
]

# ── extract helpers (referenced above) ───────────────────────────────────────

def _ffmpeg_extract(zip_path: Path):
    dest = ROOT / "ffmpeg"
    dest.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            fname = Path(member).name
            if fname in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe") and "/bin/" in member:
                data = zf.read(member)
                (dest / fname).write_bytes(data)
                print(f"    extracted {fname}")


def _vgmstream_extract(zip_path: Path):
    dest = ROOT / "vgmstream-win64"
    dest.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            fname = Path(member).name
            if fname.endswith(".exe") or fname.endswith(".dll"):
                data = zf.read(member)
                (dest / fname).write_bytes(data)
        print(f"    extracted to vgmstream-win64/")


# patch the forward references now that functions are defined
TOOLS[1]["extract"] = _ffmpeg_extract
TOOLS[2]["extract"] = _vgmstream_extract

# ── helpers ───────────────────────────────────────────────────────────────────

def find_tool(tool: dict) -> Path | None:
    for c in tool["candidates"]:
        if c.is_file():
            return c
    return None


def download_with_progress(url: str, dest: Path):
    print(f"  Downloading {url}")
    def _reporthook(count, block_size, total):
        if total <= 0:
            return
        pct = min(int(count * block_size * 100 / total), 100)
        bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
        print(f"\r    [{bar}] {pct:3d}%", end="", flush=True)
    urllib.request.urlretrieve(url, dest, reporthook=_reporthook)
    print()  # newline after bar


def try_auto_install(tool: dict) -> bool:
    tmp = ROOT / f"_setup_tmp_{tool['name']}.zip"
    try:
        download_with_progress(tool["download_url"], tmp)
        tool["extract"](tmp)
        return True
    except Exception as e:
        print(ERR(f"    Download failed: {e}"))
        return False
    finally:
        if tmp.exists():
            tmp.unlink()


def check_python():
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 10):
        print(ERR(f"  Python {major}.{minor} detected — Python 3.10+ is required."))
        print(WARN("  Please upgrade: https://www.python.org/downloads/"))
        return False
    print(OK(f"  Python {major}.{minor} ✓"))
    return True


# ── Config helpers ────────────────────────────────────────────────────────────

CONFIG_FILE = ROOT / "config.json"

def _load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {}

def _save_config(data: dict):
    existing = _load_config()
    existing.update(data)
    CONFIG_FILE.write_text(json.dumps(existing, indent=2))


_GPU_ENCODER_OPTIONS = [
    ("auto",        "Auto-detect (recommended)"),
    ("hevc_nvenc",  "NVIDIA — H.265 (hevc_nvenc)"),
    ("h264_nvenc",  "NVIDIA — H.264 (h264_nvenc)"),
    ("hevc_amf",    "AMD    — H.265 (hevc_amf)"),
    ("h264_amf",    "AMD    — H.264 (h264_amf)"),
    ("libx265",     "Software — H.265 (libx265)"),
    ("libx264",     "Software — H.264 (libx264)"),
]

def _configure_video_encoder():
    current = _load_config().get("video_encoder", "auto")
    current_label = next((l for k, l in _GPU_ENCODER_OPTIONS if k == current), current)
    print(f"  Current: {current_label}")
    print()
    ans = input("  Override encoder? (y/n, Enter = keep current): ").strip().lower()
    if ans != "y":
        print(DIM("  Keeping current setting."))
        return

    print()
    for i, (key, label) in enumerate(_GPU_ENCODER_OPTIONS):
        print(f"  [{i}] {label}")
    print()
    choice = input("  Select encoder [0]: ").strip()
    try:
        idx = int(choice) if choice else 0
        key, label = _GPU_ENCODER_OPTIONS[idx]
        _save_config({"video_encoder": key})
        print(OK(f"  ✓ Video encoder set to: {label}"))
    except (ValueError, IndexError):
        print(WARN("  Invalid choice — keeping current setting."))


# ── Runtime requirement checks ────────────────────────────────────────────────

# Each entry describes one required C/C++/.NET system runtime.
RUNTIME_REQUIREMENTS = [
    {
        "id":            "dotnet8",
        "label":         ".NET 8.0 Runtime (x64)",
        "required_by":   "AssetStudio.CLI.exe",
        "check":         "dotnet",          # handler key
        "major":         8,
        "installer_url":  "https://aka.ms/dotnet/8.0/dotnet-runtime-win-x64.exe",
        "installer_name": "dotnet-runtime-8.0-win-x64.exe",
        "installer_args": ["/install", "/quiet", "/norestart"],
        "info_url":       "https://dotnet.microsoft.com/en-us/download/dotnet/8.0",
        "auto":           True,
    },
    {
        "id":            "vcredist2022",
        "label":         "Visual C++ 2015–2022 Redistributable (x64)",
        "required_by":   "AssetStudio.CLI.exe, vgmstream-cli.exe",
        "check":         "vcredist",        # handler key
        "registry_keys": [
            r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
            r"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
        ],
        "installer_url":  "https://aka.ms/vs/17/release/vc_redist.x64.exe",
        "installer_name": "vc_redist.x64.exe",
        "installer_args": ["/install", "/quiet", "/norestart"],
        "info_url":       "https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist",
        "auto":           True,
    },
]


# ── per-type detection helpers ────────────────────────────────────────────────

def _get_installed_dotnet_versions() -> list[str]:
    """Return installed Microsoft.NETCore.App version strings via CLI or filesystem."""
    versions = []
    try:
        result = subprocess.run(
            ["dotnet", "--list-runtimes"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.splitlines():
            if line.startswith("Microsoft.NETCore.App"):
                parts = line.split()
                if len(parts) >= 2:
                    versions.append(parts[1])
        if versions:
            return versions
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Fallback: filesystem scan (runtime-only installs without dotnet CLI)
    for base in [
        Path(os.environ.get("ProgramFiles",      r"C:\Program Files"))       / "dotnet" / "shared" / "Microsoft.NETCore.App",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "dotnet" / "shared" / "Microsoft.NETCore.App",
    ]:
        if base.is_dir():
            for entry in base.iterdir():
                if entry.is_dir() and entry.name[0].isdigit():
                    versions.append(entry.name)
    return versions


def _dotnet_runtime_ok(req: dict) -> str | None:
    """Returns found version string or None."""
    installed = _get_installed_dotnet_versions()
    for v in installed:
        try:
            if int(v.split(".")[0]) == req["major"]:
                return v
        except ValueError:
            pass
    return None


def _vcredist_ok(req: dict) -> str | None:
    """Returns version string from registry, or None if not found."""
    if not WINDOWS:
        return None
    try:
        import winreg
        for key_path in req["registry_keys"]:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
                    installed, _ = winreg.QueryValueEx(k, "Installed")
                    if installed == 1:
                        try:
                            version, _ = winreg.QueryValueEx(k, "Version")
                        except OSError:
                            version = "installed"
                        return version
            except OSError:
                continue
    except ImportError:
        pass
    return None


def _runtime_is_installed(req: dict) -> str | None:
    """Dispatch to the right checker. Returns version string or None."""
    if req["check"] == "dotnet":
        return _dotnet_runtime_ok(req)
    if req["check"] == "vcredist":
        return _vcredist_ok(req)
    return None


def _run_installer(req: dict) -> bool:
    """Download installer to a temp file and run it silently."""
    tmp = ROOT / req["installer_name"]
    try:
        download_with_progress(req["installer_url"], tmp)
        print(f"  Running installer (a UAC prompt may appear)...")
        result = subprocess.run(
            [str(tmp)] + req["installer_args"],
            timeout=300
        )
        return result.returncode in (0, 3010)   # 3010 = reboot suggested but success
    except Exception as e:
        print(ERR(f"    Installer error: {e}"))
        return False
    finally:
        if tmp.exists():
            tmp.unlink()


# ── public interface called from run_setup() ─────────────────────────────────

def check_and_install_runtimes() -> list[str]:
    """
    Check every entry in RUNTIME_REQUIREMENTS.
    Prints status for all. Offers auto-install for missing ones.
    Returns list of IDs still missing after the function returns.
    """
    print(BOLD("[ System Runtimes ]"))

    missing = []
    for req in RUNTIME_REQUIREMENTS:
        found = _runtime_is_installed(req)
        if found:
            print(OK(f"  ✓ {req['label']}"))
            print(DIM(f"      version: {found}  |  required by: {req['required_by']}"))
        else:
            print(ERR(f"  ✗ {req['label']}"))
            print(DIM(f"      required by: {req['required_by']}"))
            missing.append(req)
    print()

    if not missing:
        return []

    auto   = [r for r in missing if r["auto"]]
    manual = [r for r in missing if not r["auto"]]

    still_missing_ids = [r["id"] for r in manual]
    for req in manual:
        print(WARN(f"  ! {req['label']}  →  install manually: {req['info_url']}"))

    if auto:
        ans = input(
            f"  {len(auto)} runtime(s) can be installed automatically. Proceed? (y/n): "
        ).strip().lower()
        print()
        if ans == "y":
            for req in auto:
                print(f"\n  Installing {req['label']} ...")
                ok = _run_installer(req)
                if ok and _runtime_is_installed(req):
                    print(OK(f"  ✓ {req['label']} installed."))
                else:
                    print(ERR(f"  ✗ {req['label']} install failed."))
                    print(WARN(f"    Install manually: {req['info_url']}"))
                    still_missing_ids.append(req["id"])
        else:
            for req in auto:
                print(WARN(f"  Install manually: {req['info_url']}"))
                still_missing_ids.append(req["id"])
        print()

    return still_missing_ids


# ── main ──────────────────────────────────────────────────────────────────────

def run_setup(force=False):
    print()
    print(BOLD("━" * 58))
    print(BOLD("  Maimai's AIO Conversion — First-time Setup"))
    print(BOLD("━" * 58))
    print()

    # ── Python version ────────────────────────────────────────
    print(BOLD("[ Python ]"))
    py_ok = check_python()
    print()

    # ── Runtimes (VC++, .NET, etc.) ───────────────────────────
    print(BOLD("[ Runtimes ]"))
    missing_runtimes = check_and_install_runtimes()

    # ── Tools ─────────────────────────────────────────────────
    print(BOLD("[ Tools ]"))
    missing = []
    for tool in TOOLS:
        found = find_tool(tool)
        if found:
            print(f"  {OK('✓')} {tool['label']}")
            print(DIM(f"      {found}"))
        else:
            print(f"  {ERR('✗')} {tool['label']}")
            missing.append(tool)
    print()

    if not missing:
        print(OK("  All tools are present!"))
    else:
        # separate auto-installable from manual
        auto_tools   = [t for t in missing if t["auto"]]
        manual_tools = [t for t in missing if not t["auto"]]

        if auto_tools:
            print(BOLD("[ Auto-install ]"))
            ans = input(
                f"  {len(auto_tools)} tool(s) can be downloaded automatically. Proceed? (y/n): "
            ).strip().lower()
            if ans == "y":
                for tool in auto_tools:
                    print(f"\n  Installing {tool['label']} ...")
                    ok = try_auto_install(tool)
                    if ok and find_tool(tool):
                        print(OK(f"  ✓ {tool['name']} installed."))
                        missing.remove(tool)
                    else:
                        print(ERR(f"  ✗ {tool['name']} install failed — see note below."))
            print()

        still_missing = [t for t in missing if not find_tool(t)]
        if still_missing:
            print(BOLD("[ Manual steps required ]"))
            for tool in still_missing:
                print(f"\n  {WARN('!')} {tool['label']}")
                for line in tool["note"].split("\n"):
                    print(f"      {line}")
            print()

    # ── Video encoder config ──────────────────────────────────
    print(BOLD("[ Video Encoder ]"))
    _configure_video_encoder()
    print()

    # ── Write .setup_done ────────────────────────────────────
    remaining = [t for t in TOOLS if not find_tool(t)]
    state = {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "missing_tools": [t["name"] for t in remaining],
        "missing_runtimes": missing_runtimes,
        "complete": len(remaining) == 0 and len(missing_runtimes) == 0,
    }
    SETUP_DONE.write_text(json.dumps(state, indent=2))

    if state["complete"]:
        print(OK("  Setup complete! You can now run:  python maimai.py"))
    else:
        issues = len(remaining) + len(missing_runtimes)
        print(WARN(f"  Setup done with {issues} item(s) still missing."))
        print(WARN("  Those modes will ask you for the tool path when you first use them."))

    print()


def is_setup_done() -> bool:
    """Returns True if setup was previously completed successfully."""
    if not SETUP_DONE.exists():
        return False
    try:
        state = json.loads(SETUP_DONE.read_text())
        return state.get("complete", False)
    except Exception:
        return False


def nudge_if_needed():
    """
    Called from maimai.py on startup.
    Prints a warning if setup has never been run, or if items were left missing.
    """
    if not SETUP_DONE.exists():
        print(WARN("  ⚠  First time? Run  python setup.py  to check / install tools."))
        print()
        return

    try:
        state = json.loads(SETUP_DONE.read_text())
    except Exception:
        return

    missing_tools    = state.get("missing_tools",    [])
    missing_runtimes = state.get("missing_runtimes", [])

    if missing_tools or missing_runtimes:
        print(WARN("  ⚠  Some requirements are still missing:"))
        for t in missing_tools:
            print(WARN(f"       ✗ {t}"))
        for r in missing_runtimes:
            print(WARN(f"       ✗ {r}"))
        print(WARN("     Run  python setup.py  to resolve them."))
        print()


if __name__ == "__main__":
    force = "--force" in sys.argv
    if not force and is_setup_done():
        print()
        print(OK("  Setup was already completed."))
        print(DIM("  Run  python setup.py --force  to run it again."))
        print()
        sys.exit(0)
    run_setup(force=force)

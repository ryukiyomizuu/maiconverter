import os
import sys
import time
import re
import json
import argparse
import subprocess
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

from converters.flac import (
    build_flac_encode_command as conv_build_flac_encode_command,
    build_flac_output_path as conv_build_flac_output_path,
)
from converters.image import (
    build_assetstudio_command as conv_build_assetstudio_command,
    flatten_assetstudio_texture2d_output as conv_flatten_assetstudio_texture2d_output,
    move_image_files_to_root as conv_move_image_files_to_root,
)
from converters.mp3 import (
    build_ffmpeg_mp3_command as conv_build_ffmpeg_mp3_command,
    build_mp3_output_path as conv_build_mp3_output_path,
    build_temp_wav_path as conv_build_temp_wav_path,
    build_vgmstream_wav_command as conv_build_vgmstream_wav_command,
)
from converters.mp4 import (
    ENCODER_PROFILES as mp4_ENCODER_PROFILES,
    build_crid_command as conv_build_crid_command,
    build_ffmpeg_mp4_command as conv_build_ffmpeg_mp4_command,
    build_ffmpeg_static_stretch_command as conv_build_ffmpeg_static_stretch_command,
    build_mp4_output_path as conv_build_mp4_output_path,
    find_extracted_m2v_for_dat as conv_find_extracted_m2v_for_dat,
    get_active_encoder_label as conv_get_active_encoder_label,
    get_audio_duration as conv_get_audio_duration,
    is_static_video as conv_is_static_video,
    load_config as mp4_load_config,
    save_config as mp4_save_config,
)
from tools.parser import (
    build_numeric_file_index as parser_build_numeric_file_index,
    choose_best_numeric_match as parser_choose_best_numeric_match,
    parse_music_xml_basic as parser_parse_music_xml_basic,
    resolve_awb_for_song as parser_resolve_awb_for_song,
    resolve_dat_for_song as parser_resolve_dat_for_song,
)
from tools.tools import (
    cleanup_relevant_image_outputs as tools_cleanup_relevant_image_outputs,
    cleanup_temp_video_files as tools_cleanup_temp_video_files,
    count_existing_files_with_ext as tools_count_existing_files_with_ext,
    list_files_with_ext as tools_list_files_with_ext,
    run_subprocess_safe as tools_run_subprocess_safe,
    run_crid_safe as tools_run_crid_safe,
    safe_delete as tools_safe_delete,
    safe_rmtree as tools_safe_rmtree,
)

# =========================================================
# CONFIG
# =========================================================

APP_TITLE = "Maimai's AIO Conversion"
APP_SUBTITLE = "Created by Ryuki (Thanks CGPT also <3)"

SCRIPT_ROOT = Path(__file__).resolve().parent
SUBSCRIPTS_DIR = SCRIPT_ROOT / "subscripts"

TOOL_CANDIDATES = {
    "vgmstream-cli.exe": [
        SCRIPT_ROOT / "vgmstream-win64" / "vgmstream-cli.exe",
        SCRIPT_ROOT / "vgmstream-cli.exe",
    ],
    "crid_mod.exe": [
        SCRIPT_ROOT / "crid" / "crid_mod.exe",
        SCRIPT_ROOT / "crid" / "crid.exe",
        SCRIPT_ROOT / "crid_mod.exe",
        SCRIPT_ROOT / "crid.exe",
    ],
    "ffmpeg.exe": [
        SCRIPT_ROOT / "ffmpeg" / "ffmpeg.exe",
        SCRIPT_ROOT / "ffmpeg.exe",
    ],
    "ffprobe.exe": [
        SCRIPT_ROOT / "ffmpeg" / "ffprobe.exe",
        SCRIPT_ROOT / "ffprobe.exe",
    ],
    "flac.exe": [
        SCRIPT_ROOT / "flac" / "flac.exe",
        SCRIPT_ROOT / "flac.exe",
    ],
    "maiforge.exe": [
        SCRIPT_ROOT / "maioconverter-custom" / "dist" / "win-x64" / "maiforge.exe",
        SCRIPT_ROOT / "maiforge" / "maiforge.exe",
        SCRIPT_ROOT / "maiforge.exe",
    ],
    "AssetStudio.CLI.exe": [
        SCRIPT_ROOT / "assetstudiocli" / "AssetStudio.CLI.exe",
        SCRIPT_ROOT / "AssetStudio.CLI.exe",
        Path(r"C:\Users\Jen\Downloads\Maimai\MAS\assetstudiocli\AssetStudio.CLI.exe"),
    ],
}

TOOL_PATHS = {}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tga", ".webp"}
AXXX_FOLDER_PATTERN = re.compile(r"^[A-Z]\d{3}$", re.IGNORECASE)
PRESETS_FILE   = SCRIPT_ROOT / ".db_presets.json"
SETTINGS_FILE  = SCRIPT_ROOT / ".mas_settings.json"

# =========================================================
# PLATFORM HELPERS
# =========================================================

WINDOWS = os.name == "nt"
CLI_MODE = False
NO_HEADER = False
QUIET_MODE = False
JSON_SUMMARY = False

if WINDOWS:
    import msvcrt


def clear_screen():
    if CLI_MODE:
        return
    os.system("cls" if WINDOWS else "clear")


def wait_enter(message="Press Enter to continue..."):
    if CLI_MODE:
        return
    input(f"\n{message}")


def countdown_with_skip(seconds=10):
    if CLI_MODE:
        return

    lines = [
        "Tools used for this script:",
        "vgmstream (https://github.com/vgmstream/vgmstream)",
        "crid (https://github.com/kokarare1212/CRID-usm-Decrypter)",
        "ffmpeg (https://www.ffmpeg.org/)",
        "MaiChartConverter (https://github.com/Neskol/MaichartConverter)",
        "AssetStudioCLI (https://github.com/Perfare/AssetStudio)",
        "",
        "Shout out to these dudes! If you wanna skip the countdown, press any key to continue.",
    ]

    if WINDOWS:
        for remaining in range(seconds, 0, -1):
            clear_screen()
            print(f"Starting in {remaining}...\n")
            for line in lines:
                print(line)

            start = time.time()
            while time.time() - start < 1:
                if msvcrt.kbhit():
                    msvcrt.getch()
                    clear_screen()
                    return
                time.sleep(0.05)
    else:
        for remaining in range(seconds, 0, -1):
            clear_screen()
            print(f"Starting in {remaining}...\n")
            for line in lines:
                print(line)
            time.sleep(1)

    clear_screen()

def countdown_between_batches(seconds=10, completed_label=None):
    if CLI_MODE or seconds <= 0:
        return

    header = "Next batch starts in"
    if completed_label:
        header = f"{completed_label} done. Next batch starts in"

    if WINDOWS:
        for remaining in range(seconds, 0, -1):
            clear_screen()
            show_header()
            print(f"{header} {remaining}...\n")
            print("Press any key to skip.")
            start = time.time()
            while time.time() - start < 1:
                if msvcrt.kbhit():
                    msvcrt.getch()
                    clear_screen()
                    return
                time.sleep(0.05)
    else:
        for remaining in range(seconds, 0, -1):
            clear_screen()
            show_header()
            print(f"{header} {remaining}...\n")
            time.sleep(1)

    clear_screen()


def countdown_after_conversion(seconds=5, label=None):
    """Short countdown shown after a conversion finishes before proceeding."""
    if CLI_MODE:
        return

    msg = label or "Continuing"

    if WINDOWS:
        for remaining in range(seconds, 0, -1):
            sys.stdout.write(f"\r  {msg} in {remaining}s...  Press any key to skip.")
            sys.stdout.flush()
            start = time.time()
            while time.time() - start < 1:
                if msvcrt.kbhit():
                    msvcrt.getch()
                    sys.stdout.write("\r" + " " * 60 + "\r")
                    sys.stdout.flush()
                    return
                time.sleep(0.05)
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()
    else:
        for remaining in range(seconds, 0, -1):
            sys.stdout.write(f"\r  {msg} in {remaining}s...")
            sys.stdout.flush()
            time.sleep(1)
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()


def run_subprocess_safe(cmd, cwd=None):
    return tools_run_subprocess_safe(cmd, cwd)


def run_crid_safe(cmd, cwd=None):
    return tools_run_crid_safe(cmd, cwd)


def _run_with_spinner(fn, message="Working"):
    """Run fn() in a background thread while animating a spinner on stdout. Returns fn's result."""
    result_box = [None]
    exc_box = [None]
    done = threading.Event()

    def _worker():
        try:
            result_box[0] = fn()
        except Exception as exc:
            exc_box[0] = exc
        finally:
            done.set()

    threading.Thread(target=_worker, daemon=True).start()
    frames = "|/-\\"
    i = 0
    while not done.wait(0.12):
        sys.stdout.write(f"\r{message} {frames[i % len(frames)]}")
        sys.stdout.flush()
        i += 1
    sys.stdout.write(f"\r{message} done    \n")
    sys.stdout.flush()
    if exc_box[0] is not None:
        raise exc_box[0]
    return result_box[0]


# =========================================================
# PROGRESS / NOTIFY HELPERS
# =========================================================

def _fmt_duration(secs: float) -> str:
    secs = max(0, int(secs))
    m, s = divmod(secs, 60)
    return f"{m:02d}:{s:02d}"


def _print_progress(idx: int, total: int, label: str, start_time: float):
    """Overwrite the current line with a progress bar + ETA. Call per file in mode '1'."""
    elapsed = time.time() - start_time
    if idx > 1 and elapsed > 0:
        avg = elapsed / (idx - 1)
        eta_str = _fmt_duration(avg * (total - idx + 1))
    else:
        eta_str = "--:--"
    bar_done = int(20 * idx / total) if total else 0
    bar = "\u2588" * bar_done + "\u2591" * (20 - bar_done)
    short = label if len(label) <= 35 else "..." + label[-32:]
    sys.stdout.write(
        f"\r[{idx:{len(str(total))}}/{total}] {bar} {short:<35} | "
        f"{_fmt_duration(elapsed)} elapsed | ETA {eta_str}   "
    )
    sys.stdout.flush()


def _end_progress(total: int):
    """Print a final newline to end the progress bar."""
    sys.stdout.write(f"\r{'All done':<80}\n")
    sys.stdout.flush()


def _ask_with_hint(prompt: str, hint: str = "") -> str:
    """
    Input line that fills `hint` when the user presses Tab or → (right arrow).
    Falls back to plain input() on non-Windows or when there is no hint.
    """
    if not WINDOWS or not hint:
        full_prompt = f"{prompt}[→/Tab: {hint}] " if hint else prompt
        return input(full_prompt).strip().strip('"')
    import msvcrt as _msvcrt
    hint_note = f" [→ or Tab fills last: {hint}]"
    sys.stdout.write(prompt + hint_note + "\n> ")
    sys.stdout.flush()
    buf: list = []
    while True:
        ch = _msvcrt.getwch()
        if ch in ('\r', '\n'):
            sys.stdout.write('\n')
            sys.stdout.flush()
            result = ''.join(buf).strip().strip('"')
            return result if result else hint
        elif ch == '\b':
            if buf:
                buf.pop()
                sys.stdout.write('\b \b')
                sys.stdout.flush()
        elif ch in ('\t', '\xe0', '\x00'):
            if ch in ('\xe0', '\x00'):
                ch2 = _msvcrt.getwch()
                if ch2 != 'M':
                    continue
            # fill hint
            sys.stdout.write('\b \b' * len(buf))
            sys.stdout.write(hint)
            sys.stdout.flush()
            buf = list(hint)
        elif ch == '\x03':
            raise KeyboardInterrupt
        elif ord(ch) >= 32:
            buf.append(ch)
            sys.stdout.write(ch)
            sys.stdout.flush()


def _notify_done(title: str = "maiconv", message: str = "Conversion complete!"):
    """Beep and show a Windows balloon-tip notification (best-effort)."""
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONINFORMATION)
    except Exception:
        pass
    try:
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$n = New-Object System.Windows.Forms.NotifyIcon; "
            "$n.Icon = [System.Drawing.SystemIcons]::Information; "
            "$n.Visible = $true; "
            f"$n.ShowBalloonTip(4000,'{title}','{message}',"
            "[System.Windows.Forms.ToolTipIcon]::Info); "
            "Start-Sleep -Milliseconds 4500; $n.Dispose()"
        )
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000 if WINDOWS else 0,
        )
    except Exception:
        pass


def _open_in_explorer(path: Path):
    """Open a folder in Windows Explorer."""
    try:
        subprocess.Popen(["explorer", str(path)])
    except Exception:
        pass


def _write_summary_log(log_path: Path, success: int, missing: int, failed: int,
                        elapsed: float, start_ts: float) -> Path:
    """Write a *_summary.txt alongside the main log."""
    import datetime
    summary_path = log_path.with_name(log_path.stem + "_summary.txt")
    started = datetime.datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "=" * 60,
        "CONVERSION SUMMARY",
        "=" * 60,
        f"Started   : {started}",
        f"Duration  : {_fmt_duration(elapsed)} ({elapsed:.1f}s)",
        "-" * 60,
        f"Success   : {success}",
        f"Missing   : {missing}",
        f"Failed    : {failed}",
        f"Total     : {success + missing + failed}",
        "=" * 60,
    ]
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass
    return summary_path


# =========================================================
# BASIC HELPERS
# =========================================================

def cli_print(*args, **kwargs):
    if CLI_MODE and QUIET_MODE:
        return
    print(*args, **kwargs)


def show_header():
    if CLI_MODE and (NO_HEADER or QUIET_MODE):
        return
    print(APP_TITLE)
    print(APP_SUBTITLE)
    print()


def ask_choice(prompt, valid_choices):
    while True:
        choice = input(prompt).strip()
        if choice in valid_choices:
            return choice
        print("Invalid choice.")


def ask_yes_no(prompt):
    while True:
        value = input(prompt).strip().lower()
        if value in ("y", "n"):
            return value == "y"
        print("Please enter y or n.")


def ask_existing_file(prompt):
    while True:
        raw = input(prompt).strip().strip('"')
        p = Path(raw)
        if p.exists() and p.is_file():
            return p
        print("File not found or not a file.")


def ask_existing_dir(prompt):
    while True:
        raw = input(prompt).strip().strip('"')
        p = Path(raw)
        if p.exists() and p.is_dir():
            return p
        print("Folder not found or not a folder.")


def ask_optional_existing_dir(prompt):
    while True:
        raw = input(prompt).strip().strip('"')
        if raw == "":
            return None
        p = Path(raw)
        if p.exists() and p.is_dir():
            return p
        print("Folder not found or not a folder. Leave blank if not applied.")


def ask_output_dir(prompt):
    settings = load_settings()
    last = settings.get("last_output_dir", "")
    display_prompt = f"{prompt}[last: {last}] " if last else prompt
    while True:
        raw = input(display_prompt).strip().strip('"')
        if not raw and last:
            raw = last
        p = Path(raw)
        if p.exists():
            if p.is_dir():
                update_setting("last_output_dir", str(p))
                return p
            print("Path exists but is not a folder.")
            continue
        try:
            p.mkdir(parents=True, exist_ok=True)
            update_setting("last_output_dir", str(p))
            return p
        except Exception as e:
            print(f"Could not create output folder: {e}")


def ask_axxx_or_batch(prompt):
    while True:
        p = ask_existing_dir(prompt)
        detection = detect_axxx_input(p)
        if detection:
            return detection
        print("Not an AXXX folder or a folder containing AXXX folders (e.g., A001, M100).")


def safe_delete(path: Path):
    return tools_safe_delete(path)


def safe_rmtree(path: Path):
    return tools_safe_rmtree(path)


def cleanup_temp_video_files(*paths: Path):
    return tools_cleanup_temp_video_files(*paths)


def _handle_temp_cleanup(path: Path, policy: str, deferred: list):
    """Delete a temp file according to the cleanup policy.
    auto  — delete immediately (current default behaviour)
    keep  — do nothing; leave the file on disk
    batch — queue for deletion at the end of the whole run
    """
    if policy == "auto":
        safe_delete(path)
    elif policy == "batch" and path is not None and path not in deferred:
        deferred.append(path)




def safe_int(value):
    try:
        return int(str(value).strip())
    except Exception:
        return None


def get_xml_child_text(elem, path, default=""):
    node = elem.find(path)
    if node is None or node.text is None:
        return default
    return node.text.strip()


def list_files_with_ext(path: Path, ext: str):
    return tools_list_files_with_ext(path, ext)


def count_existing_files_with_ext(folder: Path, ext: str):
    return tools_count_existing_files_with_ext(folder, ext)


def output_folder_has_any_files(folder: Path):
    if not folder.exists() or not folder.is_dir():
        return False
    return any(p.is_file() for p in folder.rglob("*"))


def output_folder_has_relevant_image_outputs(folder: Path):
    if not folder.exists() or not folder.is_dir():
        return False

    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            return True

    return False


def has_existing_files_with_ext(folder: Path, exts):
    if not folder.exists() or not folder.is_dir():
        return False

    wanted = {e.lower() for e in exts}
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in wanted:
            return True
    return False


def remove_empty_parent_dirs(paths, stop_root: Path):
    stop_root = stop_root.resolve()
    parents = set()

    for p in paths:
        try:
            current = p.parent.resolve()
            while current != stop_root and str(current).startswith(str(stop_root)):
                parents.add(current)
                current = current.parent.resolve()
        except Exception:
            continue

    for d in sorted(parents, key=lambda x: len(x.parts), reverse=True):
        try:
            if d.exists() and d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except Exception:
            pass


def cleanup_relevant_image_outputs(folder: Path):
    return tools_cleanup_relevant_image_outputs(folder)


def clear_folder_contents(folder: Path):
    if not folder.exists() or not folder.is_dir():
        return

    for child in folder.iterdir():
        if child.is_file():
            safe_delete(child)
        elif child.is_dir():
            safe_rmtree(child)


def should_process_output(output_file: Path, policy: str, log_lines=None):
    if not output_file.exists():
        return True

    if policy == "skip":
        if log_lines is not None:
            log_lines.append("=" * 80)
            log_lines.append(f"[SKIPPED] {output_file}")
            log_lines.append("DETAIL: Existing output kept.")
        return False

    if policy == "overwrite":
        safe_delete(output_file)
        return True

    return False

def output_folder_has_relevant_database_outputs(folder: Path):
    if not folder.exists() or not folder.is_dir():
        return False

    ignored_names = {"log.txt"}
    relevant_exts = {".txt", ".mp3", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".mp4", ".zip", ".json"}

    for p in folder.rglob("*"):
        if not p.is_file():
            continue

        if p.name.lower() in ignored_names:
            continue

        if p.suffix.lower() in relevant_exts:
            return True

    return False


def is_axxx_folder_name(name: str):
    return AXXX_FOLDER_PATTERN.match(name) is not None


def is_axxx_folder(path: Path):
    return path.exists() and path.is_dir() and is_axxx_folder_name(path.name)


def find_axxx_folders(root: Path):
    if not root.exists() or not root.is_dir():
        return []
    candidates = [p for p in root.iterdir() if p.is_dir() and is_axxx_folder_name(p.name)]
    return sorted(candidates, key=lambda p: p.name.lower())


def detect_axxx_input(path: Path):
    if is_axxx_folder(path):
        return {"mode_type": "single", "axxx_path": path, "axxx_paths": [path], "batch_root": None}

    candidates = find_axxx_folders(path)
    if candidates:
        return {"mode_type": "batch", "axxx_path": None, "axxx_paths": candidates, "batch_root": path}

    return None


def format_axxx_list(axxx_paths, limit=8):
    names = [p.name for p in axxx_paths]
    if len(names) <= limit:
        return ", ".join(names)
    extra = len(names) - limit
    return ", ".join(names[:limit]) + f" (+{extra} more)"


def get_existing_auto_assets(axxx_paths, selected_targets):
    existing_music = 0
    existing_cover = False
    existing_video = 0

    for axxx_root in axxx_paths:
        if "music" in selected_targets:
            existing_music += count_existing_files_with_ext(axxx_root / "musicMP3", ".mp3")
        if "cover" in selected_targets:
            if output_folder_has_relevant_image_outputs(axxx_root / "Jackets"):
                existing_cover = True
        if "video" in selected_targets:
            existing_video += count_existing_files_with_ext(axxx_root / "Movie", ".mp4")

    return existing_music, existing_cover, existing_video


def detect_axxx_temp_assets(axxx_paths: list) -> dict:
    """Scan AXXX folder(s) for pre-generated temp asset directories.
    
    Returns aggregate counts and per-folder info used for the status display.
    """
    n = len(axxx_paths)
    music_total = 0
    music_folders_with = 0
    music_folders_partial = 0
    cover_folders_with = 0
    cover_folders_partial = 0
    video_total = 0
    video_folders_with = 0
    video_folders_partial = 0
    music_source_count = 0
    cover_source_count = 0
    video_source_count = 0

    for axxx in axxx_paths:
        mp3_count = count_existing_files_with_ext(axxx / "musicMP3", ".mp3")
        awb_count = count_existing_files_with_ext(axxx / "SoundData", ".awb")
        music_complete = mp3_count > 0 and (awb_count == 0 or mp3_count >= awb_count)
        music_partial = mp3_count > 0 and not music_complete
        if music_complete:
            music_total += mp3_count
            music_folders_with += 1
        elif music_partial:
            music_folders_partial += 1

        cover_png_count = len(list((axxx / "Jackets").glob("*.png"))) if (axxx / "Jackets").is_dir() else 0
        ab_count = count_existing_files_with_ext(axxx / "AssetBundleImages" / "jacket", ".ab")
        cover_complete = cover_png_count > 0 and (ab_count == 0 or cover_png_count >= ab_count)
        cover_partial = cover_png_count > 0 and not cover_complete
        if cover_complete:
            cover_folders_with += 1
        elif cover_partial:
            cover_folders_partial += 1

        mp4_count = count_existing_files_with_ext(axxx / "Movie", ".mp4")
        dat_count = count_existing_files_with_ext(axxx / "MovieData", ".dat")
        video_complete = mp4_count > 0 and (dat_count == 0 or mp4_count >= dat_count)
        video_partial = mp4_count > 0 and not video_complete
        if video_complete:
            video_total += mp4_count
            video_folders_with += 1
        elif video_partial:
            video_folders_partial += 1

        if awb_count > 0:
            music_source_count += 1
        if ab_count > 0:
            cover_source_count += 1
        if dat_count > 0:
            video_source_count += 1

    return {
        "n_folders": n,
        "music_total": music_total,
        "music_folders_with": music_folders_with,
        "music_folders_partial": music_folders_partial,
        "cover_folders_with": cover_folders_with,
        "cover_folders_partial": cover_folders_partial,
        "video_total": video_total,
        "video_folders_with": video_folders_with,
        "video_folders_partial": video_folders_partial,
        "music_source_count": music_source_count,
        "cover_source_count": cover_source_count,
        "video_source_count": video_source_count,
    }

# =========================================================
# REQUIREMENTS / TOOLS
# =========================================================

def requirements_for_mode(mode):
    if mode == "1":
        return ["crid_mod.exe", "ffmpeg.exe", "ffprobe.exe"]
    if mode == "2":
        return ["vgmstream-cli.exe", "ffmpeg.exe"]
    if mode == "3":
        return ["vgmstream-cli.exe", "flac.exe", "ffmpeg.exe"]
    if mode == "4":
        return ["maiforge.exe"]
    if mode == "5":
        return [
            "maiforge.exe",
            "vgmstream-cli.exe",
            "ffmpeg.exe",
            "crid_mod.exe",
            "AssetStudio.CLI.exe",
        ]
    if mode == "6":
        return ["AssetStudio.CLI.exe"]
    return []


def autodetect_tool(tool_name):
    for candidate in TOOL_CANDIDATES.get(tool_name, []):
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def get_tool_path(tool_name):
    if tool_name in TOOL_PATHS and TOOL_PATHS[tool_name].exists():
        return TOOL_PATHS[tool_name]

    detected = autodetect_tool(tool_name)
    if detected:
        TOOL_PATHS[tool_name] = detected
        return detected

    return None


def ask_for_missing_tool(tool_name):
    path = ask_existing_file(f"Path to your {tool_name}: ")
    TOOL_PATHS[tool_name] = path
    return path


def resolve_requirements(required_tools):
    clear_screen()
    show_header()
    cli_print("Checking requirements...\n")

    resolved = {}
    missing = []

    for tool in required_tools:
        found = get_tool_path(tool)
        if found:
            cli_print(f"{tool} detected!")
            resolved[tool] = found
        else:
            cli_print(f"{tool} missing.")
            missing.append(tool)

    if missing:
        if CLI_MODE:
            missing_text = "\n".join(f"- {tool}" for tool in missing)
            raise FileNotFoundError(
                "Missing required tool(s):\n"
                f"{missing_text}\n\n"
                "Put them in the expected folders or run menu mode and set paths manually."
            )

        cli_print()
        for tool in missing:
            resolved[tool] = ask_for_missing_tool(tool)

    cli_print("\nAll required tools resolved.")
    wait_enter()
    return resolved

# =========================================================
# UI SCENES
# =========================================================

def scene_main_menu():
    clear_screen()
    show_header()
    print("[1] MP4 Conversion (.dat)")
    print("[2] MP3 Conversion (.awb)")
    print("[3] FLAC Conversion (.awb)")
    print("[4] Chart Conversion (.ma2)")
    print("[5] Database Conversion (AXXX Full Conversion)")
    print("[6] Image Conversion (.ab)")
    print("[S] Settings")
    print("[0] Exit")
    print()

    # Quick tool status row
    tool_checks = [
        ("vgmstream", "vgmstream-cli.exe"),
        ("ffmpeg",    "ffmpeg.exe"),
        ("crid",      "crid_mod.exe"),
        ("flac",      "flac.exe"),
        ("maiforge",  "maiforge.exe"),
        ("AssetStudio", "AssetStudio.CLI.exe"),
    ]
    parts = []
    for label, tool in tool_checks:
        exe = autodetect_tool(tool)
        found = exe is not None
        display = label
        if tool == "ffmpeg.exe" and found:
            display = f"{label} [{conv_get_active_encoder_label(str(exe))}]"
        parts.append(f"{'✓' if found else '✗'} {display}")
    print("Tools: " + "  ".join(parts))
    print()

    return ask_choice("Enter choice: ", {"0", "1", "2", "3", "4", "5", "6", "s", "S"})


def scene_single_batch_menu(mode_label):
    clear_screen()
    show_header()
    print(mode_label)
    print()
    print("[1] Single Conversion")
    print("[2] Batch Conversion")
    print()
    return ask_choice("Enter choice: ", {"1", "2"})


def scene_display_mode():
    settings = load_settings()
    default = settings.get("default_display_mode", "")
    if default in {"1", "2"}:
        return default
    clear_screen()
    show_header()
    print("Display mode\n")
    print("[1] Progress bar")
    print("[2] Logs")
    print()
    return ask_choice("Enter choice: ", {"1", "2"})


def scene_settings():
    """Interactive settings screen — edit and save persistent preferences."""
    _CAT_LABELS = ["Genre", "Level", "Cabinet", "Composer", "BPM", "SD/DX Chart", "No subfolders"]
    # Ordered encoder list with friendly labels
    _ENCODER_OPTIONS = [
        ("auto",       "Auto (recommended — picks best available)"),
        ("h264_nvenc", "H264 NVENC  (NVIDIA GPU, H264)"),
        ("hevc_nvenc", "HEVC NVENC  (NVIDIA GPU, H265 — MajdataX 5.1.7+ only)"),
        ("h264_amf",   "H264 AMF    (AMD GPU, H264)"),
        ("hevc_amf",   "HEVC AMF    (AMD GPU, H265 — MajdataX 5.1.7+ only)"),
        ("libx264",    "libx264     (CPU, H264 — most compatible)"),
        ("libx265",    "libx265     (CPU, H265 — MajdataX 5.1.7+ only)"),
    ]

    while True:
        s = load_settings()
        last_out    = s.get("last_output_dir", "") or "(not set)"
        disp        = s.get("default_display_mode", "")
        disp_label  = {"1": "Progress bar", "2": "Logs"}.get(disp, "(always ask)")
        cat         = s.get("default_categorization", "")
        try:
            cat_label = f"{cat}  {_CAT_LABELS[int(cat)]}"
        except Exception:
            cat_label = "(always ask)"
        enc         = mp4_load_config().get("video_encoder", "auto")
        enc_label   = next((lbl for key, lbl in _ENCODER_OPTIONS if key == enc), enc)
        static_mode = mp4_load_config().get("static_video", "loop")
        static_label = {"loop": "Loop/stretch to audio length", "skip": "Skip (don't convert)"}.get(static_mode, static_mode)
        temp_cleanup = s.get("temp_cleanup", "auto")
        temp_cleanup_label = {"auto": "Delete after each file", "keep": "Keep all temp files", "batch": "Delete after full run"}.get(temp_cleanup, temp_cleanup)
        retry_count   = s.get("retry_count", 1)
        workers       = s.get("parallel_workers", 1)
        notify        = s.get("notify_on_complete", True)
        notify_label  = "On" if notify else "Off"

        clear_screen()
        show_header()
        print("Settings\n")
        print(f"  [1] Last output folder    : {last_out}")
        print(f"  [2] Default display mode  : {disp_label}")
        print(f"  [3] Default categorization: {cat_label}")
        print(f"  [4] Video encoder         : {enc_label}")
        print(f"  [5] Static video behavior : {static_label}")
        print(f"  [6] Temp file cleanup     : {temp_cleanup_label}")
        print(f"  [7] Retry attempts        : {retry_count}x per file")
        print(f"  [8] Parallel workers      : {workers}")
        print(f"  [9] Notify on complete    : {notify_label}")
        print()
        print("  [C] Clear last output folder")
        print("  [0] Back")
        print()
        choice = ask_choice("Enter choice: ", {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "c", "C"})

        if choice == "0":
            return
        elif choice == "1":
            clear_screen()
            show_header()
            print("Settings — Output Folder\n")
            print(f"  Current: {last_out}")
            raw = input("  New path (blank to keep): ").strip().strip('"')
            if raw:
                p = Path(raw)
                try:
                    p.mkdir(parents=True, exist_ok=True)
                    update_setting("last_output_dir", str(p))
                    print(f"  \u2713 Saved.")
                except Exception as e:
                    print(f"  Could not use that path: {e}")
                input("  Press Enter...")
        elif choice == "2":
            clear_screen()
            show_header()
            print("Settings — Default Display Mode\n")
            print("  [1] Progress bar")
            print("  [2] Logs")
            print("  [3] Always ask (clear)")
            print()
            c2 = ask_choice("Enter choice: ", {"1", "2", "3"})
            update_setting("default_display_mode", "" if c2 == "3" else c2)
        elif choice == "3":
            clear_screen()
            show_header()
            print("Settings — Default Categorization\n")
            for i, label in enumerate(_CAT_LABELS):
                print(f"  [{i}] {label}")
            print(f"  [7] Always ask (clear)")
            print()
            c3 = ask_choice("Enter choice: ", {str(i) for i in range(8)})
            update_setting("default_categorization", "" if c3 == "7" else c3)
        elif choice == "4":
            clear_screen()
            show_header()
            print("Settings — Video Encoder\n")
            print("  H264 has the widest compatibility.")
            print("  H265 (HEVC) requires MajdataX 5.1.7 or later.\n")
            for i, (key, lbl) in enumerate(_ENCODER_OPTIONS):
                marker = " *" if key == enc else ""
                print(f"  [{i}] {lbl}{marker}")
            print()
            c4 = ask_choice("Enter choice: ", {str(i) for i in range(len(_ENCODER_OPTIONS))})
            selected_key = _ENCODER_OPTIONS[int(c4)][0]
            mp4_save_config({"video_encoder": selected_key})
            # Clear the lru_cache so the new encoder takes effect immediately
            from converters.mp4 import _pick_encoder
            _pick_encoder.cache_clear()
            print(f"\n  \u2713 Video encoder set to: {_ENCODER_OPTIONS[int(c4)][1]}")
            input("  Press Enter...")
        elif choice == "5":
            clear_screen()
            show_header()
            print("Settings — Static Video Behavior\n")
            print("  Static videos are single-frame / freeze-frame clips (no animation).\n")
            print(f"  [1] Loop/stretch to audio length  {'*' if static_mode == 'loop' else ''}")
            print(f"  [2] Skip (don't convert)          {'*' if static_mode == 'skip' else ''}")
            print()
            c5 = ask_choice("Enter choice: ", {"1", "2"})
            new_static = "loop" if c5 == "1" else "skip"
            mp4_save_config({"static_video": new_static})
            _label5 = "Loop/stretch to audio length" if new_static == "loop" else "Skip (don't convert)"
            print(f"\n  \u2713 Static video behavior set to: {_label5}")
            input("  Press Enter...")
        elif choice == "6":
            clear_screen()
            show_header()
            print("Settings — Temp File Cleanup\n")
            print("  Controls when intermediate files (.m2v, .wav) are deleted.\n")
            print(f"  [1] Delete after each file  {'*' if temp_cleanup == 'auto' else ''}")
            print(f"  [2] Keep all temp files     {'*' if temp_cleanup == 'keep' else ''}")
            print(f"  [3] Delete after full run   {'*' if temp_cleanup == 'batch' else ''}")
            print()
            c6 = ask_choice("Enter choice: ", {"1", "2", "3"})
            new_cleanup = {"1": "auto", "2": "keep", "3": "batch"}[c6]
            update_setting("temp_cleanup", new_cleanup)
            _label6 = {"auto": "Delete after each file", "keep": "Keep all temp files", "batch": "Delete after full run"}[new_cleanup]
            print(f"\n  \u2713 Temp file cleanup set to: {_label6}")
            input("  Press Enter...")
        elif choice.lower() == "c":
            update_setting("last_output_dir", "")
        elif choice == "7":
            clear_screen()
            show_header()
            print("Settings — Retry Attempts\n")
            print("  How many times to attempt a file before marking it failed.\n")
            print(f"  [1] 1× (no retry)   {'*' if retry_count == 1 else ''}")
            print(f"  [2] 2× (retry once) {'*' if retry_count == 2 else ''}")
            print(f"  [3] 3× (retry twice){'*' if retry_count == 3 else ''}")
            print()
            c7 = ask_choice("Enter choice: ", {"1", "2", "3"})
            update_setting("retry_count", int(c7))
            print(f"\n  \u2713 Retry attempts set to {c7}×.")
            input("  Press Enter...")
        elif choice == "8":
            clear_screen()
            show_header()
            print("Settings — Parallel Workers\n")
            print("  How many files to process simultaneously.")
            print("  (Note: MP4/crid conversions are always sequential.)\n")
            for n in range(1, 5):
                marker = " *" if workers == n else ""
                print(f"  [{n}] {n} worker{'s' if n > 1 else ''}{marker}")
            print()
            c8 = ask_choice("Enter choice: ", {"1", "2", "3", "4"})
            update_setting("parallel_workers", int(c8))
            print(f"\n  \u2713 Parallel workers set to {c8}.")
            input("  Press Enter...")
        elif choice == "9":
            clear_screen()
            show_header()
            print("Settings — Notify on Complete\n")
            print("  Play a sound and show a Windows notification when a batch finishes.\n")
            print(f"  [1] On  {'*' if notify else ''}")
            print(f"  [2] Off {'*' if not notify else ''}")
            print()
            c9 = ask_choice("Enter choice: ", {"1", "2"})
            update_setting("notify_on_complete", c9 == "1")
            print(f"\n  \u2713 Notify on complete set to {'On' if c9 == '1' else 'Off'}.")
            input("  Press Enter...")


def scene_blank_assets_decision():
    clear_screen()
    show_header()
    print("Music, cover, and/or video paths are blank.")
    print("How do you want to continue?\n")
    print("[1] Ignore incomplete assets and continue")
    print("[2] Auto-convert missing assets then continue")
    print("[3] Cancel")
    print()
    return ask_choice("Enter choice: ", {"1", "2", "3"})


def scene_select_missing_assets(missing_items):
    """
    Interactive selector for choosing which missing assets to auto-convert.
    Returns:
      - list[str] of selected keys ("music", "cover", "video")
      - [] when confirmed with nothing selected
      - None when cancelled
    """
    if not missing_items:
        return []

    # Windows: true checklist UX (space to toggle, enter to confirm)
    if WINDOWS:
        selected = [False] * len(missing_items)
        cursor = 0

        while True:
            clear_screen()
            show_header()
            print("Missing assets detected.")
            print("Select which missing assets to auto-convert.\n")
            print("Controls: Up/Down = move, Space = toggle, Enter = confirm, Esc = cancel\n")

            for idx, (_, label) in enumerate(missing_items):
                pointer = ">" if idx == cursor else " "
                mark = "x" if selected[idx] else " "
                print(f"{pointer} [{mark}] {label}")

            key = msvcrt.getwch()

            if key in ("\r", "\n"):
                return [missing_items[i][0] for i, state in enumerate(selected) if state]
            if key == "\x1b":  # ESC
                return None
            if key == " ":
                selected[cursor] = not selected[cursor]
                continue
            if key in ("\xe0", "\x00"):
                key2 = msvcrt.getwch()
                if key2 == "H":  # up
                    cursor = (cursor - 1) % len(missing_items)
                elif key2 == "P":  # down
                    cursor = (cursor + 1) % len(missing_items)

    # Non-Windows fallback: simple numeric selection
    clear_screen()
    show_header()
    print("Missing assets detected.")
    print("Select which missing assets to auto-convert (comma-separated numbers).\n")
    for idx, (_, label) in enumerate(missing_items, start=1):
        print(f"[{idx}] {label}")
    print("[0] None")
    print()

    while True:
        raw = input("Enter choices (example: 1,3): ").strip()
        if raw == "":
            return []

        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if parts == ["0"]:
            return []

        if not all(p.isdigit() for p in parts):
            print("Invalid input. Please enter numbers only.")
            continue

        nums = sorted(set(int(p) for p in parts))
        if any(n < 1 or n > len(missing_items) for n in nums):
            print("Invalid choice number.")
            continue

        return [missing_items[n - 1][0] for n in nums]


def scene_existing_assets_decision():
    clear_screen()
    show_header()
    print("Existing generated asset files were found.")
    print("How do you want to continue?\n")
    print("[1] Overwrite existing files")
    print("[2] Skip existing files and continue the rest")
    print("[3] Cancel")
    print()
    return ask_choice("Enter choice: ", {"1", "2", "3"})


def scene_detect_and_confirm_assets(mode_type: str, axxx_path, axxx_paths: list):
    """Auto-detect temp assets in AXXX folder(s) and ask how to proceed.

    Returns a dict with music_path, cover_path, video_path, auto_convert_assets,
    auto_convert_targets, existing_assets_policy, and ignore_incomplete — or None
    if the user cancels.
    """
    all_paths = list(axxx_paths) if axxx_paths else ([axxx_path] if axxx_path else [])
    status = detect_axxx_temp_assets(all_paths)
    n = status["n_folders"]
    is_batch = n > 1

    def _status_line(label, dir_name, folders_with, folders_partial, total_desc, source_count):
        if is_batch:
            if folders_with == n:
                found_str = f"complete in all {n} folders"
            elif folders_with > 0 and folders_partial > 0:
                found_str = f"complete in {folders_with}/{n}, partial in {folders_partial}/{n}"
            elif folders_with > 0:
                found_str = f"complete in {folders_with}/{n} folders"
            elif folders_partial > 0:
                found_str = f"partial in {folders_partial}/{n} folders"
            else:
                found_str = "not found"
        else:
            if folders_with > 0:
                found_str = total_desc
            elif folders_partial > 0:
                found_str = f"partial ({total_desc})"
            else:
                found_str = "not found"
        if folders_with == n:
            icon = "✓"
        elif folders_with > 0 or folders_partial > 0:
            icon = "~"
        else:
            icon = "✗"
        src = f" (source available in {source_count}/{n})" if (folders_with + folders_partial) < n and source_count > 0 else ""
        return f"  [{icon}] {label:<10} {dir_name:<16} {found_str}{src}"

    music_line = _status_line(
        "Music", "musicMP3/",
        status["music_folders_with"],
        status["music_folders_partial"],
        f"{status['music_total']} MP3 file(s)",
        status["music_source_count"],
    )
    cover_line = _status_line(
        "Jackets", "Jackets/",
        status["cover_folders_with"],
        status["cover_folders_partial"],
        "images found",
        status["cover_source_count"],
    )
    video_line = _status_line(
        "Video", "Movie/",
        status["video_folders_with"],
        status["video_folders_partial"],
        f"{status['video_total']} MP4 file(s)",
        status["video_source_count"],
    )

    music_complete = status["music_folders_with"] == n
    cover_complete = status["cover_folders_with"] == n
    video_complete = status["video_folders_with"] == n
    music_partial = status["music_folders_partial"] > 0
    cover_partial = status["cover_folders_partial"] > 0
    video_partial = status["video_folders_partial"] > 0
    all_complete = music_complete and cover_complete and video_complete
    any_partial = music_partial or cover_partial or video_partial

    # Which types need attention (missing entirely OR partial)
    missing_types = []
    if not music_complete:
        missing_types.append("music")
    if not cover_complete:
        missing_types.append("cover")
    if not video_complete:
        missing_types.append("video")

    can_generate = {
        t for t in missing_types
        if (t == "music" and status["music_source_count"] > 0)
        or (t == "cover" and status["cover_source_count"] > 0)
        or (t == "video" and status["video_source_count"] > 0)
    }

    batch_label = f"  Batch: {n} folders" if is_batch else "  Single"
    clear_screen()
    show_header()
    print(f"Temp Asset Detection  ({batch_label.strip()})\n")
    print("  " + "─" * 58)
    print(music_line)
    print(cover_line)
    print(video_line)
    print("  " + "─" * 58)

    if all_complete:
        print("\n  All temp assets detected.\n")
        wait_enter()
        if mode_type == "single" and axxx_path:
            return {
                "music_path": axxx_path / "musicMP3",
                "cover_path": axxx_path / "Jackets",
                "video_path": axxx_path / "Movie",
                "auto_convert_assets": False,
                "auto_convert_targets": [],
                "existing_assets_policy": None,
                "ignore_incomplete": False,
            }
        # Batch: let auto_build pick up each AXXX's own subdirs via skip policy
        return {
            "music_path": None,
            "cover_path": None,
            "video_path": None,
            "auto_convert_assets": True,
            "auto_convert_targets": ["music", "cover", "video"],
            "existing_assets_policy": "skip",
            "ignore_incomplete": False,
        }

    # Some assets are missing or partial
    missing_count = len(missing_types)
    partial_note = "  [~] = partial files from a previous interrupted run.\n" if any_partial else ""
    print(f"\n  {missing_count} asset type(s) missing or incomplete.\n{partial_note}")

    valid_choices = {"2", "3"}
    if can_generate:
        gen_names = {"music": "Music", "cover": "Jackets", "video": "Video"}
        gen_list = ", ".join(gen_names[k] for k in missing_types if k in can_generate)
        print(f"  [1] Generate missing ({gen_list}) and proceed")
        valid_choices.add("1")
    else:
        print("  [1] (Cannot generate — source files not available)")

    print("  [2] Proceed (ignore missing)")
    print("  [3] Cancel")
    print()

    choice = ask_choice("Enter choice: ", valid_choices)

    if choice == "3":
        return None

    if choice == "2":
        # Use whatever is found (complete or partial); ignore the rest
        if mode_type == "single" and axxx_path:
            return {
                "music_path": (axxx_path / "musicMP3") if (status["music_folders_with"] > 0 or status["music_folders_partial"] > 0) else None,
                "cover_path": (axxx_path / "Jackets") if (status["cover_folders_with"] > 0 or status["cover_folders_partial"] > 0) else None,
                "video_path": (axxx_path / "Movie") if (status["video_folders_with"] > 0 or status["video_folders_partial"] > 0) else None,
                "auto_convert_assets": False,
                "auto_convert_targets": [],
                "existing_assets_policy": None,
                "ignore_incomplete": True,
            }
        found_targets = []
        if status["music_folders_with"] > 0 or status["music_folders_partial"] > 0:
            found_targets.append("music")
        if status["cover_folders_with"] > 0 or status["cover_folders_partial"] > 0:
            found_targets.append("cover")
        if status["video_folders_with"] > 0 or status["video_folders_partial"] > 0:
            found_targets.append("video")
        return {
            "music_path": None,
            "cover_path": None,
            "video_path": None,
            "auto_convert_assets": bool(found_targets),
            "auto_convert_targets": found_targets,
            "existing_assets_policy": "skip" if found_targets else None,
            "ignore_incomplete": True,
        }

    # choice == "1": Let user pick which missing types to generate
    generatable = [t for t in missing_types if t in can_generate]
    gen_display = {"music": "Music  (source: SoundData/)", "cover": "Jackets (source: AssetBundleImages/)", "video": "Video  (source: MovieData/)"}

    # Toggle selection — all generatable types start ON
    selected = {t: True for t in generatable}

    while True:
        clear_screen()
        show_header()
        print("Generate Assets\n")
        print("  Toggle which asset types to generate:\n")
        for i, t in enumerate(generatable, start=1):
            state = "ON " if selected[t] else "OFF"
            print(f"  [{i}] [{state}]  {gen_display[t]}")
        print()
        print("  [C] Confirm and proceed")
        print("  [X] Cancel")
        print()

        valid = {str(i) for i in range(1, len(generatable) + 1)} | {"c", "C", "x", "X"}
        raw = input("Enter choice: ").strip()
        if raw not in valid:
            continue
        if raw.lower() == "x":
            return None
        if raw.lower() == "c":
            break
        idx = int(raw) - 1
        t = generatable[idx]
        selected[t] = not selected[t]

    targets_to_generate = [t for t in generatable if selected[t]]
    # found_targets: types already complete — always pass through (with skip policy)
    # But only include them if they weren't toggled off (they can't be, but be explicit)
    found_targets = [t for t in ["music", "cover", "video"] if t not in missing_types]
    all_targets = found_targets + targets_to_generate

    if mode_type == "single" and axxx_path:
        return {
            # Only pass a pre-built path when the asset was already complete.
            # If the type was missing (even if user toggled it off), pass None
            # so the command builder omits the flag entirely.
            "music_path": (axxx_path / "musicMP3") if "music" not in missing_types else None,
            "cover_path": (axxx_path / "Jackets") if "cover" not in missing_types else None,
            "video_path": (axxx_path / "Movie") if "video" not in missing_types else None,
            "auto_convert_assets": bool(targets_to_generate),
            "auto_convert_targets": targets_to_generate,
            "existing_assets_policy": "skip",  # preserve any already-converted files
            "ignore_incomplete": False,
        }
    # Batch: include both found (skip keeps them) and to-generate
    return {
        "music_path": None,
        "cover_path": None,
        "video_path": None,
        "auto_convert_assets": bool(all_targets),
        "auto_convert_targets": all_targets,
        "existing_assets_policy": "skip",
        "ignore_incomplete": False,
    }


def scene_existing_output_decision():
    clear_screen()
    show_header()
    print("Existing output files were found.")
    print("How do you want to continue?\n")
    print("[1] Overwrite existing files")
    print("[2] Skip existing files and continue the rest")
    print("[3] Cancel")
    print()
    return ask_choice("Enter choice: ", {"1", "2", "3"})


def resolve_existing_output_policy():
    choice = scene_existing_output_decision()
    if choice == "1":
        return "overwrite"
    if choice == "2":
        return "skip"
    return None


def resolve_existing_output_policy_if_needed(folder: Path, exts=None, folder_mode=False, image_mode=False):
    if image_mode:
        has_existing = output_folder_has_relevant_image_outputs(folder)
    elif folder_mode:
        has_existing = output_folder_has_any_files(folder)
    else:
        has_existing = has_existing_files_with_ext(folder, exts or set())

    if not has_existing:
        return "overwrite"

    return resolve_existing_output_policy()


def scene_completion(success_count, missing_count, failed_count, log_path=None,
                     output_path=None, elapsed=None):
    if load_settings().get("notify_on_complete", True):
        msg = f"Done — {success_count} ok"
        if failed_count:
            msg += f", {failed_count} failed"
        _notify_done(message=msg)

    clear_screen()
    show_header()
    print("Conversion Completed!\n")
    print(f"Successfully Converted: {success_count}")
    print(f"Missing: {missing_count}")
    print(f"Failed: {failed_count}")
    if elapsed is not None:
        print(f"Time taken: {_fmt_duration(elapsed)} ({elapsed:.1f}s)")
    print()
    if log_path:
        print(f"Logs are stored at:\n{log_path}")
    if output_path:
        print(f"\n[O] Open output folder in Explorer")
    print()
    prompt = "Press Enter to return to main menu"
    if output_path:
        prompt += ", or type O to open output"
    val = input(prompt + ": ").strip().lower()
    if val == "o" and output_path:
        _open_in_explorer(output_path)

# =========================================================
# PROMPTS
# =========================================================

def prompt_mp4(single_or_batch):
    clear_screen()
    show_header()

    s = load_settings()
    last_in = s.get("last_mp4_input", "")

    if single_or_batch == "1":
        raw_in = _ask_with_hint("Enter path to your .dat file: ", last_in)
        input_path = Path(raw_in)
        if not (input_path.exists() and input_path.is_file()):
            print("File not found.")
            wait_enter()
            return None
    else:
        raw_in = _ask_with_hint("Enter path to your .dat folder: ", last_in)
        input_path = Path(raw_in)
        if not (input_path.exists() and input_path.is_dir()):
            print("Folder not found.")
            wait_enter()
            return None
    update_setting("last_mp4_input", str(input_path))

    # crid.exe silently fails when the path contains spaces — warn immediately.
    if " " in str(input_path):
        print()
        print("  ⚠  WARNING: Your input path contains spaces:")
        print(f"     {input_path}")
        print("  crid.exe does not support paths with spaces and will silently")
        print("  produce no output. Please move your files to a path with no spaces")
        print('  (e.g. rename "Telegram Desktop" → "Telegram").')
        print()
        input("  Press Enter to continue anyway, or Ctrl+C to cancel...")
        print()

    output_path = ask_output_dir("Enter output folder: ")

    policy = resolve_existing_output_policy_if_needed(output_path, exts={".mp4"})
    if policy is None:
        return None

    return {
        "input_path": input_path,
        "output_path": output_path,
        "mode_type": "single" if single_or_batch == "1" else "batch",
        "existing_output_policy": policy,
    }


def prompt_mp3(single_or_batch):
    clear_screen()
    show_header()

    s = load_settings()
    last_in = s.get("last_mp3_input", "")

    if single_or_batch == "1":
        raw_in = _ask_with_hint("Enter path to your .awb file: ", last_in)
        input_path = Path(raw_in)
        if not (input_path.exists() and input_path.is_file()):
            print("File not found.")
            wait_enter()
            return None
    else:
        raw_in = _ask_with_hint("Enter path to your .awb folder: ", last_in)
        input_path = Path(raw_in)
        if not (input_path.exists() and input_path.is_dir()):
            print("Folder not found.")
            wait_enter()
            return None
    update_setting("last_mp3_input", str(input_path))

    output_path = ask_output_dir("Enter output folder: ")

    policy = resolve_existing_output_policy_if_needed(output_path, exts={".mp3"})
    if policy is None:
        return None

    return {
        "input_path": input_path,
        "output_path": output_path,
        "mode_type": "single" if single_or_batch == "1" else "batch",
        "existing_output_policy": policy,
    }


def prompt_flac(single_or_batch):
    clear_screen()
    show_header()

    s = load_settings()
    last_in = s.get("last_flac_input", "")

    if single_or_batch == "1":
        raw_in = _ask_with_hint("Enter path to your .awb file: ", last_in)
        input_path = Path(raw_in)
        if not (input_path.exists() and input_path.is_file()):
            print("File not found.")
            wait_enter()
            return None
    else:
        raw_in = _ask_with_hint("Enter path to your .awb folder: ", last_in)
        input_path = Path(raw_in)
        if not (input_path.exists() and input_path.is_dir()):
            print("Folder not found.")
            wait_enter()
            return None
    update_setting("last_flac_input", str(input_path))

    output_path = ask_output_dir("Enter output folder: ")

    policy = resolve_existing_output_policy_if_needed(output_path, exts={".flac"})
    if policy is None:
        return None

    return {
        "input_path": input_path,
        "output_path": output_path,
        "mode_type": "single" if single_or_batch == "1" else "batch",
        "existing_output_policy": policy,
    }


_CHART_FORMAT_OPTIONS = [
    ("zip_after", "Save as .zip"),
    ("adx_after", "Save as .adx (AstroDX)"),
]


def ask_chart_format_interactive():
    """Interactive checklist for chart output format options.
    Returns dict with zip_after and adx_after, or None if cancelled.
    """
    options = _CHART_FORMAT_OPTIONS
    toggles = [False] * len(options)
    cursor = 0

    if not WINDOWS or CLI_MODE:
        return {
            "zip_after": ask_yes_no("Save as .zip? (y/n): "),
            "adx_after": ask_yes_no("Save as .adx (AstroDX)? (y/n): "),
        }

    while True:
        clear_screen()
        show_header()
        print("Chart Output Format\n")
        print("  Up/Down = move   Space = toggle   Enter = confirm   Esc = cancel\n")
        for i, (_, label) in enumerate(options):
            pointer = ">" if cursor == i else " "
            mark = "\u25cf" if toggles[i] else " "
            print(f"  {pointer} [{mark}] {label}")

        key = msvcrt.getwch()
        if key in ("\r", "\n"):
            break
        elif key == "\x1b":
            return None
        elif key == " ":
            toggles[cursor] = not toggles[cursor]
        elif key in ("\xe0", "\x00"):
            key2 = msvcrt.getwch()
            if key2 == "H":
                cursor = (cursor - 1) % len(options)
            elif key2 == "P":
                cursor = (cursor + 1) % len(options)

    return {key: toggles[i] for i, (key, _) in enumerate(options)}


def prompt_chart():
    clear_screen()
    show_header()

    s = load_settings()
    last_in = s.get("last_chart_input", "")

    while True:
        raw_in = _ask_with_hint("Enter path to your chart file (.ma2): ", last_in)
        input_path = Path(raw_in)
        if input_path.exists() and input_path.is_file():
            break
        print("File not found or not a file.")

    update_setting("last_chart_input", str(input_path))
    output_path = ask_output_dir("Enter output folder: ")

    fmt = ask_chart_format_interactive()
    if fmt is None:
        return None
    zip_after = fmt["zip_after"]
    adx_after = fmt["adx_after"]

    policy = resolve_existing_output_policy_if_needed(output_path, folder_mode=True)
    if policy is None:
        return None

    return {
        "input_path": input_path,
        "output_path": output_path,
        "zip_after": zip_after,
        "adx_after": adx_after,
        "mode_type": "single",
        "existing_output_policy": policy,
    }


def prompt_image(single_or_batch):
    clear_screen()
    show_header()

    s = load_settings()
    last_in = s.get("last_image_input", "")

    if single_or_batch == "1":
        raw_in = _ask_with_hint("Enter path to your .ab file: ", last_in)
        input_path = Path(raw_in)
        if not (input_path.exists() and input_path.is_file()):
            print("File not found.")
            wait_enter()
            return None
    else:
        raw_in = _ask_with_hint("Enter path to your .ab folder: ", last_in)
        input_path = Path(raw_in)
        if not (input_path.exists() and input_path.is_dir()):
            print("Folder not found.")
            wait_enter()
            return None
    update_setting("last_image_input", str(input_path))

    output_path = ask_output_dir("Enter output folder: ")

    policy = resolve_existing_output_policy_if_needed(output_path, image_mode=True)
    if policy is None:
        return None

    return {
        "input_path": input_path,
        "output_path": output_path,
        "mode_type": "single" if single_or_batch == "1" else "batch",
        "existing_output_policy": policy,
    }


_DB_CATEGORY_LABELS = [
    "Genre", "Level", "Cabinet", "Composer", "BPM", "SD/DX Chart", "No subfolders"
]

_DB_TOGGLE_OPTIONS = [
    ("decimal",           "Force decimal levels"),
    ("use_number",        "Use music ID as folder name"),
    ("json_log",          "Create JSON log"),
    ("zip_after",         "Zip after conversion (per-category .zip)"),
    ("adx_after",         "AstroDX export (per-category .adx)"),
    ("adx_track",         "AstroDX export (per-track .adx)"),
    ("collection",        "Generate collection manifest"),
    ("ignore_incomplete", "Ignore errors (--ignore-incomplete)"),
    ("ignore_video",      "Ignore missing videos (--ignore-video)"),
]

# =========================================================
# SETTINGS
# =========================================================

_SETTINGS_DEFAULTS = {
    "last_output_dir": "",
    "default_display_mode": "",   # "1" or "2" — blank = always ask
    "default_categorization": "", # "0"-"6"  — blank = always ask
    "temp_cleanup": "auto",       # "auto" | "keep" | "batch"
    "retry_count": 1,             # 1–3: attempts per file before marking failed
    "parallel_workers": 2,        # workers for mp3/flac parallel conversion (1 = sequential)
    "notify_on_complete": True,   # beep + Windows notification when batch finishes
    "last_mp4_input": "",
    "last_mp3_input": "",
    "last_flac_input": "",
    "last_image_input": "",
    "last_chart_input": "",
    "last_db_input": "",
}

def load_settings() -> dict:
    """Load persistent user settings. Missing keys fall back to defaults."""
    if not SETTINGS_FILE.exists():
        return dict(_SETTINGS_DEFAULTS)
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(_SETTINGS_DEFAULTS)
        if isinstance(data, dict):
            merged.update({k: v for k, v in data.items() if k in _SETTINGS_DEFAULTS})
        return merged
    except Exception:
        return dict(_SETTINGS_DEFAULTS)


def save_settings(settings: dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def update_setting(key: str, value):
    s = load_settings()
    s[key] = value
    save_settings(s)


# =========================================================
# PRESETS
# =========================================================

def load_presets() -> dict:
    """Load saved DB option presets from disk. Returns {name: opts_dict}."""
    if not PRESETS_FILE.exists():
        return {}
    try:
        with open(PRESETS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("presets", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_preset(name: str, opts: dict):
    """Persist a named DB options preset (without output_path) to disk."""
    presets = load_presets()
    presets[name] = {k: v for k, v in opts.items() if k != "output_path"}
    try:
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump({"presets": presets}, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def scene_preset_select(presets: dict):
    """Arrow-key preset selection (Windows). Returns chosen opts dict or None (start fresh / cancel)."""
    names = list(presets.keys())
    items = names + ["[Start fresh]"]
    cursor = 0
    while True:
        clear_screen()
        show_header()
        print("Database Conversion — Presets\n")
        print("  Up/Down = move   Enter = select   Esc = cancel\n")
        for i, item in enumerate(items):
            pointer = ">" if i == cursor else " "
            print(f"  {pointer} {item}")
        print()
        key = msvcrt.getwch()
        if key in ("\r", "\n"):
            if cursor == len(names):
                return None
            return presets[names[cursor]]
        elif key == "\x1b":
            return None
        elif key in ("\xe0", "\x00"):
            key2 = msvcrt.getwch()
            if key2 == "H":
                cursor = (cursor - 1) % len(items)
            elif key2 == "P":
                cursor = (cursor + 1) % len(items)


def ask_db_options_interactive():
    """Interactive checklist for database conversion options.
    Returns dict of all options + output_path, or None if cancelled.
    """
    N_CATS = len(_DB_CATEGORY_LABELS)
    N_TOGGLES = len(_DB_TOGGLE_OPTIONS)
    TOTAL = N_CATS + N_TOGGLES

    category_idx = 2  # default: Cabinet
    # Override with saved setting if present
    _saved_cat = load_settings().get("default_categorization", "")
    if _saved_cat in {str(i) for i in range(N_CATS)}:
        category_idx = int(_saved_cat)
    toggles = [False] * N_TOGGLES
    cursor = category_idx

    if not WINDOWS or CLI_MODE:
        # Non-interactive fallback
        clear_screen()
        show_header()
        print("Database Conversion Options\n")
        print("Categorization:")
        for i, label in enumerate(_DB_CATEGORY_LABELS):
            print(f"  {i} = {label}")
        categorization = ask_choice("Enter categorization (0-6): ", {str(i) for i in range(N_CATS)})
        decimal = ask_yes_no("Force decimal levels? (y/n): ")
        use_number = ask_yes_no("Use music ID as folder name? (y/n): ")
        json_log = ask_yes_no("Create JSON log? (y/n): ")
        zip_after = ask_yes_no("Zip after conversion (.zip)? (y/n): ")
        adx_after = ask_yes_no("AstroDX export (.adx)? (y/n): ")
        adx_track = ask_yes_no("AstroDX export per-track (.adx)? (y/n): ")
        collection = ask_yes_no("Generate collection manifest? (y/n): ")
        ignore_incomplete = ask_yes_no("Ignore errors? (y/n): ")
        ignore_video = ask_yes_no("Ignore missing videos? (y/n): ")
        output_path = ask_output_dir("  Output folder: ")
        return {
            "categorization": categorization,
            "decimal": decimal,
            "use_number": use_number,
            "json_log": json_log,
            "zip_after": zip_after,
            "adx_after": adx_after,
            "adx_track": adx_track,
            "collection": collection,
            "ignore_incomplete": ignore_incomplete,
            "ignore_video": ignore_video,
            "output_path": output_path,
        }

    # Pre-fill from a saved preset if any exist
    presets = load_presets()
    if presets:
        loaded = scene_preset_select(presets)
        if loaded is not None:
            try:
                category_idx = max(0, min(int(loaded.get("categorization", category_idx)), N_CATS - 1))
            except (ValueError, TypeError):
                pass
            cursor = category_idx
            for i, (k, _) in enumerate(_DB_TOGGLE_OPTIONS):
                toggles[i] = bool(loaded.get(k, False))

    while True:
        clear_screen()
        show_header()
        print("Database Conversion Options\n")
        hint = "  Up/Down = move   Space = select/toggle   Enter = confirm   Esc = cancel"
        if presets:
            hint += "   P = load preset"
        print(hint + "\n")

        print("  Categorization:")
        for i, label in enumerate(_DB_CATEGORY_LABELS):
            pointer = ">" if cursor == i else " "
            mark = "\u25cf" if category_idx == i else " "
            print(f"  {pointer} ({mark}) {i}  {label}")

        print()
        print("  Options:")
        for i, (_, label) in enumerate(_DB_TOGGLE_OPTIONS):
            idx = N_CATS + i
            pointer = ">" if cursor == idx else " "
            mark = "\u25cf" if toggles[i] else " "
            print(f"  {pointer} [{mark}] {label}")

        key = msvcrt.getwch()

        if key in ("\r", "\n"):
            break
        elif key == "\x1b":
            return None
        elif key.lower() == "p" and presets:
            loaded = scene_preset_select(presets)
            if loaded is not None:
                try:
                    category_idx = max(0, min(int(loaded.get("categorization", category_idx)), N_CATS - 1))
                except (ValueError, TypeError):
                    pass
                cursor = category_idx
                for i, (k, _) in enumerate(_DB_TOGGLE_OPTIONS):
                    toggles[i] = bool(loaded.get(k, False))
        elif key == " ":
            if cursor < N_CATS:
                category_idx = cursor
            else:
                t = cursor - N_CATS
                toggles[t] = not toggles[t]
        elif key in ("\xe0", "\x00"):
            key2 = msvcrt.getwch()
            if key2 == "H":
                cursor = (cursor - 1) % TOTAL
            elif key2 == "P":
                cursor = (cursor + 1) % TOTAL

    # Show confirmed summary, offer to save preset, ask output path
    clear_screen()
    show_header()
    print("Database Conversion Options\n")
    print(f"  Categorization : {category_idx}  {_DB_CATEGORY_LABELS[category_idx]}")
    for i, (_, label) in enumerate(_DB_TOGGLE_OPTIONS):
        mark = "\u25cf" if toggles[i] else "\u25cb"
        print(f"  [{mark}] {label}")
    print()
    save_name = input("  Save as preset? (name or blank to skip): ").strip()
    if save_name:
        preset_opts = {"categorization": str(category_idx)}
        for i, (k, _) in enumerate(_DB_TOGGLE_OPTIONS):
            preset_opts[k] = toggles[i]
        save_preset(save_name, preset_opts)
        print(f"  \u2713 Preset '{save_name}' saved.\n")
    output_path = ask_output_dir("  Output folder: ")

    return {
        "categorization": str(category_idx),
        "decimal": toggles[0],
        "use_number": toggles[1],
        "json_log": toggles[2],
        "zip_after": toggles[3],
        "adx_after": toggles[4],
        "adx_track": toggles[5],
        "collection": toggles[6],
        "ignore_incomplete": toggles[7],
        "ignore_video": toggles[8],
        "output_path": output_path,
    }


def prompt_database():
    clear_screen()
    show_header()

    s = load_settings()
    last_db_in = s.get("last_db_input", "")

    while True:
        raw_db = _ask_with_hint("(Required) Enter path to your AXXX folder or batch root: ", last_db_in)
        _p = Path(raw_db)
        if _p.exists() and _p.is_dir():
            detection = detect_axxx_input(_p)
            if detection:
                update_setting("last_db_input", str(_p))
                break
        print("Not an AXXX folder or a folder containing AXXX folders (e.g., A001, M100).")

    mode_type = detection["mode_type"]
    axxx_path = detection.get("axxx_path")
    axxx_paths = detection.get("axxx_paths") or []

    if mode_type == "single" and axxx_path:
        print(f"  Detected: Single database ({axxx_path.name})\n")
    elif mode_type == "batch":
        print(f"  Detected: Batch database  {len(axxx_paths)} folders: {format_axxx_list(axxx_paths)}")
        print("  Non-AXXX folders/files will be ignored.\n")

    wait_enter()

    # Auto-detect temp asset directories inside the AXXX folder(s)
    asset_result = scene_detect_and_confirm_assets(mode_type, axxx_path, axxx_paths)
    if asset_result is None:
        return None

    music_path = asset_result["music_path"]
    cover_path = asset_result["cover_path"]
    video_path = asset_result["video_path"]
    auto_convert_assets = asset_result["auto_convert_assets"]
    auto_convert_targets = asset_result["auto_convert_targets"]
    existing_assets_policy = asset_result["existing_assets_policy"]
    ignore_incomplete = asset_result.get("ignore_incomplete", False)

    opts = ask_db_options_interactive()
    if opts is None:
        return None

    categorization = opts["categorization"]
    decimal = opts["decimal"]
    use_number = opts["use_number"]
    json_log = opts["json_log"]
    zip_after = opts["zip_after"]
    adx_after = opts["adx_after"]
    adx_track = opts["adx_track"]
    collection = opts["collection"]
    ignore_incomplete = opts["ignore_incomplete"]
    ignore_video = opts.get("ignore_video", False)
    output_path = opts["output_path"]

    # Check the actual AXXX-specific output dir, not just the parent folder
    if mode_type == "batch":
        _check_existing = any((output_path / p.name).exists() for p in axxx_paths)
    else:
        _check_existing = (output_path / axxx_path.name).exists()
    if _check_existing:
        output_policy = resolve_existing_output_policy()
    else:
        output_policy = "overwrite"
    if output_policy is None:
        return None

    return {
        "axxx_path": axxx_path,
        "axxx_paths": axxx_paths,
        "batch_root": detection.get("batch_root"),
        "music_path": music_path,
        "cover_path": cover_path,
        "video_path": video_path,
        "categorization": categorization,
        "decimal": decimal,
        "ignore_incomplete": ignore_incomplete,
        "ignore_video": ignore_video,
        "auto_convert_assets": auto_convert_assets,
        "auto_convert_targets": auto_convert_targets,
        "existing_assets_policy": existing_assets_policy,
        "existing_output_policy": output_policy,
        "use_number": use_number,
        "json_log": json_log,
        "zip_after": zip_after,
        "adx_after": adx_after,
        "adx_track": adx_track,
        "collection": collection,
        "output_path": output_path,
        "auto_generated_temp_dirs": [],
    }

# =========================================================
# COMMAND BUILDERS
# =========================================================

def patch_music_xml_jacket_fields(axxx_path: Path, cover_path) -> list:
    """Pre-patch empty <jacketFile> fields in Music.xml before running maiforge.
    
    Maiforge crashes with 'The path is empty. (Parameter path)' when <jacketFile>
    is empty string. This fills it from cueName/id -> UI_Jacket_XXXXXX.png.
    """
    music_root = axxx_path / "music"
    if not music_root.is_dir():
        return []

    # Build index: numeric cue_id -> jacket filename
    jacket_index: dict[int, str] = {}
    if cover_path and cover_path.is_dir():
        for f in cover_path.glob("UI_Jacket_*.png"):
            num_part = f.stem.replace("UI_Jacket_", "")
            try:
                jacket_index[int(num_part)] = f.name
            except ValueError:
                pass

    patched = 0
    logs = []
    for music_dir in music_root.iterdir():
        if not music_dir.is_dir():
            continue
        xml_path = music_dir / "Music.xml"
        if not xml_path.exists():
            continue
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            jf_el = root.find("jacketFile")
            if jf_el is None:
                continue
            if jf_el.text and jf_el.text.strip():
                continue  # already has a value

            cue_id_text = root.findtext("cueName/id") or ""
            try:
                cue_id = int(cue_id_text)
            except ValueError:
                continue

            jacket_name = jacket_index.get(cue_id)
            if not jacket_name:
                # fallback: zero-pad to 6 digits
                jacket_name = f"UI_Jacket_{cue_id:06d}.png"

            jf_el.text = jacket_name
            ET.indent(tree, space="  ")
            tree.write(xml_path, encoding="utf-8", xml_declaration=True)
            patched += 1
        except Exception:
            pass

    if patched:
        logs.append(f"[OK] Patched jacketFile in {patched} Music.xml file(s)")
    return logs


def build_compile_database_command(payload, resolved_tools):
    exe = resolved_tools["maiforge.exe"]

    cmd = [
        str(exe),
        "db-compile",
        "--input", str(payload["axxx_path"]),
        "--output", str(payload.get("maiforge_output_root") or payload["output_path"]),
        "--category", str(payload["categorization"]),
    ]

    if payload["music_path"]:
        cmd.extend(["--music", str(payload["music_path"])])
    if payload["cover_path"]:
        cmd.extend(["--cover", str(payload["cover_path"])])
    if payload["video_path"]:
        cmd.extend(["--video", str(payload["video_path"])])

    if payload["decimal"]:
        cmd.append("--decimal")
    if payload["ignore_incomplete"]:
        cmd.append("--ignore-incomplete")
    if payload.get("ignore_video"):
        cmd.append("--ignore-video")
    if payload["use_number"]:
        cmd.append("--use-number")
    if payload["json_log"]:
        cmd.append("--json")
    if payload["zip_after"]:
        cmd.append("--zip")
    if payload.get("adx_after"):
        cmd.append("--adx")
    if payload.get("adx_track"):
        cmd.append("--adx-track")
    if payload["collection"]:
        cmd.append("--collection")

    return cmd

# =========================================================
# MP4 HELPERS / RUNNER
# =========================================================

def build_mp4_output_path(dat_file: Path, output_root: Path):
    return conv_build_mp4_output_path(dat_file, output_root)


def find_extracted_m2v_for_dat(dat_file: Path):
    return conv_find_extracted_m2v_for_dat(dat_file)


def build_crid_command(dat_file: Path, resolved_tools: dict):
    return conv_build_crid_command(dat_file, resolved_tools)


def build_ffmpeg_mp4_command(video_input: Path, output_mp4: Path, resolved_tools: dict):
    return conv_build_ffmpeg_mp4_command(video_input, output_mp4, resolved_tools)


def run_mp4_shell(payload, display_mode, resolved_tools):
    input_path = payload["input_path"]
    output_root = payload["output_path"]
    mode_type = payload["mode_type"]
    policy = payload.get("existing_output_policy", "overwrite")

    dat_files = list_files_with_ext(input_path, ".dat")
    log_path = output_root / "mp4_log.txt"

    clear_screen()
    show_header()
    print("MP4 Conversion\n")
    print(f"Mode: {mode_type}")
    print(f"Input: {input_path}")
    print(f"Output: {output_root}\n")
    print(f".dat files found: {len(dat_files)}")

    if not dat_files:
        print("\nNo .dat files found.")
        wait_enter()
        return 0, 0, 1, log_path

    s = load_settings()
    cleanup_policy  = s.get("temp_cleanup", "auto")
    retry_count     = max(1, int(s.get("retry_count", 1)))
    deferred_temps: list = []

    output_root.mkdir(parents=True, exist_ok=True)
    pause_each_file = (display_mode == "2" and mode_type == "single")

    success = 0
    missing = 0
    failed  = 0
    log_lines: list = []
    failed_files: list = []
    start_ts = time.time()

    def _process_dat(dat_file, idx, total):
        """Process one .dat file with retry. Returns ('ok'|'missing'|'failed', log_entries)."""
        out_mp4 = build_mp4_output_path(dat_file, output_root)
        if not should_process_output(out_mp4, policy, []):
            return "skip", [f"[SKIPPED] {dat_file}"]

        crid_cmd     = build_crid_command(dat_file, resolved_tools)
        crid_cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in crid_cmd)

        if display_mode == "2":
            clear_screen()
            show_header()
            print("MP4 Conversion\n")
            print(f"[{idx}/{total}] {dat_file}\n")
            print("Running crid_mod:")
            print(crid_cmd_str)
            print()
        elif display_mode == "1":
            _print_progress(idx, total, dat_file.name, start_ts)

        last_exc = None
        for _attempt in range(retry_count):
            if _attempt > 0:
                if display_mode == "2":
                    print(f"  Retrying ({_attempt}/{retry_count - 1})...")
                elif display_mode == "1":
                    _print_progress(idx, total, f"(retry {_attempt}) {dat_file.name}", start_ts)
            try:
                if display_mode == "2":
                    crid_result = _run_with_spinner(
                        lambda: run_crid_safe(crid_cmd, cwd=SCRIPT_ROOT),
                        "Running crid_mod...",
                    )
                else:
                    crid_result = run_crid_safe(crid_cmd, cwd=SCRIPT_ROOT)
                crid_stdout = crid_result.stdout.strip() if crid_result.stdout else ""
                crid_stderr = crid_result.stderr.strip() if crid_result.stderr else ""

                extracted_m2v = find_extracted_m2v_for_dat(dat_file)
                if extracted_m2v is None or not extracted_m2v.exists():
                    if _attempt < retry_count - 1:
                        continue
                    _space_hint = (
                        " (crid.exe cannot handle paths with spaces — move files to a folder with no spaces)"
                        if " " in str(dat_file) else ""
                    )
                    if display_mode == "2":
                        print(f"No extracted .m2v found.{_space_hint}\n")
                        if pause_each_file:
                            wait_enter()
                    return "missing", [
                        "=" * 80,
                        f"[MISSING] {dat_file}",
                        "STEP: crid_mod output",
                        f"COMMAND: {crid_cmd_str}",
                        f"RETURN CODE: {crid_result.returncode}",
                        "STDOUT:", crid_stdout or "(empty)",
                        "STDERR:", crid_stderr or "(empty)",
                        f"DETAIL: No extracted .m2v found beside source .dat{_space_hint}",
                    ]

                ffmpeg_cmd     = build_ffmpeg_mp4_command(extracted_m2v, out_mp4, resolved_tools)
                ffmpeg_cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in ffmpeg_cmd)

                if display_mode == "2":
                    print(f"Extracted .m2v: {extracted_m2v}\n")
                    print("Running ffmpeg:")
                    print(ffmpeg_cmd_str)
                    print()

                ffmpeg_result  = run_subprocess_safe(ffmpeg_cmd, cwd=SCRIPT_ROOT)
                ffmpeg_stdout  = ffmpeg_result.stdout.strip() if ffmpeg_result.stdout else ""
                ffmpeg_stderr  = ffmpeg_result.stderr.strip() if ffmpeg_result.stderr else ""

                if display_mode == "2":
                    print(f"ffmpeg return code: {ffmpeg_result.returncode}\n")
                    if ffmpeg_stdout:
                        print("FFMPEG STDOUT:")
                        print(ffmpeg_stdout)
                        print()
                    if ffmpeg_stderr:
                        print("FFMPEG STDERR:")
                        print(ffmpeg_stderr)
                        print()
                    if pause_each_file:
                        wait_enter()

                if ffmpeg_result.returncode == 0 and out_mp4.exists():
                    _handle_temp_cleanup(extracted_m2v, cleanup_policy, deferred_temps)
                    _note = {"auto": f"Deleted temp: {extracted_m2v}",
                             "keep": f"Kept temp: {extracted_m2v}",
                             "batch": f"Queued: {extracted_m2v}"}.get(cleanup_policy, "")
                    return "ok", [
                        "=" * 80,
                        f"[OK] {dat_file}",
                        f"EXTRACTED M2V: {extracted_m2v}",
                        f"OUTPUT MP4: {out_mp4}",
                        "STEP: crid_mod",
                        f"COMMAND: {crid_cmd_str}",
                        f"RETURN CODE: {crid_result.returncode}",
                        "STDOUT:", crid_stdout or "(empty)",
                        "STDERR:", crid_stderr or "(empty)",
                        "STEP: ffmpeg",
                        f"COMMAND: {ffmpeg_cmd_str}",
                        f"RETURN CODE: {ffmpeg_result.returncode}",
                        "STDOUT:", ffmpeg_stdout or "(empty)",
                        "STDERR:", ffmpeg_stderr or "(empty)",
                        "CLEANUP:", _note,
                    ]

                # ffmpeg failed — retry or give up
                cleanup_temp_video_files(out_mp4)
                if _attempt < retry_count - 1:
                    continue
                return "failed", [
                    "=" * 80,
                    f"[FAILED] {dat_file}",
                    f"EXTRACTED M2V: {extracted_m2v}",
                    f"OUTPUT MP4: {out_mp4}",
                    "STEP: crid_mod",
                    f"COMMAND: {crid_cmd_str}",
                    f"RETURN CODE: {crid_result.returncode}",
                    "STDOUT:", crid_stdout or "(empty)",
                    "STDERR:", crid_stderr or "(empty)",
                    "STEP: ffmpeg",
                    f"COMMAND: {ffmpeg_cmd_str}",
                    f"RETURN CODE: {ffmpeg_result.returncode}",
                    "STDOUT:", ffmpeg_stdout or "(empty)",
                    "STDERR:", ffmpeg_stderr or "(empty)",
                ]

            except Exception as e:
                last_exc = e
                if _attempt < retry_count - 1:
                    continue
                if display_mode == "2" and pause_each_file:
                    print(f"EXCEPTION: {e}\n")
                    wait_enter()
                return "failed", [
                    "=" * 80,
                    f"[ERROR] {dat_file}",
                    "EXCEPTION:", str(last_exc),
                ]
        return "failed", ["=" * 80, f"[ERROR] {dat_file}", "Unknown failure"]

    for idx, dat_file in enumerate(dat_files, start=1):
        status, entries = _process_dat(dat_file, idx, len(dat_files))
        log_lines.extend(entries)
        if status == "ok":
            success += 1
        elif status == "missing":
            missing += 1
        elif status == "failed":
            failed += 1
            failed_files.append(dat_file)

    if display_mode == "1":
        _end_progress(len(dat_files))

    # ── retry-failed prompt ─────────────────────────────────────────────────
    if failed_files:
        print(f"\n{failed} file(s) failed.")
        if ask_yes_no("Retry failed files now? (y/n): "):
            retry_log: list = []
            for idx, dat_file in enumerate(failed_files, start=1):
                status, entries = _process_dat(dat_file, idx, len(failed_files))
                retry_log.extend(entries)
                if status == "ok":
                    success += 1
                    failed -= 1
                elif status == "missing":
                    missing += 1
                    failed -= 1
            log_lines.append("=" * 80)
            log_lines.append("[RETRY RUN]")
            log_lines.extend(retry_log)
            if display_mode == "1":
                _end_progress(len(failed_files))

    for p in deferred_temps:
        safe_delete(p)

    elapsed = time.time() - start_ts
    with open(log_path, "w", encoding="utf-8") as f:
        for line in log_lines:
            f.write(line + "\n")

    return success, missing, failed, log_path

# =========================================================
# MP3 HELPERS / RUNNER
# =========================================================

def extract_music_numeric_id_from_awb(awb_file: Path):
    m = re.search(r"music(\d{6})$", awb_file.stem, re.IGNORECASE)
    if m:
        return int(m.group(1))
    nums = re.findall(r"\d+", awb_file.stem)
    if nums:
        return int(nums[-1])
    return None


def extract_numeric_id_from_stem(file_path: Path):
    nums = re.findall(r"\d+", file_path.stem)
    if nums:
        return int(nums[-1])
    return None


def build_mp3_output_path(awb_file: Path, output_root: Path):
    return conv_build_mp3_output_path(awb_file, output_root)


def build_temp_wav_path(awb_file: Path):
    return conv_build_temp_wav_path(awb_file)


def build_vgmstream_wav_command(awb_file: Path, temp_wav: Path, resolved_tools: dict):
    return conv_build_vgmstream_wav_command(awb_file, temp_wav, resolved_tools)


def build_ffmpeg_mp3_command(wav_file: Path, output_mp3: Path, resolved_tools: dict):
    return conv_build_ffmpeg_mp3_command(wav_file, output_mp3, resolved_tools)


def run_mp3_shell(payload, display_mode, resolved_tools):
    input_path = payload["input_path"]
    output_root = payload["output_path"]
    mode_type = payload["mode_type"]
    policy = payload.get("existing_output_policy", "overwrite")

    awb_files = list_files_with_ext(input_path, ".awb")
    log_path = output_root / "mp3_log.txt"

    clear_screen()
    show_header()
    print("MP3 Conversion\n")
    print(f"Mode: {mode_type}")
    print(f"Input: {input_path}")
    print(f"Output: {output_root}\n")
    print(f".awb files found: {len(awb_files)}")

    if not awb_files:
        print("\nNo .awb files found.")
        wait_enter()
        return 0, 0, 1, log_path

    s = load_settings()
    cleanup_policy = s.get("temp_cleanup", "auto")
    retry_count    = max(1, int(s.get("retry_count", 1)))
    workers        = max(1, int(s.get("parallel_workers", 2)))
    deferred_temps: list = []

    output_root.mkdir(parents=True, exist_ok=True)
    pause_each_file = (display_mode == "2" and mode_type == "single")

    success = 0
    missing = 0
    failed  = 0
    log_lines: list = []
    failed_files: list = []
    start_ts = time.time()

    def _process_awb_mp3(awb_file, idx, total, _dm=None):
        """_dm overrides display_mode; pass '0' for silent (parallel mode)."""
        dm = _dm if _dm is not None else display_mode
        temp_wav = build_temp_wav_path(awb_file)
        out_mp3  = build_mp3_output_path(awb_file, output_root)
        if not should_process_output(out_mp3, policy, []):
            return "skip", [f"[SKIPPED] {awb_file}"]

        vgm_cmd     = build_vgmstream_wav_command(awb_file, temp_wav, resolved_tools)
        vgm_cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in vgm_cmd)

        if dm == "2":
            clear_screen()
            show_header()
            print("MP3 Conversion\n")
            print(f"[{idx}/{total}] {awb_file}\n")
            print("Running vgmstream:")
            print(vgm_cmd_str)
            print()
        elif dm == "1":
            _print_progress(idx, total, awb_file.name, start_ts)

        last_exc = None
        for _attempt in range(retry_count):
            if _attempt > 0:
                if dm == "2":
                    print(f"  Retrying ({_attempt}/{retry_count - 1})...")
                elif dm == "1":
                    _print_progress(idx, total, f"(retry {_attempt}) {awb_file.name}", start_ts)
            try:
                if temp_wav.exists():
                    safe_delete(temp_wav)

                vgm_result  = run_subprocess_safe(vgm_cmd, cwd=SCRIPT_ROOT)
                vgm_stdout  = vgm_result.stdout.strip() if vgm_result.stdout else ""
                vgm_stderr  = vgm_result.stderr.strip() if vgm_result.stderr else ""

                if vgm_result.returncode != 0:
                    if _attempt < retry_count - 1:
                        continue
                    if dm == "2":
                        print(f"Return code: {vgm_result.returncode}\n")
                        if pause_each_file:
                            wait_enter()
                    return "failed", [
                        "=" * 80,
                        f"[FAILED] {awb_file}",
                        "STEP: vgmstream",
                        f"COMMAND: {vgm_cmd_str}",
                        f"RETURN CODE: {vgm_result.returncode}",
                        "STDOUT:", vgm_stdout or "(empty)",
                        "STDERR:", vgm_stderr or "(empty)",
                    ]

                if not temp_wav.exists():
                    if _attempt < retry_count - 1:
                        continue
                    if dm == "2":
                        print("No extracted .wav found.\n")
                        if pause_each_file:
                            wait_enter()
                    return "missing", [
                        "=" * 80,
                        f"[MISSING] {awb_file}",
                        "STEP: vgmstream output",
                        f"COMMAND: {vgm_cmd_str}",
                        f"RETURN CODE: {vgm_result.returncode}",
                        "STDOUT:", vgm_stdout or "(empty)",
                        "STDERR:", vgm_stderr or "(empty)",
                        "DETAIL: No extracted .wav found beside source .awb",
                    ]

                ffmpeg_cmd     = build_ffmpeg_mp3_command(temp_wav, out_mp3, resolved_tools)
                ffmpeg_cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in ffmpeg_cmd)

                if dm == "2":
                    print(f"Extracted .wav: {temp_wav}\n")
                    print("Running ffmpeg:")
                    print(ffmpeg_cmd_str)
                    print()

                ffmpeg_result = run_subprocess_safe(ffmpeg_cmd, cwd=SCRIPT_ROOT)
                ffmpeg_stdout = ffmpeg_result.stdout.strip() if ffmpeg_result.stdout else ""
                ffmpeg_stderr = ffmpeg_result.stderr.strip() if ffmpeg_result.stderr else ""

                if dm == "2":
                    print(f"ffmpeg return code: {ffmpeg_result.returncode}\n")
                    if ffmpeg_stdout:
                        print("FFMPEG STDOUT:")
                        print(ffmpeg_stdout)
                        print()
                    if ffmpeg_stderr:
                        print("FFMPEG STDERR:")
                        print(ffmpeg_stderr)
                        print()
                    if pause_each_file:
                        wait_enter()

                if ffmpeg_result.returncode == 0 and out_mp3.exists():
                    _handle_temp_cleanup(temp_wav, cleanup_policy, deferred_temps)
                    _note = {"auto": f"Deleted temp: {temp_wav}",
                             "keep": f"Kept temp: {temp_wav}",
                             "batch": f"Queued: {temp_wav}"}.get(cleanup_policy, "")
                    return "ok", [
                        "=" * 80,
                        f"[OK] {awb_file}",
                        f"TEMP WAV: {temp_wav}",
                        f"OUTPUT MP3: {out_mp3}",
                        "STEP: vgmstream",
                        f"COMMAND: {vgm_cmd_str}",
                        f"RETURN CODE: {vgm_result.returncode}",
                        "STDOUT:", vgm_stdout or "(empty)",
                        "STDERR:", vgm_stderr or "(empty)",
                        "STEP: ffmpeg",
                        f"COMMAND: {ffmpeg_cmd_str}",
                        f"RETURN CODE: {ffmpeg_result.returncode}",
                        "STDOUT:", ffmpeg_stdout or "(empty)",
                        "STDERR:", ffmpeg_stderr or "(empty)",
                        "CLEANUP:", _note,
                    ]

                safe_delete(out_mp3)
                if _attempt < retry_count - 1:
                    continue
                return "failed", [
                    "=" * 80,
                    f"[FAILED] {awb_file}",
                    f"TEMP WAV: {temp_wav}",
                    f"OUTPUT MP3: {out_mp3}",
                    "STEP: vgmstream",
                    f"COMMAND: {vgm_cmd_str}",
                    f"RETURN CODE: {vgm_result.returncode}",
                    "STDOUT:", vgm_stdout or "(empty)",
                    "STDERR:", vgm_stderr or "(empty)",
                    "STEP: ffmpeg",
                    f"COMMAND: {ffmpeg_cmd_str}",
                    f"RETURN CODE: {ffmpeg_result.returncode}",
                    "STDOUT:", ffmpeg_stdout or "(empty)",
                    "STDERR:", ffmpeg_stderr or "(empty)",
                ]

            except Exception as e:
                last_exc = e
                if _attempt < retry_count - 1:
                    continue
                if dm == "2" and pause_each_file:
                    print(f"EXCEPTION: {e}\n")
                    wait_enter()
                return "failed", [
                    "=" * 80,
                    f"[ERROR] {awb_file}",
                    "EXCEPTION:", str(last_exc),
                ]
        return "failed", ["=" * 80, f"[ERROR] {awb_file}", "Unknown failure"]

    def _collect(status, entries, awb_file):
        nonlocal success, missing, failed
        log_lines.extend(entries)
        if status == "ok":
            success += 1
        elif status == "missing":
            missing += 1
        elif status == "failed":
            failed += 1
            failed_files.append(awb_file)

    use_parallel = workers > 1 and display_mode != "2"
    if use_parallel:
        import concurrent.futures, threading
        _lock = threading.Lock()
        _done = 0
        if display_mode == "1":
            print(f"\nRunning with {workers} parallel workers...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(_process_awb_mp3, f, 0, len(awb_files), "0"): f
                for f in awb_files
            }
            for future in concurrent.futures.as_completed(future_map):
                awb_file = future_map[future]
                try:
                    status, entries = future.result()
                except Exception as e:
                    status, entries = "failed", ["=" * 80, f"[ERROR] {awb_file}", "EXCEPTION:", str(e)]
                with _lock:
                    _done += 1
                    _collect(status, entries, awb_file)
                    if display_mode == "1":
                        _print_progress(_done, len(awb_files), awb_file.name, start_ts)
    else:
        for idx, awb_file in enumerate(awb_files, start=1):
            status, entries = _process_awb_mp3(awb_file, idx, len(awb_files))
            _collect(status, entries, awb_file)

    if display_mode == "1":
        _end_progress(len(awb_files))

    if failed_files:
        print(f"\n{failed} file(s) failed.")
        if ask_yes_no("Retry failed files now? (y/n): "):
            retry_log: list = []
            for idx, awb_file in enumerate(failed_files, start=1):
                status, entries = _process_awb_mp3(awb_file, idx, len(failed_files))
                retry_log.extend(entries)
                if status == "ok":
                    success += 1
                    failed -= 1
                elif status == "missing":
                    missing += 1
                    failed -= 1
            log_lines.append("=" * 80)
            log_lines.append("[RETRY RUN]")
            log_lines.extend(retry_log)
            if display_mode == "1":
                _end_progress(len(failed_files))

    for p in deferred_temps:
        safe_delete(p)

    elapsed = time.time() - start_ts
    with open(log_path, "w", encoding="utf-8") as f:
        for line in log_lines:
            f.write(line + "\n")

    return success, missing, failed, log_path

# =========================================================
# FLAC HELPERS / RUNNER
# =========================================================

def build_flac_output_path(awb_file: Path, output_root: Path):
    return conv_build_flac_output_path(awb_file, output_root)


def build_flac_encode_command(wav_file: Path, output_flac: Path, resolved_tools: dict):
    return conv_build_flac_encode_command(wav_file, output_flac, resolved_tools)


def run_flac_shell(payload, display_mode, resolved_tools):
    input_path = payload["input_path"]
    output_root = payload["output_path"]
    mode_type = payload["mode_type"]
    policy = payload.get("existing_output_policy", "overwrite")

    awb_files = list_files_with_ext(input_path, ".awb")
    log_path = output_root / "flac_log.txt"

    clear_screen()
    show_header()
    print("FLAC Conversion\n")
    print(f"Mode: {mode_type}")
    print(f"Input: {input_path}")
    print(f"Output: {output_root}\n")
    print(f".awb files found: {len(awb_files)}")

    if not awb_files:
        print("\nNo .awb files found.")
        wait_enter()
        return 0, 0, 1, log_path

    s = load_settings()
    cleanup_policy = s.get("temp_cleanup", "auto")
    retry_count    = max(1, int(s.get("retry_count", 1)))
    workers        = max(1, int(s.get("parallel_workers", 2)))
    deferred_temps: list = []

    output_root.mkdir(parents=True, exist_ok=True)
    pause_each_file = (display_mode == "2" and mode_type == "single")

    success = 0
    missing = 0
    failed  = 0
    log_lines: list = []
    failed_files: list = []
    start_ts = time.time()

    def _process_awb_flac(awb_file, idx, total, _dm=None):
        """_dm overrides display_mode; pass '0' for silent (parallel mode)."""
        dm = _dm if _dm is not None else display_mode
        temp_wav = build_temp_wav_path(awb_file)
        out_flac = build_flac_output_path(awb_file, output_root)
        if not should_process_output(out_flac, policy, []):
            return "skip", [f"[SKIPPED] {awb_file}"]

        vgm_cmd     = build_vgmstream_wav_command(awb_file, temp_wav, resolved_tools)
        vgm_cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in vgm_cmd)

        if dm == "2":
            clear_screen()
            show_header()
            print("FLAC Conversion\n")
            print(f"[{idx}/{total}] {awb_file}\n")
            print("Running vgmstream:")
            print(vgm_cmd_str)
            print()
        elif dm == "1":
            _print_progress(idx, total, awb_file.name, start_ts)

        last_exc = None
        for _attempt in range(retry_count):
            if _attempt > 0:
                if dm == "2":
                    print(f"  Retrying ({_attempt}/{retry_count - 1})...")
                elif dm == "1":
                    _print_progress(idx, total, f"(retry {_attempt}) {awb_file.name}", start_ts)
            try:
                if temp_wav.exists():
                    safe_delete(temp_wav)

                vgm_result  = run_subprocess_safe(vgm_cmd, cwd=SCRIPT_ROOT)
                vgm_stdout  = vgm_result.stdout.strip() if vgm_result.stdout else ""
                vgm_stderr  = vgm_result.stderr.strip() if vgm_result.stderr else ""

                if vgm_result.returncode != 0:
                    if _attempt < retry_count - 1:
                        continue
                    if dm == "2":
                        print(f"Return code: {vgm_result.returncode}\n")
                        if pause_each_file:
                            wait_enter()
                    return "failed", [
                        "=" * 80,
                        f"[FAILED] {awb_file}",
                        "STEP: vgmstream",
                        f"COMMAND: {vgm_cmd_str}",
                        f"RETURN CODE: {vgm_result.returncode}",
                        "STDOUT:", vgm_stdout or "(empty)",
                        "STDERR:", vgm_stderr or "(empty)",
                    ]

                if not temp_wav.exists():
                    if _attempt < retry_count - 1:
                        continue
                    if dm == "2":
                        print("No extracted .wav found.\n")
                        if pause_each_file:
                            wait_enter()
                    return "missing", [
                        "=" * 80,
                        f"[MISSING] {awb_file}",
                        "STEP: vgmstream output",
                        f"COMMAND: {vgm_cmd_str}",
                        f"RETURN CODE: {vgm_result.returncode}",
                        "STDOUT:", vgm_stdout or "(empty)",
                        "STDERR:", vgm_stderr or "(empty)",
                        "DETAIL: No extracted .wav found beside source .awb",
                    ]

                flac_cmd     = build_flac_encode_command(temp_wav, out_flac, resolved_tools)
                flac_cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in flac_cmd)

                if dm == "2":
                    print(f"Extracted .wav: {temp_wav}\n")
                    print("Running flac:")
                    print(flac_cmd_str)
                    print()

                flac_result  = run_subprocess_safe(flac_cmd, cwd=SCRIPT_ROOT)
                flac_stdout  = flac_result.stdout.strip() if flac_result.stdout else ""
                flac_stderr  = flac_result.stderr.strip() if flac_result.stderr else ""

                if dm == "2":
                    print(f"flac return code: {flac_result.returncode}\n")
                    if flac_stdout:
                        print("FLAC STDOUT:")
                        print(flac_stdout)
                        print()
                    if flac_stderr:
                        print("FLAC STDERR:")
                        print(flac_stderr)
                        print()
                    if pause_each_file:
                        wait_enter()

                if flac_result.returncode == 0 and out_flac.exists():
                    _handle_temp_cleanup(temp_wav, cleanup_policy, deferred_temps)
                    _note = {"auto": f"Deleted temp: {temp_wav}",
                             "keep": f"Kept temp: {temp_wav}",
                             "batch": f"Queued: {temp_wav}"}.get(cleanup_policy, "")
                    return "ok", [
                        "=" * 80,
                        f"[OK] {awb_file}",
                        f"TEMP WAV: {temp_wav}",
                        f"OUTPUT FLAC: {out_flac}",
                        "STEP: vgmstream",
                        f"COMMAND: {vgm_cmd_str}",
                        f"RETURN CODE: {vgm_result.returncode}",
                        "STDOUT:", vgm_stdout or "(empty)",
                        "STDERR:", vgm_stderr or "(empty)",
                        "STEP: flac",
                        f"COMMAND: {flac_cmd_str}",
                        f"RETURN CODE: {flac_result.returncode}",
                        "STDOUT:", flac_stdout or "(empty)",
                        "STDERR:", flac_stderr or "(empty)",
                        "CLEANUP:", _note,
                    ]

                safe_delete(out_flac)
                if _attempt < retry_count - 1:
                    continue
                return "failed", [
                    "=" * 80,
                    f"[FAILED] {awb_file}",
                    f"TEMP WAV: {temp_wav}",
                    f"OUTPUT FLAC: {out_flac}",
                    "STEP: vgmstream",
                    f"COMMAND: {vgm_cmd_str}",
                    f"RETURN CODE: {vgm_result.returncode}",
                    "STDOUT:", vgm_stdout or "(empty)",
                    "STDERR:", vgm_stderr or "(empty)",
                    "STEP: flac",
                    f"COMMAND: {flac_cmd_str}",
                    f"RETURN CODE: {flac_result.returncode}",
                    "STDOUT:", flac_stdout or "(empty)",
                    "STDERR:", flac_stderr or "(empty)",
                ]

            except Exception as e:
                last_exc = e
                if _attempt < retry_count - 1:
                    continue
                if dm == "2" and pause_each_file:
                    print(f"EXCEPTION: {e}\n")
                    wait_enter()
                return "failed", [
                    "=" * 80,
                    f"[ERROR] {awb_file}",
                    "EXCEPTION:", str(last_exc),
                ]
        return "failed", ["=" * 80, f"[ERROR] {awb_file}", "Unknown failure"]

    def _collect(status, entries, awb_file):
        nonlocal success, missing, failed
        log_lines.extend(entries)
        if status == "ok":
            success += 1
        elif status == "missing":
            missing += 1
        elif status == "failed":
            failed += 1
            failed_files.append(awb_file)

    use_parallel = workers > 1 and display_mode != "2"
    if use_parallel:
        import concurrent.futures, threading
        _lock = threading.Lock()
        _done = 0
        if display_mode == "1":
            print(f"\nRunning with {workers} parallel workers...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(_process_awb_flac, f, 0, len(awb_files), "0"): f
                for f in awb_files
            }
            for future in concurrent.futures.as_completed(future_map):
                awb_file = future_map[future]
                try:
                    status, entries = future.result()
                except Exception as e:
                    status, entries = "failed", ["=" * 80, f"[ERROR] {awb_file}", "EXCEPTION:", str(e)]
                with _lock:
                    _done += 1
                    _collect(status, entries, awb_file)
                    if display_mode == "1":
                        _print_progress(_done, len(awb_files), awb_file.name, start_ts)
    else:
        for idx, awb_file in enumerate(awb_files, start=1):
            status, entries = _process_awb_flac(awb_file, idx, len(awb_files))
            _collect(status, entries, awb_file)

    if display_mode == "1":
        _end_progress(len(awb_files))

    if failed_files:
        print(f"\n{failed} file(s) failed.")
        if ask_yes_no("Retry failed files now? (y/n): "):
            retry_log: list = []
            for idx, awb_file in enumerate(failed_files, start=1):
                status, entries = _process_awb_flac(awb_file, idx, len(failed_files))
                retry_log.extend(entries)
                if status == "ok":
                    success += 1
                    failed -= 1
                elif status == "missing":
                    missing += 1
                    failed -= 1
            log_lines.append("=" * 80)
            log_lines.append("[RETRY RUN]")
            log_lines.extend(retry_log)
            if display_mode == "1":
                _end_progress(len(failed_files))

    for p in deferred_temps:
        safe_delete(p)

    elapsed = time.time() - start_ts
    with open(log_path, "w", encoding="utf-8") as f:
        for line in log_lines:
            f.write(line + "\n")

    return success, missing, failed, log_path

# =========================================================
# CHART RUNNER
# =========================================================

def build_chart_conversion_command(chart_input: Path, output_path: Path, resolved_tools: dict):
    exe = resolved_tools["maiforge.exe"]
    return [
        str(exe),
        "ma2-compile",
        "--input", str(chart_input),
        "--output", str(output_path),
        "--format", "Simai",
    ]


def run_chart_shell(payload, display_mode, resolved_tools):
    input_path = payload["input_path"]
    output_path = payload["output_path"]
    policy = payload.get("existing_output_policy", "overwrite")
    log_path = output_path / "chart_log.txt"

    clear_screen()
    show_header()
    print("Chart Conversion\n")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}\n")

    if not (input_path.is_file() and input_path.suffix.lower() == ".ma2"):
        print("Invalid chart file.")
        wait_enter()
        return 0, 0, 1, log_path

    if output_folder_has_any_files(output_path):
        if policy == "skip":
            output_path.mkdir(parents=True, exist_ok=True)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("[SKIPPED]\n")
                f.write(f"CHART FILE: {input_path}\n")
                f.write(f"OUTPUT DIR: {output_path}\n")
                f.write("DETAIL: Existing output folder kept.\n")
            return 0, 0, 0, log_path
        elif policy == "overwrite":
            clear_folder_contents(output_path)

    cmd = build_chart_conversion_command(input_path, output_path, resolved_tools)
    cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in cmd)

    if display_mode == "2":
        print("Running command:")
        print(cmd_str)
        print()

    try:
        result = run_subprocess_safe(cmd, cwd=SCRIPT_ROOT)
        stdout_text = result.stdout.strip() if result.stdout else ""
        stderr_text = result.stderr.strip() if result.stderr else ""

        if display_mode == "2":
            print(f"Return code: {result.returncode}\n")
            if stdout_text:
                print("STDOUT:")
                print(stdout_text)
                print()
            if stderr_text:
                print("STDERR:")
                print(stderr_text)
                print()
            countdown_after_conversion(5, label="Continuing")

        log_lines = [
            "=" * 80,
            "[OK]" if result.returncode == 0 else "[FAILED]",
            f"CHART FILE: {input_path}",
            f"COMMAND: {cmd_str}",
            f"RETURN CODE: {result.returncode}",
            "STDOUT:",
            stdout_text if stdout_text else "(empty)",
            "STDERR:",
            stderr_text if stderr_text else "(empty)",
        ]

        output_path.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            for line in log_lines:
                f.write(line + "\n")

        if result.returncode == 0:
            if payload.get("zip_after"):
                import zipfile as _zf
                zip_dest = output_path.with_suffix(".zip")
                with _zf.ZipFile(zip_dest, "w", _zf.ZIP_DEFLATED) as zf:
                    for f in output_path.rglob("*"):
                        zf.write(f, f.relative_to(output_path.parent))
                import shutil as _sh
                _sh.rmtree(output_path)
            if payload.get("adx_after"):
                import zipfile as _zf
                adx_dest = output_path.with_suffix(".adx")
                with _zf.ZipFile(adx_dest, "w", _zf.ZIP_DEFLATED) as zf:
                    for f in output_path.rglob("*"):
                        zf.write(f, f.relative_to(output_path.parent))
                if not payload.get("zip_after"):  # only delete once
                    import shutil as _sh
                    _sh.rmtree(output_path)
            return 1, 0, 0, log_path
        return 0, 0, 1, log_path

    except Exception as e:
        output_path.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("[ERROR]\n")
            f.write(f"CHART FILE: {input_path}\n")
            f.write(f"COMMAND: {cmd_str}\n")
            f.write("EXCEPTION:\n")
            f.write(str(e) + "\n")

        if display_mode == "2":
            print("EXCEPTION:")
            print(str(e))
            print()
            countdown_after_conversion(5, label="Continuing")

        return 0, 0, 1, log_path

# =========================================================
# IMAGE (.ab) HELPERS / RUNNER
# =========================================================

def move_image_files_to_root(source_dir: Path, dest_dir: Path):
    return conv_move_image_files_to_root(source_dir, dest_dir)


def flatten_assetstudio_texture2d_output(output_root: Path):
    return conv_flatten_assetstudio_texture2d_output(output_root)


def build_assetstudio_command(asset_input: Path, output_dir: Path, resolved_tools: dict):
    return conv_build_assetstudio_command(asset_input, output_dir, resolved_tools)


def run_image_shell(payload, display_mode, resolved_tools):
    input_path = payload["input_path"]
    output_root = payload["output_path"]
    mode_type = payload["mode_type"]
    policy = payload.get("existing_output_policy", "overwrite")

    log_path = output_root / "image_log.txt"
    output_root.mkdir(parents=True, exist_ok=True)

    clear_screen()
    show_header()
    print("Image Conversion\n")
    print(f"Mode: {mode_type}")
    print(f"Input: {input_path}")
    print(f"Output: {output_root}\n")

    if mode_type == "single":
        if not (input_path.is_file() and input_path.suffix.lower() == ".ab"):
            print("Invalid .ab file.")
            wait_enter()
            return 0, 0, 1, log_path

        if output_folder_has_relevant_image_outputs(output_root):
            if policy == "skip":
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write("=" * 80 + "\n")
                    f.write("[SKIPPED]\n")
                    f.write(f"INPUT: {input_path}\n")
                    f.write(f"OUTPUT DIR: {output_root}\n")
                    f.write("DETAIL: Existing image outputs kept.\n")
                return 0, 0, 0, log_path
            elif policy == "overwrite":
                cleanup_relevant_image_outputs(output_root)

        cmd = build_assetstudio_command(input_path, output_root, resolved_tools)
        cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in cmd)

        if display_mode == "2":
            print("Running AssetStudioCLI:")
            print(cmd_str)
            print()

        try:
            result = run_subprocess_safe(cmd, cwd=SCRIPT_ROOT)
            stdout_text = result.stdout.strip() if result.stdout else ""
            stderr_text = result.stderr.strip() if result.stderr else ""
            flattened_count = flatten_assetstudio_texture2d_output(output_root)

            if display_mode == "2":
                print(f"Return code: {result.returncode}\n")
                if stdout_text:
                    print("STDOUT:")
                    print(stdout_text)
                    print()
                if stderr_text:
                    print("STDERR:")
                    print(stderr_text)
                    print()
                countdown_after_conversion(5, label="Continuing")

            log_lines = [
                "=" * 80,
                "[OK]" if result.returncode == 0 else "[FAILED]",
                f"INPUT: {input_path}",
                f"OUTPUT DIR: {output_root}",
                f"COMMAND: {cmd_str}",
                f"RETURN CODE: {result.returncode}",
                "STDOUT:",
                stdout_text if stdout_text else "(empty)",
                "STDERR:",
                stderr_text if stderr_text else "(empty)",
            ]

            with open(log_path, "w", encoding="utf-8") as f:
                for line in log_lines:
                    f.write(line + "\n")

            if result.returncode == 0:
                return 1, 0, 0, log_path
            return 0, 0, 1, log_path

        except Exception as e:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("[ERROR]\n")
                f.write(f"INPUT: {input_path}\n")
                f.write(f"OUTPUT DIR: {output_root}\n")
                f.write("EXCEPTION:\n")
                f.write(str(e) + "\n")

            if display_mode == "2":
                print("EXCEPTION:")
                print(str(e))
                print()
                countdown_after_conversion(5, label="Continuing")

            return 0, 0, 1, log_path

    else:
        if not input_path.is_dir():
            print("Invalid folder input.")
            wait_enter()
            return 0, 0, 1, log_path

        ab_files = list_files_with_ext(input_path, ".ab")

        print(f".ab files found: {len(ab_files)}")

        if not ab_files:
            print("\nNo .ab files found.")
            wait_enter()
            return 0, 0, 1, log_path

        if output_folder_has_relevant_image_outputs(output_root):
            if policy == "skip":
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write("=" * 80 + "\n")
                    f.write("[SKIPPED]\n")
                    f.write(f"INPUT FOLDER: {input_path}\n")
                    f.write(f"OUTPUT DIR: {output_root}\n")
                    f.write("DETAIL: Existing image outputs kept.\n")
                return 0, 0, 0, log_path
            elif policy == "overwrite":
                cleanup_relevant_image_outputs(output_root)

        cmd = build_assetstudio_command(input_path, output_root, resolved_tools)
        cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in cmd)

        if display_mode == "2":
            print("Running AssetStudioCLI on folder:")
            print(cmd_str)
            print()

        try:
            result = run_subprocess_safe(cmd, cwd=SCRIPT_ROOT)
            stdout_text = result.stdout.strip() if result.stdout else ""
            stderr_text = result.stderr.strip() if result.stderr else ""
            flattened_count = flatten_assetstudio_texture2d_output(output_root)

            if display_mode == "2":
                print(f"Return code: {result.returncode}\n")
                if stdout_text:
                    print("STDOUT:")
                    print(stdout_text)
                    print()
                if stderr_text:
                    print("STDERR:")
                    print(stderr_text)
                    print()
                countdown_after_conversion(5, label="Continuing")

            log_lines = [
                "=" * 80,
                "[OK]" if result.returncode == 0 else "[FAILED]",
                f"INPUT FOLDER: {input_path}",
                f"OUTPUT DIR: {output_root}",
                f"COMMAND: {cmd_str}",
                f"RETURN CODE: {result.returncode}",
                "STDOUT:",
                stdout_text if stdout_text else "(empty)",
                "STDERR:",
                stderr_text if stderr_text else "(empty)",
            ]

            with open(log_path, "w", encoding="utf-8") as f:
                for line in log_lines:
                    f.write(line + "\n")

            if result.returncode == 0:
                return 1, 0, 0, log_path
            return 0, 0, 1, log_path

        except Exception as e:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("[ERROR]\n")
                f.write(f"INPUT FOLDER: {input_path}\n")
                f.write(f"OUTPUT DIR: {output_root}\n")
                f.write("EXCEPTION:\n")
                f.write(str(e) + "\n")

            if display_mode == "2":
                print("EXCEPTION:")
                print(str(e))
                print()
                countdown_after_conversion(5, label="Continuing")

            return 0, 0, 1, log_path

# =========================================================
# DATABASE AUTO-BUILD HELPERS
# =========================================================

def parse_music_xml_basic(xml_path: Path):
    return parser_parse_music_xml_basic(xml_path)


def build_numeric_file_index(root: Path, ext: str):
    return parser_build_numeric_file_index(root, ext)


def choose_best_numeric_match(candidates):
    return parser_choose_best_numeric_match(candidates)


def resolve_awb_for_song(sound_root: Path, awb_index, song_id: int, cue_id: int):
    return parser_resolve_awb_for_song(sound_root, awb_index, song_id, cue_id)


def resolve_dat_for_song(movie_root: Path, song_id: int, cue_id: int = None):
    return parser_resolve_dat_for_song(movie_root, song_id, cue_id)

# NOTE: parser/database helper wrappers above are kept intentionally for
# compatibility with existing call sites while moving implementations to modules.


def auto_build_music_assets(axxx_root: Path, resolved_tools: dict, display_mode: str, existing_policy: str, progress_callback=None):
    music_root = axxx_root / "music"
    sound_root = axxx_root / "SoundData"
    out_root = axxx_root / "musicMP3"
    out_root.mkdir(parents=True, exist_ok=True)

    log_lines = []
    success = 0
    missing = 0
    failed = 0
    cleanup_policy = load_settings().get("temp_cleanup", "auto")
    deferred_temps: list = []

    if not music_root.exists() or not sound_root.exists():
        return out_root, success, missing, failed, ["Music or SoundData folder not found."]

    if existing_policy == "overwrite" and out_root.exists():
        for old_mp3 in out_root.rglob("*.mp3"):
            safe_delete(old_mp3)

    awb_index = build_numeric_file_index(sound_root, ".awb")
    xml_files = sorted(music_root.rglob("Music.xml"))

    for xml_path in xml_files:
        try:
            meta = parse_music_xml_basic(xml_path)
        except Exception as e:
            failed += 1
            log_lines.extend(["=" * 80, f"[ERROR] {xml_path}", f"EXCEPTION: {e}"])
            continue

        cue_id = meta["cue_id"]
        song_id = meta["song_id"]

        if song_id is None or cue_id is None:
            missing += 1
            log_lines.extend(["=" * 80, f"[MISSING] {xml_path}", "DETAIL: song_id or cue_id missing in Music.xml"])
            continue

        awb_file = resolve_awb_for_song(sound_root, awb_index, song_id, cue_id)

        if awb_file is None:
            missing += 1
            log_lines.extend(["=" * 80, f"[MISSING] {xml_path}", f"DETAIL: No AWB found for song_id {song_id} / cue_id {cue_id}"])
            continue

        temp_wav = build_temp_wav_path(awb_file)
        resolved_audio_id = extract_music_numeric_id_from_awb(awb_file)
        if resolved_audio_id is None:
            resolved_audio_id = cue_id if cue_id is not None else song_id

        out_mp3 = out_root / f"music{resolved_audio_id:06d}.mp3"

        if out_mp3.exists():
            if existing_policy == "skip":
                log_lines.extend(["=" * 80, f"[SKIPPED] {out_mp3.name}", "DETAIL: Existing file kept."])
                if progress_callback:
                    progress_callback(f"MP3: {awb_file.name}")
                continue
            elif existing_policy == "overwrite":
                safe_delete(out_mp3)

        vgm_cmd = build_vgmstream_wav_command(awb_file, temp_wav, resolved_tools)
        ffmpeg_cmd = build_ffmpeg_mp3_command(temp_wav, out_mp3, resolved_tools)

        try:
            if temp_wav.exists():
                safe_delete(temp_wav)

            vgm_result = run_subprocess_safe(vgm_cmd, cwd=SCRIPT_ROOT)
            if vgm_result.returncode != 0 or not temp_wav.exists():
                failed += 1
                log_lines.extend([
                    "=" * 80,
                    f"[FAILED] music{resolved_audio_id:06d}.mp3",
                    f"SOURCE AWB: {awb_file}",
                    f"song_id: {song_id}",
                    f"cue_id: {cue_id}",
                    "STEP: vgmstream",
                    vgm_result.stdout.strip() if vgm_result.stdout else "(empty)",
                    vgm_result.stderr.strip() if vgm_result.stderr else "(empty)",
                ])
                _handle_temp_cleanup(temp_wav, cleanup_policy, deferred_temps)
                continue

            ffmpeg_result = run_subprocess_safe(ffmpeg_cmd, cwd=SCRIPT_ROOT)
            if ffmpeg_result.returncode == 0 and out_mp3.exists():
                _handle_temp_cleanup(temp_wav, cleanup_policy, deferred_temps)
                success += 1
                log_lines.extend([
                    "=" * 80,
                    f"[OK] music{resolved_audio_id:06d}.mp3",
                    f"SOURCE AWB: {awb_file}",
                    f"song_id: {song_id}",
                    f"cue_id: {cue_id}",
                ])
            else:
                safe_delete(out_mp3)
                _handle_temp_cleanup(temp_wav, cleanup_policy, deferred_temps)
                failed += 1
                log_lines.extend([
                    "=" * 80,
                    f"[FAILED] music{resolved_audio_id:06d}.mp3",
                    f"SOURCE AWB: {awb_file}",
                    f"song_id: {song_id}",
                    f"cue_id: {cue_id}",
                    "STEP: ffmpeg",
                    ffmpeg_result.stdout.strip() if ffmpeg_result.stdout else "(empty)",
                    ffmpeg_result.stderr.strip() if ffmpeg_result.stderr else "(empty)",
                ])

        except Exception as e:
            _handle_temp_cleanup(temp_wav, cleanup_policy, deferred_temps)
            failed += 1
            log_lines.extend([
                "=" * 80,
                f"[ERROR] music{resolved_audio_id:06d}.mp3",
                f"SOURCE AWB: {awb_file}",
                f"EXCEPTION: {e}",
            ])
        finally:
            if progress_callback:
                progress_callback(f"MP3: {awb_file.name}")

    for p in deferred_temps:
        safe_delete(p)

    return out_root, success, missing, failed, log_lines


def auto_build_video_assets(axxx_root: Path, resolved_tools: dict, display_mode: str, existing_policy: str, progress_callback=None):
    movie_root = axxx_root / "MovieData"
    music_root = axxx_root / "music"
    out_root = axxx_root / "Movie"
    out_root.mkdir(parents=True, exist_ok=True)

    log_lines = []
    success = 0
    missing = 0
    failed = 0
    cleanup_policy = load_settings().get("temp_cleanup", "auto")
    deferred_temps: list = []

    if not movie_root.exists() or not music_root.exists():
        return out_root, success, missing, failed, ["MovieData or music folder not found."]

    if existing_policy == "overwrite" and out_root.exists():
        for old_mp4 in out_root.rglob("*.mp4"):
            safe_delete(old_mp4)

    xml_files = sorted(music_root.rglob("Music.xml"))

    for xml_path in xml_files:
        try:
            meta = parse_music_xml_basic(xml_path)
        except Exception as e:
            failed += 1
            log_lines.extend(["=" * 80, f"[ERROR] {xml_path}", f"EXCEPTION: {e}"])
            continue

        song_id = meta["song_id"]
        if song_id is None:
            missing += 1
            log_lines.extend(["=" * 80, f"[MISSING] {xml_path}", "DETAIL: song_id missing in Music.xml"])
            continue

        cue_id = meta["cue_id"]
        dat_file = resolve_dat_for_song(movie_root, song_id, cue_id)
        if dat_file is None:
            missing += 1
            log_lines.extend(["=" * 80, f"[MISSING] {xml_path}", f"DETAIL: No DAT found for song_id {song_id}"])
            continue

        # MaichartConverter reads musicID = filename.Substring(2, 4), so filenames must be 6-digit.
        out_mp4 = out_root / f"{dat_file.stem}.mp4"

        if out_mp4.exists():
            if existing_policy == "skip":
                log_lines.extend(["=" * 80, f"[SKIPPED] {out_mp4.name}", "DETAIL: Existing file kept."])
                if progress_callback:
                    progress_callback(f"MP4: {dat_file.name}")
                continue
            elif existing_policy == "overwrite":
                safe_delete(out_mp4)

        crid_cmd = build_crid_command(dat_file, resolved_tools)

        try:
            extracted_m2v = dat_file.with_suffix(".m2v")
            if extracted_m2v.exists():
                safe_delete(extracted_m2v)

            crid_result = run_crid_safe(crid_cmd, cwd=SCRIPT_ROOT)
            extracted_m2v = find_extracted_m2v_for_dat(dat_file)

            # crid sometimes exits non-zero even on success — only truly fail if the m2v wasn't created
            if extracted_m2v is None or not extracted_m2v.exists():
                failed += 1
                log_lines.extend([
                    "=" * 80,
                    f"[FAILED] {out_mp4.name}",
                    f"SOURCE DAT: {dat_file}",
                    f"song_id: {song_id}",
                    "STEP: crid_mod (no m2v output)",
                    f"RETURN CODE: {crid_result.returncode}",
                    crid_result.stdout.strip() if crid_result.stdout else "(empty)",
                    crid_result.stderr.strip() if crid_result.stderr else "(empty)",
                ])
                continue

            # ── Static video check (database pipeline) ────────
            ffprobe_exe = resolved_tools.get("ffprobe.exe")
            ffprobe_str = str(ffprobe_exe) if ffprobe_exe else None
            if conv_is_static_video(extracted_m2v, ffprobe_str):
                _static_mode = mp4_load_config().get("static_video", "loop")
                if _static_mode == "skip":
                    log_lines.extend([
                        "=" * 80,
                        f"[STATIC-SKIP] {dat_file.name}",
                        f"song_id: {song_id}",
                        "DETAIL: Static video detected — skipped per settings.",
                    ])
                    missing += 1
                    continue
                # loop/stretch
                # mp3 is named by cue_id (e.g. music001993.mp3 for song 11993),
                # NOT by song_id (which would give music011993.mp3 — wrong).
                _musicmp3_dir = movie_root.parent / "musicMP3"
                _cue = cue_id if cue_id is not None else song_id
                _mp3_by_cue  = _musicmp3_dir / f"music{_cue:06d}.mp3"
                _mp3_by_song = _musicmp3_dir / f"music{song_id:06d}.mp3"
                _mp3_candidate = _mp3_by_cue if _mp3_by_cue.exists() else _mp3_by_song
                _duration = conv_get_audio_duration(_mp3_candidate, ffprobe_str) if _mp3_candidate.exists() else None
                if _duration is None:
                    from converters.mp4 import _STATIC_FALLBACK_DURATION
                    _duration = _STATIC_FALLBACK_DURATION
                ffmpeg_cmd = conv_build_ffmpeg_static_stretch_command(extracted_m2v, out_mp4, _duration, resolved_tools)
                log_lines.extend([
                    "=" * 80,
                    f"[STATIC-STRETCH] {dat_file.name}",
                    f"song_id: {song_id}",
                    f"DETAIL: Static video detected — looping to {_duration:.1f}s.",
                ])
            else:
                ffmpeg_cmd = build_ffmpeg_mp4_command(extracted_m2v, out_mp4, resolved_tools)

            ffmpeg_result = run_subprocess_safe(ffmpeg_cmd, cwd=SCRIPT_ROOT)

            if ffmpeg_result.returncode == 0 and out_mp4.exists():
                _handle_temp_cleanup(extracted_m2v, cleanup_policy, deferred_temps)
                success += 1
                log_lines.extend(["=" * 80, f"[OK] {out_mp4.name}", f"SOURCE DAT: {dat_file}", f"song_id: {song_id}"])
            else:
                safe_delete(out_mp4)
                _handle_temp_cleanup(extracted_m2v, cleanup_policy, deferred_temps)
                failed += 1
                log_lines.extend([
                    "=" * 80,
                    f"[FAILED] {out_mp4.name}",
                    f"SOURCE DAT: {dat_file}",
                    f"song_id: {song_id}",
                    "STEP: ffmpeg",
                    ffmpeg_result.stdout.strip() if ffmpeg_result.stdout else "(empty)",
                    ffmpeg_result.stderr.strip() if ffmpeg_result.stderr else "(empty)",
                ])

        except Exception as e:
            _handle_temp_cleanup(dat_file.with_suffix(".m2v"), cleanup_policy, deferred_temps)
            failed += 1
            log_lines.extend([
                "=" * 80,
                f"[ERROR] {out_mp4.name}",
                f"SOURCE DAT: {dat_file}",
                f"song_id: {song_id}",
                f"EXCEPTION: {e}",
            ])
        finally:
            if progress_callback:
                progress_callback(f"MP4: {dat_file.name}")

    for p in deferred_temps:
        safe_delete(p)

    return out_root, success, missing, failed, log_lines


def auto_build_cover_assets(axxx_root: Path, resolved_tools: dict, display_mode: str, existing_policy: str, progress_callback=None):
    source_root = axxx_root / "AssetBundleImages" / "jacket"
    out_root = axxx_root / "Jackets"
    out_root.mkdir(parents=True, exist_ok=True)

    log_lines = []
    success = 0
    missing = 0
    failed = 0

    if not source_root.exists() or not source_root.is_dir():
        return out_root, success, 1, failed, ["Jacket source folder not found."]

    ab_files = list_files_with_ext(source_root, ".ab")
    if not ab_files:
        return out_root, success, 1, failed, ["No .ab files found in AssetBundleImages/jacket."]

    if output_folder_has_relevant_image_outputs(out_root):
        if existing_policy == "overwrite":
            cleanup_relevant_image_outputs(out_root)
        elif existing_policy == "skip":
            log_lines.extend([
                "=" * 80,
                f"[SKIPPED] {out_root}",
                "DETAIL: Existing jacket outputs kept.",
            ])
            if progress_callback:
                for ab_file in ab_files:
                    progress_callback(f"Jacket: {ab_file.name}")
            return out_root, 1, 0, 0, log_lines

    cmd = build_assetstudio_command(source_root, out_root, resolved_tools)

    try:
        result = run_subprocess_safe(cmd, cwd=SCRIPT_ROOT)
        stdout_text = result.stdout.strip() if result.stdout else ""
        stderr_text = result.stderr.strip() if result.stderr else ""
        flattened_count = flatten_assetstudio_texture2d_output(out_root)

        if result.returncode == 0 and output_folder_has_relevant_image_outputs(out_root):
            success = 1
            log_lines.extend([
                "=" * 80,
                "[OK] Jacket auto-build",
                f"SOURCE FOLDER: {source_root}",
                f"OUTPUT DIR: {out_root}",
                "COMMAND: " + " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in cmd),
                f"FLATTENED TEXTURE2D FILES: {flattened_count}",
                "STDOUT:",
                stdout_text if stdout_text else "(empty)",
                "STDERR:",
                stderr_text if stderr_text else "(empty)",
            ])
        else:
            failed = 1
            log_lines.extend([
                "=" * 80,
                "[FAILED] Jacket auto-build",
                f"SOURCE FOLDER: {source_root}",
                f"OUTPUT DIR: {out_root}",
                f"COMMAND: " + " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in cmd),
                "STDOUT:",
                stdout_text if stdout_text else "(empty)",
                "STDERR:",
                stderr_text if stderr_text else "(empty)",
            ])

    except Exception as e:
        failed = 1
        log_lines.extend([
            "=" * 80,
            "[ERROR] Jacket auto-build",
            f"SOURCE FOLDER: {source_root}",
            f"OUTPUT DIR: {out_root}",
            f"EXCEPTION: {e}",
        ])

    if progress_callback:
        for ab_file in ab_files:
            progress_callback(f"Jacket: {ab_file.name}")
    return out_root, success, missing, failed, log_lines

# =========================================================
# DATABASE RUNNER
# =========================================================

def cleanup_database_temp_dirs(temp_dirs, log_lines=None):
    if not temp_dirs:
        return
    for temp_dir in temp_dirs:
        try:
            if temp_dir.exists() and temp_dir.is_dir():
                safe_rmtree(temp_dir)
                if log_lines is not None:
                    log_lines.extend([
                        "=" * 80,
                        "[CLEANUP]",
                        f"Deleted temp folder: {temp_dir}",
                    ])
        except Exception as e:
            if log_lines is not None:
                log_lines.extend([
                    "=" * 80,
                    "[CLEANUP FAILED]",
                    f"TEMP FOLDER: {temp_dir}",
                    f"EXCEPTION: {e}",
                ])


def build_cli_parser():
    parser = argparse.ArgumentParser(
    prog="maioconverter",
    description="maimai AIO Conversion Tool",
    epilog=(
        "Examples:\n"
        "  maioconverter mp3 single --input FILE.awb --output OUTDIR\n"
        "  maioconverter mp4 batch --input DIR --output OUTDIR\n"
        "  maioconverter db --root A000 --output OUTDIR --categorize 2 --auto-build\n\n"
        "Use '<command> --help' or '<command> <mode> --help' for more details."
    ),
    formatter_class=argparse.RawTextHelpFormatter,
)
    subparsers = parser.add_subparsers(dest="command")

    # =====================================================
    # MP4
    # =====================================================
    mp4_parser = subparsers.add_parser("mp4",help="Convert .dat to .mp4",description="Convert maimai .dat video files into .mp4.",)
    mp4_sub = mp4_parser.add_subparsers(dest="mode_type")

    mp4_single = mp4_sub.add_parser("single", help="Single .dat conversion")
    mp4_single.add_argument("--input", required=True)
    mp4_single.add_argument("--output", required=True)
    mp4_single.add_argument("--policy", choices=["overwrite", "skip"], default="overwrite")
    mp4_single.add_argument("--display", choices=["1", "2"], default="2")

    mp4_batch = mp4_sub.add_parser("batch", help="Batch .dat conversion")
    mp4_batch.add_argument("--input", required=True)
    mp4_batch.add_argument("--output", required=True)
    mp4_batch.add_argument("--policy", choices=["overwrite", "skip"], default="overwrite")
    mp4_batch.add_argument("--display", choices=["1", "2"], default="1")

    # =====================================================
    # MP3
    # =====================================================
    mp3_parser = subparsers.add_parser("mp3",help="Convert .awb to .mp3",description="Convert maimai .awb audio files into .mp3.",)
    mp3_sub = mp3_parser.add_subparsers(dest="mode_type")

    mp3_single = mp3_sub.add_parser("single", help="Single .awb conversion")
    mp3_single.add_argument("--input", required=True)
    mp3_single.add_argument("--output", required=True)
    mp3_single.add_argument("--policy", choices=["overwrite", "skip"], default="overwrite")
    mp3_single.add_argument("--display", choices=["1", "2"], default="2")

    mp3_batch = mp3_sub.add_parser("batch", help="Batch .awb conversion")
    mp3_batch.add_argument("--input", required=True)
    mp3_batch.add_argument("--output", required=True)
    mp3_batch.add_argument("--policy", choices=["overwrite", "skip"], default="overwrite")
    mp3_batch.add_argument("--display", choices=["1", "2"], default="1")

    # =====================================================
    # FLAC
    # =====================================================
    flac_parser = subparsers.add_parser("flac",help="Convert .awb to .flac",description="Convert maimai .awb audio files into .flac.",)
    flac_sub = flac_parser.add_subparsers(dest="mode_type")

    flac_single = flac_sub.add_parser("single", help="Single .awb conversion")
    flac_single.add_argument("--input", required=True)
    flac_single.add_argument("--output", required=True)
    flac_single.add_argument("--policy", choices=["overwrite", "skip"], default="overwrite")
    flac_single.add_argument("--display", choices=["1", "2"], default="2")

    flac_batch = flac_sub.add_parser("batch", help="Batch .awb conversion")
    flac_batch.add_argument("--input", required=True)
    flac_batch.add_argument("--output", required=True)
    flac_batch.add_argument("--policy", choices=["overwrite", "skip"], default="overwrite")
    flac_batch.add_argument("--display", choices=["1", "2"], default="1")

    # =====================================================
    # IMAGE
    # =====================================================
    image_parser = subparsers.add_parser("image",help="Convert .ab image bundles",description="Convert .ab image bundles using AssetStudio CLI.",)
    image_sub = image_parser.add_subparsers(dest="mode_type")

    image_single = image_sub.add_parser("single", help="Single .ab conversion")
    image_single.add_argument("--input", required=True)
    image_single.add_argument("--output", required=True)
    image_single.add_argument("--policy", choices=["overwrite", "skip"], default="overwrite")
    image_single.add_argument("--display", choices=["1", "2"], default="2")

    image_batch = image_sub.add_parser("batch", help="Batch .ab conversion")
    image_batch.add_argument("--input", required=True)
    image_batch.add_argument("--output", required=True)
    image_batch.add_argument("--policy", choices=["overwrite", "skip"], default="overwrite")
    image_batch.add_argument("--display", choices=["1", "2"], default="1")

    # =====================================================
    # CHART
    # =====================================================
    chart_parser = subparsers.add_parser("chart",help="Convert single .ma2 chart",description="Convert a single .ma2 chart using MaichartConverter.",)
    chart_parser.add_argument("--input", required=True)
    chart_parser.add_argument("--output", required=True)
    chart_parser.add_argument("--policy", choices=["overwrite", "skip"], default="overwrite")
    chart_parser.add_argument("--display", choices=["1", "2"], default="2")

    # =====================================================
    # DATABASE
    # =====================================================
    db_parser = subparsers.add_parser("db",help="Compile database from AXXX root",description="Build a maimai database package from an AXXX root or batch folder.",)
    db_parser.add_argument("--root", required=True, help="AXXX root folder or folder containing AXXX folders")
    db_parser.add_argument("--output", required=True, help="Output folder")
    db_parser.add_argument("--categorize", choices=["0", "1", "2", "3", "4", "5", "6"], required=True)
    db_parser.add_argument("--display", choices=["1", "2"], default="2")
    db_parser.add_argument("--output-policy", choices=["overwrite", "skip"], default="overwrite")
    db_parser.add_argument("--asset-policy", choices=["overwrite", "skip"], default="overwrite")

    db_parser.add_argument("--music", default=None)
    db_parser.add_argument("--cover", default=None)
    db_parser.add_argument("--video", default=None)

    mode_group = db_parser.add_mutually_exclusive_group()
    mode_group.add_argument("--ignore-incomplete", action="store_true")
    mode_group.add_argument("--auto-build", action="store_true")

    db_parser.add_argument("--ignore-video", action="store_true")

    db_parser.add_argument("--decimal", action="store_true")
    db_parser.add_argument("--use-number", action="store_true")
    db_parser.add_argument("--json-log", action="store_true")
    db_parser.add_argument("--zip-after", action="store_true")
    db_parser.add_argument("--adx-after", action="store_true")
    db_parser.add_argument("--adx-track", action="store_true")
    db_parser.add_argument("--collection", action="store_true")

     # =====================================================
    # Parser for external tool paths
    # =====================================================

    parser.add_argument("--tool-vgmstream", dest="tool_vgmstream", default=None)
    parser.add_argument("--tool-ffmpeg", dest="tool_ffmpeg", default=None)
    parser.add_argument("--tool-ffprobe", dest="tool_ffprobe", default=None)
    parser.add_argument("--tool-flac", dest="tool_flac", default=None)
    parser.add_argument("--tool-crid", dest="tool_crid", default=None)
    parser.add_argument("--tool-maichartconverter", dest="tool_maichartconverter", default=None)
    parser.add_argument("--tool-assetstudio", dest="tool_assetstudio", default=None)

    parser.add_argument("--no-header", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--json-summary", action="store_true")

    return parser


def path_from_cli(value: str) -> Path:
    return Path(value.strip().strip('"')).resolve()

def apply_cli_tool_overrides(args):
    overrides = {
        "vgmstream-cli.exe": args.tool_vgmstream,
        "ffmpeg.exe": args.tool_ffmpeg,
        "ffprobe.exe": args.tool_ffprobe,
        "flac.exe": args.tool_flac,
        "crid_mod.exe": args.tool_crid,
        "maiforge.exe": args.tool_maichartconverter,
        "AssetStudio.CLI.exe": args.tool_assetstudio,
    }

    for tool_name, tool_path in overrides.items():
        if not tool_path:
            continue

        resolved_path = path_from_cli(tool_path)

        if not resolved_path.exists() or not resolved_path.is_file():
            raise FileNotFoundError(f"CLI tool override not found: {tool_name} -> {resolved_path}")

        TOOL_PATHS[tool_name] = resolved_path

def build_standard_payload_from_args(args, command_name):
    input_path = path_from_cli(args.input)
    output_path = path_from_cli(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    if command_name in {"mp4", "mp3", "flac", "image"}:
        return {
            "input_path": input_path,
            "output_path": output_path,
            "mode_type": args.mode_type,
            "existing_output_policy": args.policy,
        }

    if command_name == "chart":
        return {
            "input_path": input_path,
            "output_path": output_path,
            "mode_type": "single",
            "existing_output_policy": args.policy,
        }

    raise ValueError(f"Unsupported standard payload command: {command_name}")


def build_database_payload_from_args(args):
    axxx_input = path_from_cli(args.root)
    detection = detect_axxx_input(axxx_input)
    if not detection:
        raise ValueError("Invalid --root. Provide an AXXX folder or a folder containing AXXX folders (e.g., A001, M100).")

    mode_type = detection["mode_type"]
    axxx_path = detection.get("axxx_path")
    axxx_paths = detection.get("axxx_paths") or []

    output_path = path_from_cli(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    music_path = path_from_cli(args.music) if args.music else None
    cover_path = path_from_cli(args.cover) if args.cover else None
    video_path = path_from_cli(args.video) if args.video else None

    if args.auto_build:
        ignore_incomplete = False
        auto_convert_assets = True
        auto_convert_targets = ["music", "cover", "video"]
    elif args.ignore_incomplete:
        ignore_incomplete = True
        auto_convert_assets = False
        auto_convert_targets = []
    else:
        ignore_incomplete = False
        auto_convert_assets = False
        auto_convert_targets = []

    return {
        "mode_type": mode_type,
        "axxx_path": axxx_path,
        "axxx_paths": axxx_paths,
        "batch_root": detection.get("batch_root"),
        "music_path": music_path,
        "cover_path": cover_path,
        "video_path": video_path,
        "categorization": args.categorize,
        "decimal": args.decimal,
        "ignore_incomplete": ignore_incomplete,
        "ignore_video": args.ignore_video,
        "auto_convert_assets": auto_convert_assets,
        "auto_convert_targets": auto_convert_targets,
        "existing_assets_policy": args.asset_policy,
        "existing_output_policy": args.output_policy,
        "use_number": args.use_number,
        "json_log": args.json_log,
        "zip_after": args.zip_after,
        "adx_after": args.adx_after,
        "adx_track": args.adx_track,
        "collection": args.collection,
        "output_path": output_path,
        "auto_generated_temp_dirs": [],
    }


def run_database_shell_single(payload, display_mode, resolved_tools):
    clear_screen()
    show_header()
    mode_label = payload.get("mode_label")
    title = "Database Conversion"
    if mode_label:
        title = f"{title} ({mode_label})"
    print(title)
    print(f"Display mode: {'Progress bar' if display_mode == '1' else 'Logs'}\n")

    log_path = payload["output_path"] / "log.txt"
    prep_logs = []
    prep_missing = 0
    prep_failed = 0
    output_policy = payload.get("existing_output_policy", "overwrite")
    auto_temp_dirs = []
    stage_logs = []

    # The actual output directory maiforge will create is always output_path/axxx_name.
    # For batch items, output_path is already set to base_output/axxx_name, so
    # maiforge_output_root is set and maiforge outputs there directly.
    # For single mode, maiforge appends the AXXX name to output_path.
    axxx_name = payload["axxx_path"].name
    if payload.get("maiforge_output_root"):
        actual_output_dir = payload["output_path"]  # batch: already axxx-specific
    else:
        actual_output_dir = payload["output_path"] / axxx_name  # single: maiforge appends name

    selected_targets = set()
    if payload.get("auto_convert_assets"):
        selected_targets = set(payload.get("auto_convert_targets") or ["music", "cover", "video"])

    mp3_items = 0
    mp4_items = 0
    jacket_items = 0
    ma2_items = 1

    if "music" in selected_targets and payload["music_path"] is None:
        sound_root = payload["axxx_path"] / "SoundData"
        if sound_root.exists():
            mp3_items = len(list_files_with_ext(sound_root, ".awb"))
    if "video" in selected_targets and payload["video_path"] is None:
        movie_root = payload["axxx_path"] / "MovieData"
        if movie_root.exists():
            mp4_items = len(list_files_with_ext(movie_root, ".dat"))
    if "cover" in selected_targets and payload["cover_path"] is None:
        jacket_root = payload["axxx_path"] / "AssetBundleImages" / "jacket"
        if jacket_root.exists():
            jacket_items = len(list_files_with_ext(jacket_root, ".ab"))
            if jacket_items == 0:
                jacket_items = 1
        else:
            jacket_items = 1

    total_items = mp3_items + mp4_items + jacket_items + ma2_items
    done_items = 0

    def render_progress(current_task):
        if total_items <= 0:
            return
        percent = int((done_items / total_items) * 100)
        bar_len = 28
        filled = int((done_items / total_items) * bar_len)
        bar = "#" * filled + "-" * (bar_len - filled)
        if display_mode == "1":
            clear_screen()
            show_header()
            print("Database Conversion\n")
            print(f"[{bar}] {percent}%")
            print(f"{done_items}/{total_items} tasks | {current_task}\n")
        elif display_mode == "2":
            print(f"[{done_items}/{total_items} | {percent}%] {current_task}")

    def progress_step(current_task):
        nonlocal done_items
        done_items += 1
        if done_items > total_items:
            done_items = total_items
        render_progress(current_task)

    def progress_tick(current_task):
        stage_logs.append(f"[PROGRESS] {current_task} ({done_items}/{total_items})")
        render_progress(current_task)

    if actual_output_dir.exists() and actual_output_dir.is_dir():
        if output_policy == "skip":
            payload["output_path"].mkdir(parents=True, exist_ok=True)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("[SKIPPED]\n")
                f.write(f"OUTPUT DIR: {actual_output_dir}\n")
                f.write("DETAIL: Existing output folder kept.\n")
            return 0, 0, 0, log_path
        elif output_policy == "overwrite":
            clear_folder_contents(actual_output_dir)

    _autobuilt_music_path = None
    _autobuilt_video_path = None
    _autobuilt_cover_path = None

    if payload.get("auto_convert_assets"):
        axxx_root = payload["axxx_path"]
        asset_policy = payload.get("existing_assets_policy", "skip")

        if payload["music_path"] is None and "music" in selected_targets:
            _existing_music = axxx_root / "musicMP3"
            _source_awb = list((axxx_root / "SoundData").glob("*.awb")) if (axxx_root / "SoundData").is_dir() else []
            _existing_mp3 = list(_existing_music.glob("*.mp3")) if _existing_music.is_dir() else []
            _music_complete = bool(_existing_mp3) and (not _source_awb or len(_existing_mp3) >= len(_source_awb))
            _music_preexisted = _existing_music.is_dir()
            if _music_complete:
                payload["music_path"] = _existing_music
                prep_logs.append(f"[SKIP] musicMP3/ already complete in {axxx_root.name} ({len(_existing_mp3)} files) — skipping generation.")
            else:
                if _existing_mp3:
                    prep_logs.append(f"[REGEN] musicMP3/ incomplete in {axxx_root.name} ({len(_existing_mp3)}/{len(_source_awb)}) — regenerating.")
                music_path, s, m, f, logs = auto_build_music_assets(
                    axxx_root,
                    resolved_tools,
                    display_mode,
                    asset_policy,
                    progress_callback=progress_step,
                )
                payload["music_path"] = music_path
                _autobuilt_music_path = music_path
                prep_missing += m
                prep_failed += f
                prep_logs.extend(logs)

        if payload["video_path"] is None and "video" in selected_targets:
            _existing_video = axxx_root / "Movie"
            _source_dat = list((axxx_root / "MovieData").glob("*.dat")) if (axxx_root / "MovieData").is_dir() else []
            _existing_mp4 = list(_existing_video.glob("*.mp4")) if _existing_video.is_dir() else []
            _video_complete = bool(_existing_mp4) and (not _source_dat or len(_existing_mp4) >= len(_source_dat))
            _video_preexisted = _existing_video.is_dir()
            if _video_complete:
                payload["video_path"] = _existing_video
                prep_logs.append(f"[SKIP] Movie/ already complete in {axxx_root.name} ({len(_existing_mp4)} files) — skipping generation.")
            else:
                if _existing_mp4:
                    prep_logs.append(f"[REGEN] Movie/ incomplete in {axxx_root.name} ({len(_existing_mp4)}/{len(_source_dat)}) — regenerating.")
                video_path, s, m, f, logs = auto_build_video_assets(
                    axxx_root,
                    resolved_tools,
                    display_mode,
                    asset_policy,
                    progress_callback=progress_step,
                )
                payload["video_path"] = video_path
                _autobuilt_video_path = video_path
                prep_missing += m
                prep_failed += f
                prep_logs.extend(logs)

        if payload["cover_path"] is None and "cover" in selected_targets:
            _existing_cover = axxx_root / "Jackets"
            _source_ab = list((axxx_root / "AssetBundleImages" / "jacket").glob("*.ab")) if (axxx_root / "AssetBundleImages" / "jacket").is_dir() else []
            _existing_png = list(_existing_cover.glob("*.png")) if _existing_cover.is_dir() else []
            _cover_complete = bool(_existing_png) and (not _source_ab or len(_existing_png) >= len(_source_ab))
            _cover_preexisted = _existing_cover.is_dir()
            if _cover_complete:
                payload["cover_path"] = _existing_cover
                prep_logs.append(f"[SKIP] Jackets/ already complete in {axxx_root.name} ({len(_existing_png)} files) — skipping generation.")
            else:
                if _existing_png:
                    prep_logs.append(f"[REGEN] Jackets/ incomplete in {axxx_root.name} ({len(_existing_png)}/{len(_source_ab)}) — regenerating.")
                cover_path, s, m, f, logs = auto_build_cover_assets(
                    axxx_root,
                    resolved_tools,
                    display_mode,
                    asset_policy,
                    progress_callback=progress_step,
                )
                payload["cover_path"] = cover_path
                _autobuilt_cover_path = cover_path
                prep_missing += m
                prep_failed += f
                prep_logs.extend(logs)

    payload["auto_generated_temp_dirs"] = auto_temp_dirs

    required_ready = True
    required_fail_reasons = []

    if payload.get("auto_convert_assets"):
        selected_targets = set(payload.get("auto_convert_targets") or ["music", "cover", "video"])

        if "music" in selected_targets and (payload["music_path"] is None or not Path(payload["music_path"]).exists()):
            required_ready = False
            required_fail_reasons.append("Music folder is not ready.")
        if "cover" in selected_targets and (payload["cover_path"] is None or not Path(payload["cover_path"]).exists()):
            required_ready = False
            required_fail_reasons.append("Cover folder is not ready.")
        if "video" in selected_targets and (payload["video_path"] is None or not Path(payload["video_path"]).exists()):
            required_ready = False
            required_fail_reasons.append("Video folder is not ready.")

    if not required_ready:
        payload["output_path"].mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            if stage_logs:
                f.write("DATABASE PROGRESS\n")
                f.write("=" * 80 + "\n")
                for line in stage_logs:
                    f.write(line + "\n")
                f.write("\n")
            if prep_logs:
                f.write("AUTO-CONVERT PREP LOGS\n")
                f.write("=" * 80 + "\n")
                for line in prep_logs:
                    f.write(line + "\n")
                f.write("\n")
            f.write("DATABASE CONVERSION BLOCKED\n")
            f.write("=" * 80 + "\n")
            for reason in required_fail_reasons:
                f.write(reason + "\n")

        if display_mode == "2":
            print("Database conversion blocked.\n")
            for reason in required_fail_reasons:
                print(reason)
            print()
            wait_enter("Press Enter...")

        _db_cleanup_pol = load_settings().get("temp_cleanup", "auto")
        if _db_cleanup_pol in ("auto", "batch"):
            for _ab_path in [p for p in (_autobuilt_music_path, _autobuilt_video_path, _autobuilt_cover_path) if p]:
                _ab = Path(_ab_path)
                if _ab.exists():
                    for _f in _ab.iterdir():
                        if _f.is_file():
                            safe_delete(_f)

        return 0, prep_missing, prep_failed + 1, log_path

    # Pre-patch empty <jacketFile> fields in Music.xml before running maiforge.
    # Maiforge crashes with "The path is empty" when jacketFile is "".
    jacket_patch_logs = patch_music_xml_jacket_fields(
        Path(payload["axxx_path"]),
        Path(payload["cover_path"]) if payload.get("cover_path") else None,
    )
    for log_line in jacket_patch_logs:
        print(log_line)

    progress_tick("Converting ma2 files & creating folders...")
    cmd = build_compile_database_command(payload, resolved_tools)
    cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in cmd)

    if display_mode == "2":
        print("Running command:\n")
        print(cmd_str)
        print()
        print("(streaming output — please wait...)\n")

    stdout_lines = []
    stderr_lines = []
    returncode = -1

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(SCRIPT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,  # piped so we can auto-answer prompts
            bufsize=0,              # unbuffered — prompts appear immediately
        )

        def _drain(pipe, bucket, live_print):
            """Read byte-by-byte so partial lines (prompts) flush immediately.
            Auto-answers maiforge 'Continue? (y/n):' prompts with 'y'."""
            buf = b""
            try:
                while True:
                    ch = pipe.read(1)
                    if not ch:
                        break
                    buf += ch
                    if ch in (b"\n", b"\r"):
                        line = buf.decode("utf-8", errors="replace").rstrip("\r\n")
                        bucket.append(line)
                        if live_print:
                            print(line, flush=True)
                        buf = b""
                    else:
                        if live_print:
                            sys.stdout.write(ch.decode("utf-8", errors="replace"))
                            sys.stdout.flush()
                        # Auto-answer maiforge "Missing X. Continue? (y/n): " prompts
                        decoded = buf.decode("utf-8", errors="replace")
                        if decoded.rstrip().endswith("(y/n):"):
                            bucket.append(decoded)
                            if live_print:
                                sys.stdout.write(" y\n")
                                sys.stdout.flush()
                            try:
                                proc.stdin.write(b"y\n")
                                proc.stdin.flush()
                            except Exception:
                                pass
                            buf = b""
            except (ValueError, OSError):
                pass
            # Flush any remaining partial line
            if buf:
                line = buf.decode("utf-8", errors="replace")
                bucket.append(line)
                if live_print:
                    sys.stdout.write(line)
                    sys.stdout.flush()

        # Always live-print stdout so maiforge prompts are visible in all modes
        t_out = threading.Thread(target=_drain, args=(proc.stdout, stdout_lines, True), daemon=True)
        t_err = threading.Thread(target=_drain, args=(proc.stderr, stderr_lines, display_mode == "2"), daemon=True)
        t_out.start()
        t_err.start()
        proc.wait()
        # Close pipes explicitly so drain threads see EOF even if child
        # processes inherited the handles and haven't exited yet (Windows).
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.stdout.close()
        except Exception:
            pass
        try:
            proc.stderr.close()
        except Exception:
            pass
        t_out.join(timeout=15)
        t_err.join(timeout=15)
        returncode = proc.returncode

        stdout_text = "\n".join(stdout_lines).strip()
        stderr_text = "\n".join(stderr_lines).strip()

        progress_step("Converting ma2 files & creating folders...")
        if returncode == 0 and done_items < total_items:
            done_items = total_items

        payload["output_path"].mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            if stage_logs:
                f.write("DATABASE PROGRESS\n")
                f.write("=" * 80 + "\n")
                for line in stage_logs:
                    f.write(line + "\n")
                f.write("\n")
            if prep_logs:
                f.write("AUTO-CONVERT PREP LOGS\n")
                f.write("=" * 80 + "\n")
                for line in prep_logs:
                    f.write(line + "\n")
                f.write("\n")

            f.write("COMPILEDATABASE COMMAND\n")
            f.write("=" * 80 + "\n")
            f.write(cmd_str + "\n\n")
            f.write("STDOUT:\n")
            f.write(stdout_text if stdout_text else "(empty)")
            f.write("\n\nSTDERR:\n")
            f.write(stderr_text if stderr_text else "(empty)")
            f.write("\n")

        if display_mode == "2":
            print()
            countdown_after_conversion(5, label="Returning to next step")

        _db_cleanup_pol = load_settings().get("temp_cleanup", "auto")
        if _db_cleanup_pol in ("auto", "batch"):
            for _ab_path in [p for p in (_autobuilt_music_path, _autobuilt_video_path, _autobuilt_cover_path) if p]:
                _ab = Path(_ab_path)
                if _ab.exists():
                    for _f in _ab.iterdir():
                        if _f.is_file():
                            safe_delete(_f)

        if returncode == 0:
            return 1, prep_missing, prep_failed, log_path

        return 0, prep_missing, prep_failed + 1, log_path

    except Exception as e:
        payload["output_path"].mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            if stage_logs:
                f.write("DATABASE PROGRESS\n")
                f.write("=" * 80 + "\n")
                for line in stage_logs:
                    f.write(line + "\n")
                f.write("\n")
            if prep_logs:
                f.write("AUTO-CONVERT PREP LOGS\n")
                f.write("=" * 80 + "\n")
                for line in prep_logs:
                    f.write(line + "\n")
                f.write("\n")
            f.write("EXCEPTION:\n")
            f.write(str(e) + "\n")

        _db_cleanup_pol = load_settings().get("temp_cleanup", "auto")
        if _db_cleanup_pol in ("auto", "batch"):
            for _ab_path in [p for p in (_autobuilt_music_path, _autobuilt_video_path, _autobuilt_cover_path) if p]:
                _ab = Path(_ab_path)
                if _ab.exists():
                    for _f in _ab.iterdir():
                        if _f.is_file():
                            safe_delete(_f)

        print(f"Error: {e}")
        wait_enter()
        return 0, prep_missing, prep_failed + 1, log_path
    

def run_database_shell(payload, display_mode, resolved_tools):
    mode_type = payload.get("mode_type", "single")
    if mode_type != "batch":
        single_payload = dict(payload)
        if single_payload.get("axxx_path") and not single_payload.get("mode_label"):
            single_payload["mode_label"] = "Single"
        success, missing, failed, log_path = run_database_shell_single(single_payload, display_mode, resolved_tools)
        cleanup_lines = []
        cleanup_database_temp_dirs(single_payload.get("auto_generated_temp_dirs") or [], cleanup_lines)
        if cleanup_lines:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("\n".join(cleanup_lines) + "\n")
        return success, missing, failed, log_path

    axxx_paths = payload.get("axxx_paths") or []
    if not axxx_paths:
        raise ValueError("Batch database mode requires AXXX folders.")

    base_output = payload["output_path"]
    base_output.mkdir(parents=True, exist_ok=True)
    batch_log = base_output / "batch_log.txt"

    total_success = 0
    total_missing = 0
    total_failed = 0
    log_lines = [
        "BATCH DATABASE CONVERSION",
        "=" * 80,
        f"Batch root: {payload.get('batch_root') or '(not provided)'}",
        f"AXXX folders: {', '.join(p.name for p in axxx_paths)}",
        "",
    ]
    all_temp_dirs = []
    seen_temp_dirs = set()

    def register_temp_dirs(temp_dirs):
        for temp_dir in temp_dirs or []:
            key = str(temp_dir)
            if key in seen_temp_dirs:
                continue
            seen_temp_dirs.add(key)
            all_temp_dirs.append(temp_dir)

    batch_results = []

    for idx, axxx_path in enumerate(axxx_paths, start=1):
        item_payload = dict(payload)
        item_payload["mode_type"] = "single"
        item_payload["axxx_path"] = axxx_path
        item_payload["output_path"] = base_output / axxx_path.name
        item_payload["maiforge_output_root"] = base_output
        item_payload["auto_generated_temp_dirs"] = []
        item_payload["mode_label"] = f"{axxx_path.name} {idx}/{len(axxx_paths)}"

        success, missing, failed, log_path = run_database_shell_single(item_payload, display_mode, resolved_tools)
        total_success += success
        total_missing += missing
        total_failed += failed
        batch_results.append((axxx_path.name, success, missing, failed))
        register_temp_dirs(item_payload.get("auto_generated_temp_dirs"))
        log_lines.append(f"[{axxx_path.name}] success={success} missing={missing} failed={failed} log={log_path}")
        if failed > 0 and not CLI_MODE:
            if not ask_yes_no("An error occurred. Continue with remaining folders? (y/n): "):
                log_lines.append("[ABORTED] User stopped batch after error.")
                break
        if idx < len(axxx_paths) and not CLI_MODE:
            countdown_between_batches(5, completed_label=axxx_path.name)

    # Batch summary screen
    if not CLI_MODE and WINDOWS and batch_results:
        clear_screen()
        show_header()
        print("Batch Database Conversion — Summary\n")
        col_w = max(len(r[0]) for r in batch_results) + 2
        header = f"  {'Folder':<{col_w}}  {'OK':>6}  {'Missing':>8}  {'Failed':>7}"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for name, s, m, f in batch_results:
            status = "\u2713" if f == 0 else "\u2717"
            print(f"  {status} {name:<{col_w}}  {s:>6}  {m:>8}  {f:>7}")
        print("  " + "-" * (len(header) - 2))
        print(f"  {'TOTAL':<{col_w+2}}  {total_success:>6}  {total_missing:>8}  {total_failed:>7}")
        print(f"\n  Log: {batch_log}")
        print()
        input("  Press Enter to continue...")

    cleanup_lines = []
    cleanup_database_temp_dirs(all_temp_dirs, cleanup_lines)
    if cleanup_lines:
        log_lines.append("")
        log_lines.extend(cleanup_lines)

    with open(batch_log, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")

    return total_success, total_missing, total_failed, batch_log

def run_cli_mode(argv):
    if len(argv) >= 2 and argv[0] in ("-h", "--help"):
        argv = argv[1:] + ["--help"]

    parser = build_cli_parser()
    args = parser.parse_args(argv)

    global NO_HEADER, QUIET_MODE, JSON_SUMMARY

    NO_HEADER = args.no_header
    QUIET_MODE = args.quiet
    JSON_SUMMARY = args.json_summary

    if not args.command:
        parser.print_help()
        return 0

    required_tools = None
    payload = None
    display_mode = getattr(args, "display", "2")

    if args.command == "mp4":
        payload = build_standard_payload_from_args(args, "mp4")
        required_tools = requirements_for_mode("1")
    elif args.command == "mp3":
        payload = build_standard_payload_from_args(args, "mp3")
        required_tools = requirements_for_mode("2")
    elif args.command == "flac":
        payload = build_standard_payload_from_args(args, "flac")
        required_tools = requirements_for_mode("3")
    elif args.command == "chart":
        payload = build_standard_payload_from_args(args, "chart")
        required_tools = requirements_for_mode("4")
    elif args.command == "db":
        payload = build_database_payload_from_args(args)
        required_tools = requirements_for_mode("5")
    elif args.command == "image":
        payload = build_standard_payload_from_args(args, "image")
        required_tools = requirements_for_mode("6")
    else:
        raise ValueError(f"Unsupported command: {args.command}")
    
    try:
        apply_cli_tool_overrides(args)
        resolved_tools = resolve_requirements(required_tools)

        if args.command == "mp4":
            success, missing, failed, log_path = run_mp4_shell(payload, display_mode, resolved_tools)
        elif args.command == "mp3":
            success, missing, failed, log_path = run_mp3_shell(payload, display_mode, resolved_tools)
        elif args.command == "flac":
            success, missing, failed, log_path = run_flac_shell(payload, display_mode, resolved_tools)
        elif args.command == "chart":
            success, missing, failed, log_path = run_chart_shell(payload, display_mode, resolved_tools)
        elif args.command == "db":
            success, missing, failed, log_path = run_database_shell(payload, display_mode, resolved_tools)
        elif args.command == "image":
            success, missing, failed, log_path = run_image_shell(payload, display_mode, resolved_tools)

        if JSON_SUMMARY:
            print(json.dumps({
                "success": success,
                "missing": missing,
                "failed": failed,
                "log_path": str(log_path),
                "command": args.command,
            }, ensure_ascii=False))
        else:
            cli_print("\nCLI Run Completed!\n")
            cli_print(f"Successfully Converted: {success}")
            cli_print(f"Missing: {missing}")
            cli_print(f"Failed: {failed}")
            cli_print()
            cli_print(f"Logs are stored at:\n{log_path}")

        if failed > 0:
            return 2
        if missing > 0:
            return 1
        return 0

    except Exception as e:
        if JSON_SUMMARY:
            print(json.dumps({
                "error": str(e),
                "exit_code": 3,
            }, ensure_ascii=False))
        else:
            cli_print("CLI ERROR:")
            cli_print(str(e))
        return 3

# =========================================================
# CONTROLLER
# =========================================================

def handle_mode(mode):
    if mode in {"1", "2", "3", "6"}:
        single_or_batch = scene_single_batch_menu({
            "1": "MP4 Conversion",
            "2": "MP3 Conversion",
            "3": "FLAC Conversion",
            "6": "Image Conversion",
        }[mode])

        if mode == "1":
            payload = prompt_mp4(single_or_batch)
        elif mode == "2":
            payload = prompt_mp3(single_or_batch)
        elif mode == "3":
            payload = prompt_flac(single_or_batch)
        else:
            payload = prompt_image(single_or_batch)

        if payload is None:
            return

    elif mode == "4":
        payload = prompt_chart()
        if payload is None:
            return

    else:
        payload = prompt_database()
        if payload is None:
            return

    required_tools = requirements_for_mode(mode)
    resolved_tools = resolve_requirements(required_tools)
    display_mode = scene_display_mode()

    start_ts = time.time()
    if mode == "1":
        success, missing, failed, log_path = run_mp4_shell(payload, display_mode, resolved_tools)
    elif mode == "2":
        success, missing, failed, log_path = run_mp3_shell(payload, display_mode, resolved_tools)
    elif mode == "3":
        success, missing, failed, log_path = run_flac_shell(payload, display_mode, resolved_tools)
    elif mode == "4":
        success, missing, failed, log_path = run_chart_shell(payload, display_mode, resolved_tools)
    elif mode == "5":
        success, missing, failed, log_path = run_database_shell(payload, display_mode, resolved_tools)
    else:
        success, missing, failed, log_path = run_image_shell(payload, display_mode, resolved_tools)
    elapsed = time.time() - start_ts

    scene_completion(
        success, missing, failed, log_path,
        output_path=payload.get("output_path"),
        elapsed=elapsed,
    )


def main():
    global CLI_MODE

    if len(sys.argv) > 1:
        CLI_MODE = True
        exit_code = run_cli_mode(sys.argv[1:])
        sys.exit(exit_code)

    CLI_MODE = False

    # First-run nudge (non-blocking)
    try:
        from setup import nudge_if_needed
        nudge_if_needed()
    except Exception:
        pass

    countdown_with_skip(10)

    while True:
        choice = scene_main_menu()

        if choice == "0":
            clear_screen()
            print("Exiting.")
            sys.exit(0)

        if choice.lower() == "s":
            scene_settings()
            continue

        handle_mode(choice)


if __name__ == "__main__":
    main()

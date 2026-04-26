import os
import sys
import time
import re
import json
import argparse
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
    build_crid_command as conv_build_crid_command,
    build_ffmpeg_mp4_command as conv_build_ffmpeg_mp4_command,
    build_mp4_output_path as conv_build_mp4_output_path,
    find_extracted_m2v_for_dat as conv_find_extracted_m2v_for_dat,
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
    "MaichartConverter.exe": [
        SCRIPT_ROOT / "maichartconverter" / "MaichartConverter.exe",
        SCRIPT_ROOT / "MaichartConverter.exe",
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


def run_subprocess_safe(cmd, cwd=None):
    return tools_run_subprocess_safe(cmd, cwd)

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
    while True:
        raw = input(prompt).strip().strip('"')
        p = Path(raw)
        if p.exists():
            if p.is_dir():
                return p
            print("Path exists but is not a folder.")
            continue
        try:
            p.mkdir(parents=True, exist_ok=True)
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
        return ["MaichartConverter.exe"]
    if mode == "5":
        return [
            "MaichartConverter.exe",
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
    print("[0] Exit")
    print()
    return ask_choice("Enter choice: ", {"0", "1", "2", "3", "4", "5", "6"})


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
    clear_screen()
    show_header()
    print("Display mode\n")
    print("[1] Progress bar")
    print("[2] Logs")
    print()
    return ask_choice("Enter choice: ", {"1", "2"})


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


def scene_completion(success_count, missing_count, failed_count, log_path=None):
    clear_screen()
    show_header()
    print("Conversion Completed!\n")
    print(f"Successfully Converted: {success_count}")
    print(f"Missing: {missing_count}")
    print(f"Failed: {failed_count}")
    print()
    if log_path:
        print(f"Logs are stored at:\n{log_path}")
    wait_enter("Press Enter to return to main menu...")

# =========================================================
# PROMPTS
# =========================================================

def prompt_mp4(single_or_batch):
    clear_screen()
    show_header()

    if single_or_batch == "1":
        input_path = ask_existing_file("Enter path to your .dat file: ")
    else:
        input_path = ask_existing_dir("Enter path to your .dat folder: ")

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

    if single_or_batch == "1":
        input_path = ask_existing_file("Enter path to your .awb file: ")
    else:
        input_path = ask_existing_dir("Enter path to your .awb folder: ")

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

    if single_or_batch == "1":
        input_path = ask_existing_file("Enter path to your .awb file: ")
    else:
        input_path = ask_existing_dir("Enter path to your .awb folder: ")

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


def prompt_chart():
    clear_screen()
    show_header()

    input_path = ask_existing_file("Enter path to your chart file (.ma2): ")
    output_path = ask_output_dir("Enter output folder: ")

    policy = resolve_existing_output_policy_if_needed(output_path, folder_mode=True)
    if policy is None:
        return None

    return {
        "input_path": input_path,
        "output_path": output_path,
        "mode_type": "single",
        "existing_output_policy": policy,
    }


def prompt_image(single_or_batch):
    clear_screen()
    show_header()

    if single_or_batch == "1":
        input_path = ask_existing_file("Enter path to your .ab file: ")
    else:
        input_path = ask_existing_dir("Enter path to your .ab folder: ")

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


def prompt_database():
    clear_screen()
    show_header()
    print("Leave blank if not applied.\n")

    detection = ask_axxx_or_batch("(Required) Enter path to your AXXX folder or batch root: ")
    mode_type = detection["mode_type"]
    axxx_path = detection.get("axxx_path")
    axxx_paths = detection.get("axxx_paths") or []

    if mode_type == "single" and axxx_path:
        print(f"Detected: Single database ({axxx_path.name})\n")
    elif mode_type == "batch":
        print(f"Detected: Batch database with {len(axxx_paths)} folders: {format_axxx_list(axxx_paths)}")
        print("Non-AXXX folders/files will be ignored.\n")

    music_path = ask_optional_existing_dir("Enter path to your music folder (mp3): ")
    cover_path = ask_optional_existing_dir("Enter path to your cover/background folder (.png): ")
    video_path = ask_optional_existing_dir("Enter path to your video folder (.mp4): ")

    auto_convert_assets = False
    existing_assets_policy = None

    missing_count = sum([music_path is None, cover_path is None, video_path is None])
    auto_convert_targets = []

    if missing_count >= 2:
        missing_items = []
        if cover_path is None:
            missing_items.append(("cover", "Assets (Jackets)"))
        if video_path is None:
            missing_items.append(("video", "MovieData"))
        if music_path is None:
            missing_items.append(("music", "MusicData (.awb -> .mp3)"))

        selected_targets = scene_select_missing_assets(missing_items)
        if selected_targets is None:
            return None

        if selected_targets:
            ignore_incomplete = False
            auto_convert_assets = True
            auto_convert_targets = selected_targets
        else:
            ignore_incomplete = ask_yes_no("No assets selected. Ignore any errors within the process? (y/n): ")
    elif missing_count == 1:
        # Exactly 1 missing: ask if they want to convert it
        missing_items = []
        if music_path is None:
            missing_items.append(("music", "Music (MusicData)"))
        if cover_path is None:
            missing_items.append(("cover", "Assets (Jackets)"))
        if video_path is None:
            missing_items.append(("video", "MovieData"))

        missing_key, missing_name = missing_items[0] if missing_items else ("unknown", "unknown")

        convert_single = ask_yes_no(f"Auto-convert missing {missing_name}? (y/n): ")

        if convert_single:
            ignore_incomplete = False
            auto_convert_assets = True
            auto_convert_targets = [missing_key]
        else:
            ignore_incomplete = ask_yes_no("Ignore any errors within the process? (y/n): ")
    else:
        # No missing assets
        ignore_incomplete = ask_yes_no("Ignore any errors within the process? (y/n): ")

    if auto_convert_assets:
        selected_targets = set(auto_convert_targets or ["music", "cover", "video"])

        if mode_type == "batch":
            existing_music, existing_cover, existing_video = get_existing_auto_assets(axxx_paths, selected_targets)
        else:
            auto_music_dir = axxx_path / "musicMP3"
            auto_cover_dir = axxx_path / "Jackets"
            auto_video_dir = axxx_path / "Movie"
            existing_music = count_existing_files_with_ext(auto_music_dir, ".mp3") if "music" in selected_targets else 0
            existing_cover = output_folder_has_relevant_image_outputs(auto_cover_dir) if "cover" in selected_targets else False
            existing_video = count_existing_files_with_ext(auto_video_dir, ".mp4") if "video" in selected_targets else 0

        if existing_music > 0 or existing_cover or existing_video > 0:
            choice = scene_existing_assets_decision()
            if choice == "1":
                existing_assets_policy = "overwrite"
            elif choice == "2":
                existing_assets_policy = "skip"
            else:
                return None
        else:
            existing_assets_policy = "overwrite"

    clear_screen()
    show_header()
    print("Database Conversion Options\n")
    print("Categorization:")
    print("0 = Genre")
    print("1 = Level")
    print("2 = Cabinet")
    print("3 = Composer")
    print("4 = BPM")
    print("5 = SD/DX Chart")
    print("6 = No subfolders")
    categorization = ask_choice("Enter categorization: ", {"0", "1", "2", "3", "4", "5", "6"})

    decimal = ask_yes_no("Force decimal levels? (y/n): ")
    use_number = ask_yes_no("Use musicID as folder name? (y/n): ")
    json_log = ask_yes_no("Create JSON log? (y/n): ")
    zip_after = ask_yes_no("Zip after conversion? (y/n): ")
    collection = ask_yes_no("Generate collection manifest? (y/n): ")

    output_path = ask_output_dir("Enter output folder: ")
    if output_folder_has_relevant_database_outputs(output_path):
        output_policy = resolve_existing_output_policy()
    else:
        output_policy = "overwrite"
    if output_policy is None:
        return None

    return {
        "mode_type": mode_type,
        "axxx_path": axxx_path,
        "axxx_paths": axxx_paths,
        "batch_root": detection.get("batch_root"),
        "music_path": music_path,
        "cover_path": cover_path,
        "video_path": video_path,
        "categorization": categorization,
        "decimal": decimal,
        "ignore_incomplete": ignore_incomplete,
        "auto_convert_assets": auto_convert_assets,
        "auto_convert_targets": auto_convert_targets,
        "existing_assets_policy": existing_assets_policy,
        "existing_output_policy": output_policy,
        "use_number": use_number,
        "json_log": json_log,
        "zip_after": zip_after,
        "collection": collection,
        "output_path": output_path,
        "auto_generated_temp_dirs": [],
    }

# =========================================================
# COMMAND BUILDERS
# =========================================================

def build_compile_database_command(payload, resolved_tools):
    exe = resolved_tools["MaichartConverter.exe"]

    cmd = [
        str(exe),
        "CompileDatabase",
        "-p", str(payload["axxx_path"]),
        "-o", str(payload["output_path"]),
        "-g", str(payload["categorization"]),
    ]

    if payload["music_path"]:
        cmd.extend(["-m", str(payload["music_path"])])
    if payload["cover_path"]:
        cmd.extend(["-c", str(payload["cover_path"])])
    if payload["video_path"]:
        cmd.extend(["-v", str(payload["video_path"])])

    if payload["decimal"]:
        cmd.append("-d")
    if payload["ignore_incomplete"]:
        cmd.append("-i")
    if payload["use_number"]:
        cmd.append("-n")
    if payload["json_log"]:
        cmd.append("-j")
    if payload["zip_after"]:
        cmd.append("-z")
    if payload["collection"]:
        cmd.append("-k")

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
    if dat_files:
        print("\nSample files:")
        for p in dat_files[:10]:
            print(f"  {p}")

    if not dat_files:
        print("\nNo .dat files found.")
        wait_enter()
        return 0, 0, 1, log_path

    success = 0
    missing = 0
    failed = 0
    log_lines = []

    output_root.mkdir(parents=True, exist_ok=True)
    pause_each_file = (display_mode == "2" and mode_type == "single")

    for idx, dat_file in enumerate(dat_files, start=1):
        out_mp4 = build_mp4_output_path(dat_file, output_root)

        if not should_process_output(out_mp4, policy, log_lines):
            continue

        crid_cmd = build_crid_command(dat_file, resolved_tools)
        crid_cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in crid_cmd)

        if display_mode == "2":
            clear_screen()
            show_header()
            print("MP4 Conversion\n")
            print(f"[{idx}/{len(dat_files)}] {dat_file}\n")
            print("Running crid_mod:")
            print(crid_cmd_str)
            print()

        try:
            crid_result = run_subprocess_safe(crid_cmd, cwd=SCRIPT_ROOT)
            crid_stdout = crid_result.stdout.strip() if crid_result.stdout else ""
            crid_stderr = crid_result.stderr.strip() if crid_result.stderr else ""

            extracted_m2v = find_extracted_m2v_for_dat(dat_file)

            if crid_result.returncode != 0:
                failed += 1
                log_lines.extend([
                    "=" * 80,
                    f"[FAILED] {dat_file}",
                    "STEP: crid_mod",
                    f"COMMAND: {crid_cmd_str}",
                    f"RETURN CODE: {crid_result.returncode}",
                    "STDOUT:", crid_stdout if crid_stdout else "(empty)",
                    "STDERR:", crid_stderr if crid_stderr else "(empty)",
                ])
                if display_mode == "2":
                    print(f"Return code: {crid_result.returncode}\n")
                    if crid_stdout:
                        print("STDOUT:")
                        print(crid_stdout)
                        print()
                    if crid_stderr:
                        print("STDERR:")
                        print(crid_stderr)
                        print()
                    if pause_each_file:
                        wait_enter()
                continue

            if extracted_m2v is None or not extracted_m2v.exists():
                missing += 1
                log_lines.extend([
                    "=" * 80,
                    f"[MISSING] {dat_file}",
                    "STEP: crid_mod output",
                    f"COMMAND: {crid_cmd_str}",
                    f"RETURN CODE: {crid_result.returncode}",
                    "STDOUT:", crid_stdout if crid_stdout else "(empty)",
                    "STDERR:", crid_stderr if crid_stderr else "(empty)",
                    "DETAIL: No extracted .m2v found beside source .dat",
                ])
                if display_mode == "2":
                    print("No extracted .m2v found.\n")
                    if pause_each_file:
                        wait_enter()
                continue

            ffmpeg_cmd = build_ffmpeg_mp4_command(extracted_m2v, out_mp4, resolved_tools)
            ffmpeg_cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in ffmpeg_cmd)

            if display_mode == "2":
                print("Extracted .m2v:")
                print(str(extracted_m2v))
                print()
                print("Running ffmpeg:")
                print(ffmpeg_cmd_str)
                print()

            ffmpeg_result = run_subprocess_safe(ffmpeg_cmd, cwd=SCRIPT_ROOT)
            ffmpeg_stdout = ffmpeg_result.stdout.strip() if ffmpeg_result.stdout else ""
            ffmpeg_stderr = ffmpeg_result.stderr.strip() if ffmpeg_result.stderr else ""

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
                cleanup_temp_video_files(extracted_m2v)
                success += 1
                log_lines.extend([
                    "=" * 80,
                    f"[OK] {dat_file}",
                    f"EXTRACTED M2V: {extracted_m2v}",
                    f"OUTPUT MP4: {out_mp4}",
                    "STEP: crid_mod",
                    f"COMMAND: {crid_cmd_str}",
                    f"RETURN CODE: {crid_result.returncode}",
                    "STDOUT:", crid_stdout if crid_stdout else "(empty)",
                    "STDERR:", crid_stderr if crid_stderr else "(empty)",
                    "STEP: ffmpeg",
                    f"COMMAND: {ffmpeg_cmd_str}",
                    f"RETURN CODE: {ffmpeg_result.returncode}",
                    "STDOUT:", ffmpeg_stdout if ffmpeg_stdout else "(empty)",
                    "STDERR:", ffmpeg_stderr if ffmpeg_stderr else "(empty)",
                    "CLEANUP:",
                    f"Deleted temp file: {extracted_m2v}",
                ])
            else:
                cleanup_temp_video_files(out_mp4)
                failed += 1
                log_lines.extend([
                    "=" * 80,
                    f"[FAILED] {dat_file}",
                    f"EXTRACTED M2V: {extracted_m2v}",
                    f"OUTPUT MP4: {out_mp4}",
                    "STEP: crid_mod",
                    f"COMMAND: {crid_cmd_str}",
                    f"RETURN CODE: {crid_result.returncode}",
                    "STDOUT:", crid_stdout if crid_stdout else "(empty)",
                    "STDERR:", crid_stderr if crid_stderr else "(empty)",
                    "STEP: ffmpeg",
                    f"COMMAND: {ffmpeg_cmd_str}",
                    f"RETURN CODE: {ffmpeg_result.returncode}",
                    "STDOUT:", ffmpeg_stdout if ffmpeg_stdout else "(empty)",
                    "STDERR:", ffmpeg_stderr if ffmpeg_stderr else "(empty)",
                ])

        except Exception as e:
            failed += 1
            log_lines.extend([
                "=" * 80,
                f"[ERROR] {dat_file}",
                "EXCEPTION:",
                str(e),
            ])
            if display_mode == "2" and pause_each_file:
                print("EXCEPTION:")
                print(str(e))
                print()
                wait_enter()

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
    if awb_files:
        print("\nSample files:")
        for p in awb_files[:10]:
            print(f"  {p}")

    if not awb_files:
        print("\nNo .awb files found.")
        wait_enter()
        return 0, 0, 1, log_path

    success = 0
    missing = 0
    failed = 0
    log_lines = []

    output_root.mkdir(parents=True, exist_ok=True)
    pause_each_file = (display_mode == "2" and mode_type == "single")

    for idx, awb_file in enumerate(awb_files, start=1):
        temp_wav = build_temp_wav_path(awb_file)
        out_mp3 = build_mp3_output_path(awb_file, output_root)

        if not should_process_output(out_mp3, policy, log_lines):
            continue

        vgm_cmd = build_vgmstream_wav_command(awb_file, temp_wav, resolved_tools)
        vgm_cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in vgm_cmd)

        if display_mode == "2":
            clear_screen()
            show_header()
            print("MP3 Conversion\n")
            print(f"[{idx}/{len(awb_files)}] {awb_file}\n")
            print("Running vgmstream:")
            print(vgm_cmd_str)
            print()

        try:
            if temp_wav.exists():
                safe_delete(temp_wav)

            vgm_result = run_subprocess_safe(vgm_cmd, cwd=SCRIPT_ROOT)
            vgm_stdout = vgm_result.stdout.strip() if vgm_result.stdout else ""
            vgm_stderr = vgm_result.stderr.strip() if vgm_result.stderr else ""

            if vgm_result.returncode != 0:
                failed += 1
                log_lines.extend([
                    "=" * 80,
                    f"[FAILED] {awb_file}",
                    "STEP: vgmstream",
                    f"COMMAND: {vgm_cmd_str}",
                    f"RETURN CODE: {vgm_result.returncode}",
                    "STDOUT:", vgm_stdout if vgm_stdout else "(empty)",
                    "STDERR:", vgm_stderr if vgm_stderr else "(empty)",
                ])
                if display_mode == "2":
                    print(f"Return code: {vgm_result.returncode}\n")
                    if vgm_stdout:
                        print("STDOUT:")
                        print(vgm_stdout)
                        print()
                    if vgm_stderr:
                        print("STDERR:")
                        print(vgm_stderr)
                        print()
                    if pause_each_file:
                        wait_enter()
                continue

            if not temp_wav.exists():
                missing += 1
                log_lines.extend([
                    "=" * 80,
                    f"[MISSING] {awb_file}",
                    "STEP: vgmstream output",
                    f"COMMAND: {vgm_cmd_str}",
                    f"RETURN CODE: {vgm_result.returncode}",
                    "STDOUT:", vgm_stdout if vgm_stdout else "(empty)",
                    "STDERR:", vgm_stderr if vgm_stderr else "(empty)",
                    "DETAIL: No extracted .wav found beside source .awb",
                ])
                if display_mode == "2":
                    print("No extracted .wav found.\n")
                    if pause_each_file:
                        wait_enter()
                continue

            ffmpeg_cmd = build_ffmpeg_mp3_command(temp_wav, out_mp3, resolved_tools)
            ffmpeg_cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in ffmpeg_cmd)

            if display_mode == "2":
                print("Extracted .wav:")
                print(str(temp_wav))
                print()
                print("Running ffmpeg:")
                print(ffmpeg_cmd_str)
                print()

            ffmpeg_result = run_subprocess_safe(ffmpeg_cmd, cwd=SCRIPT_ROOT)
            ffmpeg_stdout = ffmpeg_result.stdout.strip() if ffmpeg_result.stdout else ""
            ffmpeg_stderr = ffmpeg_result.stderr.strip() if ffmpeg_result.stderr else ""

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

            if ffmpeg_result.returncode == 0 and out_mp3.exists():
                safe_delete(temp_wav)
                success += 1
                log_lines.extend([
                    "=" * 80,
                    f"[OK] {awb_file}",
                    f"TEMP WAV: {temp_wav}",
                    f"OUTPUT MP3: {out_mp3}",
                    "STEP: vgmstream",
                    f"COMMAND: {vgm_cmd_str}",
                    f"RETURN CODE: {vgm_result.returncode}",
                    "STDOUT:", vgm_stdout if vgm_stdout else "(empty)",
                    "STDERR:", vgm_stderr if vgm_stderr else "(empty)",
                    "STEP: ffmpeg",
                    f"COMMAND: {ffmpeg_cmd_str}",
                    f"RETURN CODE: {ffmpeg_result.returncode}",
                    "STDOUT:", ffmpeg_stdout if ffmpeg_stdout else "(empty)",
                    "STDERR:", ffmpeg_stderr if ffmpeg_stderr else "(empty)",
                    "CLEANUP:",
                    f"Deleted temp file: {temp_wav}",
                ])
            else:
                safe_delete(out_mp3)
                failed += 1
                log_lines.extend([
                    "=" * 80,
                    f"[FAILED] {awb_file}",
                    f"TEMP WAV: {temp_wav}",
                    f"OUTPUT MP3: {out_mp3}",
                    "STEP: vgmstream",
                    f"COMMAND: {vgm_cmd_str}",
                    f"RETURN CODE: {vgm_result.returncode}",
                    "STDOUT:", vgm_stdout if vgm_stdout else "(empty)",
                    "STDERR:", vgm_stderr if vgm_stderr else "(empty)",
                    "STEP: ffmpeg",
                    f"COMMAND: {ffmpeg_cmd_str}",
                    f"RETURN CODE: {ffmpeg_result.returncode}",
                    "STDOUT:", ffmpeg_stdout if ffmpeg_stdout else "(empty)",
                    "STDERR:", ffmpeg_stderr if ffmpeg_stderr else "(empty)",
                ])

        except Exception as e:
            failed += 1
            log_lines.extend([
                "=" * 80,
                f"[ERROR] {awb_file}",
                "EXCEPTION:",
                str(e),
            ])
            if display_mode == "2" and pause_each_file:
                print("EXCEPTION:")
                print(str(e))
                print()
                wait_enter()

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
    if awb_files:
        print("\nSample files:")
        for p in awb_files[:10]:
            print(f"  {p}")

    if not awb_files:
        print("\nNo .awb files found.")
        wait_enter()
        return 0, 0, 1, log_path

    success = 0
    missing = 0
    failed = 0
    log_lines = []

    output_root.mkdir(parents=True, exist_ok=True)
    pause_each_file = (display_mode == "2" and mode_type == "single")

    for idx, awb_file in enumerate(awb_files, start=1):
        temp_wav = build_temp_wav_path(awb_file)
        out_flac = build_flac_output_path(awb_file, output_root)

        if not should_process_output(out_flac, policy, log_lines):
            continue

        vgm_cmd = build_vgmstream_wav_command(awb_file, temp_wav, resolved_tools)
        vgm_cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in vgm_cmd)

        if display_mode == "2":
            clear_screen()
            show_header()
            print("FLAC Conversion\n")
            print(f"[{idx}/{len(awb_files)}] {awb_file}\n")
            print("Running vgmstream:")
            print(vgm_cmd_str)
            print()

        try:
            if temp_wav.exists():
                safe_delete(temp_wav)

            vgm_result = run_subprocess_safe(vgm_cmd, cwd=SCRIPT_ROOT)
            vgm_stdout = vgm_result.stdout.strip() if vgm_result.stdout else ""
            vgm_stderr = vgm_result.stderr.strip() if vgm_result.stderr else ""

            if vgm_result.returncode != 0:
                failed += 1
                log_lines.extend([
                    "=" * 80,
                    f"[FAILED] {awb_file}",
                    "STEP: vgmstream",
                    f"COMMAND: {vgm_cmd_str}",
                    f"RETURN CODE: {vgm_result.returncode}",
                    "STDOUT:", vgm_stdout if vgm_stdout else "(empty)",
                    "STDERR:", vgm_stderr if vgm_stderr else "(empty)",
                ])
                if display_mode == "2":
                    print(f"Return code: {vgm_result.returncode}\n")
                    if vgm_stdout:
                        print("STDOUT:")
                        print(vgm_stdout)
                        print()
                    if vgm_stderr:
                        print("STDERR:")
                        print(vgm_stderr)
                        print()
                    if pause_each_file:
                        wait_enter()
                continue

            if not temp_wav.exists():
                missing += 1
                log_lines.extend([
                    "=" * 80,
                    f"[MISSING] {awb_file}",
                    "STEP: vgmstream output",
                    f"COMMAND: {vgm_cmd_str}",
                    f"RETURN CODE: {vgm_result.returncode}",
                    "STDOUT:", vgm_stdout if vgm_stdout else "(empty)",
                    "STDERR:", vgm_stderr if vgm_stderr else "(empty)",
                    "DETAIL: No extracted .wav found beside source .awb",
                ])
                if display_mode == "2":
                    print("No extracted .wav found.\n")
                    if pause_each_file:
                        wait_enter()
                continue

            flac_cmd = build_flac_encode_command(temp_wav, out_flac, resolved_tools)
            flac_cmd_str = " ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in flac_cmd)

            if display_mode == "2":
                print("Extracted .wav:")
                print(str(temp_wav))
                print()
                print("Running flac:")
                print(flac_cmd_str)
                print()

            flac_result = run_subprocess_safe(flac_cmd, cwd=SCRIPT_ROOT)
            flac_stdout = flac_result.stdout.strip() if flac_result.stdout else ""
            flac_stderr = flac_result.stderr.strip() if flac_result.stderr else ""

            if display_mode == "2":
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
                safe_delete(temp_wav)
                success += 1
                log_lines.extend([
                    "=" * 80,
                    f"[OK] {awb_file}",
                    f"TEMP WAV: {temp_wav}",
                    f"OUTPUT FLAC: {out_flac}",
                    "STEP: vgmstream",
                    f"COMMAND: {vgm_cmd_str}",
                    f"RETURN CODE: {vgm_result.returncode}",
                    "STDOUT:", vgm_stdout if vgm_stdout else "(empty)",
                    "STDERR:", vgm_stderr if vgm_stderr else "(empty)",
                    "STEP: flac",
                    f"COMMAND: {flac_cmd_str}",
                    f"RETURN CODE: {flac_result.returncode}",
                    "STDOUT:", flac_stdout if flac_stdout else "(empty)",
                    "STDERR:", flac_stderr if flac_stderr else "(empty)",
                    "CLEANUP:",
                    f"Deleted temp file: {temp_wav}",
                ])
            else:
                safe_delete(out_flac)
                failed += 1
                log_lines.extend([
                    "=" * 80,
                    f"[FAILED] {awb_file}",
                    f"TEMP WAV: {temp_wav}",
                    f"OUTPUT FLAC: {out_flac}",
                    "STEP: vgmstream",
                    f"COMMAND: {vgm_cmd_str}",
                    f"RETURN CODE: {vgm_result.returncode}",
                    "STDOUT:", vgm_stdout if vgm_stdout else "(empty)",
                    "STDERR:", vgm_stderr if vgm_stderr else "(empty)",
                    "STEP: flac",
                    f"COMMAND: {flac_cmd_str}",
                    f"RETURN CODE: {flac_result.returncode}",
                    "STDOUT:", flac_stdout if flac_stdout else "(empty)",
                    "STDERR:", flac_stderr if flac_stderr else "(empty)",
                ])

        except Exception as e:
            failed += 1
            log_lines.extend([
                "=" * 80,
                f"[ERROR] {awb_file}",
                "EXCEPTION:",
                str(e),
            ])
            if display_mode == "2" and pause_each_file:
                print("EXCEPTION:")
                print(str(e))
                print()
                wait_enter()

    with open(log_path, "w", encoding="utf-8") as f:
        for line in log_lines:
            f.write(line + "\n")

    return success, missing, failed, log_path

# =========================================================
# CHART RUNNER
# =========================================================

def build_chart_conversion_command(chart_input: Path, output_path: Path, resolved_tools: dict):
    exe = resolved_tools["MaichartConverter.exe"]
    return [
        str(exe),
        "CompileMa2",
        "-p", str(chart_input),
        "-o", str(output_path),
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
            wait_enter()

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
            wait_enter()

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
                wait_enter()

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
                wait_enter()

            return 0, 0, 1, log_path

    else:
        if not input_path.is_dir():
            print("Invalid folder input.")
            wait_enter()
            return 0, 0, 1, log_path

        ab_files = list_files_with_ext(input_path, ".ab")

        print(f".ab files found: {len(ab_files)}")
        if ab_files:
            print("\nSample files:")
            for p in ab_files[:10]:
                print(f"  {p}")

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
                wait_enter()

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
                wait_enter()

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
                safe_delete(temp_wav)
                continue

            ffmpeg_result = run_subprocess_safe(ffmpeg_cmd, cwd=SCRIPT_ROOT)
            if ffmpeg_result.returncode == 0 and out_mp3.exists():
                safe_delete(temp_wav)
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
                safe_delete(temp_wav)
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
            safe_delete(temp_wav)
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

        resolved_video_id = extract_numeric_id_from_stem(dat_file)
        if resolved_video_id is None:
            resolved_video_id = cue_id if cue_id is not None else song_id

        out_mp4 = out_root / f"{resolved_video_id:06d}.mp4"

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

            crid_result = run_subprocess_safe(crid_cmd, cwd=SCRIPT_ROOT)
            extracted_m2v = find_extracted_m2v_for_dat(dat_file)

            if crid_result.returncode != 0 or extracted_m2v is None or not extracted_m2v.exists():
                failed += 1
                log_lines.extend([
                    "=" * 80,
                    f"[FAILED] {out_mp4.name}",
                    f"SOURCE DAT: {dat_file}",
                    f"song_id: {song_id}",
                    "STEP: crid_mod",
                    crid_result.stdout.strip() if crid_result.stdout else "(empty)",
                    crid_result.stderr.strip() if crid_result.stderr else "(empty)",
                ])
                cleanup_temp_video_files(extracted_m2v)
                continue

            ffmpeg_cmd = build_ffmpeg_mp4_command(extracted_m2v, out_mp4, resolved_tools)
            ffmpeg_result = run_subprocess_safe(ffmpeg_cmd, cwd=SCRIPT_ROOT)

            if ffmpeg_result.returncode == 0 and out_mp4.exists():
                safe_delete(extracted_m2v)
                success += 1
                log_lines.extend(["=" * 80, f"[OK] {out_mp4.name}", f"SOURCE DAT: {dat_file}", f"song_id: {song_id}"])
            else:
                safe_delete(out_mp4)
                safe_delete(extracted_m2v)
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
            safe_delete(dat_file.with_suffix(".m2v"))
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

    db_parser.add_argument("--decimal", action="store_true")
    db_parser.add_argument("--use-number", action="store_true")
    db_parser.add_argument("--json-log", action="store_true")
    db_parser.add_argument("--zip-after", action="store_true")
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
        "MaichartConverter.exe": args.tool_maichartconverter,
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
        "auto_convert_assets": auto_convert_assets,
        "auto_convert_targets": auto_convert_targets,
        "existing_assets_policy": args.asset_policy,
        "existing_output_policy": args.output_policy,
        "use_number": args.use_number,
        "json_log": args.json_log,
        "zip_after": args.zip_after,
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

    if output_folder_has_relevant_database_outputs(payload["output_path"]):
        if output_policy == "skip":
            payload["output_path"].mkdir(parents=True, exist_ok=True)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("[SKIPPED]\n")
                f.write(f"OUTPUT DIR: {payload['output_path']}\n")
                f.write("DETAIL: Existing output folder kept.\n")
            return 0, 0, 0, log_path
        elif output_policy == "overwrite":
            clear_folder_contents(payload["output_path"])

    if payload.get("auto_convert_assets"):
        axxx_root = payload["axxx_path"]
        asset_policy = payload.get("existing_assets_policy", "overwrite")

        if payload["music_path"] is None and "music" in selected_targets:
            music_path, s, m, f, logs = auto_build_music_assets(
                axxx_root,
                resolved_tools,
                display_mode,
                asset_policy,
                progress_callback=progress_step,
            )
            payload["music_path"] = music_path
            prep_missing += m
            prep_failed += f
            prep_logs.extend(logs)
            auto_temp_dirs.append(music_path)

        if payload["video_path"] is None and "video" in selected_targets:
            video_path, s, m, f, logs = auto_build_video_assets(
                axxx_root,
                resolved_tools,
                display_mode,
                asset_policy,
                progress_callback=progress_step,
            )
            payload["video_path"] = video_path
            prep_missing += m
            prep_failed += f
            prep_logs.extend(logs)
            auto_temp_dirs.append(video_path)

        if payload["cover_path"] is None and "cover" in selected_targets:
            cover_path, s, m, f, logs = auto_build_cover_assets(
                axxx_root,
                resolved_tools,
                display_mode,
                asset_policy,
                progress_callback=progress_step,
            )
            payload["cover_path"] = cover_path
            prep_missing += m
            prep_failed += f
            prep_logs.extend(logs)
            auto_temp_dirs.append(cover_path)

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

        if prep_missing > 0 or prep_failed > 0:
            required_ready = False
            if prep_missing > 0:
                required_fail_reasons.append(f"Auto-build missing count: {prep_missing}")
            if prep_failed > 0:
                required_fail_reasons.append(f"Auto-build failed count: {prep_failed}")

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

        return 0, prep_missing, prep_failed + 1, log_path

    progress_tick("Converting ma2 files & creating folders...")
    cmd = build_compile_database_command(payload, resolved_tools)

    if display_mode == "2":
        print("Running command:\n")
        print(" ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in cmd))
        print()

    try:
        result = run_subprocess_safe(cmd, cwd=SCRIPT_ROOT)
        stdout_text = result.stdout.strip() if result.stdout else ""
        stderr_text = result.stderr.strip() if result.stderr else ""

        progress_step("Converting ma2 files & creating folders...")
        if result.returncode == 0 and done_items < total_items:
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
            f.write(" ".join(f'"{str(x)}"' if " " in str(x) else str(x) for x in cmd) + "\n\n")
            f.write("STDOUT:\n")
            f.write(stdout_text if stdout_text else "(empty)")
            f.write("\n\nSTDERR:\n")
            f.write(stderr_text if stderr_text else "(empty)")
            f.write("\n")

        if display_mode == "2":
            if stdout_text:
                print("STDOUT:\n")
                print(stdout_text)
                print()
            if stderr_text:
                print("STDERR:\n")
                print(stderr_text)
                print()
            wait_enter("Database conversion finished. Press Enter...")

        if result.returncode == 0:
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

    for idx, axxx_path in enumerate(axxx_paths, start=1):
        item_payload = dict(payload)
        item_payload["mode_type"] = "single"
        item_payload["axxx_path"] = axxx_path
        item_payload["output_path"] = base_output / axxx_path.name
        item_payload["auto_generated_temp_dirs"] = []
        item_payload["mode_label"] = f"{axxx_path.name} {idx}/{len(axxx_paths)}"

        success, missing, failed, log_path = run_database_shell_single(item_payload, display_mode, resolved_tools)
        total_success += success
        total_missing += missing
        total_failed += failed
        register_temp_dirs(item_payload.get("auto_generated_temp_dirs"))
        log_lines.append(f"[{axxx_path.name}] success={success} missing={missing} failed={failed} log={log_path}")
        if failed > 0 and not CLI_MODE:
            if not ask_yes_no("There's an error in the process shit. Continue? (y/n): "):
                log_lines.append("[ABORTED] User stopped batch after error.")
                break
        if idx < len(axxx_paths):
            countdown_between_batches(10, completed_label=axxx_path.name)

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

    scene_completion(success, missing, failed, log_path)


def main():
    global CLI_MODE

    if len(sys.argv) > 1:
        CLI_MODE = True
        exit_code = run_cli_mode(sys.argv[1:])
        sys.exit(exit_code)

    CLI_MODE = False
    countdown_with_skip(10)

    while True:
        choice = scene_main_menu()

        if choice == "0":
            clear_screen()
            print("Exiting.")
            sys.exit(0)

        handle_mode(choice)


if __name__ == "__main__":
    main()

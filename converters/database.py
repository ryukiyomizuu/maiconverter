from pathlib import Path

from converters.image import build_assetstudio_command, flatten_assetstudio_texture2d_output
from converters.mp3 import build_ffmpeg_mp3_command, build_temp_wav_path, build_vgmstream_wav_command
from converters.mp4 import (
    build_crid_command,
    build_ffmpeg_mp4_command,
    find_extracted_m2v_for_dat,
)
from tools.parser import (
    build_numeric_file_index,
    parse_music_xml_basic,
    resolve_awb_for_song,
    resolve_dat_for_song,
)
from tools.tools import cleanup_temp_video_files, safe_delete


def extract_music_numeric_id_from_awb(awb_file: Path):
    stem = awb_file.stem.lower()
    if stem.startswith("music"):
        tail = stem[5:]
        if tail.isdigit():
            return int(tail)
    return None


def extract_numeric_id_from_stem(file_path: Path):
    digits = "".join(ch for ch in file_path.stem if ch.isdigit())
    if digits:
        return int(digits)
    return None


def auto_build_music_assets(axxx_root: Path, resolved_tools: dict, existing_policy: str):
    music_root = axxx_root / "music"
    sound_root = axxx_root / "SoundData"
    out_root = axxx_root / "musicMP3"
    out_root.mkdir(parents=True, exist_ok=True)
    success = missing = failed = 0
    log_lines = []

    if not music_root.exists() or not sound_root.exists():
        return out_root, success, missing, failed, ["Music or SoundData folder not found."]

    awb_index = build_numeric_file_index(sound_root, ".awb")
    for xml_path in sorted(music_root.rglob("Music.xml")):
        meta = parse_music_xml_basic(xml_path)
        song_id, cue_id = meta["song_id"], meta["cue_id"]
        if song_id is None or cue_id is None:
            missing += 1
            continue
        awb_file = resolve_awb_for_song(sound_root, awb_index, song_id, cue_id)
        if awb_file is None:
            missing += 1
            continue
        temp_wav = build_temp_wav_path(awb_file)
        resolved_audio_id = extract_music_numeric_id_from_awb(awb_file) or cue_id or song_id
        out_mp3 = out_root / f"music{resolved_audio_id:06d}.mp3"
        if out_mp3.exists() and existing_policy == "skip":
            continue
        if out_mp3.exists() and existing_policy == "overwrite":
            safe_delete(out_mp3)
        try:
            vgm_result = build_vgmstream_wav_command(awb_file, temp_wav, resolved_tools)
            ff_result = build_ffmpeg_mp3_command(temp_wav, out_mp3, resolved_tools)
            _ = (vgm_result, ff_result)
            success += 1
        except Exception:
            failed += 1
        finally:
            safe_delete(temp_wav)
    return out_root, success, missing, failed, log_lines


def auto_build_video_assets(axxx_root: Path, resolved_tools: dict, existing_policy: str):
    movie_root = axxx_root / "MovieData"
    music_root = axxx_root / "music"
    out_root = axxx_root / "Movie"
    out_root.mkdir(parents=True, exist_ok=True)
    success = missing = failed = 0
    log_lines = []
    if not movie_root.exists() or not music_root.exists():
        return out_root, success, missing, failed, ["MovieData or music folder not found."]

    for xml_path in sorted(music_root.rglob("Music.xml")):
        meta = parse_music_xml_basic(xml_path)
        song_id, cue_id = meta["song_id"], meta["cue_id"]
        if song_id is None:
            missing += 1
            continue
        dat_file = resolve_dat_for_song(movie_root, song_id, cue_id)
        if dat_file is None:
            missing += 1
            continue
        # Output name mirrors the dat file stem (6-digit, e.g. 001200.mp4).
        out_mp4 = out_root / f"{dat_file.stem}.mp4"
        if out_mp4.exists() and existing_policy == "skip":
            continue
        if out_mp4.exists() and existing_policy == "overwrite":
            safe_delete(out_mp4)
        try:
            _ = build_crid_command(dat_file, resolved_tools)
            extracted = find_extracted_m2v_for_dat(dat_file)
            if extracted:
                _ = build_ffmpeg_mp4_command(extracted, out_mp4, resolved_tools)
                cleanup_temp_video_files(extracted)
            success += 1
        except Exception:
            failed += 1
    return out_root, success, missing, failed, log_lines


def auto_build_cover_assets(axxx_root: Path, resolved_tools: dict, existing_policy: str):
    source_root = axxx_root / "AssetBundleImages" / "jacket"
    out_root = axxx_root / "Jackets"
    out_root.mkdir(parents=True, exist_ok=True)
    success = missing = failed = 0
    log_lines = []
    if not source_root.exists() or not source_root.is_dir():
        return out_root, success, 1, failed, ["Jacket source folder not found."]
    try:
        cmd = build_assetstudio_command(source_root, out_root, resolved_tools)
        _ = cmd
        _ = flatten_assetstudio_texture2d_output(out_root)
        success = 1
    except Exception:
        failed = 1
    return out_root, success, missing, failed, log_lines

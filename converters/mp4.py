from pathlib import Path


def build_mp4_output_path(dat_file: Path, output_root: Path):
    return output_root / f"{dat_file.stem}.mp4"


def find_extracted_m2v_for_dat(dat_file: Path):
    direct = dat_file.with_suffix(".m2v")
    if direct.exists():
        return direct
    candidates = list(dat_file.parent.glob("*.m2v"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def build_crid_command(dat_file: Path, resolved_tools: dict):
    crid_exe = resolved_tools["crid_mod.exe"]
    return [
        str(crid_exe),
        "-b", "7F455149",
        "-a", "9DF55E68",
        "-v", str(dat_file),
    ]


def build_ffmpeg_mp4_command(video_input: Path, output_mp4: Path, resolved_tools: dict):
    ffmpeg_exe = resolved_tools["ffmpeg.exe"]
    return [
        str(ffmpeg_exe),
        "-y",
        "-i", str(video_input),
        "-c:v", "libx265",
        "-an",
        "-crf", "36",
        str(output_mp4),
    ]

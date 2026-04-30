"""
Standalone helper: convert leftover .m2v files in MovieData/ -> Movie/*.mp4
Skips any .mp4 that already exists. Does NOT re-run crid.
Run from the MAS folder:
  python _m2v_finish.py --a000 "C:\path\to\A000"
  python _m2v_finish.py --a000 "D:\KDX\A000"        (if drive letter changed)
"""
import sys
import argparse
import subprocess
from pathlib import Path

# ── Parse A000 path first ────────────────────────────────────────────────────
_pre = argparse.ArgumentParser(add_help=False)
_pre.add_argument("--a000", default=r"C:\Users\Lon\Downloads\KDX\A000")
_pre_args, _ = _pre.parse_known_args()

A000        = Path(_pre_args.a000)
MOVIE_DATA  = A000 / "MovieData"
MOVIE_OUT   = A000 / "Movie"
MUSIC_MP3   = A000 / "musicMP3"

MAS_ROOT    = Path(__file__).resolve().parent
sys.path.insert(0, str(MAS_ROOT))

from converters.mp4 import (
    _pick_encoder,
    is_static_video,
    get_audio_duration,
    build_ffmpeg_static_stretch_command,
    _STATIC_FALLBACK_DURATION,
    load_config,
)

MOVIE_OUT.mkdir(parents=True, exist_ok=True)

ffmpeg_exe  = MAS_ROOT / "ffmpeg" / "ffmpeg.exe"
ffprobe_exe = MAS_ROOT / "ffmpeg" / "ffprobe.exe"
ffprobe_str = str(ffprobe_exe) if ffprobe_exe.exists() else None

resolved_tools = {
    "ffmpeg.exe":  ffmpeg_exe,
    "ffprobe.exe": ffprobe_exe,
}

NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

m2v_files = sorted(MOVIE_DATA.glob("*.m2v"))
total     = len(m2v_files)
skipped   = 0
success   = 0
failed    = 0

import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--static-mode", default=None)
_args, _ = _ap.parse_known_args()
static_mode = _args.static_mode or load_config().get("static_video", "loop")
codec, qflag, qval = _pick_encoder(str(ffmpeg_exe))
print(f"Encoder : {codec}")
print(f"Static  : {static_mode}")
print(f"Total m2v: {total}\n")

for i, m2v in enumerate(m2v_files, 1):
    out_mp4 = MOVIE_OUT / f"{m2v.stem}.mp4"

    if out_mp4.exists():
        skipped += 1
        continue

    prefix = f"[{i}/{total}] {m2v.name}"

    if is_static_video(m2v, ffprobe_str):
        if static_mode == "skip":
            print(f"{prefix} — static, skipped")
            skipped += 1
            continue
        # loop/stretch
        _mp3 = MUSIC_MP3 / f"music{m2v.stem}.mp3"
        if not _mp3.exists():
            _mp3 = None
        duration = get_audio_duration(_mp3, ffprobe_str) if _mp3 else None
        if duration is None:
            duration = _STATIC_FALLBACK_DURATION
        cmd = build_ffmpeg_static_stretch_command(m2v, out_mp4, duration, resolved_tools)
        print(f"{prefix} — static, stretching to {duration:.1f}s")
    else:
        cmd = [
            str(ffmpeg_exe), "-y", "-i", str(m2v),
            "-c:v", codec, qflag, qval,
        ]
        if codec in ("libx265", "libx264"):
            cmd += ["-preset", "ultrafast", "-threads", "2"]
        cmd += ["-an", str(out_mp4)]
        print(f"{prefix} — encoding")

    result = subprocess.run(cmd, capture_output=True, creationflags=NO_WINDOW)
    if result.returncode == 0 and out_mp4.exists():
        success += 1
        m2v.unlink(missing_ok=True)   # clean up m2v after successful encode
    else:
        failed += 1
        out_mp4.unlink(missing_ok=True)
        print(f"  FAILED (rc={result.returncode})")
        if result.stderr:
            print("  ", result.stderr.decode(errors="replace")[-200:])

print(f"\nDone.  success={success}  skipped={skipped}  failed={failed}")

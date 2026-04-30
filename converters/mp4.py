import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_FILE = _ROOT / "config.json"
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# All known encoder profiles: (codec, quality_flag, quality_value)
ENCODER_PROFILES = {
    "hevc_nvenc": ("hevc_nvenc", "-qp",  "36"),
    "h264_nvenc": ("h264_nvenc", "-qp",  "36"),
    "hevc_amf":   ("hevc_amf",   "-crf", "36"),
    "h264_amf":   ("h264_amf",   "-crf", "36"),
    "libx265":    ("libx265",    "-crf", "36"),
    "libx264":    ("libx264",    "-crf", "36"),
}


def load_config() -> dict:
    try:
        return json.loads(_CONFIG_FILE.read_text())
    except Exception:
        return {}


def save_config(data: dict):
    existing = load_config()
    existing.update(data)
    _CONFIG_FILE.write_text(json.dumps(existing, indent=2))


def build_mp4_output_path(dat_file: Path, output_root: Path):
    # MaichartConverter scans mp4 files and reads musicID = filename.Substring(2, 4).
    # So filenames must be 6-digit zero-padded (e.g. 001200.mp4 → ID "1200").
    return output_root / f"{dat_file.stem}.mp4"


def find_extracted_m2v_for_dat(dat_file: Path):
    # Only accept the exact matching m2v — never fall back to a random file in the folder.
    direct = dat_file.with_suffix(".m2v")
    return direct if direct.exists() else None


# .dat files under this size are almost certainly static (single-frame USM)
_STATIC_SIZE_THRESHOLD_BYTES = 500_000  # 500 KB


def is_static_video(m2v_path: Path, ffprobe_exe: str | None = None) -> bool:
    """
    Returns True if the video is a static (non-animated) clip.
    Step 1: quick size check on the source .m2v — static files are tiny.
    Step 2: if size is ambiguous, ask ffprobe to count unique scene changes.
    """
    size = m2v_path.stat().st_size

    # Fast path: file is very small → almost certainly static
    if size < _STATIC_SIZE_THRESHOLD_BYTES:
        return True

    # Slow path: run ffprobe scene-change detection
    if ffprobe_exe is None:
        return False
    try:
        result = subprocess.run(
            [
                ffprobe_exe,
                "-v", "quiet",
                "-select_streams", "v:0",
                "-show_frames",
                "-read_intervals", "%+10",   # only inspect first 10 seconds
                "-show_entries", "frame=pict_type",
                "-of", "csv=p=0",
                str(m2v_path),
            ],
            capture_output=True, text=True, timeout=15,
            creationflags=_NO_WINDOW,
        )
        frames = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        if not frames:
            return False
        # If every frame is an I-frame (intra-coded), it's likely a slideshow/still
        # A real video will have P and B frames mixed in
        unique_types = set(frames)
        return unique_types <= {"I"}
    except Exception:
        return False



_STATIC_FALLBACK_DURATION = 180.0  # seconds used when no audio file is found


def get_audio_duration(audio_path: Path, ffprobe_exe: str | None = None) -> float | None:
    """Return duration in seconds via ffprobe, or None on failure."""
    if ffprobe_exe is None or not audio_path.exists():
        return None
    try:
        result = subprocess.run(
            [ffprobe_exe, "-v", "quiet",
             "-show_entries", "format=duration",
             "-of", "csv=p=0",
             str(audio_path)],
            capture_output=True, text=True, timeout=15,
            creationflags=_NO_WINDOW,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def build_ffmpeg_static_stretch_command(m2v_path: Path, output_mp4: Path, duration: float, resolved_tools: dict):
    """Extend a static (freeze-frame) m2v to fill `duration` seconds.

    Uses tpad to clone the last decoded frame rather than stream_loop, which is
    unreliable on raw MPEG-2 (.m2v) because the mpegvideo demuxer does not
    reset timestamps on each loop iteration.
    """
    ffmpeg_exe = resolved_tools["ffmpeg.exe"]
    codec, qflag, qval = _pick_encoder(str(ffmpeg_exe))

    cmd = [
        str(ffmpeg_exe),
        "-y",
        "-i", str(m2v_path),
        "-vf", f"tpad=stop_mode=clone:stop_duration={duration:.3f}",
        "-t", f"{duration:.3f}",
        "-c:v", codec,
        qflag, qval,
        "-an",
    ]

    if codec in ("libx265", "libx264"):
        cmd += ["-preset", "ultrafast", "-threads", "2"]

    cmd.append(str(output_mp4))
    return cmd


def build_crid_command(dat_file: Path, resolved_tools: dict):
    crid_exe = resolved_tools["crid_mod.exe"]
    return [
        str(crid_exe),
        "-b", "7F455149",
        "-a", "9DF55E68",
        "-v", str(dat_file),
    ]


@lru_cache(maxsize=1)
def _detect_gpu() -> str:
    """Returns 'nvidia', 'amd', or 'none'. Cached after first call."""
    try:
        result = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "name"],
            capture_output=True, text=True, timeout=5,
            creationflags=_NO_WINDOW,
        )
        output = result.stdout.upper()
        if "NVIDIA" in output:
            return "nvidia"
        if "AMD" in output or "RADEON" in output:
            return "amd"
    except Exception:
        pass
    return "none"


def _encoder_works(ffmpeg_exe: str, codec: str) -> bool:
    """Quick probe: encode 1 frame of black video to null to test if codec loads."""
    try:
        result = subprocess.run(
            [
                ffmpeg_exe,
                "-f", "lavfi", "-i", "nullsrc=s=64x64",
                "-frames:v", "1",
                "-c:v", codec,
                "-f", "null", "-",
            ],
            capture_output=True, timeout=10,
            creationflags=_NO_WINDOW,
        )
        return result.returncode == 0
    except Exception:
        return False


@lru_cache(maxsize=1)
def _pick_encoder(ffmpeg_exe: str):
    """
    Returns (codec, quality_flag, quality_value) for the best available encoder.
    Respects config.json override, otherwise auto-detects GPU.
    Priority: HW H264 -> HW H265 -> SW H264 -> SW H265
    H264/libx264 preferred for widespread compatibility (H265 requires MajdataX 5.1.7+).
    """
    override = load_config().get("video_encoder", "auto")
    if override != "auto" and override in ENCODER_PROFILES:
        return ENCODER_PROFILES[override]

    gpu = _detect_gpu()

    candidates = []
    if gpu == "nvidia":
        candidates = [
            ("h264_nvenc", "-qp", "36"),
            ("hevc_nvenc", "-qp", "36"),
        ]
    elif gpu == "amd":
        candidates = [
            ("h264_amf",   "-crf", "36"),
            ("hevc_amf",   "-crf", "36"),
        ]

    candidates += [
        ("libx264", "-crf", "36"),
        ("libx265", "-crf", "36"),
    ]

    for codec, qflag, qval in candidates:
        if _encoder_works(ffmpeg_exe, codec):
            return codec, qflag, qval

    return "libx264", "-crf", "36"


def get_active_encoder_label(ffmpeg_exe: str) -> str:
    """Returns the codec name that will be used, e.g. 'hevc_nvenc'."""
    codec, _, _ = _pick_encoder(ffmpeg_exe)
    return codec


def build_ffmpeg_mp4_command(video_input: Path, output_mp4: Path, resolved_tools: dict):
    ffmpeg_exe = resolved_tools["ffmpeg.exe"]
    codec, qflag, qval = _pick_encoder(str(ffmpeg_exe))

    cmd = [
        str(ffmpeg_exe),
        "-y",
        "-i", str(video_input),
        "-c:v", codec,
        qflag, qval,
        "-an",
    ]

    # SW encoders benefit from preset + thread cap; HW encoders manage their own pipeline
    if codec in ("libx265", "libx264"):
        cmd += ["-preset", "ultrafast", "-threads", "2"]

    cmd.append(str(output_mp4))
    return cmd


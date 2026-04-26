from pathlib import Path


def build_mp3_output_path(awb_file: Path, output_root: Path):
    return output_root / f"{awb_file.stem}.mp3"


def build_temp_wav_path(awb_file: Path):
    return awb_file.with_suffix(".wav")


def build_vgmstream_wav_command(awb_file: Path, temp_wav: Path, resolved_tools: dict):
    vgm_exe = resolved_tools["vgmstream-cli.exe"]
    return [
        str(vgm_exe),
        "-o", str(temp_wav),
        str(awb_file),
    ]


def build_ffmpeg_mp3_command(wav_file: Path, output_mp3: Path, resolved_tools: dict):
    ffmpeg_exe = resolved_tools["ffmpeg.exe"]
    return [
        str(ffmpeg_exe),
        "-y",
        "-i", str(wav_file),
        "-vn",
        "-acodec", "libmp3lame",
        "-q:a", "2",
        str(output_mp3),
    ]

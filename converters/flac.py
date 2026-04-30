from pathlib import Path


def build_flac_output_path(awb_file: Path, output_root: Path):
    return output_root / f"{awb_file.stem}.flac"


def build_flac_encode_command(wav_file: Path, output_flac: Path, resolved_tools: dict):
    flac_exe = resolved_tools["flac.exe"]
    return [
        str(flac_exe),
        "-f",
        "-o", str(output_flac),
        str(wav_file),
    ]

from pathlib import Path


def move_image_files_to_root(source_dir: Path, dest_dir: Path):
    moved = 0
    for p in source_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tga"}:
            continue
        target = dest_dir / p.name
        if p.resolve() == target.resolve():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        p.replace(target)
        moved += 1
    return moved


def flatten_assetstudio_texture2d_output(output_root: Path):
    texture_dir = output_root / "Texture2D"
    if not texture_dir.exists() or not texture_dir.is_dir():
        return 0
    return move_image_files_to_root(texture_dir, output_root)


def build_assetstudio_command(asset_input: Path, output_dir: Path, resolved_tools: dict):
    exe = resolved_tools["AssetStudio.CLI.exe"]
    return [
        str(exe),
        str(asset_input),
        str(output_dir),
        "--game", "Normal",
        "--types", "Texture2D",
    ]

import locale
import shutil
import subprocess
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tga", ".webp"}


def run_subprocess_safe(cmd, cwd=None):
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False),
        errors="replace",
    )


def safe_delete(path: Path):
    try:
        if path is not None and path.exists() and path.is_file():
            path.unlink()
            return True
    except Exception:
        pass
    return False


def safe_rmtree(path: Path):
    try:
        if path is not None and path.exists() and path.is_dir():
            shutil.rmtree(path)
            return True
    except Exception:
        pass
    return False


def cleanup_temp_video_files(*paths: Path):
    for p in paths:
        safe_delete(p)


def safe_int(value):
    try:
        return int(str(value).strip())
    except Exception:
        return None


def list_files_with_ext(path: Path, ext: str):
    ext = ext.lower()
    if path.is_file():
        return [path] if path.suffix.lower() == ext else []
    return sorted([p for p in path.rglob(f"*{ext}") if p.is_file()])


def count_existing_files_with_ext(folder: Path, ext: str):
    if not folder.exists():
        return 0
    return sum(1 for p in folder.rglob(f"*{ext}") if p.is_file())


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
    if not folder.exists() or not folder.is_dir():
        return 0
    deleted_files = []
    deleted_count = 0
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            if safe_delete(p):
                deleted_files.append(p)
                deleted_count += 1
    remove_empty_parent_dirs(deleted_files, folder.resolve())
    return deleted_count


def clear_folder_contents(folder: Path):
    if not folder.exists() or not folder.is_dir():
        return
    for child in folder.iterdir():
        if child.is_file():
            safe_delete(child)
        elif child.is_dir():
            safe_rmtree(child)

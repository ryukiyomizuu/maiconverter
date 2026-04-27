#!/usr/bin/env python3
"""
push-wiki.py — Run this AFTER initializing the GitHub wiki through the web UI.

Steps:
  1. Go to: https://github.com/LonerYlon/maiconverter/wiki
  2. Click "Create the first page"
  3. Title: Home   Content: (anything, e.g. "initializing")
  4. Click "Save page"
  5. Then run:  python push-wiki.py
"""

import subprocess, shutil
from pathlib import Path

WIKI_SRC   = Path(__file__).resolve().parent / "docs" / "wiki"
WIKI_CLONE = Path(__file__).resolve().parent / "_wiki_tmp"
WIKI_REPO  = "https://github.com/LonerYlon/maiconverter.wiki.git"

def run(cmd, **kwargs):
    r = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if r.returncode != 0:
        print(f"ERROR: {' '.join(str(c) for c in cmd)}")
        print(r.stderr)
        raise SystemExit(1)
    return r.stdout.strip()

print("Cloning wiki repo...")
if WIKI_CLONE.exists():
    shutil.rmtree(WIKI_CLONE)

run(["git", "clone", WIKI_REPO, str(WIKI_CLONE)])

print("Copying wiki pages...")
for md_file in WIKI_SRC.glob("*.md"):
    dest = WIKI_CLONE / md_file.name
    shutil.copy(md_file, dest)
    print(f"  + {md_file.name}")

print("Committing...")
run(["git", "add", "."], cwd=str(WIKI_CLONE))
run(["git", "commit", "-m", "docs: full wiki — 14 pages (auto-pushed by push-wiki.py)"], cwd=str(WIKI_CLONE))

print("Pushing to GitHub wiki...")
run(["git", "push"], cwd=str(WIKI_CLONE))

print()
print("Done! Wiki is live at:")
print("  https://github.com/LonerYlon/maiconverter/wiki")

# cleanup (use onerror to handle read-only .git objects on Windows)
def _remove_readonly(func, path, _):
    import stat
    Path(path).chmod(stat.S_IWRITE)
    func(path)

shutil.rmtree(WIKI_CLONE, onerror=_remove_readonly)

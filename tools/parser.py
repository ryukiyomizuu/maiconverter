import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from tools.tools import safe_int


def get_xml_child_text(elem, path, default=""):
    node = elem.find(path)
    if node is None or node.text is None:
        return default
    return node.text.strip()


def parse_music_xml_basic(xml_path: Path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    payload = root
    if root.tag.lower() != "musicdata":
        for elem in root.iter():
            if elem.tag.lower() == "musicdata":
                payload = elem
                break
    song_id = safe_int(get_xml_child_text(payload, "name/id", ""))
    cue_id = safe_int(get_xml_child_text(payload, "cueName/id", ""))
    movie_id = safe_int(get_xml_child_text(payload, "movieName/id", ""))
    return {"xml_path": xml_path, "song_id": song_id, "cue_id": cue_id, "movie_id": movie_id}


def build_numeric_file_index(root: Path, ext: str):
    index = defaultdict(list)
    for p in root.rglob(f"*{ext}"):
        if not p.is_file():
            continue
        nums = set(re.findall(r"\d+", p.stem))
        nums.update(re.findall(r"\d+", p.name))
        for n in nums:
            try:
                index[int(n)].append(p)
            except ValueError:
                pass
    return index


def choose_best_numeric_match(candidates):
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: (len(str(p)), p.name.lower()))[0]


def resolve_awb_for_song(sound_root: Path, awb_index, song_id: int, cue_id: int):
    direct = sound_root / f"music{song_id:06d}.awb"
    if direct.exists():
        return direct
    direct_alt = sound_root / f"music{cue_id:06d}.awb"
    if direct_alt.exists():
        return direct_alt
    candidates = awb_index.get(song_id, [])
    if candidates:
        best = choose_best_numeric_match(candidates)
        if best:
            return best
    candidates = awb_index.get(cue_id, [])
    if candidates:
        best = choose_best_numeric_match(candidates)
        if best:
            return best
    return None


def resolve_dat_for_song(movie_root: Path, song_id: int, cue_id: int = None):
    direct = movie_root / f"{song_id:06d}.dat"
    if direct.exists():
        return direct
    if cue_id is not None:
        direct_alt = movie_root / f"{cue_id:06d}.dat"
        if direct_alt.exists():
            return direct_alt
    return None

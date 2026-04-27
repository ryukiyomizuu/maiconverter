# Maimai's AIO Conversion

> A Windows-based all-in-one pipeline for converting maimai DX game assets — audio, video, charts, images, and full database packages — into formats usable by custom clients like [AstroDX](https://github.com/2394425147/astrodx).

*Created by Ryuki*

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Setup](#setup)
- [Folder Structure](#folder-structure)
- [Usage](#usage)
  - [Interactive Mode](#interactive-mode)
  - [CLI Mode](#cli-mode)
- [Conversion Modes](#conversion-modes)
  - [1 · MP4 Conversion](#1--mp4-conversion-dat--mp4)
  - [2 · MP3 Conversion](#2--mp3-conversion-awb--mp3)
  - [3 · FLAC Conversion](#3--flac-conversion-awb--flac)
  - [4 · Chart Conversion](#4--chart-conversion-ma2--simai)
  - [5 · Database Conversion](#5--database-conversion-axxx-full-pipeline)
  - [6 · Image Conversion](#6--image-conversion-ab--png)
- [Database Options Reference](#database-options-reference)
- [Output Formats](#output-formats)
- [Credits & Third-Party Tools](#credits--third-party-tools)

---

## Features

| Feature | Details |
|---|---|
| **MP4** | Decrypt `.dat` USM videos → `.mp4` (single or batch) |
| **MP3** | Decode `.awb` audio streams → `.mp3` (single or batch) |
| **FLAC** | Decode `.awb` audio streams → `.flac` (lossless, single or batch) |
| **Chart** | Compile `.ma2` charts → Simai format for custom clients |
| **Database** | Full AXXX folder pipeline → categorised song packages |
| **Image** | Extract Unity `.ab` bundles → `.png` jacket / background images |
| **ADX export** | Package output as `.adx` (AstroDX format) per-track or per-category |
| **Batch mode** | Process multiple AXXX folders in one run |
| **Auto asset detection** | Finds `music*`, `Jackets`, video folders inside AXXX automatically |
| **Resume-safe** | Per-folder output policy (overwrite / skip) |
| **CLI mode** | Full scriptable interface for automation pipelines |
| **First-run setup** | `setup.py` checks tools, auto-downloads ffmpeg & vgmstream |

---

## Requirements

### Python
- **Python 3.10 or newer** — [python.org/downloads](https://www.python.org/downloads/)
- No extra pip packages required (stdlib only)

### External tools

| Tool | Used for | Auto-install | Manual download |
|---|---|---|---|
| **maiforge.exe** | Database & chart compilation | ✅ Bundled | — |
| **ffmpeg / ffprobe** | Audio & video encoding | ✅ via `setup.py` | [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases) |
| **vgmstream-cli** | `.awb` audio stream decoding | ✅ via `setup.py` | [vgmstream/vgmstream](https://github.com/vgmstream/vgmstream/releases) |
| **flac.exe** | Lossless audio encoding | ⬇ Manual | [xiph/flac](https://github.com/xiph/flac/releases) |
| **crid / crid_mod** | USM video decryption | ⬇ Manual | [kokarare1212/CRID-usm-Decrypter](https://github.com/kokarare1212/CRID-usm-Decrypter) |
| **AssetStudio.CLI** | Unity `.ab` asset extraction | ⬇ Manual | [Perfare/AssetStudio](https://github.com/Perfare/AssetStudio) |

---

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/LonerYlon/maiconverter.git
cd maiconverter

# 2. Run the first-time setup (checks tools, auto-downloads what it can)
python setup.py

# 3. For tools that require manual download, follow the printed instructions.

# 4. Launch
python maimai.py
```

`setup.py` flags:

| Flag | Description |
|---|---|
| *(no flags)* | Check tools, auto-install if missing, skip if already done |
| `--force` | Re-run even if setup was already completed |

After a successful run, a `.setup_done` marker is written so subsequent launches skip the check.

---

## Folder Structure

```
MAS/
├── maimai.py               ← Main script
├── setup.py                ← First-time tool setup
│
├── maiforge/               ← Bundled maiforge binary
│   └── maiforge.exe
│
├── ffmpeg/                 ← ffmpeg binaries (auto-downloaded or manual)
│   ├── ffmpeg.exe
│   └── ffprobe.exe
│
├── vgmstream-win64/        ← vgmstream binaries (auto-downloaded or manual)
│   └── vgmstream-cli.exe
│
├── flac/                   ← flac encoder (manual)
│   └── flac.exe
│
├── crid/                   ← USM decrypter (manual)
│   └── crid_mod.exe        (or crid.exe)
│
├── assetstudiocli/         ← AssetStudio CLI (manual)
│   └── AssetStudio.CLI.exe
│
├── converters/             ← Python converter helpers
├── tools/                  ← Shared Python utilities
└── _thirdparty/            ← Vendored source (MaiLib)
```

---

## Usage

### Interactive Mode

```bash
python maimai.py
```

The main menu is displayed with a live tool status row:

```
Maimai's AIO Conversion

[1] MP4 Conversion (.dat)
[2] MP3 Conversion (.awb)
[3] FLAC Conversion (.awb)
[4] Chart Conversion (.ma2)
[5] Database Conversion (AXXX Full Conversion)
[6] Image Conversion (.ab)
[0] Exit

Tools: ✓ vgmstream  ✓ ffmpeg  ✓ crid  ✓ flac  ✓ maiforge  ✓ AssetStudio
```

Navigation uses number keys. Interactive checklists (option 5, chart format, etc.) use:
- **↑ / ↓** — move cursor
- **Space** — toggle / select
- **Enter** — confirm
- **Esc** — cancel / go back

---

### CLI Mode

Append a command after `maimai.py` to skip the menu:

```bash
python maimai.py <command> [options]
```

Global flags available on all commands:

| Flag | Description |
|---|---|
| `--no-header` | Suppress the title banner |
| `--quiet` | Suppress non-essential output |
| `--json-summary` | Print a JSON result summary to stdout |
| `--tool-ffmpeg PATH` | Override path to `ffmpeg.exe` |
| `--tool-ffprobe PATH` | Override path to `ffprobe.exe` |
| `--tool-vgmstream PATH` | Override path to `vgmstream-cli.exe` |
| `--tool-flac PATH` | Override path to `flac.exe` |
| `--tool-crid PATH` | Override path to `crid_mod.exe` |
| `--tool-maichartconverter PATH` | Override path to `maiforge.exe` |
| `--tool-assetstudio PATH` | Override path to `AssetStudio.CLI.exe` |

---

## Conversion Modes

### 1 · MP4 Conversion (`.dat` → `.mp4`)

Decrypts maimai USM video files and encodes them to `.mp4`.

**Interactive:** Select single or batch, provide input path and output folder.

**CLI:**
```bash
# Single
python maimai.py mp4 single --input FILE.dat --output OUTDIR

# Batch
python maimai.py mp4 batch --input DIR --output OUTDIR [--policy overwrite|skip]
```

**Tools required:** `crid_mod.exe`, `ffmpeg.exe`, `ffprobe.exe`

---

### 2 · MP3 Conversion (`.awb` → `.mp3`)

Decodes ACB/AWB audio container streams to `.mp3`.

**CLI:**
```bash
python maimai.py mp3 single --input FILE.awb --output OUTDIR
python maimai.py mp3 batch  --input DIR       --output OUTDIR [--policy overwrite|skip]
```

**Tools required:** `vgmstream-cli.exe`, `ffmpeg.exe`

---

### 3 · FLAC Conversion (`.awb` → `.flac`)

Same pipeline as MP3 but outputs lossless `.flac` files.

**CLI:**
```bash
python maimai.py flac single --input FILE.awb --output OUTDIR
python maimai.py flac batch  --input DIR       --output OUTDIR [--policy overwrite|skip]
```

**Tools required:** `vgmstream-cli.exe`, `flac.exe`, `ffmpeg.exe`

---

### 4 · Chart Conversion (`.ma2` → Simai)

Compiles a single `.ma2` binary chart into Simai text format using `maiforge`.

**Interactive:** Asks for input `.ma2` path, output folder, then an arrow-key checklist:
- `[ ] Save as .zip`
- `[ ] Save as .adx (AstroDX)`

**CLI:**
```bash
python maimai.py chart --input CHART.ma2 --output OUTDIR [--policy overwrite|skip]
```

**Tools required:** `maiforge.exe`

---

### 5 · Database Conversion (AXXX Full Pipeline)

The main pipeline. Takes an AXXX game data folder (e.g. `A000`) and produces a fully compiled and categorised song library.

**Auto-detects two input modes:**

| Mode | Input | Detection |
|---|---|---|
| **Single** | An `AXXX` folder directly (e.g. `A000/`) | Folder name matches `[A-Z]\d{3}` |
| **Batch** | A folder *containing* AXXX folders (e.g. `KD/` with `A001/`, `M100/` inside) | Sub-folders match the pattern |

Non-AXXX files/folders inside a batch root are silently ignored.

**Asset auto-detection:** The script scans the AXXX folder for:
- `music*` / `musicMP3` → audio source
- `Jackets` / `jacket` → cover images
- `movie` / `video` → video files

Missing assets can be:
- Ignored (`--ignore-incomplete`)
- Auto-converted on the fly from raw game files (`--auto-build`)

**Interactive options checklist (↑↓ Space Enter):**

| Option | Flag | Description |
|---|---|---|
| Categorization | `--categorize N` | How songs are grouped into folders (see below) |
| Force decimal levels | `--decimal` | Use `13.5` style instead of `13+` |
| Use music ID as name | `--use-number` | Folder named by numeric ID rather than title |
| Create JSON log | `--json` | Emit a JSON log alongside output |
| Zip per-category | `--zip` | Zip each category folder, delete originals |
| ADX per-category | `--adx` | Package each category as `.adx` (AstroDX) |
| ADX per-track | `--adx-track` | Package each song individually as `.adx` |
| Collection manifest | `--collection` | Generate a collection index file |
| Ignore errors | `--ignore-incomplete` | Skip songs with missing assets instead of failing |

**CLI:**
```bash
# Single AXXX folder, auto-build missing assets
python maimai.py db \
  --root C:\KDX\A000 \
  --output C:\Output \
  --categorize 2 \
  --music C:\KDX\A000\musicMP3 \
  --cover C:\KDX\A000\Jackets \
  --auto-build

# Batch (folder containing multiple AXXX)
python maimai.py db \
  --root C:\KDX \
  --output C:\Output \
  --categorize 2 \
  --auto-build \
  --adx-after
```

**Tools required:** `maiforge.exe`, `vgmstream-cli.exe`, `ffmpeg.exe`, `crid_mod.exe`, `AssetStudio.CLI.exe`

---

### 6 · Image Conversion (`.ab` → `.png`)

Extracts Unity asset bundles containing jacket art or backgrounds.

**CLI:**
```bash
python maimai.py image single --input FILE.ab  --output OUTDIR
python maimai.py image batch  --input DIR       --output OUTDIR [--policy overwrite|skip]
```

**Tools required:** `AssetStudio.CLI.exe`

---

## Database Options Reference

### Categorization modes (`--categorize N`)

| N | Groups songs by |
|---|---|
| `0` | Genre |
| `1` | Level |
| `2` | Cabinet (default) |
| `3` | Composer |
| `4` | BPM |
| `5` | SD/DX Chart type |
| `6` | No subfolders (flat) |

### Output policy (`--policy`, `--output-policy`)

| Value | Behaviour |
|---|---|
| `overwrite` | Clear existing output folder and redo (default) |
| `skip` | Leave existing output folder untouched |

---

## Output Formats

| Extension | Description |
|---|---|
| `.mp4` | Standard video |
| `.mp3` | Compressed audio |
| `.flac` | Lossless audio |
| `.zip` | Zip archive of converted song folder |
| `.adx` | AstroDX song package (zip renamed to `.adx`) |

---

## Credits & Third-Party Tools

| Tool | Author | License / Link |
|---|---|---|
| [vgmstream](https://github.com/vgmstream/vgmstream) | vgmstream contributors | LGPL-2.1 |
| [FFmpeg](https://www.ffmpeg.org/) | FFmpeg contributors | LGPL / GPL |
| [CRID USM Decrypter](https://github.com/kokarare1212/CRID-usm-Decrypter) | kokarare1212 | MIT |
| [FLAC](https://github.com/xiph/flac) | Xiph.Org Foundation | BSD / GPL |
| [AssetStudio](https://github.com/Perfare/AssetStudio) | Perfare | MIT |
| [MaiLib](https://github.com/Neskol/MaichartConverter) | Neskol | — |
| [AstroDX](https://github.com/2394425147/astrodx) | 2394425147 | — |

> This tool is intended for personal use with game data you legally own. It is not affiliated with or endorsed by SEGA.

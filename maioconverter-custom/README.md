# Maimai Forge — Custom Converter

Custom chart/asset converter powered by MaiLib with a streamlined CLI.

## Quick start (Windows x64)

The packaged executable is:
```
.\maiforge.exe
```

Run help:
```
.\maiforge.exe --help
```

## Common commands

Compile a database:
```
.\maiforge.exe db-compile --input "C:\Path\To\A000" --output "C:\Path\To\Out" --category 0 --json --collection
```

Compile a single MA2:
```
.\maiforge.exe ma2-compile --input "C:\Path\To\chart.ma2" --output "C:\Path\To\Out" --format Simai
```

Compile Simai to MA2:
```
.\maiforge.exe simai-compile --input "C:\Path\To\maidata.txt" --output "C:\Path\To\Out" --format Ma2_104 --difficulty 4
```

## Parameters

| Flag | Applies to | Description |
| --- | --- | --- |
| `--input` | all | Source path (file or folder). |
| `--output` | all | Output folder (subfolder is created using input name). |
| `--format` | ma2-compile, ma2-by-id, simai-compile | Target format (e.g., `Simai`, `SimaiFes`, `Ma2_103`, `Ma2_104`). |
| `--rotate` | ma2-compile, ma2-by-id, simai-compile | Rotate charts (Clockwise90/180, Counterclockwise90/180, UpsideDown, LeftToRight). |
| `--shift` | ma2-compile, ma2-by-id, simai-compile | Shift chart timing by ticks (384 ticks = 1 bar). |
| `--category` | db-compile | Categorization method (0–6 = Genre/Level/Cabinet/Composer/BPM/SD‑DX/None). |
| `--music` | db-compile | Override music folder (mp3). |
| `--cover` | db-compile | Override cover folder (jacket images). |
| `--video` | db-compile | Override video folder (mp4). |
| `--decimal` | db-compile | Force decimal level output. |
| `--ignore-incomplete` | db-compile | Skip missing assets without prompting. |
| `--use-number` | db-compile | Use music ID as folder name. |
| `--json` | db-compile | Write `tracks.json`. |
| `--zip` | db-compile | Zip per category and delete folders. |
| `--zip-track` | db-compile | Zip per track folder. |
| `--collection` | db-compile | Write `collections/*.json`. |
| `--id` | ma2-by-id | Music ID for MA2 lookup. |
| `--difficulty` | ma2-by-id, simai-compile | Difficulty index. |
| `--overwrite` | simai-reverse | Overwrite extracted assets. |

## Parameters notice

- Music files should be named `musicxxxxxx.mp3` where `xxxxxx` matches the music ID in `Music.xml` (6 digits).
- Video files should be named `xxxxxx.mp4` where `xxxxxx` matches the music ID in `Music.xml` (6 digits).
- Jacket images should be named `UI_Jacket_xxxxxx.png` where `xxxxxx` matches the music ID in `Music.xml` (6 digits).
- Difficulty indices are `0–4` (Basic → Re:Master) and `7` (Utage).
- Paths do not need trailing separators. Quoted paths are allowed.

## Output behavior

- `--output` always creates a subfolder named after the input (file or folder name).
- `forge.log` is always written in the output root.
- `tracks.json` is written when `--json` is used.
- `collections/*.json` are written when `--collection` is used.
- `--zip` creates one ZIP per category folder and deletes the folders afterward.
- Missing assets prompt per track unless `--ignore-incomplete` is set.

## Disclaimer

This tool is for personal use only. You are responsible for any content you process and for complying with applicable rights/licenses.


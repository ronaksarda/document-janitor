# 🧹 Downloads Janitor

> **"The animation IS the explanation."**  
> A local, non-destructive file sorter with a claymation-style robot rig that physically sorts your cluttered folders into organized bins right before your eyes.

---

## 📖 Overview

**Downloads Janitor** organizes messy directories (such as your OS `Downloads` folder) safely, deterministically, and transparently. Instead of silently moving files in the background or deleting anything, a stop-motion clay robot visibly:
1. **Picks files off the pile**
2. **Carries them across the floor**
3. **Puts them into dedicated destination bins**

Every move is logged in an append-only journal (`journal.json`) and is **100% reversible byte-for-byte**.

---

## 🤖 The Robot & Visual Vocabulary

The user interface uses a bespoke SVG character rig with a tactile clay aesthetic (terracotta body, teal patina wash, mismatched eyes, chest bolts, and a spring antenna):

* **Pick Up**: The robot bends down, reaches for a file chip from the pile, and holds it in hand.
* **Carry**: Bobbing walk cycle across the floor. If a duplicate is detected, the robot pauses with a curious antenna wiggle before parking it. In dry run mode, a dotted path marks the preview trajectory.
* **Put In**: The robot lifts the file chip, drops it behind the bin front, the bin shakes with clay wobble, and a `+1` counter floats upward.
* **Skip & Wait**: For active downloads or files saved within the last 10 minutes, the robot taps a wooden **WAIT** sign and passes by safely.
* **Needs Review**: For unrecognized file formats, a question-mark stack appears as the robot tilts its head in curiosity without moving the file.
* **Sprout Plant**: A clay potted plant on the far right blooms and grows proportionally as files are sorted.

---

## 🗂️ Sorting Rules & Categories

Downloads Janitor routes files into strictly allowed categories:

| Rule | Category | Destination | Matching Logic |
| :--- | :--- | :--- | :--- |
| **1. Screenshots** | `Screenshots` | `Screenshots/YYYY-MM/` | Names beginning with `Screenshot`, `Screen Shot`, etc. Date extracted from filename or mtime. |
| **2. WhatsApp** | `WhatsApp` | `WhatsApp/<Type>/YYYY-MM/` | Modern and legacy styles (`IMG-YYYYMMDD-WA*`, `WhatsApp Image*`, etc.) split by `Images`, `Videos`, `Audio`, and `Documents`. |
| **3. Installers** | `Installers` | `Installers/` | `.exe`, `.dmg`, `.msi`, `.apk` |
| **4. Documents** | `Documents` | `Documents/YYYY-MM/` | `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.txt`, `.csv`, `.doc`, `.xls`, `.ppt` |
| **5. Pictures** | `Pictures` | `Pictures/YYYY-MM/` | `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.svg`, `.bmp`, `.tiff` |
| **6. Videos** | `Videos` | `Videos/YYYY-MM/` | `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm` |
| **7. Audio** | `Audio` | `Audio/YYYY-MM/` | `.mp3`, `.wav`, `.flac`, `.m4a`, `.aac`, `.ogg`, `.opus` |
| **8. Archives** | `Archives` | `Archives/` | `.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.bz2` |
| **9. Duplicates** | `Duplicates` | `Duplicates/` | Identical content by SHA-256 (including `name (1).ext`). **Oldest copy is kept in place**; copies are parked, never deleted. |
| **10. Unknown** | *In Place* | *Unchanged* | Flagged as `Needs Review` and left untouched. |

---

## 🛡️ Safety & Non-Destructive Invariants

* **No Deletions**: Files are only moved, never deleted or overwritten.
* **Collision Protection**: If a destination file already exists, a numerical suffix is safely appended: `file (2).ext`, `file (3).ext`.
* **Download In-Progress Guard**: Partial downloads (`.crdownload`, `.part`, `.tmp`) are skipped automatically.
* **Fresh File Guard**: Files modified within the last 10 minutes are skipped to protect active downloads or unsaved editor buffers.
* **Protected Folders**: Any files inside folders named `keep/` or `ignore/` are strictly ignored.
* **Office Lock Guard**: Microsoft Office temporary lock files (`~$*`) are excluded to avoid Windows permission locks.
* **Byte-for-Byte Undo**: Every move records original path, destination path, and file hash in `journal.json`. An undo restores every file to its exact original directory.

---

## 🚀 Getting Started

### 1. Launching the Web UI

Run with the bundled Windows batch launcher:
```cmd
janitor.bat ui
```
Or directly using the embedded Python environment:
```cmd
.\py311\python.exe janitor_app.py 5000
```
Open **[http://localhost:5000](http://localhost:5000)** in your browser.

#### In the Web UI:
* **Active Folder Toolbar**: Switch instantly between `My Downloads` (`C:\Users\<User>\Downloads`), `Test Folder`, or enter any custom directory.
* **Dry Run**: Preview the complete sorting walkthrough. Counters visually increment and the floor remains untouched on disk.
* **Run Now**: Move files live with step-by-step robot animation.
* **Speed Controls**: Toggle between `1x`, `4x`, `10x`, and `Instant` execution.
* **Skip Button**: Instantly fast-forwards all remaining moves to completion without aborting.
* **Preview Tab**: Checkbox table showing all planned moves, actions, destinations, and matching reasons. Select/deselect individual files before applying.
* **History Tab**: Inspect previous runs and undo entire runs or specific files with a single click.

---

### 2. Command Line Interface (CLI)

The CLI provides direct terminal commands:

#### Preview Sorting (Dry-Run)
```cmd
janitor.bat dry-run --dir "C:\Users\ADMIN\Downloads"
```

#### Execute Sorting Live
```cmd
janitor.bat run --dir "C:\Users\ADMIN\Downloads"
```

#### Undo Last Run
```cmd
janitor.bat undo --dir "C:\Users\ADMIN\Downloads"
```

#### Undo a Specific File
```cmd
janitor.bat undo --dir "C:\Users\ADMIN\Downloads" --file "Quarterly_Report_2026-04.pdf"
```

#### Undo a Specific Run ID
```cmd
janitor.bat undo --dir "C:\Users\ADMIN\Downloads" --run-id "run_1728042000_1234"
```

---

## 🧪 Testing & Verification

The suite includes 9 comprehensive unit and integration tests verifying all engine invariants:

```cmd
.\py311\python.exe -m pytest tests/ -v
```

### Covered Test Cases:
1. `test_classification`: Verifies regex rules for screenshots, WhatsApp, installers, documents, and media.
2. `test_skip_recent`: Verifies files modified < 10 minutes are skipped.
3. `test_keep_and_ignore_folders`: Verifies `keep/` and `ignore/` trees remain untouched.
4. `test_skip_downloading_files`: Verifies `.crdownload`, `.part`, `.tmp` skips.
5. `test_duplicates`: Verifies duplicate SHA-256 parking into `Duplicates/` while preserving the oldest copy.
6. `test_collision_safety`: Verifies collision resolution with ` (2)`, ` (3)`.
7. `test_dry_run_leaves_folder_hash_identical`: Verifies folder contents and hashes are 100% unaltered after dry run.
8. `test_run_then_undo_restores_folder_byte_for_byte`: Verifies complete run reversal restores exact directory tree.
9. `test_undo_single_file`: Verifies atomic restoration of an individual moved file.

---

## 🛠️ Project Structure

```text
new-project-cleanup/
├── janitor_engine.py         # Core pure-Python sorting engine & journal manager
├── janitor_app.py            # Flask web server & REST API
├── janitor_cli.py            # CLI entry point (dry-run, run, undo, ui)
├── janitor.bat               # Windows batch launcher
├── make_test_folder.py       # Fixture generator (49 diverse test files)
├── templates/
│   └── index.html            # Single-page UI with clay robot SVG rig & screens
├── assets/
│   ├── janitor_bot.html      # Original SVG robot rig reference & tween loop
│   └── robot_reference.png   # Character design visual reference
├── tests/
│   └── test_janitor.py       # Full pytest test suite
└── py311/                    # Embedded Python 3.11 runtime
```

---

## 📡 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/plan` | Scans current target directory and returns planned items, bin counts, and config. |
| `POST` | `/api/set_dir` | Changes active target directory (`{ "dir": "path" }`). |
| `POST` | `/api/apply` | Executes full or selected batch move (`{ "selected": ["file1", ...] }`). |
| `POST` | `/api/apply_single` | Executes atomic live move for one item during animated walkthrough. |
| `POST` | `/api/finish_run` | Closes active animated run session in journal. |
| `POST` | `/api/undo` | Reverses last run, specific `run_id`, or specific `file`. |
| `GET` | `/api/bins` | Returns file counts for all 9 allowed destination bins. |
| `GET` | `/api/history` | Returns journal history runs and executed move records. |
| `GET` | `/api/stats` | Returns total files sorted count and timestamp of last run. |

---

## 🎨 Design Notes

* **Palette**: Clay light `#fff8eb`, Terracotta `#c9754a`, Teal `#6f9a8a`, Deep patina `#5b8073`, Warm dark brown `#4a2f20`.
* **Wobble Filter**: SVG `feTurbulence` + `feDisplacementMap` filter for organic handmade clay edges.
* **Tween System**: Cubic bezier easing function with tab-visibility awareness and timeout safety guards to prevent animation frame stalling.

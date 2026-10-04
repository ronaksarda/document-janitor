import os
import sys
import json
import time
import shutil
import hashlib
import re
from pathlib import Path
from datetime import datetime

ALLOWED_FOLDERS = [
    "Screenshots",
    "WhatsApp",
    "Installers",
    "Documents",
    "Pictures",
    "Videos",
    "Audio",
    "Archives",
    "Duplicates"
]

INSTALLER_EXTS = {".exe", ".dmg", ".msi", ".apk"}
DOCUMENT_EXTS = {".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt", ".txt", ".csv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"}
SKIP_EXTS = {".crdownload", ".part", ".tmp"}

JOURNAL_FILE = "journal.json"

def calculate_sha256(filepath):
    h = hashlib.sha256()
    try:
        size = os.path.getsize(filepath)
        with open(filepath, "rb") as f:
            if size <= 20971520:  # <= 20MB: read full file
                while chunk := f.read(262144):
                    h.update(chunk)
            else:
                # Fast sample hash for files > 20MB
                h.update(f.read(2097152))
                f.seek(max(0, size - 2097152))
                h.update(f.read(2097152))
                h.update(str(size).encode())
        return h.hexdigest()
    except Exception:
        return ""

def extract_date_yyyy_mm(filename, mtime):
    # Try WhatsApp IMG-YYYYMMDD-WA... or VID-YYYYMMDD-WA...
    m = re.search(r'(?:IMG|VID|AUD|DOC)-(\d{4})(\d{2})\d{2}-WA', filename, re.IGNORECASE)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    
    # Try WhatsApp Image YYYY-MM-DD
    m = re.search(r'WhatsApp\s+(?:Image|Video|Audio|Doc)\s+(\d{4})-(\d{2})-\d{2}', filename, re.IGNORECASE)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # Try YYYY-MM or YYYY_MM (with optional day YYYY-MM-DD)
    m = re.search(r'(?:^|[\D])(20\d{2})[-_]([01]\d)(?:[-_][0-3]\d)?(?:[\D]|$)', filename)
    if m:
        year, month = m.group(1), m.group(2)
        if 1 <= int(month) <= 12:
            return f"{year}-{month}"

    # Try YYYYMMDD (8 digits)
    m = re.search(r'(?:^|[\D])(20\d{2})([01]\d)([0-3]\d)(?:[\D]|$)', filename)
    if m:
        year, month = m.group(1), m.group(2)
        if 1 <= int(month) <= 12:
            return f"{year}-{month}"

    # Fallback to mtime
    dt = datetime.fromtimestamp(mtime)
    return dt.strftime("%Y-%m")


def get_safe_destination(dest_path: Path) -> Path:
    if not dest_path.exists():
        return dest_path
    
    parent = dest_path.parent
    stem = dest_path.stem
    suffix = dest_path.suffix

    m = re.search(r'^(.*?)\s*\((\d+)\)$', stem)
    if m:
        base_name = m.group(1).strip()
        count = int(m.group(2)) + 1
    else:
        base_name = stem
        count = 2

    while True:
        candidate = parent / f"{base_name} ({count}){suffix}"
        if not candidate.exists():
            return candidate
        count += 1

def plan(target_dir: str | Path) -> list[dict]:
    target = Path(target_dir).resolve()
    if not target.exists():
        return []

    now = time.time()
    plan_items = []
    
    # Collect candidate files (top level files or files in subdirectories except allowed category folders)
    # Target directory scanning:
    # Look at files directly in target_dir, plus any files in 'keep' or 'ignore'
    entries = []
    for item in target.iterdir():
        if item.is_file():
            entries.append(item)
        elif item.is_dir() and item.name.lower() in {"keep", "ignore"}:
            for sub in item.rglob("*"):
                if sub.is_file():
                    entries.append(sub)

    # Sort entries by mtime ascending for deterministic duplicate handling (oldest stays/first)
    entries.sort(key=lambda p: (p.stat().st_mtime if p.exists() else 0, str(p)))

    # Track seen sha256 to identify duplicates
    # { sha256: Path }
    seen_hashes = {}
    
    # First pass: check for safety skips and compute hashes
    file_metadata = []
    for p in entries:
        try:
            st = p.stat()
            size = st.st_size
            mtime = st.st_mtime
        except Exception:
            continue

        rel_path = p.relative_to(target).as_posix()
        parts_lower = [part.lower() for part in p.relative_to(target).parts]

        # Ignore journal file completely
        if p.name == JOURNAL_FILE:
            continue

        # Safety Check: keep or ignore folder
        if any(part in {"keep", "ignore"} for part in parts_lower[:-1]):
            reason = f"inside a {parts_lower[0]} folder"
            file_metadata.append({
                "path": p,
                "rel_path": rel_path,
                "size": size,
                "mtime": mtime,
                "action": "skip",
                "dest": None,
                "rule": "safety_ignore_folder",
                "reason": reason,
                "sha256": ""
            })
            continue

        # Safety Check: temporary office lock files, hidden system files
        if p.name.startswith("~$") or p.name.startswith(".~") or p.name.lower() in {"thumbs.db", "desktop.ini"}:
            file_metadata.append({
                "path": p,
                "rel_path": rel_path,
                "size": size,
                "mtime": mtime,
                "action": "skip",
                "dest": None,
                "rule": "safety_temp_lock_file",
                "reason": "temporary or system lock file",
                "sha256": ""
            })
            continue

        # Safety Check: extension in .crdownload / .part / .tmp
        ext = p.suffix.lower()
        if ext in SKIP_EXTS:
            reason = "still downloading" if ext in {".crdownload", ".part"} else "temporary file"
            file_metadata.append({
                "path": p,
                "rel_path": rel_path,
                "size": size,
                "mtime": mtime,
                "action": "skip",
                "dest": None,
                "rule": "safety_downloading_extension",
                "reason": reason,
                "sha256": ""
            })
            continue

        # Safety Check: modified within last 10 minutes (600 seconds)
        if (now - mtime) < 600:
            file_metadata.append({
                "path": p,
                "rel_path": rel_path,
                "size": size,
                "mtime": mtime,
                "action": "skip",
                "dest": None,
                "rule": "safety_recent_file",
                "reason": "modified in the last 10 minutes",
                "sha256": ""
            })
            continue

        # Calculate hash for sorting/duplicate detection
        file_hash = calculate_sha256(p)
        file_metadata.append({
            "path": p,
            "rel_path": rel_path,
            "size": size,
            "mtime": mtime,
            "action": None, # to be determined
            "dest": None,
            "rule": None,
            "reason": None,
            "sha256": file_hash
        })

    # Now assign sorting rules
    # Sorting rules:
    # 1. Screenshots ("Screenshot*", "Screen Shot*") -> Screenshots/YYYY-MM
    # 2. WhatsApp (Image/Video/Audio/Document, IMG-YYYYMMDD-WA####, VID-YYYYMMDD-WA####) -> WhatsApp/<Type>/YYYY-MM
    # 8. Duplicates (same sha256, including "name (1).ext") -> Duplicates/. Check this before rules 3-6 and keep oldest in place.
    # 3. Installers (.exe .dmg .msi .apk) -> Installers/
    # 4. Documents (.pdf .docx .xlsx .pptx) -> Documents/YYYY-MM
    # 5. Other images -> Pictures/YYYY-MM; videos -> Videos/YYYY-MM; audio -> Audio/YYYY-MM
    # 6. Archives (.zip .rar .7z) -> Archives/
    # 7. Unknown types -> stay in place, flagged "needs review"

    for meta in file_metadata:
        if meta["action"] == "skip":
            plan_items.append({
                "file": meta["rel_path"],
                "size": meta["size"],
                "action": "skip",
                "dest": None,
                "rule": meta["rule"],
                "reason": meta["reason"],
                "sha256": meta["sha256"]
            })
            continue

        p = meta["path"]
        fname = p.name
        ext = p.suffix.lower()
        sha = meta["sha256"]
        date_folder = extract_date_yyyy_mm(fname, meta["mtime"])

        # Rule 1: Screenshots
        if re.match(r'^(?:Screenshot|Screen\s*Shot)', fname, re.IGNORECASE):
            dest = f"Screenshots/{date_folder}/{fname}"
            plan_items.append({
                "file": meta["rel_path"],
                "size": meta["size"],
                "action": "move",
                "dest": dest,
                "rule": "1. Screenshots",
                "reason": f"filename starts with Screenshot ({date_folder})",
                "sha256": sha
            })
            if sha:
                seen_hashes.setdefault(sha, meta["rel_path"])
            continue

        # Rule 2: WhatsApp
        # Types: IMG-*-WA*, VID-*-WA*, "WhatsApp Image*", "WhatsApp Video*", etc.
        stem_lower = p.stem.lower()
        wa_type = None
        if re.search(r'^(?:IMG|WhatsApp\s*Image)', fname, re.IGNORECASE) or (ext in IMAGE_EXTS and ('-wa' in stem_lower or 'whatsapp' in stem_lower)):
            wa_type = "Images"
        elif re.search(r'^(?:VID|WhatsApp\s*Video)', fname, re.IGNORECASE) or (ext in VIDEO_EXTS and ('-wa' in stem_lower or 'whatsapp' in stem_lower)):
            wa_type = "Videos"
        elif re.search(r'^(?:AUD|WhatsApp\s*Audio|PTT-)', fname, re.IGNORECASE) or (ext in AUDIO_EXTS and ('-wa' in stem_lower or 'whatsapp' in stem_lower)):
            wa_type = "Audio"
        elif re.search(r'^(?:DOC|WhatsApp\s*Doc)', fname, re.IGNORECASE) or (ext in DOCUMENT_EXTS and ('-wa' in stem_lower or 'whatsapp' in stem_lower)):
            wa_type = "Documents"


        if wa_type:
            dest = f"WhatsApp/{wa_type}/{date_folder}/{fname}"
            plan_items.append({
                "file": meta["rel_path"],
                "size": meta["size"],
                "action": "move",
                "dest": dest,
                "rule": "2. WhatsApp",
                "reason": f"matched WhatsApp {wa_type} rule ({date_folder})",
                "sha256": sha
            })
            if sha:
                seen_hashes.setdefault(sha, meta["rel_path"])
            continue

        # Rule 8: Duplicates check (before rules 3-6)
        if sha and sha in seen_hashes:
            orig = seen_hashes[sha]
            dest = f"Duplicates/{fname}"
            plan_items.append({
                "file": meta["rel_path"],
                "size": meta["size"],
                "action": "move",
                "dest": dest,
                "rule": "8. Duplicates",
                "reason": f"same content as {orig}, parking it, not deleting",
                "sha256": sha
            })
            continue

        # Record this hash as seen since it's the oldest copy for this content
        if sha:
            seen_hashes[sha] = meta["rel_path"]

        # Rule 3: Installers
        if ext in INSTALLER_EXTS:
            dest = f"Installers/{fname}"
            plan_items.append({
                "file": meta["rel_path"],
                "size": meta["size"],
                "action": "move",
                "dest": dest,
                "rule": "3. Installers",
                "reason": f"installer package ({ext})",
                "sha256": sha
            })
            continue

        # Rule 4: Documents
        if ext in DOCUMENT_EXTS:
            dest = f"Documents/{date_folder}/{fname}"
            plan_items.append({
                "file": meta["rel_path"],
                "size": meta["size"],
                "action": "move",
                "dest": dest,
                "rule": "4. Documents",
                "reason": f"document file ({ext}) -> Documents/{date_folder}",
                "sha256": sha
            })
            continue

        # Rule 5: Images, Videos, Audio
        if ext in IMAGE_EXTS:
            dest = f"Pictures/{date_folder}/{fname}"
            plan_items.append({
                "file": meta["rel_path"],
                "size": meta["size"],
                "action": "move",
                "dest": dest,
                "rule": "5. Pictures",
                "reason": f"image file ({ext}) -> Pictures/{date_folder}",
                "sha256": sha
            })
            continue
        elif ext in VIDEO_EXTS:
            dest = f"Videos/{date_folder}/{fname}"
            plan_items.append({
                "file": meta["rel_path"],
                "size": meta["size"],
                "action": "move",
                "dest": dest,
                "rule": "5. Videos",
                "reason": f"video file ({ext}) -> Videos/{date_folder}",
                "sha256": sha
            })
            continue
        elif ext in AUDIO_EXTS:
            dest = f"Audio/{date_folder}/{fname}"
            plan_items.append({
                "file": meta["rel_path"],
                "size": meta["size"],
                "action": "move",
                "dest": dest,
                "rule": "5. Audio",
                "reason": f"audio file ({ext}) -> Audio/{date_folder}",
                "sha256": sha
            })
            continue

        # Rule 6: Archives
        if ext in ARCHIVE_EXTS:
            dest = f"Archives/{fname}"
            plan_items.append({
                "file": meta["rel_path"],
                "size": meta["size"],
                "action": "move",
                "dest": dest,
                "rule": "6. Archives",
                "reason": f"archive container ({ext})",
                "sha256": sha
            })
            continue

        # Rule 7: Unknown types
        plan_items.append({
            "file": meta["rel_path"],
            "size": meta["size"],
            "action": "review",
            "dest": None,
            "rule": "7. Unknown",
            "reason": f"unknown file type ({ext or 'no extension'}), staying in place",
            "sha256": sha
        })

    return plan_items

def load_journal(target_dir: str | Path) -> list[dict]:
    jpath = Path(target_dir) / JOURNAL_FILE
    if jpath.exists():
        try:
            with open(jpath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_journal(target_dir: str | Path, runs: list[dict]):
    jpath = Path(target_dir) / JOURNAL_FILE
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=2)

def apply_plan(target_dir: str | Path, plan_items: list[dict], selected_files: list[str] | None = None) -> dict:
    target = Path(target_dir).resolve()
    selected_set = set(selected_files) if selected_files is not None else None
    
    run_id = f"run_{int(time.time())}_{os.getpid()}"
    timestamp = datetime.now().isoformat()
    executed_moves = []
    errors = []

    for item in plan_items:
        if item.get("action") != "move":
            continue
        rel_file = item["file"]
        if selected_set is not None and rel_file not in selected_set:
            continue

        src_path = target / rel_file
        if not src_path.exists():
            errors.append(f"Source file not found: {rel_file}")
            continue

        dest_rel = item["dest"]
        dest_path = target / dest_rel

        # Verify allowed folder rule
        top_folder = Path(dest_rel).parts[0]
        if top_folder not in ALLOWED_FOLDERS:
            errors.append(f"Destination folder {top_folder} not in allowed config")
            continue

        # Safe collision handling: append " (2)", " (3)", etc.
        safe_dest = get_safe_destination(dest_path)
        safe_dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.move(str(src_path), str(safe_dest))
            actual_dest_rel = safe_dest.relative_to(target).as_posix()
            executed_moves.append({
                "source": rel_file,
                "destination": actual_dest_rel,
                "sha256": item.get("sha256") or calculate_sha256(safe_dest),
                "rule": item.get("rule", "unknown"),
                "reason": item.get("reason", "")
            })
        except Exception as e:
            errors.append(f"Failed to move {rel_file}: {str(e)}")

    if executed_moves:
        runs = load_journal(target)
        runs.append({
            "run_id": run_id,
            "timestamp": timestamp,
            "moves": executed_moves
        })
        save_journal(target, runs)

    # Clean up empty parent directories of moved items if empty (excluding allowed folders)
    return {
        "run_id": run_id,
        "count": len(executed_moves),
        "moves": executed_moves,
        "errors": errors
    }

# Active run tracking for per-file animation mode
_active_run_id = None
_active_run_timestamp = None

def apply_single_item(target_dir: str | Path, item: dict) -> dict:
    """Move a single file using the plan item from the frontend.
    Groups consecutive single-item moves into the same journal run."""
    global _active_run_id, _active_run_timestamp
    
    target = Path(target_dir).resolve()
    errors = []
    
    rel_file = item["file"]
    dest_rel = item["dest"]
    
    src_path = target / rel_file
    if not src_path.exists():
        return {"success": False, "errors": [f"Source file not found: {rel_file}"], "moves": []}
    
    top_folder = Path(dest_rel).parts[0]
    if top_folder not in ALLOWED_FOLDERS:
        return {"success": False, "errors": [f"Folder {top_folder} not allowed"], "moves": []}
    
    dest_path = target / dest_rel
    safe_dest = get_safe_destination(dest_path)
    safe_dest.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        shutil.move(str(src_path), str(safe_dest))
    except Exception as e:
        return {"success": False, "errors": [str(e)], "moves": []}
    
    actual_dest_rel = safe_dest.relative_to(target).as_posix()
    move_record = {
        "source": rel_file,
        "destination": actual_dest_rel,
        "sha256": item.get("sha256") or calculate_sha256(safe_dest),
        "rule": item.get("rule", ""),
        "reason": item.get("reason", "")
    }
    
    # Append to active run or create new one
    runs = load_journal(target)
    if _active_run_id is None:
        _active_run_id = f"run_{int(time.time())}_{os.getpid()}"
        _active_run_timestamp = datetime.now().isoformat()
    
    # Find existing active run or create new entry
    found = False
    for r in runs:
        if r["run_id"] == _active_run_id:
            r["moves"].append(move_record)
            found = True
            break
    if not found:
        runs.append({
            "run_id": _active_run_id,
            "timestamp": _active_run_timestamp,
            "moves": [move_record]
        })
    save_journal(target, runs)
    
    return {
        "success": True,
        "run_id": _active_run_id,
        "errors": [],
        "moves": [move_record]
    }

def finish_active_run():
    """Call after a batch of single-item applies to reset the active run tracker."""
    global _active_run_id, _active_run_timestamp
    _active_run_id = None
    _active_run_timestamp = None


def undo(target_dir: str | Path, run_id: str | None = None, file_name: str | None = None) -> dict:
    target = Path(target_dir).resolve()
    runs = load_journal(target)
    if not runs:
        return {"success": False, "message": "No runs recorded in journal"}

    undone_moves = []
    errors = []

    # If file_name is specified, search backwards across runs for that file
    if file_name:
        target_name = Path(file_name).name
        found = False
        for run in reversed(runs):
            for move in list(reversed(run["moves"])):
                if Path(move["destination"]).name == target_name or Path(move["source"]).name == target_name or move["destination"] == file_name or move["source"] == file_name:
                    found = True
                    cur_path = target / move["destination"]
                    orig_path = target / move["source"]
                    if not cur_path.exists():
                        errors.append(f"File {move['destination']} missing, cannot undo")
                        continue
                    safe_orig = get_safe_destination(orig_path)
                    safe_orig.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.move(str(cur_path), str(safe_orig))
                        undone_moves.append({
                            "source": move["destination"],
                            "destination": safe_orig.relative_to(target).as_posix(),
                            "original_source": move["source"]
                        })
                        run["moves"].remove(move)
                        # Clean up empty source directory if empty
                        try:
                            if cur_path.parent != target and not any(cur_path.parent.iterdir()):
                                cur_path.parent.rmdir()
                        except Exception:
                            pass
                    except Exception as e:
                        errors.append(f"Error undoing {move['destination']}: {e}")
                    break
            if found:
                break
        # Remove empty runs
        runs = [r for r in runs if r["moves"]]
        save_journal(target, runs)
        return {
            "success": len(undone_moves) > 0,
            "undone": undone_moves,
            "errors": errors
        }

    # Undo entire run (specific run_id or most recent)
    target_run = None
    if run_id:
        for r in runs:
            if r["run_id"] == run_id:
                target_run = r
                break
        if not target_run:
            return {"success": False, "message": f"Run {run_id} not found"}
    else:
        target_run = runs[-1]

    for move in reversed(target_run["moves"]):
        cur_path = target / move["destination"]
        orig_path = target / move["source"]
        if not cur_path.exists():
            errors.append(f"File {move['destination']} missing, cannot undo")
            continue
        safe_orig = get_safe_destination(orig_path)
        safe_orig.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(cur_path), str(safe_orig))
            undone_moves.append({
                "source": move["destination"],
                "destination": safe_orig.relative_to(target).as_posix(),
                "original_source": move["source"]
            })
            # Clean up empty parent directory
            try:
                p = cur_path.parent
                while p != target and p.exists() and not any(p.iterdir()):
                    p.rmdir()
                    p = p.parent
            except Exception:
                pass
        except Exception as e:
            errors.append(f"Error moving back {move['destination']}: {e}")

    runs.remove(target_run)
    save_journal(target, runs)

    return {
        "success": True,
        "run_id": target_run["run_id"],
        "count": len(undone_moves),
        "undone": undone_moves,
        "errors": errors
    }

def get_bin_counts(target_dir: str | Path) -> dict:
    target = Path(target_dir).resolve()
    counts = {folder: 0 for folder in ALLOWED_FOLDERS}
    for folder in ALLOWED_FOLDERS:
        fpath = target / folder
        if fpath.exists() and fpath.is_dir():
            cnt = sum(1 for p in fpath.rglob("*") if p.is_file())
            counts[folder] = cnt
    return counts

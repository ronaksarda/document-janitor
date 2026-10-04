import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shutil
import hashlib
import time
import pytest

from janitor_engine import plan, apply_plan, undo, calculate_sha256, get_safe_destination
from make_test_folder import create_test_files


def get_folder_manifest(folder: Path) -> dict:
    manifest = {}
    for p in folder.rglob("*"):
        if p.is_file():
            rel = p.relative_to(folder).as_posix()
            manifest[rel] = calculate_sha256(p)
    return manifest

def get_folder_tree_hash(folder: Path) -> str:
    manifest = get_folder_manifest(folder)
    # Sort keys for deterministic hash
    combined = "\n".join(f"{k}:{manifest[k]}" for k in sorted(manifest.keys()))
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()

@pytest.fixture
def test_folder(tmp_path):
    folder = tmp_path / "downloads"
    create_test_files(folder)
    return folder

def test_classification(test_folder):
    p = plan(test_folder)
    by_file = {item["file"]: item for item in p}

    # Screenshots
    assert by_file["Screenshot_20260401-120000.png"]["dest"].startswith("Screenshots/2026-04/")
    assert by_file["Screenshot_20260401-120000.png"]["action"] == "move"
    assert by_file["Screen Shot 2026-03-15 at 4.12.33 PM.png"]["dest"].startswith("Screenshots/2026-03/")

    # WhatsApp
    assert by_file["IMG-20260810-WA0001.jpg"]["dest"].startswith("WhatsApp/Images/2026-08/")
    assert by_file["VID-20260620-WA0003.mp4"]["dest"].startswith("WhatsApp/Videos/2026-06/")
    assert by_file["AUD-20260515-WA0004.opus"]["dest"].startswith("WhatsApp/Audio/2026-05/")
    assert by_file["DOC-20260418-WA0005.pdf"]["dest"].startswith("WhatsApp/Documents/2026-04/")
    assert by_file["WhatsApp Image 2026-08-21 at 12.31.59.jpeg"]["dest"].startswith("WhatsApp/Images/2026-08/")

    # Installers
    assert by_file["NodeJS_Setup_v20.exe"]["dest"] == "Installers/NodeJS_Setup_v20.exe"
    assert by_file["ChromeInstaller.dmg"]["dest"] == "Installers/ChromeInstaller.dmg"

    # Documents
    assert by_file["Quarterly_Report_2026-04.pdf"]["dest"].startswith("Documents/2026-04/")
    assert by_file["Meeting_Notes.docx"]["dest"].startswith("Documents/")

    # Pictures / Videos / Audio
    assert by_file["family_vacation_2026-05.jpg"]["dest"].startswith("Pictures/2026-05/")
    assert by_file["birthday_clip.mov"]["dest"].startswith("Videos/")
    assert by_file["podcast_episode_12.mp3"]["dest"].startswith("Audio/")

    # Archives
    assert by_file["source_code_backup.zip"]["dest"] == "Archives/source_code_backup.zip"

    # Unknown
    assert by_file["unknown_binary.xyz"]["action"] == "review"
    assert by_file["unknown_binary.xyz"]["dest"] is None
    assert by_file["mystery_data"]["action"] == "review"

def test_skip_recent(test_folder):
    p = plan(test_folder)
    by_file = {item["file"]: item for item in p}
    
    # Fresh screenshot modified 1m ago
    assert by_file["Screenshot fresh.png"]["action"] == "skip"
    assert "modified in the last 10 minutes" in by_file["Screenshot fresh.png"]["reason"]
    
    assert by_file["just_saved_file.pdf"]["action"] == "skip"

def test_keep_and_ignore_folders(test_folder):
    p = plan(test_folder)
    by_file = {item["file"]: item for item in p}

    assert by_file["keep/precious_file.docx"]["action"] == "skip"
    assert "inside a keep folder" in by_file["keep/precious_file.docx"]["reason"]

    assert by_file["ignore/ignored_data.txt"]["action"] == "skip"
    assert "inside a ignore folder" in by_file["ignore/ignored_data.txt"]["reason"]

def test_skip_downloading_files(test_folder):
    p = plan(test_folder)
    by_file = {item["file"]: item for item in p}

    assert by_file["uncompleted_download.crdownload"]["action"] == "skip"
    assert by_file["firefox_stream.part"]["action"] == "skip"
    assert by_file["scratch_cache.tmp"]["action"] == "skip"

def test_duplicates(test_folder):
    p = plan(test_folder)
    by_file = {item["file"]: item for item in p}

    # shared_report.pdf is older than shared_report (1).pdf
    assert by_file["shared_report (1).pdf"]["action"] == "move"
    assert by_file["shared_report (1).pdf"]["dest"].startswith("Duplicates/")
    assert "parking it, not deleting" in by_file["shared_report (1).pdf"]["reason"]

    # dataset_copy2.csv is duplicate of dataset_copy1.csv
    assert by_file["dataset_copy2.csv"]["action"] == "move"
    assert by_file["dataset_copy2.csv"]["dest"].startswith("Duplicates/")

def test_collision_safety(tmp_path):
    dest_dir = tmp_path / "Documents" / "2026-01"
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_file = dest_dir / "invoice.pdf"
    target_file.write_bytes(b"existing invoice")

    safe1 = get_safe_destination(target_file)
    assert safe1.name == "invoice (2).pdf"

    safe1.write_bytes(b"invoice 2")
    safe2 = get_safe_destination(target_file)
    assert safe2.name == "invoice (3).pdf"

def test_dry_run_leaves_folder_hash_identical(test_folder):
    hash_before = get_folder_tree_hash(test_folder)
    
    # Simulate dry run: plan is computed, no files are modified
    p = plan(test_folder)
    assert len(p) > 0

    hash_after = get_folder_tree_hash(test_folder)
    assert hash_before == hash_after, "Dry run must leave folder hash identical!"

def test_run_then_undo_restores_folder_byte_for_byte(test_folder):
    # Ignore journal file when computing pre-run vs post-undo manifest
    manifest_before = get_folder_manifest(test_folder)
    
    p = plan(test_folder)
    result = apply_plan(test_folder, p)
    assert result["count"] > 0
    assert len(result["errors"]) == 0

    # Undo
    undo_res = undo(test_folder, run_id=result["run_id"])
    assert undo_res["success"] is True

    manifest_after = get_folder_manifest(test_folder)
    # Exclude journal.json
    manifest_after.pop("journal.json", None)
    
    assert manifest_before == manifest_after, "Run then undo must restore folder byte-for-byte!"

def test_undo_single_file(test_folder):
    p = plan(test_folder)
    result = apply_plan(test_folder, p)
    
    # Pick one moved file
    moved_item = result["moves"][0]
    dest_file = moved_item["destination"]
    orig_src = moved_item["source"]

    undo_res = undo(test_folder, file_name=dest_file)
    assert undo_res["success"] is True
    assert (test_folder / orig_src).exists()

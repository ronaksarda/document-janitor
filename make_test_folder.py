import os
import sys
import time
from pathlib import Path

def create_test_files(target_dir: str | Path):
    target = Path(target_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)

    now = time.time()
    old_time = now - (3600 * 24 * 30)  # 30 days ago
    fresh_time = now - 60               # 1 minute ago (within 10-minute skip window)

    # 1. Screenshots (Screenshot* and Screen Shot*)
    files_to_create = [
        ("Screenshot 2026-05-12 at 10.30.00.png", b"screenshot 1", old_time),
        ("Screenshot_20260401-120000.png", b"screenshot 2", old_time),
        ("Screen Shot 2026-03-15 at 4.12.33 PM.png", b"screenshot 3", old_time),
        ("Screenshot_2026-02-10_preview.jpg", b"screenshot 4", old_time),
        ("Screenshot fresh.png", b"fresh screenshot", fresh_time),

        # 2. WhatsApp in both naming styles (IMG-YYYYMMDD-WA0001, WhatsApp Image YYYY-MM-DD...)
        ("IMG-20260810-WA0001.jpg", b"wa image 1", old_time),
        ("IMG-20260714-WA0002.jpeg", b"wa image 2", old_time),
        ("VID-20260620-WA0003.mp4", b"wa video 1", old_time),
        ("AUD-20260515-WA0004.opus", b"wa audio 1", old_time),
        ("DOC-20260418-WA0005.pdf", b"wa doc 1", old_time),
        ("WhatsApp Image 2026-08-21 at 12.31.59.jpeg", b"wa modern img", old_time),
        ("WhatsApp Video 2026-09-02 at 18.00.12.mp4", b"wa modern vid", old_time),
        ("WhatsApp Audio 2026-03-10 at 09.15.00.mp3", b"wa modern aud", old_time),
        ("WhatsApp Doc 2026-01-20 at 14.22.33.docx", b"wa modern doc", old_time),

        # 3. Installers (.exe, .dmg, .msi, .apk)
        ("NodeJS_Setup_v20.exe", b"installer exe", old_time),
        ("ChromeInstaller.dmg", b"installer dmg", old_time),
        ("DatabaseTools.msi", b"installer msi", old_time),
        ("TestApp_v1.0.apk", b"installer apk", old_time),

        # 4. Documents (.pdf, .docx, .xlsx, .pptx)
        ("Quarterly_Report_2026-04.pdf", b"pdf report content", old_time),
        ("Meeting_Notes.docx", b"docx notes content", old_time),
        ("Financial_Model_2026-03.xlsx", b"xlsx spreadsheet content", old_time),
        ("Project_Pitch_Final.pptx", b"pptx presentation content", old_time),
        ("Notes_plain.txt", b"plain text notes", old_time),
        ("Expenses_2026-01.csv", b"csv data", old_time),

        # 5. Other images, videos, audio
        ("family_vacation_2026-05.jpg", b"vacation photo", old_time),
        ("avatar_clay.png", b"clay avatar image", old_time),
        ("podcast_episode_12.mp3", b"audio podcast mp3", old_time),
        ("guitar_sample.wav", b"guitar riff audio", old_time),
        ("birthday_clip.mov", b"mov video clip", old_time),
        ("tutorial_demo.mkv", b"mkv video demo", old_time),

        # 6. Archives (.zip, .rar, .7z)
        ("source_code_backup.zip", b"zip archive data", old_time),
        ("old_photos.rar", b"rar archive data", old_time),
        ("assets_bundle.7z", b"7z bundle data", old_time),

        # 7. Unknown types (stay in place, flagged "needs review")
        ("unknown_binary.xyz", b"mystery binary data", old_time),
        ("custom_model.weights", b"weights data", old_time),
        ("mystery_data", b"no extension data", old_time),

        # 8. Duplicates (same sha256, including "name (1).ext")
        ("shared_report.pdf", b"identical content for duplicate check 123", old_time - 500),
        ("shared_report (1).pdf", b"identical content for duplicate check 123", old_time),
        ("dataset_copy1.csv", b"identical csv content xyz 789", old_time - 300),
        ("dataset_copy2.csv", b"identical csv content xyz 789", old_time),

        # 9. Safety skips: .crdownload, .part, .tmp, fresh files (<10m)
        ("uncompleted_download.crdownload", b"half downloaded bytes", old_time),
        ("firefox_stream.part", b"firefox partial download", old_time),
        ("scratch_cache.tmp", b"temp cache", old_time),
        ("just_saved_file.pdf", b"just modified pdf", fresh_time),

        # 10. Unicode and spaced filenames
        ("Tetsuya 写真 2026.png", b"unicode japanese name", old_time),
        ("Résumé & Portfolio — Jane Doe (2026-02).pdf", b"unicode accents and symbols", old_time),
        ("File with   many    spaces.zip", b"spaced file name", old_time),
    ]

    # Create files
    for fname, content, mtime in files_to_create:
        fpath = target / fname
        fpath.write_bytes(content)
        os.utime(str(fpath), (mtime, mtime))

    # 11. File inside keep/ and ignore/ folders
    keep_dir = target / "keep"
    keep_dir.mkdir(exist_ok=True)
    keep_file = keep_dir / "precious_file.docx"
    keep_file.write_bytes(b"do not touch this keep file")
    os.utime(str(keep_file), (old_time, old_time))

    ignore_dir = target / "ignore"
    ignore_dir.mkdir(exist_ok=True)
    ignore_file = ignore_dir / "ignored_data.txt"
    ignore_file.write_bytes(b"do not touch this ignore file")
    os.utime(str(ignore_file), (old_time, old_time))

    total_files = len(list(target.rglob("*")))
    print(f"Created test folder at {target} with {len(files_to_create) + 2} test files.")
    return target

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "./test_downloads"
    create_test_files(out_dir)

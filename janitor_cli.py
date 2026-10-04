import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


import argparse
from janitor_engine import plan, apply_plan, undo, load_journal, get_bin_counts


def main():
    parser = argparse.ArgumentParser(prog="janitor", description="Downloads Janitor file sorter")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # dry-run
    p_dry = subparsers.add_parser("dry-run", help="Preview sorting without modifying files")
    p_dry.add_argument("--dir", default=".", help="Target directory (default: current directory)")

    # run
    p_run = subparsers.add_parser("run", help="Sort files in directory")
    p_run.add_argument("--dir", default=".", help="Target directory (default: current directory)")

    # undo
    p_undo = subparsers.add_parser("undo", help="Undo last run or specific file")
    p_undo.add_argument("--file", help="Specific file name to undo")
    p_undo.add_argument("--dir", default=".", help="Target directory (default: current directory)")
    p_undo.add_argument("--run-id", help="Specific run ID to undo")

    # ui
    p_ui = subparsers.add_parser("ui", help="Launch the clay robot UI")
    p_ui.add_argument("--dir", default=".", help="Target directory (default: current directory)")
    p_ui.add_argument("--port", type=int, default=5000, help="Port to listen on (default 5000)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    target_dir = Path(args.dir).resolve()

    if args.command == "dry-run":
        print(f"Janitor Dry-Run: Scanning {target_dir}...")
        items = plan(target_dir)
        moves = [i for i in items if i["action"] == "move"]
        skips = [i for i in items if i["action"] == "skip"]
        reviews = [i for i in items if i["action"] == "review"]

        print("\n--- PLANNED MOVES (walkthrough, no files touched) ---")
        if not moves:
            print("Nothing to sweep. Suspicious.")
        else:
            for m in moves:
                print(f"[MOVE] {m['file']} -> {m['dest']} ({m['reason']})")

        if skips:
            print("\n--- SKIPPED FILES ---")
            for s in skips:
                print(f"[SKIP] {s['file']} ({s['reason']})")

        if reviews:
            print("\n--- NEEDS REVIEW ---")
            for r in reviews:
                print(f"[REVIEW] {r['file']} ({r['reason']})")

        print(f"\nSummary: {len(moves)} to move, {len(skips)} skipped, {len(reviews)} to review.")

    elif args.command == "run":
        print(f"Janitor Run: Sorting {target_dir}...")
        items = plan(target_dir)
        res = apply_plan(target_dir, items)
        print(f"Completed run {res['run_id']}. Moved {res['count']} files.")
        for m in res["moves"]:
            print(f"[OK] {m['source']} -> {m['destination']}")
        if res["errors"]:
            print(f"Errors encountered: {len(res['errors'])}")
            for e in res["errors"]:
                print(f"[ERROR] {e}")

    elif args.command == "undo":
        print(f"Janitor Undo: Reversing in {target_dir}...")
        res = undo(target_dir, run_id=args.run_id, file_name=args.file)
        if not res.get("success"):
            print(f"Undo failed: {res.get('message', 'Unknown error')}")
            sys.exit(1)
        else:
            undone = res.get("undone", [])
            print(f"Successfully reversed {len(undone)} moves:")
            for u in undone:
                print(f"[RESTORED] {u['source']} -> {u['destination']}")

    elif args.command == "ui":
        from janitor_app import start_server
        start_server(target_dir, port=args.port)

if __name__ == "__main__":
    main()

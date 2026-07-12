#!/usr/bin/env python3
"""University Backup — one program to save your Canvas and OneDrive before you graduate.

Just run:   python backup.py
and follow the menu. First run asks for your Canvas web address and access token.
"""
import sys

from canvasbackup import canvas, config, onedrive, organise


def menu():
    print("""
=====================================================
   University Backup  —  Canvas + OneDrive
=====================================================
  1. Back up Canvas  (all courses: slides, files,
     videos, pages, assignments, grades) + organise
  2. Back up OneDrive (choose which folders)
  3. Do both
  4. Re-organise already-downloaded Canvas files
  5. Change settings (Canvas address / token / folder)
  6. Quit
""")
    return input("Choose 1-6: ").strip()


def ensure_canvas_config(cfg):
    if not cfg.get("canvas_url") or not cfg.get("canvas_token"):
        cfg = config.interactive_setup(cfg)
    return cfg


def main():
    cfg = config.load()
    while True:
        choice = menu()
        if choice == "1":
            cfg = ensure_canvas_config(cfg)
            cfg = config.choose_output(cfg)
            out = canvas.run(cfg)
            organise.run(cfg["output_dir"])
            print(f"\nAll done. Your files are in: {out.parent}")
        elif choice == "2":
            if not cfg.get("output_dir"):
                cfg = config.interactive_setup(cfg)
            cfg = config.choose_output(cfg)
            onedrive.run(cfg)
        elif choice == "3":
            cfg = ensure_canvas_config(cfg)
            cfg = config.choose_output(cfg)
            canvas.run(cfg)
            organise.run(cfg["output_dir"])
            onedrive.run(cfg)
        elif choice == "4":
            if not cfg.get("output_dir"):
                cfg = config.interactive_setup(cfg)
            organise.run(cfg["output_dir"])
        elif choice == "5":
            cfg = config.interactive_setup(cfg)
        elif choice == "6" or choice.lower() in ("q", "quit", "exit"):
            print("Bye — good luck after graduation!")
            return
        else:
            print("Please choose a number from 1 to 6.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)

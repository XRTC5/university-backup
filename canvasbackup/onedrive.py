"""OneDrive backup via rclone — with a pick-and-choose folder menu.

rclone (https://rclone.org) is a free tool that talks to OneDrive. This module
just drives it: one-time login, then let the user choose which top-level folders
to copy. Works with personal and university/OneDrive-for-Business accounts.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

REMOTE = "onedrive"  # name of the rclone remote this tool creates/uses


def _rclone():
    exe = shutil.which("rclone")
    if not exe:
        print("\nrclone is not installed.")
        print("Install it from https://rclone.org/downloads/ then run this again.")
        print("  Windows: download the .exe and add it to your PATH, or `winget install Rclone.Rclone`")
        print("  macOS:   `brew install rclone`")
        print("  Linux:   `sudo -v ; curl https://rclone.org/install.sh | sudo bash`")
        return None
    return exe


def _remote_exists(exe):
    out = subprocess.run([exe, "listremotes"], capture_output=True, text=True)
    return f"{REMOTE}:" in out.stdout


def _ensure_remote(exe):
    if _remote_exists(exe):
        return True
    print("\nA browser window will open — sign in with your university/personal account.")
    print("Accept the default answers to any questions rclone asks in the terminal.\n")
    input("Press ENTER to start the OneDrive login...")
    # interactive: inherits this terminal so the user can answer prompts
    r = subprocess.run([exe, "config", "create", REMOTE, "onedrive"])
    return r.returncode == 0 and _remote_exists(exe)


def _top_folders(exe):
    out = subprocess.run([exe, "lsjson", f"{REMOTE}:", "--dirs-only"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return []
    try:
        return sorted(d["Path"] for d in json.loads(out.stdout))
    except json.JSONDecodeError:
        return []


def run(cfg):
    exe = _rclone()
    if not exe:
        return
    if not _ensure_remote(exe):
        print("OneDrive login did not complete. Try again later.")
        return

    folders = _top_folders(exe)
    dest_root = Path(cfg["output_dir"]) / "OneDrive"

    print("\n=== Your OneDrive top-level folders ===")
    print("  0. EVERYTHING (whole OneDrive)")
    for i, f in enumerate(folders, 1):
        print(f"  {i}. {f}")
    choice = input("\nWhich to back up? e.g. 0 for all, or 1,3,4 : ").strip()

    if choice == "0" or not choice:
        targets = [None]  # whole drive
    else:
        picks = {int(x) for x in choice.replace(" ", "").split(",") if x.isdigit()}
        targets = [folders[i - 1] for i in picks if 1 <= i <= len(folders)]
        if not targets:
            print("Nothing selected.")
            return

    for t in targets:
        src = f"{REMOTE}:" if t is None else f"{REMOTE}:{t}"
        dest = dest_root if t is None else dest_root / t
        label = "whole OneDrive" if t is None else t
        print(f"\nCopying {label} ...  (this can take a while; it is resumable)")
        subprocess.run([exe, "copy", src, str(dest), "--progress",
                        "--transfers", "8", "--checkers", "16"])
    print("\nOneDrive backup done.")

    # opt-in: also grab files/folders others shared with you
    from . import shared
    shared.run(cfg, exe)

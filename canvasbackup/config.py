"""Load / save config and interactive first-run setup.

Config lives in config.yaml next to the program (gitignored). It never contains
anything that isn't the user's own Canvas URL + token + chosen output folder.
"""
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def load() -> dict:
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return {}


def save(cfg: dict) -> None:
    CONFIG_PATH.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    print(f"Saved settings to {CONFIG_PATH}")


def interactive_setup(cfg: dict) -> dict:
    print("\n=== Canvas setup ===")
    print("1. Log into Canvas in your browser.")
    print("2. Go to  Account > Settings  and scroll to 'Approved Integrations'.")
    print("3. Click '+ New Access Token', give it any name, and copy the token.\n")

    default_url = cfg.get("canvas_url", "")
    url = input(f"Your Canvas web address (e.g. https://canvas.yourschool.edu)"
                f"{f' [{default_url}]' if default_url else ''}: ").strip()
    if not url and default_url:
        url = default_url
    if not url.startswith("http"):
        url = "https://" + url
    url = url.rstrip("/")

    token = input("Paste your Canvas access token: ").strip()

    default_out = cfg.get("output_dir") or str(Path.home() / "UniBackup")
    out = input(f"Where should backups be saved? [{default_out}]: ").strip() or default_out

    cfg.update({"canvas_url": url, "canvas_token": token, "output_dir": out})
    save(cfg)
    return cfg


def choose_output(cfg: dict) -> dict:
    """Ask where to save this run's backup, defaulting to the saved location."""
    default_out = cfg.get("output_dir") or str(Path.home() / "UniBackup")
    out = input(f"\nWhere should the files be saved? "
                f"[{default_out}]: ").strip() or default_out
    out = str(Path(out).expanduser())
    if out != cfg.get("output_dir"):
        cfg["output_dir"] = out
        save(cfg)
    print(f"Saving to: {out}")
    return cfg

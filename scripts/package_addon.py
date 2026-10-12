"""Baut dist/noah_token_bridge/: der fertige Add-on-Ordner zum Kopieren nach /addons/.

    python scripts/package_addon.py
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "noah_token_bridge"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "addon", OUT)
    shutil.copytree(
        ROOT / "noah_bridge", OUT / "noah_bridge",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy(ROOT / "requirements.txt", OUT / "requirements.txt")
    print(f"Add-on-Ordner: {OUT}")


if __name__ == "__main__":
    main()

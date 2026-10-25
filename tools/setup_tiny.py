"""Copy an existing TinyLanguage checkout into the local ignored runtime."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    if not (source / "src" / "tiny_language.py").is_file():
        parser.error("Im Quellordner fehlt src/tiny_language.py.")
    target = ROOT / ".runtime" / "tinylanguage"
    if source == target or target.is_relative_to(source):
        parser.error("Quell- und Zielordner müssen getrennt sein.")
    shutil.copytree(source / "src", target / "src", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.tmp", "tiny_language_stitched.py"))
    (target / "SOURCE.txt").write_text(str(source) + "\n", encoding="utf-8")
    print(f"TinyLanguage-Laufzeit kopiert: {target}")


if __name__ == "__main__":
    main()


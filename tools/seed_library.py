"""Install the archived, evolutionarily discovered examples without overwriting user files."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    count = 0
    for category in ("datasets", "programs"):
        destination = args.data_dir / category
        destination.mkdir(parents=True, exist_ok=True)
        for source in (ROOT / "examples" / "library" / category).glob("*.json"):
            target = destination / source.name
            if not target.exists():
                shutil.copy2(source, target)
                count += 1
    print(f"{count} neue Beispieldateien in {args.data_dir.resolve()} übernommen.")


if __name__ == "__main__":
    main()


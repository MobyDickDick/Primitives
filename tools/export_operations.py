"""Export small reference tables; these are tasks, not synthesized NAND circuits."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from primitives.operations import OPERATIONS, generate_operation


def export(destination):
    destination.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, definition in OPERATIONS.items():
        specs = [(name.lower(), {"signed": definition["default_signed"]})]
        if definition["shift"]:
            specs.append((name.lower() + "-n1", {"signed": definition["default_signed"], "shift": 1}))
        for filename, params in specs:
            ds = generate_operation({"definition": name, "parameters": params}, samples=65536)
            path = destination / (filename + ".json")
            path.write_text(json.dumps(ds.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "examples" / "operations")
    args = parser.parse_args()
    print(f"{len(export(args.out))} Referenz-Vektorsätze nach {args.out.resolve()} exportiert.")


if __name__ == "__main__":
    main()

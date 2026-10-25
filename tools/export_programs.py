"""Rebuild the small, exhaustive source-program examples."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from primitives.dataset import generate
from primitives.library import write_json


EXAMPLES = {
    "sum-for": ("Summe for", "s = 0\nfor i in range(n):\n    s += i\nreturn s\n"),
    "sum-while": ("Summe while", "s = 0\ni = 0\nwhile i < n:\n    s += i\n    i += 1\nreturn s\n"),
    "selection": ("Auswahl if/else", "if n < 8:\n    if n == 0:\n        c = 1\n    else:\n        c = n * 2\nelse:\n    c = n - 1\nreturn c\n"),
    "reverse-bits": ("Bitreihenfolge umkehren", "# Vier Eingangsbits in umgekehrter Reihenfolge ausgeben\na = bits(n, 4)  # Index 0 ist das niederwertigste Bit\nreturn pack(a[::-1])\n"),
    "sum-jumps": ("Summe mit Rücksprung", 's = 0\ni = 0\nlabel("loop")\njump_if(i >= n, "done")\ns += i\ni += 1\ngoto("loop")\nlabel("done")\nreturn s\n'),
    "selection-zero": ("Auswahl mit Zero-Sprung", 'jump_zero(n, "zero")\nreturn n\nlabel("zero")\nreturn 42\n'),
}
PORTS = {"inputs": [{"name": "n", "bits": 4}], "outputs": [{"name": "c", "bits": 8}]}


def main():
    directory = Path(__file__).resolve().parents[1] / "examples" / "programs"
    directory.mkdir(exist_ok=True)
    write_json(directory / "interface.json", PORTS)
    for key, (name, source) in EXAMPLES.items():
        ds = generate(name, 4, 8, ports=PORTS, program={"version": 1, "source": source})
        write_json(directory / f"{key}.json", ds.to_dict())
        (directory / f"{key}.prim").write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()

"""Independent code identities, prefix semantics, sorting and migration checks."""
import json
import random
import tempfile
import unittest
from pathlib import Path

from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import bits
from primitives.examples import install_examples, install_structured_examples
from primitives.library import Library
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_structured import KINDS, ROOT, bundle, definition


def expected(kind, width, value):
    mask = (1 << width) - 1
    a, b = value & mask, value >> width & mask
    if kind == "sort2":
        return [a, b] if a <= b else [b, a]
    digits = bits(a, width)
    if kind == "gray":
        result = [digits[i] ^ (digits[i + 1] if i + 1 < width else 0) for i in range(width)]
    elif kind == "ungray":
        result = [sum(digits[i:]) % 2 for i in range(width)]
    else:
        result = [int(any(digits[:i + 1])) for i in range(width)]
    return [sum(v << i for i, v in enumerate(result))]


class StructuredTests(unittest.TestCase):
    def test_exported_instances_and_larger_widths(self):
        rng = random.Random(28)
        for kind in KINDS:
            for width in (1, 2, 4, 8, 16):
                with self.subTest(kind=kind, width=width):
                    program = Template(definition(kind)).instantiate({"t": width})
                    hierarchy = bundle(kind, width)
                    expanded = hierarchy.expand()
                    implementations = [hierarchy, expanded.simplify(), synthesize(program)]
                    if width <= 4:
                        prefix = ROOT / f"examples/circuits/recursive-{kind}/{kind}-{width}"
                        read = lambda suffix: json.loads(prefix.with_suffix(f".{suffix}.json").read_text(encoding="utf-8"))
                        self.assertEqual(read("block"), hierarchy.to_dict())
                        self.assertEqual(read("template"), program.spec)
                        implementations.append(Circuit.from_dict(read("circuit")))
                    n = expanded.inputs
                    values = range(1 << n) if width <= 4 else [0, (1 << n) - 1] + [rng.getrandbits(n) for _ in range(12)]
                    for value in values:
                        result = expected(kind, width, value)
                        self.assertEqual(program.run(value), result)
                        encoded = [bit for v in result for bit in bits(v, width)]
                        for implementation in implementations:
                            self.assertEqual(implementation.evaluate(bits(value, n)), encoded)

    def test_constraints(self):
        for kind in KINDS:
            for width in (0, 3, 65, True):
                with self.subTest(kind=kind, width=width), self.assertRaises(ValueError):
                    Template(definition(kind)).instantiate({"t": width})

    def test_install_once_and_preserve_user_changes(self):
        with tempfile.TemporaryDirectory(dir=".jobs") as directory:
            library = Library(directory)
            install_examples(library)
            before = len(library.blocks())
            install_structured_examples(library)
            self.assertEqual(len(library.blocks()), before + 12)
            self.assertEqual(len(library.templates()), 26)
            folder = next(f for f in library.tree()["folders"] if f["id"] == "structured-logic")
            self.assertEqual(folder["parent"], "recursion")
            library.save_folder("Meine Bitcodes", "Meine Beschreibung", key=folder["id"], parent="recursion")
            next(p for p in (Path(directory) / "blocks").glob("*.json")).unlink()
            snapshot = library.tree()
            install_structured_examples(library)
            self.assertEqual(library.tree(), snapshot)
            self.assertEqual(len(library.blocks()), before + 11)


if __name__ == "__main__":
    unittest.main()

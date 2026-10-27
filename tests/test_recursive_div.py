"""Verify MSB-aligned division against independent integer arithmetic."""
import ast
import json
import random
import tempfile
import unittest

from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, integer
from primitives.examples import install_examples
from primitives.library import Library, fitness
from primitives.program import template_source
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_recursive_div import OUTPUT, SOURCE, definition, netlist


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class RecursiveDivTests(unittest.TestCase):
    def test_exports_source_and_nands_exhaustively(self):
        template = Template(definition())
        self.assertEqual(read(SOURCE.with_suffix(".abstract.json")), template.to_dict())
        reports = read(OUTPUT / "verification.json")
        for width in (1, 2, 3, 4):
            with self.subTest(width=width):
                program = template.instantiate({"w": width})
                compiled = synthesize(program)
                prefix = OUTPUT / f"div-{width}"
                circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                self.assertEqual(circuit, compiled)
                self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"), netlist(circuit, width))
                dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                checked = fitness(circuit, dataset)
                self.assertTrue(checked["verified_truth_table"])
                self.assertEqual(next(r for r in reports if r["parameters"]["w"] == width)["fitness"], checked)
                for a in range(1 << width):
                    for b in range(1 << width):
                        expected = [a // b, 0] if b else [0, 1]
                        x = a | b << width
                        self.assertEqual(program.run(x), expected, (width, a, b))
                        self.assertEqual(integer(circuit.evaluate(bits(x, 2 * width))),
                                         expected[0] | expected[1] << width, (width, a, b))

    def test_large_widths_msb_boundaries_and_recursion(self):
        rng = random.Random(27)
        for width in (5, 6, 7, 8):
            program = Template(definition()).instantiate({"w": width})
            maximum = (1 << width) - 1
            pairs = [(a, b) for a in (0, 1, maximum) for b in (0, 1, maximum)]
            divisors = {1, 3, 5, maximum, (1 << (width - 1)) + 3}
            divisors.update((1 << k) + delta for k in range(width) for delta in (-1, 0, 1)
                            if 1 <= (1 << k) + delta <= maximum)
            for b in sorted(divisors):
                # Exercise equality, a<b, exact scaled divisors and the
                # alignment candidate just too large (fallback to d-1).
                for shift in range(width):
                    boundary = b << shift
                    if boundary <= maximum:
                        pairs.extend((a, b) for a in (boundary - 1, boundary, boundary + 1)
                                     if 0 <= a <= maximum)
            pairs += [(rng.randrange(maximum + 1), rng.randrange(maximum + 1)) for _ in range(50)]
            for a, b in pairs:
                self.assertEqual(program.run(a | b << width), [a // b, 0] if b else [0, 1],
                                 (width, a, b))
            with self.assertRaisesRegex(ValueError, "512 Gattern"):
                synthesize(program)

    def test_no_source_loops_or_runtime_division_and_width_validation(self):
        tree = ast.parse(template_source(definition()["source"]))
        self.assertFalse(any(isinstance(n, (ast.For, ast.While, ast.FloorDiv, ast.Mod)) for n in ast.walk(tree)))
        template = Template(definition())
        for width in (0, 9, 16, True):
            with self.assertRaises(ValueError):
                template.instantiate({"w": width})

    def test_library_upgrade_preserves_edits_and_deletions(self):
        with tempfile.TemporaryDirectory(dir=".jobs") as folder:
            library = Library(folder)
            marker = library.root / "example-installations.json"
            marker.write_text(json.dumps({"arithmetic-v1": True, "recursive-gt-v1": True, "recursive-equ-v1": True, "recursive-checked-v1": True,
                                          "recursive-mul-v1": True, "number-of-ones-v1": True,
                                          "recursive-max-index-v1": True}), encoding="utf-8")
            organization = library._organization()
            organization["folders"].append({"id": "examples", "parent": None,
                                             "name": "Meine Beispiele", "description": "Erhalten"})
            library._write_organization(organization)
            install_examples(library)
            self.assertEqual(len(library.templates()), 1)
            self.assertEqual(len(library.programs()), 4)
            self.assertEqual(next(f for f in library.tree()["folders"] if f["id"] == "examples")["description"],
                             "Erhalten")
            self.assertTrue(all(p["fitness"]["verified_truth_table"] for p in library.programs()))
            library.move_entry("function", library.datasets()[0]["function_id"], "functions")
            library.delete_function(library.datasets()[1]["function_id"])
            next((library.root / "templates").glob("*.json")).unlink()
            before = library.tree()
            install_examples(Library(folder))
            self.assertEqual(library.tree(), before)
            self.assertEqual(len(library.programs()), 3)
            self.assertEqual(len(library.templates()), 0)


if __name__ == "__main__":
    unittest.main()

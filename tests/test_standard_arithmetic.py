"""Unequal operand widths, exported NANDs, independent oracles and migration."""
from itertools import product
import json
from pathlib import Path
import random
import tempfile
import unittest

from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, integer
from primitives.examples import install_standard_arithmetic_examples
from primitives.library import Library, fitness
from primitives.program import specialize_interface
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_standard_arithmetic import KINDS, ROOT, WIDTHS, definition


def expected(kind, a, b, p, q):
    if kind == "add":
        return [a + b]
    if kind == "sub":
        return [(a - b) & ((1 << max(p, q)) - 1), int(b > a)]
    if kind == "mul":
        return [a * b]
    if b == 0:
        return [0, 0, 0, 1]
    quotient, remainder = divmod(a, b)
    return [quotient, remainder, 1, 0]


class StandardArithmeticTests(unittest.TestCase):
    def test_all_36_exported_solutions_exhaustively(self):
        for kind, p, q in product(KINDS, WIDTHS, WIDTHS):
            with self.subTest(kind=kind, p=p, q=q):
                prefix = ROOT / f"examples/circuits/standard-{kind}/{kind}-{p}-{q}"
                read = lambda suffix: json.loads(prefix.with_suffix(f".{suffix}.json").read_text(encoding="utf-8"))
                template = Template(definition(kind))
                saved_template = Template(json.loads((ROOT / f"examples/templates/standard-{kind}.abstract.json").read_text(encoding="utf-8")))
                self.assertEqual(saved_template.to_dict(), template.to_dict())
                program = template.instantiate({"p": p, "q": q})
                self.assertEqual(read("template"), program.spec)
                circuit = Circuit.from_dict(read("circuit"))
                self.assertEqual(circuit.to_dict(), synthesize(program).to_dict())
                block = BlockBundle(read("block"))
                dataset = Dataset.from_dict(read("vectors"))
                self.assertTrue(fitness(circuit, dataset)["verified_truth_table"])
                self.assertEqual(len(dataset.rows), 1 << (p + q))
                for a, b in product(range(1 << p), range(1 << q)):
                    value = a | b << p
                    reference = expected(kind, a, b, p, q)
                    self.assertEqual(program.run(value), reference)
                    for implementation in (circuit, block):
                        output = implementation.evaluate(bits(value, p + q))
                        self.assertEqual([integer(output[port["offset"]:port["offset"] + port["bits"]])
                                          for port in program.ports["outputs"]], reference)

    def test_non_power_of_two_widths_and_constraints(self):
        rng = random.Random(28)
        for kind in KINDS:
            for p, q in ((3, 5), (5, 3)):
                program = Template(definition(kind)).instantiate({"p": p, "q": q})
                circuit = synthesize(program)
                pairs = [(0, 0), ((1 << p) - 1, (1 << q) - 1)]
                pairs += [(rng.randrange(1 << p), rng.randrange(1 << q)) for _ in range(20)]
                for a, b in pairs:
                    value = a | b << p
                    reference = expected(kind, a, b, p, q)
                    self.assertEqual(program.run(value), reference)
                    encoded = [bit for port, number in zip(program.ports["outputs"], reference)
                               for bit in bits(number, port["bits"])]
                    self.assertEqual(circuit.evaluate(bits(value, p + q)), encoded)
            for p, q in ((0, 1), (1, 0), (17, 1), (1, True)):
                with self.assertRaises(ValueError):
                    Template(definition(kind)).instantiate({"p": p, "q": q})

    def test_symbolic_min_max_width_validation_in_both_entry_points(self):
        document = definition("add")
        for expression, width in (("max(p,q)+1", 5), ("min(p,q)+1", 3),
                                  ("max(min(p,q),1)+1", 3)):
            document["interface"]["outputs"][0]["bits"] = expression
            document["source"] = "return 0"
            program = Template(document).instantiate({"p": 2, "q": 4})
            self.assertEqual(program.ports["outputs"][0]["bits"], width)
        for expression in ("max(p)", "min(p,q,1)", "max(p,q=1)", "unknown(p,q)", "max(p,True)"):
            document["interface"]["outputs"][0]["bits"] = expression
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    Template(document).instantiate({"p": 2, "q": 4})
                with self.assertRaises(ValueError):
                    specialize_interface(document["interface"], {"p": 2, "q": 4})

    def test_migration_preserves_names_folders_and_deletions(self):
        with tempfile.TemporaryDirectory(dir=".jobs") as directory:
            library = Library(directory)
            install_standard_arithmetic_examples(library)
            self.assertEqual(len(library.templates()), 4)
            self.assertEqual(len(library.datasets()), 36)
            self.assertEqual(len(library.blocks()), 36)
            self.assertTrue(all(p["fitness"]["verified_truth_table"] for p in library.programs()))
            entry = library.datasets()[0]
            library.update_function(entry["function_id"], "Mein Rechner", "Eigener Text")
            library.move_entry("function", entry["function_id"], "functions")
            library.save_folder("Meine Standardlösungen", "Eigene Beschreibung", "arithmetic", "standard-arithmetic")
            library.delete_function(library.datasets()[1]["function_id"])
            next((Path(directory) / "templates").glob("*.json")).unlink()
            next((Path(directory) / "blocks").glob("*.json")).unlink()
            before = library.tree()
            install_standard_arithmetic_examples(Library(directory))
            self.assertEqual(library.tree(), before)
            self.assertEqual(len(library.datasets()), 35)
            self.assertEqual(len(library.templates()), 3)
            self.assertEqual(len(library.blocks()), 35)
            self.assertEqual(next(d for d in library.datasets() if d["function_id"] == entry["function_id"])["name"], "Mein Rechner")


if __name__ == "__main__":
    unittest.main()

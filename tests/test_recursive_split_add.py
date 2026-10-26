"""Verify recursive wiring, carry preservation, and checked-in flat instances."""
import json
from pathlib import Path
import random
import unittest

from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, integer
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_recursive_add import definition, netlist


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples/circuits/recursive-split-add"


class RecursiveSplitAddTests(unittest.TestCase):
    def test_flat_instances_match_source_and_independent_addition_exhaustively(self):
        document = definition()
        self.assertEqual(json.loads((ROOT / "examples/templates/recursive-split-add.abstract.json").read_text(encoding="utf-8")),
                         Template(document).to_dict())
        for width in (1, 2, 4):
            with self.subTest(width=width):
                program = Template(document).instantiate({"n": width})
                prefix = OUTPUT / f"add-{width}"
                circuit = Circuit.from_dict(json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8")))
                self.assertEqual(circuit, synthesize(program))
                self.assertEqual(json.loads(prefix.with_suffix(".template.json").read_text(encoding="utf-8")), program.spec)
                self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"), netlist(circuit, width))
                dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                self.assertTrue(fitness(circuit, dataset)["verified_truth_table"])
                for a in range(1 << width):
                    for b in range(1 << width):
                        x = a | (b << width)
                        self.assertEqual(program.run(x), [(a+b) % (1 << width), (a+b) >> width])
                        self.assertEqual(integer(circuit.evaluate(bits(x, 2*width))), a+b)

    def test_larger_declared_widths_with_carry_boundaries(self):
        rng = random.Random(42)
        for width in (8, 16):
            program = Template(definition()).instantiate({"n": width})
            circuit = synthesize(program)
            maximum = (1 << width) - 1
            pairs = [(0, 0), (maximum, 1), (maximum, maximum), (0, maximum)]
            pairs += [(rng.randrange(maximum+1), rng.randrange(maximum+1)) for _ in range(16)]
            for a, b in pairs:
                x = a | (b << width)
                self.assertEqual(program.run(x), [(a+b) & maximum, (a+b) >> width])
                self.assertEqual(integer(circuit.evaluate(bits(x, 2*width))), a+b)

    def test_incrementer_includes_nonpower_width_and_full_overflow(self):
        document = definition()
        functions = document["source"].split("result = bits(ADD<n>")[0]
        document["conditions"] = ["n >= 1"]
        document["interface"]["inputs"][1] = {"name": "b", "bits": 1}
        document["interface"]["outputs"] = [{"name": "c", "bits": "n+1"}]
        document["source"] = functions + "return INC<n>(a, b)\n"
        for width in (1, 2, 3, 5):
            program = Template(document).instantiate({"n": width})
            circuit = synthesize(program)
            for a in range(1 << width):
                for enable in (0, 1):
                    x = a | (enable << width)
                    self.assertEqual(program.run(x), [a + enable])
                    self.assertEqual(integer(circuit.evaluate(bits(x, width+1))), a + enable)

    def test_template_and_direct_calls_reject_invalid_adder_widths(self):
        document = definition()
        for width in (0, 3, 6):
            with self.subTest(width=width), self.assertRaises(ValueError):
                Template(document).instantiate({"n": width})
        for width in (0, 3):
            bad = {**document, "source": document["source"].replace("ADD<n>(a, b)", f"ADD<{width}>(a, b)")}
            program = Template(bad).instantiate({"n": 4})
            with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                program.run(0)
            with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                synthesize(program)


if __name__ == "__main__":
    unittest.main()

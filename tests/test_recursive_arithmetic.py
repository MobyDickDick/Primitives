"""Recursive borrow/carry propagation and the normalized error representation."""
import copy
import json
from pathlib import Path
import random
import unittest

from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, integer
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_recursive_arithmetic import VARIANTS, definition, netlist


ROOT = Path(__file__).resolve().parents[1]


class RecursiveArithmeticTests(unittest.TestCase):
    def assert_pair(self, operation, width, program, circuit, a, b):
        value = a - b if operation == "sub" else a + b
        error = int(value < 0 or value >= 1 << width)
        expected = [0 if error else value, error]
        x = a | (b << width)
        self.assertEqual(program.run(x), expected, (operation, width, a, b))
        self.assertEqual(integer(circuit.evaluate(bits(x, 2 * width))),
                         expected[0] | (error << width), (operation, width, a, b))

    def test_source_and_flat_instances_exhaustively(self):
        for operation, (stem, _, _) in VARIANTS.items():
            document = definition(operation)
            self.assertEqual(json.loads((ROOT / "examples/templates" / f"{stem}.abstract.json").read_text(encoding="utf-8")),
                             Template(document).to_dict())
            for width in (1, 2, 4):
                with self.subTest(operation=operation, width=width):
                    program = Template(document).instantiate({"n": width})
                    prefix = ROOT / "examples/circuits" / stem / f"{operation}-{width}"
                    circuit = Circuit.from_dict(json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8")))
                    self.assertEqual(circuit, synthesize(program))
                    self.assertEqual(json.loads(prefix.with_suffix(".template.json").read_text(encoding="utf-8")), program.spec)
                    self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"), netlist(circuit, width, operation))
                    dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                    self.assertTrue(fitness(circuit, dataset)["verified_truth_table"])
                    for a in range(1 << width):
                        for b in range(1 << width):
                            self.assert_pair(operation, width, program, circuit, a, b)

    def test_large_widths_borrow_and_overflow_boundaries(self):
        rng = random.Random(25)
        for operation in VARIANTS:
            for width in (8, 16):
                program = Template(definition(operation)).instantiate({"n": width})
                circuit = synthesize(program)
                maximum = (1 << width) - 1
                half = 1 << (width // 2)
                pairs = [(0, 0), (0, 1), (1, 0), (maximum, maximum), (maximum, 1),
                         (maximum, 2), (0, maximum), (half, 1), (half, half - 1),
                         (half - 1, half), (half, half + 1), (maximum - 1, 1)]
                pairs += [(rng.randrange(maximum + 1), rng.randrange(maximum + 1)) for _ in range(32)]
                for a, b in pairs:
                    self.assert_pair(operation, width, program, circuit, a, b)

    def test_raw_subtraction_preserves_negative_remainders(self):
        document = definition("sub")
        document["source"] = document["source"].replace("result = bits(SUB<n>", "result = bits(SUB_raw<n>")
        for width in (1, 2, 4):
            program = Template(document).instantiate({"n": width})
            circuit = synthesize(program)
            for a in range(1 << width):
                for b in range(1 << width):
                    expected = [(a - b) % (1 << width), int(a < b)]
                    x = a | b << width
                    self.assertEqual(program.run(x), expected)
                    self.assertEqual(integer(circuit.evaluate(bits(x, 2 * width))),
                                     expected[0] | expected[1] << width)

    def test_one_bit_subtraction_matches_requested_basis(self):
        program = Template(definition("sub")).instantiate({"n": 1})
        for a in (0, 1):
            for b in (0, 1):
                self.assertEqual(program.run(a | b << 1), [a & (1 ^ b), (1 ^ a) & b])

    def helper(self, operation, expression, width, output_width, b_width=None):
        document = definition(operation)
        document["source"] = document["source"].rsplit("\nresult = bits(", 1)[0] + f"\nreturn {expression}\n"
        document["conditions"] = ["n >= 1"]
        document["interface"]["outputs"] = [{"name": "c", "bits": output_width}]
        if b_width is not None:
            document["interface"]["inputs"][1]["bits"] = b_width
        return Template(document).instantiate({"n": width})

    def test_decrementer_for_nonpower_widths_and_full_borrow(self):
        for width in (1, 2, 3, 5):
            program = self.helper("sub", "DEC<n>(a, b)", width, width + 1, 1)
            circuit = synthesize(program)
            for a in range(1 << width):
                for enable in (0, 1):
                    expected = (a - enable) % (1 << width) | int(a < enable) << width
                    x = a | enable << width
                    self.assertEqual(program.run(x), [expected])
                    self.assertEqual(integer(circuit.evaluate(bits(x, width + 1))), expected)

    def test_concatenation_widths_order_zero_padding_and_error_marker(self):
        for operation in VARIANTS:
            for expression, expected in (("CONCAT<2, 3>(a, b)", 25),
                                         ("CONCAT<3, 2>(a, b)", 17),
                                         ("CONCAT<4, 1>(const<4>(0), 1)", 16)):
                program = self.helper(operation, expression, 3, 5)
                circuit = synthesize(program)
                x = 1 | 6 << 3
                self.assertEqual(program.run(x), [expected])
                self.assertEqual(integer(circuit.evaluate(bits(x, 6))), expected)
            for expression in ("CONCAT<0, 1>(0, 1)", "CONCAT<128, 1>(0, 1)", "const<0>(0)"):
                program = self.helper(operation, expression, 1, 1)
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    program.run(0)
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    synthesize(program)

    def test_invalid_template_and_direct_widths_are_rejected(self):
        for operation in VARIANTS:
            document = definition(operation)
            for width in (0, 3, 6, 32):
                with self.assertRaises(ValueError):
                    Template(document).instantiate({"n": width})
            name = "SUB" if operation == "sub" else "ADD_checked"
            for width in (0, 3):
                bad = copy.deepcopy(document)
                bad["source"] = bad["source"].replace(f"{name}<n>(a, b)", f"{name}<{width}>(a, b)")
                program = Template(bad).instantiate({"n": 4})
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    program.run(0)
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    synthesize(program)


if __name__ == "__main__":
    unittest.main()

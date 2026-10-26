"""Check full recursive products, overflow normalization and both circuit forms."""
import copy
import json
import random
import unittest

from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, integer
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_recursive_mul import OUTPUT, SOURCE, bundle, definition, helper, netlist


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class RecursiveMulTests(unittest.TestCase):
    def test_source_boxes_and_flat_exports_against_all_input_pairs(self):
        template = Template(definition())
        self.assertEqual(read(SOURCE.with_suffix(".abstract.json")), template.to_dict())
        reports = read(OUTPUT / "verification.json")
        for width in (1, 2, 4):
            with self.subTest(width=width):
                prefix = OUTPUT / f"mul-{width}"
                program = template.instantiate({"w": width})
                hierarchy = BlockBundle(read(prefix.with_suffix(".block.json")))
                expanded = hierarchy.expand()
                circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                compiled = synthesize(program)
                dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                raw_program = helper(width, "MUL_raw", [("a", width), ("b", width)],
                                     2 * width, "MUL_raw<w>(a, b)")
                self.assertEqual(hierarchy.to_dict(), bundle(width).to_dict())
                self.assertEqual(circuit, expanded.simplify())
                self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"), netlist(circuit, width))
                checked = fitness(circuit, dataset)
                self.assertTrue(checked["verified_truth_table"])
                report = next(item for item in reports if item["parameters"]["w"] == width)
                self.assertEqual(report["fitness"], checked)
                self.assertEqual(report["hierarchy"], hierarchy.summary())
                # Projection must expose actual callable sub-boxes at every recursive level.
                self.assertEqual([n["name"] for n in hierarchy.view()["circuit"]["view_nodes"]
                                  if n["kind"] == "instance"], [f"MUL_raw<{width}>", f"CHECK<{width}>"])
                product_view = hierarchy.view(["product"])
                if width > 1:
                    children = [n for n in product_view["circuit"]["view_nodes"]
                                if n["kind"] == "instance" and n["id"].startswith("p")]
                    self.assertEqual(len(children), 4)
                    self.assertTrue(all(n["name"] == f"MUL_raw<{width // 2}>" for n in children))
                for a in range(1 << width):
                    for b in range(1 << width):
                        value = a * b
                        error = int(value >= 1 << width)
                        expected = [0 if error else value, error]
                        encoded = expected[0] | error << width
                        x = a | b << width
                        vector = bits(x, 2 * width)
                        self.assertEqual(program.run(x), expected, (width, a, b))
                        self.assertEqual(raw_program.run(x), [value], (width, a, b))
                        for implementation in (hierarchy, expanded, circuit, compiled):
                            self.assertEqual(integer(implementation.evaluate(vector)), encoded, (width, a, b))

    def test_one_bit_basis_and_exact_overflow_boundary(self):
        template = Template(definition())
        one = template.instantiate({"w": 1})
        for a in (0, 1):
            for b in (0, 1):
                self.assertEqual(one.run(a | b << 1), [a & b, 0])
        for width in (2, 4):
            program = template.instantiate({"w": width})
            half = 1 << (width // 2)
            for a, b in ((half, half), ((1 << width) - 1, 1), (0, (1 << width) - 1)):
                value = a * b
                self.assertEqual(program.run(a | b << width),
                                 [value, 0] if value < 1 << width else [0, 1])

    def test_large_width_references_and_structural_budget(self):
        rng = random.Random(26)
        for width in (8,):
            program = Template(definition()).instantiate({"w": width})
            maximum = (1 << width) - 1
            half = 1 << (width // 2)
            pairs = [(0, maximum), (maximum, 0), (maximum, 1), (maximum, maximum),
                     (half, half), (half - 1, half + 1)]
            pairs += [(rng.randrange(maximum + 1), rng.randrange(maximum + 1)) for _ in range(4)]
            for a, b in pairs:
                value = a * b
                self.assertEqual(program.run(a | b << width),
                                 [value, 0] if value < 1 << width else [0, 1])
            with self.assertRaisesRegex(ValueError, "512 Gattern"):
                synthesize(program)

    def test_invalid_template_and_recursive_call_widths(self):
        document = definition()
        for width in (0, 3, 6, 16, 32, True):
            with self.assertRaises(ValueError):
                Template(document).instantiate({"w": width})
        for name in ("MUL", "MUL_raw"):
            for width in (0, 3):
                bad = copy.deepcopy(document)
                bad["source"] = bad["source"].replace("result = bits(MUL<w>(a, b)",
                                                      f"result = bits({name}<{width}>(a, b)")
                program = Template(bad).instantiate({"w": 4})
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    program.run(0)
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    synthesize(program)


if __name__ == "__main__":
    unittest.main()

"""Independent arithmetic checks of division, exported NANDs and register reuse."""
import ast
import json
import random
import unittest

from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, integer
from primitives.library import fitness
from primitives.program import template_source
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.investigate_division import (OUTPUT, aligned_divmod, clocked_divide,
                                        definition, division_dataset, step_dataset)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class DivisionInvestigationTests(unittest.TestCase):
    def test_all_width_pairs_and_register_transitions(self):
        template = Template(definition())
        report = read(OUTPUT / "verification.json")
        self.assertEqual(report["total_division_pairs"], 900)
        count = 0
        for m in range(1, 5):
            for n in range(1, 5):
                with self.subTest(m=m, n=n):
                    prefix = OUTPUT / f"div-{m}-{n}"
                    program = template.instantiate({"m": m, "n": n})
                    circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                    self.assertEqual(circuit, synthesize(program))
                    dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                    self.assertEqual(dataset.rows, division_dataset(m, n, program).rows)
                    self.assertTrue(fitness(circuit, dataset)["verified_truth_table"])
                    step = Circuit.from_dict(read(OUTPUT / f"step-{n}.circuit.json"))
                    for a in range(1 << m):
                        for b in range(1 << n):
                            expected = [a // b, 0] if b else [0, 1]
                            self.assertEqual(program.run(a | b << m), expected)
                            self.assertEqual(integer(circuit.evaluate(bits(a, m) + bits(b, n))),
                                             expected[0] | expected[1] << m)
                            state = clocked_divide(a, b, m, n, step)
                            self.assertEqual([state["c"], state["err"]], expected)
                            self.assertEqual(state["cycles"], m if b else 0)
                            if b:
                                self.assertEqual(state["remainder"], a % b)
                                # Every prefix satisfies prefix = b*q + r, 0<=r<b.
                                for i, t in enumerate(state["trace"], 1):
                                    self.assertLess(t["rnext"], b)
                                    self.assertEqual(a >> (m - i), b*t["qnext"] + t["rnext"])
                            count += 1
        self.assertEqual(count, 900)

    def test_total_step_truth_tables_include_unreachable_states(self):
        template = Template(definition(True))
        for n in range(1, 5):
            program = template.instantiate({"n": n})
            dataset = Dataset.from_dict(read(OUTPUT / f"step-{n}.vectors.json"))
            self.assertEqual(dataset.rows, step_dataset(n, program).rows)
            for suffix in ("circuit.json", "evolution.json"):
                obj = read(OUTPUT / f"step-{n}.{suffix}")
                circuit = Circuit.from_dict(obj if suffix == "circuit.json" else obj["circuit"])
                self.assertTrue(fitness(circuit, dataset)["verified_truth_table"])
            for r in range(1 << n):
                for b in range(1 << n):
                    for digit in (0, 1):
                        t = 2*r + digit
                        take = int(t >= b)
                        self.assertEqual(program.run(r | b << n | digit << (2*n)),
                                         [(t - b*take) % (1 << n), take])

    def test_msb_recursion_and_decreasing_bit_length(self):
        for a in range(256):
            for b in range(1, 32):
                self.assertEqual(aligned_divmod(a, b), divmod(a, b))
                if a >= b:
                    d = a.bit_length() - b.bit_length()
                    s = b << d
                    if s > a:
                        d, s = d - 1, s >> 1
                    self.assertLessEqual(s, a)
                    self.assertGreater(2*s, a)
                    self.assertLess((a-s).bit_length(), a.bit_length())
        for a, b in ((-1, 2), (1, 0), (1, -1), (True, 1)):
            with self.assertRaises(ValueError):
                aligned_divmod(a, b)

    def test_search_exports_are_rechecked_and_sparse_table_is_not_exhaustive(self):
        for m in range(1, 5):
            for n in range(1, 5):
                prefix = OUTPUT / f"div-{m}-{n}"
                result = read(prefix.with_suffix(".evolution.json"))
                dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                self.assertEqual(result["fitness"], fitness(Circuit.from_dict(result["circuit"]), dataset))
                self.assertEqual(result["search"]["library_candidates"], 0)
                self.assertEqual(result["search"]["repair_cases"], 0)
        sparse = Dataset.from_dict(read(OUTPUT / "values-1-to-4.vectors.json"))
        self.assertEqual(len(sparse.rows), 16)
        self.assertFalse(sparse.exhaustive)
        self.assertTrue(all(row[-1] == 0 for row in sparse.rows))
        result = read(OUTPUT / "values-1-to-4.evolution.json")
        self.assertEqual(result["fitness"], fitness(Circuit.from_dict(result["circuit"]), sparse))
        self.assertFalse(result["fitness"]["verified_truth_table"])

    def test_static_source_and_supported_larger_reference_widths(self):
        tree = ast.parse(template_source(definition()["source"]))
        self.assertFalse(any(isinstance(n, (ast.For, ast.While, ast.FloorDiv, ast.Mod)) for n in ast.walk(tree)))
        template = Template(definition())
        rng = random.Random(90)
        for m, n in ((1, 8), (8, 1), (5, 7), (8, 8)):
            program = template.instantiate({"m": m, "n": n})
            for _ in range(20):
                a, b = rng.randrange(1 << m), rng.randrange(1 << n)
                self.assertEqual(program.run(a | b << m), [a // b, 0] if b else [0, 1])
        for params in ({"m": 0, "n": 1}, {"m": 1, "n": 9}):
            with self.assertRaises(ValueError):
                template.instantiate(params)


if __name__ == "__main__":
    unittest.main()

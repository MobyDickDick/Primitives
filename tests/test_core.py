import json
from pathlib import Path
import tempfile
import unittest
from primitives.circuit import Circuit, parse_expression
from primitives.dataset import Dataset, Expression, bits, generate, integer, preset
from primitives.evolution import Problem, SearchConfig
from primitives.library import Library
from primitives.runner import ROOT, search


class DatasetTests(unittest.TestCase):
    def test_contradictions_and_duplicate_rows(self):
        with self.assertRaisesRegex(ValueError, "Widerspruch"):
            Dataset("bad", 2, 1, [[0, 1, 0], [0, 1, 1]])
        with self.assertRaisesRegex(ValueError, "Widerspruch"):
            Dataset("bad", 1, 2, [[0, 1, 0], [0, 1, 1]])
        self.assertEqual(len(Dataset("ok", 1, 1, [[0, 1], [0, 1]]).rows), 1)

    def test_malformed_rows(self):
        for rows in ([], [[0, 0]], [[0, 1, 2]], [[0, 1, 0.0]], [[False, 1, 0]]):
            with self.assertRaises(ValueError):
                Dataset("bad", 2, 1, rows)

    def test_bit_order_and_arithmetic(self):
        self.assertEqual(bits(6, 4), [0, 1, 1, 0])
        for name in ("add", "sub", "mul", "div"):
            d = preset(name)
            self.assertTrue(d.exhaustive)
            for row in d.rows:
                a, b = integer(row[:2]), integer(row[2:4])
                expected = {"add": a+b, "sub": (a-b)%4, "mul": a*b, "div": a//b if b else 0}[name]
                self.assertEqual(integer(row[4:]), expected)

    def test_fixed_point_endpoints(self):
        d = preset("sin", samples=3)
        self.assertEqual(d.inputs, 16)
        self.assertEqual(d.outputs, 12)
        values = {integer(r[:16]): integer(r[16:]) for r in d.rows}
        self.assertEqual(values[0], 0)
        self.assertEqual(values[65535], 0)
        self.assertFalse(d.exhaustive)
        cosine = {integer(r[:16]): integer(r[16:]) for r in preset("cos", samples=2).rows}
        self.assertEqual(cosine, {0: 4095, 65535: 0})

    def test_expression_is_restricted(self):
        for source in ("__import__('os')", "x.real", "[x]", "2**1000000", "x << 100", "sqrt(-1)", "1/0"):
            with self.assertRaises(ValueError, msg=source):
                Expression(source)({"x": 1})
        self.assertEqual(Expression("a//b if b else 0")({"a": 3, "b": 0}), 0)
        with self.assertRaisesRegex(ValueError, "Ausgabe"):
            generate("overflow", 2, 1, "x+2")

    def test_sampling_and_oracle(self):
        a = generate("sample", 16, 16, "x", 20, 7)
        self.assertEqual(a.to_dict(), generate("sample", 16, 16, "x", 20, 7).to_dict())
        self.assertEqual(len(a.rows), 20)
        d = generate("oracle", 2, 2, "oracle", oracle=lambda x: (x&1)+((x>>1)&1))
        self.assertEqual(d.rows, Dataset.from_dict(json.loads((ROOT / "examples" / "half_adder.json").read_text())).rows)


class CircuitTests(unittest.TestCase):
    def test_user_notation(self):
        c = parse_expression("(1, (2,3))", 3)
        for x in range(8):
            b = bits(x, 3)
            self.assertEqual(c.evaluate(b), [1 - (b[0] & (1 - (b[1] & b[2])))])
        self.assertEqual(c.expressions(), ["(1) ⊼ ((2) ⊼ (3))"])
        for source in (c.expressions()[0], r"(1) \bar{\wedge} ((2) \bar{\wedge} (3))"):
            self.assertEqual(parse_expression(source, 3), c)

    def test_infix_grouping_and_shared_nodes(self):
        legacy = parse_expression("((1,2),(2,1))", 2)
        infix = parse_expression("((1) ⊼ (2)) ⊼ ((2) ⊼ (1))", 2)
        self.assertEqual(infix, legacy)
        self.assertEqual(parse_expression("(1)", 2).evaluate([1, 0]), [1])
        for source in ("1 ⊼ 2 ⊼ 3", "(1) ⊼", "⊼ (1) (2)", "(1)(2)", "(1) ∧ (2)"):
            with self.assertRaises(ValueError, msg=source):
                parse_expression(source, 3)

    def test_parse_and_reference_validation(self):
        for text in ("(0,1)", "(1,4)", "(1,2", "(1,2),3", "", "__import__", "(1 2)"):
            with self.assertRaises(ValueError, msg=text):
                parse_expression(text, 3)
        with self.assertRaises(ValueError):
            Circuit(2, ((0, 2),), (2,))

    def test_shared_nodes_and_compaction(self):
        c = parse_expression("((1,2),(2,1))", 2)
        self.assertEqual(len(c.gates), 2)
        unused = Circuit(2, ((0, 1), (0, 0), (2, 2)), (4, 0))
        compact = unused.compact()
        self.assertEqual(len(compact.gates), 2)
        for x in range(4):
            self.assertEqual(unused.evaluate(bits(x, 2)), compact.evaluate(bits(x, 2)))

    def test_packed_fitness_matches_scalar(self):
        d = preset("add")
        p = Problem(d, SearchConfig(gates=12, backend="python"))
        for _ in range(20):
            genome = p.random_genome()
            from primitives.evolution import genome_circuit
            c = genome_circuit(genome, d.inputs, d.outputs)
            errors = sum(a != b for row in d.rows for a, b in zip(c.evaluate(row[:d.inputs]), row[d.inputs:]))
            self.assertEqual(p.metrics(genome)[0], errors)


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / ".jobs").mkdir(exist_ok=True)

    def test_search_reproducible_and_bounded(self):
        config = SearchConfig(gates=8, population=24, generations=300, backend="python")
        a, b = search(preset("xor"), config), search(preset("xor"), config)
        self.assertEqual(a["circuit"], b["circuit"])
        self.assertLessEqual(a["search"]["evaluations"], 1 + config.population * config.generations)
        self.assertTrue(a["fitness"]["verified_truth_table"])

    def test_approximate_does_not_claim_exact(self):
        r = search(preset("xor"), SearchConfig(gates=1, population=2, generations=2, backend="python"))
        self.assertGreater(r["fitness"]["errors"], 0)
        self.assertFalse(r["fitness"]["exact_on_dataset"])

    def test_sample_is_not_full_verification(self):
        r = search(Dataset("one-row", 2, 1, [[0, 0, 1]]), SearchConfig(gates=1, backend="python"))
        self.assertTrue(r["fitness"]["exact_on_dataset"])
        self.assertFalse(r["fitness"]["verified_truth_table"])

    def test_library_roundtrip_and_composition(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as tmp:
            library = Library(tmp)
            r = search(preset("nand"), SearchConfig(gates=4, backend="python"), library)
            self.assertIn("exakt", r["id"])
            self.assertEqual(library.load_program(r["id"])["circuit"], r["circuit"])
            self.assertTrue(library.load_dataset(r["dataset_id"]).exhaustive)
            c = Circuit.from_dict(r["circuit"])
            problem = Problem(preset("xor"), SearchConfig(gates=8), [c])
            for _ in range(20):
                genome = problem.specimen()
                problem.metrics(genome)  # Valid acyclic grafts with resampled arguments.
            r2 = search(preset("or"), SearchConfig(gates=8, backend="python"), library)
            self.assertEqual(r2["search"]["library_candidates"], 1)
            self.assertIn(r["id"], r2["search"]["seed_library"])
            with self.assertRaises(ValueError):
                library.load_program("../../bad")

    @unittest.skipUnless((ROOT / ".runtime" / "tinylanguage" / "src" / "tiny_language.py").exists(), "TinyLanguage nicht eingerichtet")
    def test_real_tinylanguage_evolution(self):
        r = search(preset("xor"), SearchConfig(gates=8, population=24, generations=200))
        self.assertTrue(r["fitness"]["verified_truth_table"])
        c = Circuit.from_dict(r["circuit"])
        for row in preset("xor").rows:
            self.assertEqual(c.evaluate(row[:2]), row[2:])


if __name__ == "__main__":
    unittest.main()


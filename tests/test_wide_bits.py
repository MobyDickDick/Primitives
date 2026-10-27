"""128-bit interfaces across generation, execution, synthesis and persistence."""
import json
import unittest

from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import Dataset, Expression, bits, generate, integer
from primitives.evolution import Problem, SearchConfig
from primitives.formula import parse_formula, to_formula
from primitives.library import fitness
from primitives.operations import generate_operation
from primitives.ports import decode, encode, interface
from primitives.program import Program
from primitives.synthesis import synthesize


def ports(width, signed=False):
    return {"inputs": [{"name": "a", "bits": width, "signed": signed}],
            "outputs": [{"name": "c", "bits": width, "signed": signed}]}


class WideBitsTests(unittest.TestCase):
    def test_samples_of_huge_domains_are_exact_unique_and_reproducible(self):
        for width in (33, 63, 64, 127, 128):
            with self.subTest(width=width):
                ds = generate("wide", width, width, "x", samples=256, seed=27)
                self.assertEqual(ds.to_dict(), generate("wide", width, width, "x", 256, 27).to_dict())
                self.assertEqual(len(ds.rows), 256)
                self.assertEqual(len({tuple(row[:width]) for row in ds.rows}), 256)
                self.assertFalse(ds.exhaustive)
                self.assertEqual(ds.rows[0], [0] * (width * 2))
                self.assertEqual(ds.rows[-1], [1] * (width * 2))
                for row in ds.rows:
                    self.assertEqual(row[:width], row[width:])
                self.assertEqual(Dataset.from_dict(json.loads(json.dumps(ds.to_dict()))), ds)

    def test_wide_arithmetic_and_prioritized_edges(self):
        for op, result_width in (("ADD", 65), ("MUL", 128)):
            spec = {"definition": op, "parameters": {"a_bits": 64, "b_bits": 64, "result_bits": result_width}}
            ds = generate_operation(spec, samples=256, seed=27)
            self.assertEqual(ds.to_dict(), generate_operation(spec, 256, 27).to_dict())
            self.assertEqual(len(ds.rows), 256)
            self.assertIn([1] * 128, [row[:128] for row in ds.rows])
            for row in ds.rows:
                a, b = integer(row[:64]), integer(row[64:128])
                self.assertEqual(integer(row[128:]), a + b if op == "ADD" else a * b)

    def test_unsigned_and_signed_boundary_values(self):
        for signed in (False, True):
            spec = interface(ports(128, signed))
            values = (0, 1, (1 << 128) - 1) if not signed else (-(1 << 127), -1, 0, (1 << 127) - 1)
            for value in values:
                encoded = encode(value, spec["outputs"][0], 0)
                self.assertEqual(decode(encoded, spec["inputs"][0]), value)
                program = Program({"version": 1, "source": "return pack(bits(a, 128))"}, ports(128))
                self.assertEqual(program.run(encoded), [encoded])
            for value in ((-1, 1 << 128) if not signed else (-(1 << 127) - 1, 1 << 127)):
                with self.assertRaises(ValueError):
                    encode(value, spec["outputs"][0], 0)

    def test_shifts_and_powers_through_128_bits(self):
        self.assertEqual(Expression("2 ** 128 - 1")({}), (1 << 128) - 1)
        for amount in (0, 33, 64, 127, 128):
            for operation in ("SHL", "SHR", "SAR"):
                ds = generate_operation({"definition": operation, "parameters": {
                    "a_bits": 128, "result_bits": 128, "shift": amount,
                    "signed": operation == "SAR"}}, samples=12)
                for row in ds.rows:
                    a = integer(row[:128])
                    expected = ((a << amount) & ((1 << 128) - 1) if operation == "SHL" else
                                a >> amount if operation == "SHR" else
                                (a - (1 << 128) if a >> 127 else a) >> amount)
                    self.assertEqual(integer(row[128:]), expected % (1 << 128))
        program = Program({"version": 1, "source": "return (a >> 127) << 127"}, ports(128))
        self.assertEqual(program.run((1 << 128) - 1), [1 << 127])
        for source in ("1 << 129", "1 >> 129", "2 ** 129"):
            with self.assertRaises(ValueError):
                Expression(source)({})

    def test_template_synthesis_circuit_and_fitness_at_128_bits(self):
        program = Program({"version": 2, "parameters": {"n": 128}, "interface": ports("n"),
                           "source": "return pack(bits(a, n)[::-1])", "conditions": ["2**n > n"]})
        circuit = synthesize(program)
        self.assertEqual(circuit, Circuit(128, (), tuple(reversed(range(128)))))
        ds = generate("reverse128", 128, 128, ports=program.ports, program=program.spec, samples=8)
        self.assertEqual(fitness(circuit, ds)["errors"], 0)
        problem = Problem(ds, SearchConfig(gates=1, backend="python"), incumbent=circuit)
        self.assertEqual(problem.metrics(problem.initial_genome())[0], 0)
        self.assertEqual(Circuit.from_dict(json.loads(json.dumps(circuit.to_dict()))), circuit)
        # A leaf block exercises named ports, expansion and vector generation.
        bundle = BlockBundle.from_circuit("reverse128", circuit, program.ports)
        self.assertEqual(bundle.expand(), circuit)
        self.assertEqual(fitness(circuit, bundle.dataset(8))["errors"], 0)

    def test_nand_wires_beyond_index_127_and_128_bit_overflow(self):
        circuit = Circuit(128, tuple((i, i) for i in range(128)), tuple(range(128, 256)))
        ds = generate_operation({"definition": "NOT", "parameters": {
            "a_bits": 128, "result_bits": 128}}, samples=8)
        self.assertEqual(fitness(circuit, ds)["errors"], 0)
        bundle = BlockBundle.from_circuit("invert128", circuit)
        self.assertEqual(len(bundle.definition["interface"]["inputs"]), 128)
        for row in ds.rows:
            self.assertEqual(bundle.evaluate(row[:128]), row[128:])
        wrapped = generate_operation({"definition": "INC", "parameters": {
            "a_bits": 128, "result_bits": 128, "overflow": "wrap"}}, samples=2)
        self.assertIn([1] * 128 + [0] * 128, wrapped.rows)
        with self.assertRaisesRegex(ValueError, "Ausgabe"):
            generate_operation({"definition": "INC", "parameters": {
                "a_bits": 128, "result_bits": 128, "overflow": "error"}}, samples=2)

    def test_128_single_bit_ports_and_formula_results(self):
        spec = {"inputs": [{"name": f"a{i}", "bits": 1} for i in range(128)],
                "outputs": [{"name": f"c{i}", "bits": 1} for i in range(128)]}
        formula = ";".join(f"c{i}=a{i}" for i in range(128))
        self.assertEqual(len(parse_formula(to_formula(parse_formula(formula)))), 128)
        ds = generate("identity", 128, 128, ports=spec, formula=formula, samples=3)
        self.assertTrue(all(row[:128] == row[128:] for row in ds.rows))

    def test_width_limit_is_still_enforced(self):
        for width in (0, 129, True):
            with self.assertRaises(ValueError):
                interface(ports(width))
            with self.assertRaises(ValueError):
                generate("invalid", width, 1, "0")
            with self.assertRaises(ValueError):
                Circuit(width, (), (0,))
        with self.assertRaises(ValueError):
            interface({"inputs": [{"name": "a", "bits": 128}, {"name": "b", "bits": 1}],
                       "outputs": [{"name": "c", "bits": 1}]})
        with self.assertRaises(ValueError):
            Circuit(128, (), (0,) * 129)
        with self.assertRaises(ValueError):
            Program({"version": 2, "parameters": {"n": 129}, "interface": ports(1),
                     "source": "return a"})


if __name__ == "__main__":
    unittest.main()

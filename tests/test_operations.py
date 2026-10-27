import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, generate, integer
from primitives.evolution import SearchConfig
from primitives.library import Library
from primitives.operations import OPERATIONS, generate_operation
from primitives.ports import interface
from primitives.runner import ROOT, search


def operation(name, a, b, c, **params):
    return generate_operation({"definition": name, "parameters": {
        "a_bits": a, "b_bits": b, "result_bits": c, **params}}, samples=65536)


class OperationTests(unittest.TestCase):
    def test_arithmetic_widths_and_flags_against_integer_reference(self):
        for name in ("ADD", "SUB", "MUL"):
            for a_width, b_width, c_width in ((2, 3, 4), (4, 4, 4), (4, 4, 5), (2, 2, 4)):
                for signed in (False, True):
                    with self.subTest(name=name, widths=(a_width, b_width, c_width), signed=signed):
                        ds = operation(name, a_width, b_width, c_width, signed=signed, flag=True)
                        self.assertTrue(ds.exhaustive)
                        for row in ds.rows:
                            a, b = integer(row[:a_width]), integer(row[a_width:ds.inputs])
                            if signed:
                                if a >= 2 ** (a_width - 1): a -= 2 ** a_width
                                if b >= 2 ** (b_width - 1): b -= 2 ** b_width
                            expected = {"ADD": a + b, "SUB": a - b, "MUL": a * b}[name]
                            low = -(2 ** (c_width - 1)) if signed else 0
                            high = 2 ** (c_width - int(signed)) - 1
                            self.assertEqual(integer(row[ds.inputs:ds.inputs + c_width]), expected % 2 ** c_width)
                            flag = expected < 0 if name == "SUB" and not signed else not low <= expected <= high
                            self.assertEqual(row[-1], int(flag))
        truncated = operation("SUB", 3, 1, 1, flag=True)
        self.assertIn(bits(7, 3) + [0] + [1, 0], truncated.rows)  # 7 - 0 truncates, but does not borrow.

    def test_error_overflow_and_legacy_semantics(self):
        for name in ("ADD", "SUB", "MUL"):
            with self.assertRaisesRegex(ValueError, "Ausgabe c"):
                operation(name, 2, 2, 2, overflow="error")
        with self.assertRaisesRegex(ValueError, "Ausgabe"):
            generate("legacy", 4, 2, "a+b")
        self.assertTrue(operation("ADD", 2, 3, 4, overflow="error").exhaustive)
        self.assertTrue(operation("ADD", 2, 3, 4, overflow="error", signed=True).exhaustive)

    def test_word_logic_with_unequal_widths(self):
        for name in ("NOT", "NAND", "AND", "OR", "XOR", "NOR", "XNOR"):
            ds = operation(name, 2, 3, 4)
            for row in ds.rows:
                a = integer(row[:2])
                b = integer(row[2:ds.inputs])
                expected = {"NOT": ~a, "AND": a & b, "OR": a | b, "XOR": a ^ b,
                            "NAND": ~(a & b), "NOR": ~(a | b), "XNOR": ~(a ^ b)}[name]
                self.assertEqual(integer(row[ds.inputs:]), expected & 15)

    def test_named_multi_input_and_multi_result_roundtrip(self):
        ports = {"inputs": [{"name": "left", "bits": 2, "signed": True},
                            {"name": "right", "bits": 3}, {"name": "enable", "bits": 1}],
                 "outputs": [{"name": "sum", "bits": 4, "signed": True, "overflow": "wrap"},
                             {"name": "valid", "bits": 1}]}
        ds = generate("named", 6, 5, {"sum": "left+right if enable else 0", "valid": "enable"}, 64, ports=ports)
        for row in ds.rows:
            left, right, enabled = integer(row[:2]), integer(row[2:5]), row[5]
            if left >= 2: left -= 4
            self.assertEqual(integer(row[6:10]), (left + right) % 16 if enabled else 0)
            self.assertEqual(row[10], enabled)
        restored = Dataset.from_dict(json.loads(json.dumps(ds.to_dict())))
        self.assertEqual(restored.to_dict(), ds.to_dict())
        self.assertEqual([p["offset"] for p in restored.metadata["interface"]["inputs"]], [0, 2, 5])

    def test_invalid_interfaces_metadata_and_limits(self):
        base = {"inputs": [{"name": "a", "bits": 2}], "outputs": [{"name": "c", "bits": 2}]}
        for name in ("x", "x0", "sin", "for", "a-b", "_private"):
            bad = copy.deepcopy(base); bad["inputs"][0]["name"] = name
            with self.assertRaises(ValueError): interface(bad)
        for edit in ({"bits": 0}, {"bits": True}, {"bits": 129}, {"offset": 1}, {"signed": 1}):
            bad = copy.deepcopy(base); bad["inputs"][0].update(edit)
            with self.assertRaises(ValueError): interface(bad)
        for bad in ({**base, "bit_order": "MSB-first"},
                    {**base, "outputs": [{"name": "a", "bits": 1}]},
                    {**base, "inputs": [{"name": "a", "bits": 128}, {"name": "b", "bits": 1}]},
                    {**base, "outputs": [{"name": "c", "bits": 1, "overflow": "silent"}]}):
            with self.assertRaises(ValueError): interface(bad)
        with self.assertRaises(ValueError): generate("bad", 3, 2, "a", ports=base)
        with self.assertRaises(ValueError): generate("bad", 2, 2, {"wrong": "a"}, ports=base)
        with self.assertRaises(ValueError): operation("ADD", 128, 1, 1)
        with self.assertRaises(ValueError): operation("ADD", 1, 1, 128, flag=True)
        with self.assertRaises(ValueError): operation("ADD", 1, 1, 1, signed=1)
        bad = operation("ADD", 2, 3, 4).to_dict()
        bad["metadata"]["interface"]["inputs"][0]["bits"] = 3
        with self.assertRaises(ValueError): Dataset.from_dict(bad)
        bad = operation("ADD", 2, 3, 4).to_dict()
        bad["metadata"]["operation"]["parameters"]["signed"] = True
        with self.assertRaises(ValueError): Dataset.from_dict(bad)

    def test_sampling_is_bounded_reproducible_and_not_full(self):
        spec = {"definition": "ADD", "parameters": {"a_bits": 16, "b_bits": 16, "result_bits": 32}}
        a = generate_operation(spec, 100, 7)
        self.assertEqual(a.to_dict(), generate_operation(spec, 100, 7).to_dict())
        self.assertEqual(len(a.rows), 100)
        self.assertFalse(a.exhaustive)
        self.assertIn(bits(0, 64), a.rows)
        with self.assertRaises(ValueError): generate_operation(spec, 65537)

    def test_any_nand_circuit_can_be_referenced_with_new_widths(self):
        c = Circuit(2, ((0, 1), (2, 2)), (2, 3, 0))
        ports = {"inputs": [{"name": "left", "bits": 2}, {"name": "right", "bits": 3}],
                 "outputs": [{"name": name, "bits": 4, "overflow": "wrap"} for name in ("nand", "andResult", "direct")]}
        ds = generate("wider NAND", 5, 12, None, 32, ports=ports, reference_circuit=c.to_dict())
        for row in ds.rows:
            a, b = integer(row[:2]), integer(row[2:5])
            self.assertEqual([integer(row[i:i+4]) for i in (5, 9, 13)], [~(a & b) & 15, a & b, a])
        self.assertEqual(Dataset.from_dict(ds.to_dict()).to_dict(), ds.to_dict())
        for x in range(4):
            one_bit = {"inputs": [{"name": "a", "bits": 1}, {"name": "b", "bits": 1}],
                       "outputs": [{"name": f"out{i}", "bits": 1, "overflow": "wrap"} for i in range(3)]}
            d = generate("same", 2, 3, None, 4, ports=one_bit, reference_circuit=c.to_dict())
            self.assertIn(bits(x, 2) + c.evaluate(bits(x, 2)), d.rows)
        with self.assertRaises(ValueError): generate("bad", 2, 2, None, ports={"inputs": [{"name": "a", "bits": 2}],
            "outputs": [{"name": "out", "bits": 2}]}, reference_circuit=c.to_dict())

    def test_reference_needs_no_existing_implementation_and_survives_search(self):
        ds = operation("XOR", 1, 1, 1)
        (ROOT / ".jobs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as tmp:
            library = Library(tmp)
            self.assertEqual(library.programs(), [])
            key = library.save_dataset(ds)
            self.assertEqual(library.load_dataset(key).metadata, ds.metadata)
            result = search(ds, SearchConfig(gates=8, generations=300, backend="python"), library)
            self.assertTrue(result["fitness"]["verified_truth_table"])
            self.assertEqual(library.load_program(result["id"])["dataset_metadata"], ds.metadata)
            self.assertEqual(library.load_dataset(result["dataset_id"]).metadata, ds.metadata)
            renamed = generate("other ports", 2, 1, {"value": "left ^ right"}, ports={
                "inputs": [{"name": "left", "bits": 1}, {"name": "right", "bits": 1}],
                "outputs": [{"name": "value", "bits": 1}]})
            kept = library.save_program(result, renamed)
            self.assertEqual(kept["id"], result["id"])
            saved_variant = next(d for d in library.datasets() if d["name"] == "other ports")
            self.assertEqual(library.load_dataset(saved_variant["id"]).metadata, renamed.metadata)

    def test_cli_widths_and_named_multi_results(self):
        (ROOT / ".jobs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as tmp:
            output = Path(tmp) / "vectors.json"
            def run(*args):
                return subprocess.run([sys.executable, "-m", "primitives", "--data-dir", tmp, "generate", *args,
                                       "--out", str(output)], cwd=ROOT, capture_output=True, text=True)
            result = run("--operation", "ADD", "--a-bits", "2", "--b-bits", "3", "--result-bits", "4", "--flag")
            self.assertEqual(result.returncode, 0, result.stderr)
            ds = Dataset.from_dict(json.loads(output.read_text(encoding="utf-8")))
            self.assertEqual((ds.inputs, ds.outputs, len(ds.rows)), (5, 5, 32))
            spec = Path(tmp) / "ports.json"
            spec.write_text(json.dumps({"inputs": [{"name": "value", "bits": 2}],
                "outputs": [{"name": "copy", "bits": 2}, {"name": "zero", "bits": 1}]}), encoding="utf-8")
            expressions = Path(tmp) / "expressions.json"
            expressions.write_text(json.dumps({"copy": "value", "zero": "value == 0"}), encoding="utf-8")
            result = run("--interface", str(spec), "--expressions", str(expressions), "--inputs", "2", "--outputs", "3")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(Dataset.from_dict(json.loads(output.read_text(encoding="utf-8"))).rows), 4)
            self.assertNotEqual(run("--preset", "add", "--a-bits", "3").returncode, 0)

    def test_independent_add_functions_coexist_without_circuits(self):
        (ROOT / ".jobs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as tmp:
            library = Library(tmp)
            for a, b, c in ((1, 1, 2), (4, 4, 5), (8, 8, 9), (1, 1, 16)):
                ds = generate_operation({"definition": "ADD", "parameters": {
                    "a_bits": a, "b_bits": b, "result_bits": c}}, samples=256)
                library.save_dataset(ds)
                for row in ds.rows:
                    self.assertEqual(integer(row[a+b:]), integer(row[:a]) + integer(row[a:a+b]))
            reloaded = Library(tmp)
            catalog = reloaded.datasets()
            self.assertEqual({d["function_name"] for d in catalog}, {"ADD(1,1,2)", "ADD(4,4,5)", "ADD(8,8,9)", "ADD(1,1,16)"})
            self.assertEqual(len({d["function_id"] for d in catalog}), 4)
            self.assertEqual(reloaded.programs(), [])
            for entry in catalog:
                self.assertEqual(reloaded.load_dataset(entry["id"]).metadata, entry["metadata"])
            # New samples belong to the same defined function, but remain individually loadable.
            sampled = generate_operation({"definition": "ADD", "parameters": {
                "a_bits": 8, "b_bits": 8, "result_bits": 9}}, samples=32, seed=9, name="other sample")
            library.save_dataset(sampled)
            catalog = library.datasets()
            self.assertEqual(len(catalog), 5)
            self.assertEqual(len({d["function_id"] for d in catalog}), 4)
            signed = generate_operation({"definition": "ADD", "parameters": {
                "a_bits": 8, "b_bits": 8, "result_bits": 9, "signed": True}})
            library.save_dataset(signed)
            self.assertEqual(len({d["function_id"] for d in library.datasets()}), 5)


if __name__ == "__main__":
    unittest.main()

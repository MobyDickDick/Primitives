import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, integer, preset
from primitives.operations import OPERATIONS, generate_operation, operation_variant
from primitives.ports import decode
from primitives.runner import ROOT


def task(name, **params):
    return generate_operation({"definition": name, "parameters": params}, samples=65536)


class CPUOperationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / ".jobs").mkdir(exist_ok=True)

    def test_division_exhaustive_signed_unsigned_and_unequal_widths(self):
        for signed in (False, True):
            for a_bits, b_bits in ((3, 3), (2, 3)):
                ds = task("DIV", a_bits=a_bits, b_bits=b_bits, result_bits=4, signed=signed)
                self.assertTrue(ds.exhaustive)
                for row in ds.rows:
                    a, b = [decode(integer(row[:ds.inputs]), p) for p in ds.metadata["interface"]["inputs"]]
                    # Independent truncation toward zero using signed floor quotient.
                    q = a // b if b else 0
                    if b and a % b and (a < 0) != (b < 0): q += 1
                    self.assertEqual(row[ds.inputs:], bits(q % 16, 4) + [int(b != 0), int(b == 0)])
        wrapped = task("DIV", signed=True)
        self.assertIn(bits(4, 3) + bits(7, 3) + bits(4, 3) + [1, 0], wrapped.rows)
        with self.assertRaisesRegex(ValueError, "Ausgabe c"):
            task("DIV", signed=True, overflow="error")
        self.assertEqual(preset("div").outputs, 2)  # Existing CLI preset retains its contract.

    def test_predicates_and_comparisons_for_all_small_inputs(self):
        predicates = {"IsZero": lambda a: a == 0, "IsNonZero": lambda a: a != 0, "IsNegative": lambda a: a < 0}
        comparisons = {"EQ": lambda a,b: a == b, "NE": lambda a,b: a != b,
                       "LT": lambda a,b: a < b, "LE": lambda a,b: a <= b,
                       "GT": lambda a,b: a > b, "GE": lambda a,b: a >= b}
        for name in [*predicates, *comparisons]:
            for signed in (False, True):
                ds = task(name, a_bits=3, b_bits=2, signed=signed)
                self.assertTrue(ds.exhaustive)
                self.assertFalse(ds.metadata["interface"]["outputs"][0]["signed"])
                for row in ds.rows:
                    args = [decode(integer(row[:ds.inputs]), p) for p in ds.metadata["interface"]["inputs"]]
                    expected = predicates[name](*args) if name in predicates else comparisons[name](*args)
                    self.assertEqual(row[-1], int(expected), (name, signed, args))

    def test_shifts_exhaustive_zero_width_and_oversized_counts(self):
        for name in ("SHL", "SHR", "SAR"):
            for signed in (False, True):
                ds = task(name, a_bits=3, b_bits=3, result_bits=4, signed=signed)
                for row in ds.rows:
                    a, n = integer(row[:3]), integer(row[3:6])
                    if name == "SHL": expected = (a * (2 ** n)) % 8
                    elif name == "SHR": expected = a // (2 ** n)
                    else: expected = (a - 8 if a >= 4 else a) // (2 ** n)
                    if signed and name != "SAR" and expected >= 4: expected -= 8
                    self.assertEqual(integer(row[6:]), expected % 16, (name, signed, a, n))
                for n in (0, 1, 3, 4, 32):
                    fixed = task(name, a_bits=3, result_bits=4, signed=signed, shift=n)
                    self.assertEqual(fixed.inputs, 3)
                    self.assertEqual(Dataset.from_dict(fixed.to_dict()).to_dict(), fixed.to_dict())
                    for row in fixed.rows:
                        a = integer(row[:3])
                        expected = ((a * 2 ** n) % 8 if name == "SHL" else a // 2 ** n if name == "SHR"
                                    else (a - 8 if a >= 4 else a) // 2 ** n)
                        if signed and name != "SAR" and expected >= 4: expected -= 8
                        self.assertEqual(integer(row[3:]), expected % 16)
        # A wide count bus must never evaluate an enormous Python shift.
        ds = generate_operation({"definition": "SHL", "parameters": {"a_bits": 1, "b_bits": 31}}, 64)
        self.assertFalse(ds.exhaustive)
        self.assertEqual(len(ds.rows), 64)

    def test_increment_decrement_and_multiplexer(self):
        for name, delta in (("INC", 1), ("DEC", -1)):
            for signed in (False, True):
                ds = task(name, a_bits=3, result_bits=3, signed=signed, flag=True)
                for row in ds.rows:
                    a = decode(integer(row[:3]), ds.metadata["interface"]["inputs"][0])
                    expected = a + delta
                    low, high = (-4, 3) if signed else (0, 7)
                    self.assertEqual(row[3:], bits(expected % 8, 3) + [int(not low <= expected <= high)])
                with self.assertRaises(ValueError):
                    task(name, a_bits=3, result_bits=3, signed=signed, overflow="error")
        for signed in (False, True):
            ds = task("MUX", a_bits=2, b_bits=3, result_bits=4, signed=signed)
            for row in ds.rows:
                a, b, select = [decode(integer(row[:6]), p) for p in ds.metadata["interface"]["inputs"]]
                self.assertEqual(integer(row[6:]), (b if select else a) % 16)

    def test_sampling_includes_individual_boundaries_and_shift_limits(self):
        for name in ("DIV", "SHR", "LT"):
            spec = {"definition": name, "parameters": {"a_bits": 16, "b_bits": 16, "signed": True}}
            ds = generate_operation(spec, 256, 7)
            inputs = {integer(r[:32]) for r in ds.rows}
            for a, b in ((0, 0), (65535, 65535), (32768, 0), (0, 32768), (0, 16), (0, 17), (32768, 65535)):
                self.assertIn(a + (b << 16), inputs)
            self.assertEqual(len(ds.rows), 256)
            self.assertFalse(ds.exhaustive)
            self.assertEqual(ds.to_dict(), generate_operation(spec, 256, 7).to_dict())

    def test_invalid_parameters_and_limits(self):
        for name, params in (("SHL", {"shift": -1}), ("SAR", {"shift": True}), ("SHR", {"shift": 129}),
                             ("ADD", {"shift": 1}), ("DIV", {"flag": True}), ("MUX", {"flag": True}),
                             ("EQ", {"result_bits": 2}), ("IsZero", {"result_bits": 2}),
                             ("DIV", {"result_bits": 127}), ("MUX", {"a_bits": 64, "b_bits": 64})):
            with self.subTest(name=name, params=params), self.assertRaises(ValueError): task(name, **params)
        with self.assertRaises(ValueError): operation_variant({"definition": "SHL", "parameters": {"unknown": 1}})

    def test_archived_examples_and_existing_nand_implementations(self):
        paths = list((ROOT / "examples" / "operations").glob("*.json"))
        self.assertEqual(len(paths), len(OPERATIONS) + 3)
        seen = set()
        for path in paths:
            ds = Dataset.from_dict(json.loads(path.read_text(encoding="utf-8")))
            seen.add(ds.metadata["operation"]["definition"])
            self.assertTrue(ds.exhaustive)
            self.assertEqual(ds.to_dict(), generate_operation(ds.metadata["operation"], 65536).to_dict())
        self.assertEqual(seen, set(OPERATIONS))
        for path in (ROOT / "examples" / "library" / "programs").glob("*.json"):
            result = json.loads(path.read_text(encoding="utf-8"))
            ds = Dataset.from_dict(json.loads((ROOT / "examples" / "library" / "datasets" / (result["dataset_id"] + ".json")).read_text(encoding="utf-8")))
            circuit = Circuit.from_dict(result["circuit"])
            for row in ds.rows:
                self.assertEqual(circuit.evaluate(row[:ds.inputs]), row[ds.inputs:])

    def test_cli_fixed_shift_and_signed_division(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as tmp:
            out = Path(tmp) / "vectors.json"
            for args in (("--operation", "SAR", "--shift", "32", "--signed"), ("--operation", "DIV", "--signed")):
                run = subprocess.run([sys.executable, "-m", "primitives", "--data-dir", tmp, "generate", *args,
                                      "--out", str(out)], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                ds = Dataset.from_dict(json.loads(out.read_text(encoding="utf-8")))
                self.assertTrue(ds.exhaustive)
            for args in (("--operation", "ADD", "--shift", "1"), ("--preset", "xor", "--shift", "1")):
                run = subprocess.run([sys.executable, "-m", "primitives", "generate", *args, "--out", str(out)],
                                     cwd=ROOT, capture_output=True, text=True)
                self.assertNotEqual(run.returncode, 0)

    def test_seed_library_is_idempotent_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as tmp:
            command = [sys.executable, "tools/seed_library.py", "--data-dir", tmp]
            first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            paths = sorted(Path(tmp).rglob("*.json"))
            before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
            self.assertEqual(len(paths), 45)  # 29 reference datasets + 8 datasets + 8 circuits.
            second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertTrue(second.stdout.startswith("0 "), second.stdout)
            self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths})


if __name__ == "__main__":
    unittest.main()

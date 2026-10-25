import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from primitives.dataset import Dataset, generate, integer, preset
from primitives.library import Library, function_id
from primitives.program import Program, ProgramCancelled, DEFAULT_LIMITS
from primitives.runner import ROOT


PORTS = {"inputs": [{"name": "n", "bits": 4}], "outputs": [{"name": "c", "bits": 8}]}
FOR = "s = 0\nfor i in range(n):\n    s += i\nreturn s"
WHILE = "s = 0\ni = 0\nwhile i < n:\n    s += i\n    i += 1\nreturn s"


def spec(source, **limits):
    return {"version": 1, "source": source, "limits": limits}


def vectors(source, ports=PORTS, **kwargs):
    return generate("Programm", sum(p["bits"] for p in ports["inputs"]), sum(p["bits"] for p in ports["outputs"]),
                    ports=ports, program=spec(source), **kwargs)


class ProgramTests(unittest.TestCase):
    def test_sum_for_while_and_independent_reference_all_inputs(self):
        for source in (FOR, WHILE):
            ds = vectors(source)
            self.assertTrue(ds.exhaustive)
            for row in ds.rows:
                n = integer(row[:4])
                self.assertEqual(integer(row[4:]), n * (n - 1) // 2)
            self.assertEqual(ds.metadata["program"]["limits"], DEFAULT_LIMITS)

    def test_nested_branches_and_multiple_returns(self):
        source = "if n < 8:\n    if n == 0:\n        return 1\n    else:\n        c = n * 2\nelse:\n    c = n - 1\nreturn c"
        for row in vectors(source).rows:
            n = integer(row[:4])
            self.assertEqual(integer(row[4:]), 1 if n == 0 else 2 * n if n < 8 else n - 1)

    def test_range_steps_nested_loops_and_range_bound_snapshot(self):
        source = "s = 0\nm = n\nfor i in range(m, -1, -2):\n    m = 0\n    for j in range(1, 4):\n        s += j\nreturn s"
        for row in vectors(source).rows:
            n = integer(row[:4])
            self.assertEqual(integer(row[4:]), (n // 2 + 1) * 6)
        self.assertEqual(Program(spec("for i in range(0):\n    c = 1\nreturn 7"), PORTS).run(0), [7])
        self.assertEqual(Program(spec("s = 0\nfor i in range(0, n, 2):\n    s += i\nreturn s"), PORTS).run(7), [12])

    def test_fresh_state_and_uninitialized_paths(self):
        p = Program(spec("if n == 0:\n    c = 7\nreturn c"), PORTS)
        self.assertEqual(p.run(0), [7])
        with self.assertRaisesRegex(ValueError, "x=1.*Zeile 3.*noch nicht zugewiesen"):
            p.run(1)
        with self.assertRaisesRegex(ValueError, "Programmende ohne return"):
            Program(spec("if n:\n    return n"), PORTS).run(0)

    def test_signed_multiple_outputs_wrap_and_error(self):
        ports = {"inputs": [{"name": "a", "bits": 3, "signed": True}, {"name": "b", "bits": 2}],
                 "outputs": [{"name": "c", "bits": 3, "signed": True, "overflow": "wrap"},
                             {"name": "negative", "bits": 1}]}
        ds = vectors("s = a + b\nreturn s, s < 0", ports)
        for row in ds.rows:
            a, b = integer(row[:3]), integer(row[3:5])
            if a >= 4: a -= 8
            self.assertEqual(integer(row[5:8]), (a + b) % 8)
            self.assertEqual(row[8], int(a + b < 0))
        ports["outputs"][0]["overflow"] = "error"
        with self.assertRaisesRegex(ValueError, "Ausgabe c für x="):
            vectors("return a+b, a+b < 0", ports)

    def test_integer_operators_short_circuit_and_negative_division(self):
        p = Program(spec("v = (-7 // 3) + mod(-7, 3)\nif n == 0 or 1 // n:\n    v += 4\nreturn (v ** 2) + xor(5, 3) + (2 ^ 3)"), PORTS)
        self.assertEqual(p.run(0), [16])
        self.assertEqual(Program(spec("return 0 < n < 16 and not (n == 3)"), PORTS).run(3), [0])
        self.assertEqual(Program(spec("return abs(-n) if n else max(1, min(2, 3))"), PORTS).run(0), [2])

    def test_reject_host_access_and_invalid_syntax_before_any_execution(self):
        for source in ("import os\nreturn 0", "return n.real", "return __import__('os')", "return [n][0]",
                       "if False:\n    open('x')\nreturn 0", "return (lambda: 0)()", "return 1.5", "return 'x'",
                       "def f():\n    return 0\nreturn 0", "for i in [1,2]:\n    c = i\nreturn c",
                       "return n / 2", "return abs", "while True:\n    break\nreturn 0", "n = 1\nreturn n",
                       "return missing", "a = b = 0\nreturn a", "return 1, 2", "c = 0",
                       "if n\n    return 1", "for i in range(1):\nreturn 0", "return n[0]"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                Program(spec(source), PORTS)

    def test_bounded_failures_include_input_and_source_location(self):
        cases = [(spec("while True:\n    c = 0\nreturn c", steps=100), "Anweisungsbudget"),
                 (spec(FOR, iterations=2), "Iterationsbudget"),
                 (spec("return 1 // 0"), "division"),
                 (spec("return 1 << 33"), "Schiebeweite"),
                 (spec("for i in range(0, n, 0):\n    c = i\nreturn c"), "Schritt"),
                 (spec("s = 2 ** 32\nreturn (s ** 5)"), "Ganzzahlergebnis")]
        for program, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, f"Eingabe x=15.*Zeile .*{message}"):
                Program(program, PORTS).run(15)
        with self.assertRaisesRegex(ValueError, "Gesamtbudget"):
            generate("total", 4, 8, ports=PORTS, program=spec("return n", total_steps=3))

    def test_cancellation_before_and_during_run(self):
        event = threading.Event(); event.set()
        with self.assertRaises(ProgramCancelled):
            generate("cancel", 4, 8, ports=PORTS, program=spec(FOR), cancel_event=event)
        class AfterTicks:
            calls = 0
            def is_set(self):
                self.calls += 1
                return self.calls > 20
        with self.assertRaises(ProgramCancelled):
            generate("cancel", 4, 8, ports=PORTS, program=spec(WHILE), cancel_event=AfterTicks())

    def test_limits_and_language_version_validation(self):
        for bad in ({"version": 2, "source": FOR}, {"version": True, "source": FOR}, spec(""),
                    spec("a" * 16001), spec(FOR, steps=0), spec(FOR, total_steps=5000001),
                    spec(FOR, steps=True), spec(FOR, unknown=7), {**spec(FOR), "extra": 2}):
            with self.subTest(bad=str(bad)[:100]), self.assertRaises(ValueError):
                Program(bad, PORTS)
        source = "\n".join(f"v{i} = 0" for i in range(65)) + "\nreturn 0"
        with self.assertRaisesRegex(ValueError, "64 lokale"):
            Program(spec(source), PORTS)
        source = "return " + "abs(" * 34 + "n" + ")" * 34
        with self.assertRaisesRegex(ValueError, "zu tief"):
            Program(spec(source), PORTS)

    def test_metadata_roundtrip_library_identity_and_legacy(self):
        ds = vectors(FOR)
        self.assertEqual(Dataset.from_dict(ds.to_dict()).to_dict(), ds.to_dict())
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as folder:
            library = Library(folder)
            key = library.save_dataset(ds)
            self.assertEqual(Library(folder).load_dataset(key).metadata, ds.metadata)
            sampled = vectors(FOR, samples=3, seed=8)
            sampled.metadata["program"]["limits"]["steps"] = 5000
            self.assertEqual(function_id(ds), function_id(sampled))
            self.assertNotEqual(function_id(ds), function_id(vectors(WHILE)))
            library.save_dataset(sampled)
            self.assertEqual(len({d["function_id"] for d in library.datasets()}), 1)
        bad = copy.deepcopy(ds.to_dict()); bad["metadata"]["expression"] = "n"
        with self.assertRaises(ValueError): Dataset.from_dict(bad)
        bad = copy.deepcopy(ds.to_dict()); del bad["metadata"]["interface"]
        with self.assertRaises(ValueError): Dataset.from_dict(bad)
        self.assertEqual(preset("xor").rows, [[0, 0, 0], [0, 1, 1], [1, 0, 1], [1, 1, 0]])

    def test_cli_actual_generation_and_failure_without_output_file(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as folder:
            folder = Path(folder)
            source, ports, out = folder / "sum.prim", folder / "ports.json", folder / "vectors.json"
            source.write_text(FOR, encoding="utf-8"); ports.write_text(json.dumps(PORTS), encoding="utf-8")
            args = [sys.executable, "-m", "primitives", "--data-dir", str(folder / "data"), "generate",
                    "--program-file", str(source), "--interface", str(ports), "--inputs", "4", "--outputs", "8", "--out", str(out)]
            result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            ds = Dataset.from_dict(json.loads(out.read_text(encoding="utf-8")))
            self.assertEqual(ds.rows, vectors(FOR).rows)
            previous = out.read_bytes()
            source.write_text("while True:\n    c = 0\nreturn c", encoding="utf-8")
            result = subprocess.run(args + ["--program-steps", "100"], cwd=ROOT, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(out.read_bytes(), previous)

    def test_archived_program_examples(self):
        from tools.export_programs import EXAMPLES
        directory = ROOT / "examples" / "programs"
        for key, (name, source) in EXAMPLES.items():
            path = directory / f"{key}.json"
            obj = json.loads(path.read_text(encoding="utf-8"))
            ds = Dataset.from_dict(obj)
            self.assertEqual(ds.name, name)
            self.assertEqual(ds.metadata["program"]["source"], source)
            self.assertEqual((directory / f"{key}.prim").read_text(encoding="utf-8"), source)
            actual = generate(ds.name, ds.inputs, ds.outputs, ports=ds.metadata["interface"], program=ds.metadata["program"])
            self.assertEqual(actual.to_dict(), obj)


if __name__ == "__main__":
    unittest.main()

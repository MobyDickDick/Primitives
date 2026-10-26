import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import unittest

from primitives.dataset import Dataset, generate, integer
from primitives.library import function_id
from primitives.program import Program, ProgramCancelled, template_source
from primitives.templates import Template


ROOT = Path(__file__).resolve().parents[1]
# Test the exact example offered by the UI, against independent integer addition.
ADDER = re.search(r'const recursiveAdderSource = `([^`]+)`;',
                  (ROOT / "web/app.js").read_text(encoding="utf-8")).group(1)
PORTS = {"inputs": [{"name": "a", "bits": "n"}, {"name": "b", "bits": "n"}],
         "outputs": [{"name": "c", "bits": "n+1"}]}


def template(n=4, source=ADDER, **limits):
    return {"version": 2, "parameters": {"n": n}, "interface": copy.deepcopy(PORTS),
            "source": source, "limits": limits,
            "conditions": ["n >= 1", "is_power_of_two(n)"] if source == ADDER else []}


def vectors(spec, samples=None):
    p = Program(spec)
    return generate("Template", sum(x["bits"] for x in p.ports["inputs"]),
                    sum(x["bits"] for x in p.ports["outputs"]),
                    ports=p.ports, program=p.spec, samples=samples)


class TemplateTests(unittest.TestCase):
    def test_angle_syntax_nested_calls_expressions_and_original_source_coordinates(self):
        source = ("# f<n>(a) bleibt ein Kommentar\n"
                  "def f(k, a):\n    return k + a\n"
                  "return 2 * f<n>(f<n-1>(a)) + f<1>(b) if a < b else f<0>(a) - 1")
        p = Program(template(4, source))
        self.assertEqual(p.run(2 | (3 << 4)), [22])
        self.assertEqual(p.run(3), [2])
        lowered = template_source(source)
        self.assertEqual(len(lowered), len(source))
        self.assertEqual(lowered.splitlines()[0], source.splitlines()[0])
        self.assertEqual([len(line) for line in lowered.splitlines()], [len(line) for line in source.splitlines()])
        self.assertEqual(p.spec["source"], source)
        source = "def f<k, q>(a):\n    return k + q + a\nreturn f<n, 2>(a)"
        self.assertEqual(Program(template(4, source)).run(3), [9])

    def test_recursive_adder_exhaustively_for_power_of_two_and_base_widths(self):
        for n in (1, 2, 4):
            ds = vectors(template(n), samples=1 << (2 * n))
            self.assertTrue(ds.exhaustive)
            for row in ds.rows:
                self.assertEqual(integer(row[2*n:]), integer(row[:n]) + integer(row[n:2*n]))
            self.assertEqual(ds.metadata["interface"]["outputs"][0]["bits"], n + 1)

    def test_bigger_legal_widths_and_rejection_of_nonpowers(self):
        for n in (8, 16):
            ds = vectors(template(n), samples=16)
            for row in ds.rows:
                self.assertEqual(integer(row[2*n:]), integer(row[:n]) + integer(row[n:2*n]))
        for n in (0, 3, 5, 6, 15):
            with self.subTest(n=n), self.assertRaisesRegex(ValueError, "Bedingung nicht erfüllt"):
                Program(template(n))
        spec = template(8, ADDER.replace("return add<n>(a, b)", "return add<6>(a, b)"))
        with self.assertRaisesRegex(ValueError, "Funktionsbedingung nicht erfüllt"):
            Program(spec).run(0)

    def test_parameters_roundtrip_specialization_identity_and_limits(self):
        p = template(2, "return a + b + (n - 2)")
        ds = vectors(p)
        restored = Dataset.from_dict(json.loads(json.dumps(ds.to_dict())))
        self.assertEqual(restored.to_dict(), ds.to_dict())
        self.assertEqual(restored.metadata["program"]["interface"], PORTS)
        changed = template(2, p["source"], steps=5000)
        self.assertEqual(function_id(ds), function_id(vectors(changed, samples=3)))
        # Same concrete ports and source but different fixed parameter changes identity.
        fixed = copy.deepcopy(p); fixed["interface"] = ds.metadata["interface"]
        ds1 = vectors(fixed)
        fixed["parameters"]["n"] = 3
        self.assertNotEqual(function_id(ds1), function_id(vectors(fixed)))
        broken = copy.deepcopy(ds.to_dict())
        broken["metadata"]["program"]["parameters"]["n"] = 3
        with self.assertRaisesRegex(ValueError, "Schnittstelle"):
            Dataset.from_dict(broken)

    def test_nested_functions_and_curried_calls_use_fresh_local_state(self):
        source = ("def twice(k, v):\n    t = v * 2\n    return t + k\n"
                  "def outer(k, v):\n    t = 7\n    return twice(k)(v) + t\n"
                  "return outer(n, a) + outer(0)(b)")
        p = Program(template(4, source))
        self.assertEqual([p.run(x) for x in (0, 1, 0)], [[18], [20], [18]])
        with self.assertRaisesRegex(ValueError, "unbekannte Variable a"):
            Program(template(source="def f(k):\n    return a\nreturn f(n)"))

    def test_depth_shared_step_iteration_total_budgets_and_cancellation(self):
        recursive = "def f(k):\n    return f(k)\nreturn f(n)"
        with self.assertRaisesRegex(ValueError, "Aufruftiefe"):
            Program(template(source=recursive)).run(0)
        with self.assertRaisesRegex(ValueError, "Anweisungsbudget"):
            Program(template(source=recursive, steps=10)).run(0)
        loop = "def f(k):\n    s = k\n    for i in range(10):\n        s += i\n    return s\nreturn f(a) + f(b)"
        with self.assertRaisesRegex(ValueError, "Iterationsbudget"):
            Program(template(source=loop, iterations=15)).run(0)
        with self.assertRaisesRegex(ValueError, "Gesamtbudget"):
            vectors(template(2, total_steps=50))
        event = threading.Event(); event.set()
        p = Program(template())
        with self.assertRaises(ProgramCancelled):
            p.run(0, p.budget(event))
        # Argument expressions cannot create an unbounded host recursion either.
        nested = "def f(k):\n    return f(f(k))\nreturn f(n)"
        with self.assertRaisesRegex(ValueError, "Aufruftiefe"):
            Program(template(source=nested)).run(0)

    def test_widths_and_function_syntax_rejected_before_execution(self):
        for n in (0, 17, True, -1, 33):
            with self.subTest(n=n), self.assertRaises(ValueError):
                Program(template(n))
        for width in ("n / 2", "abs(n)", "n.real", "2**32", "1//0", "missing", "-1", "0", "n + True", "2**100000"):
            spec = template(); spec["interface"]["inputs"][0]["bits"] = width
            with self.subTest(width=width), self.assertRaises(ValueError):
                Program(spec)
        for source in (
            "def f(k=1):\n    return k\nreturn f()",
            "def f(k):\n    return k\nreturn f(n, a)",
            "def f(k):\n    return k\nreturn f(k=n)",
            "def f(k):\n    return k\ndef f(k):\n    return k\nreturn 0",
            "def f(k):\n    return k\nreturn f",
            "def f(k):\n    def g(v):\n        return v\n    return k\nreturn 0",
            "def f(k):\n    return k, k\nreturn 0",
            "def f(k):\n    return open(k)\nreturn 0",
            "n = 1\nreturn a + b",
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                Program(template(source=source))

    def test_debugger_runs_calls_atomically_and_keeps_the_same_budget(self):
        p = Program(template(4))
        budget = p.budget()
        expected = p.run(63, budget)
        execution = p.debug(63)
        while execution.status not in ("done", "failed"):
            snapshot = execution.step()
        self.assertEqual(snapshot["status"], "done", snapshot)
        self.assertEqual(snapshot["result"], [str(v) for v in expected])
        self.assertEqual(snapshot["steps"], budget.steps)
        self.assertEqual(snapshot["variables"]["n"], "4")

    def test_abstract_template_has_no_values_and_instantiates_independently(self):
        instance = template()
        abstract = Template({"schema": 1, "kind": "template", "name": "Addition",
                             "parameters": ["n"], **{k: instance[k] for k in ("source", "interface", "limits", "conditions")}})
        self.assertEqual(abstract.to_dict()["parameters"], ["n"])
        self.assertEqual(abstract.instantiate({"n": 8}).ports["inputs"][0]["bits"], 8)
        self.assertEqual(abstract.instantiate({"n": 2}).run(15), [6])
        with self.assertRaisesRegex(ValueError, "Bedingung nicht erfüllt"):
            abstract.instantiate({"n": 6})
        for values in ({}, {"n": 2, "m": 1}, {"n": True}):
            with self.assertRaises(ValueError):
                abstract.instantiate(values)

    def test_conditions_are_bounded_and_checked_at_import_and_debug(self):
        for expression in ("open(n)", "n.real", "is_power_of_two(n, n)", "n == missing", "[n]", "1/2"):
            spec = template(); spec["conditions"] = [expression]
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                Program(spec)
        for expression in ("1 // 0", "2**1000000", "(2**32)**32"):
            spec = template(); spec["conditions"] = [expression]
            with self.assertRaises(ValueError):
                Program(spec)
        spec = template(); spec["conditions"] = ["n == 4 or 1 // 0"]
        Program(spec)  # conditions short-circuit
        ds = vectors(template(2))
        broken = copy.deepcopy(ds.to_dict())
        broken["metadata"]["program"]["conditions"] = ["n > 4"]
        with self.assertRaisesRegex(ValueError, "Bedingung nicht erfüllt"):
            Dataset.from_dict(broken)

    def test_portable_examples_and_cli_concretization(self):
        folder = ROOT / "examples" / "templates"
        abstract = Template(json.loads((folder / "recursive-adder.abstract.json").read_text(encoding="utf-8")))
        self.assertEqual(abstract.document["source"], ADDER)
        self.assertEqual((folder / "recursive-adder.prim").read_text(encoding="utf-8").strip(), ADDER.strip())
        stored = Dataset.from_dict(json.loads((folder / "recursive-adder-n4.json").read_text(encoding="utf-8")))
        self.assertEqual(stored.to_dict(), vectors(template(4), samples=256).to_dict() | {"name": stored.name})
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as tmp:
            out = Path(tmp) / "vectors.json"
            command = [sys.executable, "-m", "primitives", "generate", "--template-file",
                       str(folder / "recursive-adder.abstract.json"), "--parameters", '{"n":8}',
                       "--samples", "8", "--out", str(out)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            generated = Dataset.from_dict(json.loads(out.read_text(encoding="utf-8")))
            self.assertEqual((generated.inputs, generated.outputs), (16, 9))
            before = out.read_bytes()
            command[command.index('{"n":8}')] = '{"n":6}'
            result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(out.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

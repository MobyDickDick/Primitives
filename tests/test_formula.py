import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from primitives.dataset import Dataset, Expression, generate, integer
from primitives.formula import parse_formula, python_expressions, to_formula
from primitives.library import Library, function_id
from primitives.runner import ROOT


PORTS = {"inputs": [{"name": "a", "bits": 4}, {"name": "b", "bits": 4}],
         "outputs": [{"name": "c", "bits": 4}, {"name": "e", "bits": 1}]}
SOURCE = "c = mod(a+b,2^4), e = div(a+b,2^4)"


class FormulaTests(unittest.TestCase):
    def test_sum_and_carry_over_all_256_inputs(self):
        ds = generate("own addition", 8, 5, None, 256, ports=PORTS, formula=SOURCE)
        self.assertTrue(ds.exhaustive)
        for row in ds.rows:
            total = integer(row[:4]) + integer(row[4:8])
            self.assertEqual(integer(row[8:12]), total % 16)
            self.assertEqual(row[12], total // 16)
        self.assertEqual(ds.metadata["formula"], {"version": 1, "source": SOURCE})
        self.assertEqual(Dataset.from_dict(json.loads(json.dumps(ds.to_dict()))).to_dict(), ds.to_dict())

    def test_plain_expression_and_free_result_names(self):
        ports = {"inputs": PORTS["inputs"], "outputs": [{"name": "sum", "bits": 5}]}
        for source in ("a + b", "sum = a + b"):
            ds = generate("sum", 8, 5, None, 256, ports=ports, formula=source)
            for row in ds.rows:
                self.assertEqual(integer(row[8:]), integer(row[:4]) + integer(row[4:8]))
        self.assertEqual(parse_formula("c=mod(a+b,2^4); e=div(a+b,2^4)"), parse_formula(SOURCE))
        self.assertEqual(parse_formula("c=mod(a+b,2^4)\ne=div(a+b,2^4)"), parse_formula(SOURCE))

    def test_power_precedence_and_existing_xor_stay_distinct(self):
        self.assertEqual(Expression("2^4*3", syntax="math")({}), 48)
        self.assertEqual(Expression("2^3^2", syntax="math")({}), 512)
        self.assertEqual(Expression("-2^2", syntax="math")({}), -4)
        self.assertEqual(Expression("2^4")({}), 6)
        self.assertEqual(Expression("xor(9,5)", syntax="math")({}), 12)
        ports = {"inputs": [{"name": "a", "bits": 2}], "outputs": [{"name": "c", "bits": 2, "overflow": "wrap"}]}
        math = generate("math", 2, 2, None, ports=ports, formula="a^2")
        old = generate("old", 2, 2, {"c": "a^2"}, ports=ports)
        self.assertNotEqual(function_id(math), function_id(old))
        self.assertNotEqual(math.rows, old.rows)

    def test_div_mod_signed_and_zero_errors(self):
        self.assertEqual(Expression("div(-7,4)", syntax="math")({}), -2)
        self.assertEqual(Expression("mod(-7,4)", syntax="math")({}), 1)
        for source in ("mod(a,0)", "div(a,0)", "a^33", "sqrt(-1)"):
            with self.assertRaises(ValueError):
                generate("bad", 8, 5, None, ports={"inputs": PORTS["inputs"], "outputs": [{"name": "c", "bits": 5}]}, formula=source)

    def test_invalid_formulas_and_metadata_fail_without_host_execution(self):
        for source in ("", "c=a; c=b", "c=a; b+1", "c=d=a", "if a: c=1", "c=mod(a,b", "import os", "a" * 4001):
            with self.subTest(source=source), self.assertRaises(ValueError): parse_formula(source)
        for source in ("c=__import__('os'); e=0", "c=a.real; e=0", "c=[a]; e=0", "c=unknown; e=0", "c=a; e=c", "c=0 if a else missing; e=0"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                generate("bad", 8, 5, None, ports=PORTS, formula=source)
        with self.assertRaises(ValueError): generate("bad", 8, 5, None, ports=PORTS, formula="a+b")
        with self.assertRaises(ValueError): generate("bad", 2, 1, None, formula="a+b")
        obj = generate("good", 8, 5, None, ports=PORTS, formula=SOURCE).to_dict()
        bad = copy.deepcopy(obj); bad["metadata"]["formula"]["source"] = "c=a; e=0"
        with self.assertRaises(ValueError): Dataset.from_dict(bad)
        bad = copy.deepcopy(obj); bad["metadata"]["formula"]["version"] = 2
        with self.assertRaises(ValueError): Dataset.from_dict(bad)

    def test_operation_conversion_preserves_python_xor_and_power(self):
        converted = to_formula({"c": "a^b", "e": "(a+b)//16", "power": "2**4"})
        expressions = parse_formula(converted)
        self.assertIn("xor(a, b)", converted)
        for a in range(4):
            for b in range(4):
                self.assertEqual(Expression(expressions["c"], syntax="math")({"a": a, "b": b}), a ^ b)
                self.assertEqual(Expression(expressions["power"], syntax="math")({}), 16)
        converted_back = python_expressions(SOURCE)
        for a in range(16):
            for b in range(16):
                self.assertEqual(Expression(converted_back["c"])({"a": a, "b": b}), (a+b) % 16)
                self.assertEqual(Expression(converted_back["e"])({"a": a, "b": b}), (a+b) // 16)

    def test_roundtrip_library_and_cli(self):
        (ROOT / ".jobs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as tmp:
            ds = generate("formula", 8, 5, None, ports=PORTS, formula=SOURCE)
            library = Library(tmp)
            key = library.save_dataset(ds)
            self.assertEqual(library.load_dataset(key).to_dict(), ds.to_dict())
            self.assertEqual(library.datasets()[0]["metadata"]["formula"]["source"], SOURCE)
            spec, source, output = [Path(tmp) / name for name in ("ports.json", "formula.txt", "out.json")]
            spec.write_text(json.dumps(PORTS), encoding="utf-8")
            source.write_text(SOURCE, encoding="utf-8")
            for args in (["--formula", SOURCE], ["--formula-file", str(source)]):
                cli = subprocess.run([sys.executable, "-m", "primitives", "--data-dir", tmp, "generate",
                    "--interface", str(spec), "--inputs", "8", "--outputs", "5", *args, "--out", str(output)],
                    cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(cli.returncode, 0, cli.stderr)
                self.assertEqual(Dataset.from_dict(json.loads(output.read_text(encoding="utf-8"))).rows, ds.rows)


if __name__ == "__main__":
    unittest.main()

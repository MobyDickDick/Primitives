import json
from pathlib import Path
import random
import unittest

from primitives.dataset import bits, integer
from primitives.synthesis import synthesize
from primitives.templates import Template


ROOT = Path(__file__).resolve().parents[1]


def arithmetic(name):
    return Template(json.loads((ROOT / "examples/templates" / f"{name}.abstract.json").read_text(encoding="utf-8")))


def expected(name, a, b, n):
    if name == "ripple-add":
        return [a + b]
    if name == "ripple-sub":
        return [(a - b) % 2**n, int(a < b)]
    if name == "shift-add-mul":
        return [a * b]
    return [a // b, a % b, 1, 0] if b else [0, 0, 0, 1]


class SynthesisTests(unittest.TestCase):
    def test_all_four_templates_and_nand_networks_exhaustively(self):
        for name in ("ripple-add", "ripple-sub", "shift-add-mul", "restoring-div"):
            for n in (1, 2, 3, 4):
                with self.subTest(template=name, n=n):
                    program = arithmetic(name).instantiate({"n": n})
                    circuit = synthesize(program)
                    self.assertLessEqual(len(circuit.gates), 512)
                    for a in range(2**n):
                        for b in range(2**n):
                            x = a | b << n
                            reference = expected(name, a, b, n)
                            self.assertEqual(program.run(x), reference)
                            output = circuit.evaluate(bits(x, 2*n))
                            self.assertEqual([integer(output[p["offset"]:p["offset"]+p["bits"]])
                                              for p in program.ports["outputs"]], reference)

    def test_large_template_widths_and_gate_limit(self):
        rng = random.Random(71)
        for name, n in (("ripple-add", 16), ("ripple-sub", 16), ("shift-add-mul", 16), ("restoring-div", 15)):
            program = arithmetic(name).instantiate({"n": n})
            pairs = [(0, 0), (2**n-1, 1), (0, 2**n-1), (2**n-1, 2**n-1)]
            pairs += [(rng.randrange(2**n), rng.randrange(2**n)) for _ in range(20)]
            for a, b in pairs:
                self.assertEqual(program.run(a | b << n), expected(name, a, b, n))
            if name in ("ripple-add", "ripple-sub"):
                circuit = synthesize(program)
                for a, b in pairs:
                    outputs = circuit.evaluate(bits(a | b << n, 2*n))
                    self.assertEqual([integer(outputs[p["offset"]:p["offset"]+p["bits"]])
                                      for p in program.ports["outputs"]], expected(name, a, b, n))
            else:
                with self.assertRaisesRegex(ValueError, "512 Gattern"):
                    synthesize(program)

    def test_compiles_source_and_rejects_input_dependent_control_without_saving(self):
        document = arithmetic("ripple-add").to_dict()
        document["source"] = "x = bits(a, n)\ny = bits(b, n)\nreturn x[0] ^ y[0]"
        document["interface"]["outputs"] = [{"name": "c", "bits": 1}]
        circuit = synthesize(Template(document).instantiate({"n": 1}))
        self.assertEqual([circuit.evaluate(bits(x, 2)) for x in range(4)], [[0], [1], [1], [0]])
        for source in ("return a + b", "if a:\n    return 1\nreturn 0", "for i in range(a):\n    t = i\nreturn 0"):
            document["source"] = source
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "festen Parametern"):
                synthesize(Template(document).instantiate({"n": 1}))
        document["source"] = "while 1:\n    t = 0\nreturn 0"
        document["limits"]["steps"] = 10
        with self.assertRaisesRegex(ValueError, "Anweisungsbudget"):
            synthesize(Template(document).instantiate({"n": 1}))

    def test_constants_static_control_and_output_overflow(self):
        document = arithmetic("ripple-add").to_dict()
        for source, result in (("return 0", [0, 0]), ("return 3", [1, 1]),
                               ("if n == 1:\n    return 1\nreturn 0", [1, 0])):
            document["source"] = source
            circuit = synthesize(Template(document).instantiate({"n": 1}))
            for x in range(4):
                self.assertEqual(circuit.evaluate(bits(x, 2)), result)
        document["source"] = "return 4"
        with self.assertRaisesRegex(ValueError, "Portbreite"):
            synthesize(Template(document).instantiate({"n": 1}))


if __name__ == "__main__":
    unittest.main()

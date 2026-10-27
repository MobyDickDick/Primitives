"""Independent checks for generative logic, wiring and unsigned selection."""
import json
import random
import tempfile
import unittest

from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits
from primitives.examples import install_examples
from primitives.library import Library, fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_generative import KINDS, OUTPUT, TEMPLATES, bundle, definition, netlist


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def expected(kind, width, value):
    a = value % (2 ** width)
    b = (value // (2 ** width)) % (2 ** width)
    if kind == "parity":
        return sum(bits(a, width)) % 2
    if kind == "iszero":
        return int(not a)
    if kind == "reverse":
        return sum(bit << (width - i - 1) for i, bit in enumerate(bits(a, width)))
    if kind == "mux":
        return a if value < 2 ** (2 * width) else b
    if kind == "min":
        return a if a <= b else b
    return a if a >= b else b


class GenerativeTests(unittest.TestCase):
    def test_all_exported_forms_against_independent_oracles(self):
        for kind in KINDS:
            template = Template(definition(kind))
            self.assertEqual(read(TEMPLATES / f"recursive-{kind}.abstract.json"), template.to_dict())
            reports = read(OUTPUT / f"recursive-{kind}/verification.json")
            for width in (1, 2, 4):
                with self.subTest(kind=kind, width=width):
                    prefix = OUTPUT / f"recursive-{kind}/{kind}-{width}"
                    program = template.instantiate({"t": width})
                    hierarchy = BlockBundle(read(prefix.with_suffix(".block.json")))
                    expanded = hierarchy.expand()
                    circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                    compiled = synthesize(program)
                    dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                    self.assertEqual(hierarchy.to_dict(), bundle(kind, width).to_dict())
                    self.assertEqual(circuit, expanded.simplify())
                    self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                    self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"),
                                     netlist(circuit, program, f"{kind.upper()}<{width}>"))
                    self.assertEqual(len(dataset.rows), 1 << dataset.inputs)
                    checked = fitness(circuit, dataset)
                    self.assertTrue(checked["verified_truth_table"])
                    report = next(r for r in reports if r["parameters"]["t"] == width)
                    self.assertEqual(report["fitness"], checked)
                    self.assertEqual(report["hierarchy"], hierarchy.summary())
                    for value in range(1 << dataset.inputs):
                        result = expected(kind, width, value)
                        self.assertEqual(program.run(value), [result])
                        for impl in (hierarchy, expanded, circuit, compiled):
                            self.assertEqual(impl.evaluate(bits(value, dataset.inputs)), bits(result, dataset.outputs))
                    if kind == "reverse":
                        self.assertEqual(len(circuit.gates), 0)
                    if width > 1:
                        children = [n for n in hierarchy.view()["circuit"]["view_nodes"] if n["kind"] == "instance"]
                        names = [n["name"] for n in children]
                        self.assertEqual(names[:2], ([f"GT<{width}>", f"MUX<{width}>"] if kind in ("min", "max")
                                                     else [f"{kind.upper()}<{width // 2}>"] * 2))

    def test_larger_widths_boundaries_and_random_inputs(self):
        rng = random.Random(20261027)
        for kind in KINDS:
            for width in (8, 16):
                with self.subTest(kind=kind, width=width):
                    program = Template(definition(kind)).instantiate({"t": width})
                    hierarchy, circuit = bundle(kind, width), synthesize(program)
                    n = sum(p["bits"] for p in program.ports["inputs"])
                    m = sum(p["bits"] for p in program.ports["outputs"])
                    mask = (1 << width) - 1
                    cases = {0, (1 << n) - 1, mask, mask << width if n > width else 1 << (width - 1)}
                    cases.update(rng.getrandbits(n) for _ in range(12))
                    if kind == "mux":
                        cases.update(v ^ (1 << (2 * width)) for v in list(cases))
                    for value in cases:
                        result = expected(kind, width, value)
                        self.assertEqual(program.run(value), [result])
                        for impl in (hierarchy, circuit):
                            self.assertEqual(impl.evaluate(bits(value, n)), bits(result, m))

    def test_parameter_constraints_and_direct_call_assertions(self):
        for kind in KINDS:
            for width in (0, 3, 6, 65, True):
                with self.subTest(kind=kind, width=width), self.assertRaises(ValueError):
                    Template(definition(kind)).instantiate({"t": width})
            document = definition(kind)
            args = "a, b, sel" if kind == "mux" else "a, b" if kind in ("min", "max") else "a"
            document["source"] = document["source"].rsplit("\nreturn ", 1)[0] + f"\nreturn {kind.upper()}<3>({args})\n"
            program = Template(document).instantiate({"t": 4})
            with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                program.run(0)
            with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                synthesize(program)
        with self.assertRaises(ValueError):
            Template(definition("mux")).instantiate({"t": 64})

    def test_upgrade_preserves_folders_moves_and_deletions(self):
        with tempfile.TemporaryDirectory(dir=".jobs") as folder:
            library = Library(folder)
            marker = library.root / "example-installations.json"
            previous = ("arithmetic", "recursive-checked", "recursive-mul", "number-of-ones",
                        "recursive-msb-div", "recursive-max-index", "recursive-equ", "recursive-gt")
            marker.write_text(json.dumps({f"{key}-v1": True for key in previous}), encoding="utf-8")
            organization = library._organization()
            organization["folders"].append({"id": "examples", "parent": None, "name": "Meine Beispiele", "description": "Erhalten"})
            library._write_organization(organization)
            install_examples(library)
            self.assertEqual(len(library.templates()), 6)
            self.assertEqual(len(library.datasets()), 18)
            self.assertEqual(len(library.blocks()), 18)
            self.assertEqual({d["name"] for d in library.datasets()},
                             {f"{kind.upper()}<{width}>" for kind in KINDS for width in (1, 2, 4)})
            self.assertTrue(all(p["fitness"]["verified_truth_table"] for p in library.programs()))
            self.assertEqual(next(f for f in library.tree()["folders"] if f["id"] == "examples")["description"], "Erhalten")
            chosen = next(d for d in library.datasets() if d["name"] == "MIN<4>")
            library.move_entry("function", chosen["function_id"], "functions")
            chosen = next(d for d in library.datasets() if d["name"] == "MAX<4>")
            library.delete_function(chosen["function_id"])
            next((library.root / "templates").glob("*.json")).unlink()
            next((library.root / "blocks").glob("*.json")).unlink()
            before = library.tree()
            install_examples(Library(folder))
            self.assertEqual(library.tree(), before)
            self.assertEqual(len(library.datasets()), 17)
            self.assertEqual(len(library.templates()), 5)
            self.assertEqual(len(library.blocks()), 17)


if __name__ == "__main__":
    unittest.main()

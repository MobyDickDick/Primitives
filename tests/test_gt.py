"""Verify recursive GreaterThan against independent unsigned integer comparison."""
import json
import random
import tempfile
import unittest

from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, integer
from primitives.examples import install_examples
from primitives.library import Library, fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_gt import OUTPUT, SOURCE, bundle, definition, netlist


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class GreaterThanTests(unittest.TestCase):
    def test_exported_representations_exhaustively(self):
        template = Template(definition())
        self.assertEqual(read(SOURCE.with_suffix(".abstract.json")), template.to_dict())
        reports = read(OUTPUT / "verification.json")
        for width in (1, 2, 4):
            with self.subTest(width=width):
                prefix = OUTPUT / f"gt-{width}"
                program = template.instantiate({"t": width})
                hierarchy = BlockBundle(read(prefix.with_suffix(".block.json")))
                expanded = hierarchy.expand()
                circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                compiled = synthesize(program)
                dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                self.assertEqual(hierarchy.to_dict(), bundle(width).to_dict())
                self.assertEqual(circuit, expanded.simplify())
                self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"), netlist(circuit, width))
                self.assertEqual([p["bits"] for p in program.ports["inputs"]], [width, width])
                self.assertEqual([p["bits"] for p in program.ports["outputs"]], [1])
                self.assertEqual(len(dataset.rows), 1 << (2 * width))
                checked = fitness(circuit, dataset)
                self.assertTrue(checked["verified_truth_table"])
                report = next(r for r in reports if r["parameters"]["t"] == width)
                self.assertEqual(report["fitness"], checked)
                self.assertEqual(report["hierarchy"], hierarchy.summary())
                for a in range(1 << width):
                    for b in range(1 << width):
                        expected = int(a > b)
                        value = a | b << width
                        self.assertEqual(program.run(value), [expected])
                        for implementation in (hierarchy, expanded, circuit, compiled):
                            self.assertEqual(integer(implementation.evaluate(bits(value, 2 * width))), expected)
                if width > 1:
                    children = [n for n in hierarchy.view()["circuit"]["view_nodes"] if n["kind"] == "instance"]
                    self.assertEqual([n["name"] for n in children],
                                     [f"GT<{width // 2}>", f"EQU<{width // 2}>", f"GT<{width // 2}>"])
                if width == 4:
                    children = [n for n in hierarchy.view(["upper"])["circuit"]["view_nodes"]
                                if n["kind"] == "instance"]
                    self.assertEqual([n["name"] for n in children], ["GT<1>", "EQU<1>", "GT<1>"])

    def test_larger_widths_and_most_significant_difference(self):
        rng = random.Random(27)
        template = Template(definition())
        for width in (8, 16, 32, 64):
            program = template.instantiate({"t": width})
            implementations = [synthesize(program)] if width <= 32 else []
            if width <= 16:
                hierarchy = bundle(width)
                implementations.extend((hierarchy, hierarchy.expand().simplify()))
            maximum = (1 << width) - 1
            cases = {(0, 0), (maximum, maximum), (0, maximum), (maximum, 0)}
            for a in (0, maximum, rng.getrandbits(width)):
                cases.add((a, a))
                for i in range(width):
                    cases.update(((a, a ^ (1 << i)), (a ^ (1 << i), a)))
            # A higher differing bit wins over every opposing lower bit.
            for i in range(width):
                prefix = rng.getrandbits(width - i - 1) << (i + 1)
                a, b = prefix | (1 << i), prefix | ((1 << i) - 1)
                cases.update(((a, b), (b, a)))
            for _ in range(20):
                a, b = rng.getrandbits(width), rng.getrandbits(width)
                cases.update(((a, a), (a, b), (b, a)))
            for a, b in cases:
                expected = int(a > b)
                value = a | b << width
                self.assertEqual(program.run(value), [expected], (width, a, b))
                for implementation in implementations:
                    self.assertEqual(integer(implementation.evaluate(bits(value, 2 * width))), expected, (width, a, b))

    def test_alias_and_hardware_limits(self):
        document = definition()
        document["source"] = document["source"].rsplit("\nreturn GT", 1)[0] + "\nreturn GreaterThan<t>(a, b)\n"
        program = Template(document).instantiate({"t": 4})
        circuit = synthesize(program)
        for a in range(16):
            for b in range(16):
                value = a | b << 4
                self.assertEqual(program.run(value), [int(a > b)])
                self.assertEqual(circuit.evaluate(bits(value, 8)), [int(a > b)])
        with self.assertRaisesRegex(ValueError, "512"):
            synthesize(Template(definition()).instantiate({"t": 64}))
        with self.assertRaisesRegex(ValueError, "512"):
            bundle(32)

    def test_invalid_widths_and_direct_call_guards(self):
        template = Template(definition())
        for width in (0, -1, 3, 6, 31, 128, True):
            with self.subTest(width=width), self.assertRaises(ValueError):
                template.instantiate({"t": width})
        for call in ("GT<0>(a, b)", "GT<3>(a, b)", "GreaterThan<3>(a, b)",
                     "Equal<0>(a, b)", "Equal<3>(a, b)", "Upper<1>(a)", "Lower<3>(a)"):
            document = definition()
            document["source"] = document["source"].rsplit("\nreturn GT", 1)[0] + f"\nreturn {call}\n"
            program = Template(document).instantiate({"t": 4})
            with self.subTest(call=call):
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    program.run(0)
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    synthesize(program)

    def test_library_upgrade_preserves_edits_and_deletions(self):
        with tempfile.TemporaryDirectory(dir=".jobs") as folder:
            library = Library(folder)
            marker = library.root / "example-installations.json"
            marker.write_text(json.dumps({"arithmetic-v1": True, "generative-logic-v1": True, "recursive-checked-v1": True,
                                          "recursive-mul-v1": True, "number-of-ones-v1": True,
                                          "recursive-msb-div-v1": True, "recursive-max-index-v1": True,
                                          "recursive-equ-v1": True}), encoding="utf-8")
            organization = library._organization()
            organization["folders"].append({"id": "examples", "parent": None,
                                             "name": "Meine Beispiele", "description": "Erhalten"})
            library._write_organization(organization)
            install_examples(library)
            self.assertEqual(len(library.templates()), 1)
            self.assertEqual(len(library.blocks()), 3)
            self.assertEqual({p["dataset_name"] for p in library.programs()}, {"GT<1>", "GT<2>", "GT<4>"})
            self.assertTrue(all(p["fitness"]["verified_truth_table"] for p in library.programs()))
            self.assertTrue(all(f == "recursion" for f in library.tree()["entries"].values()))
            self.assertEqual(next(f for f in library.tree()["folders"] if f["id"] == "examples")["description"], "Erhalten")
            library.move_entry("function", library.datasets()[0]["function_id"], "functions")
            library.delete_function(library.datasets()[1]["function_id"])
            next((library.root / "templates").glob("*.json")).unlink()
            next((library.root / "blocks").glob("*.json")).unlink()
            before = library.tree()
            install_examples(Library(folder))
            self.assertEqual(library.tree(), before)
            self.assertEqual(len(library.programs()), 2)
            self.assertEqual(len(library.blocks()), 2)
            self.assertEqual(len(library.templates()), 0)


if __name__ == "__main__":
    unittest.main()

"""Verify the recursive highest-set-bit index against independent integers."""
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
from tools.export_max_index import OUTPUT, SOURCE, bundle, definition, netlist


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class MaxIndexTests(unittest.TestCase):
    def test_exported_representations_exhaustively(self):
        template = Template(definition())
        self.assertEqual(read(SOURCE.with_suffix(".abstract.json")), template.to_dict())
        reports = read(OUTPUT / "verification.json")
        for width in (1, 2, 4):
            with self.subTest(width=width):
                prefix = OUTPUT / f"m-{width}"
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
                self.assertEqual([p["bits"] for p in program.ports["outputs"]], [width, 1])
                self.assertEqual(len(dataset.rows), 1 << width)
                checked = fitness(circuit, dataset)
                self.assertTrue(checked["verified_truth_table"])
                report = next(r for r in reports if r["parameters"]["t"] == width)
                self.assertEqual(report["fitness"], checked)
                self.assertEqual(report["hierarchy"], hierarchy.summary())
                for a in range(1 << width):
                    expected = [a.bit_length() - 1, 0] if a else [0, 1]
                    self.assertEqual(program.run(a), expected)
                    for implementation in (hierarchy, expanded, circuit, compiled):
                        result = implementation.evaluate(bits(a, width))
                        self.assertEqual([integer(result[:width]), result[width]], expected)
                if width > 1:
                    children = [n for n in hierarchy.view()["circuit"]["view_nodes"] if n["kind"] == "instance"]
                    self.assertEqual([n["name"] for n in children], [f"m<{width // 2}>"] * 2)
                if width == 4:
                    grandchildren = [n for n in hierarchy.view(["upper"])["circuit"]["view_nodes"]
                                     if n["kind"] == "instance"]
                    self.assertEqual([n["name"] for n in grandchildren], ["m<1>"] * 2)

    def test_larger_widths_boundaries_and_padding(self):
        rng = random.Random(27)
        for width in (8, 16):
            program = Template(definition()).instantiate({"t": width})
            implementations = (synthesize(program), bundle(width))
            cases = set(range(256)) if width == 8 else {0, (1 << width) - 1}
            for i in range(width):
                cases.update((1 << i, (1 << i) - 1))
            cases.update(rng.getrandbits(width) for _ in range(20))
            for a in cases:
                expected = [a.bit_length() - 1, 0] if a else [0, 1]
                self.assertEqual(program.run(a), expected, (width, a))
                for implementation in implementations:
                    result = implementation.evaluate(bits(a, width))
                    self.assertEqual([integer(result[:width]), result[width]], expected, (width, a))
                    self.assertFalse(any(result[width.bit_length() - 1:width]))

    def test_invalid_widths(self):
        template = Template(definition())
        for width in (0, -1, 3, 6, 31, 32, 64, True):
            with self.subTest(width=width), self.assertRaises(ValueError):
                template.instantiate({"t": width})
        for width in (0, 3):
            document = definition()
            document["source"] = document["source"].rsplit("\nresult = bits(m<t>", 1)[0] + f"\nreturn m<{width}>(a), 0\n"
            program = Template(document).instantiate({"t": 4})
            with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                program.run(0)
            with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                synthesize(program)

    def test_library_upgrade_preserves_organization_and_deletions(self):
        with tempfile.TemporaryDirectory(dir=".jobs") as folder:
            library = Library(folder)
            marker = library.root / "example-installations.json"
            marker.write_text(json.dumps({"arithmetic-v1": True, "recursive-gt-v1": True, "recursive-equ-v1": True, "recursive-checked-v1": True,
                                          "recursive-mul-v1": True, "number-of-ones-v1": True,
                                          "recursive-msb-div-v1": True}), encoding="utf-8")
            organization = library._organization()
            organization["folders"].append({"id": "examples", "parent": None,
                                             "name": "Meine Beispiele", "description": "Erhalten"})
            library._write_organization(organization)
            install_examples(library)
            self.assertEqual(len(library.templates()), 1)
            self.assertEqual(len(library.blocks()), 3)
            self.assertEqual({p["dataset_name"] for p in library.programs()}, {"m<1>", "m<2>", "m<4>"})
            self.assertTrue(all(p["fitness"]["verified_truth_table"] for p in library.programs()))
            self.assertEqual(next(f for f in library.tree()["folders"] if f["id"] == "examples")["description"],
                             "Erhalten")
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

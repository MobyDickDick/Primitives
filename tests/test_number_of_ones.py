"""Check recursive population counts and every exported representation."""
import copy
import json
import random
import tempfile
import unittest

from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, integer
from primitives.examples import install_examples
from primitives.library import Library, fitness
from primitives.program import exact_log2
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_number_of_ones import OUTPUT, SOURCE, adder_program, bundle, definition, netlist


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class NumberOfOnesTests(unittest.TestCase):
    def test_all_exported_representations_exhaustively(self):
        template = Template(definition())
        self.assertEqual(read(SOURCE.with_suffix(".abstract.json")), template.to_dict())
        reports = read(OUTPUT / "verification.json")
        for width in (1, 2, 4):
            with self.subTest(width=width):
                prefix = OUTPUT / f"number-of-ones-{width}"
                program = template.instantiate({"w": width})
                hierarchy = BlockBundle(read(prefix.with_suffix(".block.json")))
                expanded = hierarchy.expand()
                circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                compiled = synthesize(program)
                dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                self.assertEqual(hierarchy.to_dict(), bundle(width).to_dict())
                self.assertEqual(circuit, expanded.simplify())
                self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"), netlist(circuit, width))
                self.assertEqual(program.ports["outputs"][0]["bits"], width.bit_length())
                self.assertEqual(len(dataset.rows), 1 << width)
                checked = fitness(circuit, dataset)
                self.assertTrue(checked["verified_truth_table"])
                report = next(r for r in reports if r["parameters"]["w"] == width)
                self.assertEqual(report["fitness"], checked)
                self.assertEqual(report["hierarchy"], hierarchy.summary())
                for a in range(1 << width):
                    expected = a.bit_count()
                    self.assertEqual(program.run(a), [expected])
                    for implementation in (hierarchy, expanded, circuit, compiled):
                        self.assertEqual(integer(implementation.evaluate(bits(a, width))), expected)
                if width == 1:
                    self.assertEqual(circuit, Circuit(1, (), (0,)))
                else:
                    children = [n for n in hierarchy.view()["circuit"]["view_nodes"] if n["kind"] == "instance"]
                    self.assertEqual([n["name"] for n in children],
                                     [f"NumberOfOnes<{width // 2}>"] * 2 + [f"ADD_count<{width.bit_length() - 1}>"])
                if width == 4:
                    grandchildren = [n for n in hierarchy.view(["lower"])["circuit"]["view_nodes"]
                                     if n["kind"] == "instance"]
                    self.assertEqual([n["name"] for n in grandchildren],
                                     ["NumberOfOnes<1>", "NumberOfOnes<1>", "ADD_count<1>"])

    def test_larger_widths_and_non_power_of_two_adder_width(self):
        rng = random.Random(26)
        for width in (8, 16, 32):
            program = Template(definition()).instantiate({"w": width})
            compiled = synthesize(program)
            hierarchy = bundle(width)
            cases = list(range(256)) if width == 8 else [0, (1 << width) - 1, 1 << (width - 1),
                                                        (1 << (width // 2)) - 1]
            cases += [rng.getrandbits(width) for _ in range(12)]
            for a in cases:
                expected = a.bit_count()
                self.assertEqual(program.run(a), [expected], (width, a))
                for implementation in (compiled, hierarchy):
                    self.assertEqual(integer(implementation.evaluate(bits(a, width))), expected, (width, a))
        # w=8 needs ADD_count<3>; w=32 needs ADD_count<5>.
        for width in (3, 5):
            program = adder_program(width)
            compiled = synthesize(program)
            maximum = (1 << width) - 1
            for a in range(1 << width):
                for b in range(1 << width):
                    self.assertEqual(program.run(a | b << width), [a + b])
                    self.assertEqual(integer(compiled.evaluate(bits(a | b << width, 2 * width))), a + b)
            self.assertEqual(program.run(maximum | maximum << width), [2 * maximum])

    def test_width_validation_and_log2_grammar(self):
        document = definition()
        for width in (0, 3, 6, 31, 64, True):
            with self.assertRaises(ValueError):
                Template(document).instantiate({"w": width})
        for value in (0, -1, 3, True):
            with self.assertRaises(ValueError):
                exact_log2(value)
        for expression in ("LOG2(0)", "LOG2(3)", "LOG2(True)", "LOG2(w,w)",
                           "LOG2(w, extra=1)", "LOG2(w.real)", "LOG2(abs(w))", "is_power_of_two(w)"):
            bad = copy.deepcopy(document)
            bad["interface"]["outputs"][0]["bits"] = expression
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                Template(bad).instantiate({"w": 4})
        for width in (0, 3):
            bad = copy.deepcopy(document)
            bad["source"] = bad["source"].rsplit("\nreturn NumberOfOnes", 1)[0] + f"\nreturn NumberOfOnes<{width}>(a)\n"
            program = Template(bad).instantiate({"w": 4})
            with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                program.run(0)
            with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                synthesize(program)
        bad = copy.deepcopy(document)
        bad["source"] = "return LOG2(a)"
        program = Template(bad).instantiate({"w": 4})
        self.assertEqual(program.run(8), [3])
        with self.assertRaisesRegex(ValueError, "festen Parametern"):
            synthesize(program)

    def test_library_upgrade_installs_once_and_preserves_deletions(self):
        with tempfile.TemporaryDirectory(dir=".jobs") as folder:
            library = Library(folder)
            (library.root / "example-installations.json").write_text(json.dumps(
                {"arithmetic-v1": True, "routing-v1": True, "generative-logic-v1": True, "recursive-gt-v1": True, "recursive-equ-v1": True, "recursive-checked-v1": True, "recursive-mul-v1": True,
                 "recursive-msb-div-v1": True, "recursive-max-index-v1": True}), encoding="utf-8")
            install_examples(library)
            self.assertEqual(len(library.templates()), 1)
            self.assertEqual(len(library.blocks()), 3)
            self.assertEqual({p["dataset_name"] for p in library.programs()},
                             {"NumberOfOnes<1>", "NumberOfOnes<2>", "NumberOfOnes<4>"})
            self.assertTrue(all(p["fitness"]["verified_truth_table"] for p in library.programs()))
            self.assertTrue(all(f == "recursion" for f in library.tree()["entries"].values()))
            library.delete_function(library.datasets()[0]["function_id"])
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

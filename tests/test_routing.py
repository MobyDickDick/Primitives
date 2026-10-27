"""Independent channel-routing checks, exported artifacts and library upgrade."""
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
from tools.export_routing import (KINDS, OUTPUT, SELECTORS, TEMPLATES, WIDTHS,
                                  bundle, definition, directed_inputs, label, netlist)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def expected(kind, n, w, value):
    """Decode channels as lists; deliberately independent of the exporter oracle."""
    data_bits = n * (2 ** w) if kind == "multiplexer" else n
    inputs = bits(value, data_bits + w)
    selected = integer(inputs[data_bits:])
    if kind == "multiplexer":
        channels = [inputs[i:i + n] for i in range(0, data_bits, n)]
        return integer(channels[selected])
    channels = [[0] * n for _ in range(2 ** w)]
    channels[selected] = inputs[:n]
    return integer([bit for channel in channels for bit in channel])


class RoutingTests(unittest.TestCase):
    def test_all_exports_against_independent_channels(self):
        rng = random.Random(20261027)
        for kind in KINDS:
            template = Template(definition(kind))
            self.assertEqual(read(TEMPLATES / f"recursive-{kind}.abstract.json"), template.to_dict())
            reports = read(OUTPUT / f"recursive-{kind}/verification.json")
            self.assertEqual(len(reports), 9)
            for n in WIDTHS:
                for w in SELECTORS:
                    with self.subTest(kind=kind, n=n, w=w):
                        prefix = OUTPUT / f"recursive-{kind}/{kind}-{n}-{w}"
                        program = template.instantiate({"n": n, "w": w})
                        hierarchy = BlockBundle(read(prefix.with_suffix(".block.json")))
                        expanded = hierarchy.expand()
                        circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                        compiled = synthesize(program)
                        dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                        self.assertEqual(hierarchy.to_dict(), bundle(kind, n, w).to_dict())
                        self.assertEqual(circuit, expanded.simplify())
                        self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                        self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"),
                                         netlist(circuit, program, label(kind, n, w)))
                        report = next(r for r in reports if r["parameters"] == {"n": n, "w": w})
                        self.assertEqual(report["fitness"], fitness(circuit, dataset))
                        self.assertEqual(report["hierarchy"], hierarchy.summary())
                        self.assertEqual(dataset.exhaustive, dataset.inputs <= 12)
                        self.assertEqual(report["verification"]["exhaustive"], dataset.exhaustive)
                        self.assertEqual(report["fitness"]["verified_truth_table"], dataset.exhaustive)
                        cases = set(directed_inputs(kind, n, w))
                        for row in dataset.rows:
                            value = integer(row[:dataset.inputs])
                            cases.add(value)
                            self.assertEqual(integer(row[dataset.inputs:]), expected(kind, n, w, value))
                        self.assertEqual(len(cases), report["verification"]["independent_cases"])
                        cases.update(rng.getrandbits(dataset.inputs) for _ in range(32))
                        for value in sorted(cases):
                            result = expected(kind, n, w, value)
                            self.assertEqual(program.run(value), [result])
                            for implementation in (hierarchy, expanded, circuit, compiled):
                                self.assertEqual(implementation.evaluate(bits(value, dataset.inputs)),
                                                 bits(result, dataset.outputs))
                        if w > 1:
                            children = [node["name"] for node in hierarchy.view()["circuit"]["view_nodes"]
                                        if node["kind"] == "instance"]
                            self.assertEqual(children.count(label(kind, n, w - 1)), 3 if w == 2 else 2)
                            self.assertIn(label(kind, n, 1), children)

    def test_basic_meaning_and_channel_bit_order(self):
        mux = Template(definition("multiplexer")).instantiate({"n": 1, "w": 1})
        demux = Template(definition("demultiplexer")).instantiate({"n": 1, "w": 1})
        for a0 in (0, 1):
            for a1 in (0, 1):
                self.assertEqual(mux.run(a0 + 2 * a1), [a0])
                self.assertEqual(mux.run(a0 + 2 * a1 + 4), [a1])
        self.assertEqual(demux.run(1), [1])
        self.assertEqual(demux.run(3), [2])
        mux = Template(definition("multiplexer")).instantiate({"n": 2, "w": 2})
        channels = 0 + 1 * 4 + 2 * 16 + 3 * 64
        for selected in range(4):
            self.assertEqual(mux.run(channels | (selected << 8)), [selected])

    def test_other_legal_widths_and_boundaries(self):
        rng = random.Random(93218)
        for kind in KINDS:
            for n, w in ((3, 2), (1, 3), (1, 6), (7, 3)):
                with self.subTest(kind=kind, n=n, w=w):
                    program = Template(definition(kind)).instantiate({"n": n, "w": w})
                    circuit, hierarchy = synthesize(program), bundle(kind, n, w)
                    cases = {0, (1 << circuit.inputs) - 1}
                    cases.update(rng.getrandbits(circuit.inputs) for _ in range(12))
                    for value in cases:
                        result = expected(kind, n, w, value)
                        self.assertEqual(program.run(value), [result])
                        for impl in (circuit, hierarchy):
                            self.assertEqual(integer(impl.evaluate(bits(value, circuit.inputs))), result)
        # Exactly 128 demultiplexer output bits, without claiming a larger NAND budget.
        program = Template(definition("demultiplexer")).instantiate({"n": 1, "w": 7})
        self.assertEqual(program.run(1 | (127 << 1)), [1 << 127])
        with self.assertRaisesRegex(ValueError, "512"):
            synthesize(program)

    def test_parameter_conditions_and_direct_call_guards(self):
        for kind in KINDS:
            for n, w in ((0, 1), (1, 0), (1, 8), (65, 1), (True, 1), (1, True), (128, 128)):
                with self.subTest(kind=kind, n=n, w=w), self.assertRaises(ValueError):
                    Template(definition(kind)).instantiate({"n": n, "w": w})
            for n, w in ((0, 1), (1, 0), (1, 8), (65, 1)):
                document = definition(kind)
                function = "MUX" if kind == "multiplexer" else "DEMUX"
                document["source"] = document["source"].rsplit("\nreturn ", 1)[0] + f"\nreturn {function}<{n},{w}>(a, b)\n"
                program = Template(document).instantiate({"n": 1, "w": 1})
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    program.run(0)
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    synthesize(program)
        with self.assertRaises(ValueError):
            Template(definition("multiplexer")).instantiate({"n": 1, "w": 7})

    def test_library_upgrade_and_repeat_preserve_user_changes(self):
        with tempfile.TemporaryDirectory(dir=".jobs") as folder:
            library = Library(folder)
            marker = library.root / "example-installations.json"
            previous = ("arithmetic", "recursive-checked", "recursive-mul", "number-of-ones",
                        "recursive-msb-div", "recursive-max-index", "recursive-equ", "recursive-gt", "generative-logic")
            marker.write_text(json.dumps({f"{key}-v1": True for key in previous}), encoding="utf-8")
            organization = library._organization()
            organization["folders"].append({"id": "examples", "parent": None,
                                             "name": "Meine Beispiele", "description": "Erhalten"})
            library._write_organization(organization)
            install_examples(library)
            self.assertEqual(len(library.templates()), 2)
            self.assertEqual(len(library.datasets()), 18)
            self.assertEqual(len(library.blocks()), 18)
            self.assertTrue(all(p["fitness"]["exact_on_dataset"] for p in library.programs()))
            self.assertEqual(sum(p["fitness"]["verified_truth_table"] for p in library.programs()), 14)
            self.assertTrue(all(f == "routing" for f in library.tree()["entries"].values()))
            library.save_folder("Meine Schalter", "Eigene Beschreibung", "recursion", "routing")
            library.move_entry("function", library.datasets()[0]["function_id"], "functions")
            library.delete_function(library.datasets()[1]["function_id"])
            next((library.root / "templates").glob("*.json")).unlink()
            next((library.root / "blocks").glob("*.json")).unlink()
            before = library.tree()
            install_examples(Library(folder))
            self.assertEqual(library.tree(), before)
            self.assertEqual(len(library.datasets()), 17)
            self.assertEqual(len(library.templates()), 1)
            self.assertEqual(len(library.blocks()), 17)


if __name__ == "__main__":
    unittest.main()

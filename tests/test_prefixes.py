"""GEN-06: independent inclusive prefixes, exports, boundaries and upgrades."""
import json
from pathlib import Path
import random
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen

from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, integer
from primitives.examples import install_examples, install_prefix_examples
from primitives.library import Library, fitness
from primitives.server import make_server
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_generative import netlist
from tools.export_prefixes import KINDS, WIDTHS, ROOT, TEMPLATES, OUTPUT, bundle, definition
from tools.export_structured import definition as structured_definition


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def expected(kind, width, value):
    # Serial accumulation over individual bits, independent of recursive halves
    # and of the exporter's masked integer / population-count oracle.
    result = []
    accumulator = 1 if kind == "prefix_and" else 0
    for bit in bits(value, width):
        accumulator = accumulator & bit if kind == "prefix_and" else accumulator ^ bit
        result.append(accumulator)
    return result


class PrefixTests(unittest.TestCase):
    def test_all_exported_tables_and_hardware_forms(self):
        total = 0
        for kind in KINDS:
            template = Template(definition(kind))
            self.assertEqual(read(TEMPLATES / f"recursive-{kind}.abstract.json"), template.to_dict())
            reports = read(OUTPUT / f"recursive-{kind}/verification.json")
            self.assertEqual(len(reports), 3)
            for width in WIDTHS:
                with self.subTest(kind=kind, width=width):
                    name = f"{kind.upper()}<{width}>"
                    prefix = OUTPUT / f"recursive-{kind}/{kind}-{width}"
                    program = template.instantiate({"t": width})
                    hierarchy = BlockBundle(read(prefix.with_suffix(".block.json")))
                    expanded = hierarchy.expand()
                    circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                    compiled = synthesize(program)
                    dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                    self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                    self.assertEqual(hierarchy.to_dict(), bundle(kind, width).to_dict())
                    self.assertEqual(circuit, expanded.simplify())
                    self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"),
                                     netlist(circuit, program, name))
                    self.assertEqual([(p["name"], p["bits"]) for p in program.ports["inputs"]], [("a", width)])
                    self.assertEqual([(p["name"], p["bits"]) for p in program.ports["outputs"]], [("c", width)])
                    self.assertEqual(len(dataset.rows), 1 << width)
                    for row in dataset.rows:
                        value = integer(row[:width])
                        result = expected(kind, width, value)
                        self.assertEqual(row, bits(value, width) + result)
                        self.assertEqual(program.run(value), [integer(result)])
                        for impl in (hierarchy, expanded, circuit, compiled):
                            self.assertEqual(impl.evaluate(bits(value, width)), result)
                    report = next(r for r in reports if r["parameters"] == {"t": width})
                    self.assertEqual(report["fitness"], fitness(circuit, dataset))
                    self.assertTrue(report["fitness"]["verified_truth_table"])
                    self.assertEqual(report["hierarchy"], hierarchy.summary())
                    self.assertEqual(len(circuit.gates), (width * (width.bit_length() - 1)) *
                                     (1 if kind == "prefix_and" else 2))
                    total += len(dataset.rows)
        self.assertEqual(total, 44)

    def test_orientation_and_relationship_to_existing_templates(self):
        # Bit 0 propagates upwards here; UNGRAY propagates the highest bit downwards.
        prefix = Template(definition("prefix_xor")).instantiate({"t": 4})
        ungray = Template(structured_definition("ungray")).instantiate({"t": 4})
        self.assertEqual((prefix.run(1), ungray.run(1)), ([15], [1]))
        self.assertEqual((prefix.run(8), ungray.run(8)), ([8], [15]))
        for width in (1, 2, 4, 8):
            p_and = Template(definition("prefix_and")).instantiate({"t": width})
            p_xor = Template(definition("prefix_xor")).instantiate({"t": width})
            p_or = Template(structured_definition("prefix_or")).instantiate({"t": width})
            mask = (1 << width) - 1
            for value in range(1 << width):
                # De Morgan relates AND to the existing OR; adjacent prefix-XOR
                # outputs recover the original input, including the boundary bit.
                self.assertEqual(p_and.run(value)[0], mask ^ p_or.run(mask ^ value)[0])
                result = p_xor.run(value)[0]
                self.assertEqual((result ^ (result << 1)) & mask, value)

    def test_sampled_large_widths_and_hardware_boundaries(self):
        rng = random.Random(20261104)
        for kind in KINDS:
            for width in (8, 16, 32, 64, 128):
                program = Template(definition(kind)).instantiate({"t": width})
                hardware = [synthesize(program), bundle(kind, width)] if (
                    width <= (64 if kind == "prefix_and" else 32)) else []
                values = {0, 1, (1 << width) - 1, 1 << (width - 1), (1 << (width - 1)) - 1,
                          sum(1 << i for i in range(0, width, 2))}
                values.update(rng.getrandbits(width) for _ in range(8))
                # Every single zero / one checks all prefix positions and boundaries.
                values.update(1 << i for i in range(width))
                values.update(((1 << width) - 1) ^ (1 << i) for i in range(width))
                for value in values:
                    result = expected(kind, width, value)
                    self.assertEqual(program.run(value), [integer(result)], (kind, width, value))
                    for impl in hardware:
                        self.assertEqual(impl.evaluate(bits(value, width)), result)
        for kind, width in (("prefix_and", 128), ("prefix_xor", 64), ("prefix_xor", 128)):
            program = Template(definition(kind)).instantiate({"t": width})
            with self.assertRaisesRegex(ValueError, "512"):
                synthesize(program)
            with self.assertRaisesRegex(ValueError, "512"):
                bundle(kind, width)

    def test_parameter_and_direct_call_guards(self):
        for kind in KINDS:
            for width in (0, -1, 3, 127, 129, 256, True):
                with self.subTest(kind=kind, width=width), self.assertRaises(ValueError):
                    Template(definition(kind)).instantiate({"t": width})
            merge = "PrefixANDMerge" if kind == "prefix_and" else "PrefixXORMerge"
            for call in (f"{kind.upper()}<0>(a)", f"{kind.upper()}<3>(a)",
                         f"{kind.upper()}<256>(a)", f"{merge}<0>(a, a)", f"{merge}<65>(a, a)"):
                document = definition(kind)
                document["source"] = document["source"].split("# Ergebnisport", 1)[0] + f"return {call}\n"
                program = Template(document).instantiate({"t": 1})
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    program.run(0)
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    synthesize(program)

    def test_migration_keeps_user_data_and_deleted_examples(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            install_examples(library)
            self.assertFalse(any(t["name"].startswith(("PREFIX_AND<", "PREFIX_XOR<")) for t in library.templates()))
            library.save_folder("Meine Rekursion", "Eigener Text", "examples", "recursion")
            entries = library.tree()["entries"].copy()
            install_prefix_examples(library)
            self.assertTrue(read(Path(directory) / "example-installations.json")["prefixes-v1"])
            self.assertTrue(entries.items() <= library.tree()["entries"].items())
            folder = next(f for f in library.tree()["folders"] if f["id"] == "recursion")
            self.assertEqual((folder["name"], folder["description"]), ("Meine Rekursion", "Eigener Text"))
            new = [d for d in library.datasets() if d["name"].startswith(("PREFIX_AND<", "PREFIX_XOR<"))]
            self.assertEqual(len(new), 6)
            library.update_function(new[0]["function_id"], "Mein Präfix", "Meine Beschreibung")
            library.move_entry("function", new[0]["function_id"], "functions")
            library.delete_function(new[1]["function_id"])
            template = next(t for t in library.templates() if t["name"] == "PREFIX_AND<t>")
            (Path(directory) / "templates" / f"{template['id']}.json").unlink()
            block = next(b for b in library.blocks() if b["name"] == "PREFIX_XOR<4>")
            (Path(directory) / "blocks" / f"{block['id']}.json").unlink()
            before = {p: p.read_bytes() for p in Path(directory).rglob("*.json")}
            install_prefix_examples(Library(directory))
            self.assertEqual({p: p.read_bytes() for p in Path(directory).rglob("*.json")}, before)

    def test_upgrade_keeps_existing_solution_labels_and_assignments(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            prefix = OUTPUT / "recursive-prefix_and/prefix_and-4"
            dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
            # A serial AND chain needs only six NANDs, versus eight in this
            # parallel recursive export. The migration must retain the winner.
            circuit = Circuit(4, ((0, 1), (4, 4), (5, 2), (6, 6), (7, 3), (8, 8)), (0, 5, 7, 9))
            self.assertTrue(fitness(circuit, dataset)["verified_truth_table"])
            saved = library.save_program({"circuit": circuit.to_dict(), "note": "Eigene Lösung"}, dataset)
            key = library.datasets()[0]["function_id"]
            library.update_function(key, "Eigener Name", "Erhalten")
            library.move_entry("function", key, "functions")
            template_key = library.save_template(Template(definition("prefix_and")))
            library.move_entry("template", template_key, "templates")
            install_prefix_examples(library)
            self.assertEqual(library.load_program(saved["id"])["note"], "Eigene Lösung")
            self.assertEqual(next(p for p in library.programs() if p["dataset_name"] == "Eigener Name")["id"], saved["id"])
            self.assertEqual(library.tree()["entries"][f"function:{key}"], "functions")
            self.assertEqual(library.tree()["entries"][f"template:{template_key}"], "templates")
            self.assertEqual(next(d for d in library.datasets() if d["function_id"] == key)["name"], "Eigener Name")
            self.assertEqual((len(library.templates()), len(library.datasets()), len(library.blocks())), (2, 6, 6))

    def test_server_upgrade_catalog_synthesis_and_nested_navigation(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            previous = ("arithmetic", "recursive-checked", "recursive-mul", "number-of-ones",
                        "recursive-msb-div", "recursive-max-index", "recursive-equ", "recursive-gt",
                        "generative-logic", "routing", "structured-logic", "standard-arithmetic",
                        "arithmetic-comments", "zero-counts", "priority-encoder", "onehot", "barrel-shifter", "rotations")
            (Path(directory) / "example-installations.json").write_text(
                json.dumps({f"{key}-v1": True for key in previous}), encoding="utf-8")
            server = make_server(0, directory, background=False)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"

            def request(path, data=None):
                req = Request(base + path, data=json.dumps(data).encode() if data is not None else None,
                              headers={"Content-Type": "application/json"})
                with urlopen(req, timeout=30) as response:
                    return json.load(response)

            try:
                catalog = request("/api/catalog")
                self.assertEqual((len(catalog["templates"]), len(catalog["datasets"]), len(catalog["blocks"])), (2, 6, 6))
                for kind in KINDS:
                    template = next(t for t in catalog["templates"] if t["name"] == f"{kind.upper()}<t>")
                    saved = request("/api/templates/synthesize", {
                        "template_id": template["id"], "parameters": {"t": 4}, "samples": 16, "name": f"{kind} HTTP"})
                    self.assertTrue(saved["result"]["fitness"]["verified_truth_table"])
                    block = next(b for b in catalog["blocks"] if b["name"] == f"{kind.upper()}<4>")
                    for value in range(16):
                        evaluation = request("/api/blocks/evaluate", {"block_id": block["id"], "bits": bits(value, 4)})
                        self.assertEqual(evaluation["outputs"], expected(kind, 4, value))
                    view = request("/api/blocks/view", {"block_id": block["id"], "path": ["upper"]})
                    self.assertEqual(sum(n["kind"] == "instance" for n in view["circuit"]["view_nodes"]), 3)
                    view = request("/api/blocks/view", {"block_id": block["id"], "path": ["upper", "prefix"]})
                    self.assertGreater(len(view["circuit"]["gates"]), 0)
            finally:
                server.shutdown()
                server.server_close()
                server.executor.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

"""GEN-01: independent zero-count oracles, hardware forms and migration."""
import json
from pathlib import Path
import random
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen

from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits
from primitives.examples import install_examples, install_zero_count_examples
from primitives.library import Library, fitness
from primitives.server import make_server
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_generative import netlist
from tools.export_zero_counts import KINDS, OUTPUT, ROOT, TEMPLATES, bundle, definition, merge_program


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def expected(kind, width, value):
    # Scan a formatted word, independently of recursive halves and integer bit_length.
    word = f"{value:0{width}b}"
    ordered = word if kind == "clz" else word[::-1]
    return len(ordered) - len(ordered.lstrip("0"))


class ZeroCountTests(unittest.TestCase):
    def test_all_exported_forms_exhaustively(self):
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
                    self.assertEqual([p["bits"] for p in program.ports["inputs"]], [width])
                    self.assertEqual([p["bits"] for p in program.ports["outputs"]], [width.bit_length()])
                    self.assertEqual(len(dataset.rows), 1 << width)
                    checked = fitness(circuit, dataset)
                    self.assertTrue(checked["verified_truth_table"])
                    report = next(r for r in reports if r["parameters"]["t"] == width)
                    self.assertEqual(report["fitness"], checked)
                    self.assertEqual(report["hierarchy"], hierarchy.summary())
                    for row in dataset.rows:
                        value = sum(bit << i for i, bit in enumerate(row[:width]))
                        result = expected(kind, width, value)
                        self.assertEqual(row[width:], bits(result, dataset.outputs))
                        self.assertEqual(program.run(value), [result])
                        for impl in (hierarchy, expanded, circuit, compiled):
                            self.assertEqual(impl.evaluate(bits(value, width)), bits(result, dataset.outputs))
                    if width > 1:
                        children = [n["name"] for n in hierarchy.view()["circuit"]["view_nodes"]
                                    if n["kind"] == "instance"]
                        self.assertEqual(children, [f"{kind.upper()}<{width // 2}>"] * 2 +
                                         [f"ISZERO<{width // 2}>", f"CountMerge<{width // 2}>"])

    def test_larger_widths_single_bits_boundaries_and_samples(self):
        rng = random.Random(20261029)
        for width in (8, 16, 32, 64, 128):
            maximum = (1 << width) - 1
            cases = {0, maximum, 1, 1 << (width - 1)}
            indices = range(width) if width <= 32 else (0, 1, width // 2 - 1, width // 2, width - 2, width - 1)
            cases.update(1 << i for i in indices)
            cases.update(maximum ^ (1 << i) for i in indices)
            cases.update(rng.getrandbits(width) for _ in range(10))
            programs = {kind: Template(definition(kind)).instantiate({"t": width}) for kind in KINDS}
            circuits = {kind: [synthesize(programs[kind]), bundle(kind, width)] if width <= 32 else []
                        for kind in KINDS}
            for value in cases:
                reversed_value = int(f"{value:0{width}b}"[::-1], 2)
                self.assertEqual(programs["clz"].run(value), programs["ctz"].run(reversed_value))
                for kind in KINDS:
                    result = expected(kind, width, value)
                    self.assertEqual(programs[kind].run(value), [result], (kind, width, value))
                    for impl in circuits[kind]:
                        self.assertEqual(impl.evaluate(bits(value, width)), bits(result, width.bit_length()))

    def test_offset_addition_and_selection_including_all_zero_carry(self):
        for k in (1, 2, 4, 8):
            program = merge_program(k)
            circuit = synthesize(program)
            r = k.bit_length()
            for z in (0, 1):
                for first in range(k + z):
                    for second in range(k + 1):
                        value = first | second << r | z << (2 * r)
                        result = k + second if z else first
                        self.assertEqual(program.run(value), [result])
                        self.assertEqual(circuit.evaluate(bits(value, 2 * r + 1)), bits(result, r + 1))

    def test_parameter_guards_and_hardware_limits(self):
        for kind in KINDS:
            for width in (0, -1, 3, 6, 129, 256, True):
                with self.subTest(kind=kind, width=width), self.assertRaises(ValueError):
                    Template(definition(kind)).instantiate({"t": width})
            for call in (f"{kind.upper()}<3>(a)", f"{kind.upper()}<256>(a)",
                         "ISZERO<0>(a)", "CountMerge<3>(a, a, 1)"):
                document = definition(kind)
                document["source"] = document["source"].rsplit("\nreturn ", 1)[0] + f"\nreturn {call}\n"
                program = Template(document).instantiate({"t": 4})
                with self.subTest(kind=kind, call=call):
                    with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                        program.run(0)
                    with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                        synthesize(program)
            for width in (64, 128):
                program = Template(definition(kind)).instantiate({"t": width})
                with self.assertRaisesRegex(ValueError, "512"):
                    synthesize(program)
                with self.assertRaisesRegex(ValueError, "512"):
                    bundle(kind, width)

    def test_separate_migration_and_existing_library_edits_survive(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            # An older library's installation must not claim the new templates.
            install_examples(library)
            self.assertFalse(any(t["name"].startswith(("CLZ", "CTZ")) for t in library.templates()))
            library.save_folder("Meine Rekursion", "Eigener Text", "examples", "recursion")
            old_entries = library.tree()["entries"].copy()
            install_zero_count_examples(library)
            self.assertEqual({t["name"] for t in library.templates()} & {"CLZ<t>", "CTZ<t>"}, {"CLZ<t>", "CTZ<t>"})
            self.assertTrue(read(Path(directory) / "example-installations.json")["zero-counts-v1"])
            self.assertTrue(old_entries.items() <= library.tree()["entries"].items())
            self.assertEqual(next(f for f in library.tree()["folders"] if f["id"] == "recursion")["name"], "Meine Rekursion")
            new = [d for d in library.datasets() if d["name"].startswith(("CLZ", "CTZ"))]
            self.assertEqual(len(new), 6)
            self.assertTrue(all(p["fitness"]["verified_truth_table"] for p in library.programs()
                                if p["dataset_name"].startswith(("CLZ", "CTZ"))))
            key = new[0]["function_id"]
            library.update_function(key, "Mein Nullzähler", "Beschreibung")
            library.move_entry("function", key, "functions")
            library.delete_function(new[1]["function_id"])
            template = next(t for t in library.templates() if t["name"] == "CLZ<t>")
            (Path(directory) / "templates" / f"{template['id']}.json").unlink()
            block = next(b for b in library.blocks() if b["name"] == "CLZ<4>")
            (Path(directory) / "blocks" / f"{block['id']}.json").unlink()
            before = {p: p.read_bytes() for p in Path(directory).rglob("*.json")}
            install_zero_count_examples(Library(directory))
            self.assertEqual({p: p.read_bytes() for p in Path(directory).rglob("*.json")}, before)
            self.assertEqual(next(d for d in library.datasets() if d["function_id"] == key)["name"], "Mein Nullzähler")

    def test_fresh_migration_keeps_existing_better_solution(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            prefix = OUTPUT / "recursive-clz/clz-4"
            dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
            # A flatter Boolean implementation costs 17 NANDs versus the bundled 19.
            document = definition("clz")
            document["source"] = """x = bits(a, 4)
z = (1 ^ x[3]) & (1 ^ x[2])
l = x[1] | x[0]
c0 = ((1 ^ x[3]) & x[2]) | (z & (1 ^ x[1]) & x[0])
c1 = z & l
c2 = z & (1 ^ l)
return pack([c0, c1, c2])
"""
            circuit = synthesize(Template(document).instantiate({"t": 4}))
            self.assertTrue(fitness(circuit, dataset)["verified_truth_table"])
            self.assertLess(len(circuit.gates), len(read(prefix.with_suffix(".circuit.json"))["gates"]))
            saved = library.save_program({"circuit": circuit.to_dict(), "note": "Eigene beste Lösung"}, dataset)
            library.update_function(dataset_key := library.datasets()[0]["function_id"], "Eigener Name", "Erhalten")
            library.move_entry("function", dataset_key, "functions")
            install_zero_count_examples(library)
            self.assertEqual(library.load_program(saved["id"])["note"], "Eigene beste Lösung")
            self.assertEqual(library.tree()["entries"][f"function:{dataset_key}"], "functions")
            self.assertEqual(next(d for d in library.datasets() if d["function_id"] == dataset_key)["name"], "Eigener Name")
            self.assertEqual(len(library.templates()), 2)
            self.assertEqual(len(library.datasets()), 6)
            self.assertEqual(len(library.blocks()), 6)

    def test_server_upgrade_exposes_templates_and_direct_synthesis(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            # Older examples have already been installed, then removed by their owner.
            previous = ("arithmetic", "recursive-checked", "recursive-mul", "number-of-ones",
                        "recursive-msb-div", "recursive-max-index", "recursive-equ", "recursive-gt",
                        "generative-logic", "routing", "structured-logic", "standard-arithmetic",
                        "arithmetic-comments", "priority-encoder", "onehot")
            (Path(directory) / "example-installations.json").write_text(
                json.dumps({f"{key}-v1": True for key in previous}), encoding="utf-8")
            server = make_server(0, directory, background=False)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(base + "/api/catalog", timeout=10) as response:
                    catalog = json.load(response)
                self.assertEqual(len(catalog["templates"]), 2)
                self.assertEqual(len(catalog["datasets"]), 6)
                self.assertEqual(len(catalog["blocks"]), 6)
                template = next(t for t in catalog["templates"] if t["name"] == "CTZ<t>")
                request = Request(base + "/api/templates/synthesize", data=json.dumps({
                    "template_id": template["id"], "parameters": {"t": 4}, "samples": 16,
                    "name": "CTZ HTTP"}).encode(), headers={"Content-Type": "application/json"})
                with urlopen(request, timeout=10) as response:
                    saved = json.load(response)
                self.assertTrue(saved["result"]["fitness"]["verified_truth_table"])
                self.assertEqual(saved["dataset"]["outputs"], 3)
            finally:
                server.shutdown()
                server.server_close()
                server.executor.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

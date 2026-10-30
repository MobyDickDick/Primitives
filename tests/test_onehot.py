"""GEN-03: independent complete tables, roundtrips, hardware limits and upgrades."""
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
from primitives.examples import install_examples, install_onehot_examples
from primitives.library import Library, fitness
from primitives.server import make_server
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_generative import netlist
from tools.export_onehot import KINDS, OUTPUT, ROOT, TEMPLATES, bundle, definition, label, packed_result


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def expected(kind, w, value):
    # Scan actual bits, independent of the recursive implementation and export oracle.
    if kind == "decoder":
        result = [0] * (1 << w)
        if value & (1 << w):
            result[value % (1 << w)] = 1
        return [integer(result)]
    positions = [i for i in range(1 << w) if (value >> i) & 1]
    return [positions[0] if len(positions) == 1 else 0, int(len(positions) == 1), int(len(positions) > 1)]


class OneHotTests(unittest.TestCase):
    def test_all_exported_tables_and_hardware_forms(self):
        total = 0
        for kind in KINDS:
            template = Template(definition(kind))
            self.assertEqual(read(TEMPLATES / f"recursive-{kind}.abstract.json"), template.to_dict())
            reports = read(OUTPUT / f"recursive-{kind}/verification.json")
            self.assertEqual(len(reports), 3)
            for w in (1, 2, 4):
                with self.subTest(kind=kind, w=w):
                    prefix = OUTPUT / f"recursive-{kind}/{kind}-{w}"
                    program = template.instantiate({"w": w})
                    hierarchy = BlockBundle(read(prefix.with_suffix(".block.json")))
                    expanded = hierarchy.expand()
                    circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                    dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                    self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                    self.assertEqual(hierarchy.to_dict(), bundle(kind, w).to_dict())
                    self.assertEqual(circuit, expanded.simplify())
                    self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"),
                                     netlist(circuit, program, label(kind, w)))
                    self.assertEqual(len(dataset.rows), 1 << dataset.inputs)
                    self.assertEqual([p["bits"] for p in program.ports["inputs"]],
                                     [w, 1] if kind == "decoder" else [1 << w])
                    self.assertEqual([p["bits"] for p in program.ports["outputs"]],
                                     [1 << w] if kind == "decoder" else [w, 1, 1])
                    # All 65536 patterns of OHE<4> are checked, including every multihot code.
                    for row in dataset.rows:
                        value = integer(row[:dataset.inputs])
                        result = expected(kind, w, value)
                        self.assertEqual(row[dataset.inputs:], packed_result(program, result))
                    for impl in (expanded, circuit, synthesize(program)):
                        self.assertTrue(fitness(impl, dataset)["verified_truth_table"])
                    report = next(r for r in reports if r["parameters"] == {"w": w})
                    self.assertEqual(report["fitness"], fitness(circuit, dataset))
                    self.assertEqual(report["hierarchy"], hierarchy.summary())
                    if w > 1:
                        self.assertEqual(sum(n["kind"] == "instance"
                                             for n in hierarchy.view()["circuit"]["view_nodes"]), 3)
                    total += len(dataset.rows)
        self.assertEqual(total, 65600)

    def test_reference_hierarchy_and_both_roundtrips(self):
        for w in (1, 2, 4):
            decoder = Template(definition("decoder")).instantiate({"w": w})
            encoder = Template(definition("onehot-encoder")).instantiate({"w": w})
            decbox, encbox = bundle("decoder", w), bundle("onehot-encoder", w)
            # Every valid code and both enable states; all small invalid patterns,
            # every two-bit error for w=4, and deterministic larger multihot patterns.
            count = 1 << w
            cases = set(range(1 << count)) if w < 4 else {0, (1 << count) - 1}
            cases.update(1 << i for i in range(count))
            cases.update((1 << i) | (1 << j) for i in range(count) for j in range(i + 1, count))
            cases.update(random.Random(value).getrandbits(count) for value in range(64))
            for value in cases:
                result = expected("onehot-encoder", w, value)
                self.assertEqual(encoder.run(value), result)
                self.assertEqual(encbox.evaluate(bits(value, count)), packed_result(encoder, result))
                code, valid, _ = result
                reconstructed = decoder.run(code | (valid << w))[0]
                self.assertEqual(reconstructed, value if valid else 0)
            for code in range(count):
                for enable in (0, 1):
                    value = code | (enable << w)
                    decoded = decoder.run(value)
                    self.assertEqual(decoded, expected("decoder", w, value))
                    self.assertEqual(decbox.evaluate(bits(value, w + 1)), bits(decoded[0], count))
                    self.assertEqual(encoder.run(decoded[0]), [code, 1, 0] if enable else [0, 0, 0])

    def test_larger_references_and_synthesizable_hardware(self):
        rng = random.Random(20261030)
        for w in (3, 5, 6, 7):
            count = 1 << w
            decoder = Template(definition("decoder")).instantiate({"w": w})
            encoder = Template(definition("onehot-encoder")).instantiate({"w": w})
            decimpl = [synthesize(decoder), bundle("decoder", w)] if w <= 6 else []
            encimpl = [synthesize(encoder), bundle("onehot-encoder", w)] if w <= 5 else []
            # Decoder input spaces are small even when outputs grow exponentially.
            for value in range(1 << (w + 1)):
                result = expected("decoder", w, value)
                self.assertEqual(decoder.run(value), result)
                for impl in decimpl:
                    self.assertEqual(impl.evaluate(bits(value, w + 1)), bits(result[0], count))
            cases = {0, (1 << count) - 1}
            cases.update(1 << i for i in range(count))
            cases.update((1 << i) | (1 << j) for i in range(count) for j in (0, count // 2, count - 1) if i != j)
            cases.update(rng.getrandbits(count) for _ in range(16))
            for value in cases:
                result = expected("onehot-encoder", w, value)
                self.assertEqual(encoder.run(value), result, (w, value))
                for impl in encimpl:
                    self.assertEqual(impl.evaluate(bits(value, count)), packed_result(encoder, result))

    def test_parameter_call_and_hardware_guards(self):
        for kind in KINDS:
            for w in (0, -1, 8, 128, True):
                with self.subTest(kind=kind, w=w), self.assertRaises(ValueError):
                    Template(definition(kind)).instantiate({"w": w})
            for w in (0, 8):
                document = definition(kind)
                # Keep definitions, replace the top-level result call.
                document["source"] = document["source"].replace(
                    "DEC<w>(a, enable)\n" if kind == "decoder" else "OHE<w>(a), w + 2)",
                    f"DEC<{w}>(a, enable)\n" if kind == "decoder" else f"OHE<{w}>(a), w + 2)")
                program = Template(document).instantiate({"w": 1})
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    program.run(0)
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    synthesize(program)
        for kind, widths in (("decoder", (7,)), ("onehot-encoder", (6, 7))):
            for w in widths:
                program = Template(definition(kind)).instantiate({"w": w})
                with self.assertRaisesRegex(ValueError, "512"):
                    synthesize(program)
                with self.assertRaisesRegex(ValueError, "512"):
                    bundle(kind, w)

    def test_migration_preserves_folders_edits_and_deleted_examples(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            install_examples(library)
            self.assertFalse(any(t["name"] == "DEC<w>" for t in library.templates()))
            library.save_folder("Meine Codes", "Eigene Beschreibung", "examples", "recursion")
            entries = library.tree()["entries"].copy()
            install_onehot_examples(library)
            self.assertTrue(read(Path(directory) / "example-installations.json")["onehot-v1"])
            self.assertTrue(entries.items() <= library.tree()["entries"].items())
            folder = next(f for f in library.tree()["folders"] if f["id"] == "recursion")
            self.assertEqual((folder["name"], folder["description"]), ("Meine Codes", "Eigene Beschreibung"))
            new = [d for d in library.datasets() if d["name"].startswith(("DEC<", "OHE<"))]
            self.assertEqual(len(new), 6)
            key = new[0]["function_id"]
            library.update_function(key, "Mein Decoder", "Eigener Text")
            library.move_entry("function", key, "functions")
            library.delete_function(new[1]["function_id"])
            template = next(t for t in library.templates() if t["name"] == "DEC<w>")
            (Path(directory) / "templates" / f"{template['id']}.json").unlink()
            block = next(b for b in library.blocks() if b["name"] == "OHE<4>")
            (Path(directory) / "blocks" / f"{block['id']}.json").unlink()
            before = {p: p.read_bytes() for p in Path(directory).rglob("*.json")}
            install_onehot_examples(Library(directory))
            self.assertEqual({p: p.read_bytes() for p in Path(directory).rglob("*.json")}, before)
            self.assertEqual(next(d for d in library.datasets() if d["function_id"] == key)["name"], "Mein Decoder")

    def test_migration_preserves_a_better_circuit_and_assignments(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            dataset = Dataset.from_dict(read(OUTPUT / "recursive-onehot-encoder/onehot-encoder-2.vectors.json"))
            document = definition("onehot-encoder")
            document["source"] = """x = bits(a, 4)
lo = x[0] | x[1]
hi = x[2] | x[3]
multiple = (x[0] & x[1]) | (x[2] & x[3]) | (lo & hi)
valid = (lo | hi) & (1 ^ multiple)
return pack([(x[1] | x[3]) & valid, hi & valid]), valid, multiple
"""
            circuit = synthesize(Template(document).instantiate({"w": 2}))
            self.assertTrue(fitness(circuit, dataset)["verified_truth_table"])
            original = read(OUTPUT / "recursive-onehot-encoder/onehot-encoder-2.circuit.json")
            self.assertLess(len(circuit.gates), len(original["gates"]))
            saved = library.save_program({"circuit": circuit.to_dict(), "note": "Eigene bessere Lösung"}, dataset)
            key = library.datasets()[0]["function_id"]
            library.update_function(key, "Eigener Name", "Erhalten")
            library.move_entry("function", key, "functions")
            template_key = library.save_template(Template(definition("onehot-encoder")))
            library.move_entry("template", template_key, "templates")
            install_onehot_examples(library)
            self.assertEqual(library.load_program(saved["id"])["note"], "Eigene bessere Lösung")
            self.assertEqual(library.tree()["entries"][f"function:{key}"], "functions")
            self.assertEqual(library.tree()["entries"][f"template:{template_key}"], "templates")
            self.assertEqual(next(d for d in library.datasets() if d["function_id"] == key)["name"], "Eigener Name")
            self.assertEqual(len(library.templates()), 2)
            self.assertEqual(len(library.datasets()), 6)
            self.assertEqual(len(library.blocks()), 6)

    def test_server_upgrade_catalog_synthesis_and_block_evaluation(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            previous = ("arithmetic", "recursive-checked", "recursive-mul", "number-of-ones",
                        "recursive-msb-div", "recursive-max-index", "recursive-equ", "recursive-gt",
                        "generative-logic", "routing", "structured-logic", "standard-arithmetic",
                        "arithmetic-comments", "zero-counts", "priority-encoder")
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
                self.assertEqual(len(catalog["templates"]), 2)
                self.assertEqual(len(catalog["datasets"]), 6)
                self.assertEqual(len(catalog["blocks"]), 6)
                for kind in KINDS:
                    template = next(t for t in catalog["templates"] if t["name"] == label(kind, "w"))
                    saved = request("/api/templates/synthesize", {
                        "template_id": template["id"], "parameters": {"w": 2}, "samples": 16, "name": f"{kind} HTTP"})
                    self.assertTrue(saved["result"]["fitness"]["verified_truth_table"])
                    block = next(b for b in catalog["blocks"] if b["name"] == label(kind, 4))
                    program = Template(definition(kind)).instantiate({"w": 4})
                    n = sum(p["bits"] for p in program.ports["inputs"])
                    for value in (0, 1, 3, (1 << n) - 1):
                        evaluation = request("/api/blocks/evaluate", {"block_id": block["id"], "bits": bits(value, n)})
                        self.assertEqual(evaluation["outputs"], packed_result(program, expected(kind, 4, value)))
            finally:
                server.shutdown()
                server.server_close()
                server.executor.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

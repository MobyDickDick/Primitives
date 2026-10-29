"""GEN-02: independent oracles, hardware forms, limits and library upgrades."""
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
from primitives.examples import install_examples, install_priority_encoder_examples
from primitives.library import Library, fitness
from primitives.server import make_server
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_generative import netlist
from tools.export_max_index import definition as maximum_definition
from tools.export_priority_encoder import OUTPUT, ROOT, SOURCE, bundle, definition, merge_program


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def expected(width, value):
    # Scan bits from zero; independent of recursive halves and bit_length.
    for index in range(width):
        if (value >> index) & 1:
            return [index, 1]
    return [0, 0]


class PriorityEncoderTests(unittest.TestCase):
    def test_all_exported_forms_exhaustively_and_maximum_counterpart(self):
        template = Template(definition())
        self.assertEqual(read(SOURCE.with_suffix(".abstract.json")), template.to_dict())
        reports = read(OUTPUT / "verification.json")
        self.assertEqual(len(reports), 3)
        for width in (1, 2, 4):
            with self.subTest(width=width):
                prefix = OUTPUT / f"pe-{width}"
                program = template.instantiate({"t": width})
                maximum = Template(maximum_definition()).instantiate({"t": width})
                hierarchy = BlockBundle(read(prefix.with_suffix(".block.json")))
                expanded = hierarchy.expand()
                circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                compiled = synthesize(program)
                dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                w = max(1, width.bit_length() - 1)
                self.assertEqual(hierarchy.to_dict(), bundle(width).to_dict())
                self.assertEqual(circuit, expanded.simplify())
                self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"),
                                 netlist(circuit, program, f"PE<{width}>"))
                self.assertEqual([(p["name"], p["bits"]) for p in program.ports["inputs"]], [("a", width)])
                self.assertEqual([(p["name"], p["bits"]) for p in program.ports["outputs"]], [("c", w), ("valid", 1)])
                self.assertEqual(len(dataset.rows), 1 << width)
                checked = fitness(circuit, dataset)
                self.assertTrue(checked["verified_truth_table"])
                report = next(r for r in reports if r["parameters"]["t"] == width)
                self.assertEqual(report["fitness"], checked)
                self.assertEqual(report["hierarchy"], hierarchy.summary())
                for row in dataset.rows:
                    value = sum(bit << i for i, bit in enumerate(row[:width]))
                    result = expected(width, value)
                    packed = bits(result[0], w) + [result[1]]
                    self.assertEqual(row[width:], packed)
                    self.assertEqual(program.run(value), result)
                    for impl in (hierarchy, expanded, circuit, compiled):
                        self.assertEqual(impl.evaluate(bits(value, width)), packed)
                    reverse = int(f"{value:0{width}b}"[::-1], 2)
                    max_index, error = maximum.run(reverse)
                    self.assertEqual(result, [width - 1 - max_index if value else 0, 1 - error])
                if width > 1:
                    children = [n["name"] for n in hierarchy.view()["circuit"]["view_nodes"]
                                if n["kind"] == "instance"]
                    self.assertEqual(children, [f"PE<{width // 2}>"] * 2 + [f"PriorityMerge<{width // 2}>"])

    def test_larger_widths_boundaries_multihot_and_samples(self):
        rng = random.Random(20261029)
        for width in (8, 16, 32, 64, 128):
            maximum = (1 << width) - 1
            cases = {0, maximum}
            # Every bit can win. Set every higher bit too to check priority.
            cases.update(1 << i for i in range(width))
            cases.update(maximum ^ ((1 << i) - 1) for i in range(width))
            cases.update(rng.getrandbits(width) for _ in range(12))
            program = Template(definition()).instantiate({"t": width})
            implementations = [synthesize(program), bundle(width)] if width <= 32 else []
            for value in cases:
                result = expected(width, value)
                self.assertEqual(program.run(value), result, (width, value))
                packed = bits(result[0], width.bit_length() - 1) + [result[1]]
                for impl in implementations:
                    self.assertEqual(impl.evaluate(bits(value, width)), packed)

    def test_merge_for_all_valid_and_invalid_child_results(self):
        for k in (1, 2, 4, 8):
            program = merge_program(k)
            circuit = synthesize(program)
            r, w = max(1, k.bit_length() - 1), k.bit_length()
            children = [(0, 0)] + [(i, 1) for i in range(k)]
            for lo, lv in children:
                for hi, hv in children:
                    value = lo | (hi << r) | (lv << (2 * r)) | (hv << (2 * r + 1))
                    result = [lo if lv else k + hi if hv else 0, lv | hv]
                    self.assertEqual(program.run(value), result)
                    self.assertEqual(circuit.evaluate(bits(value, 2 * r + 2)), bits(result[0], w) + [result[1]])

    def test_parameter_guards_call_guards_and_hardware_limits(self):
        for width in (0, -1, 3, 6, 129, 256, True):
            with self.subTest(width=width), self.assertRaises(ValueError):
                Template(definition()).instantiate({"t": width})
        for call in ("PE<0>(a)", "PE<3>(a)", "PE<256>(a)", "PriorityMerge<3>(0, 0, 0, 0)"):
            document = definition()
            document["source"] = document["source"].split("# Ergebnisports", 1)[0] + f"\nreturn {call}, 0\n"
            program = Template(document).instantiate({"t": 4})
            with self.subTest(call=call):
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    program.run(0)
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    synthesize(program)
        for width in (64, 128):
            program = Template(definition()).instantiate({"t": width})
            with self.assertRaisesRegex(ValueError, "512"):
                synthesize(program)
            with self.assertRaisesRegex(ValueError, "512"):
                bundle(width)

    def test_separate_migration_keeps_folders_edits_and_deletions(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            install_examples(library)
            self.assertFalse(any(t["name"] == "PE<t>" for t in library.templates()))
            library.save_folder("Meine Rekursion", "Eigener Text", "examples", "recursion")
            old_entries = library.tree()["entries"].copy()
            install_priority_encoder_examples(library)
            self.assertTrue(read(Path(directory) / "example-installations.json")["priority-encoder-v1"])
            self.assertTrue(old_entries.items() <= library.tree()["entries"].items())
            self.assertEqual(next(f for f in library.tree()["folders"] if f["id"] == "recursion")["name"], "Meine Rekursion")
            new = [d for d in library.datasets() if d["name"].startswith("PE<")]
            self.assertEqual(len(new), 3)
            self.assertTrue(all(p["fitness"]["verified_truth_table"] for p in library.programs()
                                if p["dataset_name"].startswith("PE<")))
            key = new[0]["function_id"]
            library.update_function(key, "Mein Encoder", "Beschreibung")
            library.move_entry("function", key, "functions")
            library.delete_function(new[1]["function_id"])
            template = next(t for t in library.templates() if t["name"] == "PE<t>")
            library.move_entry("template", template["id"], "functions")
            (Path(directory) / "templates" / f"{template['id']}.json").unlink()
            block = next(b for b in library.blocks() if b["name"] == "PE<4>")
            (Path(directory) / "blocks" / f"{block['id']}.json").unlink()
            before = {p: p.read_bytes() for p in Path(directory).rglob("*.json")}
            install_priority_encoder_examples(Library(directory))
            self.assertEqual({p: p.read_bytes() for p in Path(directory).rglob("*.json")}, before)
            self.assertEqual(next(d for d in library.datasets() if d["function_id"] == key)["name"], "Mein Encoder")

    def test_fresh_migration_keeps_existing_better_solution_and_organization(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            dataset = Dataset.from_dict(read((OUTPUT / "pe-4").with_suffix(".vectors.json")))
            document = definition()
            document["source"] = """x = bits(a, 4)
l = x[0] | x[1]
h = x[2] | x[3]
c0 = (1 ^ x[0]) & (x[1] | ((1 ^ x[2]) & x[3]))
c1 = (1 ^ l) & h
return pack([c0, c1]), l | h
"""
            circuit = synthesize(Template(document).instantiate({"t": 4}))
            self.assertTrue(fitness(circuit, dataset)["verified_truth_table"])
            self.assertLess(len(circuit.gates), len(read((OUTPUT / "pe-4").with_suffix(".circuit.json"))["gates"]))
            saved = library.save_program({"circuit": circuit.to_dict(), "note": "Eigene beste Lösung"}, dataset)
            key = library.datasets()[0]["function_id"]
            library.update_function(key, "Eigener Name", "Erhalten")
            library.move_entry("function", key, "functions")
            template_key = library.save_template(Template(definition()))
            library.move_entry("template", template_key, "templates")
            install_priority_encoder_examples(library)
            reloaded = Library(directory)
            self.assertEqual(next(p for p in reloaded.programs() if p["id"] == saved["id"])["note"], "Eigene beste Lösung")
            self.assertEqual(reloaded.tree()["entries"][f"function:{key}"], "functions")
            self.assertEqual(reloaded.tree()["entries"][f"template:{template_key}"], "templates")
            self.assertEqual(next(d for d in reloaded.datasets() if d["function_id"] == key)["name"], "Eigener Name")
            self.assertEqual(len(reloaded.templates()), 1)
            self.assertEqual(len(reloaded.datasets()), 3)
            self.assertEqual(len(reloaded.blocks()), 3)

    def test_server_upgrade_catalog_synthesis_and_fbox_evaluation(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            previous = ("arithmetic", "recursive-checked", "recursive-mul", "number-of-ones",
                        "recursive-msb-div", "recursive-max-index", "recursive-equ", "recursive-gt",
                        "generative-logic", "routing", "structured-logic", "standard-arithmetic",
                        "arithmetic-comments", "zero-counts")
            (Path(directory) / "example-installations.json").write_text(
                json.dumps({f"{key}-v1": True for key in previous}), encoding="utf-8")
            server = make_server(0, directory, background=False)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"

            def request(path, data=None):
                req = Request(base + path, data=json.dumps(data).encode() if data is not None else None,
                              headers={"Content-Type": "application/json"})
                with urlopen(req, timeout=10) as response:
                    return json.load(response)

            try:
                catalog = request("/api/catalog")
                self.assertEqual(len(catalog["templates"]), 1)
                self.assertEqual(len(catalog["datasets"]), 3)
                self.assertEqual(len(catalog["blocks"]), 3)
                template = catalog["templates"][0]
                self.assertEqual(template["name"], "PE<t>")
                saved = request("/api/templates/synthesize", {
                    "template_id": template["id"], "parameters": {"t": 4}, "samples": 16, "name": "PE HTTP"})
                self.assertTrue(saved["result"]["fitness"]["verified_truth_table"])
                self.assertEqual(saved["dataset"]["outputs"], 3)
                block = next(b for b in catalog["blocks"] if b["name"] == "PE<4>")
                for value in (0, 1, 2, 8, 10, 15):
                    evaluation = request("/api/blocks/evaluate", {"block_id": block["id"], "bits": bits(value, 4)})
                    result = expected(4, value)
                    self.assertEqual(evaluation["outputs"], bits(result[0], 2) + [result[1]])
            finally:
                server.shutdown()
                server.server_close()
                server.executor.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

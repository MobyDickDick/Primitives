"""GEN-12: independent sorting, multiset preservation, limits and upgrades."""
from collections import Counter
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
from primitives.examples import install_examples, install_sort_network_examples
from primitives.library import Library, fitness, function_id
from primitives.server import make_server
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_generative import netlist
from tools.export_sort_network import CASES, OUTPUT, ROOT, TEMPLATES, bundle, definition
from tools.export_structured import definition as structured_definition


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def channels(value, k, n):
    return [(value >> (i*n)) & ((1 << n)-1) for i in range(2**k)]


class SortNetworkTests(unittest.TestCase):
    def check_value(self, program, hardware, k, n, value):
        original = channels(value, k, n)
        result = program.run(value)[0]
        actual = channels(result, k, n)
        self.assertEqual(actual, sorted(original))
        self.assertEqual(Counter(actual), Counter(original))
        for impl in hardware:
            self.assertEqual(impl.evaluate(bits(value, n*2**k)), bits(result, n*2**k))
        return result

    def test_complete_small_exports_and_visible_sort2_hierarchy(self):
        reports = read(OUTPUT / "verification.json")
        self.assertEqual(len(reports), len(CASES))
        self.assertEqual(read(TEMPLATES / "sort-network.abstract.json"), Template(definition()).to_dict())
        total = 0
        for k, n in CASES:
            with self.subTest(k=k, n=n):
                prefix = OUTPUT / f"sort-{k}-{n}"
                program = Template(definition()).instantiate({"k": k, "n": n})
                hierarchy = BlockBundle(read(prefix.with_suffix(".block.json")))
                expanded, compiled = hierarchy.expand(), synthesize(program)
                circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                self.assertEqual(hierarchy.to_dict(), bundle(k, n).to_dict())
                self.assertEqual(circuit, expanded.simplify())
                self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"),
                                 netlist(circuit, program, f"SORT_NET<{k},{n}>"))
                self.assertEqual(len(hierarchy.definition["nodes"]), 2**k*k*(k+1)//4)
                definitions = hierarchy.to_dict()["definitions"]
                for node in hierarchy.definition["nodes"]:
                    self.assertEqual(definitions[node["definition"]]["name"], f"SORT2<{n}>")
                width = n*2**k
                self.assertEqual(len(dataset.rows), 1 << width)
                self.assertEqual(program.ports["inputs"][0]["bits"], width)
                self.assertEqual(program.ports["outputs"][0]["bits"], width)
                for row in dataset.rows:
                    result = self.check_value(program, (hierarchy, expanded, circuit, compiled), k, n, integer(row[:width]))
                    self.assertEqual(row[width:], bits(result, width))
                report = next(r for r in reports if r["parameters"] == {"k": k, "n": n})
                self.assertEqual(report["fitness"], fitness(circuit, dataset))
                self.assertTrue(report["fitness"]["verified_truth_table"])
                self.assertEqual(report["hierarchy"], hierarchy.summary())
                total += len(dataset.rows)
        self.assertEqual(total, 548)

    def test_eight_binary_channels_exhaustively(self):
        k, n = 3, 1
        program = Template(definition()).instantiate({"k": k, "n": n})
        hardware = (synthesize(program), bundle(k, n), bundle(k, n).expand().simplify())
        for value in range(256):
            self.check_value(program, hardware, k, n, value)

    def test_larger_samples_duplicates_order_boundaries_and_identity(self):
        rng = random.Random(20261112)
        for k, n in ((0, 1), (0, 64), (1, 8), (1, 16), (1, 32), (2, 4), (2, 8),
                     (3, 2), (3, 4), (4, 1), (5, 1)):
            program = Template(definition()).instantiate({"k": k, "n": n})
            hardware = [synthesize(program), bundle(k, n)] if (k, n) in ((0, 1), (0, 64), (1, 8), (1, 16), (2, 4)) else []
            mask = (1 << n)-1
            lists = [[0]*2**k, [mask]*2**k, [mask if i % 2 else 0 for i in range(2**k)],
                     [min(i, mask) for i in range(2**k)], [min(i, mask) for i in reversed(range(2**k))],
                     [1 << (n-1)] + [0]*(2**k-1)]
            lists += [[rng.getrandbits(n) for _ in range(2**k)] for _ in range(8)]
            for values in lists:
                with self.subTest(k=k, n=n, values=values):
                    value = sum(v << (i*n) for i, v in enumerate(values))
                    self.check_value(program, hardware, k, n, value)

    def test_sort2_dependency_remains_equivalent(self):
        # The helper's local half-width variable was renamed to avoid template k.
        for n in (1, 2, 4):
            doc = definition()
            doc["source"] = doc["source"].split("# Ergebnisport", 1)[0] + f"return SORT2<{n}>(a,b)\n"
            doc["interface"] = {"inputs": [{"name": "a", "bits": n}, {"name": "b", "bits": n}],
                                "outputs": [{"name": "c", "bits": 2*n}]}
            helper = Template(doc).instantiate({"k": 1, "n": n})
            original = Template(structured_definition("sort2")).instantiate({"t": n})
            self.assertEqual(synthesize(helper), synthesize(original))

    def test_parameters_direct_calls_port_and_construction_budgets(self):
        for k, n in ((-1, 1), (8, 1), (True, 1), (1, True), (1, 0), (1, 3), (0, 128), (2, 64), (7, 2)):
            with self.subTest(k=k, n=n), self.assertRaises(ValueError):
                Template(definition()).instantiate({"k": k, "n": n})
        doc = definition()
        doc["source"] = doc["source"].split("# Ergebnisport", 1)[0] + "return SORT_NET<1,3>(a)\n"
        program = Template(doc).instantiate({"k": 1, "n": 1})
        for build in (lambda: program.run(0), lambda: synthesize(program)):
            with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                build()
        for k, n in ((1, 32), (2, 8), (3, 2), (4, 1)):
            program = Template(definition()).instantiate({"k": k, "n": n})
            for build in (lambda: synthesize(program), lambda: bundle(k, n)):
                with self.subTest(k=k, n=n), self.assertRaisesRegex(ValueError, "512"):
                    build()
        # Legal 128-bit interfaces still obey the per-input instruction budget.
        for k, n in ((1, 64), (7, 1)):
            program = Template(definition()).instantiate({"k": k, "n": n})
            with self.assertRaisesRegex(ValueError, "Anweisungsbudget"):
                program.run(0)

    def test_migration_preserves_labels_folders_better_solutions_and_deletions(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            organization = library._organization()
            organization["folders"].extend(
                {"id": key, "parent": parent, "name": f"Mein {key}", "description": "Eigene Beschreibung"}
                for key, parent in (("examples", None), ("recursion", "examples"), ("sort-network", "recursion")))
            library._write_organization(organization)
            dataset = Dataset.from_dict(read(OUTPUT / "sort-2-2.vectors.json"))
            saved = library.save_program({"circuit": read(OUTPUT / "sort-2-2.circuit.json")}, dataset)
            key = function_id(dataset)
            library.update_function(key, "Mein Sortierer", "Beschreibung")
            library.move_entry("function", key, "functions")
            template_key = library.save_template(Template(definition()))
            library.move_entry("template", template_key, "templates")
            # Binary min/max is just AND/OR: five NANDs beat generic SORT2's nine.
            smaller = Circuit(2, ((0, 1), (2, 2), (0, 0), (1, 1), (4, 5)), (3, 6))
            binary = Dataset.from_dict(read(OUTPUT / "sort-1-1.vectors.json"))
            self.assertTrue(fitness(smaller, binary)["verified_truth_table"])
            better = library.save_program({"circuit": smaller.to_dict()}, binary)
            before = library.tree()
            install_sort_network_examples(library)
            self.assertTrue(read(Path(directory) / "example-installations.json")["sort-network-v1"])
            self.assertEqual(library.tree()["folders"], before["folders"])
            self.assertTrue(before["entries"].items() <= library.tree()["entries"].items())
            self.assertEqual((len(library.templates()), len(library.datasets()), len(library.blocks())), (1, 5, 5))
            self.assertTrue({saved["id"], better["id"]} <= {p["id"] for p in library.programs()})
            library.delete_function(key)
            (Path(directory) / "templates" / f"{template_key}.json").unlink()
            block = next(b for b in library.blocks() if b["name"] == "SORT_NET<2,2>")
            (Path(directory) / "blocks" / f"{block['id']}.json").unlink()
            snapshot = {p: p.read_bytes() for p in Path(directory).rglob("*.json")}
            install_sort_network_examples(Library(directory))
            self.assertEqual({p: p.read_bytes() for p in Path(directory).rglob("*.json")}, snapshot)
            # The original installer also leaves this migration's deletions alone.
            install_examples(library)
            self.assertNotIn(template_key, {t["id"] for t in library.templates()})

    def test_http_upgrade_synthesis_evaluation_and_nested_view(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            # Mark existing migrations complete to exercise only the new upgrade.
            previous = ("signed-arithmetic", "signed", "saturating", "parallel-add", "prefixes", "arithmetic",
                        "recursive-checked", "recursive-mul", "number-of-ones", "recursive-msb-div", "recursive-max-index",
                        "recursive-equ", "recursive-gt", "generative-logic", "routing", "structured-logic",
                        "standard-arithmetic", "arithmetic-comments", "zero-counts", "priority-encoder", "onehot",
                        "barrel-shifter", "rotations", "multipliers")
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
                self.assertEqual((len(catalog["templates"]), len(catalog["datasets"]), len(catalog["blocks"])), (1, 5, 5))
                template = catalog["templates"][0]
                saved = request("/api/templates/synthesize", {"template_id": template["id"],
                    "parameters": {"k": 2, "n": 2}, "samples": 256, "name": "Sortieren HTTP"})
                self.assertTrue(saved["result"]["fitness"]["verified_truth_table"])
                block = next(b for b in catalog["blocks"] if b["name"] == "SORT_NET<2,2>")
                value = 3 | 1 << 2 | 3 << 4 | 0 << 6
                evaluated = request("/api/blocks/evaluate", {"block_id": block["id"], "bits": bits(value, 8)})
                self.assertEqual(evaluated["outputs"], bits(0 | 1 << 2 | 3 << 4 | 3 << 6, 8))
                view = request("/api/blocks/view", {"block_id": block["id"], "path": []})
                self.assertEqual(len([node for node in view["circuit"]["view_nodes"] if node["kind"] == "instance"]), 6)
                child = request("/api/blocks/view", {"block_id": block["id"], "path": ["s2_d1_c0"]})
                self.assertEqual(child["name"], "SORT2<2>")
            finally:
                server.shutdown()
                server.server_close()
                server.executor.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

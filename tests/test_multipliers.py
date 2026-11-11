"""GEN-11: complete products, independent integer oracles and library upgrade."""
import json
from itertools import product
from pathlib import Path
import random
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen

from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, integer
from primitives.examples import install_multiplier_examples
from primitives.library import Library, fitness, function_id
from primitives.server import make_server
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_generative import netlist
from tools.export_multipliers import (KINDS, ROOT, TEMPLATES, OUTPUT, WIDTHS, bundle,
                                      comparison, comparison_programs, definition)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class MultiplierTests(unittest.TestCase):
    def test_all_exports_complete_products_and_comparisons(self):
        reports = read(OUTPUT / "verification.json")
        self.assertEqual(len(reports), 18)
        total = 0
        for kind in KINDS:
            template = Template(definition(kind))
            self.assertEqual(read(TEMPLATES / f"{kind}-mul.abstract.json"), template.to_dict())
            for p, q in product(WIDTHS, repeat=2):
                with self.subTest(kind=kind, p=p, q=q):
                    name = f"{kind.upper()}_MUL<{p},{q}>"
                    prefix = OUTPUT / f"{kind}-{p}-{q}"
                    program = template.instantiate({"p": p, "q": q})
                    hierarchy = BlockBundle(read(prefix.with_suffix(".block.json")))
                    expanded, compiled = hierarchy.expand(), synthesize(program)
                    circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                    dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                    self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                    self.assertEqual(hierarchy.to_dict(), bundle(kind, p, q).to_dict())
                    self.assertEqual(circuit, expanded.simplify())
                    self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"), netlist(circuit, program, name))
                    self.assertEqual([port["bits"] for port in program.ports["inputs"]], [p, q])
                    self.assertEqual(program.ports["outputs"][0]["bits"], p + q)
                    self.assertEqual(len(dataset.rows), 1 << (p + q))
                    other_programs = comparison_programs(p, q)
                    other_circuits = [synthesize(other) for other in other_programs.values()]
                    for row in dataset.rows:
                        a, b = integer(row[:p]), integer(row[p:p+q])
                        # Python integer multiplication is independent of the compressors.
                        wanted = bits(a * b, p + q)
                        self.assertEqual(row, bits(a, p) + bits(b, q) + wanted)
                        for impl in (program, *other_programs.values()):
                            self.assertEqual(impl.run(a | b << p), [a * b])
                        for impl in (hierarchy, expanded, circuit, compiled, *other_circuits):
                            self.assertEqual(impl.evaluate(row[:p+q]), wanted)
                    report = next(r for r in reports if r["name"] == name)
                    self.assertEqual(report["fitness"], fitness(circuit, dataset))
                    self.assertTrue(report["fitness"]["verified_truth_table"])
                    self.assertEqual(report["hierarchy"], hierarchy.summary())
                    self.assertEqual(report["comparison"], comparison(p, q))
                    total += len(dataset.rows)
        self.assertEqual(total, 968)

    def test_larger_samples_transposition_and_tree_remainders(self):
        rng = random.Random(20261111)
        # 5/6/7/8 rows cover both kinds of leftovers and multiple tree levels.
        for p, q in ((3, 5), (5, 3), (5, 5), (6, 6), (7, 7), (8, 8), (16, 4), (1, 63), (63, 1)):
            programs = {kind: Template(definition(kind)).instantiate({"p": p, "q": q}) for kind in KINDS}
            hardware = {kind: [synthesize(program), bundle(kind, p, q)] for kind, program in programs.items()
                        if (p, q) in ((3, 5), (5, 3), (5, 5), (6, 6), (1, 63), (63, 1))}
            values = lambda w: {0, 1, 1 << (w - 1), (1 << w) - 1, (1 << (w - 1)) - 1}
            pairs = set(product(values(p), values(q)))
            pairs.update((rng.getrandbits(p), rng.getrandbits(q)) for _ in range(8))
            for a, b in pairs:
                for kind, program in programs.items():
                    with self.subTest(kind=kind, p=p, q=q, a=a, b=b):
                        self.assertEqual(program.run(a | b << p), [a * b])
                        for impl in hardware.get(kind, []):
                            self.assertEqual(impl.evaluate(bits(a, p) + bits(b, q)), bits(a * b, p + q))
        # Beyond four rows the constructions really have different schedules.
        array, wallace = (synthesize(Template(definition(kind)).instantiate({"p": 6, "q": 6})) for kind in KINDS)
        self.assertNotEqual(array, wallace)
        self.assertEqual((len(array.gates), array.depth), (318, 39))
        self.assertEqual((len(wallace.gates), wallace.depth), (333, 38))

    def test_compressor_identity_and_parallel_bit_carries(self):
        for kind in KINDS:
            document = definition(kind)
            document["source"] = document["source"].split("# Ergebnisport", 1)[0] + "return MulCSA<4>(a,b,c)\n"
            document["interface"] = {"inputs": [{"name": name, "bits": 4} for name in ("a", "b", "c")],
                                     "outputs": [{"name": "pair", "bits": 8}]}
            program = Template(document).instantiate({"p": 4, "q": 4})
            circuit = synthesize(program)
            for a, b, c in product(range(16), repeat=3):
                encoded = program.run(a | b << 4 | c << 8)[0]
                low, carry = encoded % 16, encoded // 16
                self.assertEqual((low + carry) % 16, (a + b + c) % 16)
                self.assertEqual(carry % 2, 0)
                self.assertEqual(integer(circuit.evaluate(bits(a | b << 4 | c << 8, 12))), encoded)

    def test_parameter_direct_call_array_port_and_construction_limits(self):
        for kind in KINDS:
            invalid = [(0, 1), (1, 0), (-1, 2), (True, 1), (64, 1), (64, 64), (128, 1)]
            if kind == "wallace":
                invalid += [(9, 9), (4, 29), (29, 4)]
            for p, q in invalid:
                with self.subTest(kind=kind, p=p, q=q), self.assertRaises(ValueError):
                    Template(definition(kind)).instantiate({"p": p, "q": q})
            document = definition(kind)
            document["source"] = document["source"].split("# Ergebnisport", 1)[0] + f"return {kind.upper()}_MUL<0,1>(a,b)\n"
            document["interface"]["outputs"] = [{"name": "c", "bits": 1}]
            program = Template(document).instantiate({"p": 1, "q": 1})
            for build in (lambda: program.run(0), lambda: synthesize(program)):
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    build()
            for width in (7, 8):
                program = Template(definition(kind)).instantiate({"p": width, "q": width})
                with self.assertRaisesRegex(ValueError, "512"):
                    synthesize(program)
                with self.assertRaisesRegex(ValueError, "512"):
                    bundle(kind, width, width)

    def test_migration_preserves_folders_labels_better_solutions_and_deletions(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            organization = library._organization()
            organization["folders"].extend([
                {"id": "examples", "parent": None, "name": "Eigene Beispiele", "description": "Behalten"},
                {"id": "arithmetic", "parent": "examples", "name": "Meine Rechner", "description": "Text"},
                {"id": "multipliers", "parent": "arithmetic", "name": "Multiplizierer angepasst", "description": "Notizen"}])
            library._write_organization(organization)
            dataset = Dataset.from_dict(read(OUTPUT / "array-4-4.vectors.json"))
            saved = library.save_program({"circuit": read(OUTPUT / "array-4-4.circuit.json")}, dataset)
            key = function_id(dataset)
            library.update_function(key, "Mein Produkt", "Beschreibung")
            library.move_entry("function", key, "functions")
            template_key = library.save_template(Template(definition("array")))
            # Four NANDs compute [a AND b, 0]; exported 1/1 uses five.
            smaller = Circuit(2, ((0, 1), (2, 2), (2, 3), (4, 4)), (3, 5))
            small_dataset = Dataset.from_dict(read(OUTPUT / "array-1-1.vectors.json"))
            self.assertTrue(fitness(smaller, small_dataset)["verified_truth_table"])
            better = library.save_program({"circuit": smaller.to_dict(), "note": "Vier NANDs"}, small_dataset)
            before_tree = library.tree()
            install_multiplier_examples(library)
            self.assertTrue(read(Path(directory) / "example-installations.json")["multipliers-v1"])
            self.assertEqual(library.tree()["folders"], before_tree["folders"])
            self.assertTrue(before_tree["entries"].items() <= library.tree()["entries"].items())
            self.assertEqual((len(library.templates()), len(library.datasets()), len(library.blocks())), (2, 18, 18))
            winner_ids = {p["id"] for p in library.programs()}
            self.assertTrue({saved["id"], better["id"]} <= winner_ids)
            library.delete_function(key)
            (Path(directory) / "templates" / f"{template_key}.json").unlink()
            block = next(b for b in library.blocks() if b["name"] == "WALLACE_MUL<4,4>")
            (Path(directory) / "blocks" / f"{block['id']}.json").unlink()
            before = {p: p.read_bytes() for p in Path(directory).rglob("*.json")}
            install_multiplier_examples(Library(directory))
            self.assertEqual({p: p.read_bytes() for p in Path(directory).rglob("*.json")}, before)

    def test_http_upgrade_synthesis_evaluation_and_block_view(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            previous = ("sort-network", "signed-arithmetic", "signed", "saturating", "parallel-add", "prefixes", "arithmetic",
                        "recursive-checked", "recursive-mul", "number-of-ones", "recursive-msb-div", "recursive-max-index",
                        "recursive-equ", "recursive-gt", "generative-logic", "routing", "structured-logic",
                        "standard-arithmetic", "arithmetic-comments", "zero-counts", "priority-encoder", "onehot",
                        "barrel-shifter", "rotations")
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
                self.assertEqual((len(catalog["templates"]), len(catalog["datasets"]), len(catalog["blocks"])), (2, 18, 18))
                for kind in KINDS:
                    template = next(t for t in catalog["templates"] if t["name"] == f"{kind.upper()}_MUL<p,q>")
                    saved = request("/api/templates/synthesize", {"template_id": template["id"],
                        "parameters": {"p": 4, "q": 4}, "samples": 256, "name": f"{kind} HTTP"})
                    self.assertTrue(saved["result"]["fitness"]["verified_truth_table"])
                    block = next(b for b in catalog["blocks"] if b["name"] == f"{kind.upper()}_MUL<4,4>")
                    for a, b in ((0, 0), (15, 15), (4, 4), (3, 11)):
                        evaluated = request("/api/blocks/evaluate", {"block_id": block["id"], "bits": bits(a, 4) + bits(b, 4)})
                        self.assertEqual(evaluated["outputs"], bits(a * b, 8))
                    view = request("/api/blocks/view", {"block_id": block["id"], "path": []})
                    self.assertEqual(len(view["circuit"]["gates"]), 124)
            finally:
                server.shutdown()
                server.server_close()
                server.executor.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

"""GEN-10: independently decoded signed arithmetic, exports and upgrades."""
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
from primitives.examples import install_signed_arithmetic_examples
from primitives.library import Library, fitness
from primitives.server import make_server
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_generative import netlist
from tools.export_signed_arithmetic import KINDS, ROOT, TEMPLATES, OUTPUT, WIDTHS, bundle, definition, encoded


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def decode(value, width):
    sign, low = divmod(value, 2 ** (width - 1))
    return low - sign * 2 ** (width - 1)


def expected(kind, a, b, p, q):
    a, b = decode(a, p), decode(b, q)
    w = max(p, q)
    if kind == "cmp":
        return [int(a < b), int(a == b), int(a > b)]
    if kind in ("add", "sub"):
        value = a + b if kind == "add" else a - b
        return [value % (2 ** w), int(value < -(2 ** (w - 1)) or value >= 2 ** (w - 1))]
    if kind == "mul":
        return [(a * b) % (2 ** (p + q))]
    if b == 0:
        return [0, 0, 0, 1, 0]
    # Python floor division is corrected towards zero, independently of the
    # magnitude/restoring construction and the exporter's oracle.
    quotient, remainder = divmod(a, b)
    if remainder and (a < 0) != (b < 0):
        quotient += 1
    overflow = int(quotient > 2 ** (p - 1) - 1)
    return [quotient % (2 ** p), (a - quotient * b) % (2 ** q), 1 - overflow, 0, overflow]


class SignedArithmeticTests(unittest.TestCase):
    def test_all_exported_forms_and_complete_tables(self):
        reports = read(OUTPUT / "verification.json")
        self.assertEqual(len(reports), 45)
        total = 0
        for kind in KINDS:
            template = Template(definition(kind))
            self.assertEqual(read(TEMPLATES / f"signed-{kind}.abstract.json"), template.to_dict())
            for p, q in product(WIDTHS, repeat=2):
                with self.subTest(kind=kind, p=p, q=q):
                    name = f"S{kind.upper()}<{p},{q}>"
                    prefix = OUTPUT / f"s{kind}-{p}-{q}"
                    program = template.instantiate({"p": p, "q": q})
                    hierarchy = BlockBundle(read(prefix.with_suffix(".block.json")))
                    expanded = hierarchy.expand()
                    circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                    compiled = synthesize(program)
                    dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                    self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                    self.assertEqual(hierarchy.to_dict(), bundle(kind, p, q).to_dict())
                    self.assertEqual(circuit, expanded.simplify())
                    self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"), netlist(circuit, program, name))
                    self.assertEqual([(port["name"], port["bits"]) for port in program.ports["inputs"]], [("a", p), ("b", q)])
                    self.assertFalse(any(port["signed"] for side in ("inputs", "outputs") for port in program.ports[side]))
                    self.assertEqual(len(dataset.rows), 2 ** (p + q))
                    for row in dataset.rows:
                        a, b = integer(row[:p]), integer(row[p:p+q])
                        wanted = expected(kind, a, b, p, q)
                        output = encoded(program, wanted)
                        self.assertEqual(row, bits(a, p) + bits(b, q) + output)
                        self.assertEqual(program.run(a | b << p), wanted)
                        for impl in (hierarchy, expanded, circuit, compiled):
                            self.assertEqual(impl.evaluate(row[:p+q]), output)
                        if kind == "cmp":
                            self.assertEqual(sum(wanted), 1)
                        if kind == "div" and wanted[2]:
                            sa, sb = decode(a, p), decode(b, q)
                            quotient, remainder = decode(wanted[0], p), decode(wanted[1], q)
                            self.assertEqual(sa, quotient * sb + remainder)
                            self.assertLess(abs(remainder), abs(sb))
                            self.assertTrue(remainder == 0 or (remainder < 0) == (sa < 0))
                    report = next(r for r in reports if r["name"] == name)
                    self.assertEqual(report["fitness"], fitness(circuit, dataset))
                    self.assertTrue(report["fitness"]["verified_truth_table"])
                    self.assertEqual(report["hierarchy"], hierarchy.summary())
                    total += len(dataset.rows)
        self.assertEqual(total, 2420)

    def test_division_zero_overflow_and_rounding(self):
        for p, q in product(WIDTHS, repeat=2):
            program = Template(definition("div")).instantiate({"p": p, "q": q})
            minimum, minus_one = 1 << (p - 1), (1 << q) - 1
            self.assertEqual(program.run(minimum | minus_one << p), [minimum, 0, 0, 0, 1])
            for a in range(1 << p):
                self.assertEqual(program.run(a), [0, 0, 0, 1, 0])
        program = Template(definition("div")).instantiate({"p": 4, "q": 4})
        for a, b, quotient, remainder in ((-7, 3, -2, -1), (7, -3, -2, 1), (-7, -3, 2, -1)):
            self.assertEqual(program.run(a % 16 | (b % 16) << 4), [quotient % 16, remainder % 16, 1, 0, 0])

    def test_larger_non_power_of_two_and_port_boundary_samples(self):
        rng = random.Random(20261110)
        for kind in KINDS:
            sizes = [(3, 5), (5, 3), (8, 8), (16, 16)]
            if kind in ("cmp", "add", "sub"):
                sizes += [(64, 64), (1, 127), (127, 1)]
            for p, q in sizes:
                with self.subTest(kind=kind, p=p, q=q):
                    program = Template(definition(kind)).instantiate({"p": p, "q": q})
                    values = lambda w: {0, 1, (1 << w) - 1, 1 << (w - 1), (1 << (w - 1)) - 1}
                    pairs = set(product(values(p), values(q)))
                    pairs.update((rng.getrandbits(p), rng.getrandbits(q)) for _ in range(6))
                    hardware = [synthesize(program), bundle(kind, p, q)] if max(p, q) <= 5 and kind != "div" else []
                    for a, b in pairs:
                        wanted = expected(kind, a, b, p, q)
                        self.assertEqual(program.run(a | b << p), wanted)
                        for impl in hardware:
                            self.assertEqual(impl.evaluate(bits(a, p) + bits(b, q)), encoded(program, wanted))

    def test_parameters_direct_call_and_gate_budgets(self):
        for kind in KINDS:
            invalid = [(0, 1), (1, 0), (-1, 2), (True, 1), (128, 1), (64, 65)]
            if kind in ("mul", "div"):
                invalid += [(17, 1), (1, 17), (23, 23)]
            if kind == "div":
                invalid += [(1, 125)]
            for p, q in invalid:
                with self.subTest(kind=kind, p=p, q=q), self.assertRaises(ValueError):
                    Template(definition(kind)).instantiate({"p": p, "q": q})
            # Public helper calls enforce the same conditions as specialization.
            document = definition(kind)
            document["source"] = document["source"].split("# Ergebnisport", 1)[0] + f"return S{kind.upper()}<0,1>(a,b)\n"
            document["interface"]["outputs"] = [{"name": "c", "bits": 1}]
            program = Template(document).instantiate({"p": 1, "q": 1})
            for build in (lambda: program.run(0), lambda: synthesize(program)):
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    build()
            # Find each equal-width construction boundary and verify rejection.
            previous = None
            for width in range(1, 65):
                try:
                    program = Template(definition(kind)).instantiate({"p": width, "q": width})
                    circuit = synthesize(program)
                except ValueError as exc:
                    self.assertIn("512", str(exc))
                    self.assertIsNotNone(previous)
                    self.assertLessEqual(len(previous.gates), 512)
                    break
                previous = circuit
            else:
                self.fail("Expected a construction gate limit")

    def test_migration_preserves_labels_folders_winners_and_deletions(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            organization = library._organization()
            organization["folders"].extend([
                {"id": "examples", "parent": None, "name": "Eigene Beispiele", "description": "Behalten"},
                {"id": "arithmetic", "parent": "examples", "name": "Eigene Rechner", "description": "Text"},
                {"id": "signed-arithmetic", "parent": "arithmetic", "name": "Signed angepasst", "description": "Notizen"},
            ])
            library._write_organization(organization)
            dataset = Dataset.from_dict(read(OUTPUT / "sadd-4-4.vectors.json"))
            saved = library.save_program({"circuit": read(OUTPUT / "sadd-4-4.circuit.json"), "note": "Eigene Lösung"}, dataset)
            key = next(d["function_id"] for d in library.datasets() if d["name"] == dataset.name)
            library.update_function(key, "Meine Addition", "Beschreibung")
            library.move_entry("function", key, "functions")
            template_key = library.save_template(Template(definition("add")))
            # Keep the template's implicit default folder too.
            smaller = Circuit(2, ((0, 1), (0, 2), (1, 2), (3, 4), (5, 5), (3, 3), (4, 4)), (7, 6, 8))
            small_dataset = Dataset.from_dict(read(OUTPUT / "scmp-1-1.vectors.json"))
            self.assertTrue(fitness(smaller, small_dataset)["verified_truth_table"])
            better = library.save_program({"circuit": smaller.to_dict(), "note": "Sieben NANDs"}, small_dataset)
            before_tree = library.tree()
            install_signed_arithmetic_examples(library)
            self.assertTrue(read(Path(directory) / "example-installations.json")["signed-arithmetic-v1"])
            self.assertEqual(library.tree()["folders"], before_tree["folders"])
            self.assertTrue(before_tree["entries"].items() <= library.tree()["entries"].items())
            self.assertEqual((len(library.templates()), len(library.datasets()), len(library.blocks())), (5, 45, 45))
            winners = {p["dataset_name"]: p for p in library.programs()}
            self.assertEqual(winners["Meine Addition"]["id"], saved["id"])
            self.assertEqual(winners[small_dataset.name]["id"], better["id"])
            self.assertEqual(winners[small_dataset.name]["note"], "Sieben NANDs")
            library.delete_function(key)
            (Path(directory) / "templates" / f"{template_key}.json").unlink()
            block = next(b for b in library.blocks() if b["name"] == "SDIV<4,4>")
            (Path(directory) / "blocks" / f"{block['id']}.json").unlink()
            before = {p: p.read_bytes() for p in Path(directory).rglob("*.json")}
            install_signed_arithmetic_examples(Library(directory))
            self.assertEqual({p: p.read_bytes() for p in Path(directory).rglob("*.json")}, before)

    def test_http_upgrade_catalog_synthesis_and_blocks(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            previous = ("multipliers", "signed", "saturating", "parallel-add", "prefixes", "arithmetic", "recursive-checked",
                        "recursive-mul", "number-of-ones", "recursive-msb-div", "recursive-max-index", "recursive-equ",
                        "recursive-gt", "generative-logic", "routing", "structured-logic", "standard-arithmetic",
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
                self.assertEqual((len(catalog["templates"]), len(catalog["datasets"]), len(catalog["blocks"])), (5, 45, 45))
                for kind in KINDS:
                    template = next(t for t in catalog["templates"] if t["name"] == f"S{kind.upper()}<p,q>")
                    saved = request("/api/templates/synthesize", {"template_id": template["id"],
                        "parameters": {"p": 4, "q": 4}, "samples": 256, "name": f"S{kind.upper()} HTTP"})
                    self.assertTrue(saved["result"]["fitness"]["verified_truth_table"])
                    block = next(b for b in catalog["blocks"] if b["name"] == f"S{kind.upper()}<4,4>")
                    program = Template(definition(kind)).instantiate({"p": 4, "q": 4})
                    for a, b in ((0, 0), (8, 15), (9, 3), (7, 13), (9, 13), (7, 7)):
                        evaluated = request("/api/blocks/evaluate", {"block_id": block["id"], "bits": bits(a, 4) + bits(b, 4)})
                        self.assertEqual(evaluated["outputs"], encoded(program, expected(kind, a, b, 4, 4)))
                    view = request("/api/blocks/view", {"block_id": block["id"], "path": []})
                    self.assertGreater(len(view["circuit"]["gates"]), 0)
            finally:
                server.shutdown()
                server.server_close()
                server.executor.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

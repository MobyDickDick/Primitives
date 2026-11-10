"""GEN-08: independent saturation, exact boundaries, exports and library upgrades."""
from itertools import product
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
from primitives.examples import install_examples, install_saturating_examples
from primitives.library import Library, fitness
from primitives.server import make_server
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import ports
from tools.export_generative import netlist
from tools.export_saturating import (KINDS, FLAGS, ROOT, TEMPLATES, OUTPUT, WIDTHS,
                                     bundle, component, definition)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def expected(kind, a, b, width):
    """Signed integer arithmetic with explicit clamping, no carry/borrow logic."""
    value = a + b if kind == "add" else a - b
    limit = (1 << width) - 1
    flag = int(value > limit if kind == "add" else value < 0)
    return [limit if value > limit else 0 if value < 0 else value, flag]


class SaturatingTests(unittest.TestCase):
    def test_all_exported_forms_tables_flags_and_exact_boundaries(self):
        reports = read(OUTPUT / "verification.json")
        self.assertEqual(len(reports), 18)
        total = 0
        for kind in KINDS:
            template = Template(definition(kind))
            self.assertEqual(read(TEMPLATES / f"sat-{kind}.abstract.json"), template.to_dict())
            for p, q in product(WIDTHS, repeat=2):
                with self.subTest(kind=kind, p=p, q=q):
                    w, name = max(p, q), f"SAT_{kind.upper()}<{p},{q}>"
                    prefix = OUTPUT / f"sat-{kind}-{p}-{q}"
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
                    self.assertEqual([(x["name"], x["bits"]) for x in program.ports["inputs"]], [("a", p), ("b", q)])
                    self.assertEqual([(x["name"], x["bits"]) for x in program.ports["outputs"]], [("c", w), (FLAGS[kind], 1)])
                    self.assertEqual(len(dataset.rows), 1 << (p + q))
                    seen_flags, seen_boundary = set(), False
                    for row in dataset.rows:
                        inputs = row[:p + q]
                        a, b = integer(inputs[:p]), integer(inputs[p:])
                        wanted = expected(kind, a, b, w)
                        encoded = bits(wanted[0], w) + [wanted[1]]
                        self.assertEqual(row, inputs + encoded)
                        self.assertEqual(program.run(a | b << p), wanted)
                        for impl in (hierarchy, expanded, circuit, compiled):
                            self.assertEqual(impl.evaluate(inputs), encoded)
                        seen_flags.add(wanted[1])
                        boundary = a + b == (1 << w) - 1 if kind == "add" else a == b
                        if boundary:
                            self.assertEqual(wanted[1], 0)
                            seen_boundary = True
                    self.assertEqual(seen_flags, {0, 1})
                    self.assertTrue(seen_boundary)
                    report = next(r for r in reports if r["name"] == name)
                    self.assertEqual(report["fitness"], fitness(circuit, dataset))
                    self.assertTrue(report["fitness"]["verified_truth_table"])
                    self.assertEqual(report["hierarchy"], hierarchy.summary())
                    total += len(dataset.rows)
        self.assertEqual(total, 968)

    def test_saturation_stages_for_all_values_and_both_flags(self):
        # Include raw words/flags that are unreachable for some operand widths.
        for kind, w in product(KINDS, WIDTHS):
            stage = component(kind, w, w, "Saturation stage",
                ports([("value", w), ("flag", 1)], [("c", w), (FLAGS[kind], 1)]),
                f"result = bits(Sat{kind.title()}Clamp<{w}>(value,flag), {w + 1})\n"
                f"return pack(result[:{w}]), result[{w}]")
            circuit = synthesize(stage)
            for value, flag in product(range(1 << w), (0, 1)):
                wanted = value if not flag else (1 << w) - 1 if kind == "add" else 0
                self.assertEqual(stage.run(value | flag << w), [wanted, flag])
                self.assertEqual(circuit.evaluate(bits(value, w) + [flag]), bits(wanted, w) + [flag])

    def test_larger_and_non_power_of_two_widths_with_boundary_samples(self):
        rng = random.Random(20261107)
        for kind in KINDS:
            for p, q in ((3, 5), (5, 3), (8, 8), (16, 16), (32, 32), (64, 64), (1, 64), (64, 1)):
                w = max(p, q)
                program = Template(definition(kind)).instantiate({"p": p, "q": q})
                hardware = [synthesize(program), bundle(kind, p, q)] if w <= 16 else []
                if kind == "add" and w == 32:
                    hardware = [synthesize(program), bundle(kind, p, q)]
                if kind == "sub" and w == 32:
                    hardware = [bundle(kind, p, q)]
                ap, bq = (1 << p) - 1, (1 << q) - 1
                pairs = {(0, 0), (ap, bq), (ap, 0), (0, bq), (ap, 1), (1, bq), (1, 1)}
                pairs.update((rng.getrandbits(p), rng.getrandbits(q)) for _ in range(4))
                # Exact upper boundary and first overflow; equality and first underflow.
                pairs.update(((1 << w) - 1 - b, b) for b in (0, 1, bq) if 0 <= (1 << w) - 1 - b <= ap)
                pairs.update((x, x) for x in (0, 1, min(ap, bq)))
                pairs.update((x - 1, x) for x in (1, min(ap, bq)))
                for a, b in pairs:
                    wanted = expected(kind, a, b, w)
                    self.assertEqual(program.run(a | b << p), wanted)
                    for impl in hardware:
                        self.assertEqual(impl.evaluate(bits(a, p) + bits(b, q)), bits(wanted[0], w) + [wanted[1]])

    def test_parameter_direct_call_port_and_gate_limits(self):
        for kind in KINDS:
            for p, q in ((0, 1), (-1, 1), (1, 0), (128, 1), (1, 128), (65, 64), (1, True)):
                with self.subTest(kind=kind, p=p, q=q), self.assertRaises(ValueError):
                    Template(definition(kind)).instantiate({"p": p, "q": q})
            for call in (f"SAT_{kind.upper()}<0,1>(a,b)", f"SAT_{kind.upper()}<65,64>(a,b)",
                         f"Sat{kind.title()}Raw<128,1>(a,b)", f"Sat{kind.title()}Clamp<0>(a,b)",
                         f"Sat{kind.title()}Clamp<128>(a,b)"):
                program = component(kind, 1, 1, "Invalid call", ports([("a", 1), ("b", 1)], [("c", 1)]), f"return {call}")
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    program.run(0)
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    synthesize(program)
            direct_limit, box_limit = (39, 46) if kind == "add" else (30, 34)
            for w in (direct_limit, box_limit):
                block = bundle(kind, w, w)
                circuit = block.expand().simplify()
                self.assertLessEqual(len(circuit.gates), 512)
                program = Template(definition(kind)).instantiate({"p": w, "q": w})
                if w == direct_limit:
                    direct = synthesize(program)
                else:
                    with self.assertRaisesRegex(ValueError, "512"):
                        synthesize(program)
                for a, b in ((0, 0), ((1 << w) - 1, 1), (0, 1)):
                    wanted = expected(kind, a, b, w)
                    self.assertEqual(program.run(a | b << w), wanted)
                    self.assertEqual(circuit.evaluate(bits(a, w) + bits(b, w)), bits(wanted[0], w) + [wanted[1]])
                    if w == direct_limit:
                        self.assertEqual(direct.evaluate(bits(a, w) + bits(b, w)), bits(wanted[0], w) + [wanted[1]])
            with self.assertRaisesRegex(ValueError, "512"):
                synthesize(Template(definition(kind)).instantiate({"p": direct_limit + 1, "q": direct_limit + 1}))
            with self.assertRaisesRegex(ValueError, "512"):
                bundle(kind, box_limit + 1, box_limit + 1)
            for p, q in ((127, 1), (1, 127)):
                program = Template(definition(kind)).instantiate({"p": p, "q": q})
                self.assertEqual(sum(x["bits"] for x in program.ports["inputs"]), 128)
                self.assertEqual(sum(x["bits"] for x in program.ports["outputs"]), 128)
                with self.assertRaisesRegex(ValueError, "Anweisungsbudget"):
                    program.run(0)

    def test_migration_preserves_customizations_solutions_and_deletions(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            install_examples(library)
            self.assertFalse(any(t["name"].startswith("SAT_") for t in library.templates()))
            library.save_folder("Meine Rechner", "Beschreibung", "examples", "arithmetic")
            entries = library.tree()["entries"].copy()
            dataset = Dataset.from_dict(read(OUTPUT / "sat-add-4-4.vectors.json"))
            circuit = read(OUTPUT / "sat-add-4-4.circuit.json")
            saved = library.save_program({"circuit": circuit, "note": "Eigene Lösung"}, dataset)
            # One-bit saturating addition is simply OR plus AND (5 NANDs),
            # smaller than the generic ripple-and-clamp construction (7).
            small_dataset = Dataset.from_dict(read(OUTPUT / "sat-add-1-1.vectors.json"))
            smaller = Circuit(2, ((0, 0), (1, 1), (2, 3), (0, 1), (5, 5)), (4, 6))
            self.assertTrue(fitness(smaller, small_dataset)["verified_truth_table"])
            better = library.save_program({"circuit": smaller.to_dict(), "note": "Kleinere Lösung"}, small_dataset)
            key = next(d["function_id"] for d in library.datasets() if d["name"] == dataset.name)
            library.update_function(key, "Mein Rechner", "Notizen")
            library.move_entry("function", key, "functions")
            template_key = library.save_template(Template(definition("add")))
            library.move_entry("template", template_key, "templates")
            install_saturating_examples(library)
            self.assertTrue(read(Path(directory) / "example-installations.json")["saturating-v1"])
            self.assertTrue(entries.items() <= library.tree()["entries"].items())
            folder = next(f for f in library.tree()["folders"] if f["id"] == "arithmetic")
            self.assertEqual((folder["name"], folder["description"]), ("Meine Rechner", "Beschreibung"))
            winner = next(p for p in library.programs() if p["dataset_name"] == "Mein Rechner")
            self.assertEqual((winner["id"], winner["note"]), (saved["id"], "Eigene Lösung"))
            small_winner = next(p for p in library.programs() if p["dataset_name"] == small_dataset.name)
            self.assertEqual((small_winner["id"], small_winner["note"]), (better["id"], "Kleinere Lösung"))
            self.assertEqual(library.tree()["entries"][f"function:{key}"], "functions")
            self.assertEqual(library.tree()["entries"][f"template:{template_key}"], "templates")
            self.assertEqual(len([b for b in library.blocks() if b["name"].startswith("SAT_")]), 18)
            new = [d for d in library.datasets() if d["name"].startswith("SAT_")]
            self.assertEqual(len(new), 17)  # The eighteenth function was renamed above.
            library.delete_function(new[0]["function_id"])
            (Path(directory) / "templates" / f"{template_key}.json").unlink()
            block = next(b for b in library.blocks() if b["name"] == "SAT_SUB<4,4>")
            (Path(directory) / "blocks" / f"{block['id']}.json").unlink()
            before = {p: p.read_bytes() for p in Path(directory).rglob("*.json")}
            install_saturating_examples(Library(directory))
            self.assertEqual({p: p.read_bytes() for p in Path(directory).rglob("*.json")}, before)

    def test_server_upgrade_synthesis_evaluation_and_hierarchy_navigation(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            previous = ("signed-arithmetic", "signed", "arithmetic", "recursive-checked", "recursive-mul", "number-of-ones",
                        "recursive-msb-div", "recursive-max-index", "recursive-equ", "recursive-gt",
                        "generative-logic", "routing", "structured-logic", "standard-arithmetic",
                        "arithmetic-comments", "zero-counts", "priority-encoder", "onehot", "barrel-shifter",
                        "rotations", "prefixes", "parallel-add")
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
                    template = next(t for t in catalog["templates"] if t["name"] == f"SAT_{kind.upper()}<p,q>")
                    saved = request("/api/templates/synthesize", {"template_id": template["id"],
                        "parameters": {"p": 4, "q": 4}, "samples": 256, "name": f"SAT_{kind.upper()} HTTP"})
                    self.assertTrue(saved["result"]["fitness"]["verified_truth_table"])
                    block = next(b for b in catalog["blocks"] if b["name"] == f"SAT_{kind.upper()}<4,4>")
                    for a, b in ((0, 0), (15, 0), (15, 1), (0, 1), (15, 15), (5, 10)):
                        evaluated = request("/api/blocks/evaluate", {"block_id": block["id"], "bits": bits(a, 4) + bits(b, 4)})
                        wanted = expected(kind, a, b, 4)
                        self.assertEqual(evaluated["outputs"], bits(wanted[0], 4) + [wanted[1]])
                    view = request("/api/blocks/view", {"block_id": block["id"], "path": []})
                    self.assertEqual([n["id"] for n in view["circuit"]["view_nodes"] if n["kind"] == "instance"],
                                     ["arithmetic", "saturate"])
                    view = request("/api/blocks/view", {"block_id": block["id"], "path": ["saturate"]})
                    self.assertGreater(len(view["circuit"]["gates"]), 0)
            finally:
                server.shutdown()
                server.server_close()
                server.executor.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

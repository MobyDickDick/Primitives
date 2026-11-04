"""GEN-04: exhaustive bit-position oracle, exports, boundaries and migration."""
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
from primitives.examples import install_examples, install_barrel_shifter_examples
from primitives.library import Library, fitness
from primitives.server import make_server
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_barrel_shifter import KINDS, WIDTHS, OUTPUT, ROOT, TEMPLATES, bundle, definition, label
from tools.export_generative import netlist


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def expected(kind, t, a, s):
    # Track each output position; no arithmetic shift or shared export oracle.
    source = bits(a, t)
    result = []
    for i in range(t):
        position = i - s if kind == "shl" else i + s
        result.append(source[position] if 0 <= position < t else source[-1] if kind == "sar" else 0)
    return integer(result)


class BarrelShifterTests(unittest.TestCase):
    def test_all_tables_programs_and_hardware_forms(self):
        total = 0
        for kind in KINDS:
            template = Template(definition(kind))
            self.assertEqual(read(TEMPLATES / f"barrel-{kind}.abstract.json"), template.to_dict())
            reports = read(OUTPUT / f"barrel-{kind}/verification.json")
            self.assertEqual(len(reports), 9)
            for t in WIDTHS:
                for s_bits in WIDTHS:
                    with self.subTest(kind=kind, t=t, s_bits=s_bits):
                        prefix = OUTPUT / f"barrel-{kind}/{kind}-{t}-{s_bits}"
                        program = template.instantiate({"t": t, "s_bits": s_bits})
                        hierarchy = BlockBundle(read(prefix.with_suffix(".block.json")))
                        expanded = hierarchy.expand()
                        circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                        compiled = synthesize(program)
                        dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                        self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                        self.assertEqual(hierarchy.to_dict(), bundle(kind, t, s_bits).to_dict())
                        self.assertEqual(circuit, expanded.simplify())
                        self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"),
                                         netlist(circuit, program, label(kind, t, s_bits)))
                        self.assertEqual([p["bits"] for p in program.ports["inputs"]], [t, s_bits])
                        self.assertEqual([p["bits"] for p in program.ports["outputs"]], [t])
                        self.assertEqual(len(dataset.rows), 1 << (t + s_bits))
                        for row in dataset.rows:
                            value = integer(row[:dataset.inputs])
                            inputs = bits(value, t + s_bits)
                            result = expected(kind, t, value % (1 << t), value >> t)
                            self.assertEqual(row, inputs + bits(result, t))
                            self.assertEqual(program.run(value), [result])
                            for impl in (hierarchy, expanded, circuit, compiled):
                                self.assertEqual(impl.evaluate(inputs), bits(result, t))
                        report = next(r for r in reports if r["parameters"] == {"t": t, "s_bits": s_bits})
                        self.assertEqual(report["fitness"], fitness(circuit, dataset))
                        self.assertTrue(report["fitness"]["verified_truth_table"])
                        self.assertEqual(report["hierarchy"], hierarchy.summary())
                        self.assertEqual(sum(n["kind"] == "instance" for n in hierarchy.view()["circuit"]["view_nodes"]), s_bits)
                        total += len(dataset.rows)
        self.assertEqual(total, 1452)

    def test_larger_and_non_power_of_two_widths(self):
        rng = random.Random(20261102)
        # Explicitly sampled; includes both total-port boundaries and highest selector bit.
        for t, s_bits in ((3, 3), (8, 4), (16, 4), (32, 6), (64, 4), (127, 1), (1, 127)):
            for kind in KINDS:
                program = Template(definition(kind)).instantiate({"t": t, "s_bits": s_bits})
                hardware = [synthesize(program), bundle(kind, t, s_bits)] if t <= 16 or t == 1 else []
                distances = {s for s in (0, 1, t - 1, t, t + 1, (1 << s_bits) - 1, 1 << (s_bits - 1))
                             if 0 <= s < (1 << s_bits)}
                values = {0, 1, (1 << t) - 1, 1 << (t - 1), (1 << (t - 1)) - 1}
                values.update(rng.getrandbits(t) for _ in range(4))
                for a in values:
                    for s in distances:
                        result = expected(kind, t, a, s)
                        value = a | (s << t)
                        self.assertEqual(program.run(value), [result], (kind, t, s_bits, a, s))
                        for impl in hardware:
                            self.assertEqual(impl.evaluate(bits(value, t + s_bits)), bits(result, t))

    def test_parameters_call_guards_and_gate_limit(self):
        for kind in KINDS:
            for t, s_bits in ((0, 1), (-1, 1), (1, 0), (128, 1), (64, 65), (True, 1), (1, True)):
                with self.subTest(kind=kind, t=t, s_bits=s_bits), self.assertRaises(ValueError):
                    Template(definition(kind)).instantiate({"t": t, "s_bits": s_bits})
            for call in (f"{kind.upper()}<0,1>(a, s)", f"{kind.upper()}<128,1>(a, s)",
                         f"{kind.upper()}Stage<1,0>(a, s)"):
                document = definition(kind)
                document["source"] = document["source"].split("# Ergebnisport", 1)[0] + f"return {call}\n"
                program = Template(document).instantiate({"t": 1, "s_bits": 1})
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    program.run(0)
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    synthesize(program)
            program = Template(definition(kind)).instantiate({"t": 64, "s_bits": 6})
            self.assertEqual(program.run(0), [0])
            with self.assertRaisesRegex(ValueError, "512"):
                synthesize(program)
            with self.assertRaisesRegex(ValueError, "512"):
                bundle(kind, 64, 6)
            large = Template(definition(kind)).instantiate({"t": 64, "s_bits": 64})
            with self.assertRaisesRegex(ValueError, "Anweisungsbudget"):
                large.run(0)

    def test_migration_keeps_user_data_and_deleted_examples(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            install_examples(library)
            self.assertFalse(any(t["name"].startswith(("SHL<", "SHR<", "SAR<")) for t in library.templates()))
            library.save_folder("Meine Rekursion", "Eigener Text", "examples", "recursion")
            entries = library.tree()["entries"].copy()
            install_barrel_shifter_examples(library)
            self.assertTrue(read(Path(directory) / "example-installations.json")["barrel-shifter-v1"])
            self.assertTrue(entries.items() <= library.tree()["entries"].items())
            folder = next(f for f in library.tree()["folders"] if f["id"] == "recursion")
            self.assertEqual((folder["name"], folder["description"]), ("Meine Rekursion", "Eigener Text"))
            new = [d for d in library.datasets() if d["name"].startswith(("SHL<", "SHR<", "SAR<"))]
            self.assertEqual(len(new), 27)
            key = new[0]["function_id"]
            library.update_function(key, "Meine Verschiebung", "Meine Beschreibung")
            library.move_entry("function", key, "functions")
            library.delete_function(new[1]["function_id"])
            template = next(t for t in library.templates() if t["name"] == "SHL<t,s_bits>")
            (Path(directory) / "templates" / f"{template['id']}.json").unlink()
            block = next(b for b in library.blocks() if b["name"] == "SAR<4,4>")
            (Path(directory) / "blocks" / f"{block['id']}.json").unlink()
            before = {p: p.read_bytes() for p in Path(directory).rglob("*.json")}
            install_barrel_shifter_examples(Library(directory))
            self.assertEqual({p: p.read_bytes() for p in Path(directory).rglob("*.json")}, before)

    def test_upgrade_preserves_better_circuit_and_assignments(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            prefix = OUTPUT / "barrel-shl/shl-4-4"
            dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
            document = definition("shl")
            document["source"] = document["source"].split("# Ergebnisport", 1)[0] + """
sh = bits(s, 4)
x = bits(SHL<t,2>(a, pack(sh[:2])), t)
en = (1 ^ sh[2]) & (1 ^ sh[3])
y = []
for i in range(t):
    y = y + [x[i] & en]
return pack(y)
"""
            circuit = synthesize(Template(document).instantiate({"t": 4, "s_bits": 4}))
            self.assertTrue(fitness(circuit, dataset)["verified_truth_table"])
            self.assertLess(len(circuit.gates), len(read(prefix.with_suffix(".circuit.json"))["gates"]))
            saved = library.save_program({"circuit": circuit.to_dict(), "note": "Eigene bessere Lösung"}, dataset)
            key = library.datasets()[0]["function_id"]
            library.update_function(key, "Eigener Name", "Erhalten")
            library.move_entry("function", key, "functions")
            template_key = library.save_template(Template(definition("shl")))
            library.move_entry("template", template_key, "templates")
            install_barrel_shifter_examples(library)
            self.assertEqual(library.load_program(saved["id"])["note"], "Eigene bessere Lösung")
            self.assertEqual(library.tree()["entries"][f"function:{key}"], "functions")
            self.assertEqual(library.tree()["entries"][f"template:{template_key}"], "templates")
            self.assertEqual(next(d for d in library.datasets() if d["function_id"] == key)["name"], "Eigener Name")
            self.assertEqual((len(library.templates()), len(library.datasets()), len(library.blocks())), (3, 27, 27))

    def test_server_upgrade_catalog_synthesis_and_stage_navigation(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            previous = ("prefixes", "arithmetic", "recursive-checked", "recursive-mul", "number-of-ones",
                        "recursive-msb-div", "recursive-max-index", "recursive-equ", "recursive-gt",
                        "generative-logic", "routing", "structured-logic", "standard-arithmetic",
                        "arithmetic-comments", "zero-counts", "priority-encoder", "onehot", "rotations")
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
                self.assertEqual((len(catalog["templates"]), len(catalog["datasets"]), len(catalog["blocks"])), (3, 27, 27))
                for kind in KINDS:
                    template = next(t for t in catalog["templates"] if t["name"] == label(kind, "t", "s_bits"))
                    saved = request("/api/templates/synthesize", {
                        "template_id": template["id"], "parameters": {"t": 4, "s_bits": 4},
                        "samples": 256, "name": f"{kind} HTTP"})
                    self.assertTrue(saved["result"]["fitness"]["verified_truth_table"])
                    block = next(b for b in catalog["blocks"] if b["name"] == label(kind, 4, 4))
                    for a, s in ((0, 0), (15, 0), (8, 1), (7, 4), (8, 15)):
                        evaluation = request("/api/blocks/evaluate", {"block_id": block["id"], "bits": bits(a | (s << 4), 8)})
                        self.assertEqual(evaluation["outputs"], bits(expected(kind, 4, a, s), 4))
                    view = request("/api/blocks/view", {"block_id": block["id"], "path": ["shift_1"]})
                    self.assertGreater(len(view["circuit"]["gates"]), 0)
            finally:
                server.shutdown()
                server.server_close()
                server.executor.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

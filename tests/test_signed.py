"""GEN-09: signed semantics, minimum overflow, exports and library upgrades."""
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
from primitives.examples import install_signed_examples
from primitives.library import Library, fitness
from primitives.server import make_server
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import ports
from tools.export_generative import netlist
from tools.export_signed import KINDS, ROOT, TEMPLATES, OUTPUT, WIDTHS, bundle, component, definition


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def expected(kind, value, width):
    # Decode by subtracting the unsigned sign weight; avoid bit-level carry logic.
    sign, low = divmod(value, 2 ** (width - 1))
    signed = low - sign * 2 ** (width - 1)
    if kind == "sign":
        return [int(signed < 0)]
    result = -signed if kind == "neg" else abs(signed)
    overflow = int(not -(2 ** (width - 1)) <= result < 2 ** (width - 1))
    return [result % (2 ** width), overflow]


def encoded(kind, result, width):
    return result if kind == "sign" else bits(result[0], width) + [result[1]]


class SignedTests(unittest.TestCase):
    def test_all_exported_forms_tables_and_signed_boundaries(self):
        reports = read(OUTPUT / "verification.json")
        self.assertEqual(len(reports), 9)
        total = 0
        for kind in KINDS:
            template = Template(definition(kind))
            self.assertEqual(read(TEMPLATES / f"signed-{kind}.abstract.json"), template.to_dict())
            for width in WIDTHS:
                with self.subTest(kind=kind, width=width):
                    name = f"{kind.upper()}<{width}>"
                    prefix = OUTPUT / f"{kind}-{width}"
                    program = template.instantiate({"t": width})
                    hierarchy = BlockBundle(read(prefix.with_suffix(".block.json")))
                    expanded = hierarchy.expand()
                    circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                    compiled = synthesize(program)
                    dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                    self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                    self.assertEqual(hierarchy.to_dict(), bundle(kind, width).to_dict())
                    self.assertEqual(circuit, expanded.simplify())
                    self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"), netlist(circuit, program, name))
                    self.assertEqual([(p["name"], p["bits"]) for p in program.ports["inputs"]], [("a", width)])
                    self.assertEqual([(p["name"], p["bits"]) for p in program.ports["outputs"]],
                                     [("negative", 1)] if kind == "sign" else [("c", width), ("overflow", 1)])
                    self.assertEqual(len(dataset.rows), 1 << width)
                    for row in dataset.rows:
                        value = integer(row[:width])
                        wanted = expected(kind, value, width)
                        output = encoded(kind, wanted, width)
                        self.assertEqual(row, bits(value, width) + output)
                        self.assertEqual(program.run(value), wanted)
                        for impl in (hierarchy, expanded, circuit, compiled):
                            self.assertEqual(impl.evaluate(bits(value, width)), output)
                        if kind != "sign":
                            self.assertEqual(wanted[1], int(value == 1 << (width - 1)))
                    report = next(r for r in reports if r["name"] == name)
                    self.assertEqual(report["fitness"], fitness(circuit, dataset))
                    self.assertTrue(report["fitness"]["verified_truth_table"])
                    self.assertEqual(report["hierarchy"], hierarchy.summary())
                    total += len(dataset.rows)
        self.assertEqual(total, 66)

    def test_involution_absolute_value_and_minimum_representation(self):
        for width in (1, 2, 3, 4, 5):
            neg = Template(definition("neg")).instantiate({"t": width})
            absolute = Template(definition("abs")).instantiate({"t": width})
            sign = Template(definition("sign")).instantiate({"t": width})
            minimum = 1 << (width - 1)
            for value in range(1 << width):
                n, overflow = neg.run(value)
                a, abs_overflow = absolute.run(value)
                self.assertEqual(neg.run(n)[0], value)
                self.assertEqual(absolute.run(n), [a, abs_overflow])
                self.assertEqual(absolute.run(a), [a, abs_overflow])
                self.assertEqual(sign.run(a), [int(abs_overflow != 0)])
                if value == minimum:
                    self.assertEqual((n, overflow, a, abs_overflow), (minimum, 1, minimum, 1))
                elif value == 0:
                    self.assertEqual((n, overflow, a, abs_overflow), (0, 0, 0, 0))

    def test_conditional_negation_stage_for_both_control_values(self):
        for width in WIDTHS:
            stage = component("abs", width, "Conditional negation",
                ports([("a", width), ("flip", 1)], [("c", width)]),
                f"return FlipAddOne<{width}>(a, flip)")
            circuit = synthesize(stage)
            for value in range(1 << width):
                for flip in (0, 1):
                    wanted = (-value if flip else value) % (1 << width)
                    self.assertEqual(stage.run(value | flip << width), [wanted])
                    self.assertEqual(circuit.evaluate(bits(value, width) + [flip]), bits(wanted, width))

    def test_larger_and_non_power_of_two_references_with_boundary_samples(self):
        rng = random.Random(20261108)
        for kind in KINDS:
            for width in (3, 5, 8, 16, 32, 64, 127, *([128] if kind == "sign" else [])):
                with self.subTest(kind=kind, width=width):
                    program = Template(definition(kind)).instantiate({"t": width})
                    hardware = [synthesize(program), bundle(kind, width)] if width <= 32 or kind == "sign" else []
                    if kind == "neg" and width == 64:
                        hardware = [synthesize(program)]
                    minimum, mask = 1 << (width - 1), (1 << width) - 1
                    values = {0, 1, mask, minimum, minimum - 1, minimum + 1}
                    values.update(rng.getrandbits(width) for _ in range(8))
                    for value in values:
                        wanted = expected(kind, value, width)
                        self.assertEqual(program.run(value), wanted)
                        for impl in hardware:
                            self.assertEqual(impl.evaluate(bits(value, width)), encoded(kind, wanted, width))

    def test_parameter_direct_call_port_and_gate_limits(self):
        for kind in KINDS:
            maximum = 128 if kind == "sign" else 127
            for width in (0, -1, maximum + 1, True):
                with self.subTest(kind=kind, width=width), self.assertRaises(ValueError):
                    Template(definition(kind)).instantiate({"t": width})
            for width in (0, maximum + 1):
                program = component(kind, 1, "Invalid direct call", ports([("a", 1)], [("c", 1)]),
                                    f"return {kind.upper()}<{width}>(a)")
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    program.run(0)
                with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                    synthesize(program)
            program = Template(definition(kind)).instantiate({"t": maximum})
            self.assertEqual(sum(p["bits"] for p in program.ports["inputs"]), maximum)
            self.assertEqual(sum(p["bits"] for p in program.ports["outputs"]), 1 if kind == "sign" else 128)
            for value in (0, 1 << (maximum - 1), (1 << maximum) - 1):
                self.assertEqual(program.run(value), expected(kind, value, maximum))
        for kind, direct_limit, box_limit in (("neg", 85, 57), ("abs", 43, 43)):
            for limit, build in ((direct_limit, lambda w: synthesize(Template(definition(kind)).instantiate({"t": w}))),
                                 (box_limit, lambda w: bundle(kind, w).expand().simplify())):
                circuit = build(limit)
                self.assertLessEqual(len(circuit.gates), 512)
                for value in (0, 1, (1 << limit) - 1, 1 << (limit - 1)):
                    self.assertEqual(circuit.evaluate(bits(value, limit)), encoded(kind, expected(kind, value, limit), limit))
                with self.assertRaisesRegex(ValueError, "512"):
                    build(limit + 1)

    def test_migration_preserves_customizations_solutions_and_deletions(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            organization = library._organization()
            organization["folders"].extend([
                {"id": "examples", "parent": None, "name": "Meine Beispiele", "description": "Erhalten"},
                {"id": "arithmetic", "parent": "examples", "name": "Meine Rechner", "description": "Beschreibung"},
                {"id": "signed", "parent": "arithmetic", "name": "Meine Vorzeichen", "description": "Eigener Text"},
            ])
            library._write_organization(organization)
            dataset = Dataset.from_dict(read(OUTPUT / "abs-4.vectors.json"))
            saved = library.save_program({"circuit": read(OUTPUT / "abs-4.circuit.json"), "note": "Eigene Lösung"}, dataset)
            # Seven NANDs beat the generic eight-NAND NEG<2> construction.
            smaller = Circuit(2, ((0, 1), (0, 2), (1, 2), (3, 4), (0, 0), (1, 6), (7, 7)), (0, 5, 8))
            small_dataset = Dataset.from_dict(read(OUTPUT / "neg-2.vectors.json"))
            self.assertTrue(fitness(smaller, small_dataset)["verified_truth_table"])
            better = library.save_program({"circuit": smaller.to_dict(), "note": "Kleinere Lösung"}, small_dataset)
            key = next(d["function_id"] for d in library.datasets() if d["name"] == dataset.name)
            library.update_function(key, "Mein Absolutwert", "Notizen")
            library.move_entry("function", key, "functions")
            template_key = library.save_template(Template(definition("abs")))
            library.move_entry("template", template_key, "templates")
            before_tree = library.tree()
            install_signed_examples(library)
            self.assertTrue(read(Path(directory) / "example-installations.json")["signed-v1"])
            self.assertTrue(before_tree["entries"].items() <= library.tree()["entries"].items())
            self.assertEqual(library.tree()["folders"], before_tree["folders"])
            winner = next(p for p in library.programs() if p["dataset_name"] == "Mein Absolutwert")
            self.assertEqual((winner["id"], winner["note"]), (saved["id"], "Eigene Lösung"))
            small_winner = next(p for p in library.programs() if p["dataset_name"] == small_dataset.name)
            self.assertEqual((small_winner["id"], small_winner["note"]), (better["id"], "Kleinere Lösung"))
            self.assertEqual((len(library.templates()), len(library.datasets()), len(library.blocks())), (3, 9, 9))
            chosen = next(d for d in library.datasets() if d["name"] == "NEG<4>")
            library.delete_function(chosen["function_id"])
            (Path(directory) / "templates" / f"{template_key}.json").unlink()
            block = next(b for b in library.blocks() if b["name"] == "ABS<4>")
            (Path(directory) / "blocks" / f"{block['id']}.json").unlink()
            before = {p: p.read_bytes() for p in Path(directory).rglob("*.json")}
            install_signed_examples(Library(directory))
            self.assertEqual({p: p.read_bytes() for p in Path(directory).rglob("*.json")}, before)

    def test_server_upgrade_synthesis_evaluation_and_hierarchy_navigation(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            previous = ("signed-arithmetic", "arithmetic", "recursive-checked", "recursive-mul", "number-of-ones",
                        "recursive-msb-div", "recursive-max-index", "recursive-equ", "recursive-gt",
                        "generative-logic", "routing", "structured-logic", "standard-arithmetic",
                        "arithmetic-comments", "zero-counts", "priority-encoder", "onehot", "barrel-shifter",
                        "rotations", "prefixes", "parallel-add", "saturating")
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
                self.assertEqual((len(catalog["templates"]), len(catalog["datasets"]), len(catalog["blocks"])), (3, 9, 9))
                for kind in KINDS:
                    template = next(t for t in catalog["templates"] if t["name"] == f"{kind.upper()}<t>")
                    saved = request("/api/templates/synthesize", {"template_id": template["id"],
                        "parameters": {"t": 4}, "samples": 16, "name": f"{kind.upper()} HTTP"})
                    self.assertTrue(saved["result"]["fitness"]["verified_truth_table"])
                    block = next(b for b in catalog["blocks"] if b["name"] == f"{kind.upper()}<4>")
                    for value in range(16):
                        evaluated = request("/api/blocks/evaluate", {"block_id": block["id"], "bits": bits(value, 4)})
                        self.assertEqual(evaluated["outputs"], encoded(kind, expected(kind, value, 4), 4))
                    if kind != "sign":
                        view = request("/api/blocks/view", {"block_id": block["id"], "path": []})
                        self.assertEqual([n["id"] for n in view["circuit"]["view_nodes"] if n["kind"] == "instance"],
                                         ["arithmetic", "overflow"])
                        for path in (["arithmetic"], ["overflow"]):
                            view = request("/api/blocks/view", {"block_id": block["id"], "path": path})
                            self.assertGreater(len(view["circuit"]["gates"]), 0)
            finally:
                server.shutdown()
                server.server_close()
                server.executor.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

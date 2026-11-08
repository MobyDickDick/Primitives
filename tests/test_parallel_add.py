"""GEN-07: independent full sums, every carry, structural costs and migration."""
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
from primitives.examples import install_examples, install_parallel_add_examples
from primitives.library import Library, fitness
from primitives.server import make_server
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_generative import netlist
from tools.export_blocks import ports
from tools.export_parallel_add import (ROOT, TEMPLATES, OUTPUT, WIDTHS, bundle,
                                       comparison, component, definition, stage_program)
from tools.export_standard_arithmetic import definition as standard_definition


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def serial(a, b, width):
    """Full-adder truth by counting ones, independent of generate/propagate."""
    result, carries, carry = [], [], 0
    for x, y in zip(bits(a, width), bits(b, width)):
        count = x + y + carry
        result.append(count % 2)
        carry = int(count >= 2)
        carries.append(carry)
    return result + [carry], carries


class ParallelAddTests(unittest.TestCase):
    def test_all_exported_forms_tables_and_every_internal_carry(self):
        template = Template(definition())
        self.assertEqual(read(TEMPLATES / "parallel-prefix-add.abstract.json"), template.to_dict())
        reports = read(OUTPUT / "verification.json")
        self.assertEqual(len(reports), 9)
        total = 0
        for p, q in product(WIDTHS, repeat=2):
            with self.subTest(p=p, q=q):
                w = max(p, q)
                prefix = OUTPUT / f"cla-{p}-{q}"
                program = template.instantiate({"p": p, "q": q})
                hierarchy = BlockBundle(read(prefix.with_suffix(".block.json")))
                expanded = hierarchy.expand()
                circuit = Circuit.from_dict(read(prefix.with_suffix(".circuit.json")))
                compiled = synthesize(program)
                dataset = Dataset.from_dict(read(prefix.with_suffix(".vectors.json")))
                self.assertEqual(read(prefix.with_suffix(".template.json")), program.spec)
                self.assertEqual(hierarchy.to_dict(), bundle(p, q).to_dict())
                self.assertEqual(circuit, expanded.simplify())
                self.assertEqual(prefix.with_suffix(".nand.txt").read_text(encoding="utf-8"),
                                 netlist(circuit, program, f"CLA<{p},{q}>"))
                self.assertEqual([(port["name"], port["bits"]) for port in program.ports["inputs"]], [("a", p), ("b", q)])
                self.assertEqual([(port["name"], port["bits"]) for port in program.ports["outputs"]], [("c", w), ("carry", 1)])
                self.assertEqual(len(dataset.rows), 1 << (p + q))
                # Read the actual final generate bus from the expanded hierarchy.
                final_id = f"prefix_{1 << ((w - 1).bit_length() - 1)}" if w > 1 else "generate"
                final = next(n for n in hierarchy.view()["circuit"]["view_nodes"] if n.get("id") == final_id)
                seen_carries = [set() for _ in range(w)]
                for row in dataset.rows:
                    inputs = row[:p + q]
                    a, b = integer(inputs[:p]), integer(inputs[p:])
                    expected, carries = serial(a, b, w)
                    self.assertEqual(row, inputs + expected)
                    self.assertEqual(program.run(a | b << p), [integer(expected[:w]), expected[w]])
                    for impl in (hierarchy, expanded, circuit, compiled):
                        self.assertEqual(impl.evaluate(inputs), expected)
                    wires = expanded.wires(inputs)
                    self.assertEqual([wires[r] for r in final["signalRefs"][w:]], carries)
                    for seen, carry in zip(seen_carries, carries):
                        seen.add(carry)
                self.assertTrue(all(seen == {0, 1} for seen in seen_carries))
                report = next(r for r in reports if r["parameters"] == {"p": p, "q": q})
                self.assertEqual(report["fitness"], fitness(circuit, dataset))
                self.assertTrue(report["fitness"]["verified_truth_table"])
                self.assertEqual(report["hierarchy"], hierarchy.summary())
                self.assertEqual(report["comparison"], comparison(p, q, circuit))
                total += len(dataset.rows)
        self.assertEqual(total, 484)

    def test_prefix_stages_read_previous_stage_simultaneously(self):
        # Arbitrary P/G words include states that do not arise from two operands.
        # Each output combines two adjacent groups, with carry-in tested as 0/1.
        for w, d in ((2, 1), (4, 1), (4, 2)):
            program = stage_program(w, d)
            circuit = synthesize(program)
            for prop, gen in product(range(1 << w), repeat=2):
                ps, gs = bits(prop, w), bits(gen, w)
                out_p, out_g = ps[:], gs[:]
                for i in range(d, w):
                    for cin in (0, 1):
                        lower = gs[i - d] if ps[i - d] == 0 else max(gs[i - d], cin)
                        wanted = gs[i] if ps[i] == 0 else max(gs[i], lower)
                        if cin == 0:
                            out_g[i] = wanted
                        else:
                            out_p[i] = ps[i] * ps[i - d]
                        self.assertEqual(max(out_g[i], out_p[i] * cin), wanted)
                encoded = out_p + out_g
                self.assertEqual(program.run(prop | gen << w), [integer(out_p), integer(out_g)])
                self.assertEqual(circuit.evaluate(ps + gs), encoded)

    def test_unequal_non_power_of_two_and_larger_sampled_widths(self):
        rng = random.Random(20261106)
        for p, q in ((3, 5), (5, 3), (8, 8), (16, 16), (18, 18), (19, 19), (1, 32), (32, 1), (32, 32)):
            w = max(p, q)
            program = Template(definition()).instantiate({"p": p, "q": q})
            hardware = []
            if w <= 18:
                hardware += [synthesize(program), bundle(p, q)]
            elif w == 19:
                hardware += [bundle(p, q)]
            pairs = {(0, 0), ((1 << p) - 1, (1 << q) - 1), ((1 << p) - 1, 1), (1, (1 << q) - 1)}
            pairs.update((rng.getrandbits(p), rng.getrandbits(q)) for _ in range(8))
            # Force carry generation, propagation and termination at every bit.
            pairs.update(((1 << i) - 1, 1) for i in range(1, p + 1))
            pairs.update((1, (1 << i) - 1) for i in range(1, q + 1))
            for a, b in pairs:
                expected, _ = serial(a, b, w)
                self.assertEqual(program.run(a | b << p), [integer(expected[:w]), expected[w]])
                for impl in hardware:
                    self.assertEqual(impl.evaluate(bits(a, p) + bits(b, q)), expected)

    def test_parameters_direct_call_guards_and_hardware_budgets(self):
        for p, q in ((0, 1), (-1, 1), (1, 0), (65, 1), (1, 65), (128, 1), (1, True)):
            with self.subTest(p=p, q=q), self.assertRaises(ValueError):
                Template(definition()).instantiate({"p": p, "q": q})
        for call in ("CLA<0,1>(a,b)", "CLA<65,1>(a,b)", "AddGP<1,0>(a,b)",
                     "AddPrefixStage<4,0>(a,b)", "AddPrefixStage<4,4>(a,b)",
                     "AddPrefixStage<65,1>(a,b)", "AddPrefixSum<0>(a,b)", "AddPrefixSum<65>(a,b)"):
            program = component(1, 1, "Invalid call", ports([("a", 1), ("b", 1)], [("c", 1)]), f"return {call}")
            with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                program.run(0)
            with self.assertRaisesRegex(ValueError, "Funktionsbedingung"):
                synthesize(program)
        for w in (19, 20, 32, 64):
            program = Template(definition()).instantiate({"p": w, "q": w})
            with self.assertRaisesRegex(ValueError, "512"):
                synthesize(program)
            if w >= 20:
                with self.assertRaisesRegex(ValueError, "512"):
                    bundle(w, w)
        # This syntactically valid 128-input reference reaches the unchanged
        # per-input interpreter budget; never advertise it as an executable net.
        program = Template(definition()).instantiate({"p": 64, "q": 64})
        self.assertEqual(sum(p["bits"] for p in program.ports["inputs"]), 128)
        with self.assertRaisesRegex(ValueError, "Anweisungsbudget"):
            program.run(0)

    def test_cost_comparison_uses_same_full_sum_and_shows_tradeoff(self):
        for w in (4, 8, 16):
            parallel = bundle(w, w).expand().simplify()
            ripple = synthesize(Template(standard_definition("add")).instantiate({"p": w, "q": w}))
            measured = comparison(w, w)
            self.assertEqual(measured["ripple"], {"gates": len(ripple.gates), "depth": ripple.depth})
            for a, b in ((0, 0), ((1 << w) - 1, 1), ((1 << w) - 1, (1 << w) - 1)):
                inputs = bits(a, w) + bits(b, w)
                self.assertEqual(parallel.evaluate(inputs), ripple.evaluate(inputs))
            self.assertGreater(measured["delta"]["gates"], 0)
            if w == 4:
                self.assertEqual(measured["delta"]["depth"], 0)
            else:
                self.assertLess(measured["delta"]["depth"], 0)

    def test_migration_retains_user_data_and_does_not_restore_deletions(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            install_examples(library)
            self.assertFalse(any(t["name"] == "CLA<p,q>" for t in library.templates()))
            library.save_folder("Meine Rechner", "Eigene Beschreibung", "examples", "arithmetic")
            entries = library.tree()["entries"].copy()
            install_parallel_add_examples(library)
            self.assertTrue(read(Path(directory) / "example-installations.json")["parallel-add-v1"])
            self.assertTrue(entries.items() <= library.tree()["entries"].items())
            folder = next(f for f in library.tree()["folders"] if f["id"] == "arithmetic")
            self.assertEqual((folder["name"], folder["description"]), ("Meine Rechner", "Eigene Beschreibung"))
            new = [d for d in library.datasets() if d["name"].startswith("CLA<")]
            self.assertEqual(len(new), 9)
            library.update_function(new[0]["function_id"], "Mein Addierer", "Eigene Notizen")
            library.move_entry("function", new[0]["function_id"], "functions")
            library.delete_function(new[1]["function_id"])
            template = next(t for t in library.templates() if t["name"] == "CLA<p,q>")
            (Path(directory) / "templates" / f"{template['id']}.json").unlink()
            block = next(b for b in library.blocks() if b["name"] == "CLA<4,4>")
            (Path(directory) / "blocks" / f"{block['id']}.json").unlink()
            before = {p: p.read_bytes() for p in Path(directory).rglob("*.json")}
            install_parallel_add_examples(Library(directory))
            self.assertEqual({p: p.read_bytes() for p in Path(directory).rglob("*.json")}, before)

    def test_migration_keeps_better_solution_labels_and_assignments(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            dataset = Dataset.from_dict(read(OUTPUT / "cla-4-4.vectors.json"))
            ripple = synthesize(Template(standard_definition("add")).instantiate({"p": 4, "q": 4}))
            saved = library.save_program({"circuit": ripple.to_dict(), "note": "Eigene Lösung"}, dataset)
            key = library.datasets()[0]["function_id"]
            library.update_function(key, "Eigener Name", "Erhalten")
            library.move_entry("function", key, "functions")
            template_key = library.save_template(Template(definition()))
            library.move_entry("template", template_key, "templates")
            install_parallel_add_examples(library)
            winner = next(p for p in library.programs() if p["dataset_name"] == "Eigener Name")
            self.assertEqual((winner["id"], winner["note"]), (saved["id"], "Eigene Lösung"))
            self.assertEqual(library.tree()["entries"][f"function:{key}"], "functions")
            self.assertEqual(library.tree()["entries"][f"template:{template_key}"], "templates")
            self.assertEqual((len(library.templates()), len(library.datasets()), len(library.blocks())), (1, 9, 9))

    def test_server_upgrade_synthesis_evaluation_and_prefix_navigation(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            previous = ("signed", "arithmetic", "recursive-checked", "recursive-mul", "number-of-ones",
                        "recursive-msb-div", "recursive-max-index", "recursive-equ", "recursive-gt",
                        "generative-logic", "routing", "structured-logic", "standard-arithmetic",
                        "arithmetic-comments", "zero-counts", "priority-encoder", "onehot", "barrel-shifter", "rotations", "prefixes", "saturating")
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
                self.assertEqual((len(catalog["templates"]), len(catalog["datasets"]), len(catalog["blocks"])), (1, 9, 9))
                template = catalog["templates"][0]
                saved = request("/api/templates/synthesize", {
                    "template_id": template["id"], "parameters": {"p": 4, "q": 4}, "samples": 256, "name": "CLA HTTP"})
                self.assertTrue(saved["result"]["fitness"]["verified_truth_table"])
                block = next(b for b in catalog["blocks"] if b["name"] == "CLA<4,4>")
                for a, b in ((0, 0), (15, 1), (15, 15), (5, 10)):
                    evaluated = request("/api/blocks/evaluate", {"block_id": block["id"], "bits": bits(a, 4) + bits(b, 4)})
                    self.assertEqual(evaluated["outputs"], serial(a, b, 4)[0])
                view = request("/api/blocks/view", {"block_id": block["id"], "path": []})
                self.assertEqual([n["id"] for n in view["circuit"]["view_nodes"] if n["kind"] == "instance"],
                                 ["generate", "prefix_1", "prefix_2", "sum"])
                view = request("/api/blocks/view", {"block_id": block["id"], "path": ["prefix_2"]})
                self.assertGreater(len(view["circuit"]["gates"]), 0)
            finally:
                server.shutdown()
                server.server_close()
                server.executor.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

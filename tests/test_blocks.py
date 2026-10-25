import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from primitives.blocks import BlockBundle, block_id
from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, integer, preset
from primitives.evolution import Problem, SearchConfig
from primitives.library import Library, fitness
from primitives.repair import repair_result
from primitives.runner import ROOT, search, tiny_interpreter
from tools.export_blocks import examples, inp, out, ports, instance


class BlockTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".jobs").mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".jobs")
        self.addCleanup(self.tmp.cleanup)
        self.library = Library(self.tmp.name)
        self.examples = examples()

    def test_nested_adders_against_integer_arithmetic_and_expansion(self):
        for name, bundle in self.examples.items():
            circuit = bundle.expand()
            for x in range(1 << circuit.inputs):
                vector = bits(x, circuit.inputs)
                if name == "ripple-adder-2": expected = (x & 3) + ((x >> 2) & 3) + (x >> 4)
                else: expected = sum(vector)
                self.assertEqual(integer(bundle.evaluate(vector)), expected, (name, x))
                self.assertEqual(circuit.evaluate(vector), bundle.evaluate(vector))
            self.assertEqual(BlockBundle(bundle.to_dict()).expand(), circuit)
        self.assertEqual(self.examples["ripple-adder-2"].summary()["definitions"], 6)
        self.assertEqual(self.examples["ripple-adder-2"].summary()["instances"], 2)

    def test_multiple_unequal_ports_bit_permutations_direct_outputs_and_nand(self):
        leaf_ports = ports([("left", 2), ("right", 1)], [("pair", 2), ("flag", 1)])
        leaf = BlockBundle.from_circuit("bus", Circuit(3, ((0, 2),), (1, 0, 3)), leaf_ports)
        definition = {"name": "connected buses", "version": 1,
            "interface": ports([("a", 2), ("b", 1)], [("value", 2), ("carry", 1)]),
            "nodes": [instance("second", leaf, left=[out("first", "flag"), out("first", "pair", 0)], right=[inp("b")]),
                      instance("first", leaf, left=[inp("a", 1), inp("a", 0)], right=[inp("b")]),
                      {"id": "invert", "type": "nand", "inputs": [out("second", "flag"), out("second", "flag")]}],
            "outputs": {"value": [out("second", "pair", 1), out("first", "pair", 1)], "carry": [out("invert", "out")]}}
        bundle = BlockBundle.create(definition, [leaf])
        for x in range(8):
            a0, a1, b = bits(x, 3)
            expected = [1 - (a1 & b), a1, (1 - (a1 & b)) & b]
            self.assertEqual(bundle.evaluate(bits(x, 3)), expected)
            self.assertEqual(bundle.expand().evaluate(bits(x, 3)), expected)

    def test_portable_roundtrip_after_reload_and_without_dependency_files(self):
        bundle = self.examples["ripple-adder-2"]
        saved = self.library.save_block(bundle)
        self.assertEqual(self.library.blocks(), [saved])
        restored = Library(self.tmp.name).load_block(saved["id"])
        self.assertEqual(restored.to_dict(), bundle.to_dict())
        self.assertEqual(len(list((Path(self.tmp.name) / "blocks").glob("*.json"))), 1)
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as other:
            destination = Library(other)
            destination.save_block(json.loads(json.dumps(restored.to_dict())))
            self.assertEqual(destination.load_block(bundle.root).evaluate([1, 1, 1, 1, 1]), [1, 1, 1])
        before = bundle.to_dict()
        bundle.definition["name"] = "mutated copy"
        exported = bundle.to_dict(); exported["definitions"].clear()
        self.assertEqual(bundle.to_dict(), before)

    def test_version_and_implementation_stay_pinned_when_best_program_changes(self):
        ds = preset("and")
        old = self.library.save_program({"circuit": Circuit(2, (), (0,)).to_dict()}, ds)
        block = self.library.block_from_program(old["id"], "pinned AND attempt")
        self.assertEqual(block.evaluate([1, 0]), [1])
        new = self.library.save_program({"circuit": Circuit(2, ((0, 1), (2, 2)), (3,)).to_dict()}, ds)
        self.assertNotEqual(old["id"], new["id"])
        self.assertEqual(self.library.load_block(block.root).evaluate([1, 0]), [1])
        v2 = self.library.block_from_program(new["id"], "pinned AND attempt", version=2)
        self.assertNotEqual(v2.root, block.root)
        self.assertEqual(v2.evaluate([1, 0]), [0])
        self.assertEqual(len(self.library.blocks()), 2)

    def test_program_export_and_rewrapping_preserve_hierarchy(self):
        bundle = self.examples["full-adder"]
        ds = bundle.dataset(8)
        result = {"circuit": bundle.expand().to_dict(), "hierarchy": bundle.to_dict()}
        saved = self.library.save_program(result, ds)
        loaded = self.library.load_program(saved["id"])
        self.assertEqual(loaded["hierarchy"], bundle.to_dict())
        wrapper = self.library.block_from_program(saved["id"], "wrapped full adder")
        self.assertEqual(wrapper.summary()["definitions"], bundle.summary()["definitions"] + 1)
        self.assertEqual(wrapper.evaluate([1, 0, 1]), [0, 1])
        renamed = bundle.wrap("bus remap", ports([("word", 3)], [("answer", 2)]))
        self.assertEqual(renamed.evaluate([1, 0, 1]), [0, 1])
        bad = {**result, "circuit": Circuit(3, (), (0, 1)).to_dict()}
        with self.assertRaisesRegex(ValueError, "Hierarchie"):
            self.library.save_program(bad, ds)

    def test_hierarchy_dataset_roundtrip_and_sampling(self):
        bundle = self.examples["ripple-adder-2"]
        ds = bundle.dataset(32)
        self.assertTrue(ds.exhaustive)
        self.assertEqual(Dataset.from_dict(ds.to_dict()).to_dict(), ds.to_dict())
        for row in ds.rows:
            self.assertEqual(bundle.evaluate(row[:5]), row[5:])
        sampled = bundle.dataset(7, 9)
        self.assertFalse(sampled.exhaustive)
        self.assertEqual(sampled.to_dict(), bundle.dataset(7, 9).to_dict())
        bad = ds.to_dict(); bad["metadata"]["interface"]["inputs"][0]["bits"] = 1
        with self.assertRaises(ValueError): Dataset.from_dict(bad)

    def test_missing_dependencies_and_recursive_definitions(self):
        half = self.examples["half-adder"]
        doc = half.to_dict()
        target = doc["definitions"][half.root]["nodes"][0]["definition"]
        del doc["definitions"][target]
        with self.assertRaisesRegex(ValueError, "Fehlende"):
            BlockBundle(doc)
        for indirect in (False, True):
            d = {"name": "cycle", "version": 1, "interface": ports([("a", 1)], [("c", 1)]),
                 "nodes": [{"id": "self", "type": "instance", "definition": "other" if indirect else "root", "inputs": {"a": [inp("a")]}}],
                 "outputs": {"c": [out("self", "c")]}}
            other = copy.deepcopy(d); other["nodes"][0]["definition"] = "root"
            doc = {"schema": 1, "root": "root", "definitions": {"root": d, **({"other": other} if indirect else {})}}
            with self.assertRaisesRegex(ValueError, "rekursive"):
                BlockBundle(doc)

    def test_invalid_connections_cycles_widths_names_and_identity(self):
        half = self.examples["half-adder"]
        d = half.definition
        dependencies = [BlockBundle.from_circuit("XOR", Circuit(2, ((0, 1), (0, 2), (1, 2), (3, 4)), (5,)), ports([("a", 1), ("b", 1)], [("value", 1)])),
                        BlockBundle.from_circuit("AND", Circuit(2, ((0, 1), (2, 2)), (3,)), ports([("a", 1), ("b", 1)], [("value", 1)]))]
        invalid = []
        bad = copy.deepcopy(d); bad["nodes"][0]["inputs"]["a"] = []; invalid.append(bad)
        bad = copy.deepcopy(d); bad["nodes"][0]["inputs"]["a"] = [inp("a", 1)]; invalid.append(bad)
        bad = copy.deepcopy(d); bad["nodes"][0]["inputs"]["a"] = [out("absent", "value")]; invalid.append(bad)
        bad = copy.deepcopy(d); bad["nodes"][0]["inputs"]["a"] = [out("carry", "missing")]; invalid.append(bad)
        bad = copy.deepcopy(d); bad["nodes"][0]["inputs"]["a"] = [out("carry", "value")]; bad["nodes"][1]["inputs"]["a"] = [out("sum", "value")]; invalid.append(bad)
        bad = copy.deepcopy(d); bad["nodes"].append(copy.deepcopy(bad["nodes"][0])); invalid.append(bad)
        bad = copy.deepcopy(d); bad["outputs"]["sum"] = [inp("a", True)]; invalid.append(bad)
        bad = copy.deepcopy(d); del bad["outputs"]["carry"]; invalid.append(bad)
        for bad in invalid:
            with self.subTest(bad=bad), self.assertRaises(ValueError): BlockBundle.create(bad, dependencies)
        with self.assertRaises(ValueError): BlockBundle.from_circuit("bad ports", Circuit(2, (), (0,)), ports([("a", 1)], [("c", 1)]))
        with self.assertRaises(ValueError): BlockBundle.from_circuit("empty ports", Circuit(1, (), (0,)), {})
        with self.assertRaises(ValueError): half.wrap("empty ports", {})
        with self.assertRaises(ValueError): BlockBundle.create(None)
        bad = half.to_dict(); bad["definitions"][half.root]["name"] = "tampered"
        with self.assertRaisesRegex(ValueError, "Kennung|kennung"): BlockBundle(bad)
        for vector in ([1], [True, 0], [0, 2]):
            with self.assertRaises(ValueError): half.evaluate(vector)

    def test_limits_on_expanded_gates_depth_and_instances(self):
        leaf = BlockBundle.from_circuit("large", Circuit(1, tuple((0, 0) for _ in range(257)), (257,)))
        d = {"name": "too large", "version": 1, "interface": ports([("a", 1)], [("c", 1)]),
             "nodes": [instance("one", leaf, in0=[inp("a")]), instance("two", leaf, in0=[inp("a")])],
             "outputs": {"c": [out("two", "out0")]}}
        with self.assertRaisesRegex(ValueError, "512"): BlockBundle.create(d, [leaf])
        small = BlockBundle.from_circuit("wire", Circuit(1, (), (0,)))
        for i in range(32): small = small.wrap(f"layer{i}")
        with self.assertRaisesRegex(ValueError, "32"): small.wrap("too deep")
        small = BlockBundle.from_circuit("wire", Circuit(1, (), (0,)))
        for i in range(9):
            d = {"name": f"binary{i}", "version": 1, "interface": ports([("a", 1)], [("c", 1)]),
                 "nodes": [instance("one", small, **{small.definition["interface"]["inputs"][0]["name"]: [inp("a")]}),
                           instance("two", small, **{small.definition["interface"]["inputs"][0]["name"]: [inp("a")]})],
                 "outputs": {"c": [out("two", small.definition["interface"]["outputs"][0]["name"])]}}
            small = BlockBundle.create(d, [small])
        d["name"] = "too many"; d["nodes"] = [instance("one", small, a=[inp("a")]), instance("two", small, a=[inp("a")]), instance("three", small, a=[inp("a")])]
        with self.assertRaisesRegex(ValueError, "2048"): BlockBundle.create(d, [small])

    def test_evolution_uses_expansion_without_claiming_preserved_instances(self):
        block = self.examples["half-adder"]
        self.library.save_block(block)
        ds = block.dataset(4)
        result = search(ds, SearchConfig(gates=12, population=12, generations=200, backend="python"), self.library, save=False)
        self.assertEqual(result["fitness"]["errors"], 0)
        self.assertEqual(result["search"]["seed_blocks"], [block.root])
        self.assertNotIn("hierarchy", result)
        self.assertEqual(block.to_dict(), self.library.load_block(block.root).to_dict())
        problem = Problem(ds, SearchConfig(gates=12, backend="python"), [block.expand()])
        self.assertTrue(problem.library)
        genome = problem.specimen()
        self.assertEqual(len(genome), 26)
        self.assertEqual(len(problem.result(genome, 0)["circuit"]["outputs"]), 2)

    def test_tiny_backend_accepts_nested_block_seeds(self):
        try: tiny_interpreter()
        except ValueError: self.skipTest("TinyLanguage-Laufzeit fehlt")
        block = self.examples["half-adder"]
        self.library.save_block(block)
        result = search(block.dataset(4), SearchConfig(gates=12, generations=200, backend="tiny"), self.library, save=False)
        self.assertTrue(result["fitness"]["verified_truth_table"])
        self.assertEqual(result["search"]["seed_blocks"], [block.root])
        self.assertNotIn("hierarchy", result)

    def test_repair_drops_changed_hierarchy_and_legacy_circuits_remain_readable(self):
        block = BlockBundle.from_circuit("approximate AND", Circuit(2, (), (0,)))
        result = {"circuit": block.expand().to_dict(), "hierarchy": block.to_dict()}
        repaired = repair_result(result, preset("and"))
        self.assertNotIn("hierarchy", repaired)
        self.assertIn("hierarchy", result)
        self.assertEqual(repaired["fitness"]["errors"], 0)
        saved = self.library.save_program(repaired, preset("and"))
        self.assertEqual(Circuit.from_dict(self.library.load_program(saved["id"])["circuit"]).evaluate([1, 0]), [0])

    def test_archives_and_actual_cli_import_expand_vectors_and_compose(self):
        for name, bundle in self.examples.items():
            archived = json.loads((ROOT / "examples" / "blocks" / (name + ".json")).read_text(encoding="utf-8"))
            self.assertEqual(BlockBundle(archived).to_dict(), bundle.to_dict())
        path = ROOT / "examples" / "blocks" / "ripple-adder-2.json"
        def run(*args):
            result = subprocess.run([sys.executable, "-m", "primitives", "--data-dir", self.tmp.name, "blocks", *map(str, args)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout
        summary = json.loads(run("import", path))
        self.assertEqual(json.loads(run("list"))[0]["id"], summary["id"])
        self.assertEqual(json.loads(run("eval", path, "11111")), [1, 1, 1])
        output = Path(self.tmp.name) / "out.json"
        run("expand", path, "--out", output)
        expanded = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(expanded["hierarchy"]["root"], summary["id"])
        run("vectors", path, "--samples", 32, "--out", output)
        self.assertTrue(Dataset.from_dict(json.loads(output.read_text(encoding="utf-8"))).exhaustive)
        wrapper = self.examples["ripple-adder-2"].wrap("CLI wrapper")
        definition_file = Path(self.tmp.name) / "definition.json"
        definition_file.write_text(json.dumps(wrapper.definition), encoding="utf-8")
        created = json.loads(run("compose", definition_file, "--dependency", summary["id"], "--out", output))
        self.assertEqual(created["id"], wrapper.root)


if __name__ == "__main__":
    unittest.main()

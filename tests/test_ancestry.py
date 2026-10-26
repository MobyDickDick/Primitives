"""Reconstruct actual candidate genomes independently of the ancestry recorder."""
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from primitives.ancestry import Ancestry
from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import generate, preset
from primitives.evolution import Problem, SearchConfig, genome_circuit, migrate, search_python
from primitives.library import Library, fitness
from primitives.repair import repair_result
from primitives.runner import ROOT, search, tiny_interpreter


class AncestryTests(unittest.TestCase):
    def backends(self):
        yield "python"
        try:
            tiny_interpreter()
        except ValueError:
            return
        yield "tiny"

    def reconstruct(self, result, dataset):
        info = result["search"]
        ancestry = info["ancestry"]
        genomes, nodes = {}, {}
        for node in ancestry["nodes"]:
            key = node["id"]
            self.assertNotIn(key, genomes)
            self.assertLessEqual(key, info["evaluations"])
            for parent in node["parents"]:
                self.assertLess(parent, key)
                self.assertEqual(nodes[parent]["restart"], node["restart"])
            if node["parents"]:
                genome = list(genomes[node["parents"][0]])
                for index, value in node["changes"]:
                    self.assertNotEqual(genome[index], value)
                    genome[index] = value
                # Every non-mutated gene must come from the stated parent.
                for index, value in enumerate(genome):
                    if index not in node["mutation_genes"]:
                        parent = node["parents"][index in node["crossover_genes"]]
                        self.assertEqual(value, genomes[parent][index])
            else:
                genome = list(node["genome"])
                for seed in node["origin"].get("seeds", []):
                    source = ancestry["sources"][seed["source"]]
                    circuit = Circuit.from_dict(source["circuit"])
                    if "inputs" in seed:
                        mapping = list(seed["inputs"])
                        for index, (a, b) in enumerate(circuit.gates):
                            offset = seed["gate_offset"] + index
                            self.assertEqual(genome[2*offset:2*offset+2], [mapping[a], mapping[b]])
                            mapping.append(dataset.inputs + offset)
                    else:
                        self.assertEqual(genome_circuit(genome, dataset.inputs, dataset.outputs).compact(), circuit)
            circuit = genome_circuit(genome, dataset.inputs, dataset.outputs)
            errors = sum(actual != expected for row in dataset.rows
                         for actual, expected in zip(circuit.evaluate(row[:dataset.inputs]), row[dataset.inputs:]))
            expected_score = errors * (info["gates"] + 1)**2
            if not info["neutral"]:
                expected_score += len(circuit.active()) * (info["gates"] + 1) + circuit.depth
            self.assertEqual(node["score"], expected_score)
            genomes[key], nodes[key] = genome, node
        root = ancestry["root"]
        self.assertIn(root, genomes)
        self.assertEqual(nodes[root]["score"], info["history"][-1]["score"])
        for event in ancestry["migrations"]:
            self.assertIn(event["candidate_id"], nodes)
            self.assertEqual(event["target_island"], (event["source_island"] + 1) % info["islands"])
        self.assertEqual(ancestry["transformations"][-1]["circuit"], result["circuit"])
        compact = genome_circuit(genomes[root], dataset.inputs, dataset.outputs).compact().to_dict()
        self.assertEqual(ancestry["transformations"][0], {"operation": "compact", "circuit": compact})
        return ancestry, genomes

    def test_exact_crossover_and_mutation_trace_reconstructs_both_parents(self):
        dataset = preset("xor")
        p = Problem(dataset, SearchConfig(gates=1, population=2, generations=1, backend="python"))
        p.rng = Mock()
        p.rng.random.side_effect = [1, 0, 1, 1, 0, 1, 1, 0]
        p.rng.randrange.return_value = 2
        p.rng.choice.side_effect = lambda values: values[0]
        with patch.object(p, "initial_genome", return_value=[0, 0, 0]), \
             patch.object(p, "specimen", return_value=[1, 1, 1]), \
             patch("primitives.evolution.tournament", side_effect=[0, 1]):
            result = search_python(p)
        ancestry, genomes = self.reconstruct(result, dataset)
        self.assertEqual(ancestry["root"], 3)
        node = ancestry["nodes"][-1]
        self.assertEqual(node["parents"], [1, 2])
        self.assertEqual(node["crossover_genes"], [1])
        self.assertEqual(node["mutation_genes"], [2])
        self.assertEqual(genomes[3], [0, 1, 2])

    def test_equal_genomes_have_distinct_identities_and_keep_first_elite(self):
        p = Problem(preset("xor"), SearchConfig(gates=1, population=2, generations=1, backend="python"))
        p.rng = Mock()
        p.rng.random.return_value = 1
        p.rng.choice.side_effect = lambda values: values[0]
        with patch.object(p, "initial_genome", return_value=[0, 1, 2]), \
             patch.object(p, "specimen", return_value=[0, 1, 2]), \
             patch("primitives.evolution.tournament", side_effect=[1, 0]):
            result = search_python(p)
        self.assertEqual(list(p.ancestry.nodes), [1, 2, 3])
        self.assertEqual(p.ancestry.nodes[3]["parents"], [2])
        self.assertEqual(p.ancestry.nodes[3]["changes"], [])
        self.assertEqual(result["search"]["ancestry"]["root"], 1)
        self.assertEqual(len(result["search"]["ancestry"]["nodes"]), 1)

    def test_real_backends_reconstruct_variation_migrations_and_repeat_identically(self):
        dataset = generate("half-adder", 2, 2, "x0+x1")
        for backend in self.backends():
            with self.subTest(backend=backend):
                config = SearchConfig(gates=8, population=6, generations=12, islands=2,
                    migration_interval=1, backend=backend, seed=2 if backend == "python" else 1)
                result = search(dataset, config)
                ancestry, _ = self.reconstruct(result, dataset)
                self.assertTrue(any(node["parents"] for node in ancestry["nodes"]))
                self.assertTrue(ancestry["migrations"])
                self.assertEqual(result["fitness"], fitness(Circuit.from_dict(result["circuit"]), dataset))
                self.assertEqual(ancestry, search(dataset, config)["search"]["ancestry"])

    def test_restarts_keep_distinct_ids_and_no_cross_restart_parentage(self):
        for backend in self.backends():
            with self.subTest(backend=backend):
                config = SearchConfig(gates=1, population=6, generations=5, restarts=3,
                                      islands=3, migration_interval=1, neutral=True, backend=backend)
                result = search(preset("xor"), config)
                self.assertEqual(result["search"]["evaluations"], 31)
                self.assertEqual(result["search"]["restarts_completed"], 3)
                self.reconstruct(result, preset("xor"))

    def test_migration_copies_identity_simultaneously_with_the_genome(self):
        groups, ranks, identities = [[[0], [1]], [[2], [3]], [[4], [5]]], [[1, 2], [10, 11], [20, 21]], [[1, 2], [3, 4], [5, 6]]
        ancestry = Ancestry()
        self.assertEqual(migrate(groups, ranks, identities, ancestry, 2, 9), 2)
        self.assertEqual(identities, [[1, 2], [3, 1], [5, 3]])
        self.assertEqual([e["candidate_id"] for e in ancestry.migrations], [1, 3])
        self.assertTrue(all(e["restart"] == 2 and e["generation"] == 9 for e in ancestry.migrations))

    def test_only_actual_eligible_program_and_block_sources_are_claimed(self):
        for backend in self.backends():
            with self.subTest(backend=backend), tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as temp:
                lib = Library(temp)
                nand = Circuit(2, ((0, 1),), (2,))
                source = lib.save_program({"circuit": nand.to_dict()}, preset("nand"))
                block = BlockBundle.from_circuit("NAND", nand)
                lib.save_block(block)
                excluded = lib.save_program({"circuit": Circuit(3, (), (0,)).to_dict()}, generate("large", 3, 1, "x0"))
                result = search(preset("xor"), SearchConfig(gates=4, population=4, generations=3, backend=backend), lib, save=False)
                ancestry, _ = self.reconstruct(result, preset("xor"))
                self.assertEqual(result["search"]["library_candidates"], 2)
                self.assertTrue(ancestry["sources"])
                self.assertLessEqual(set(ancestry["sources"]), {"program:" + source["id"], "block:" + block.root})
                self.assertNotIn("program:" + excluded["id"], ancestry["sources"])
                self.assertTrue(all(n["operator"] != "random" for n in ancestry["nodes"] if not n["parents"]))

    def test_incumbent_simplification_and_saved_retest_preserve_correct_provenance(self):
        redundant = Circuit(2, ((0, 1), (2, 2), (3, 3)), (4,))
        for backend in self.backends():
            with self.subTest(backend=backend), tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as temp:
                lib = Library(temp)
                old = lib.save_program({"circuit": redundant.to_dict()}, preset("nand"))
                config = SearchConfig(gates=3, neutral=True, backend=backend)
                result = search(preset("nand"), config, lib)
                ancestry, _ = self.reconstruct(result, preset("nand"))
                self.assertEqual(ancestry["nodes"][0]["operator"], "incumbent")
                self.assertIn("program:" + old["id"], ancestry["sources"])
                self.assertEqual([t["operation"] for t in ancestry["transformations"]], ["compact", "simplification"])
                self.assertEqual(Library(temp).load_program(result["id"])["search"]["ancestry"], ancestry)
                # A tied retest keeps the existing program and its original genealogy.
                repeated = search(preset("nand"), config, lib)
                self.assertFalse(repeated["comparison"]["accepted"])
                self.assertEqual(repeated["search"]["ancestry"], ancestry)

    def test_repair_is_separate_from_the_evolutionary_candidate_and_does_not_mutate_it(self):
        from test_repair import MUL_APPROXIMATION
        dataset = preset("mul")
        p = Problem(dataset, SearchConfig(gates=9, population=2, generations=1, backend="python"),
                    incumbent=MUL_APPROXIMATION, time_budget=0)
        result = search_python(p)
        original = json.loads(json.dumps(result))
        repaired = repair_result(result, dataset)
        self.assertEqual(result, original)
        ancestry, _ = self.reconstruct(repaired, dataset)
        self.assertEqual(ancestry["transformations"][-1]["operation"], "repair")
        self.assertEqual(ancestry["root"], 1)
        self.assertTrue(repaired["fitness"]["verified_truth_table"])

    def test_better_incumbent_selection_is_explicit_before_repair(self):
        from test_repair import MUL_APPROXIMATION
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as temp:
            lib = Library(temp)
            old = lib.save_program({"circuit": MUL_APPROXIMATION.to_dict()}, preset("mul"))
            result = search(preset("mul"), SearchConfig(gates=1, population=2, generations=1,
                            repair_cases=4, backend="python"), lib, save=False)
            ancestry, _ = self.reconstruct(result, preset("mul"))
            steps = ancestry["transformations"]
            self.assertEqual([t["operation"] for t in steps], ["compact", "incumbent_selection", "repair"])
            self.assertEqual(steps[1]["source"]["id"], old["id"])
            self.assertEqual(steps[1]["circuit"], MUL_APPROXIMATION.to_dict())

    def test_cli_exports_self_contained_ancestry(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as temp:
            proc = subprocess.run([sys.executable, "-X", "utf8", "-m", "primitives", "--data-dir", temp,
                "evolve", "--preset", "xor", "--backend", "python", "--gates", "1",
                "--population", "2", "--generations", "2"], cwd=ROOT, capture_output=True,
                text=True, encoding="utf-8", timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.reconstruct(result, preset("xor"))
            self.assertEqual(result["search"]["ancestry"], Library(temp).load_program(result["id"])["search"]["ancestry"])


if __name__ == "__main__":
    unittest.main()

"""Neutral selection and a separate, globally function-preserving rewrite pass."""
import itertools
import json
import random
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from primitives.circuit import Circuit
from primitives.dataset import Dataset, preset
from primitives.evolution import Problem, SearchCancelled, SearchConfig, search_python
from primitives.library import Library, fitness
from primitives.runner import ROOT, search, tiny_interpreter


class SimplificationTests(unittest.TestCase):
    def assert_equivalent(self, circuit):
        result = circuit.simplify()
        for bits in itertools.product((0, 1), repeat=circuit.inputs):
            bits = list(bits)
            self.assertEqual(result.evaluate(bits), circuit.evaluate(bits))
        self.assertLessEqual(len(result.gates), len(circuit.compact().gates))
        self.assertLessEqual(result.depth, circuit.depth)
        self.assertEqual(result.simplify(), result)
        return result

    def test_shared_commutative_nands_multiple_outputs_and_dead_gates(self):
        circuit = Circuit(2, ((0, 1), (1, 0), (2, 3), (0, 0)), (4, 2, 0, 3))
        result = self.assert_equivalent(circuit)
        self.assertEqual(result, Circuit(2, ((0, 1), (2, 2)), (3, 2, 0, 2)))

    def test_double_negation_preserves_shared_inverter_and_direct_outputs(self):
        circuit = Circuit(2, ((0, 0), (2, 2), (3, 3), (4, 4)), (2, 3, 4, 5, 1))
        self.assertEqual(self.assert_equivalent(circuit), Circuit(2, ((0, 0),), (2, 0, 2, 0, 1)))
        self.assertEqual(self.assert_equivalent(Circuit(1, ((0, 0), (1, 1)), (2,))), Circuit(1, (), (0,)))

    def test_random_circuits_against_all_inputs(self):
        rng = random.Random(91)
        for inputs in range(1, 5):
            for _ in range(40):
                gates = tuple(tuple(rng.randrange(inputs + i) for _ in range(2)) for i in range(24))
                circuit = Circuit(inputs, gates, tuple(rng.randrange(inputs + 24) for _ in range(4)))
                with self.subTest(circuit=circuit):
                    self.assert_equivalent(circuit)

    def test_full_width_and_cancellation_during_rewrite(self):
        circuit = Circuit(32, ((0, 31), (32, 32), (33, 33)), (34, 0, 31))
        self.assertEqual(circuit.simplify(), Circuit(32, ((0, 31),), (32, 0, 31)))
        checks = Mock(side_effect=[None, None, SearchCancelled("stop")])
        with self.assertRaises(SearchCancelled):
            circuit.simplify(check=checks)
        self.assertEqual(checks.call_count, 3)


class NeutralTests(unittest.TestCase):
    # Three active NANDs implement one NAND through a double inversion.
    redundant = Circuit(2, ((0, 1), (2, 2), (3, 3)), (4,))

    def backends(self):
        yield "python"
        try:
            tiny_interpreter()
        except ValueError:
            return
        yield "tiny"

    def test_neutral_scores_ignore_structure_without_changing_default_scores(self):
        small = [0, 1, 0, 0, 0, 0, 2]
        large = [0, 1, 2, 2, 3, 3, 4]
        for neutral in (False, True):
            p = Problem(preset("xor"), SearchConfig(gates=3, backend="python", neutral=neutral))
            a, b = p.score(small), p.score(large)
            self.assertEqual(a // p.error_weight, b // p.error_weight)
            if neutral:
                self.assertEqual(a, b)
                self.assertEqual(a, p.error_weight)
            else:
                self.assertLess(a, b)
        for value in (0, 1, "true", None, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                SearchConfig(neutral=value).validate()

    def test_larger_neutral_offspring_enters_population_and_elite_is_retained(self):
        small = [0, 1, 0, 0, 0, 0, 2]
        large = [0, 1, 2, 2, 3, 3, 4]
        p = Problem(preset("xor"), SearchConfig(gates=3, population=2, generations=1,
                                               backend="python", neutral=True))
        p.rng = Mock()
        p.rng.random.return_value = 0  # Inject an independently generated candidate.
        p.rng.choice.side_effect = lambda values: values[0]
        snapshots = []
        observe = p.observe

        def capture(groups, *args):
            snapshots.append([[g[:] for g in group] for group in groups])
            return observe(groups, *args)

        with patch.object(p, "initial_genome", return_value=small), \
             patch.object(p, "specimen", side_effect=[small[:], large]), \
             patch.object(p, "observe", side_effect=capture):
            result = search_python(p)
        self.assertIn(large, snapshots[-1][0])
        self.assertEqual(result["search"]["phases"][0]["result"]["gates"], 1)
        self.assertEqual(result["circuit"], Circuit(2, ((0, 1),), (2,)).to_dict())
        self.assertEqual(result["search"]["evaluations"], 3)

    def test_both_backends_simplify_after_early_success_and_save_phases(self):
        for backend in self.backends():
            with self.subTest(backend=backend), tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as temp:
                lib = Library(temp)
                lib.save_program({"circuit": self.redundant.to_dict()}, preset("nand"))
                result = search(preset("nand"), SearchConfig(gates=3, backend=backend, neutral=True), lib)
                phases = result["search"]["phases"]
                self.assertEqual([p["name"] for p in phases], ["neutral_evolution", "simplification"])
                self.assertEqual(phases[0]["evaluations"], 1)
                self.assertEqual(phases[0]["result"], {"errors": 0, "gates": 3, "depth": 3})
                self.assertEqual(phases[1]["evaluations"], 0)
                self.assertEqual(phases[1]["removed_gates"], 2)
                self.assertEqual(phases[1]["result"], {"errors": 0, "gates": 1, "depth": 1})
                self.assertEqual(result["search"]["history"][-1]["score"], 0)
                self.assertEqual(result["fitness"], fitness(Circuit.from_dict(result["circuit"]), preset("nand")))
                self.assertEqual(Library(temp).load_program(result["id"])["search"]["phases"], phases)

    def test_both_backends_share_restart_budget_and_record_errors_only_history(self):
        for backend in self.backends():
            with self.subTest(backend=backend):
                config = SearchConfig(gates=1, population=7, generations=9, restarts=3, islands=3,
                                      migration_interval=1, neutral=True, backend=backend)
                result = search(preset("xor"), config)
                info = result["search"]
                self.assertEqual(info["evaluations"], 64)
                self.assertEqual([r["evaluations"] for r in info["runs"]], [21, 21, 22])
                self.assertEqual(info["objective"], "errors_only")
                self.assertTrue(all(h["score"] == h["errors"] * 4 for h in info["history"]))
                self.assertTrue(all(r["migrations"] > 0 for r in info["runs"]))
                self.assertEqual(result["fitness"], fitness(Circuit.from_dict(result["circuit"]), preset("xor")))
                repeat = search(preset("xor"), config)
                self.assertEqual(result["circuit"], repeat["circuit"])
                for field in ("phases", "runs", "history", "diversity_history"):
                    self.assertEqual(info[field], repeat["search"][field])

    def test_simplification_of_sample_preserves_unseen_inputs_and_verification_status(self):
        dataset = Dataset.from_dict({"name": "sample", "inputs": 2, "outputs": 1, "rows": [[0, 0, 1]]})
        p = Problem(dataset, SearchConfig(gates=3, backend="python", neutral=True), incumbent=self.redundant)
        result = search_python(p)
        self.assertTrue(result["fitness"]["exact_on_dataset"])
        self.assertFalse(result["fitness"]["verified_truth_table"])
        circuit = Circuit.from_dict(result["circuit"])
        for bits in itertools.product((0, 1), repeat=2):
            self.assertEqual(circuit.evaluate(list(bits)), self.redundant.evaluate(list(bits)))

    def test_time_limit_finalizes_and_cancellation_still_discards_job(self):
        config = SearchConfig(gates=3, backend="python", neutral=True, optimize=True)
        p = Problem(preset("nand"), config, incumbent=self.redundant, time_budget=0)
        result = search_python(p)
        self.assertEqual(result["search"]["evaluations"], 1)
        self.assertEqual(result["search"]["phases"][1]["removed_gates"], 2)
        cancelled = threading.Event()
        p = Problem(preset("nand"), config, incumbent=self.redundant, cancel_event=cancelled)
        observe = p.observe

        def cancel_at_end(groups, generation, stage, migrations=0):
            value = observe(groups, generation, stage, migrations)
            if stage == "final":
                cancelled.set()
            return value

        with patch.object(p, "observe", side_effect=cancel_at_end), self.assertRaises(SearchCancelled):
            search_python(p)

    def test_cli_exposes_neutral_mode(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as temp:
            proc = subprocess.run([sys.executable, "-X", "utf8", "-m", "primitives", "--data-dir", temp,
                                   "evolve", "--preset", "xor", "--backend", "python", "--neutral",
                                   "--gates", "1", "--population", "2", "--generations", "2"],
                                  cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertTrue(result["search"]["neutral"])
            self.assertEqual(len(result["search"]["phases"]), 2)
            self.assertEqual(result["search"]["evaluations"], 5)


if __name__ == "__main__":
    unittest.main()

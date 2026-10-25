"""Population selection, independent fitness checks and search limits."""
import threading
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from primitives.circuit import Circuit
from primitives.dataset import generate, preset
from primitives.evolution import Problem, SearchCancelled, SearchConfig, diversity, migrate, search_python, tournament
from primitives.library import Library, fitness
from primitives.runner import ROOT, search, tiny_interpreter


class PopulationTests(unittest.TestCase):
    def test_tournament_chooses_best_draw_from_the_whole_population(self):
        rng = Mock()
        rng.randrange.side_effect = [0, 3, 2]
        self.assertEqual(tournament([40, 30, 10, 20], rng), 2)
        self.assertEqual(rng.randrange.call_count, 3)
        rng.reset_mock()
        rng.randrange.side_effect = [1, 0]
        self.assertEqual(tournament([5, 9], rng), 0)
        self.assertEqual(rng.randrange.call_count, 2)

    def test_initial_population_is_evaluated_and_can_solve_before_reproduction(self):
        p = Problem(preset("nand"), SearchConfig(gates=1, population=4, backend="python"))
        with patch.object(p, "initial_genome", return_value=[0, 0, 0]), \
             patch.object(p, "specimen", side_effect=[[1, 1, 1], [0, 0, 2], [0, 1, 2]]):
            result = search_python(p)
        self.assertTrue(result["fitness"]["verified_truth_table"])
        self.assertEqual(result["search"]["evaluations"], 4)
        self.assertEqual(result["search"]["parent_population"], 4)
        self.assertEqual(result["search"]["generation"], 0)

    def test_offspring_uses_tournament_parents_without_mutating_them(self):
        p = Problem(preset("xor"), SearchConfig(gates=1, population=4, generations=1, backend="python"))
        genomes = [[0, 0, 0], [0, 1, 1], [0, 0, 2], [0, 1, 2]]
        original = [g[:] for g in genomes]
        evaluated = []
        real_score = p.score

        def score(genome):
            evaluated.append(genome[:])
            return real_score(genome)

        p.rng = Mock()
        p.rng.random.return_value = 1  # No injection, crossover or mutation.
        p.rng.randrange.side_effect = [2, 1, 3, 0, 2, 1]
        p.rng.choice.side_effect = lambda values: values[0]
        with patch.object(p, "initial_genome", return_value=genomes[0]), \
             patch.object(p, "specimen", side_effect=genomes[1:]), patch.object(p, "score", side_effect=score):
            result = search_python(p)
        self.assertEqual(evaluated, original + [original[3]])
        self.assertEqual(genomes, original)
        self.assertEqual(p.rng.randrange.call_count, 6)  # Two independent tournaments.
        self.assertEqual(result["fitness"], fitness(Circuit.from_dict(result["circuit"]), p.dataset))

    def test_initialization_honors_cancellation(self):
        cancelled = threading.Event()
        p = Problem(preset("xor"), SearchConfig(gates=1, backend="python"), cancel_event=cancelled)
        real_specimen = p.specimen

        def specimen():
            cancelled.set()
            return real_specimen()

        with patch.object(p, "initial_genome", return_value=[0, 0, 0]), \
             patch.object(p, "specimen", side_effect=specimen):
            with self.assertRaises(SearchCancelled):
                search_python(p)
        self.assertEqual(p.evaluations, 1)

    def test_time_limit_can_stop_partway_through_initialization(self):
        p = Problem(preset("xor"), SearchConfig(gates=1, population=4, backend="python"))
        with patch.object(p, "expired", side_effect=[False, True, True]):
            result = search_python(p)
        self.assertEqual(result["search"]["evaluations"], 2)
        self.assertEqual(result["search"]["parent_population"], 2)
        self.assertEqual(result["search"]["generation"], 0)

    def test_exact_incumbent_stops_without_filling_unused_population(self):
        p = Problem(preset("nand"), SearchConfig(gates=2, backend="python"),
                    incumbent=Circuit(2, ((0, 1),), (2,)))
        result = search_python(p)
        self.assertEqual(result["search"]["evaluations"], 1)
        self.assertEqual(result["search"]["parent_population"], 1)
        self.assertTrue(result["fitness"]["verified_truth_table"])

    def test_budget_includes_initial_population_and_retains_absolute_limit(self):
        config = SearchConfig(population=25, generations=20000)
        config.validate()  # Existing maximum-size requests remain valid.
        self.assertEqual(config.evaluation_budget, 500000)
        with self.assertRaises(ValueError):
            SearchConfig(population=26, generations=20000).validate()

    def test_both_backends_fill_population_and_stop_within_budget(self):
        backends = ["python"]
        try:
            tiny_interpreter()
            backends.append("tiny")
        except ValueError:
            pass
        for backend in backends:
            for population in (2, 5):
                with self.subTest(backend=backend, population=population):
                    config = SearchConfig(gates=1, population=population, generations=3, backend=backend)
                    # XOR cannot be represented with one NAND, so no early success.
                    result = search(preset("xor"), config)
                    self.assertEqual(result["search"]["evaluations"], config.evaluation_budget)
                    self.assertEqual(result["search"]["parent_population"], population)
                    self.assertEqual(result["search"]["generation"], 3)
                    self.assertEqual(result["search"]["selection"], "tournament")
                    self.assertEqual(result["search"]["tournament_size"], min(3, population))
                    expected = fitness(Circuit.from_dict(result["circuit"]), preset("xor"))
                    self.assertEqual(result["fitness"], expected)
                    repeat = search(preset("xor"), config)
                    self.assertEqual(result["circuit"], repeat["circuit"])
                    self.assertEqual(result["search"]["history"], repeat["search"]["history"])

    def test_elite_history_and_final_result_match_independent_evaluation(self):
        for seed in range(5):
            with self.subTest(seed=seed):
                config = SearchConfig(gates=8, population=12, generations=60, seed=seed,
                                      backend="python", optimize=True)
                dataset = generate("half-adder", 2, 2, "x0 + x1")
                result = search(dataset, config)
                history = result["search"]["history"]
                scores = [entry["score"] for entry in history]
                self.assertEqual(scores, sorted(set(scores), reverse=True))
                expected = fitness(Circuit.from_dict(result["circuit"]), dataset)
                self.assertEqual(result["fitness"], expected)
                self.assertEqual(scores[-1], expected["errors"] * 81 + expected["gates"] * 9 + expected["depth"])


class IslandTests(unittest.TestCase):
    def backends(self):
        yield "python"
        try:
            tiny_interpreter()
        except ValueError:
            return
        yield "tiny"

    def test_diversity_matches_pairwise_gene_comparison(self):
        genomes = [[0, 0, 1], [0, 0, 1], [1, 0, 2], [1, 1, 2]]
        pairs = list(itertools.combinations(genomes, 2))
        expected = sum(a != b for x, y in pairs for a, b in zip(x, y)) / (len(pairs) * 3)
        measured = diversity(genomes)
        self.assertEqual(measured["unique_genomes"], 3)
        self.assertEqual(measured["unique_fraction"], .75)
        self.assertEqual(measured["mean_hamming"], expected)
        for group in ([], [[0, 1]], [[0, 1]] * 4):
            self.assertEqual(diversity(group)["mean_hamming"], 0)

    def test_invalid_partition_and_restart_budgets_are_rejected(self):
        invalid = [{"restarts": v} for v in (0, 33, True, 1.5)]
        invalid += [{"islands": v} for v in (0, 17, True, 2.5)]
        invalid += [{"migration_interval": v} for v in (0, 20001, False, "10")]
        invalid += [{"population": 5, "islands": 3}, {"population": 4, "generations": 1, "restarts": 2}]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                SearchConfig(**kwargs).validate()

    def test_migration_snapshots_all_sources_and_never_replaces_a_better_member(self):
        populations = [[[0], [1]], [[2], [3]], [[4], [5]]]
        ranks = [[1, 2], [10, 11], [20, 21]]
        self.assertEqual(migrate(populations, ranks), 2)
        # The third island receives the original second island's elite, not a cascade of the first.
        self.assertEqual(populations, [[[0], [1]], [[2], [0]], [[4], [2]]])
        self.assertEqual(ranks, [[1, 2], [10, 1], [20, 10]])
        populations[0][0][0] = 99
        self.assertEqual(populations[1][1], [0])

    def test_both_backends_share_budget_across_reproducible_restarts_and_islands(self):
        dataset = preset("xor")  # Impossible with one NAND; exhaust all restart quotas.
        for backend in self.backends():
            with self.subTest(backend=backend):
                config = SearchConfig(gates=1, population=7, generations=9, seed=2**31-1,
                                      restarts=3, islands=3, migration_interval=1, backend=backend)
                result = search(dataset, config)
                info = result["search"]
                self.assertEqual(info["evaluations"], 64)
                self.assertEqual(info["restarts_completed"], 3)
                self.assertEqual([r["seed"] for r in info["runs"]], [2**31-1, 0, 1])
                self.assertEqual([r["evaluations"] for r in info["runs"]], [21, 21, 22])
                self.assertTrue(all(r["island_populations"] == [3, 2, 2] for r in info["runs"]))
                self.assertTrue(all(r["migrations"] > 0 for r in info["runs"]))
                self.assertEqual(len(info["diversity_history"]), 6)
                self.assertEqual(result["fitness"], fitness(Circuit.from_dict(result["circuit"]), dataset))
                history = [h["score"] for h in info["history"]]
                self.assertEqual(history, sorted(set(history), reverse=True))
                self.assertEqual(history[-1], min(r["best_score"] for r in info["runs"]))
                repeat = search(dataset, config)
                self.assertEqual(result["circuit"], repeat["circuit"])
                for field in ("history", "runs", "diversity_history"):
                    self.assertEqual(info[field], repeat["search"][field])

    def test_restarts_do_not_seed_from_previous_winner(self):
        p = Problem(preset("xor"), SearchConfig(gates=1, population=2, generations=2,
                                               restarts=2, backend="python"))
        # Two runs containing initialization only (plus one final offspring).
        with patch.object(p, "initial_genome", return_value=[0, 1, 2]) as initial, \
             patch.object(p, "specimen", return_value=[0, 0, 0]):
            result = search_python(p)
        self.assertEqual(initial.call_count, 1)
        self.assertLess(result["search"]["runs"][0]["best_score"], result["search"]["runs"][1]["best_score"])
        self.assertEqual(result["circuit"], Circuit(2, ((0, 1),), (2,)).to_dict())

    def test_early_success_does_not_initialize_remaining_islands_or_restarts(self):
        for backend in self.backends():
            with self.subTest(backend=backend), tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as temp:
                library = Library(temp)
                library.save_program({"circuit": Circuit(2, ((0, 1),), (2,)).to_dict()}, preset("nand"))
                result = search(preset("nand"), SearchConfig(gates=2, population=6, generations=10,
                                restarts=3, islands=3, backend=backend), library, save=False)
                self.assertEqual(result["search"]["evaluations"], 1)
                self.assertEqual(result["search"]["restarts_completed"], 1)
                self.assertEqual(result["search"]["runs"][0]["island_populations"], [1, 0, 0])
                self.assertTrue(result["fitness"]["verified_truth_table"])

    def test_partial_initialization_time_limit_and_cancellation_between_restarts(self):
        p = Problem(preset("xor"), SearchConfig(gates=1, population=6, generations=5,
                                               restarts=2, islands=3, backend="python"))
        with patch.object(p, "expired", side_effect=[False] + [True] * 10):
            result = search_python(p)
        self.assertEqual(result["search"]["evaluations"], 2)
        self.assertEqual(result["search"]["runs"][0]["island_populations"], [2, 0, 0])
        cancelled = threading.Event()
        p = Problem(preset("xor"), SearchConfig(gates=1, population=2, generations=3,
                                               restarts=2, backend="python"), cancel_event=cancelled)
        observe = p.observe

        def cancel_after_run(*args):
            value = observe(*args)
            if args[2] == "final":
                cancelled.set()
            return value

        with patch.object(p, "observe", side_effect=cancel_after_run), self.assertRaises(SearchCancelled):
            search_python(p)

    def test_optimization_keeps_searching_after_exactness_across_restarts(self):
        config = SearchConfig(gates=2, population=6, generations=4, restarts=2, islands=3,
                              migration_interval=1, optimize=True, backend="python")
        result = search_python(Problem(preset("nand"), config, incumbent=Circuit(2, ((0, 1),), (2,))))
        self.assertEqual(result["search"]["evaluations"], config.evaluation_budget)
        self.assertEqual(result["search"]["restarts_completed"], 2)
        self.assertTrue(result["fitness"]["verified_truth_table"])

    def test_cli_saves_restart_and_diversity_metadata(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as temp:
            proc = subprocess.run([sys.executable, "-X", "utf8", "-m", "primitives", "--data-dir", temp, "evolve",
                                   "--preset", "xor", "--backend", "python", "--gates", "1",
                                   "--population", "6", "--generations", "4", "--restarts", "2",
                                   "--islands", "3", "--migration-interval", "1"], cwd=ROOT,
                                  capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            saved = Library(Path(temp)).load_program(result["id"])
            self.assertEqual(saved["search"]["restarts_completed"], 2)
            self.assertEqual(saved["search"]["islands"], 3)
            self.assertEqual(saved["search"]["diversity"], result["search"]["diversity"])


if __name__ == "__main__":
    unittest.main()

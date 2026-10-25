"""Population selection, independent fitness checks and search limits."""
import threading
import unittest
from unittest.mock import Mock, patch

from primitives.circuit import Circuit
from primitives.dataset import generate, preset
from primitives.evolution import Problem, SearchCancelled, SearchConfig, search_python, tournament
from primitives.library import fitness
from primitives.runner import search, tiny_interpreter


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


if __name__ == "__main__":
    unittest.main()

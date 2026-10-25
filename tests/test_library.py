import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from primitives.circuit import Circuit
from primitives.dataset import Dataset, generate, preset
from primitives.evolution import SearchConfig
from primitives.library import Library, fitness, write_json
from primitives.runner import ROOT, search


class RetestTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".jobs").mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".jobs")
        self.addCleanup(self.tmp.cleanup)
        self.library = Library(self.tmp.name)
        self.dataset = preset("and")
        self.exact = Circuit(2, ((0, 1), (2, 2)), (3,))
        self.approximate = Circuit(2, (), (0,))

    def result(self, circuit):
        return {"circuit": circuit.to_dict(), "fitness": {}, "search": {"history": []}}

    def save(self, circuit, dataset=None):
        return self.library.save_program(self.result(circuit), dataset or self.dataset)

    def test_worse_retest_keeps_old_program_even_with_fewer_gates(self):
        old = self.save(self.exact)
        # Stale or incorrect candidate metrics cannot overwrite the actual winner.
        candidate = self.result(self.approximate)
        candidate["fitness"] = {"errors": 0, "accuracy": 1}
        kept = self.library.save_program(candidate, self.dataset)
        self.assertEqual(kept["id"], old["id"])
        self.assertEqual(kept["created_at"], old["created_at"])
        self.assertFalse(kept["comparison"]["accepted"])
        self.assertEqual(kept["comparison"]["candidate_fitness"]["errors"], 1)
        self.assertEqual(len(self.library.programs()), 1)
        self.assertEqual(len(list((Path(self.tmp.name) / "programs").glob("*.json"))), 1)

    def test_better_retest_replaces_displayed_version_and_survives_reload(self):
        old = self.save(self.approximate)
        new = self.save(self.exact)
        self.assertTrue(new["comparison"]["accepted"])
        self.assertEqual(new["fitness"]["errors"], 0)
        reloaded = Library(self.tmp.name)
        self.assertEqual([p["id"] for p in reloaded.programs()], [new["id"]])
        self.assertEqual(reloaded.load_program(old["id"])["circuit"], old["circuit"])

    def test_equal_quality_keeps_old_version_and_simpler_exact_version_wins(self):
        redundant = Circuit(2, ((0, 1), (2, 2), (3, 3), (4, 4)), (5,))
        self.save(redundant)
        better = self.save(self.exact)
        self.assertTrue(better["comparison"]["accepted"])
        same = self.save(self.exact)
        self.assertFalse(same["comparison"]["accepted"])
        self.assertEqual(same["id"], better["id"])

    def test_depth_breaks_tie_after_accuracy_and_gate_count(self):
        deep = Circuit(2, ((0, 1), (2, 2), (3, 3)), (4,))
        shallow = Circuit(2, ((0, 0), (1, 1), (2, 3)), (4,))
        # Both circuits output 1 for this sample, with three active gates.
        dataset = Dataset("sample", 2, 1, [[0, 1, 1]])
        self.assertEqual(fitness(deep, dataset)["errors"], fitness(shallow, dataset)["errors"])
        self.save(deep, dataset)
        result = self.save(shallow, dataset)
        self.assertTrue(result["comparison"]["accepted"])
        self.assertEqual(result["fitness"]["depth"], 2)

    def test_same_vectors_ignore_label_and_metadata_but_different_tasks_stay_separate(self):
        old = self.save(self.exact)
        renamed = generate("AND renamed", 2, 1, "x0 & x1", seed=99)
        self.assertEqual(self.save(self.approximate, renamed)["id"], old["id"])
        self.save(self.exact, preset("or"))
        self.save(Circuit(1, ((0, 0),), (1,)), preset("not"))
        self.assertEqual(len(self.library.programs()), 3)

    def test_existing_duplicates_are_rechecked_and_only_best_is_listed(self):
        old = self.save(self.exact)
        duplicate = {**old, "id": "legacy-duplicate", "circuit": self.approximate.to_dict(),
                     "fitness": {"errors": 0, "accuracy": 1}}
        write_json(Path(self.tmp.name) / "programs" / "legacy-duplicate.json", duplicate)
        self.assertEqual([p["id"] for p in self.library.programs()], [old["id"]])
        self.assertEqual(self.save(self.approximate)["id"], old["id"])

    def test_search_returns_kept_program_with_comparison(self):
        old = self.save(self.exact)
        candidate = self.result(self.approximate)
        with patch("primitives.runner.search_python", return_value=candidate):
            result = search(self.dataset, SearchConfig(backend="python"), self.library)
        self.assertEqual(result["id"], old["id"])
        self.assertFalse(result["comparison"]["accepted"])


if __name__ == "__main__":
    unittest.main()

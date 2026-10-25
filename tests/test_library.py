import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from primitives.circuit import Circuit
from primitives.dataset import Dataset, generate, preset
from primitives.evolution import SearchConfig
from primitives.library import Library, fitness, function_id, write_json
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

    def test_legacy_expressions_are_displayed_infix_on_load(self):
        old = self.save(self.exact)
        old["expressions"] = ["((1,2),(1,2))"]
        write_json(Path(self.tmp.name) / "programs" / f'{old["id"]}.json', old)
        loaded = self.library.load_program(old["id"])
        self.assertEqual(loaded["expressions"], ["((1) ⊼ (2)) ⊼ ((1) ⊼ (2))"])
        self.assertEqual(loaded["circuit"], old["circuit"])

    def test_search_returns_kept_program_with_comparison(self):
        old = self.save(self.exact)
        candidate = self.result(self.approximate)
        with patch("primitives.runner.search_python", return_value=candidate):
            result = search(self.dataset, SearchConfig(backend="python"), self.library)
        self.assertEqual(result["id"], old["id"])
        self.assertFalse(result["comparison"]["accepted"])

    def test_delete_function_removes_all_samples_and_historical_programs(self):
        old = self.save(self.approximate)
        best = self.save(self.exact)
        sampled = preset("and", samples=2, seed=8)
        sample_id = self.library.save_dataset(sampled)
        other = self.save(self.exact, preset("or"))
        self.library.set_frozen(best["id"], True)
        block = self.library.block_from_program(best["id"], "Bleibender Baustein")
        deleted = self.library.delete_function(function_id(self.dataset))
        self.assertEqual(set(deleted["dataset_ids"]), {old["dataset_id"], sample_id})
        self.assertEqual(set(deleted["program_ids"]), {old["id"], best["id"]})
        reloaded = Library(self.tmp.name)
        self.assertEqual([p["id"] for p in reloaded.programs()], [other["id"]])
        self.assertEqual([d["id"] for d in reloaded.datasets()], [other["dataset_id"]])
        self.assertFalse(reloaded.is_frozen(best["task_id"]))
        self.assertEqual(reloaded.load_block(block.root).to_dict(), block.to_dict())
        for key in deleted["dataset_ids"]:
            with self.assertRaises(FileNotFoundError): reloaded.load_dataset(key)
        for key in deleted["program_ids"]:
            with self.assertRaises(FileNotFoundError): reloaded.load_program(key)

    def test_delete_function_preserves_circuits_shared_with_other_function(self):
        old = self.save(self.approximate)
        best = self.save(self.exact)
        equivalent = generate("AND anders beschrieben", 2, 1, "x1 & x0")
        self.assertNotEqual(function_id(self.dataset), function_id(equivalent))
        equivalent_id = self.library.save_dataset(equivalent)
        self.library.set_frozen(best["id"], True)
        deleted = self.library.delete_function(function_id(self.dataset))
        self.assertEqual(deleted["program_ids"], [])
        reloaded = Library(self.tmp.name)
        self.assertEqual([d["id"] for d in reloaded.datasets()], [equivalent_id])
        for program in (old, best):
            saved = reloaded.load_program(program["id"])
            self.assertEqual(saved["dataset_id"], equivalent_id)
            self.assertEqual(saved["dataset_name"], equivalent.name)
            self.assertEqual(saved["dataset_metadata"], equivalent.metadata)
            self.assertTrue(saved["frozen"])
        self.assertEqual(reloaded.programs()[0]["id"], best["id"])
        # Deleting the final reference now removes both circuit versions too.
        deleted = reloaded.delete_function(function_id(equivalent))
        self.assertEqual(set(deleted["program_ids"]), {old["id"], best["id"]})
        self.assertEqual(reloaded.programs(), [])

    def test_delete_function_without_circuit_and_invalid_ids(self):
        key = self.library.save_dataset(self.dataset)
        for invalid in ("../outside", "AND", None):
            with self.subTest(key=invalid), self.assertRaises(ValueError):
                self.library.delete_function(invalid)
        with self.assertRaises(FileNotFoundError):
            self.library.delete_function("000000000000")
        self.assertEqual(self.library.load_dataset(key).to_dict(), self.dataset.to_dict())
        deleted = self.library.delete_function(function_id(self.dataset))
        self.assertEqual(deleted["dataset_ids"], [key])
        self.assertEqual(deleted["program_ids"], [])
        self.assertEqual(self.library.datasets(), [])

    def test_function_details_apply_to_samples_exports_and_old_circuits_without_new_ids(self):
        old = self.save(self.approximate)
        best = self.save(self.exact)
        sample_id = self.library.save_dataset(preset("and", samples=2, seed=8))
        ids = {old["dataset_id"], sample_id}
        key = function_id(self.dataset)
        updated = self.library.update_function(key, "  Mein UND  ", "Zwei Bits verknüpfen.\nFür den Handtest.")
        self.assertEqual(set(updated["dataset_ids"]), ids)
        library = Library(self.tmp.name)
        self.assertEqual({d["id"] for d in library.datasets()}, ids)
        for d in library.datasets():
            self.assertEqual(d["function_name"], "Mein UND")
            self.assertEqual(d["description"], updated["description"])
        for program in (old, best):
            loaded = library.load_program(program["id"])
            self.assertEqual(loaded["dataset_name"], "Mein UND")
            self.assertEqual(loaded["dataset_metadata"]["description"], updated["description"])
            self.assertEqual(loaded["circuit"], program["circuit"])
        document = library.dataset_document(library.load_dataset(sample_id))
        imported = Dataset.from_dict(document)
        self.assertEqual(function_id(imported), key)
        self.assertEqual(imported.name, "Mein UND")
        self.assertEqual(imported.metadata["description"], updated["description"])
        # A background retest keeps using the original stored dataset, avoiding copies.
        self.assertEqual(library.save_program(self.result(self.exact), self.dataset)["id"], best["id"])
        self.assertEqual({d["id"] for d in library.datasets()}, ids)

    def test_function_details_validate_text_clear_description_and_stay_isolated(self):
        self.library.save_dataset(self.dataset)
        other_id = self.library.save_dataset(preset("or"))
        key = function_id(self.dataset)
        for name, description in [(" ", ""), ("x" * 121, ""), (None, ""), ("ok", None), ("ok", "x" * 4001)]:
            with self.subTest(name=str(name)[:12]), self.assertRaises(ValueError):
                self.library.update_function(key, name, description)
        with self.assertRaises(ValueError): self.library.update_function("../outside", "ok", "")
        with self.assertRaises(FileNotFoundError): self.library.update_function("000000000000", "ok", "")
        self.library.update_function(key, "Name", "Beschreibung")
        self.library.update_function(key, "Name", "")
        self.assertEqual(next(d for d in self.library.datasets() if d["function_id"] == key)["description"], "")
        self.assertEqual(self.library.dataset_document(self.library.load_dataset(other_id))["name"], "or")
        self.library.delete_function(key)
        self.assertNotIn(key, self.library._function_details())


if __name__ == "__main__":
    unittest.main()

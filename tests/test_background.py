import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from primitives.background import BackgroundOptimizer
from primitives.circuit import Circuit
from primitives.dataset import preset
from primitives.evolution import Problem, SearchConfig, search_python
from primitives.library import Library, write_json
from primitives.runner import ROOT, search
from test_repair import MUL_APPROXIMATION


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".jobs").mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".jobs")
        self.addCleanup(self.tmp.cleanup)
        self.library = Library(self.tmp.name)
        self.optimizer = BackgroundOptimizer(self.library, interval=0)
        self.addCleanup(self.optimizer.close)

    def save(self, circuit, name="nand"):
        return self.library.save_program({"circuit": circuit.to_dict(), "search": {"history": []}}, preset(name))

    def test_real_worker_repairs_mul_and_commits_only_one_winner(self):
        old = self.save(MUL_APPROXIMATION, "mul")
        self.optimizer.tick()
        worker = self.optimizer._process
        self.assertIsNotNone(worker)
        self.assertEqual(worker.wait(timeout=15), 0)
        result = json.loads((Path(self.optimizer._folder.name) / "result.json").read_text())
        self.assertTrue(result["fitness"]["verified_truth_table"])
        self.optimizer.tick()
        programs = self.library.programs()
        self.assertEqual(len(programs), 1)
        self.assertNotEqual(programs[0]["id"], old["id"])
        self.assertTrue(programs[0]["fitness"]["verified_truth_table"])
        self.assertIn("bessere Version", self.optimizer.status()["message"])

    def test_frozen_is_persistent_cancels_worker_and_prevents_late_save(self):
        old = self.save(Circuit(2, (), (0,)), "and")
        self.optimizer.tick()
        worker = self.optimizer._process
        self.library.set_frozen(old["id"], True)
        self.optimizer.cancel_task(old["task_id"])
        self.assertIsNotNone(worker.poll())
        self.assertIsNone(self.optimizer._process)
        self.optimizer.tick()
        self.assertIsNone(self.optimizer._process)
        reloaded = Library(self.tmp.name)
        self.assertTrue(reloaded.programs()[0]["frozen"])
        exact = {"circuit": Circuit(2, ((0, 1), (2, 2)), (3,)).to_dict(), "search": {"history": []}}
        self.assertIsNone(self.library.save_program(exact, preset("and"), background=True))
        self.assertEqual(self.library.programs()[0]["id"], old["id"])
        # An explicit manual change is allowed and inherits the task's freeze.
        better = self.library.save_program(exact, preset("and"))
        self.assertTrue(better["frozen"])
        self.library.set_frozen(old["id"], False)
        self.assertFalse(reloaded.programs()[0]["frozen"])

    def test_manual_search_preempts_and_resumes_background_worker(self):
        self.save(Circuit(2, ((0, 1),), (2,)))
        self.optimizer.tick()
        worker = self.optimizer._process
        self.optimizer.pause()
        self.assertIsNotNone(worker.poll())
        self.optimizer.tick()
        self.assertIsNone(self.optimizer._process)
        self.assertEqual(self.optimizer.status()["status"], "paused")
        self.optimizer.resume()
        self.optimizer.tick()
        self.assertIsNotNone(self.optimizer._process)

    def test_round_robin_skips_frozen_and_uses_idle_priority(self):
        self.save(Circuit(2, ((0, 1),), (2,)))
        self.save(Circuit(2, (), (0,)), "and")
        frozen = self.save(Circuit(2, (), (0,)), "or")
        self.library.set_frozen(frozen["id"], True)
        seen = []
        with patch("primitives.background.subprocess.Popen") as spawn:
            worker = Mock()
            worker.poll.return_value = None
            spawn.return_value = worker
            for _ in range(2):
                self.optimizer.tick()
                task = self.optimizer._task
                seen.append(task["task_id"])
                current = next(p for p in self.library.programs() if p["task_id"] == task["task_id"])
                write_json(Path(self.optimizer._folder.name) / "result.json", current)
                worker.poll.return_value = 0
                self.optimizer.tick()
                worker.poll.return_value = None
            self.assertEqual(len(set(seen)), 2)
            self.assertNotIn(frozen["task_id"], seen)
            if os.name == "nt":
                self.assertEqual(spawn.call_args.kwargs["creationflags"],
                                 subprocess.CREATE_NO_WINDOW | subprocess.IDLE_PRIORITY_CLASS)

    def test_close_stops_thread_and_child_and_cleans_temporary_files(self):
        self.save(Circuit(2, ((0, 1),), (2,)))
        self.optimizer.start()
        deadline = time.monotonic() + 5
        while self.optimizer.status()["attempts"] == 0 and time.monotonic() < deadline:
            time.sleep(0.02)
        worker = self.optimizer._process
        self.assertIsNotNone(worker)
        folder = Path(self.optimizer._folder.name)
        self.optimizer.close()
        self.assertFalse(self.optimizer._thread.is_alive())
        self.assertIsNotNone(worker.poll())
        self.assertFalse(folder.exists())

    def test_exact_incumbent_is_still_optimized(self):
        redundant = Circuit(2, ((0, 1), (2, 2), (3, 3), (4, 4)), (5,))
        config = SearchConfig(gates=6, population=12, generations=30, backend="python", optimize=True)
        result = search_python(Problem(preset("and"), config, incumbent=redundant))
        self.assertGreater(result["search"]["evaluations"], 1)
        self.assertEqual(result["search"]["generation"], 30)
        self.assertTrue(result["fitness"]["verified_truth_table"])
        self.assertLessEqual(result["fitness"]["gates"], len(redundant.gates))

    def test_auto_repair_can_correct_the_previous_winner_and_save_false_never_commits(self):
        old = self.save(MUL_APPROXIMATION, "mul")
        config = SearchConfig(gates=1, population=2, generations=1, backend="python", repair_cases=4)
        result = search(preset("mul"), config, self.library, save=False)
        self.assertTrue(result["fitness"]["verified_truth_table"])
        self.assertEqual(self.library.programs()[0]["id"], old["id"])

    def test_time_limit_stops_a_worker_and_enforces_a_cooldown(self):
        self.save(Circuit(2, ((0, 1),), (2,)))
        self.optimizer.interval = 5
        self.optimizer._next_due = 0
        with patch("primitives.background.subprocess.Popen") as spawn:
            worker = Mock()
            worker.poll.return_value = None
            spawn.return_value = worker
            self.optimizer.tick()
            folder = Path(self.optimizer._folder.name)
            self.optimizer._started = time.monotonic() - 10
            self.optimizer.tick()
            worker.terminate.assert_called_once()
            self.assertFalse(folder.exists())
            self.assertEqual(self.optimizer.status()["message"], "Zeitbudget erreicht.")
            self.optimizer.tick()
            self.assertEqual(spawn.call_count, 1)

    def test_zero_time_budget_keeps_incumbent_without_exploring(self):
        incumbent = Circuit(2, ((0, 1),), (2,))
        config = SearchConfig(gates=4, backend="python", optimize=True)
        result = search_python(Problem(preset("nand"), config, incumbent=incumbent, time_budget=0))
        self.assertEqual(result["circuit"], incumbent.to_dict())
        self.assertEqual(result["search"]["evaluations"], 1)


if __name__ == "__main__":
    unittest.main()

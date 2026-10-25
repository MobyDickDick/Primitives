import threading
import unittest

from primitives.program import Program, ProgramCancelled
from primitives.dataset import generate, integer


PORTS = {"inputs": [{"name": "n", "bits": 4}], "outputs": [{"name": "c", "bits": 8}]}
SUM = 's = 0\ni = 0\nlabel("loop")\njump_if(i >= n, "done")\ns += i\ni += 1\ngoto("loop")\nlabel("done")\nreturn s'


def program(source, **limits):
    return Program({"version": 1, "source": source, "limits": limits}, PORTS)


class ProgramDebugTests(unittest.TestCase):
    def finish(self, execution, count=1):
        while execution.status not in ("done", "failed"):
            execution.step(count)
        return execution.snapshot()

    def test_forward_backward_and_all_conditional_paths(self):
        p = program(SUM)
        ds = generate("Sprungsumme", 4, 8, ports=PORTS, program=p.spec)
        for row in ds.rows:
            n = integer(row[:4])
            self.assertEqual(integer(row[4:]), n * (n - 1) // 2)
        for command, predicate in (("jump_zero", lambda n: n == 0),
                                   ("jump_nonzero", lambda n: n != 0),
                                   ("jump_negative", lambda n: n < 0),
                                   ("jump_if", lambda n: n != 0)):
            p = program(f'{command}(n - 7, "yes")\nreturn 1\nlabel("yes")\nreturn 2')
            for n in range(16):
                self.assertEqual(p.run(n), [2 if predicate(n - 7) else 1])

    def test_step_continue_and_run_have_identical_results_and_budgets(self):
        sources = [SUM, 's = 0\nfor i in range(n):\n    if i % 2:\n        s += i\nreturn s',
                   'a = bits(n, 4)\na[0] ^= 1\nreturn pack(a)',
                   's = 0\nwhile s < n:\n    s += 1\nreturn s']
        for source in sources:
            p = program(source)
            for n in range(16):
                budget = p.budget()
                expected = p.run(n, budget)
                for count in (1, 100):
                    snapshot = self.finish(p.debug(n), count)
                    self.assertEqual(snapshot["status"], "done", snapshot)
                    self.assertEqual(snapshot["result"], [str(v) for v in expected])
                    self.assertEqual(snapshot["steps"], budget.steps)
                    self.assertEqual(snapshot["iterations"], budget.iterations)

    def test_reset_stop_snapshot_arrays_and_exact_large_integers(self):
        execution = program('a = [0, 0]\na[0] = 1\ns = 2 ** 32\nreturn pack(a)').debug(5)
        initial = execution.snapshot()
        execution.step()
        before = execution.snapshot()
        execution.step()
        self.assertEqual(before["variables"]["a"], [0, 0])
        stopped = execution.stop()
        self.assertEqual(stopped["status"], "stopped")
        self.assertEqual(execution.snapshot(), stopped)
        final = self.finish(execution)
        self.assertEqual(final["variables"]["s"], "4294967296")
        self.assertEqual(execution.reset(), initial)
        self.assertEqual(self.finish(execution), final)

    def test_invalid_targets_and_block_entry_rejected_before_execution(self):
        sources = ['goto("missing")\nreturn 0', 'label("a")\nlabel("a")\nreturn 0',
                   'goto(n)\nreturn 0', 'goto("bad-name")\nreturn 0',
                   'jump_if(1, "x", "y")\nreturn 0', 'label(name="x")\nreturn 0',
                   'goto("inside")\nfor i in range(n):\n    label("inside")\nreturn 0',
                   'if n:\n    goto("other")\nelse:\n    label("other")\nreturn 0',
                   'label("outer")\nif n:\n    label("inner")\ngoto("inner")\nreturn 0',
                   'jump_error("x")\nreturn 0', 'return goto']
        for source in sources:
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "Zeile"):
                program(source)

    def test_structured_blocks_can_exit_and_restart_for_loop(self):
        p = program('s = 0\nlabel("restart")\nfor i in range(n):\n    if s == 2:\n        goto("done")\n    s += 1\nlabel("done")\nreturn s')
        self.assertEqual([p.run(n) for n in range(4)], [[0], [1], [2], [2]])
        p = program('s = 0\nlabel("restart")\nfor i in range(2):\n    s += 1\n    jump_if(s < 3, "restart")\nreturn s')
        self.assertEqual(p.run(5), [4])
        p = program('goto("done")\nc = 1\nlabel("done")\nreturn c')
        with self.assertRaisesRegex(ValueError, "x=0.*noch nicht zugewiesen"):
            p.run(0)

    def test_back_jumps_limits_cancellation_and_debug_failures(self):
        loop = 'label("loop")\ngoto("loop")\nreturn 0'
        for limits, message in (({"steps": 8}, "Anweisungsbudget"),
                                ({"iterations": 2}, "Iterationsbudget"),
                                ({"total_steps": 8}, "Gesamtbudget")):
            p = program(loop, **limits)
            with self.assertRaisesRegex(ValueError, f"x=3.*Zeile.*{message}"):
                p.run(3)
            snapshot = self.finish(p.debug(3))
            self.assertEqual(snapshot["status"], "failed")
            self.assertIn(message, snapshot["error"])
        event = threading.Event(); event.set()
        p = program(loop)
        with self.assertRaises(ProgramCancelled):
            p.run(0, p.budget(event))
        snapshot = self.finish(program("return 256").debug(0))
        self.assertEqual(snapshot["status"], "failed")
        self.assertIn("Ausgabe c", snapshot["error"])
        for x in (-1, 16, True, "5"):
            with self.assertRaises(ValueError):
                program(SUM).debug(x)


if __name__ == "__main__":
    unittest.main()

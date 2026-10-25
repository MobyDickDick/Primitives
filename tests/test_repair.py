import unittest

from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, preset
from primitives.library import fitness
from primitives.repair import repair_result


MUL_APPROXIMATION = Circuit(4, ((3, 0), (2, 0), (1, 3), (1, 2), (4, 7),
                                (5, 5), (6, 6), (9, 10), (11, 11)), (9, 8, 10, 12))


class RepairTests(unittest.TestCase):
    def result(self, circuit):
        return {"circuit": circuit.to_dict(), "search": {"history": []}}

    def test_mul_last_case_is_compiled_into_nand_gates(self):
        original = MUL_APPROXIMATION
        dataset = preset("mul")
        repaired = repair_result(self.result(original), dataset)
        circuit = Circuit.from_dict(repaired["circuit"])
        self.assertEqual(circuit.evaluate([1, 1, 1, 1]), [1, 0, 0, 1])
        for row in dataset.rows:
            self.assertEqual(circuit.evaluate(row[:4]), row[4:])
            if row[:4] != [1, 1, 1, 1]:
                self.assertEqual(circuit.evaluate(row[:4]), original.evaluate(row[:4]))
        self.assertTrue(repaired["fitness"]["verified_truth_table"])
        self.assertEqual(len(circuit.gates), 20)
        self.assertEqual(repaired["correction"]["added_gates"], 11)

    def test_multiple_cases_can_force_both_zero_and_one(self):
        original = Circuit(4, (), (0, 1, 2, 3))
        exceptions = {0, 5, 10, 15}
        rows = [bits(x, 4) + ([1-b for b in bits(x, 4)] if x in exceptions else bits(x, 4))
                for x in range(16)]
        dataset = Dataset("exceptions", 4, 4, rows)
        repaired = repair_result(self.result(original), dataset)
        circuit = Circuit.from_dict(repaired["circuit"])
        for row in rows:
            self.assertEqual(circuit.evaluate(row[:4]), row[4:])
        self.assertEqual(len(repaired["correction"]["cases"]), 4)
        self.assertEqual(fitness(circuit, dataset)["errors"], 0)

    def test_sample_repair_does_not_claim_complete_truth_table(self):
        original = Circuit(3, (), (0,))
        rows = [bits(x, 3) + [1 if x == 0 else x & 1] for x in range(4)]
        repaired = repair_result(self.result(original), Dataset("sample", 3, 1, rows))
        circuit = Circuit.from_dict(repaired["circuit"])
        self.assertTrue(repaired["fitness"]["exact_on_dataset"])
        self.assertFalse(repaired["fitness"]["verified_truth_table"])
        for x in range(4, 8):
            self.assertEqual(circuit.evaluate(bits(x, 3)), original.evaluate(bits(x, 3)))

    def test_many_failures_and_already_exact_circuits_are_not_patched(self):
        for circuit, dataset in ((Circuit(2, (), (0,)), preset("xor")),
                                 (Circuit(2, ((0, 1),), (2,)), preset("nand"))):
            result = self.result(circuit)
            self.assertIs(repair_result(result, dataset), result)
        result = self.result(MUL_APPROXIMATION)
        self.assertIs(repair_result(result, preset("mul"), max_cases=0), result)

    def test_gate_limit_does_not_create_an_invalid_circuit(self):
        original = Circuit(4, tuple((i+3, i+3) for i in range(512)), (515,))
        rows = [bits(x, 4) + [original.evaluate(bits(x, 4))[0] ^ (x == 15)] for x in range(16)]
        # Dataset bits are integers, including the toggled target.
        dataset = Dataset("large", 4, 1, rows)
        result = self.result(original)
        self.assertIs(repair_result(result, dataset), result)


if __name__ == "__main__":
    unittest.main()

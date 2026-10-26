"""Compile a small number of exact input exceptions into ordinary NAND gates."""
from .circuit import Circuit
from .library import fitness
from .evolution import check_cancelled
from .ancestry import transformed


def repair_result(result, dataset, max_cases=4, *, cancel_event=None):
    circuit = Circuit.from_dict(result["circuit"]).compact()
    failures = []
    for row in dataset.rows:
        check_cancelled(cancel_event)
        inputs, expected = row[:dataset.inputs], row[dataset.inputs:]
        actual = circuit.evaluate(inputs)
        if actual != expected:
            failures.append({"inputs": inputs, "expected": expected, "actual": actual})
            if len(failures) > max_cases:
                return result
    if not failures or len(failures) * 4 > len(dataset.rows):
        return result

    gates, outputs = list(circuit.gates), list(circuit.outputs)
    known = {tuple(sorted(pair)): circuit.inputs + i for i, pair in enumerate(gates)}

    def nand(a, b):
        pair = tuple(sorted((a, b)))
        if pair not in known:
            if len(gates) >= 512:
                raise OverflowError
            known[pair] = circuit.inputs + len(gates)
            gates.append(pair)
        return known[pair]

    def invert(a):
        return nand(a, a)

    def conjunction(a, b):
        return invert(nand(a, b))

    try:
        for case in failures:
            literals = [i if bit else invert(i) for i, bit in enumerate(case["inputs"])]
            match = literals[0]
            for literal in literals[1:]:
                match = conjunction(match, literal)
            for i, (actual, expected) in enumerate(zip(case["actual"], case["expected"])):
                if actual != expected:
                    outputs[i] = (nand(invert(outputs[i]), invert(match)) if expected
                                  else conjunction(outputs[i], invert(match)))
        corrected = Circuit(circuit.inputs, tuple(gates), tuple(outputs)).compact()
    except OverflowError:
        return result
    checked = fitness(corrected, dataset)
    if checked["errors"]:
        raise ValueError("Die Restfallkorrektur hat die Gegenprüfung nicht bestanden.")
    # Corrections change the implementation; the old hierarchy is no longer exact.
    result = {k: v for k, v in result.items() if k != "hierarchy"}
    result = transformed(result, "repair", corrected, method="nand-exceptions", cases=failures)
    return {**result, "circuit": corrected.to_dict(), "fitness": checked,
            "correction": {"method": "nand-exceptions", "cases": failures,
                           "base_gates": len(circuit.gates),
                           "added_gates": len(corrected.gates) - len(circuit.gates)}}

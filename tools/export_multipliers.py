"""Export and independently verify GEN-11: python -m tools.export_multipliers."""
from functools import lru_cache
from itertools import product

from primitives.blocks import BlockBundle
from primitives.dataset import Dataset, bits
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import ports
from tools.export_generative import netlist
from tools.export_parallel_add import ROOT, TEMPLATES, WIDTHS, write_json
from tools.export_recursive_mul import helper as recursive_helper
from tools.export_standard_arithmetic import definition as standard_definition


KINDS = ("array", "wallace")
OUTPUT = ROOT / "examples/circuits/multipliers"


def definition(kind):
    if kind not in KINDS:
        raise ValueError("Unknown multiplier construction")
    conditions = ["p >= 1", "q >= 1", "p + q <= 64"]
    if kind == "wallace":
        conditions.append("min(p,q)*(p+q) <= 128")
    return {
        "schema": 1, "kind": "template", "name": f"{kind.upper()}_MUL<p,q>",
        "description": ("Carry-Save-Array-Kaskade" if kind == "array" else
                        "Wallace-Baum mit zeilenweiser 3:2-Reduktion") +
            ": unsigned a[p], b[q], vollständiges Produkt c[p+q], LSB-first. "
            "Schmalerer Operand bestimmt die Zeilenzahl; abschliessender Ripple-Carry-Addierer. "
            "Keine Sättigung, kein Fehlerflag, kein Minimalitätsnachweis. "
            "Interne Bitarrays maximal 128 Bits; NAND-Netze/F-Boxen maximal 512 Gatter.",
        "parameters": ["p", "q"], "conditions": conditions,
        "interface": ports([("a", "p"), ("b", "q")], [("c", "p+q")]),
        "source": (TEMPLATES / f"{kind}-mul.prim").read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


@lru_cache(maxsize=None)
def bundle(kind, p, q):
    program = Template(definition(kind)).instantiate({"p": p, "q": q})
    return BlockBundle.from_circuit(f"{kind.upper()}_MUL<{p},{q}>", synthesize(program), program.ports)


def recursive_program(p, q):
    """Full recursive product, zero-padded to the next power-of-two width.

    The public MUL<w> clips to w bits and reports an error. Use its existing
    MUL_raw<w> core instead so all constructions have the same full product.
    """
    width = 1 << (max(p, q) - 1).bit_length()
    return recursive_helper(width, "MUL_raw_full", [("a", p), ("b", q)], p + q,
                            f"pack(bits(MUL_raw<w>(a,b),{p+q}))")


def comparison_programs(p, q):
    return {**{kind: Template(definition(kind)).instantiate({"p": p, "q": q}) for kind in KINDS},
            "shift_add": Template(standard_definition("mul")).instantiate({"p": p, "q": q}),
            "recursive_full": recursive_program(p, q)}


def comparison(p, q):
    return {kind: {"gates": len(circuit.gates), "depth": circuit.depth}
            for kind, program in comparison_programs(p, q).items()
            for circuit in [synthesize(program)]}


def export():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reports = []
    for kind in KINDS:
        template = Template(definition(kind))
        write_json(TEMPLATES / f"{kind}-mul.abstract.json", template.to_dict())
        for p, q in product(WIDTHS, repeat=2):
            name = f"{kind.upper()}_MUL<{p},{q}>"
            program = template.instantiate({"p": p, "q": q})
            hierarchy = bundle(kind, p, q)
            expanded, compiled = hierarchy.expand(), synthesize(program)
            circuit = expanded.simplify()
            comparisons = [synthesize(other) for other in comparison_programs(p, q).values()]
            rows = []
            for a, b in product(range(1 << p), range(1 << q)):
                expected = a * b  # Independent integer multiplication.
                inputs, outputs = bits(a, p) + bits(b, q), bits(expected, p + q)
                if program.run(a | b << p) != [expected] or any(
                        impl.evaluate(inputs) != outputs for impl in
                        (hierarchy, expanded, circuit, compiled, *comparisons)):
                    raise ValueError(f"{name} failed for a={a}, b={b}")
                rows.append(inputs + outputs)
            dataset = Dataset(name, p + q, p + q, rows,
                {"program": program.spec, "interface": program.ports, "description": template.document["description"]})
            checked = fitness(circuit, dataset)
            if not checked["verified_truth_table"]:
                raise ValueError("Export requires a fully verified truth table")
            prefix = OUTPUT / f"{kind}-{p}-{q}"
            for suffix, document in (("block", hierarchy.to_dict()), ("circuit", circuit.to_dict()),
                                     ("template", program.spec), ("vectors", dataset.to_dict())):
                write_json(prefix.with_suffix(f".{suffix}.json"), document)
            prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program, name), encoding="utf-8", newline="\n")
            reports.append({"name": name, "kind": kind, "parameters": {"p": p, "q": q},
                "interface": program.ports, "fitness": checked, "hierarchy": hierarchy.summary(),
                "synthesis": {"method": "structural-carry-save", "version": 1},
                "comparison": comparison(p, q)})
            print(f"{name}: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(rows)} inputs verified", flush=True)
    write_json(OUTPUT / "verification.json", reports)


if __name__ == "__main__":
    export()

"""Export and independently verify GEN-10: python -m tools.export_signed_arithmetic."""
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


KINDS = ("cmp", "add", "sub", "mul", "div")
OUTPUT = ROOT / "examples/circuits/signed-arithmetic"


def definition(kind):
    outputs = {
        "cmp": [("lt", 1), ("eq", 1), ("gt", 1)],
        "add": [("c", "max(p,q)"), ("overflow", 1)],
        "sub": [("c", "max(p,q)"), ("overflow", 1)],
        "mul": [("c", "p+q")],
        "div": [("c", "p"), ("rest", "q"), ("valid", 1), ("div0", 1), ("overflow", 1)],
    }[kind]
    semantics = {
        "cmp": "lt=(a<b), eq=(a==b), gt=(a>b), genau eine Relation gesetzt.",
        "add": "c=(a+b) modulo 2**max(p,q), overflow bei nicht darstellbarer signed Summe.",
        "sub": "c=(a-b) modulo 2**max(p,q), overflow bei nicht darstellbarer signed Differenz.",
        "mul": "Vollständiges signed Produkt c[p+q], kein Overflow.",
        "div": "Division gegen null; Rest mit Dividendenvorzeichen. c[p], rest[q]. "
               "b=0: c=rest=valid=overflow=0, div0=1. MIN_p/-1: c=MIN_p, rest=valid=div0=0, overflow=1. "
               "Sonst valid=1, div0=overflow=0.",
    }[kind]
    conditions = ["p >= 1", "q >= 1", "p + q + 3 <= 128" if kind == "div" else "p + q <= 128"]
    if kind in ("mul", "div"):
        conditions.extend(["p <= 16", "q <= 16"])
    return {
        "schema": 1, "kind": "template", "name": f"S{kind.upper()}<p,q>",
        "description": "Zweierkomplement mit expliziter Vorzeichen-Bitlogik, LSB-first; " + semantics +
            " Ports übertragen unsigned Bitmuster. Grenzen siehe Parameterbedingungen; maximal 512 NANDs.",
        "parameters": ["p", "q"], "conditions": conditions,
        "interface": ports([("a", "p"), ("b", "q")], outputs),
        "source": (TEMPLATES / f"signed-{kind}.prim").read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


@lru_cache(maxsize=None)
def bundle(kind, p, q):
    program = Template(definition(kind)).instantiate({"p": p, "q": q})
    return BlockBundle.from_circuit(f"S{kind.upper()}<{p},{q}>", synthesize(program), program.ports)


def reference(kind, a, b, p, q):
    """Independent signed integer oracle, without bit-level arithmetic."""
    a = a if a < 1 << (p - 1) else a - (1 << p)
    b = b if b < 1 << (q - 1) else b - (1 << q)
    w = max(p, q)
    if kind == "cmp":
        return [int(a < b), int(a == b), int(a > b)]
    if kind in ("add", "sub"):
        result = a + b if kind == "add" else a - b
        return [result % (1 << w), int(not -(1 << (w - 1)) <= result < 1 << (w - 1))]
    if kind == "mul":
        return [a * b % (1 << (p + q))]
    if b == 0:
        return [0, 0, 0, 1, 0]
    quotient = (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)
    overflow = int(quotient >= 1 << (p - 1))
    return [quotient % (1 << p), (a - quotient * b) % (1 << q), 1 ^ overflow, 0, overflow]


def encoded(program, values):
    return [digit for port, value in zip(program.ports["outputs"], values) for digit in bits(value, port["bits"])]


def export():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reports = []
    for kind in KINDS:
        template = Template(definition(kind))
        write_json(TEMPLATES / f"signed-{kind}.abstract.json", template.to_dict())
        for p, q in product(WIDTHS, repeat=2):
            name = f"S{kind.upper()}<{p},{q}>"
            program = template.instantiate({"p": p, "q": q})
            hierarchy = bundle(kind, p, q)
            expanded = hierarchy.expand()
            circuit, compiled = expanded.simplify(), synthesize(program)
            rows = []
            for a, b in product(range(1 << p), range(1 << q)):
                expected = reference(kind, a, b, p, q)
                inputs, outputs = bits(a, p) + bits(b, q), encoded(program, expected)
                if program.run(a | b << p) != expected or any(
                        impl.evaluate(inputs) != outputs for impl in (hierarchy, expanded, circuit, compiled)):
                    raise ValueError(f"{name} failed for a={a}, b={b}")
                rows.append(inputs + outputs)
            dataset = Dataset(name, p + q, len(circuit.outputs), rows,
                {"program": program.spec, "interface": program.ports, "description": template.document["description"]})
            checked = fitness(circuit, dataset)
            if not checked["verified_truth_table"]:
                raise ValueError("Export requires a fully verified truth table")
            prefix = OUTPUT / f"s{kind}-{p}-{q}"
            for suffix, document in (("block", hierarchy.to_dict()), ("circuit", circuit.to_dict()),
                                     ("template", program.spec), ("vectors", dataset.to_dict())):
                write_json(prefix.with_suffix(f".{suffix}.json"), document)
            prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program, name), encoding="utf-8", newline="\n")
            reports.append({"name": name, "kind": kind, "parameters": {"p": p, "q": q},
                "interface": program.ports, "fitness": checked, "hierarchy": hierarchy.summary(),
                "synthesis": {"method": "structural-bitwise-signed", "version": 1}})
            print(f"{name}: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(rows)} inputs verified", flush=True)
    write_json(OUTPUT / "verification.json", reports)


if __name__ == "__main__":
    export()

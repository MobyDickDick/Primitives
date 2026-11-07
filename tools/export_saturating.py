"""Export and independently verify GEN-08: python -m tools.export_saturating."""
from functools import lru_cache
from itertools import product

from primitives.blocks import BlockBundle
from primitives.dataset import Dataset, bits
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import inp, instance, out, ports
from tools.export_generative import netlist
from tools.export_parallel_add import ROOT, TEMPLATES, WIDTHS, write_json


KINDS = ("add", "sub")
FLAGS = {"add": "overflow", "sub": "underflow"}
OUTPUT = ROOT / "examples/circuits/saturating"


def definition(kind):
    flag = FLAGS[kind]
    semantics = ("c=min(a+b,2**max(p,q)-1), overflow=1 genau bei a+b>=2**max(p,q)."
                 if kind == "add" else "c=max(a-b,0), underflow=1 genau bei a<b.")
    return {
        "schema": 1, "kind": "template", "name": f"SAT_{kind.upper()}<p,q>",
        "description": "Unsigned Sättigungsarithmetik: " + semantics +
            " a[p], b[q], c[max(p,q)], " + flag + "[1]; Nullerweiterung, LSB-first. "
            "1<=p,q<=127, p+q<=128; NAND-Netze/F-Boxen maximal 512 Gatter.",
        "parameters": ["p", "q"],
        "conditions": ["p >= 1", "q >= 1", "p <= 127", "q <= 127", "p + q <= 128"],
        "interface": ports([("a", "p"), ("b", "q")], [("c", "max(p,q)"), (flag, 1)]),
        "source": (TEMPLATES / f"sat-{kind}.prim").read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def component(kind, p, q, name, interface, call):
    document = definition(kind)
    document.update(name=name, interface=interface)
    document["source"] = document["source"].split("# Ergebnisports", 1)[0] + call + "\n"
    return Template(document).instantiate({"p": p, "q": q})


@lru_cache(maxsize=None)
def bundle(kind, p, q):
    program = Template(definition(kind)).instantiate({"p": p, "q": q})
    w, title, flag = max(p, q), kind.title(), FLAGS[kind]
    raw = component(kind, p, q, f"Sat{title}Raw<{p},{q}>", program.ports,
                    f"raw = bits(Sat{title}Raw<{p},{q}>(a,b), {w + 1})\n"
                    f"return pack(raw[:{w}]), raw[{w}]")
    arithmetic = BlockBundle.from_circuit(f"Sat{title}Raw<{p},{q}>", synthesize(raw), raw.ports)
    clamp = component(kind, p, q, f"Sat{title}Clamp<{w}>",
                      ports([("value", w), ("flag", 1)], [("c", w), (flag, 1)]),
                      f"result = bits(Sat{title}Clamp<{w}>(value,flag), {w + 1})\n"
                      f"return pack(result[:{w}]), result[{w}]")
    saturation = BlockBundle.from_circuit(f"Sat{title}Clamp<{w}>", synthesize(clamp), clamp.ports)
    return BlockBundle.create({"name": f"SAT_{kind.upper()}<{p},{q}>", "version": 1,
        "interface": program.ports,
        "nodes": [instance("arithmetic", arithmetic, a=[inp("a", i) for i in range(p)],
                           b=[inp("b", i) for i in range(q)]),
                  instance("saturate", saturation, value=[out("arithmetic", "c", i) for i in range(w)],
                           flag=[out("arithmetic", flag)])],
        "outputs": {"c": [out("saturate", "c", i) for i in range(w)],
                    flag: [out("saturate", flag)]}}, [arithmetic, saturation])


def reference(kind, a, b, width):
    """Integer oracle independent of carry/borrow and bit-level saturation."""
    if kind == "add":
        return [min(a + b, (1 << width) - 1), int(a + b >= 1 << width)]
    return [max(a - b, 0), int(a < b)]


def export():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reports = []
    for kind in KINDS:
        template = Template(definition(kind))
        write_json(TEMPLATES / f"sat-{kind}.abstract.json", template.to_dict())
        for p, q in product(WIDTHS, repeat=2):
            w, name = max(p, q), f"SAT_{kind.upper()}<{p},{q}>"
            program = template.instantiate({"p": p, "q": q})
            hierarchy = bundle(kind, p, q)
            expanded = hierarchy.expand()
            circuit, compiled = expanded.simplify(), synthesize(program)
            rows = []
            for a, b in product(range(1 << p), range(1 << q)):
                expected = reference(kind, a, b, w)
                inputs = bits(a, p) + bits(b, q)
                outputs = bits(expected[0], w) + [expected[1]]
                if program.run(a | b << p) != expected or any(
                        impl.evaluate(inputs) != outputs for impl in (hierarchy, expanded, circuit, compiled)):
                    raise ValueError(f"{name} failed for a={a}, b={b}")
                rows.append(inputs + outputs)
            dataset = Dataset(name, p + q, w + 1, rows,
                {"program": program.spec, "interface": program.ports, "description": template.document["description"]})
            checked = fitness(circuit, dataset)
            if not checked["verified_truth_table"]:
                raise ValueError("Export requires a fully verified truth table")
            prefix = OUTPUT / f"sat-{kind}-{p}-{q}"
            for suffix, document in (("block", hierarchy.to_dict()), ("circuit", circuit.to_dict()),
                                     ("template", program.spec), ("vectors", dataset.to_dict())):
                write_json(prefix.with_suffix(f".{suffix}.json"), document)
            prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program, name), encoding="utf-8", newline="\n")
            reports.append({"name": name, "kind": kind, "parameters": {"p": p, "q": q},
                "interface": program.ports, "fitness": checked, "hierarchy": hierarchy.summary(),
                "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1}})
            print(f"{name}: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(rows)} inputs verified", flush=True)
    write_json(OUTPUT / "verification.json", reports)


if __name__ == "__main__":
    export()

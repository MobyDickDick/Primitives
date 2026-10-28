"""Export bit codes, prefix logic and sorting with explicit, inspectable FBoxes."""
from functools import lru_cache
from pathlib import Path

from primitives.blocks import BlockBundle
from primitives.dataset import bits, generate
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import inp, instance, out, ports
from tools.export_generative import bundle as logic_bundle
from tools.export_gt import bundle as gt_bundle
from tools.export_recursive_add import write_json

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("gray", "ungray", "prefix_or", "sort2")
DESCRIPTIONS = {
    "gray": "Binär zu Gray-Code: c=a XOR (a>>1). Benachbarte Zahlen unterscheiden sich in genau einem Codebit.",
    "ungray": "Gray-Code zu Binär. Rekursive Dekodierung der oberen Hälfte liefert das Präfixbit für die untere Hälfte.",
    "prefix_or": "Inklusive Präfix-ODER ab Bit 0: c[i] ist 1, wenn eines der Bits a[0] bis a[i] gesetzt ist.",
    "sort2": "Sortiert zwei unsigned t-Bit-Werte: lo=min(a,b), hi=max(a,b). Ein gemeinsamer Vergleich steuert zwei Auswahlboxen.",
}


def source(kind):
    if kind == "sort2":
        templates = ROOT / "examples/templates"
        gt = (templates / "recursive-gt.prim").read_text(encoding="utf-8").rsplit("\nreturn ", 1)[0]
        mux = (templates / "recursive-mux.prim").read_text(encoding="utf-8").rsplit("\nreturn ", 1)[0]
        return gt + "\n" + mux + '''
def SORT2<t>(a, b):
    assert t >= 1 and (t & (t - 1)) == 0
    sel = GT<t>(a, b)
    return pack(bits(MUX<t>(a, b, sel), t) + bits(MUX<t>(b, a, sel), t))

result = bits(SORT2<t>(a, b), 2 * t)
return pack(result[:t]), pack(result[t:])
'''
    name = kind.upper()
    adjustment = {
        "gray": "    lo[k - 1] = lo[k - 1] ^ x[k]\n",
        "ungray": "    for i in range(k):\n        lo[i] = lo[i] ^ hi[0]\n",
        "prefix_or": "    for i in range(k):\n        hi[i] = hi[i] | lo[k - 1]\n",
    }[kind]
    return f'''def {name}<t>(a):
    assert t >= 1 and (t & (t - 1)) == 0
    if t == 1:
        return a
    x = bits(a, t)
    k = t // 2
    lo = bits({name}<k>(pack(x[:k])), k)
    hi = bits({name}<k>(pack(x[k:])), k)
{adjustment}    return pack(lo + hi)

return {name}<t>(a)
'''


def definition(kind):
    return {"schema": 1, "kind": "template", "name": f"{kind.upper()}<t>",
            "description": DESCRIPTIONS[kind] + " t ist eine positive Zweierpotenz.",
            "parameters": ["t"], "conditions": ["t >= 1", "t <= 64", "is_power_of_two(t)"],
            "interface": ports([("a", "t"), ("b", "t")] if kind == "sort2" else [("a", "t")],
                               [("lo", "t"), ("hi", "t")] if kind == "sort2" else [("c", "t")]),
            "source": source(kind), "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000}}


def combine(kind, width):
    """A named bus operation makes the recursive boundary visible as an FBox."""
    op = "^" if kind == "xor" else "|"
    spec = {"version": 2, "parameters": {"k": width},
            "source": f"x = bits(a, k)\ns = bits(sel, 1)\nfor i in range(k):\n    x[i] = x[i] {op} s[0]\nreturn pack(x)\n",
            "interface": ports([("a", width), ("sel", 1)], [("c", width)])}
    from primitives.program import Program
    program = Program(spec)
    return BlockBundle.from_circuit(f"{kind.upper()}_PREFIX<{width}>", synthesize(program), program.ports)


@lru_cache(maxsize=None)
def bundle(kind, width):
    program = Template(definition(kind)).instantiate({"t": width})
    name = f"{kind.upper()}<{width}>"
    if kind == "sort2":
        gt, mux = gt_bundle(width), logic_bundle("mux", width)
        a, b = [inp("a", i) for i in range(width)], [inp("b", i) for i in range(width)]
        nodes = [instance("compare", gt, a=a, b=b),
                 instance("minimum", mux, a=a, b=b, sel=[out("compare", "c")]),
                 instance("maximum", mux, a=b, b=a, sel=[out("compare", "c")])]
        outputs = {p: [out(n, "c", i) for i in range(width)] for p, n in (("lo", "minimum"), ("hi", "maximum"))}
        dependencies = [gt, mux]
    elif width == 1:
        return BlockBundle.from_circuit(name, synthesize(program), program.ports)
    else:
        k = width // 2
        child = bundle(kind, k)
        nodes = [instance("lower", child, a=[inp("a", i) for i in range(k)]),
                 instance("upper", child, a=[inp("a", k + i) for i in range(k)])]
        lo, hi = [out("lower", "c", i) for i in range(k)], [out("upper", "c", i) for i in range(k)]
        merge = combine("or" if kind == "prefix_or" else "xor", 1 if kind == "gray" else k)
        if kind == "gray":
            nodes.append(instance("boundary", merge, a=[lo[-1]], sel=[inp("a", k)]))
            lo[-1] = out("boundary", "c")
        elif kind == "ungray":
            nodes.append(instance("prefix", merge, a=lo, sel=[hi[0]]))
            lo = [out("prefix", "c", i) for i in range(k)]
        else:
            nodes.append(instance("prefix", merge, a=hi, sel=[lo[-1]]))
            hi = [out("prefix", "c", i) for i in range(k)]
        outputs, dependencies = {"c": lo + hi}, [child, merge]
    return BlockBundle.create({"name": name, "version": 1, "interface": program.ports,
                               "nodes": nodes, "outputs": outputs}, dependencies)


def reference(kind, width, value):
    mask = (1 << width) - 1
    a, b = value & mask, (value >> width) & mask
    if kind == "sort2":
        return [min(a, b), max(a, b)]
    if kind == "gray":
        return [a ^ (a >> 1)]
    if kind == "ungray":
        result = 0
        while a:
            result ^= a
            a >>= 1
        return [result]
    return [sum(int(bool(a & ((1 << (i + 1)) - 1))) << i for i in range(width))]


def export():
    for kind in KINDS:
        doc = definition(kind)
        template = Template(doc)
        write_json(ROOT / f"examples/templates/recursive-{kind}.abstract.json", template.to_dict())
        (ROOT / f"examples/templates/recursive-{kind}.prim").write_text(doc["source"], encoding="utf-8")
        folder = ROOT / f"examples/circuits/recursive-{kind}"
        folder.mkdir(parents=True, exist_ok=True)
        reports = []
        for width in (1, 2, 4):
            program = template.instantiate({"t": width})
            hierarchy = bundle(kind, width)
            expanded = hierarchy.expand()
            circuit, compiled = expanded.simplify(), synthesize(program)
            n = expanded.inputs
            m = len(expanded.outputs)
            for value in range(1 << n):
                expected = reference(kind, width, value)
                encoded = [bit for v, port in zip(expected, program.ports["outputs"]) for bit in bits(v, port["bits"])]
                assert program.run(value) == expected, (kind, width, value)
                for implementation in (hierarchy, expanded, circuit, compiled):
                    assert implementation.evaluate(bits(value, n)) == encoded, (kind, width, value)
            dataset = generate(f"{kind.upper()}<{width}>", n, m, ports=program.ports, program=program.spec, samples=1 << n)
            dataset.metadata["description"] = doc["description"]
            prefix = folder / f"{kind}-{width}"
            for suffix, document in (("block", hierarchy.to_dict()), ("circuit", circuit.to_dict()),
                                     ("template", program.spec), ("vectors", dataset.to_dict())):
                write_json(prefix.with_suffix(f".{suffix}.json"), document)
            checked = fitness(circuit, dataset)
            assert checked["verified_truth_table"]
            reports.append({"name": dataset.name, "parameters": {"t": width}, "fitness": checked,
                            "hierarchy": hierarchy.summary()})
            print(f"{dataset.name}: {len(circuit.gates)} NANDs, {len(dataset.rows)} inputs verified")
        write_json(folder / "verification.json", reports)


if __name__ == "__main__":
    export()

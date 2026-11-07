"""Export and independently verify GEN-07: python -m tools.export_parallel_add."""
from functools import lru_cache
from itertools import product
import json
from pathlib import Path

from primitives.blocks import BlockBundle
from primitives.dataset import Dataset, bits
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import inp, instance, out, ports
from tools.export_generative import netlist
from tools.export_standard_arithmetic import definition as standard_definition


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "examples/templates"
OUTPUT = ROOT / "examples/circuits/parallel-prefix-add"
WIDTHS = (1, 2, 4)


def write_json(path, document):
    # Keep generated artifacts identical on Windows and Unix.
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2),
                    encoding="utf-8", newline="\n")


def definition():
    return {
        "schema": 1, "kind": "template", "name": "CLA<p,q>",
        "description": "Unsigned Parallelpräfix-Addition mit Generate/Propagate und festen "
            "Abständen 1,2,4,... (Kogge-Stone). a[p], b[q], c[max(p,q)], carry[1]; "
            "c + carry*2**max(p,q) = a+b, eingehender Carry 0, LSB-first. "
            "1<=p,q<=64 wegen interner 2*w-Bit-Busse; NAND-Netze/F-Boxen maximal 512 Gatter. "
            "Vergleich mit dem Ripple-Carry-Standard ohne Minimalitätsbehauptung.",
        "parameters": ["p", "q"],
        "conditions": ["p >= 1", "q >= 1", "p <= 64", "q <= 64"],
        "interface": ports([("a", "p"), ("b", "q")], [("c", "max(p,q)"), ("carry", 1)]),
        "source": (TEMPLATES / "parallel-prefix-add.prim").read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def component(p, q, name, interface, call):
    document = definition()
    document.update(name=name, interface=interface)
    document["source"] = document["source"].split("# Ergebnisports", 1)[0] + call + "\n"
    return Template(document).instantiate({"p": p, "q": q})


def stage_program(width, distance):
    return component(width, width, f"AddPrefixStage<{width},{distance}>",
                     ports([("prop_in", width), ("gen_in", width)], [("prop", width), ("gen", width)]),
                     f"gp = bits(AddPrefixStage<{width},{distance}>(prop_in, gen_in), {2 * width})\n"
                     f"return pack(gp[:{width}]), pack(gp[{width}:])")


@lru_cache(maxsize=None)
def bundle(p, q):
    program = Template(definition()).instantiate({"p": p, "q": q})
    w = max(p, q)
    gp = component(p, q, f"AddGP<{p},{q}>",
                   ports([("a", p), ("b", q)], [("prop", w), ("gen", w)]),
                   f"gp = bits(AddGP<{p},{q}>(a, b), {2 * w})\n"
                   f"return pack(gp[:{w}]), pack(gp[{w}:])")
    initial = BlockBundle.from_circuit(f"AddGP<{p},{q}>", synthesize(gp), gp.ports)
    dependencies = [initial]
    nodes = [instance("generate", initial, a=[inp("a", i) for i in range(p)],
                      b=[inp("b", i) for i in range(q)])]
    previous, distance = "generate", 1
    while distance < w:
        stage = stage_program(w, distance)
        block = BlockBundle.from_circuit(f"AddPrefixStage<{w},{distance}>", synthesize(stage), stage.ports)
        dependencies.append(block)
        name = f"prefix_{distance}"
        nodes.append(instance(name, block, prop_in=[out(previous, "prop", i) for i in range(w)],
                              gen_in=[out(previous, "gen", i) for i in range(w)]))
        previous, distance = name, distance * 2
    finish = component(p, q, f"AddPrefixSum<{w}>",
                       ports([("prop", w), ("gen", w)], [("c", w), ("carry", 1)]),
                       f"result = bits(AddPrefixSum<{w}>(prop, gen), {w + 1})\n"
                       f"return pack(result[:{w}]), result[{w}]")
    final = BlockBundle.from_circuit(f"AddPrefixSum<{w}>", synthesize(finish), finish.ports)
    dependencies.append(final)
    nodes.append(instance("sum", final, prop=[out("generate", "prop", i) for i in range(w)],
                          gen=[out(previous, "gen", i) for i in range(w)]))
    return BlockBundle.create({"name": f"CLA<{p},{q}>", "version": 1, "interface": program.ports,
                               "nodes": nodes, "outputs": {"c": [out("sum", "c", i) for i in range(w)],
                                                           "carry": [out("sum", "carry")]}}, dependencies)


def comparison(p, q, circuit=None):
    """Same full sum, input widths, structural synthesizer and NAND cost model."""
    parameters = {"p": p, "q": q}
    parallel = circuit if circuit is not None else bundle(p, q).expand().simplify()
    ripple = synthesize(Template(standard_definition("add")).instantiate(parameters))
    return {"parallel": {"gates": len(parallel.gates), "depth": parallel.depth},
            "ripple": {"gates": len(ripple.gates), "depth": ripple.depth},
            "delta": {"gates": len(parallel.gates) - len(ripple.gates),
                      "depth": parallel.depth - ripple.depth}}


def export():
    template = Template(definition())
    write_json(TEMPLATES / "parallel-prefix-add.abstract.json", template.to_dict())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reports = []
    for p, q in product(WIDTHS, repeat=2):
        name, w = f"CLA<{p},{q}>", max(p, q)
        program = template.instantiate({"p": p, "q": q})
        hierarchy = bundle(p, q)
        expanded = hierarchy.expand()
        circuit, compiled = expanded.simplify(), synthesize(program)
        rows = []
        for a, b in product(range(1 << p), range(1 << q)):
            total = a + b  # Independent integer addition, not generate/propagate.
            expected = [total % (1 << w), total // (1 << w)]
            inputs, outputs = bits(a, p) + bits(b, q), bits(total, w + 1)
            if program.run(a | b << p) != expected or any(
                    impl.evaluate(inputs) != outputs for impl in (hierarchy, expanded, circuit, compiled)):
                raise ValueError(f"{name} failed for a={a}, b={b}")
            rows.append(inputs + outputs)
        dataset = Dataset(name, p + q, w + 1, rows,
                          {"program": program.spec, "interface": program.ports,
                           "description": template.document["description"]})
        checked = fitness(circuit, dataset)
        if not checked["verified_truth_table"]:
            raise ValueError("Export requires a fully verified truth table")
        prefix = OUTPUT / f"cla-{p}-{q}"
        for suffix, document in (("block", hierarchy.to_dict()), ("circuit", circuit.to_dict()),
                                 ("template", program.spec), ("vectors", dataset.to_dict())):
            write_json(prefix.with_suffix(f".{suffix}.json"), document)
        prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program, name), encoding="utf-8", newline="\n")
        reports.append({"name": name, "parameters": {"p": p, "q": q}, "interface": program.ports,
                        "fitness": checked, "hierarchy": hierarchy.summary(),
                        "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1},
                        "comparison": comparison(p, q, circuit),
                        "files": {key: f"cla-{p}-{q}.{suffix}" for key, suffix in (
                            ("block", "block.json"), ("circuit", "circuit.json"), ("template", "template.json"),
                            ("vectors", "vectors.json"), ("netlist", "nand.txt"))}})
        print(f"{name}: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(rows)} inputs verified", flush=True)
    write_json(OUTPUT / "verification.json", reports)


if __name__ == "__main__":
    export()

"""Export and independently verify GEN-04. Run: python -m tools.export_barrel_shifter."""
from functools import lru_cache
from pathlib import Path

from primitives.blocks import BlockBundle
from primitives.dataset import Dataset, bits
from primitives.library import fitness, write_json
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import inp, instance, out, ports
from tools.export_generative import netlist


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "examples/templates"
OUTPUT = ROOT / "examples/circuits"
KINDS = ("shl", "shr", "sar")
WIDTHS = (1, 2, 4)


def label(kind, t, s_bits):
    if kind not in KINDS:
        raise ValueError(f"Unknown barrel shifter: {kind}")
    return f"{kind.upper()}<{t},{s_bits}>"


def definition(kind):
    return {
        "schema": 1, "kind": "template", "name": label(kind, "t", "s_bits"),
        "description": label(kind, "t", "s_bits") + ": variable Verschiebung von a[t] um unsigned s[s_bits] "
            "über feste Bit-MUX-Stufen; c[t], LSB-first. " + (
                "SAR interpretiert a als Zweierkomplement und wiederholt das Vorzeichenbit; "
                "bei s>=t besteht das Ergebnis nur aus Vorzeichenbits. " if kind == "sar" else
                "Logische Verschiebung mit Nullen; bei s>=t ist das Ergebnis null. "
            ) + "t>=1, s_bits>=1, t+s_bits<=128. NAND-Netze/F-Boxen: maximal 512 Gatter; Ausführungsbudgets gelten.",
        "parameters": ["t", "s_bits"],
        "conditions": ["t >= 1", "s_bits >= 1", "t + s_bits <= 128"],
        "interface": ports([("a", "t"), ("s", "s_bits")], [("c", "t")]),
        "source": (TEMPLATES / f"barrel-{kind}.prim").read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def stage_program(kind, t, k):
    document = definition(kind)
    document["name"] = f"{kind.upper()}Stage<{t},{k}>"
    document["interface"] = ports([("a", t), ("sel", 1)], [("c", t)])
    document["source"] = document["source"].split("# Ergebnisport", 1)[0] + f"return {kind.upper()}Stage<{t},{k}>(a, sel)\n"
    return Template(document).instantiate({"t": t, "s_bits": 1})


@lru_cache(maxsize=None)
def bundle(kind, t, s_bits):
    program = Template(definition(kind)).instantiate({"t": t, "s_bits": s_bits})
    stages, nodes = [], []
    previous = [inp("a", i) for i in range(t)]
    for j in range(s_bits):
        k = min(1 << j, t)
        stage = stage_program(kind, t, k)
        block = BlockBundle.from_circuit(f"{kind.upper()}Stage<{t},{k}>", synthesize(stage), stage.ports)
        stages.append(block)
        name = f"shift_{j}"
        nodes.append(instance(name, block, a=previous, sel=[inp("s", j)]))
        previous = [out(name, "c", i) for i in range(t)]
    return BlockBundle.create({"name": label(kind, t, s_bits), "version": 1,
                               "interface": program.ports, "nodes": nodes, "outputs": {"c": previous}}, stages)


def reference(kind, t, a, s):
    """Independent integer arithmetic, never used to construct the circuit."""
    if kind == "sar":
        signed = a - (1 << t) if a & (1 << (t - 1)) else a
        return (signed >> min(s, t)) & ((1 << t) - 1)
    if s >= t:
        return 0
    return ((a << s) if kind == "shl" else (a >> s)) & ((1 << t) - 1)


def export():
    for kind in KINDS:
        template = Template(definition(kind))
        write_json(TEMPLATES / f"barrel-{kind}.abstract.json", template.to_dict())
        folder = OUTPUT / f"barrel-{kind}"
        folder.mkdir(parents=True, exist_ok=True)
        reports = []
        for t in WIDTHS:
            for s_bits in WIDTHS:
                program = template.instantiate({"t": t, "s_bits": s_bits})
                hierarchy = bundle(kind, t, s_bits)
                expanded = hierarchy.expand()
                circuit, compiled = expanded.simplify(), synthesize(program)
                rows = []
                for value in range(1 << (t + s_bits)):
                    a, s = value % (1 << t), value >> t
                    expected = reference(kind, t, a, s)
                    inputs, outputs = bits(value, t + s_bits), bits(expected, t)
                    if program.run(value) != [expected] or any(
                            impl.evaluate(inputs) != outputs for impl in (hierarchy, expanded, circuit, compiled)):
                        raise ValueError(f"{label(kind, t, s_bits)} failed for a={a}, s={s}")
                    rows.append(inputs + outputs)
                dataset = Dataset(label(kind, t, s_bits), t + s_bits, t, rows,
                                  {"program": program.spec, "interface": program.ports,
                                   "description": template.document["description"]})
                checked = fitness(circuit, dataset)
                if not checked["verified_truth_table"]:
                    raise ValueError("Export requires a fully verified truth table")
                prefix = folder / f"{kind}-{t}-{s_bits}"
                write_json(prefix.with_suffix(".block.json"), hierarchy.to_dict())
                write_json(prefix.with_suffix(".circuit.json"), circuit.to_dict())
                write_json(prefix.with_suffix(".template.json"), program.spec)
                write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
                prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program, label(kind, t, s_bits)), encoding="utf-8")
                reports.append({"name": label(kind, t, s_bits), "parameters": {"t": t, "s_bits": s_bits},
                                "interface": program.ports, "fitness": checked, "hierarchy": hierarchy.summary(),
                                "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1},
                                "files": {key: f"{kind}-{t}-{s_bits}.{suffix}" for key, suffix in (
                                    ("block", "block.json"), ("circuit", "circuit.json"), ("template", "template.json"),
                                    ("vectors", "vectors.json"), ("netlist", "nand.txt"))}})
                print(f"{label(kind, t, s_bits)}: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(rows)} inputs verified", flush=True)
        write_json(folder / "verification.json", reports)


if __name__ == "__main__":
    export()

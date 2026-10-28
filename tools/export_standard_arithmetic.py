"""Export conventional arithmetic for independently sized unsigned operands.

Run: python -m tools.export_standard_arithmetic
"""
from itertools import product
from pathlib import Path

from primitives.blocks import BlockBundle
from primitives.dataset import bits, generate
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_templates import ADD, MUL, SUB
from tools.export_recursive_add import write_json


ROOT = Path(__file__).resolve().parents[1]
WIDTHS = (1, 2, 4)
KINDS = ("add", "sub", "mul", "div")
NAMES = {"add": "Standardaddition", "sub": "Standardsubtraktion",
         "mul": "Standardmultiplikation", "div": "Standarddivision"}
DESCRIPTIONS = {
    "add": "Ripple-Carry-Addition: vollständige Summe mit max(p,q)+1 Bits.",
    "sub": "Ripple-Borrow-Subtraktion: c=(a-b) modulo 2**max(p,q), borrow=1 genau bei a<b.",
    "mul": "Schiebe-Addier-Multiplikation aus AND-Teilprodukten: vollständiges Produkt mit p+q Bits.",
    "div": "Restoring-Division mit p festen Stufen: c=a//b, rest=a%b. Bei b=0: c=rest=valid=0, div0=1; sonst valid=1, div0=0.",
}

DIV = '''# Schriftliche Binärdivision: a ist der Dividend, b der Divisor.
# p ist die Bitbreite von a, q die Bitbreite von b; beide sind vorzeichenlos.
# Bitarrays sind LSB-first: Index 0 ist die Einerstelle (Wert 1).
x = bits(a, p)
y = bits(b, q)
quotient = [0] * p
# Nach jedem erfolgreichen Schritt ist der Rest kleiner als b.
# Das Zusatzbit bietet Platz für 2*Rest plus das nächste Dividend-Bit.
remainder = [0] * (q + 1)
# Die Division beginnt beim höchsten Bit von a: p-1, p-2, ..., 0.
# range schliesst die Grenze -1 aus; es gibt genau p feste Stufen.
for i in range(p - 1, -1, -1):
    # Nächstes Bit herunterholen: neuer Rest = 2*alter Rest + x[i].
    # [x[i]] + remainder[:q] fügt das neue Bit vorne ein;
    # bei LSB-first rücken die bisherigen Bits dadurch eine Stelle nach oben.
    remainder = [x[i]] + remainder[:q]
    # Probe: Passt b in diesen Rest? Dazu versuchsweise Rest-b berechnen.
    # subtract<q+1> liefert q+1 Differenzbits und ein Leihbit (Borrow).
    # Insgesamt q+2 Bits; das Leihbit steht an Index q+1.
    difference = bits(subtract<q+1>(pack(remainder), b), q + 2)
    # Leihbit 0: Rest>=b, Differenz übernehmen und Quotientenbit auf 1 setzen.
    # Leihbit 1: Rest<b, bisherigen Rest behalten und Quotientenbit auf 0 setzen.
    # 1 ^ bit kehrt ein einzelnes Bit um; ^ ist XOR, keine Potenz.
    take = 1 ^ difference[q + 1]
    for j in range(q + 1):
        # Bitweise Auswahl ohne eingabeabhängiges if:
        # take=1 wählt difference[j], take=0 wählt remainder[j].
        # Den bisherigen Rest zu behalten heisst hier Wiederherstellung
        # (englisch restoring). & ist AND, | ist OR.
        remainder[j] = (difference[j] & take) | (remainder[j] & (1 ^ take))
    quotient[i] = take
# Prüfen, ob der Divisor ungleich 0 ist: ODER über alle seine Bits.
valid = 0
for i in range(q):
    valid = valid | y[i]
# b=0 ist ungültig: AND mit valid=0 setzt sämtliche Ergebnisbits auf 0.
# Für b!=0 bleiben Quotient und Rest unverändert.
for i in range(p):
    quotient[i] = quotient[i] & valid
for i in range(q):
    remainder[i] = remainder[i] & valid
# pack wandelt LSB-first-Bitarrays zurück in ganze Zahlen.
# Reihenfolge der Ergebnisports: c, rest, valid, div0.
# Das Zusatzbit des temporären Rests wird nicht mehr benötigt.
return pack(quotient), pack(remainder[:q]), valid, 1 ^ valid
'''


def definition(kind):
    # bits(a,w) and bits(b,w) zero-extend narrower inputs; this is wiring.
    width = "# Gemeinsame Rechenbreite: die grössere der beiden Eingangsbreiten.\n# bits(a,w) und bits(b,w) ergänzen schmalere Eingänge oben mit Nullen.\nw = p if p >= q else q\n"
    sources = {
        "add": ADD + "\n" + width + "# Die vollständige Summe hat w+1 Bits, einschliesslich Übertrag.\nreturn add<w>(a, b)\n",
        "sub": SUB + "\n" + width + "difference = bits(subtract<w>(a, b), w + 1)\n# Untere w Bits: modulare Differenz; letztes Bit: Leihbit (a<b).\nreturn pack(difference[:w]), difference[w]\n",
        "mul": MUL + "\n" + width + "# Das Produkt braucht bei diesen Eingängen nur p+q der 2*w Rechenbits.\nreturn pack(bits(multiply<w>(a, b), p + q))\n",
        "div": SUB + "\n" + DIV,
    }
    outputs = {
        "add": [("c", "max(p,q)+1")],
        "sub": [("c", "max(p,q)"), ("borrow", 1)],
        "mul": [("c", "p+q")],
        "div": [("c", "p"), ("rest", "q"), ("valid", 1), ("div0", 1)],
    }
    conditions = ["p >= 1", "q >= 1", "p <= 16", "q <= 16"]
    return {
        "schema": 1, "kind": "template", "name": f"{NAMES[kind]}<p,q>",
        "description": DESCRIPTIONS[kind] + " Vorzeichenlose Eingänge: a[p], b[q]; unabhängig wählbare Bitbreiten.",
        "parameters": ["p", "q"], "conditions": conditions,
        "interface": {"inputs": [{"name": "a", "bits": "p"}, {"name": "b", "bits": "q"}],
                      "outputs": [{"name": name, "bits": n} for name, n in outputs[kind]]},
        "source": sources[kind],
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def reference(kind, a, b, p, q):
    """Integer oracle independent of bit-level construction."""
    if kind == "add":
        return [a + b]
    if kind == "sub":
        return [(a - b) % (1 << max(p, q)), int(a < b)]
    if kind == "mul":
        return [a * b]
    return [a // b, a % b, 1, 0] if b else [0, 0, 0, 1]


def netlist(circuit, ports, name):
    names = [f"{port['name']}{i}" for port in ports["inputs"] for i in range(port["bits"])]
    lines = [f"# {name}: flat NAND netlist; bit 0 is the LSB.", "# Inputs: " + ", ".join(names)]
    for i, (a, b) in enumerate(circuit.gates):
        lines.append(f"g{i} = NAND({names[a]}, {names[b]})")
        names.append(f"g{i}")
    for port in ports["outputs"]:
        for i in range(port["bits"]):
            lines.append(f"{port['name']}{i} = {names[circuit.outputs[port['offset'] + i]]}")
    return "\n".join(lines) + "\n"


def export():
    for kind in KINDS:
        template = Template(definition(kind))
        stem = ROOT / f"examples/templates/standard-{kind}"
        write_json(stem.with_suffix(".abstract.json"), template.to_dict())
        stem.with_suffix(".prim").write_text(template.document["source"], encoding="utf-8")
        folder = ROOT / f"examples/circuits/standard-{kind}"
        folder.mkdir(parents=True, exist_ok=True)
        reports = []
        for p, q in product(WIDTHS, repeat=2):
            program = template.instantiate({"p": p, "q": q})
            circuit = synthesize(program)
            name = f"{NAMES[kind]} ({p}/{q} Bit)"
            block = BlockBundle.from_circuit(name, circuit, program.ports)
            for a, b in product(range(1 << p), range(1 << q)):
                value = a | b << p
                expected = reference(kind, a, b, p, q)
                encoded = [digit for port, number in zip(program.ports["outputs"], expected)
                           for digit in bits(number, port["bits"])]
                if program.run(value) != expected or any(
                        impl.evaluate(bits(value, p + q)) != encoded for impl in (circuit, block)):
                    raise ValueError(f"{name} failed for {a}, {b}")
            dataset = generate(name, p + q, len(circuit.outputs), ports=program.ports,
                               program=program.spec, samples=1 << (p + q))
            dataset.metadata["description"] = template.document["description"]
            checked = fitness(circuit, dataset)
            if not checked["verified_truth_table"]:
                raise ValueError(f"{name} was not exhaustively verified")
            prefix = folder / f"{kind}-{p}-{q}"
            for suffix, document in (("circuit", circuit.to_dict()), ("block", block.to_dict()),
                                     ("template", program.spec), ("vectors", dataset.to_dict())):
                write_json(prefix.with_suffix(f".{suffix}.json"), document)
            prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program.ports, name), encoding="utf-8")
            reports.append({"name": name, "parameters": program.parameters, "interface": program.ports,
                            "fitness": checked, "synthesis": {"method": "structural-bitwise", "version": 1}})
            print(f"{name}: {len(circuit.gates)} NANDs, {len(dataset.rows)} inputs verified")
        write_json(folder / "verification.json", reports)


if __name__ == "__main__":
    export()

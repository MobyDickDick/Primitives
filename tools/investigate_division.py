"""Reproducible exhaustive division tables, NAND synthesis and evolution.

Run: python -m tools.investigate_division
No changes to the user's library. Random search has no seeds or repair;
kernel optimization explicitly starts from a structurally compiled solution.
"""
import csv
from dataclasses import asdict
from pathlib import Path

from primitives.circuit import Circuit
from primitives.dataset import Dataset, bits, integer
from primitives.evolution import Problem, SearchConfig, search_python
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_recursive_add import write_json


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/templates/recursive-stream-div.prim"
OUTPUT = ROOT / "examples/experiments/division"
SEEDS = (11, 29, 47)


def definition(kernel=False):
    source = SOURCE.read_text(encoding="utf-8")
    if kernel:
        source = source.split("# Public quotient interface.")[0] + """
result = bits(DIV_STEP<n>(r, b, digit), n + 1)
return pack(result[:n]), result[n]
"""
    return {
        "schema": 1, "kind": "template",
        "name": "Divisionsschritt" if kernel else "Rekursive Division mit gemeinsamem Rest",
        "description": ("Ein getaktet wiederverwendbarer Schritt; auf erreichbaren Zuständen gilt b>0 und r<b. "
                        "Ausserhalb dieser Invariante wird der Rest modulo 2**n ausgegeben."
                        if kernel else "Unsigned DIV<m,n>: c=a//b, err=0; bei b=0 c=0, err=1."),
        "parameters": ["n"] if kernel else ["m", "n"],
        "conditions": (["n >= 1", "n <= 16"] if kernel else
                       ["m >= 1", "m <= 8", "n >= 1", "n <= 8"]),
        "interface": {
            "inputs": ([{"name": "r", "bits": "n"}, {"name": "b", "bits": "n"},
                        {"name": "digit", "bits": 1}] if kernel else
                       [{"name": "a", "bits": "m"}, {"name": "b", "bits": "n"}]),
            "outputs": ([{"name": "rnext", "bits": "n"}, {"name": "take", "bits": 1}]
                        if kernel else [{"name": "c", "bits": "m"}, {"name": "err", "bits": 1}]),
        },
        "source": source,
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def aligned_divmod(a, b):
    """Largest fitting power-of-two multiple; no // or % in the algorithm."""
    if type(a) is not int or type(b) is not int or a < 0 or b <= 0:
        raise ValueError("a muss nichtnegativ und b positiv sein.")
    if a < b:
        return 0, a
    shift = a.bit_length() - b.bit_length()
    scaled = b << shift
    if scaled > a:
        shift -= 1
        scaled >>= 1
    quotient, remainder = aligned_divmod(a - scaled, b)
    return (1 << shift) | quotient, remainder


def division_dataset(m, n, program):
    rows = []
    for a in range(1 << m):
        for b in range(1 << n):
            q, err = (a // b, 0) if b else (0, 1)
            rows.append(bits(a, m) + bits(b, n) + bits(q, m) + [err])
    return Dataset(f"DIV<{m},{n}>", m + n, m + 1, rows,
                   {"interface": program.ports, "program": program.spec})


def step_dataset(n, program):
    rows = []
    for r in range(1 << n):
        for b in range(1 << n):
            for digit in (0, 1):
                t = 2 * r + digit
                take = int(t >= b)
                # Define all states, including unreachable r>=b and b=0.
                rnext = (t - b if take else t) % (1 << n)
                rows.append(bits(r, n) + bits(b, n) + [digit] + bits(rnext, n) + [take])
    return Dataset(f"DIV_STEP<{n}>", 2 * n + 1, n + 1, rows,
                   {"interface": program.ports, "program": program.spec})


def clocked_divide(a, b, m, n, step):
    """Simulate synchronous register updates around ONE physical NAND kernel.

    Registers, clock, controller, quotient shift and zero detection are modelled
    in Python, not included in the kernel's NAND count or the DAG circuit type.
    """
    if not (1 <= m <= 16 and 1 <= n <= 16 and 0 <= a < 1 << m and 0 <= b < 1 << n):
        raise ValueError("Ungültige Breiten oder Operanden.")
    if step.inputs != 2 * n + 1 or len(step.outputs) != n + 1:
        raise ValueError("Schrittnetz und Divisorbreite passen nicht zusammen.")
    if b == 0:
        return {"c": 0, "err": 1, "remainder": 0, "cycles": 0, "trace": []}
    q, r, trace = 0, 0, []
    for i in range(m - 1, -1, -1):
        digit = (a >> i) & 1
        out = step.evaluate(bits(r, n) + bits(b, n) + [digit])
        rnext, take = integer(out[:n]), out[n]
        trace.append({"cycle": m - i, "input_bit": digit, "r": r,
                      "rnext": rnext, "take": take, "qnext": 2 * q + take})
        q, r = 2 * q + take, rnext
    return {"c": q, "err": 0, "remainder": r, "cycles": m, "trace": trace}


def netlist(circuit, ports):
    names = [f"{p['name']}{i}" for p in ports["inputs"] for i in range(p["bits"])]
    lines = ["# Flat NAND kernel/network. Bit index 0 is the LSB.",
             "# Inputs: " + ", ".join(names)]
    for i, (a, b) in enumerate(circuit.gates):
        lines.append(f"g{i} = NAND({names[a]}, {names[b]})")
        names.append(f"g{i}")
    labels = [f"{p['name']}{i}" for p in ports["outputs"] for i in range(p["bits"])]
    lines.extend(f"{label} = {names[ref]}" for label, ref in zip(labels, circuit.outputs))
    return "\n".join(lines) + "\n"


def write_table(path, m, n, values=None):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["a", "b", "a_binary_msb_first", "b_binary_msb_first",
                         "c", "c_binary_msb_first", "err", "remainder"])
        pairs = values if values is not None else ((a, b) for a in range(1 << m) for b in range(1 << n))
        for a, b in pairs:
            c, err, r = (a // b, 0, a % b) if b else (0, 1, "")
            writer.writerow([a, b, f"{a:0{m}b}", f"{b:0{n}b}", c, f"{c:0{m}b}", err, r])


def checked_search(dataset, config, incumbent=None):
    result = search_python(Problem(dataset, config, incumbent=incumbent))
    checked = fitness(Circuit.from_dict(result["circuit"]), dataset)
    if result["fitness"] != checked:
        raise AssertionError("Unabhängige Fitnessprüfung stimmt nicht überein.")
    return result


def export(output=OUTPUT, seeds=SEEDS, generations=200):
    output.mkdir(parents=True, exist_ok=True)
    template, kernel_template = Template(definition()), Template(definition(True))
    write_json(output / "division.abstract.json", template.to_dict())
    write_json(output / "step.abstract.json", kernel_template.to_dict())
    write_table(output / "values-1-to-4.csv", 3, 3,
                ((a, b) for a in range(1, 5) for b in range(1, 5)))
    numeric_program = template.instantiate({"m": 3, "n": 3})
    numeric_full = division_dataset(3, 3, numeric_program)
    numeric = Dataset("DIV: Zahlenwerte 1 bis 4", 6, 4,
                      [bits(a, 3) + bits(b, 3) + bits(a // b, 3) + [0]
                       for a in range(1, 5) for b in range(1, 5)], numeric_full.metadata)
    write_json(output / "values-1-to-4.vectors.json", numeric.to_dict())
    numeric_runs, numeric_best = [], None
    for seed in seeds:
        config = SearchConfig(gates=32, population=24, generations=generations, seed=seed, backend="python")
        result = checked_search(numeric, config)
        candidate = Circuit.from_dict(result["circuit"])
        numeric_runs.append({"config": asdict(config), "fitness": result["fitness"],
                             "full_3_bit_check": fitness(candidate, numeric_full),
                             "evaluations": result["search"]["evaluations"]})
        if numeric_best is None or tuple(result["fitness"][k] for k in ("errors", "gates", "depth")) < tuple(numeric_best["fitness"][k] for k in ("errors", "gates", "depth")):
            numeric_best = result
    write_json(output / "values-1-to-4.evolution.json", numeric_best)
    print(f"Values 1..4: random best {numeric_best['fitness']['errors']} bit errors", flush=True)
    summaries, kernels = [], {}
    for n in range(1, 5):
        program = kernel_template.instantiate({"n": n})
        circuit = synthesize(program)
        dataset = step_dataset(n, program)
        if not fitness(circuit, dataset)["verified_truth_table"]:
            raise AssertionError(f"Schritt {n} ist falsch.")
        runs = []
        best, best_result = circuit, None
        for seed in seeds:
            config = SearchConfig(gates=len(circuit.gates) + 8, population=24,
                                  generations=generations, seed=seed, backend="python", optimize=True)
            result = checked_search(dataset, config, circuit)
            runs.append({"config": asdict(config), "fitness": result["fitness"],
                         "evaluations": result["search"]["evaluations"]})
            candidate = Circuit.from_dict(result["circuit"])
            if best_result is None or (len(candidate.gates), candidate.depth) < (len(best.gates), best.depth):
                best, best_result = candidate, result
        kernels[n] = best
        prefix = output / f"step-{n}"
        write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
        write_json(prefix.with_suffix(".circuit.json"), best.to_dict())
        write_json(prefix.with_suffix(".evolution.json"), best_result)
        prefix.with_suffix(".nand.txt").write_text(netlist(best, program.ports), encoding="utf-8")
        summaries.append({"n": n, "structural": fitness(circuit, dataset),
                          "optimized": fitness(best, dataset), "runs": runs})
        print(f"STEP<{n}>: {len(circuit.gates)} -> {len(best.gates)} NANDs", flush=True)

    reports = []
    for m in range(1, 5):
        for n in range(1, 5):
            program = template.instantiate({"m": m, "n": n})
            circuit = synthesize(program)
            dataset = division_dataset(m, n, program)
            checked = fitness(circuit, dataset)
            if not checked["verified_truth_table"]:
                raise AssertionError(f"DIV<{m},{n}> ist falsch.")
            for a in range(1 << m):
                for b in range(1 << n):
                    state = clocked_divide(a, b, m, n, kernels[n])
                    expected = [a // b, 0] if b else [0, 1]
                    x = a | b << m
                    if program.run(x) != expected or [state["c"], state["err"]] != expected:
                        raise AssertionError((m, n, a, b))
                    if b and (aligned_divmod(a, b) != divmod(a, b) or state["remainder"] != a % b):
                        raise AssertionError((m, n, a, b, "Rest"))
            prefix = output / f"div-{m}-{n}"
            write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
            write_json(prefix.with_suffix(".circuit.json"), circuit.to_dict())
            prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program.ports), encoding="utf-8")
            write_table(prefix.with_suffix(".csv"), m, n)
            runs, best_result = [], None
            for seed in seeds:
                config = SearchConfig(gates=min(128, max(8, len(circuit.gates) + 8)),
                                      population=24, generations=generations, seed=seed, backend="python")
                result = checked_search(dataset, config)
                runs.append({"config": asdict(config), "fitness": result["fitness"],
                             "evaluations": result["search"]["evaluations"]})
                f = result["fitness"]
                if best_result is None or ((f["errors"], f["gates"], f["depth"]) <
                                          tuple(best_result["fitness"][k] for k in ("errors", "gates", "depth"))):
                    best_result = result
            write_json(prefix.with_suffix(".evolution.json"), best_result)
            report = {"m": m, "n": n, "pairs": len(dataset.rows), "structural": checked,
                      "sequential_verified": True, "cycles_nonzero_divisor": m,
                      "random_search": runs, "random_best": best_result["fitness"]}
            reports.append(report)
            print(f"DIV<{m},{n}>: {len(circuit.gates)} NANDs; random best {report['random_best']['errors']} bit errors", flush=True)
    write_json(output / "verification.json", {"schema": 1, "seeds": list(seeds),
               "generations": generations, "numeric_values": numeric_runs,
               "kernels": summaries, "division": reports,
               "total_division_pairs": sum(r["pairs"] for r in reports),
               "scope": "Kernel NAND counts exclude registers, clock, controller and zero detection."})
    write_json(output / "trace-13-div-3.json", clocked_divide(13, 3, 4, 2, kernels[2]))
    write_report(output, reports, summaries, seeds, generations, numeric_runs)


def write_report(output, reports, kernels, seeds, generations, numeric_runs):
    lines = ["# Gemessene Divisionsexperimente", "",
             "Erzeugt mit `python -m tools.investigate_division`.", "",
             "`m,n` sind hier Bitbreiten; die separat angefragten Zahlenwerte 1 bis 4 stehen in `values-1-to-4.csv`.",
             "Semantik: c=floor(a/b), err=0; bei b=0: c=0, err=1. Ein Rest ungleich null ist kein Fehler.", "",
             f"Zufallssuche: Python, Seeds {list(seeds)}, Population 24, höchstens {generations} Generationen/Seed,",
             f"höchstens {1 + 24 * generations} Bewertungen/Seed, Fehler/Gatter/Tiefe als Rang.",
             "Keine Bibliothek, kein bekannter Dividierer als Start, keine Restfallkorrektur; Abbruch bei Fehlerfreiheit.",
             "Das Suchgatterbudget ist min(128,max(8,strukturelle Gatter+8)); die JSON-Berichte enthalten jede Konfiguration.",
             "Der beste von drei Läufen ist keine Erfolgswahrscheinlichkeit und ein Fehlschlag kein Unmöglichkeitsbeweis.", "",
             "## Genau die Zahlenwerte 1 bis 4", "",
             "Zusätzlich separat gesucht: nur die 16 angefragten Paare, 32 Suchgatter, drei Seeds, gleiche Population und Generationenzahl.",
             "Diese Teilmenge enthält keinen Nullteiler; ihr Fehlerbit ist immer 0. Sie identifiziert daher keine allgemeine Division.",
             "Die Gegenprüfung testet dieselbe gefundene Schaltung auf allen 64 Paaren zweier 3-Bit-Zahlen, einschliesslich Nullteilern.", "",
             "| Seed | Bitfehler / 64 Sollbits (16 Paare) | Gegenprüfung: Bitfehler / 256 Sollbits |",
             "|---|---|---|"]
    for r in numeric_runs:
        lines.append(f"| {r['config']['seed']} | {r['fitness']['errors']} | {r['full_3_bit_check']['errors']} |")
    lines += ["", "## Alle Bitbreiten 1 bis 4", "",
             "| m | n | Eingaben | NANDs konstruiert | Tiefe | Suchbudget Gatter | Beste Bitfehler / Sollbits | Such-NANDs | exakt / Läufe |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in reports:
        f, best = r["structural"], r["random_best"]
        successes = sum(run["fitness"]["exact_on_dataset"] for run in r["random_search"])
        lines.append(f"| {r['m']} | {r['n']} | {r['pairs']} | {f['gates']} | {f['depth']} | "
                     f"{r['random_search'][0]['config']['gates']} | {best['errors']} / {best['total_bits']} | {best['gates']} | {successes} / {len(seeds)} |")
    lines += ["", "Alle 900 Eingabepaare wurden für die strukturellen Netze und die getaktete Simulation vollständig geprüft.",
              "Die separaten CSV-Dateien enthalten lesbare Binärzahlen mit höchstem Bit links; JSON-Vektoren sind LSB-first.",
              "Bei Nullteiler bleibt das CSV-Restfeld leer. Der Rest dient nur zur Kontrolle und gehört nicht zum DIV-Ausgang.", "",
              "## Wiederverwendeter Schritt", "",
              "Diese Evolution startet ausdrücklich vom korrekten konstruierten Schrittnetz und optimiert es weiter.",
              "Die gesamte Wahrheitstabelle wird geprüft, auch Zustände ausserhalb r<b und b>0.",
              "Dort lautet die definierte Restfunktion (2*r+digit-b*take) modulo 2**n mit take=(2*r+digit>=b).", "",
              "| n | NANDs konstruiert | NANDs nach Evolution | geprüfte Schritt-Eingaben |",
              "|---|---|---|---|"]
    for r in kernels:
        lines.append(f"| {r['n']} | {r['structural']['gates']} | {r['optimized']['gates']} | {1 << (2*r['n']+1)} |")
    lines += ["", "Schritt-NAND-Zahlen enthalten keine Register, Taktsteuerung oder Nullteilererkennung.",
              "Die Rückführung wird in Python mit getrennten Registerzuständen simuliert; das Projektformat bleibt azyklisch.",
              "Die Division braucht bei b>0 genau m Rechenschritte, zusätzlich zum Laden und Auslesen in realer Hardware.",
              "Die JSON-Datei `trace-13-div-3.json` zeigt sämtliche Zustandsübergänge für 13/3.", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    export()

"""Validated N+M vectors and bounded expression based truth-table generation."""
import ast
from dataclasses import dataclass, field
import math
import operator
import random
from .ports import decode, encode, interface
from .formula import parse_formula


def bits(value, width):
    return [(value >> i) & 1 for i in range(width)]


def integer(vector):
    return sum(b << i for i, b in enumerate(vector))


def validate_description(value):
    if not isinstance(value, str) or len(value) > 4000:
        raise ValueError("Die Beschreibung muss Text mit höchstens 4000 Zeichen sein.")
    return value.strip()


@dataclass
class Dataset:
    name: str
    inputs: int
    outputs: int
    rows: list[list[int]]
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 120:
            raise ValueError("Der Datensatz braucht einen Namen mit 1–120 Zeichen.")
        if any(type(w) is not int or not 1 <= w <= 32 for w in (self.inputs, self.outputs)):
            raise ValueError("N und M müssen zwischen 1 und 32 liegen.")
        if not isinstance(self.rows, list) or not 1 <= len(self.rows) <= 65536:
            raise ValueError("Es sind 1–65536 Zuordnungsvektoren erforderlich.")
        unique = {}
        for i, row in enumerate(self.rows):
            if not isinstance(row, (list, tuple)) or len(row) != self.inputs + self.outputs:
                raise ValueError(f"Zeile {i + 1}: Länge muss N+M={self.inputs + self.outputs} sein.")
            if any(type(b) is not int or b not in (0, 1) for b in row):
                raise ValueError(f"Zeile {i + 1}: Nur ganzzahlige Bits 0 und 1 sind erlaubt.")
            key, value = tuple(row[:self.inputs]), tuple(row[self.inputs:])
            if key in unique and unique[key] != value:
                raise ValueError(f"Widerspruch in Zeile {i + 1}: Eingabe {list(key)} hat zwei verschiedene Ausgaben.")
            unique[key] = value
        self.rows = [list(k + v) for k, v in sorted(unique.items())]
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata muss ein Objekt sein.")
        validate_description(self.metadata.get("description", ""))
        if "interface" in self.metadata:
            self.metadata = {**self.metadata, "interface": interface(self.metadata["interface"], self.inputs, self.outputs)}
        if "program" in self.metadata:
            from .program import Program
            if (not self.metadata.get("interface") or any(k in self.metadata for k in
                    ("expression", "formula", "operation", "reference_circuit", "hierarchy", "oracle_file"))):
                raise ValueError("Programmreferenz braucht eine eigene benannte Schnittstelle ohne andere Referenz.")
            program = Program(self.metadata["program"], self.metadata["interface"])
            self.metadata = {**self.metadata, "program": program.spec}
        if "hierarchy" in self.metadata:
            from .blocks import BlockBundle
            bundle = BlockBundle(self.metadata["hierarchy"])
            c = bundle.expand()
            if (c.inputs != self.inputs or len(c.outputs) != self.outputs
                    or bundle.definition["interface"] != self.metadata.get("interface")
                    or any(k in self.metadata for k in ("expression", "formula", "operation", "reference_circuit"))):
                raise ValueError("Bausteinreferenz passt nicht zum Datensatz oder seiner Schnittstelle.")
        if "formula" in self.metadata:
            formula = self.metadata["formula"]
            ports = self.metadata.get("interface")
            if (not isinstance(formula, dict) or formula.get("version") != 1 or not ports
                    or "operation" in self.metadata or "reference_circuit" in self.metadata):
                raise ValueError("Formelmetadaten brauchen version 1 und eine eigene benannte Schnittstelle.")
            expressions = parse_formula(formula.get("source"), ports["outputs"][0]["name"])
            if expressions != self.metadata.get("expression") or set(expressions) != {p["name"] for p in ports["outputs"]}:
                raise ValueError("Formel, Ergebnisausdrücke und Ergebnisports passen nicht zusammen.")
        if "reference_circuit" in self.metadata:
            from .circuit import Circuit
            c = Circuit.from_dict(self.metadata["reference_circuit"])
            ports = self.metadata.get("interface", {})
            if len(ports.get("inputs", [])) != c.inputs or len(ports.get("outputs", [])) != len(c.outputs):
                raise ValueError("Die Referenzschaltung braucht einen benannten Port pro ursprünglichem Anschluss.")
        if "operation" in self.metadata:
            from .operations import operation_variant
            op = self.metadata["operation"]
            if not isinstance(op, dict) or op.get("version") != 1 or not isinstance(op.get("parameters"), dict):
                raise ValueError("Ungültige Operationsmetadaten.")
            canonical, ports, expressions = operation_variant(op)
            if op != canonical or self.metadata.get("interface") != ports or self.metadata.get("expression") != expressions:
                raise ValueError("Operationsmetadaten passen nicht zur Schnittstelle oder Referenz.")

    @property
    def exhaustive(self):
        return len(self.rows) == 1 << self.inputs

    def to_dict(self):
        return {"schema": 1, "name": self.name, "inputs": self.inputs, "outputs": self.outputs,
                "rows": self.rows, "metadata": self.metadata, "exhaustive": self.exhaustive}

    @classmethod
    def from_dict(cls, obj):
        return cls(obj["name"], obj["inputs"], obj["outputs"], obj["rows"], obj.get("metadata", {}))


FUNCTIONS = {name: getattr(math, name) for name in ("sin", "cos", "sqrt", "isqrt", "floor", "ceil")}
FUNCTIONS.update(abs=abs, min=min, max=max, round=round)
BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
          ast.BitAnd: operator.and_, ast.BitOr: operator.or_, ast.BitXor: operator.xor,
          ast.LShift: operator.lshift, ast.RShift: operator.rshift, ast.Pow: operator.pow}
CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
       ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}


class Expression:
    """Small AST interpreter, deliberately without eval/import/attribute access."""
    def __init__(self, text, *, syntax="python"):
        if not isinstance(text, str) or len(text) > 1000:
            raise ValueError("Ausdruck zu lang oder ungültig.")
        try:
            self.root = ast.parse(text.replace("^", "**") if syntax == "math" else text, mode="eval").body
        except SyntaxError as exc:
            raise ValueError(f"Ungültiger Ausdruck: {exc.msg}") from exc
        if sum(1 for _ in ast.walk(self.root)) > 200:
            raise ValueError("Ausdruck zu komplex.")
        self.functions = {**FUNCTIONS}
        if syntax == "math":
            self.functions.update(mod=operator.mod, div=operator.floordiv, xor=operator.xor)

    def __call__(self, names):
        def visit(n):
            if isinstance(n, ast.Constant) and type(n.value) in (int, float, bool):
                value = n.value
            elif isinstance(n, ast.Name) and n.id in names:
                value = names[n.id]
            elif isinstance(n, ast.BinOp) and type(n.op) in BINOPS:
                a, b = visit(n.left), visit(n.right)
                if isinstance(n.op, (ast.LShift, ast.RShift, ast.Pow)) and (type(b) is not int or not 0 <= b <= 32):
                    raise ValueError("Schiebeweite/Exponent muss ganzzahlig zwischen 0 und 32 liegen.")
                value = BINOPS[type(n.op)](a, b)
            elif isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd, ast.Not, ast.Invert)):
                value = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Not: operator.not_, ast.Invert: operator.invert}[type(n.op)](visit(n.operand))
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in self.functions and not n.keywords and 1 <= len(n.args) <= 3:
                value = self.functions[n.func.id](*(visit(a) for a in n.args))
            elif isinstance(n, ast.IfExp):
                value = visit(n.body) if visit(n.test) else visit(n.orelse)
            elif isinstance(n, ast.BoolOp):
                value = bool(visit(n.values[0]))
                for v in n.values[1:]:
                    if isinstance(n.op, ast.And):
                        value = value and bool(visit(v))
                    else:
                        value = value or bool(visit(v))
            elif isinstance(n, ast.Compare) and all(type(o) in CMP for o in n.ops):
                a, value = visit(n.left), True
                for op, rhs in zip(n.ops, n.comparators):
                    b = visit(rhs)
                    value = value and CMP[type(op)](a, b)
                    a = b
            else:
                raise ValueError("Nicht erlaubter Ausdruck. Variablen, Operatoren und freigegebene Mathematikfunktionen verwenden.")
            if type(value) not in (bool, int, float) or not math.isfinite(value) or abs(value) > 2**128:
                raise ValueError("Ergebnis ist keine endliche Zahl im erlaubten Bereich.")
            return value
        try:
            return visit(self.root)
        except (ArithmeticError, TypeError) as exc:
            raise ValueError(f"Ausdruck kann nicht ausgewertet werden: {exc}") from exc


PRESETS = {
    "not": (1, 1, "1-x0"), "nand": (2, 1, "1-(x0 & x1)"),
    "and": (2, 1, "x0 & x1"), "or": (2, 1, "x0 | x1"),
    "xor": (2, 1, "x0 ^ x1"), "nor": (2, 1, "1-(x0 | x1)"),
    "xnor": (2, 1, "1-(x0 ^ x1)"), "majority": (3, 1, "(x0+x1+x2)>=2"),
    "add": (4, 3, "a+b"), "sub": (4, 2, "(a-b) % 4"),
    "mul": (4, 4, "a*b"), "div": (4, 2, "a//b if b else 0"),
    "sqrt": (8, 4, "isqrt(x)"),
    "sin": (16, 12, "round(sin(pi*x/65535)*4095)"),
    "cos": (16, 12, "round((cos(pi*x/65535)+1)*4095/2)"),
}


def generate(name, inputs, outputs, expression=None, samples=None, seed=1, *, oracle=None, ports=None, reference_circuit=None, formula=None, edge_inputs=None, program=None, cancel_event=None):
    if any(type(w) is not int or not 1 <= w <= 32 for w in (inputs, outputs)):
        raise ValueError("N und M müssen zwischen 1 und 32 liegen.")
    if program is not None:
        from .program import Program
        prepared = Program(program, ports)
        ports = prepared.ports
    ports = interface(ports, inputs, outputs) if ports is not None else None
    if ports is not None and oracle is not None:
        raise ValueError("Benannte Ports werden nur für Ausdrücke unterstützt.")
    interpreter = budget = None
    if program is not None:
        from .program import Program
        if not ports or any(v is not None for v in (expression, formula, oracle, reference_circuit)):
            raise ValueError("Programm braucht eine eigene benannte Schnittstelle ohne andere Referenz.")
        interpreter = prepared
        budget = interpreter.budget(cancel_event)
    if formula is not None:
        if not ports or oracle is not None or reference_circuit is not None:
            raise ValueError("Formeln brauchen eine eigene benannte Schnittstelle.")
        if any(p["name"] in ("mod", "div", "xor") for p in ports["inputs"] + ports["outputs"]):
            raise ValueError("mod, div und xor sind im Formelmodus als Funktionsnamen reserviert.")
        expression = parse_formula(formula, ports["outputs"][0]["name"])
    reference = None
    if reference_circuit is not None:
        from .circuit import Circuit
        reference = Circuit.from_dict(reference_circuit)
        if not ports or len(ports["inputs"]) != reference.inputs or len(ports["outputs"]) != len(reference.outputs):
            raise ValueError("Die Referenzschaltung braucht einen benannten Port pro ursprünglichem Anschluss.")
    if ports and reference is None and interpreter is None:
        if isinstance(expression, str) and len(ports["outputs"]) == 1:
            expression = {ports["outputs"][0]["name"]: expression}
        if not isinstance(expression, dict) or set(expression) != {p["name"] for p in ports["outputs"]}:
            raise ValueError("Für jeden Ergebnisport ist genau ein Ausdruck erforderlich.")
        functions = {key: Expression(value, syntax="math" if formula is not None else "python") for key, value in expression.items()}
        if formula is not None:
            allowed = {p["name"] for p in ports["inputs"]} | {"x", "pi"} | {f"x{i}" for i in range(inputs)}
            for key, fn in functions.items():
                for node in ast.walk(fn.root):
                    if isinstance(node, ast.Name) and node.id not in allowed | set(fn.functions):
                        raise ValueError(f"Ergebnis {key}: unbekannter Eingangsname {node.id}. Ergebnisse dürfen nicht voneinander abhängen.")
    total = 1 << inputs
    if samples is not None and (type(samples) is not int or not 1 <= samples <= 65536):
        raise ValueError("Die Anzahl Vektoren muss zwischen 1 und 65536 liegen.")
    count = min(total, samples if samples is not None else 256)
    # Include domain endpoints in a sample, particularly for fixed-point functions.
    xs = list(range(total)) if count == total else list(dict.fromkeys(
        [0, total - 1] + (edge_inputs or [])))[:count]
    if count != total and count > len(xs):
        if edge_inputs is None:
            xs += random.Random(seed).sample(range(1, total - 1), count - len(xs))
        else:
            used = set(xs)
            candidates = random.Random(seed).sample(range(total), min(total, count + len(used)))
            xs += [x for x in candidates if x not in used][:count - len(xs)]
        xs.sort()
    fn = None if ports else Expression(expression) if oracle is None else lambda env: oracle(env["x"])
    rows = []
    for x in xs:
        vector = bits(x, inputs)
        env = {"x": x, "a": x & ((1 << (inputs // 2)) - 1), "b": x >> (inputs // 2), "pi": math.pi}
        env.update({f"x{i}": v for i, v in enumerate(vector)})
        if ports:
            # An explicit interface replaces the historical implicit a/b halves.
            env = {"x": x, "pi": math.pi, **{f"x{i}": v for i, v in enumerate(vector)},
                   **{p["name"]: decode(x, p) for p in ports["inputs"]}}
            if interpreter:
                results = interpreter.run(x, budget)
            elif reference:
                wires = [env[p["name"]] for p in ports["inputs"]]
                for a, b in reference.gates:
                    wires.append(~(wires[a] & wires[b]))
                results = [wires[o] for o in reference.outputs]
            else:
                results = [functions[p["name"]](env) for p in ports["outputs"]]
            output = []
            for port, value in zip(ports["outputs"], results):
                output += bits(encode(value, port, x), port["bits"])
            rows.append(vector + output)
            continue
        result = fn(env)
        if result != int(result) or not 0 <= result < 1 << outputs:
            raise ValueError(f"Ausgabe für x={x} ist {result}; erwartet wird eine ganze Zahl 0…{(1 << outputs) - 1}.")
        rows.append(vector + bits(int(result), outputs))
    metadata = {"expression": expression, "seed": seed, "bit_order": "LSB-first"}
    if ports:
        metadata["interface"] = ports
    if formula is not None:
        metadata["formula"] = {"version": 1, "source": formula}
    if interpreter:
        budget.check_cancelled()
        metadata.pop("expression")
        metadata["program"] = interpreter.spec
    if reference:
        metadata.pop("expression")
        metadata["reference_circuit"] = reference.to_dict()
    return Dataset(name, inputs, outputs, rows, metadata)


def preset(name, samples=None, seed=1):
    if name not in PRESETS:
        raise ValueError("Unbekannte Vorlage.")
    n, m, expr = PRESETS[name]
    return generate(name, n, m, expr, samples, seed)


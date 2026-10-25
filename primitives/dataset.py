"""Validated N+M vectors and bounded expression based truth-table generation."""
import ast
from dataclasses import dataclass, field
import math
import operator
import random


def bits(value, width):
    return [(value >> i) & 1 for i in range(width)]


def integer(vector):
    return sum(b << i for i, b in enumerate(vector))


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
    def __init__(self, text):
        if not isinstance(text, str) or len(text) > 1000:
            raise ValueError("Ausdruck zu lang oder ungültig.")
        try:
            self.root = ast.parse(text, mode="eval").body
        except SyntaxError as exc:
            raise ValueError(f"Ungültiger Ausdruck: {exc.msg}") from exc
        if sum(1 for _ in ast.walk(self.root)) > 200:
            raise ValueError("Ausdruck zu komplex.")

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
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCTIONS and not n.keywords and 1 <= len(n.args) <= 3:
                value = FUNCTIONS[n.func.id](*(visit(a) for a in n.args))
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


def generate(name, inputs, outputs, expression, samples=None, seed=1, *, oracle=None):
    if any(type(w) is not int or not 1 <= w <= 32 for w in (inputs, outputs)):
        raise ValueError("N und M müssen zwischen 1 und 32 liegen.")
    total = 1 << inputs
    if samples is not None and (type(samples) is not int or not 1 <= samples <= 65536):
        raise ValueError("Die Anzahl Vektoren muss zwischen 1 und 65536 liegen.")
    count = min(total, samples if samples is not None else 256)
    # Include domain endpoints in a sample, particularly for fixed-point functions.
    xs = list(range(total)) if count == total else sorted({0, total - 1} if count >= 2 else {0})
    if count != total and count > len(xs):
        xs += random.Random(seed).sample(range(1, total - 1), count - len(xs))
        xs.sort()
    fn, rows = Expression(expression) if oracle is None else lambda env: oracle(env["x"]), []
    for x in xs:
        vector = bits(x, inputs)
        env = {"x": x, "a": x & ((1 << (inputs // 2)) - 1), "b": x >> (inputs // 2), "pi": math.pi}
        env.update({f"x{i}": v for i, v in enumerate(vector)})
        result = fn(env)
        if result != int(result) or not 0 <= result < 1 << outputs:
            raise ValueError(f"Ausgabe für x={x} ist {result}; erwartet wird eine ganze Zahl 0…{(1 << outputs) - 1}.")
        rows.append(vector + bits(int(result), outputs))
    return Dataset(name, inputs, outputs, rows, {"expression": expression, "seed": seed, "bit_order": "LSB-first"})


def preset(name, samples=None, seed=1):
    if name not in PRESETS:
        raise ValueError("Unbekannte Vorlage.")
    n, m, expr = PRESETS[name]
    return generate(name, n, m, expr, samples, seed)


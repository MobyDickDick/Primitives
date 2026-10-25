"""Acyclic NAND circuits; wire indices are zero based in JSON."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Circuit:
    inputs: int
    gates: tuple[tuple[int, int], ...]
    outputs: tuple[int, ...]

    def __post_init__(self):
        if type(self.inputs) is not int or not 1 <= self.inputs <= 32:
            raise ValueError("Die Anzahl Eingänge muss zwischen 1 und 32 liegen.")
        if len(self.gates) > 512 or not 1 <= len(self.outputs) <= 32:
            raise ValueError("Höchstens 512 Gatter und 1–32 Ausgänge sind erlaubt.")
        for i, gate in enumerate(self.gates):
            if len(gate) != 2 or any(type(r) is not int or not 0 <= r < self.inputs + i for r in gate):
                raise ValueError(f"Gatter {i}: ungültiger oder vorwärts gerichteter Verweis.")
        if any(type(r) is not int or not 0 <= r < self.inputs + len(self.gates) for r in self.outputs):
            raise ValueError("Ungültiger Ausgangsverweis.")

    @classmethod
    def from_dict(cls, obj):
        return cls(obj["inputs"], tuple(tuple(g) for g in obj["gates"]), tuple(obj["outputs"]))

    def to_dict(self):
        return {"inputs": self.inputs, "gates": [list(g) for g in self.gates], "outputs": list(self.outputs)}

    def wires(self, bits):
        if len(bits) != self.inputs or any(type(b) is not int or b not in (0, 1) for b in bits):
            raise ValueError("Der Eingabevektor enthält nicht die erwarteten Bits.")
        values = list(bits)
        for a, b in self.gates:
            values.append(1 - (values[a] & values[b]))
        return values

    def evaluate(self, bits):
        values = self.wires(bits)
        return [values[o] for o in self.outputs]

    def active(self):
        active, pending = set(), list(self.outputs)
        while pending:
            r = pending.pop()
            if r >= self.inputs and r not in active:
                active.add(r)
                pending.extend(self.gates[r - self.inputs])
        return active

    def compact(self):
        active = self.active()
        mapping = {i: i for i in range(self.inputs)}
        gates = []
        for i, (a, b) in enumerate(self.gates, self.inputs):
            if i in active:
                mapping[i] = self.inputs + len(gates)
                gates.append((mapping[a], mapping[b]))
        return Circuit(self.inputs, tuple(gates), tuple(mapping[o] for o in self.outputs))

    @property
    def depth(self):
        depths = [0] * self.inputs
        for a, b in self.gates:
            depths.append(1 + max(depths[a], depths[b]))
        return max(depths[o] for o in self.outputs)

    def expressions(self, max_chars=10000):
        values = [str(i + 1) for i in range(self.inputs)]
        for a, b in self.gates:
            expr = f"({values[a]}) ⊼ ({values[b]})"
            if len(expr) > max_chars:
                raise ValueError("Klammerausdruck zu gross; bitte die Gatterliste verwenden.")
            values.append(expr)
        return [values[o] for o in self.outputs]


def parse_expression(source: str, inputs: int) -> Circuit:
    """Parse infix NAND and legacy pairs; merge identical subexpressions."""
    if not isinstance(source, str) or len(source) > 10000:
        raise ValueError("Ungültiger oder zu langer NAND-Ausdruck.")
    tokens = re.findall(r"\d+|\S", source.replace(r"\bar{\wedge}", "⊼"))
    pos, gates, known = 0, [], {}

    def parse(level=0):
        nonlocal pos
        a = atom(level)
        if pos < len(tokens) and tokens[pos] == "⊼":
            pos += 1
            return gate(a, atom(level))
        return a

    def gate(a, b):
        pair = tuple(sorted((a, b)))
        if pair not in known:
            known[pair] = inputs + len(gates)
            gates.append(pair)
        return known[pair]

    def atom(level):
        nonlocal pos
        if level > 100 or pos >= len(tokens):
            raise ValueError("Unvollständiger oder zu tief verschachtelter NAND-Ausdruck.")
        token = tokens[pos]
        pos += 1
        if token.isdigit():
            value = int(token)
            if not 1 <= value <= inputs:
                raise ValueError(f"Eingang {value} liegt nicht zwischen 1 und {inputs}.")
            return value - 1
        if token != "(":
            raise ValueError("Eine Eingangsnummer oder '(' wird erwartet.")
        a = parse(level + 1)
        if pos < len(tokens) and tokens[pos] == ",":
            pos += 1
            a = gate(a, parse(level + 1))
        expect(")")
        return a

    def expect(token):
        nonlocal pos
        if pos >= len(tokens) or tokens[pos] != token:
            raise ValueError(f"'{token}' wird erwartet.")
        pos += 1

    output = parse()
    if pos != len(tokens):
        raise ValueError("Unerwartete Zeichen nach dem NAND-Ausdruck.")
    return Circuit(inputs, tuple(gates), (output,))


"""Structural NAND lowering of fixed-control bit-array programs.

Only parameters control loops/branches/indices. Input-dependent work consists
of explicit single-bit &, | and ^ operations, with bits/pack as wiring.
Unsupported constructs fail rather than falling back to truth-table synthesis.
"""
import ast
from dataclasses import dataclass

from .circuit import Circuit
from .limits import MAX_BITS
from .program import BINOPS, CMP, MAX_ARRAY_BITS, MAX_CALL_DEPTH, Program, exact_log2


@dataclass(frozen=True)
class Wire:
    ref: int


@dataclass(frozen=True)
class Word:
    bits: tuple


class Synthesizer:
    def __init__(self, program):
        self.program = program
        self.inputs = sum(p["bits"] for p in program.ports["inputs"])
        self.gates, self.known = [], {}
        self.budget = program.budget()
        self.budget.start()

    def nand(self, a, b):
        pair = tuple(sorted((a.ref, b.ref)))
        if pair not in self.known:
            if len(self.gates) >= 512:
                raise ValueError("NAND-Synthese überschreitet die Grenze von 512 Gattern. Kleinere Bitbreite wählen.")
            self.known[pair] = Wire(self.inputs + len(self.gates))
            self.gates.append(pair)
        return self.known[pair]

    def invert(self, value):
        if type(value) is int:
            return 1 ^ value
        if value.ref >= self.inputs:
            a, b = self.gates[value.ref - self.inputs]
            if a == b:
                return Wire(a)
        return self.nand(value, value)

    def logic(self, op, a, b):
        if a == b:
            return 0 if op is ast.BitXor else a
        if type(a) is int:
            a, b = b, a
        if type(b) is int:
            if op is ast.BitAnd:
                return a if b else 0
            if op is ast.BitOr:
                return 1 if b else a
            return self.invert(a) if b else a
        if op is ast.BitAnd:
            return self.invert(self.nand(a, b))
        if op is ast.BitOr:
            return self.nand(self.invert(a), self.invert(b))
        common = self.nand(a, b)
        return self.nand(self.nand(a, common), self.nand(b, common))

    @staticmethod
    def fail(node, message):
        Program._error(node, "NAND-Synthese: " + message)

    def static(self, value, node):
        if type(value) not in (int, bool):
            self.fail(node, "Steuerung, Index und Ganzzahlarithmetik müssen allein von festen Parametern abhängen.")
        return int(value)

    def bit(self, value, node):
        if isinstance(value, Wire) or type(value) is int and value in (0, 1):
            return value
        self.fail(node, "explizites einzelnes Bit erforderlich; bits(wert, breite) verwenden.")

    def array(self, value, node):
        if not isinstance(value, list):
            self.fail(node, "Bit-Array erforderlich.")
        return value

    def unpack(self, value, width, node):
        width = self.static(width, node)
        if not 1 <= width <= MAX_ARRAY_BITS:
            self.fail(node, "Bitbreite muss zwischen 1 und 128 liegen.")
        if isinstance(value, Wire):
            value = Word((value,))
        if isinstance(value, Word):
            return list((value.bits + (0,) * width)[:width])
        value = self.static(value, node)
        return [(value >> i) & 1 for i in range(width)]

    def expression(self, node, env, depth):
        self.budget.tick(node)
        value = lambda child: self.expression(child, env, depth)
        if isinstance(node, ast.Constant):
            result = node.value
        elif isinstance(node, ast.Name):
            if node.id not in env:
                self.fail(node, f"Variable {node.id} wurde noch nicht zugewiesen.")
            result = env[node.id]
        elif isinstance(node, ast.List):
            result = [self.bit(value(child), child) for child in node.elts]
        elif isinstance(node, ast.Subscript):
            items = self.array(value(node.value), node)
            if isinstance(node.slice, ast.Slice):
                parts = [self.static(value(v), v) if v is not None else None
                         for v in (node.slice.lower, node.slice.upper, node.slice.step)]
                result = items[slice(*parts)]
            else:
                i = self.static(value(node.slice), node)
                if not 0 <= i < len(items):
                    self.fail(node, "Arrayindex ausserhalb der Bitbreite.")
                result = items[i]
        elif isinstance(node, ast.BinOp):
            a, b = value(node.left), value(node.right)
            op = type(node.op)
            if op is ast.Add and isinstance(a, list) and isinstance(b, list):
                result = a + b
            elif op is ast.Mult and (isinstance(a, list) or isinstance(b, list)):
                items, count = (a, b) if isinstance(a, list) else (b, a)
                count = self.static(count, node)
                if count < 0 or len(items) * count > MAX_ARRAY_BITS:
                    self.fail(node, "Arraywiederholung überschreitet 128 Bits.")
                result = items * count
            elif op in (ast.BitAnd, ast.BitOr, ast.BitXor) and (isinstance(a, Wire) or isinstance(b, Wire)):
                result = self.logic(op, self.bit(a, node), self.bit(b, node))
            else:
                a, b = self.static(a, node), self.static(b, node)
                if op in (ast.Pow, ast.LShift, ast.RShift) and not 0 <= b <= MAX_BITS:
                    self.fail(node, f"Exponent/Schiebeweite muss zwischen 0 und {MAX_BITS} liegen.")
                result = BINOPS[op](a, b)
        elif isinstance(node, ast.UnaryOp):
            a = self.static(value(node.operand), node)
            result = {ast.USub: lambda: -a, ast.UAdd: lambda: a,
                      ast.Not: lambda: int(not a), ast.Invert: lambda: ~a}[type(node.op)]()
        elif isinstance(node, ast.Compare):
            a, result = self.static(value(node.left), node), 1
            for op, child in zip(node.ops, node.comparators):
                b = self.static(value(child), child)
                if not CMP[type(op)](a, b):
                    result = 0
                    break
                a = b
        elif isinstance(node, ast.BoolOp):
            result = int(bool(self.static(value(node.values[0]), node)))
            for child in node.values[1:]:
                if (isinstance(node.op, ast.And) and not result) or (isinstance(node.op, ast.Or) and result):
                    break
                result = int(bool(self.static(value(child), child)))
        elif isinstance(node, ast.IfExp):
            result = value(node.body if self.static(value(node.test), node) else node.orelse)
        elif isinstance(node, ast.Call):
            args = [value(a) for a in node.args]
            name = node.func.id
            if name == "bits":
                result = self.unpack(*args, node)
            elif name == "pack":
                result = Word(tuple(self.array(args[0], node)))
            elif name == "len":
                result = len(self.array(args[0], node))
            elif name == "LOG2":
                result = exact_log2(self.static(args[0], node))
            elif name in self.program.functions:
                if depth >= MAX_CALL_DEPTH:
                    self.fail(node, "Aufruftiefe überschritten.")
                function = self.program.functions[name]
                if any(isinstance(a, list) for a in args):
                    self.fail(node, "Funktionsargumente müssen Zahlen sein; pack(array) verwenden.")
                result = self.execute(function, {**self.program.parameters, **dict(zip(function.arguments, args))}, depth + 1)[0]
            else:
                self.fail(node, f"{name} wird nicht strukturell übersetzt; explizite Bitoperationen verwenden.")
        else:
            self.fail(node, "Ausdruck wird nicht strukturell übersetzt.")
        if isinstance(result, list):
            if len(result) > MAX_ARRAY_BITS:
                self.fail(node, "Bit-Array überschreitet 128 Bits.")
            for _ in result:
                self.budget.tick(node)
        elif type(result) in (int, bool):
            if abs(result) > 2**128:
                self.fail(node, "Ganzzahlergebnis zu gross.")
            result = int(result)
        return result

    def execute(self, program, env, depth=0):
        pc, iterators = 0, {}
        while pc < len(program.code):
            op, arg, node = program.code[pc]
            self.budget.tick(node)
            value = lambda expression: self.expression(expression, env, depth)
            pc += 1
            if op == "assign":
                result = value(arg[1])
                if isinstance(arg[0], str):
                    env[arg[0]] = result
                else:
                    target = arg[0]
                    items = self.array(value(target.value), node)
                    i = self.static(value(target.slice), node)
                    if not 0 <= i < len(items):
                        self.fail(node, "Arrayindex ausserhalb der Bitbreite.")
                    items[i] = self.bit(result, node)
            elif op == "return":
                results = [value(v) for v in arg]
                if any(isinstance(v, list) for v in results):
                    self.fail(node, "Rückgabe braucht pack(array).")
                return results
            elif op == "require":
                if not self.static(value(arg), node):
                    self.fail(node, "Funktionsbedingung nicht erfüllt.")
            elif op == "test":
                if not self.static(value(arg[0]), node):
                    pc = arg[1]
            elif op == "jump":
                pc = arg
            elif op == "iteration":
                self.budget.iteration(node)
            elif op == "range":
                args = [self.static(value(a), node) for a in arg[1]]
                iterators[arg[2]] = iter(range(*args))
            elif op == "next":
                try:
                    env[arg[0]] = next(iterators[pc - 1])
                    self.budget.iteration(node)
                except StopIteration:
                    pc = arg[2]
            else:
                self.fail(node, "Sprünge werden nicht strukturell übersetzt.")
        self.fail(node, "Programmende ohne return.")

    def compile(self):
        if any(p["signed"] for side in ("inputs", "outputs") for p in self.program.ports[side]):
            raise ValueError("Die strukturelle NAND-Synthese unterstützt unsigned Ports.")
        env = {**self.program.parameters, **{
            p["name"]: Word(tuple(Wire(p["offset"] + i) for i in range(p["bits"])))
            for p in self.program.ports["inputs"]}}
        values = self.execute(self.program, env)
        outputs = []
        node = self.program.code[-1][2]
        for port, value in zip(self.program.ports["outputs"], values):
            width = port["bits"]
            if port["overflow"] == "error":
                if isinstance(value, Word) and any(bit != 0 for bit in value.bits[width:]):
                    self.fail(node, "Ergebnisbreite nicht nachweisbar; ausdrücklich mit bits/pack begrenzen.")
                if type(value) is int and not 0 <= value < 2**width:
                    self.fail(node, "Ergebnis ausserhalb der Portbreite.")
            outputs.extend(self.unpack(value, width, node))
        # Constants are ordinary NAND wiring, without extra primary inputs.
        if any(type(bit) is int for bit in outputs):
            one = self.nand(Wire(0), self.invert(Wire(0)))
            zero = self.nand(one, one)
            outputs = [one if bit == 1 else zero if bit == 0 else bit for bit in outputs]
        return Circuit(self.inputs, tuple(self.gates), tuple(bit.ref for bit in outputs)).simplify()


def synthesize(program):
    if not isinstance(program, Program) or program.spec["version"] != 2:
        raise ValueError("Strukturelle NAND-Synthese benötigt ein konkretisiertes Template.")
    try:
        return Synthesizer(program).compile()
    except (ArithmeticError, IndexError) as exc:
        raise ValueError(f"NAND-Synthese: {exc}") from exc

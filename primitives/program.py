"""Versioned, bounded integer programs. ASTs are interpreted, never executed."""
import ast
import keyword
import operator
import re
from .ports import decode, interface


DEFAULT_LIMITS = {"steps": 10000, "iterations": 10000, "total_steps": 1000000}
MAX_LIMITS = {"steps": 100000, "iterations": 100000, "total_steps": 5000000}
FUNCTIONS = {"abs": abs, "min": min, "max": max, "div": operator.floordiv,
             "mod": operator.mod, "xor": operator.xor}
BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
          ast.BitAnd: operator.and_, ast.BitOr: operator.or_, ast.BitXor: operator.xor,
          ast.LShift: operator.lshift, ast.RShift: operator.rshift}
CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
       ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}
RESERVED = set(FUNCTIONS) | {"range"}


class ProgramCancelled(ValueError):
    pass


def program_spec(spec):
    if not isinstance(spec, dict) or type(spec.get("version")) is not int or spec["version"] != 1:
        raise ValueError("Programm braucht Sprachversion 1.")
    if set(spec) - {"version", "source", "limits"}:
        raise ValueError("Unbekannte Programmparameter.")
    source = spec.get("source")
    if not isinstance(source, str) or not source.strip() or len(source) > 16000:
        raise ValueError("Programm braucht 1–16000 Zeichen.")
    limits = spec.get("limits", {})
    if not isinstance(limits, dict) or set(limits) - set(DEFAULT_LIMITS):
        raise ValueError("Programmbudgets: steps, iterations und total_steps verwenden.")
    limits = {**DEFAULT_LIMITS, **limits}
    for key, value in limits.items():
        if type(value) is not int or not 1 <= value <= MAX_LIMITS[key]:
            raise ValueError(f"Programmbudget {key}: 1–{MAX_LIMITS[key]} erforderlich.")
    return {"version": 1, "source": source, "limits": limits}


class Program:
    """Small Python-style grammar: assignment, return, if/else, while, range-for."""
    def __init__(self, spec, ports):
        self.spec = program_spec(spec)
        self.ports = interface(ports)
        self.inputs = {p["name"] for p in self.ports["inputs"]}
        if RESERVED & {p["name"] for side in ("inputs", "outputs") for p in self.ports[side]}:
            raise ValueError("range, abs, min, max, div, mod und xor sind im Programmmodus reserviert.")
        try:
            tree = ast.parse(self.spec["source"])
        except (SyntaxError, RecursionError, ValueError) as exc:
            raise ValueError(f"Programm: Zeile {getattr(exc, 'lineno', 1)}, Spalte {getattr(exc, 'offset', 1)}: ungültige Syntax.") from exc
        if sum(1 for _ in ast.walk(tree)) > 2000:
            raise ValueError("Programm ist zu komplex (höchstens 2000 Syntaxknoten).")
        self.locals = set()
        self.code = []
        self._compile(tree.body, 0)
        if not any(op == "return" for op, _, _ in self.code):
            raise ValueError("Programm braucht eine return-Anweisung.")
        allowed = self.inputs | self.locals
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in allowed | RESERVED:
                self._error(node, f"unbekannte Variable {node.id}.")

    @staticmethod
    def _error(node, message):
        raise ValueError(f"Zeile {getattr(node, 'lineno', 1)}, Spalte {getattr(node, 'col_offset', 0) + 1}: {message}")

    def _target(self, node):
        if (not isinstance(node, ast.Name) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,31}", node.id)
                or keyword.iskeyword(node.id) or node.id in RESERVED | self.inputs):
            self._error(node, "lokaler Bezeichner erforderlich; Eingänge sind schreibgeschützt.")
        self.locals.add(node.id)
        if len(self.locals) > 64:
            self._error(node, "höchstens 64 lokale Variablen erlaubt.")
        return node.id

    def _expr(self, node, depth=0):
        if depth > 32:
            self._error(node, "Ausdruck zu tief verschachtelt.")
        children = []
        if isinstance(node, ast.Constant) and type(node.value) in (int, bool) and abs(node.value) <= 2**128:
            pass
        elif isinstance(node, ast.Name) and node.id not in RESERVED:
            pass
        elif isinstance(node, ast.BinOp) and type(node.op) in BINOPS:
            children = [node.left, node.right]
        elif isinstance(node, ast.UnaryOp) and type(node.op) in (ast.USub, ast.UAdd, ast.Not, ast.Invert):
            children = [node.operand]
        elif isinstance(node, ast.BoolOp) and type(node.op) in (ast.And, ast.Or):
            children = node.values
        elif isinstance(node, ast.Compare) and all(type(op) in CMP for op in node.ops):
            children = [node.left, *node.comparators]
        elif isinstance(node, ast.IfExp):
            children = [node.test, node.body, node.orelse]
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS
              and not node.keywords and ((node.func.id == "abs" and len(node.args) == 1)
              or (node.func.id != "abs" and len(node.args) == 2))):
            children = node.args
        else:
            self._error(node, "nicht erlaubter Ausdruck; nur ganze Zahlen und freigegebene Operatoren/Funktionen verwenden.")
        for child in children:
            self._expr(child, depth + 1)
        return node

    def _emit(self, op, arg, node):
        self.code.append((op, arg, node))
        return len(self.code) - 1

    def _compile(self, statements, depth):
        if depth > 16:
            self._error(statements[0], "höchstens 16 verschachtelte Kontrollstrukturen erlaubt.")
        for node in statements:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                self._emit("assign", (self._target(node.targets[0]), self._expr(node.value)), node)
            elif isinstance(node, ast.AugAssign) and type(node.op) in BINOPS:
                name = self._target(node.target)
                expr = ast.copy_location(ast.BinOp(left=ast.copy_location(ast.Name(id=name, ctx=ast.Load()), node.target),
                                                  op=node.op, right=node.value), node)
                self._emit("assign", (name, self._expr(expr)), node)
            elif isinstance(node, ast.Return) and node.value is not None:
                values = node.value.elts if isinstance(node.value, ast.Tuple) else [node.value]
                if len(values) != len(self.ports["outputs"]):
                    self._error(node, "return braucht genau einen Wert je Ergebnisport, in Portreihenfolge.")
                self._emit("return", [self._expr(v) for v in values], node)
            elif isinstance(node, ast.If):
                branch = self._emit("test", [self._expr(node.test), None], node)
                self._compile(node.body, depth + 1)
                end = self._emit("jump", None, node)
                self.code[branch][1][1] = len(self.code)
                self._compile(node.orelse, depth + 1)
                self.code[end] = ("jump", len(self.code), node)
            elif isinstance(node, ast.While) and not node.orelse:
                start = self._emit("test", [self._expr(node.test), None], node)
                self._emit("iteration", None, node)
                self._compile(node.body, depth + 1)
                self._emit("jump", start, node)
                self.code[start][1][1] = len(self.code)
            elif (isinstance(node, ast.For) and not node.orelse and isinstance(node.iter, ast.Call)
                  and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range"
                  and not node.iter.keywords and 1 <= len(node.iter.args) <= 3):
                name = self._target(node.target)
                init = self._emit("range", [name, [self._expr(a) for a in node.iter.args], None], node)
                start = self._emit("next", [name, init, None], node)
                self._compile(node.body, depth + 1)
                self._emit("jump", start, node)
                self.code[init][1][2] = start
                self.code[start][1][2] = len(self.code)
            else:
                self._error(node, "nicht erlaubte Anweisung. Zuweisung, return, if/else, while oder for … in range(…) verwenden.")

    def budget(self, cancel_event=None):
        return Budget(self.spec["limits"], cancel_event)

    def run(self, x, budget=None):
        budget = budget if budget is not None else self.budget()
        budget.start()
        env = {p["name"]: decode(x, p) for p in self.ports["inputs"]}
        iterators = {}
        pc = 0

        def value(node):
            budget.tick(node)
            if isinstance(node, ast.Constant):
                result = node.value
            elif isinstance(node, ast.Name):
                if node.id not in env:
                    self._error(node, f"Variable {node.id} wurde noch nicht zugewiesen.")
                result = env[node.id]
            elif isinstance(node, ast.BinOp):
                a, b = value(node.left), value(node.right)
                if type(node.op) in (ast.Pow, ast.LShift, ast.RShift) and not 0 <= b <= 32:
                    self._error(node, "Exponent/Schiebeweite muss zwischen 0 und 32 liegen.")
                result = BINOPS[type(node.op)](a, b)
            elif isinstance(node, ast.UnaryOp):
                result = {ast.USub: operator.neg, ast.UAdd: operator.pos,
                          ast.Not: operator.not_, ast.Invert: operator.invert}[type(node.op)](value(node.operand))
            elif isinstance(node, ast.BoolOp):
                result = bool(value(node.values[0]))
                for child in node.values[1:]:
                    if isinstance(node.op, ast.And): result = result and bool(value(child))
                    else: result = result or bool(value(child))
            elif isinstance(node, ast.Compare):
                a, result = value(node.left), True
                for op, child in zip(node.ops, node.comparators):
                    b = value(child)
                    if not CMP[type(op)](a, b):
                        result = False
                        break
                    a = b
            elif isinstance(node, ast.IfExp):
                result = value(node.body) if value(node.test) else value(node.orelse)
            else:  # Calls have been restricted to integer functions during validation.
                result = FUNCTIONS[node.func.id](*(value(a) for a in node.args))
            if type(result) not in (int, bool) or abs(result) > 2**128:
                self._error(node, "Ganzzahlergebnis überschreitet den Bereich −2^128…2^128.")
            return int(result)

        node = self.code[0][2]
        try:
            while pc < len(self.code):
                op, arg, node = self.code[pc]
                budget.tick(node)
                pc += 1
                if op == "assign":
                    env[arg[0]] = value(arg[1])
                elif op == "return":
                    return [value(v) for v in arg]
                elif op == "test":
                    if not value(arg[0]): pc = arg[1]
                elif op == "jump":
                    pc = arg
                elif op == "iteration":
                    budget.iteration(node)
                elif op == "range":
                    args = [value(a) for a in arg[1]]
                    start, stop, step = (0, args[0], 1) if len(args) == 1 else (*args, 1) if len(args) == 2 else args
                    if step == 0: self._error(node, "range-Schritt darf nicht 0 sein.")
                    iterators[arg[2]] = [start, stop, step]
                elif op == "next":
                    current, stop, step = iterators[pc - 1]
                    finished = current >= stop if step > 0 else current <= stop
                    if finished:
                        pc = arg[2]
                    else:
                        budget.iteration(node)
                        env[arg[0]] = current
                        iterators[pc - 1][0] += step
            self._error(node, "Programmende ohne return für diese Eingabe.")
        except ProgramCancelled:
            raise
        except (ValueError, ArithmeticError, TypeError) as exc:
            inputs = ', '.join(f"{p['name']}={decode(x, p)}" for p in self.ports['inputs'])
            raise ValueError(f"Eingabe x={x} ({inputs}), "
                             f"Zeile {node.lineno}, Spalte {node.col_offset + 1}: {exc}") from exc


class Budget:
    def __init__(self, limits, cancel_event):
        self.limits, self.cancel_event = limits, cancel_event
        self.total = 0

    def start(self):
        self.steps = self.iterations = 0

    def tick(self, node):
        self.check_cancelled()
        self.steps += 1
        self.total += 1
        if self.steps > self.limits["steps"]:
            Program._error(node, "Anweisungsbudget je Eingabe überschritten (mögliche Endlosschleife).")
        if self.total > self.limits["total_steps"]:
            Program._error(node, "Gesamtbudget der Vektorerzeugung überschritten.")

    def iteration(self, node):
        self.iterations += 1
        if self.iterations > self.limits["iterations"]:
            Program._error(node, "Iterationsbudget je Eingabe überschritten (mögliche Endlosschleife).")

    def check_cancelled(self):
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise ProgramCancelled("Vektorerzeugung abgebrochen; kein Datensatz gespeichert.")

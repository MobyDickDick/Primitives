"""Versioned, bounded integer/bit-array programs. ASTs are interpreted, never executed."""
import ast
import keyword
import operator
import re
from .ports import decode, interface


DEFAULT_LIMITS = {"steps": 10000, "iterations": 10000, "total_steps": 1000000}
MAX_LIMITS = {"steps": 100000, "iterations": 100000, "total_steps": 5000000}
MAX_ARRAY_BITS = 128
FUNCTIONS = {"abs": abs, "min": min, "max": max, "div": operator.floordiv,
             "mod": operator.mod, "xor": operator.xor}
FUNCTION_ARITY = {name: 1 if name == "abs" else 2 for name in FUNCTIONS}
FUNCTION_ARITY.update(bits=2, pack=1, len=1)
BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
          ast.BitAnd: operator.and_, ast.BitOr: operator.or_, ast.BitXor: operator.xor,
          ast.LShift: operator.lshift, ast.RShift: operator.rshift}
CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
       ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}
RESERVED = set(FUNCTION_ARITY) | {"range"}


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
    """Bounded Python-style assignments, bit arrays, return, if/else and loops."""
    def __init__(self, spec, ports):
        self.spec = program_spec(spec)
        self.ports = interface(ports)
        self.inputs = {p["name"] for p in self.ports["inputs"]}
        if RESERVED & {p["name"] for side in ("inputs", "outputs") for p in self.ports[side]}:
            raise ValueError("range, abs, min, max, div, mod, xor, bits, pack und len sind im Programmmodus reserviert.")
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

    def _assignment_target(self, node):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and not isinstance(node.slice, ast.Slice):
            self._target(node.value)
            self._expr(node.slice)
            return node
        return self._target(node)

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
        elif isinstance(node, ast.List):
            if len(node.elts) > MAX_ARRAY_BITS:
                self._error(node, "Bit-Arrays dürfen höchstens 128 Bits enthalten.")
            children = node.elts
        elif isinstance(node, ast.Subscript):
            children = [node.value]
            if isinstance(node.slice, ast.Slice):
                children += [v for v in (node.slice.lower, node.slice.upper, node.slice.step) if v is not None]
            else:
                children.append(node.slice)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTION_ARITY
              and not node.keywords and len(node.args) == FUNCTION_ARITY[node.func.id]):
            children = node.args
        else:
            self._error(node, "nicht erlaubter Ausdruck; nur ganze Zahlen, Bit-Arrays und freigegebene Operatoren/Funktionen verwenden.")
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
                self._emit("assign", (self._assignment_target(node.targets[0]), self._expr(node.value)), node)
            elif isinstance(node, ast.AugAssign) and type(node.op) in BINOPS:
                target = self._assignment_target(node.target)
                left = ast.copy_location(ast.Name(id=target, ctx=ast.Load()), node.target) if isinstance(target, str) else target
                expr = ast.copy_location(ast.BinOp(left=left,
                                                  op=node.op, right=node.value), node)
                self._emit("assign", (target, self._expr(expr)), node)
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

        def scalar(result, node):
            if type(result) not in (int, bool):
                self._error(node, "ganze Zahl erforderlich; Bit-Arrays mit pack(a) umwandeln.")
            return int(result)

        def array(result, node):
            if not isinstance(result, list):
                self._error(node, "Bit-Array erforderlich; Zahlen mit bits(n, breite) umwandeln.")
            return result

        def bit(result, node):
            result = scalar(result, node)
            if result not in (0, 1):
                self._error(node, "Bit-Array erlaubt nur 0 und 1.")
            return result

        def index(items, result, node):
            result = scalar(result, node)
            if not 0 <= result < len(items):
                self._error(node, f"Arrayindex {result} ausserhalb 0…{len(items) - 1}.")
            return result

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
                if isinstance(node.op, ast.Add) and isinstance(a, list) and isinstance(b, list):
                    if len(a) + len(b) > MAX_ARRAY_BITS:
                        self._error(node, "Bit-Arrays dürfen höchstens 128 Bits enthalten.")
                    result = a + b
                elif isinstance(node.op, ast.Mult) and (isinstance(a, list) or isinstance(b, list)):
                    items, count = (a, b) if isinstance(a, list) else (b, a)
                    count = scalar(count, node)
                    if count < 0 or len(items) * count > MAX_ARRAY_BITS:
                        self._error(node, "Arraywiederholung braucht eine nichtnegative Anzahl und höchstens 128 Bits.")
                    result = items * count if items else []
                else:
                    a, b = scalar(a, node), scalar(b, node)
                    if type(node.op) in (ast.Pow, ast.LShift, ast.RShift) and not 0 <= b <= 32:
                        self._error(node, "Exponent/Schiebeweite muss zwischen 0 und 32 liegen.")
                    result = BINOPS[type(node.op)](a, b)
            elif isinstance(node, ast.UnaryOp):
                result = {ast.USub: operator.neg, ast.UAdd: operator.pos,
                          ast.Not: operator.not_, ast.Invert: operator.invert}[type(node.op)](scalar(value(node.operand), node.operand))
            elif isinstance(node, ast.BoolOp):
                result = bool(scalar(value(node.values[0]), node.values[0]))
                for child in node.values[1:]:
                    if isinstance(node.op, ast.And): result = result and bool(scalar(value(child), child))
                    else: result = result or bool(scalar(value(child), child))
            elif isinstance(node, ast.Compare):
                a, result = scalar(value(node.left), node.left), True
                for op, child in zip(node.ops, node.comparators):
                    b = scalar(value(child), child)
                    if not CMP[type(op)](a, b):
                        result = False
                        break
                    a = b
            elif isinstance(node, ast.IfExp):
                result = value(node.body) if scalar(value(node.test), node.test) else value(node.orelse)
            elif isinstance(node, ast.List):
                result = [bit(value(child), child) for child in node.elts]
            elif isinstance(node, ast.Subscript):
                items = array(value(node.value), node.value)
                if isinstance(node.slice, ast.Slice):
                    parts = [scalar(value(v), v) if v is not None else None
                             for v in (node.slice.lower, node.slice.upper, node.slice.step)]
                    if parts[2] == 0:
                        self._error(node, "Array-Schritt darf nicht 0 sein.")
                    result = items[slice(*parts)]
                else:
                    result = items[index(items, value(node.slice), node.slice)]
            else:  # Calls have been restricted during validation.
                args = [value(a) for a in node.args]
                name = node.func.id
                if name == "bits":
                    number, width = [scalar(a, node) for a in args]
                    if not 1 <= width <= MAX_ARRAY_BITS:
                        self._error(node, "Bitbreite für bits muss zwischen 1 und 128 liegen.")
                    result = [(number >> i) & 1 for i in range(width)]
                elif name in ("pack", "len"):
                    items = array(args[0], node)
                    result = len(items) if name == "len" else sum(b << i for i, b in enumerate(items))
                else:
                    result = FUNCTIONS[name](*(scalar(a, node) for a in args))
            if isinstance(result, list):
                # Charge bounded bulk work too, including copies/slices/conversions.
                for _ in result:
                    budget.tick(node)
                return result
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
                    result = value(arg[1])
                    if isinstance(arg[0], str):
                        env[arg[0]] = result
                    else:
                        target = arg[0]
                        items = array(value(target.value), target.value)
                        i = index(items, value(target.slice), target.slice)
                        items[i] = bit(result, target)
                elif op == "return":
                    return [scalar(value(v), v) for v in arg]
                elif op == "test":
                    if not scalar(value(arg[0]), arg[0]): pc = arg[1]
                elif op == "jump":
                    pc = arg
                elif op == "iteration":
                    budget.iteration(node)
                elif op == "range":
                    args = [scalar(value(a), a) for a in arg[1]]
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

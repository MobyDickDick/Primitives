"""Versioned, bounded integer/bit-array programs. ASTs are interpreted, never executed."""
import ast
import copy
import io
import keyword
import operator
import re
import tokenize
from .ports import decode, encode, interface
from .limits import MAX_BITS


DEFAULT_LIMITS = {"steps": 10000, "iterations": 10000, "total_steps": 1000000}
MAX_LIMITS = {"steps": 100000, "iterations": 100000, "total_steps": 5000000}
MAX_ARRAY_BITS = MAX_BITS


def exact_log2(value):
    """Integer logarithm for positive powers of two, without float rounding."""
    if type(value) is not int or value <= 0 or value & (value - 1):
        raise ValueError("LOG2 braucht eine positive Zweierpotenz.")
    return value.bit_length() - 1


FUNCTIONS = {"abs": abs, "min": min, "max": max, "div": operator.floordiv,
             "mod": operator.mod, "xor": operator.xor, "LOG2": exact_log2}
FUNCTION_ARITY = {name: 1 if name in ("abs", "LOG2") else 2 for name in FUNCTIONS}
FUNCTION_ARITY.update(bits=2, pack=1, len=1)
BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
          ast.BitAnd: operator.and_, ast.BitOr: operator.or_, ast.BitXor: operator.xor,
          ast.LShift: operator.lshift, ast.RShift: operator.rshift}
CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
       ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}
RESERVED = set(FUNCTION_ARITY) | {"range"}
JUMPS = {"goto", "jump_if", "jump_zero", "jump_nonzero", "jump_negative"}
MAX_CALL_DEPTH = 32


def template_source(source):
    """Lower f<n>(a,b) to f(n, a,b), preserving all source coordinates.

    Tokenization keeps comments/strings and ordinary comparisons untouched.
    Right-to-left rewriting also handles nested template calls.
    """
    tokens = [t for t in tokenize.generate_tokens(io.StringIO(source).readline)
              if t.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                                tokenize.DEDENT, tokenize.COMMENT, tokenize.ENDMARKER)]
    names = {tokens[i + 1].string for i, token in enumerate(tokens[:-1]) if token.string == "def"}
    spellings = [t.string for t in tokens]
    offsets, offset = [], 0
    for line in source.splitlines(keepends=True):
        offsets.append(offset)
        offset += len(line)
    chars = list(source)

    def replace(index, value):
        token = tokens[index]
        chars[offsets[token.start[0] - 1] + token.start[1]] = value
        spellings[index] = value.strip()

    for i in range(len(tokens) - 2, -1, -1):
        if tokens[i].type != tokenize.NAME or spellings[i] not in names or spellings[i + 1] != "<":
            continue
        depth = 0
        for j in range(i + 2, len(tokens) - 1):
            text = spellings[j]
            if text == ">" and depth == 0 and spellings[j + 1] == "(":
                replace(i + 1, "(")
                replace(j, ",")
                replace(j + 1, " ")
                break
            if text in ("(", "[", "{"):
                depth += 1
            elif text in (")", "]", "}"):
                depth -= 1
                if depth < 0:
                    break
            elif depth == 0 and text in (":", ";", "return", "def", "="):
                break
    return "".join(chars)


def identifier(name):
    return (isinstance(name, str) and re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,31}", name)
            and not keyword.iskeyword(name) and name not in RESERVED | JUMPS | {"label"})


def specialize_interface(spec, parameters):
    """Evaluate bounded integer width expressions without eval or host calls."""
    def width(text):
        if type(text) is int:
            return text
        if not isinstance(text, str) or not 1 <= len(text) <= 128:
            raise ValueError("Template-Breite braucht eine ganze Zahl oder einen Parameterausdruck.")
        try:
            tree = ast.parse(text, mode="eval")
            if sum(1 for _ in ast.walk(tree)) > 64:
                raise ValueError("Template-Breitenausdruck zu komplex.")

            def visit(node):
                if isinstance(node, ast.Constant) and type(node.value) is int:
                    result = node.value
                elif isinstance(node, ast.Name) and node.id in parameters:
                    result = parameters[node.id]
                elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                      and node.func.id in ("LOG2", "min", "max")
                      and len(node.args) == (1 if node.func.id == "LOG2" else 2) and not node.keywords):
                    result = FUNCTIONS[node.func.id](*(visit(arg) for arg in node.args))
                elif isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.Pow):
                    a, b = visit(node.left), visit(node.right)
                    if isinstance(node.op, ast.Pow) and not 0 <= b <= 16:
                        raise ValueError("Template-Exponent muss zwischen 0 und 16 liegen.")
                    result = BINOPS[type(node.op)](a, b)
                else:
                    raise ValueError("Template-Breite: nur Parameter, ganze Zahlen, +, -, *, //, %, **, LOG2, min und max erlaubt.")
                if abs(result) > 2**32:
                    raise ValueError("Template-Breitenergebnis zu gross.")
                return result

            return visit(tree.body)
        except (SyntaxError, ArithmeticError, RecursionError) as exc:
            raise ValueError(f"Ungültige Template-Breite {text!r}.") from exc

    if not isinstance(spec, dict):
        raise ValueError("Template braucht eine Schnittstelle.")
    concrete = copy.deepcopy(spec)
    for side in ("inputs", "outputs"):
        if not isinstance(concrete.get(side), list):
            raise ValueError("Template braucht inputs und outputs.")
        for port in concrete[side]:
            if not isinstance(port, dict):
                raise ValueError("Jeder Template-Port muss ein Objekt sein.")
            port["bits"] = width(port.get("bits"))
    return interface(concrete)


class ProgramCancelled(ValueError):
    pass


def program_spec(spec):
    if not isinstance(spec, dict) or type(spec.get("version")) is not int or spec["version"] not in (1, 2):
        raise ValueError("Programm braucht Sprachversion 1 oder 2.")
    version = spec["version"]
    extra = {"parameters", "interface", "conditions"} if version == 2 else set()
    if set(spec) - ({"version", "source", "limits"} | extra):
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
    result = {"version": version, "source": source, "limits": limits}
    if version == 2:
        parameters = spec.get("parameters")
        if (not isinstance(parameters, dict) or len(parameters) > 16
                or any(not identifier(k) or k == "is_power_of_two" or type(v) is not int or not 0 <= v <= MAX_BITS for k, v in parameters.items())):
            raise ValueError(f"Template braucht parameters: höchstens 16 benannte ganzzahlige Parameter von 0 bis {MAX_BITS}.")
        if "conditions" in spec:
            from .templates import conditions
            result["conditions"] = conditions(spec["conditions"], set(parameters), parameters)
        specialize_interface(spec.get("interface"), parameters)
        result.update(parameters=dict(parameters), interface=copy.deepcopy(spec["interface"]))
    return result


class Program:
    """Bounded Python-style assignments, bit arrays, return, if/else and loops."""
    def __init__(self, spec, ports=None):
        self.spec = program_spec(spec)
        self.parameters = self.spec.get("parameters", {})
        self.ports = (specialize_interface(self.spec["interface"], self.parameters)
                      if self.spec["version"] == 2 else interface(ports))
        if self.spec["version"] == 2 and ports is not None:
            if specialize_interface(ports, self.parameters) != self.ports:
                raise ValueError("Template und konkrete Schnittstelle stimmen nicht überein.")
        self.inputs = {p["name"] for p in self.ports["inputs"]} | set(self.parameters)
        if set(self.parameters) & {p["name"] for side in ("inputs", "outputs") for p in self.ports[side]}:
            raise ValueError("Template-Parameter und Ports brauchen verschiedene Namen.")
        if RESERVED & {p["name"] for side in ("inputs", "outputs") for p in self.ports[side]}:
            raise ValueError("range, abs, min, max, div, mod, xor, LOG2, bits, pack und len sind im Programmmodus reserviert.")
        try:
            source = template_source(self.spec["source"]) if self.spec["version"] == 2 else self.spec["source"]
            tree = ast.parse(source)
        except (SyntaxError, RecursionError, ValueError, tokenize.TokenError, IndentationError) as exc:
            raise ValueError(f"Programm: Zeile {getattr(exc, 'lineno', 1)}, Spalte {getattr(exc, 'offset', 1)}: ungültige Syntax.") from exc
        if sum(1 for _ in ast.walk(tree)) > 2000:
            raise ValueError("Programm ist zu komplex (höchstens 2000 Syntaxknoten).")
        self.functions = {}
        definitions = [n for n in tree.body if isinstance(n, ast.FunctionDef)] if self.spec["version"] == 2 else []
        if len(definitions) > 16:
            raise ValueError("Höchstens 16 Template-Funktionen erlaubt.")
        for node in definitions:
            args = node.args
            names = [a.arg for a in args.args]
            if (not identifier(node.name) or node.name in self.functions or node.name in self.inputs
                    or node.name in {p["name"] for p in self.ports["outputs"]}
                    or node.decorator_list or node.returns or getattr(node, "type_params", [])
                    or args.posonlyargs or args.vararg or args.kwarg or args.kwonlyargs or args.defaults
                    or not 1 <= len(names) <= 16 or len(set(names)) != len(names)
                    or any(not identifier(n) for n in names) or any(a.annotation for a in args.args)):
                self._error(node, "Funktion braucht einen eindeutigen Namen und 1–16 einfache Argumente ohne Annotationen oder Vorgaben.")
            child = object.__new__(Program)
            child.spec, child.ports = self.spec, self.ports
            child.parameters, child.functions = self.parameters, self.functions
            child.arguments = names
            child.inputs = set(names) | set(self.parameters)
            self.functions[node.name] = child
        if set(self.functions) & {a for child in self.functions.values() for a in child.arguments}:
            raise ValueError("Funktionsargumente dürfen keine Funktionsnamen verdecken.")
        # Curried notation add(n)(a,b) is syntax sugar for add(n,a,b).
        class Calls(ast.NodeTransformer):
            def visit_Call(visitor, node):
                node = visitor.generic_visit(node)
                if (isinstance(node.func, ast.Call) and isinstance(node.func.func, ast.Name)
                        and node.func.func.id in self.functions and not node.func.keywords):
                    return ast.copy_location(ast.Call(func=node.func.func,
                        args=node.func.args + node.args, keywords=node.keywords), node)
                return node
        tree = Calls().visit(tree)
        for node in definitions:
            self.functions[node.name]._compile_body(ast.Module(body=node.body, type_ignores=[]), 1)
        self._compile_body(ast.Module(body=[n for n in tree.body if n not in definitions], type_ignores=[]),
                           len(self.ports["outputs"]))

    def _compile_body(self, tree, return_count):
        self.return_count = return_count
        self.locals = set()
        self.code = []
        self.labels, self.references = {}, []
        self._compile(tree.body, 0)
        for index, target, scope, node in self.references:
            if target not in self.labels:
                self._error(node, f"unbekanntes Label {target}.")
            destination, target_scope = self.labels[target]
            if scope[:len(target_scope)] != target_scope:
                self._error(node, "Sprung darf keinen Block betreten; Ziel muss im selben oder einem umgebenden Block liegen.")
            self.code[index][1][1] = destination
        if not any(op == "return" for op, _, _ in self.code):
            raise ValueError("Programm braucht eine return-Anweisung.")
        allowed = self.inputs | self.locals
        commands = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                    and node.id not in allowed | RESERVED and id(node) not in commands):
                self._error(node, f"unbekannte Variable {node.id}.")

    @staticmethod
    def _error(node, message):
        raise ValueError(f"Zeile {getattr(node, 'lineno', 1)}, Spalte {getattr(node, 'col_offset', 0) + 1}: {message}")

    def _target(self, node):
        if (not isinstance(node, ast.Name) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,31}", node.id)
                or keyword.iskeyword(node.id) or node.id in RESERVED | self.inputs | set(self.functions)):
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
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in self.functions
              and not node.keywords and len(node.args) == len(self.functions[node.func.id].arguments)):
            children = node.args
        else:
            self._error(node, "nicht erlaubter Ausdruck; nur ganze Zahlen, Bit-Arrays und freigegebene Operatoren/Funktionen verwenden.")
        for child in children:
            self._expr(child, depth + 1)
        return node

    def _emit(self, op, arg, node):
        self.code.append((op, arg, node))
        return len(self.code) - 1

    def _compile(self, statements, depth, scope=()):
        if depth > 16:
            self._error(statements[0], "höchstens 16 verschachtelte Kontrollstrukturen erlaubt.")
        for node in statements:
            if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name) and node.value.func.id in JUMPS | {"label"}):
                call, name = node.value, node.value.func.id
                arity = 1 if name in ("label", "goto") else 2
                if (call.keywords or len(call.args) != arity or not isinstance(call.args[-1], ast.Constant)
                        or not isinstance(call.args[-1].value, str)
                        or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,31}", call.args[-1].value)):
                    self._error(node, 'Sprungsyntax: label("ziel"), goto("ziel") oder jump_if(bedingung, "ziel"); Label braucht einen Bezeichner.')
                target = call.args[-1].value
                if name == "label":
                    if target in self.labels:
                        self._error(node, f"doppeltes Label {target}.")
                    self.labels[target] = (len(self.code), scope)
                    self._emit("label", target, node)
                else:
                    condition = self._expr(call.args[0]) if arity == 2 else None
                    index = self._emit("branch", [condition, None, name], node)
                    self.references.append((index, target, scope, node))
            elif isinstance(node, ast.Assign) and len(node.targets) == 1:
                self._emit("assign", (self._assignment_target(node.targets[0]), self._expr(node.value)), node)
            elif isinstance(node, ast.AugAssign) and type(node.op) in BINOPS:
                target = self._assignment_target(node.target)
                left = ast.copy_location(ast.Name(id=target, ctx=ast.Load()), node.target) if isinstance(target, str) else target
                expr = ast.copy_location(ast.BinOp(left=left,
                                                  op=node.op, right=node.value), node)
                self._emit("assign", (target, self._expr(expr)), node)
            elif isinstance(node, ast.Return) and node.value is not None:
                values = node.value.elts if isinstance(node.value, ast.Tuple) else [node.value]
                if len(values) != self.return_count:
                    self._error(node, "return braucht genau einen Wert je Ergebnisport, in Portreihenfolge.")
                self._emit("return", [self._expr(v) for v in values], node)
            elif isinstance(node, ast.Assert) and node.msg is None and self.spec["version"] == 2:
                self._emit("require", self._expr(node.test), node)
            elif isinstance(node, ast.If):
                branch = self._emit("test", [self._expr(node.test), None], node)
                self._compile(node.body, depth + 1, scope + ((node.lineno, "body"),))
                end = self._emit("jump", None, node)
                self.code[branch][1][1] = len(self.code)
                self._compile(node.orelse, depth + 1, scope + ((node.lineno, "else"),))
                self.code[end] = ("jump", len(self.code), node)
            elif isinstance(node, ast.While) and not node.orelse:
                start = self._emit("test", [self._expr(node.test), None], node)
                self._emit("iteration", None, node)
                self._compile(node.body, depth + 1, scope + ((node.lineno, "body"),))
                self._emit("jump", start, node)
                self.code[start][1][1] = len(self.code)
            elif (isinstance(node, ast.For) and not node.orelse and isinstance(node.iter, ast.Call)
                  and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range"
                  and not node.iter.keywords and 1 <= len(node.iter.args) <= 3):
                name = self._target(node.target)
                init = self._emit("range", [name, [self._expr(a) for a in node.iter.args], None], node)
                start = self._emit("next", [name, init, None], node)
                self._compile(node.body, depth + 1, scope + ((node.lineno, "body"),))
                self._emit("jump", start, node)
                self.code[init][1][2] = start
                self.code[start][1][2] = len(self.code)
            else:
                self._error(node, "nicht erlaubte Anweisung. Zuweisung, return, if/else, while oder for … in range(…) verwenden.")

    def budget(self, cancel_event=None):
        return Budget(self.spec["limits"], cancel_event)

    def run(self, x, budget=None):
        execution = self._execute(x, budget)
        while True:
            try:
                next(execution)
            except StopIteration as end:
                return end.value

    def debug(self, x):
        return Execution(self, x)

    def _execute(self, x, budget=None, *, env=None, depth=0):
        if type(x) is not int or not 0 <= x < 2 ** sum(p["bits"] for p in self.ports["inputs"]):
            raise ValueError("Testeingabe x muss eine gültige unsigned Eingangsbitkombination sein.")
        budget = budget if budget is not None else self.budget()
        if env is None:
            budget.start()
            env = {**self.parameters, **{p["name"]: decode(x, p) for p in self.ports["inputs"]}}
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
                    if type(node.op) in (ast.Pow, ast.LShift, ast.RShift) and not 0 <= b <= MAX_BITS:
                        self._error(node, f"Exponent/Schiebeweite muss zwischen 0 und {MAX_BITS} liegen.")
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
                if name in self.functions:
                    if depth >= MAX_CALL_DEPTH:
                        self._error(node, "Aufruftiefe überschritten (höchstens 32 Funktionsaufrufe).")
                    function = self.functions[name]
                    local = {**self.parameters, **dict(zip(function.arguments, (scalar(a, node) for a in args)))}
                    execution = function._execute(x, budget, env=local, depth=depth + 1)
                    while True:
                        try:
                            next(execution)
                        except StopIteration as end:
                            result = end.value[0]
                            break
                elif name == "bits":
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
                yield pc, env
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
                elif op == "require":
                    if not scalar(value(arg), arg):
                        self._error(node, "Funktionsbedingung nicht erfüllt: " + self.spec["source"].splitlines()[node.lineno - 1].strip())
                elif op == "test":
                    if not scalar(value(arg[0]), arg[0]): pc = arg[1]
                elif op == "jump":
                    pc = arg
                elif op == "branch":
                    condition = scalar(value(arg[0]), arg[0]) if arg[0] is not None else 1
                    taken = condition == 0 if arg[2] == "jump_zero" else condition < 0 if arg[2] == "jump_negative" else condition != 0
                    if taken:
                        if arg[1] <= pc - 1:
                            budget.iteration(node)
                        pc = arg[1]
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


class Execution:
    """One bounded execution, shared by instruction stepping and normal runs."""
    def __init__(self, program, x):
        self.program, self.x = program, x
        self.reset()

    def reset(self):
        self.budget = self.program.budget()
        self.iterator = self.program._execute(self.x, self.budget)
        self.status, self.result, self.error = "paused", None, None
        self.pc, self.env = next(self.iterator)
        self.instructions = 0
        return self.snapshot()

    def step(self, count=1):
        if type(count) is not int or not 1 <= count <= 100:
            raise ValueError("Debugschritte pro Aufruf: 1–100.")
        if self.status in ("done", "failed"):
            return self.snapshot()
        self.status = "paused"
        for _ in range(count):
            try:
                self.instructions += 1
                self.pc, self.env = next(self.iterator)
            except StopIteration as end:
                self.result = end.value
                try:
                    self.encoded = {p["name"]: encode(v, p, self.x)
                                    for p, v in zip(self.program.ports["outputs"], self.result)}
                    self.status = "done"
                except ValueError as exc:
                    self.status, self.error = "failed", str(exc)
                break
            except ValueError as exc:
                self.status, self.error = "failed", str(exc)
                break
        return self.snapshot()

    def stop(self):
        if self.status == "paused":
            self.status = "stopped"
        return self.snapshot()

    def snapshot(self):
        op, _, node = self.program.code[self.pc]
        # Copy arrays: later mutations must never change an earlier snapshot.
        return {"status": self.status, "x": self.x, "pc": self.pc,
                "line": node.lineno, "operation": op,
                "source": self.program.spec["source"].splitlines()[node.lineno - 1],
                "variables": {k: copy.deepcopy(v) if isinstance(v, list) else str(v) for k, v in self.env.items()},
                "result": None if self.result is None else [str(v) for v in self.result],
                "outputs": getattr(self, "encoded", None) if self.status == "done" else None,
                "error": self.error, "instructions": self.instructions,
                "steps": self.budget.steps, "iterations": self.budget.iterations}


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

"""Abstract templates and bounded, side-effect-free specialization constraints."""
import ast
import copy
import operator
import tokenize

from .dataset import validate_description
from .ports import interface
from .limits import MAX_BITS
from .program import Program, exact_log2, identifier, program_spec, template_source


OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
       ast.BitAnd: operator.and_, ast.BitOr: operator.or_, ast.BitXor: operator.xor}
CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
       ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}


class Condition:
    def __init__(self, source, names):
        if not isinstance(source, str) or not 1 <= len(source) <= 256:
            raise ValueError("Template-Bedingung braucht 1–256 Zeichen.")
        try:
            self.root = ast.parse(source, mode="eval").body
        except (SyntaxError, RecursionError) as exc:
            raise ValueError("Ungültige Template-Bedingung.") from exc
        self.source = source
        if sum(1 for _ in ast.walk(self.root)) > 128:
            raise ValueError("Template-Bedingung zu komplex.")

        def validate(node):
            if isinstance(node, ast.Constant) and type(node.value) in (int, bool) and abs(node.value) <= 2**128:
                return
            if isinstance(node, ast.Name) and node.id in names:
                return
            if isinstance(node, ast.BinOp) and type(node.op) in OPS:
                children = [node.left, node.right]
            elif isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
                children = node.values
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Not, ast.USub, ast.UAdd)):
                children = [node.operand]
            elif isinstance(node, ast.Compare) and all(type(op) in CMP for op in node.ops):
                children = [node.left, *node.comparators]
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                  and node.func.id in ("is_power_of_two", "LOG2") and len(node.args) == 1 and not node.keywords):
                children = node.args
            else:
                raise ValueError("Template-Bedingung: nur Parameter, Ganzzahloperatoren, Vergleiche, and/or/not, LOG2(n) und is_power_of_two(n) erlaubt.")
            for child in children:
                validate(child)
        validate(self.root)

    def check(self, parameters):
        def visit(node):
            if isinstance(node, ast.Constant):
                return node.value
            if isinstance(node, ast.Name):
                return parameters[node.id]
            if isinstance(node, ast.BinOp):
                a, b = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Pow) and not 0 <= b <= MAX_BITS:
                    raise ValueError(f"Bedingungsexponent muss zwischen 0 und {MAX_BITS} liegen.")
                result = OPS[type(node.op)](a, b)
                if abs(result) > 2**128:
                    raise ValueError("Zwischenwert der Template-Bedingung zu gross.")
                return result
            if isinstance(node, ast.BoolOp):
                return all(visit(n) for n in node.values) if isinstance(node.op, ast.And) else any(visit(n) for n in node.values)
            if isinstance(node, ast.UnaryOp):
                return {ast.Not: operator.not_, ast.USub: operator.neg, ast.UAdd: operator.pos}[type(node.op)](visit(node.operand))
            if isinstance(node, ast.Compare):
                left = visit(node.left)
                for op, child in zip(node.ops, node.comparators):
                    right = visit(child)
                    if not CMP[type(op)](left, right):
                        return False
                    left = right
                return True
            value = visit(node.args[0])
            if node.func.id == "LOG2":
                return exact_log2(value)
            return value > 0 and (value & (value - 1)) == 0
        try:
            satisfied = visit(self.root)
        except ArithmeticError as exc:
            raise ValueError(f"Template-Bedingung kann nicht ausgewertet werden: {self.source}.") from exc
        if not satisfied:
            values = ", ".join(f"{k}={v}" for k, v in parameters.items())
            raise ValueError(f"Template-Bedingung nicht erfüllt: {self.source} ({values}).")


def conditions(sources, names, parameters=None):
    if not isinstance(sources, list) or len(sources) > 16:
        raise ValueError("Höchstens 16 Template-Bedingungen erlaubt.")
    for source in sources:
        condition = Condition(source, names)
        if parameters is not None:
            condition.check(parameters)
    return list(sources)


class Template:
    """A saved definition has parameter names, but no concrete parameter values."""
    def __init__(self, document):
        if not isinstance(document, dict) or document.get("schema") != 1 or document.get("kind") != "template":
            raise ValueError("Abstraktes Template braucht schema 1 und kind template.")
        if set(document) - {"schema", "kind", "name", "description", "parameters", "interface", "source", "limits", "conditions"}:
            raise ValueError("Unbekannte Felder im abstrakten Template.")
        name = document.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError("Template braucht einen Namen mit 1–120 Zeichen.")
        names = document.get("parameters")
        if (not isinstance(names, list) or len(names) > 16 or any(not identifier(n) for n in names)
                or len(set(names)) != len(names) or "is_power_of_two" in names):
            raise ValueError("Template braucht höchstens 16 eindeutige Parameternamen.")
        base = program_spec({"version": 1, "source": document.get("source"), "limits": document.get("limits", {})})
        try:
            tree = ast.parse(template_source(base["source"]))
        except (SyntaxError, ValueError, RecursionError, tokenize.TokenError) as exc:
            raise ValueError("Ungültiger Template-Quelltext.") from exc
        if sum(1 for _ in ast.walk(tree)) > 2000:
            raise ValueError("Template-Quelltext zu komplex.")
        raw = copy.deepcopy(document.get("interface"))
        if not isinstance(raw, dict):
            raise ValueError("Template braucht eine symbolische Schnittstelle.")
        dummy = copy.deepcopy(raw)
        for side in ("inputs", "outputs"):
            if not isinstance(dummy.get(side), list):
                raise ValueError("Template braucht inputs und outputs.")
            for port in dummy[side]:
                if not isinstance(port, dict):
                    raise ValueError("Template-Port muss ein Objekt sein.")
                width = port.get("bits")
                if type(width) is not int and (not isinstance(width, str) or not 1 <= len(width) <= 128):
                    raise ValueError("Ungültige symbolische Portbreite.")
                if isinstance(width, str):
                    # Width grammar is a subset of the validated condition grammar.
                    parsed = Condition(width, set(names))
                    if any(not isinstance(n, (ast.Expression, ast.Constant, ast.Name, ast.Load, ast.BinOp,
                                              ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.Pow, ast.Call))
                           or isinstance(n, ast.Call) and n.func.id != "LOG2"
                           for n in ast.walk(parsed.root)):
                        raise ValueError("Ungültiger Operator in einer symbolischen Portbreite.")
                port["bits"] = 1
                port.pop("offset", None)
        normalized = interface(dummy)
        if set(names) & {p["name"] for side in ("inputs", "outputs") for p in normalized[side]}:
            raise ValueError("Template-Parameter und Ports brauchen verschiedene Namen.")
        self.document = {"schema": 1, "kind": "template", "name": name.strip(),
                         "description": validate_description(document.get("description", "")),
                         "parameters": list(names), "interface": raw, "source": base["source"],
                         "limits": base["limits"], "conditions": conditions(document.get("conditions", []), set(names))}

    def to_dict(self):
        return copy.deepcopy(self.document)

    def instantiate(self, parameters):
        if not isinstance(parameters, dict) or set(parameters) != set(self.document["parameters"]):
            raise ValueError("Konkretisierung braucht genau die deklarierten Template-Parameter.")
        return Program({"version": 2, "parameters": parameters,
                        **{k: self.document[k] for k in ("source", "limits", "interface", "conditions")}})

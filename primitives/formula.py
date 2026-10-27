"""Bounded arithmetic result definitions, without host-code execution."""
import ast
from .limits import MAX_BITS


def parse_formula(source, result_name="c"):
    if not isinstance(source, str) or not source.strip() or len(source) > 4000:
        raise ValueError("Formel braucht 1–4000 Zeichen.")
    # Only top-level commas separate results; commas in mod(a,b) remain intact.
    parts, start, depth = [], 0, 0
    for i, char in enumerate(source):
        if char == "(": depth += 1
        elif char == ")": depth -= 1
        elif depth == 0 and char in ",;\n":
            if source[start:i].strip(): parts.append(source[start:i].strip())
            start = i + 1
    if source[start:].strip(): parts.append(source[start:].strip())
    if depth != 0 or not 1 <= len(parts) <= MAX_BITS:
        raise ValueError(f"Formel braucht ausgeglichene Klammern und 1–{MAX_BITS} Ergebnisdefinitionen.")
    expressions = {}
    for part in parts:
        try:
            tree = ast.parse(part.replace("^", "**"), mode="exec")
        except (SyntaxError, RecursionError) as exc:
            raise ValueError("Ungültige Formel. Beispiel: c = mod(a+b,2^4); e = div(a+b,2^4)") from exc
        if len(tree.body) != 1:
            raise ValueError("Pro Ergebnis genau eine Formel verwenden.")
        node = tree.body[0]
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name, expression = node.targets[0].id, part.split("=", 1)[1].strip()
        elif isinstance(node, ast.Expr) and len(parts) == 1:
            name, expression = result_name, part
        else:
            raise ValueError("Erlaubt sind ein Ausdruck oder benannte Ergebnisse wie c = a+b.")
        if name in expressions:
            raise ValueError(f"Ergebnis {name} wurde mehrfach definiert.")
        if not expression or len(expression) > 1000:
            raise ValueError(f"Ergebnis {name}: Ausdruck braucht 1–1000 Zeichen.")
        expressions[name] = expression
    return expressions


def to_formula(expressions):
    """Translate historical Python XOR into an unambiguous math formula."""
    from .dataset import Expression

    class ConvertXor(ast.NodeTransformer):
        def visit_BinOp(self, node):
            self.generic_visit(node)
            if isinstance(node.op, ast.BitXor):
                return ast.Call(func=ast.Name(id="xor", ctx=ast.Load()), args=[node.left, node.right], keywords=[])
            return node

    if not isinstance(expressions, dict) or not 1 <= len(expressions) <= MAX_BITS:
        raise ValueError(f"Ergebnisausdrücke müssen eine Zuordnung mit 1–{MAX_BITS} Einträgen sein.")
    return "\n".join(f"{name} = {ast.unparse(ConvertXor().visit(Expression(expr).root))}" for name, expr in expressions.items())


def python_expressions(source, result_name="c"):
    """Preserve meaning when moving a math formula to the historical port editor."""
    from .dataset import Expression

    class ConvertFunctions(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            operators = {"mod": ast.Mod, "div": ast.FloorDiv, "xor": ast.BitXor}
            if isinstance(node.func, ast.Name) and node.func.id in operators and len(node.args) == 2 and not node.keywords:
                return ast.BinOp(left=node.args[0], op=operators[node.func.id](), right=node.args[1])
            return node

    return {name: ast.unparse(ConvertFunctions().visit(Expression(expr, syntax="math").root))
            for name, expr in parse_formula(source, result_name).items()}

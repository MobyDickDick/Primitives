"""Reference definitions and concrete width variants, independent of NAND circuits."""
from itertools import product

from .ports import bounds, interface


OPERATIONS = {
    "ADD": {"operands": 2, "expression": "a+b", "defaults": [2, 2, 3]},
    "SUB": {"operands": 2, "expression": "a-b", "defaults": [2, 2, 2]},
    "MUL": {"operands": 2, "expression": "a*b", "defaults": [2, 2, 4]},
    "NOT": {"operands": 1, "expression": "~a", "defaults": [1, 1, 1]},
    "NAND": {"operands": 2, "expression": "~(a&b)", "defaults": [1, 1, 1]},
    "AND": {"operands": 2, "expression": "a&b", "defaults": [1, 1, 1]},
    "OR": {"operands": 2, "expression": "a|b", "defaults": [1, 1, 1]},
    "XOR": {"operands": 2, "expression": "a^b", "defaults": [1, 1, 1]},
    "NOR": {"operands": 2, "expression": "~(a|b)", "defaults": [1, 1, 1]},
    "XNOR": {"operands": 2, "expression": "~(a^b)", "defaults": [1, 1, 1]},
}

OPERATIONS.update({
    "DIV": {"operands": 2, "defaults": [3, 3, 3], "description": "Division gegen null gerundet; zusätzliche valid- und div0-Ausgänge."},
    "IsZero": {"operands": 1, "expression": "a == 0", "defaults": [3, 1, 1]},
    "IsNonZero": {"operands": 1, "expression": "a != 0", "defaults": [3, 1, 1]},
    "IsNegative": {"operands": 1, "expression": "a < 0", "defaults": [3, 1, 1]},
    **{name: {"operands": 2, "expression": f"a {symbol} b", "defaults": [2, 2, 1]}
       for name, symbol in (("EQ", "=="), ("NE", "!="), ("LT", "<"), ("LE", "<="), ("GT", ">"), ("GE", ">="))},
    "SHL": {"operands": 2, "defaults": [3, 2, 3], "description": "Links schieben im a-Wort; hohe Bits entfallen, ab a-Breite ist das Ergebnis null."},
    "SHR": {"operands": 2, "defaults": [3, 2, 3], "description": "Logisch rechts schieben, links mit Nullen auffüllen."},
    "SAR": {"operands": 2, "defaults": [3, 2, 3], "description": "Arithmetisch rechts schieben, Vorzeichenbit von a fortsetzen."},
    "INC": {"operands": 1, "expression": "a+1", "defaults": [3, 1, 3]},
    "DEC": {"operands": 1, "expression": "a-1", "defaults": [3, 1, 3]},
    "MUX": {"operands": 3, "expression": "b if select else a", "defaults": [2, 2, 2],
            "description": "select=0 wählt a, select=1 wählt b (zusätzlicher Ein-Bit-Eingang)."},
})

SHIFTS = {"SHL", "SHR", "SAR"}
PREDICATES = {"IsZero", "IsNonZero", "IsNegative", "EQ", "NE", "LT", "LE", "GT", "GE"}
FLAG_OPERATIONS = {"ADD", "SUB", "MUL", "INC", "DEC"}
PARAMETERS = {"a_bits", "b_bits", "result_bits", "signed", "overflow", "flag", "shift"}
for _name, _definition in OPERATIONS.items():
    _definition["flag"] = _name in FLAG_OPERATIONS
    _definition["predicate"] = _name in PREDICATES
    _definition["shift"] = _name in SHIFTS
    _definition["default_signed"] = _name in {"IsNegative", "SAR", "DIV"}


def variant(name, a_bits=None, b_bits=None, result_bits=None, signed=False, overflow="wrap", flag=False, shift=None):
    if name not in OPERATIONS:
        raise ValueError("Unbekannte Operationsdefinition.")
    definition = OPERATIONS[name]
    a_bits, b_bits, result_bits = [d if v is None else v for v, d in
                                  zip((a_bits, b_bits, result_bits), definition["defaults"])]
    if any(type(w) is not int or not 1 <= w <= 32 for w in (a_bits, b_bits, result_bits)):
        raise ValueError("Operand- und Ergebnisbreiten müssen zwischen 1 und 32 liegen.")
    if type(signed) is not bool or type(flag) is not bool or overflow not in ("wrap", "error"):
        raise ValueError("signed/flag müssen boolesch und overflow wrap oder error sein.")
    if shift is not None and (name not in SHIFTS or type(shift) is not int or not 0 <= shift <= 32):
        raise ValueError("Feste Schiebeweite ist nur für SHL/SHR/SAR erlaubt und muss zwischen 0 und 32 liegen.")
    if flag and name not in FLAG_OPERATIONS:
        raise ValueError("Statusausgang ist für ADD, SUB, MUL, INC und DEC verfügbar.")
    if name in PREDICATES and result_bits != 1:
        raise ValueError("Prädikate und Vergleiche brauchen genau ein Ergebnisbit.")
    ports = {"inputs": [{"name": "a", "bits": a_bits, "signed": signed}],
             "outputs": [{"name": "c", "bits": result_bits, "signed": signed and name not in PREDICATES, "overflow": overflow}]}
    if definition["operands"] >= 2 and shift is None:
        ports["inputs"].append({"name": "b", "bits": b_bits, "signed": signed and name not in SHIFTS})
    if name == "MUX":
        ports["inputs"].append({"name": "select", "bits": 1})
    # Bitwise NOT/NAND/NOR/XNOR invert exactly the result width, even in error mode.
    expr = definition.get("expression")
    if name == "DIV":
        # Exact integer arithmetic: Python // on negative values rounds differently.
        expr = "((abs(a)//abs(b)) * (-1 if (a < 0) != (b < 0) else 1)) if b else 0"
    if name in SHIFTS:
        amount = "b" if shift is None else str(shift)
        word = f"(a & {(1 << a_bits) - 1})"
        if name == "SHL":
            expr = f"(({word} << {amount}) & {(1 << a_bits) - 1}) if {amount} < {a_bits} else 0"
        elif name == "SHR":
            expr = f"({word} >> {amount}) if {amount} < {a_bits} else 0"
        else:
            signed_word = f"(({word} ^ {1 << (a_bits - 1)}) - {1 << (a_bits - 1)})"
            expr = f"{signed_word} >> min({amount}, {a_bits})"
        if signed and name in {"SHL", "SHR"}:
            expr = f"((({expr}) ^ {1 << (a_bits - 1)}) - {1 << (a_bits - 1)})"
    if name in ("NOT", "NAND", "NOR", "XNOR"):
        expr = f"({expr}) & {(1 << result_bits) - 1}"
        if signed:
            expr = f"(({expr}) ^ {1 << (result_bits - 1)}) - {1 << (result_bits - 1)}"
    expressions = {"c": expr}
    if name == "DIV":
        ports["outputs"].extend([{"name": "valid", "bits": 1}, {"name": "div0", "bits": 1}])
        expressions.update(valid="b != 0", div0="b == 0")
    if flag:
        low, high = bounds(ports["outputs"][0])
        status = "overflow" if signed or name == "MUL" else "borrow" if name in ("SUB", "DEC") else "carry"
        ports["outputs"].append({"name": status, "bits": 1})
        expressions[status] = f"({expr}) < 0" if name in ("SUB", "DEC") and not signed else f"({expr}) < {low} or ({expr}) > {high}"
    ports = interface(ports)
    params = {"a_bits": a_bits, "result_bits": result_bits, "signed": signed, "overflow": overflow, "flag": flag}
    if definition["operands"] >= 2 and shift is None:
        params["b_bits"] = b_bits
    if name in SHIFTS and shift is not None:
        params["shift"] = shift
    return {"definition": name, "version": 1, "parameters": params}, ports, expressions


def operation_variant(operation):
    if not isinstance(operation, dict) or set(operation) - {"definition", "version", "parameters"} or operation.get("version", 1) != 1:
        raise ValueError("Operation braucht definition, version 1 und parameters.")
    params = operation.get("parameters", {})
    if not isinstance(params, dict) or set(params) - PARAMETERS:
        raise ValueError("Ungültige Operationsparameter.")
    return variant(operation.get("definition"), **params)


def operation_label(operation):
    op, ports, _ = operation_variant(operation)
    label = f"{op['definition']}({','.join(str(p['bits']) for p in ports['inputs'])},{ports['outputs'][0]['bits']})"
    return label + (f" [n={op['parameters']['shift']}]" if "shift" in op["parameters"] else "")


def edge_inputs(ports):
    """Prioritize endpoints, signed boundaries and each operand in isolation."""
    choices = []
    width = ports["inputs"][0]["bits"]
    for p in ports["inputs"]:
        mask, sign = (1 << p["bits"]) - 1, 1 << (p["bits"] - 1)
        values = [0, 1, mask, sign, sign - 1, mask - 1]
        if p["name"] == "b":
            values += [width - 1, width, width + 1]
        choices.append(list(dict.fromkeys(v for v in values if 0 <= v <= mask)))
    pack = lambda values: sum(v << p["offset"] for v, p in zip(values, ports["inputs"]))
    edges = [0, sum(((1 << p["bits"]) - 1) << p["offset"] for p in ports["inputs"])]
    for i, values in enumerate(choices):
        for v in values:
            isolated = [0] * len(choices); isolated[i] = v
            edges.append(pack(isolated))
    return list(dict.fromkeys(edges + [pack(values) for values in product(*choices)]))


def generate_operation(operation, samples=None, seed=1, name=None):
    from .dataset import generate
    op, ports, expressions = operation_variant(operation)
    label = operation_label(op)
    dataset = generate(name or label, sum(p["bits"] for p in ports["inputs"]),
                       sum(p["bits"] for p in ports["outputs"]), expressions, samples, seed, ports=ports,
                       edge_inputs=edge_inputs(ports))
    dataset.metadata["operation"] = op
    return dataset

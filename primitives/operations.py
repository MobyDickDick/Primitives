"""Reference definitions and concrete width variants, independent of NAND circuits."""
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


def variant(name, a_bits=None, b_bits=None, result_bits=None, signed=False, overflow="wrap", flag=False):
    if name not in OPERATIONS:
        raise ValueError("Unbekannte Operationsdefinition.")
    definition = OPERATIONS[name]
    a_bits, b_bits, result_bits = [d if v is None else v for v, d in
                                  zip((a_bits, b_bits, result_bits), definition["defaults"])]
    if any(type(w) is not int or not 1 <= w <= 32 for w in (a_bits, b_bits, result_bits)):
        raise ValueError("Operand- und Ergebnisbreiten müssen zwischen 1 und 32 liegen.")
    if type(signed) is not bool or type(flag) is not bool or overflow not in ("wrap", "error"):
        raise ValueError("signed/flag müssen boolesch und overflow wrap oder error sein.")
    if flag and name not in ("ADD", "SUB", "MUL"):
        raise ValueError("Statusausgang ist für ADD, SUB und MUL verfügbar.")
    ports = {"inputs": [{"name": "a", "bits": a_bits, "signed": signed}],
             "outputs": [{"name": "c", "bits": result_bits, "signed": signed, "overflow": overflow}]}
    if definition["operands"] == 2:
        ports["inputs"].append({"name": "b", "bits": b_bits, "signed": signed})
    # Bitwise NOT/NAND/NOR/XNOR invert exactly the result width, even in error mode.
    expr = definition["expression"]
    if name in ("NOT", "NAND", "NOR", "XNOR"):
        expr = f"({expr}) & {(1 << result_bits) - 1}"
        if signed:
            expr = f"(({expr}) ^ {1 << (result_bits - 1)}) - {1 << (result_bits - 1)}"
    expressions = {"c": expr}
    if flag:
        low, high = bounds(ports["outputs"][0])
        status = "overflow" if signed or name == "MUL" else "borrow" if name == "SUB" else "carry"
        ports["outputs"].append({"name": status, "bits": 1})
        expressions[status] = f"({expr}) < 0" if name == "SUB" and not signed else f"({expr}) < {low} or ({expr}) > {high}"
    ports = interface(ports)
    params = {"a_bits": a_bits, "result_bits": result_bits, "signed": signed, "overflow": overflow, "flag": flag}
    if definition["operands"] == 2:
        params["b_bits"] = b_bits
    return {"definition": name, "version": 1, "parameters": params}, ports, expressions


def operation_variant(operation):
    if not isinstance(operation, dict) or set(operation) - {"definition", "version", "parameters"} or operation.get("version", 1) != 1:
        raise ValueError("Operation braucht definition, version 1 und parameters.")
    params = operation.get("parameters", {})
    if not isinstance(params, dict) or set(params) - {"a_bits", "b_bits", "result_bits", "signed", "overflow", "flag"}:
        raise ValueError("Ungültige Operationsparameter.")
    return variant(operation.get("definition"), **params)


def operation_label(operation):
    op, ports, _ = operation_variant(operation)
    return f"{op['definition']}({','.join(str(p['bits']) for p in ports['inputs'])},{ports['outputs'][0]['bits']})"


def generate_operation(operation, samples=None, seed=1, name=None):
    from .dataset import generate
    op, ports, expressions = operation_variant(operation)
    label = operation_label(op)
    dataset = generate(name or label, sum(p["bits"] for p in ports["inputs"]),
                       sum(p["bits"] for p in ports["outputs"]), expressions, samples, seed, ports=ports)
    dataset.metadata["operation"] = op
    return dataset

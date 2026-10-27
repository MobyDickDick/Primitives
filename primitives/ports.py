"""Named bit-vector interfaces; offsets are relative to each side, LSB first."""
import keyword
import re
from .limits import MAX_BITS


RESERVED = {"x", "pi", "sin", "cos", "sqrt", "isqrt", "floor", "ceil", "abs", "min", "max", "round"}


def interface(spec, inputs=None, outputs=None):
    if not isinstance(spec, dict) or spec.get("schema", 1) != 1 or spec.get("bit_order", "LSB-first") != "LSB-first":
        raise ValueError("Schnittstelle braucht schema 1 und Bitreihenfolge LSB-first.")
    result = {"schema": 1, "bit_order": "LSB-first"}
    names = set()
    for side, expected in (("inputs", inputs), ("outputs", outputs)):
        ports = spec.get(side)
        if not isinstance(ports, list) or not 1 <= len(ports) <= MAX_BITS:
            raise ValueError(f"{side}: 1–{MAX_BITS} benannte Ports erforderlich.")
        offset, normalized = 0, []
        for port in ports:
            if not isinstance(port, dict):
                raise ValueError("Jeder Port muss ein Objekt sein.")
            name, width = port.get("name"), port.get("bits")
            if (not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,31}", name)
                    or keyword.iskeyword(name) or name in RESERVED or re.fullmatch(r"x\d+", name) or name in names):
                raise ValueError("Portnamen müssen eindeutige Bezeichner sein; x, x0… und Funktionsnamen sind reserviert.")
            if type(width) is not int or not 1 <= width <= MAX_BITS or type(port.get("signed", False)) is not bool:
                raise ValueError(f"Portbreite muss 1–{MAX_BITS} sein, signed muss boolesch sein.")
            if "offset" in port and (type(port["offset"]) is not int or port["offset"] != offset):
                raise ValueError(f"Port {name}: Bitoffset muss {offset} sein.")
            normalized.append({"name": name, "bits": width, "signed": port.get("signed", False), "offset": offset})
            if side == "outputs":
                overflow = port.get("overflow", "error")
                if overflow not in ("wrap", "error"):
                    raise ValueError("Überlauf muss wrap oder error sein.")
                normalized[-1]["overflow"] = overflow
            names.add(name)
            offset += width
        if offset > MAX_BITS or expected is not None and offset != expected:
            raise ValueError(f"{side}: Summe der Portbreiten muss {expected or f'1–{MAX_BITS}'} sein (erhalten: {offset}).")
        result[side] = normalized
    return result


def decode(value, port):
    value = (value >> port["offset"]) & ((1 << port["bits"]) - 1)
    return value - (1 << port["bits"]) if port["signed"] and value & (1 << (port["bits"] - 1)) else value


def bounds(port):
    width = port["bits"]
    return (-(1 << (width - 1)), (1 << (width - 1)) - 1) if port["signed"] else (0, (1 << width) - 1)


def encode(value, port, x):
    low, high = bounds(port)
    if value != int(value) or port["overflow"] == "error" and not low <= value <= high:
        raise ValueError(f"Ausgabe {port['name']} für x={x} ist {value}; erwartet wird eine ganze Zahl {low}…{high}.")
    return int(value) % (1 << port["bits"])

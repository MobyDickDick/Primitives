"""Export conventional, fixed-step arithmetic templates as portable definitions."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ADD = '''def add<w>(a, b):
    x = bits(a, w)
    y = bits(b, w)
    result = [0] * (w + 1)
    carry = 0
    for i in range(w):
        parity = x[i] ^ y[i]
        result[i] = parity ^ carry
        carry = (x[i] & y[i]) | (parity & carry)
    result[w] = carry
    return pack(result)
'''

SUB = '''def subtract<w>(a, b):
    x = bits(a, w)
    y = bits(b, w)
    result = [0] * (w + 1)
    borrow = 0
    for i in range(w):
        parity = x[i] ^ y[i]
        result[i] = parity ^ borrow
        borrow = ((1 ^ x[i]) & y[i]) | ((1 ^ parity) & borrow)
    result[w] = borrow
    return pack(result)
'''

MUL = '''def multiply<w>(a, b):
    x = bits(a, w)
    y = bits(b, w)
    result = [0] * (2 * w)
    for i in range(w):
        carry = 0
        for j in range(w):
            partial = x[j] & y[i]
            parity = result[i + j] ^ partial
            digit = parity ^ carry
            carry = (result[i + j] & partial) | (parity & carry)
            result[i + j] = digit
        result[i + w] = carry
    return pack(result)
'''

DIV = '''# Restoring division: n feste Stufen, keine datenabhaengigen Schleifen.
x = bits(a, n)
y = bits(b, n)
quotient = [0] * n
remainder = [0] * (n + 1)
for i in range(n - 1, -1, -1):
    remainder = [x[i]] + remainder[:n]
    difference = bits(subtract<n+1>(pack(remainder), b), n + 2)
    take = 1 ^ difference[n + 1]
    for j in range(n + 1):
        remainder[j] = (difference[j] & take) | (remainder[j] & (1 ^ take))
    quotient[i] = take
valid = 0
for i in range(n):
    valid = valid | y[i]
for i in range(n):
    quotient[i] = quotient[i] & valid
    remainder[i] = remainder[i] & valid
return pack(quotient), pack(remainder[:n]), valid, 1 ^ valid
'''


def definitions():
    inputs = [{"name": "a", "bits": "n"}, {"name": "b", "bits": "n"}]
    cases = [
        ("ripple-add", "Addition", "Ripple-Carry-Addierer: zwei unsigned n-Bit-Zahlen ergeben eine vollständige n+1-Bit-Summe. Feste Volladdierstufen; direkt nach NAND übersetzbar.",
         ADD + '\nreturn add<n>(a, b)\n', [{"name": "c", "bits": "n+1"}], 16),
        ("ripple-sub", "Subtraktion", "Ripple-Borrow-Subtrahierer: c=(a-b) modulo 2^n; borrow=1 genau bei a<b. Feste Subtrahierstufen; unsigned Eingänge.",
         SUB + '\ndifference = bits(subtract<n>(a, b), n + 1)\nreturn pack(difference[:n]), difference[n]\n',
         [{"name": "c", "bits": "n"}, {"name": "borrow", "bits": 1}], 16),
        ("shift-add-mul", "Multiplikation", "Unsigned Multiplikation mit AND-Teilprodukten und festen Addierstufen. Das vollständige Produkt hat 2*n Bits; keine Multiplikation von Eingangswerten im Quelltext.",
         MUL + '\nreturn multiply<n>(a, b)\n', [{"name": "c", "bits": "2*n"}], 16),
        ("restoring-div", "Division", "Unsigned schriftliche Binärdivision mit n festen Subtraktions-/Auswahlstufen. c=a//b, rest=a%b. Bei b=0: c=0, rest=0, valid=0, div0=1; sonst valid=1, div0=0.",
         SUB + '\n' + DIV, [{"name": "c", "bits": "n"}, {"name": "rest", "bits": "n"},
                            {"name": "valid", "bits": 1}, {"name": "div0", "bits": 1}], 15),
    ]
    for filename, name, description, source, outputs, maximum in cases:
        yield filename, {"schema": 1, "kind": "template", "name": name, "description": description,
                         "parameters": ["n"], "conditions": ["n >= 1", f"n <= {maximum}"],
                         "interface": {"inputs": inputs, "outputs": outputs}, "source": source,
                         "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000}}


if __name__ == "__main__":
    folder = ROOT / "examples" / "templates"
    for filename, document in definitions():
        (folder / f"{filename}.abstract.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (folder / f"{filename}.prim").write_text(document["source"], encoding="utf-8")

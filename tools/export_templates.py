"""Export conventional, fixed-step arithmetic templates as portable definitions."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ADD = '''def add<w>(a, b):
    # Zwei vorzeichenlose Zahlen bitweise addieren; w ist die feste Bitbreite.
    # bits liefert die Bits von rechts nach links: Index 0 hat den Wert 1,
    # Index 1 den Wert 2, Index 2 den Wert 4 usw. Fehlende obere Bits sind 0.
    x = bits(a, w)
    y = bits(b, w)
    # Ein zusätzliches Bit nimmt den letzten Übertrag auf: z.B. 1+1 = 10.
    result = [0] * (w + 1)
    carry = 0  # Übertrag aus der vorherigen, niedrigeren Stelle.
    for i in range(w):
        # ^ ist XOR: 1, wenn genau eines der beiden Bits 1 ist.
        parity = x[i] ^ y[i]
        # Das Summenbit berücksichtigt auch den eingehenden Übertrag.
        result[i] = parity ^ carry
        # Ein neuer Übertrag entsteht bei zwei gesetzten Eingangsbits
        # oder wenn ein einzelnes gesetztes Bit zum alten Übertrag hinzukommt.
        carry = (x[i] & y[i]) | (parity & carry)
    result[w] = carry
    # pack setzt das Bitarray wieder zu einer ganzen Zahl zusammen.
    return pack(result)
'''

SUB = '''def subtract<w>(a, b):
    # a-b an w Stellen berechnen. Das zusätzliche Bit meldet a<b.
    # Bitarrays sind LSB-first: x[0] ist die Einerstelle, x[1] die Zweierstelle.
    x = bits(a, w)
    y = bits(b, w)
    result = [0] * (w + 1)
    borrow = 0  # Leihbit: Die niedrigere Stelle hat sich eine 1 ausgeliehen.
    for i in range(w):
        # Ohne eingehendes Leihbit ist das Differenzbit x[i] XOR y[i].
        parity = x[i] ^ y[i]
        # Ein eingehendes Leihbit zieht eine weitere 1 ab und kippt dieses Bit.
        result[i] = parity ^ borrow
        # Neues Leihbit in zwei Fällen:
        # 1. x[i]=0, y[i]=1: Die aktuelle Stelle braucht eine geliehene 1.
        # 2. x[i]=y[i] und borrow=1: Die Leihe muss weitergereicht werden.
        # Für einzelne Bits bedeutet 1 ^ bit die Umkehrung von 0 und 1.
        borrow = ((1 ^ x[i]) & y[i]) | ((1 ^ parity) & borrow)
    # Die unteren w Bits enthalten (a-b) modulo 2**w.
    # Bit w ist das letzte Leihbit: 1 genau dann, wenn a<b.
    result[w] = borrow
    # Beispiel w=2: 1-2 liefert die unteren Bits 11 und Leihbit 1,
    # also pack([1,1,1])=7. Aufrufer trennen Differenz und Leihbit wieder.
    return pack(result)
'''

MUL = '''def multiply<w>(a, b):
    # Schriftliche Binärmultiplikation: Teilprodukte bilden und addieren.
    # Index 0 ist jeweils das niederwertigste Bit.
    x = bits(a, w)
    y = bits(b, w)
    # Das vollständige Produkt zweier w-Bit-Zahlen passt in 2*w Bits.
    result = [0] * (2 * w)
    for i in range(w):
        # Für jedes Bit y[i] eine neue Teilproduktzeile addieren.
        carry = 0
        for j in range(w):
            # AND ist die Multiplikation zweier einzelner Bits.
            partial = x[j] & y[i]
            # Das Teilprodukt gehört wegen seiner Stellenwerte zu Bit i+j.
            # Vorhandenes Ergebnisbit, Teilprodukt und Übertrag addieren.
            parity = result[i + j] ^ partial
            digit = parity ^ carry
            carry = (result[i + j] & partial) | (parity & carry)
            result[i + j] = digit
        # Letzten Übertrag dieser Zeile an die nächste freie Stelle schreiben.
        result[i + w] = carry
    return pack(result)
'''

DIV = '''# Schriftliche Binärdivision: c=a//b, rest=a%b; beide Eingänge haben n Bits.
# Die Bits werden vom höchsten zum niedrigsten verarbeitet.
x = bits(a, n)
y = bits(b, n)
quotient = [0] * n
# Ein zusätzliches Bit bietet Platz für den vorübergehend verdoppelten Rest.
remainder = [0] * (n + 1)
# range(start, stop, step) schliesst stop aus: n-1, n-2, ..., 0.
for i in range(n - 1, -1, -1):
    # Nächstes Dividend-Bit herunterholen: neuer Rest = 2*alter Rest + x[i].
    # Wegen LSB-first steht das neue Bit am Anfang des Arrays.
    remainder = [x[i]] + remainder[:n]
    # Versuchsweise b abziehen. subtract liefert n+1 Differenzbits
    # und an Index n+1 ein Leihbit, zusammen also n+2 Bits.
    difference = bits(subtract<n+1>(pack(remainder), b), n + 2)
    # Kein Leihbit bedeutet Rest>=b: Die Subtraktion darf übernommen werden.
    take = 1 ^ difference[n + 1]
    for j in range(n + 1):
        # Bitweise Auswahl: take=1 nimmt die Differenz, take=0 den alten Rest.
        # Das ist die Wiederherstellung (restoring) nach einem Fehlversuch.
        remainder[j] = (difference[j] & take) | (remainder[j] & (1 ^ take))
    quotient[i] = take
# ODER aller Divisorbits: valid=1 genau dann, wenn b ungleich 0 ist.
valid = 0
for i in range(n):
    valid = valid | y[i]
# Bei Division durch 0 Quotient und Rest auf 0 setzen.
for i in range(n):
    quotient[i] = quotient[i] & valid
    remainder[i] = remainder[i] & valid
# Rückgabereihenfolge: Quotient, Rest, gültig, Division-durch-null-Flag.
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

# Primitives
generate simple Programms

## Beispiele anpassen

In der Browseroberfläche eine **Vorlage** auswählen, **Name**, **Eingangsbits N**,
**Ausgangsbits M** und **Ausdruck** bearbeiten, dann **Vektoren erzeugen** klicken.
Der Name ist eine Beschriftung; die Berechnung bestimmen die Bitanzahlen und der Ausdruck.

### MUL(2,2,4)

Die Vorlage **MUL(2,2,4)** ist direkt auswählbar. Alternativ diese Werte eintragen:

| Feld | Wert |
|---|---|
| Name | `MUL(2,2,4)` |
| Eingangsbits N | `4` (2 für a + 2 für b) |
| Ausgangsbits M | `4` (für c) |
| Ausdruck | `a*b` |
| Maximale Anzahl Vektoren | `16` oder mehr |

`a` und `b` sind die untere und obere Hälfte der Eingabe, jeweils 0–3.
Die Reihenfolge einer Vektorzeile ist `a0, a1, b0, b1, c0, c1, c2, c3`
(jeweils das niederwertigste Bit zuerst).
Alle 16 Eingabekombinationen werden erzeugt; der grösste Ausgang ist 3 × 3 = 9.
Tatsächlich erreichbar sind nur 0, 1, 2, 3, 4, 6 und 9. Auch 5, 7 und 8 sowie
10–15 kommen nie als Sollausgabe vor. Dafür braucht es keine zusätzlichen
Verbotszeilen: Eine auf allen 16 Eingaben korrekte Schaltung liefert diese Werte nie.

Die fertige Wahrheitstabelle lässt sich auch über **Eigene Vektoren importieren**
aus [`examples/mul-2-2-4.json`](examples/mul-2-2-4.json) laden.
Auf der Kommandozeile bleibt die Vorlage über `--preset mul` verfügbar.

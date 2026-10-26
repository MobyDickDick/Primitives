# Rekursive Multiplikation mit Überlauf

Die [ausführbare Quelle](../examples/templates/recursive-split-mul.prim) und das
[abstrakte Template](../examples/templates/recursive-split-mul.abstract.json)
implementieren `MUL<w>(a,b)` für unsigned Operanden. `w` ist eine positive
Zweierpotenz. Die Ausgabe besteht aus `w` Ergebnisbits `c` und einem Bit `err`:

```text
a*b <  2**w: [a*b, 0]
a*b >= 2**w: [CONST<w>(0), 1]
```

Der Überlauf beginnt bereits bei `2**w`. Beispielsweise liefert
`MUL<2>(2,2) = [0,1]`, während `MUL<2>(3,1) = [3,0]` gilt.
Für `w=1` gilt `c = a AND b` und `err = 0`.
Alle Bitblöcke und Ports verwenden LSB-first.

## Rekursion und vollständige Teilprodukte

Mit `k=w//2`, `a=a_lo+2**k*a_hi` und `b=b_lo+2**k*b_hi` lautet die Formel:

```text
p00 = MUL_raw<k>(a_lo, b_lo)
p01 = MUL_raw<k>(a_lo, b_hi)
p10 = MUL_raw<k>(a_hi, b_lo)
p11 = MUL_raw<k>(a_hi, b_hi)
P = p00 + 2**k * (p01 + p10) + 2**w * p11
```

`MUL_raw<k>` liefert das vollständige Produkt mit `2*k` Bits. Die öffentliche
Funktion `MUL<k>` darf hier nicht eingesetzt werden: Zum Beispiel muss das
Teilprodukt `MUL_raw<2>(3,3)=9` erhalten bleiben. Die Fehlerdarstellung der
öffentlichen Funktion wäre `[0,1]` und würde die weiteren Summen verfälschen.

Der Basisfall ist `MUL_raw<1>(a,b) = [a AND b, 0]`. Damit verwendet
`MUL_raw<2>` vier Ein-Bit-Multiplikationen; `MUL_raw<4>` verwendet vier
Zwei-Bit-Multiplikationen mit insgesamt sechzehn Ein-Bit-Multiplikationen.

Die Quelle erhält die Überträge bei der Addition der verschobenen Produkte:

```text
cross = p01 + p10                         # w+1 Bits
low   = p00 + 2**k * (cross modulo 2**k)  # w+1 Bits
high  = p11 + (cross // 2**k)             # w+1 Bits
upper = (high modulo 2**w) + low[w]       # w+1 Bits
P     = [low[:w], upper[:w]]              # 2*w Bits
```

`ADD<w>` wird rekursiv mit bedingtem `INC` realisiert. Die Verschiebungen
sind Bitverdrahtung und Nullauffüllung. Die oberen Überträge von `high` und
`upper` sind immer null, da das Produkt zweier `w`-Bit-Zahlen in `2*w` Bits
passt. `CHECK<w>` verknüpft die oberen `w` Produktbits mit OR zu `err` und
maskiert die unteren Bits bei einem Fehler auf null. Alle Entscheidungen
über Eingabewerte sind Bitoperationen und direkt nach NAND übersetzbar.

## Konkrete F-Boxen und flache NAND-Netze

Die Dateien liegen unter [examples/circuits/recursive-split-mul](../examples/circuits/recursive-split-mul/).

| w | F-Box-Paket | Flaches NAND-Netz | NANDs in der Hierarchie | NANDs flach | Geprüfte Eingabepaare |
| --- | --- | --- | --- | --- | --- |
| 1 | [mul-1.block.json](../examples/circuits/recursive-split-mul/mul-1.block.json) | [mul-1.circuit.json](../examples/circuits/recursive-split-mul/mul-1.circuit.json) | 8 | 7 | 4 |
| 2 | [mul-2.block.json](../examples/circuits/recursive-split-mul/mul-2.block.json) | [mul-2.circuit.json](../examples/circuits/recursive-split-mul/mul-2.circuit.json) | 81 | 68 | 16 |
| 4 | [mul-4.block.json](../examples/circuits/recursive-split-mul/mul-4.block.json) | [mul-4.circuit.json](../examples/circuits/recursive-split-mul/mul-4.circuit.json) | 444 | 363 | 256 |

Jedes Paket enthält sämtliche Abhängigkeiten mit festen Versionskennungen.
Die Wurzel `MUL<w>` enthält die Boxen `MUL_raw<w>` und `CHECK<w>`. Innerhalb
von `MUL_raw<w>` liegen für `w>1` vier Multiplikationsboxen, drei
Additionsboxen und ein bedingter Inkrementierer. `ADD_shifted` und
`ADD_extended` verdrahten ihre schmaleren Eingänge intern mit Nullbits;
ihre Logik ist dieselbe rekursive Addition. Die Blätter enthalten NAND-Gatter.
Die konstante Null am Ein-Bit-Ausgang wird ebenfalls mit NANDs realisiert.

Die flachen Netze entstehen durch Expansion der F-Boxen und anschliessende
Vereinfachung: unbenutzte Gatter werden entfernt und gleiche NAND-Paare
zusammengefasst. Die Boxstruktur bleibt im separaten Paket erhalten.
Zusätzlich liegen je Breite die lesbare `.nand.txt`-Liste, die konkrete
`.template.json`-Instanz und vollständige `.vectors.json`-Sollvektoren vor.
[verification.json](../examples/circuits/recursive-split-mul/verification.json)
enthält die Prüfberichte und Dateizuordnungen.

Die Tests vergleichen Quellauswertung, F-Box-Auswertung, expandiertes Netz,
vereinfachtes Netz und direkte Quellsynthese für sämtliche Eingaben mit
unabhängiger Ganzzahlmultiplikation. Die vollständigen Rohprodukte werden
zusätzlich geprüft. Für `w=8` werden Grenzfälle und feste Zufallsstichproben
der Referenzauswertung geprüft. Die NAND-Synthese ist dort durch das bestehende
512-Gatter-Limit begrenzt. Das Template erlaubt `w=1,2,4,8`; grössere Breiten
überschreiten bei dieser Rekursion das bestehende Auswertungsbudget.

## Bibliothek und Reproduktion

Beim nächsten Serverstart werden einmalig unter **Beispiele → Rekursion** das
Template sowie die drei konkreten Funktionen mit flachen NAND-Netzen ergänzt.
Unter **Unterprogramm-Bausteine** stehen `MUL<1>`, `MUL<2>` und `MUL<4>` als
verschachtelte F-Boxen bereit. **Baustein öffnen** zeigt die anklickbaren
Unterfunktionen und erlaubt lokale Handtests. Bestehende Ordnerzuordnungen
bleiben erhalten; später gelöschte Beispiele werden nicht erneut installiert.

```powershell
python -m tools.export_recursive_mul
python -m unittest discover -s tests -p test_recursive_mul.py -v
```

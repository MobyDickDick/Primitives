# Rekursive Subtraktion und Nullwert bei Fehlern

Die [Quelle von SUB](../examples/templates/recursive-split-sub.prim) und das
[abstrakte Template](../examples/templates/recursive-split-sub.abstract.json)
implementieren die Halbierung beider Operanden, rekursive Subtraktion und
bedingtes Dekrementieren der oberen Differenz. `w` ist die gesamte
Operandenbreite und eine positive Zweierpotenz. Alle Bitfolgen sind LSB-first.

## Ergebnis und Verkettung

`SUB<w>(a,b)` liefert `w` Ergebnisbits plus ein Borrow-/Fehlerbit:

```text
a >= b: [a-b, 0]
a <  b: [const<w>(0), 1]
```

Das letzte Bit bedeutet bei unsigned Eingaben, dass die mathematische
Differenz negativ ist. Die Ausgabe ist eine Fehlerdarstellung, kein
Zweierkomplement und kein negatives Zahlenergebnis.

Die [Addition mit Fehlerbit](../examples/templates/recursive-split-add-checked.prim)
und ihr [abstraktes Template](../examples/templates/recursive-split-add-checked.abstract.json)
bieten dieselbe Ausgabeform als `ADD_checked<w>(a,b)`:

```text
a+b <  2**w: [a+b, 0]
a+b >= 2**w: [const<w>(0), 1]
```

Der Überlauf beginnt bei `2**w`, nicht erst bei `2**w+1`.
Die [bisherige Addition](REKURSIVE-ADDITION.md) und die interne Funktion
`ADD<w>` liefern weiterhin die vollständige Summe mit `w+1` Bits.
Die Nullsetzung erfolgt erst am Ausgang von `ADD_checked`.

`[c_lo,c_hi]` bezeichnet hier die flache Verkettung beider Bitblöcke,
zuerst die niederwertigen Bits. In beiden neuen Quellen ist dafür eine
eigene Funktion enthalten:

```text
def CONCAT<lo_width, hi_width>(lo, hi):
    assert lo_width > 0 and hi_width > 0 and lo_width + hi_width <= 128
    return pack(bits(lo, lo_width) + bits(hi, hi_width))

# c_lo hat k Bits; c_hi hat k Ergebnisbits plus ein Flag:
return CONCAT<k, k+1>(c_lo, c_hi)

# [const<w>(0), 1]:
return CONCAT<w, 1>(const<w>(0), 1)
```

Die Breiten sind nötig, weil gepackte Ganzzahlen führende Nullbits nicht
speichern. Eine gewöhnliche Arrayliste `[c_lo,c_hi]` akzeptiert in der
Sprache weiterhin nur einzelne Bits. Die Funktion macht die gewünschte
Bitblock-Verkettung ohne Änderung dieser bestehenden Syntax verfügbar.
`const<w>(value)` liefert die unteren `w` Bits als gepackte Zahl; die
Ausgabebreite ergibt sich aus dem expliziten Parameter von `CONCAT`.

## Basisfall und interne Differenzen

Der ergänzte Basisfall ist für die öffentliche Funktion `SUB` korrekt:

```text
SUB<1>(a,b) = [a0 AND NOT b0, NOT a0 AND b0]
```

| a0 | b0 | Resultat | Borrow |
| --- | --- | --- | --- |
| 0 | 0 | 0 | 0 |
| 0 | 1 | 0 | 1 |
| 1 | 0 | 1 | 0 |
| 1 | 1 | 0 | 0 |

Bei einzelnen Bits wird NOT als `1 ^ bit` geschrieben. Der Operator `~`
auf einer Ganzzahl invertiert dagegen alle Bits und liefert zum Beispiel
`~0 = -1`.

Die rekursive Hilfsfunktion `SUB_raw<w>` muss die modulare Differenz
erhalten. Ihr Basisfall lautet deshalb:

```text
SUB_raw<1>(a,b) = [a0 XOR b0, NOT a0 AND b0]
```

Beispiel `SUB<8>(16,1)`: In der unteren 4-Bit-Hälfte entsteht `0-1`,
also intern `[15,1]`. Das Borrow reduziert die obere Differenz von 1 auf 0.
Zusammen ist das Ergebnis 15. Würde schon die untere Hälfte `[0,1]`
zurückgeben, gingen die vier gesetzten Restbits verloren.

## Bereinigte Rekursion

Der folgende Pseudocode verwendet `[lo,hi]` als Bitblock-Verkettung.
`bits(x,q)` macht die `q` Bits einer gepackten Zahl zugänglich.

```text
SUB_raw<w>(a,b):
    Voraussetzung: w >= 1 und w ist eine Zweierpotenz
    wenn w == 1:
        return [a0 XOR b0, NOT a0 AND b0]

    k = w // 2
    lo = bits(SUB_raw<k>(Lower<k>(a), Lower<k>(b)), k+1)
    hi = bits(SUB_raw<k>(Higher<k>(a), Higher<k>(b)), k+1)
    adjusted = bits(DEC<k>(pack(hi[:k]), lo[k]), k+1)
    borrow = hi[k] OR adjusted[k]
    return [lo[:k], adjusted[:k], borrow]

SUB<w>(a,b):
    result = bits(SUB_raw<w>(a,b), w+1)
    wenn result[w]:
        return [const<w>(0), 1]
    return result
```

`DEC<k>(x,enable)` berechnet `x-enable` modulo `2**k` plus Borrow.
Die Quelle implementiert dies rekursiv mit XOR für das Ergebnisbit und
`NOT x0 AND enable` für das nächste Borrow. Die Breite von `DEC` darf auch
eine ungerade Zahl sein.

Die Korrekturen gegenüber der Skizze:

- Der Basisfall ist `w == 1`; der rekursive Fall beginnt bei `w > 1`.
- `Lower` und `Higher` erhalten hier die Halbbreite `k=w//2`.
  `Higer` ist zu `Higher` korrigiert; das ältere ADD-Beispiel nennt die
  obere Auswahl `Upper`.
- Das Borrow der unteren Teildifferenz steht bei `lo[k]`, nicht bei
  `lo[w-1]`. Jede Teildifferenz hat `k+1` Bits.
- Das obere Borrow darf beim Dekrementieren nicht verloren gehen:
  Das Endflag ist `hi[k] OR adjusted[k]`.
- Erst die fertige Differenz darf bei Borrow auf null gesetzt werden.
  Negative Teildifferenzen behalten intern ihre modularen Restbits.

Die tatsächliche Quelle ersetzt die datenabhängigen `if`-Anweisungen
durch Bitmasken. Deshalb sind beide Templates direkt in NAND übersetzbar.

## Geprüfte Instanzen

| Template | NANDs, w=1 | NANDs, w=2 | NANDs, w=4 |
| --- | --- | --- | --- |
| SUB | 6 | 25 | 64 |
| ADD_checked | 7 | 24 | 61 |

Unter [SUB](../examples/circuits/recursive-split-sub/) und
[ADD_checked](../examples/circuits/recursive-split-add-checked/) liegen
flache NAND-Netze, lesbare NAND-Listen, konkrete Templates,
Referenzvektoren und Verifikationsberichte. Für 1, 2 und 4 Bits wurden
alle 4, 16 bzw. 256 Eingabepaare gegen unabhängige Ganzzahlarithmetik
geprüft. Tests für 8 und 16 Bits prüfen zusätzlich Grenzfälle und feste
Zufallsstichproben, einschliesslich Borrow über mehrere Hälften.

Nach einem Serverneustart erscheinen die neuen Templates einmalig unter
**Beispiele → Rekursion**, auch in bestehenden Bibliotheken. Ordnernamen,
Beschreibungen und bestehende Zuordnungen bleiben erhalten.

```powershell
python -m tools.export_recursive_arithmetic
python -m unittest discover -s tests -p test_recursive_arithmetic.py -v
```

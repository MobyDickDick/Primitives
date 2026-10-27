# Rekursive Addition und flache NAND-Instanzen

Für die entsprechende Subtraktion, die Bitblock-Verkettung `[c_lo,c_hi]`
und `ADD_checked` mit Nullwert bei Überlauf siehe
[Rekursive Subtraktion und Nullwert bei Fehlern](REKURSIVE-SUBTRAKTION.md).

Die [editierbare Quelle](../examples/templates/recursive-split-add.prim) setzt
die Addition durch unabhaengige Addition beider Haelften und anschliessendes
bedingtes Inkrementieren der oberen Summe um. Das
[abstrakte Template](../examples/templates/recursive-split-add.abstract.json)
ist unter **Abstrakte Templates** importierbar. Es ist ein eigenes Beispiel;
der aeltere rekursive Addierer und der Ripple-Carry-Addierer bleiben erhalten.

## Breiten und Ergebnis

`ADD<w>(a,b)` nimmt zwei unsigned Zahlen mit jeweils `w` Bits entgegen und
liefert die vollstaendige Summe mit `w+1` Bits. `w` ist eine positive
Zweierpotenz. Die Schnittstelle der konkreten Instanz besteht aus `a[n]`,
`b[n]`, `c[n]` und `err[1]`:

```text
c   = (a+b) mod 2^n
err = (a+b) div 2^n
a+b = c + 2^n * err
```

`err` bezeichnet den normalen Enduebertrag. Er ist kein Ausfuehrungsfehler.
Alle Bitfolgen sind LSB-first. Fuer `w>1` gilt `k=w//2`; die gedachte
Rueckgabe `[c_lo,c_hi,err]` wird als flache Bitfolge mit den Breiten
`k`, `k`, `1` dargestellt. Im Basisfall sind es Summenbit und Uebertrag.
Eigene Funktionen geben diese Bitfolgen mit `pack` als Zahl zurueck.

`Lower<k>(a)` und `Upper<k>(a)` erhalten die **Halbbreite** und waehlen aus
einer `2*k`-Bit-Zahl jeweils die unteren bzw. oberen `k` Bits aus.

## Bereinigte Rekursion

Mathematisch, mit expliziten Ergebnisbreiten:

```text
ADD<w>(a,b):
    Voraussetzung: w > 0 und w ist eine Zweierpotenz
    wenn w == 1:
        return [a0 XOR b0, a0 AND b0]

    k       = w div 2
    lo      = ADD<k>(Lower<k>(a), Lower<k>(b))       # k+1 Bits
    hi_temp = ADD<k>(Upper<k>(a), Upper<k>(b))       # k+1 Bits
    hi      = INC<k+1>(hi_temp, lo[k])               # k+2 Bits
    return lo[0:k] ++ hi[0:k+1]                     # w+1 Bits
```

`++` bedeutet hier Bitfolgenverkettung. Die tatsaechliche Sprache schreibt
dafuer `+` zwischen Arrays. `INC<q>(x,enable)` liefert `x+enable` mit `q+1`
Bits; bei `enable=0` bleibt der Wert unveraendert. Jede Stufe verwendet XOR
fuer das neue Bit und AND fuer den naechsten Uebertrag und ruft sich fuer den
Rest rekursiv auf. `q` darf auch eine ungerade Zahl sein.

Die Rekursion der Addition verwendet `k`, nicht `w-1`. Beim Inkrementieren
muss zudem das bereits vorhandene Uebertragsbit der oberen Summe erhalten
bleiben. Deshalb arbeitet `INC` auf **k+1 Bits**. Ein Aufruf `ADD<k>` mit der
gesamten oberen Teilsumme wuerde deren hoechstes Bit abschneiden.

Das letzte Bit `hi[k+1]` kann bei dieser Verwendung nicht gesetzt sein:
`hi_temp <= 2^(k+1)-2`, und es wird hoechstens 1 addiert. Es wird deshalb
beim Verdrahten nicht ausgegeben. Der Enduebertrag ist `hi[k]`.

Ein datenabhaengiges `if carry` ist nicht noetig: Das Freigabebit steuert die
Bitoperationen des Inkrementierers. Alle verbleibenden `if`-Bedingungen
haengen ausschliesslich von festen Breiten ab und werden beim Uebersetzen
aufgeloest.

## Erzeugte Instanzen

| Instanz | Eingaenge | Ausgaenge | NANDs | Tiefe | Vollstaendig gepruefte Paare |
| --- | --- | --- | --- | --- | --- |
| ADD<1> | 2 | 2 | 5 | 3 | 4 |
| ADD<2> | 4 | 3 | 19 | 8 | 16 |
| ADD<4> | 8 | 5 | 52 | 15 | 256 |

Die [Pruefergebnisse](../examples/circuits/recursive-split-add/verification.json)
enthalten Schnittstellen, Gatterzahlen und Verifikationsstatus.

| Instanz | Flaches NAND-Netz | Lesbare Verdrahtung | Konkretes Template | Referenzvektoren |
| --- | --- | --- | --- | --- |
| ADD<1> | [JSON](../examples/circuits/recursive-split-add/add-1.circuit.json) | [NAND-Liste](../examples/circuits/recursive-split-add/add-1.nand.txt) | [Template](../examples/circuits/recursive-split-add/add-1.template.json) | [Vektoren](../examples/circuits/recursive-split-add/add-1.vectors.json) |
| ADD<2> | [JSON](../examples/circuits/recursive-split-add/add-2.circuit.json) | [NAND-Liste](../examples/circuits/recursive-split-add/add-2.nand.txt) | [Template](../examples/circuits/recursive-split-add/add-2.template.json) | [Vektoren](../examples/circuits/recursive-split-add/add-2.vectors.json) |
| ADD<4> | [JSON](../examples/circuits/recursive-split-add/add-4.circuit.json) | [NAND-Liste](../examples/circuits/recursive-split-add/add-4.nand.txt) | [Template](../examples/circuits/recursive-split-add/add-4.template.json) | [Vektoren](../examples/circuits/recursive-split-add/add-4.vectors.json) |

Die `.circuit.json`-Dateien enthalten ausschliesslich das gewoehnliche
Schaltungsformat `inputs`, `gates`, `outputs` und sind unter
**Schaltbild → NAND-Schaltung bearbeiten oder importieren** importierbar.
Eingangsreferenzen sind `a0,...,a(n-1),b0,...,b(n-1)`; danach folgen die
NAND-Gatter in Auswertungsreihenfolge. Alle Referenzen sind nullbasiert.
Ausgaenge sind `c0,...,c(n-1),err`. Es gibt keine Template-Aufrufe oder
Unterbausteine mehr in diesen Dateien.

## Konkretes Template und flaches Netz

Die vorhandene Pipeline lautet:

```python
program = Template(document).instantiate({"n": 4})
circuit = synthesize(program)
flat_json = circuit.to_dict()
```

Konkretisierung ersetzt die Parameter und prueft die Schnittstelle.
`synthesize` entfaltet danach die tatsaechlichen Funktionsaufrufe, festen
Verzweigungen und Schleifen in ein flaches NAND-Netz. `bits`, Slices,
Verkettungen und `pack` beschreiben Verdrahtung; die Bitoperatoren erzeugen
die Gatter. Die Konstruktion verwendet keine Referenzvektoren. Erst danach
wird gegen Interpreter und unabhaengige Ganzzahladdition geprueft.

Fuer jedes innerhalb der Projektgrenzen erfolgreich strukturell
uebersetzbare Template ist damit eine flache Instanz verfuegbar. Beliebige
Referenzprogramme sind noch nicht alle strukturell uebersetzbar; insbesondere
datenabhaengige Verzweigungen und Ganzzahlarithmetik auf Eingangswerten
werden derzeit abgelehnt. Ausserdem gelten die Grenzen von 128 Eingangsbits,
128 Ausgangsbits und 512 NAND-Gattern. Die rekursive Quelldarstellung ist
kein Nachweis minimaler Gatterzahl.

Reproduzieren und pruefen, vom Projektverzeichnis aus:

```powershell
python -m tools.export_recursive_add
python -m unittest discover -s tests -p test_recursive_split_add.py -v
```

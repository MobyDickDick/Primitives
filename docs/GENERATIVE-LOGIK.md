# Weitere generative Templates

Sechs zusätzliche Templates verwenden die Bitbreite `t=2^w`, mit ganzzahligem
`w>=0`. Für jedes sind die konkreten Instanzen `t=1,2,4` erzeugt. Alle Werte
sind vorzeichenlos; Bit 0 ist das niederwertigste Bit.

| Template | Bedeutung | Beispiel für t=4 | Quelle | Abstraktes Template |
| --- | --- | --- | --- | --- |
| `PARITY<t>(a)` | 1 bei ungerader Anzahl gesetzter Bits, sonst 0 | `PARITY<4>(7)=1`, `PARITY<4>(15)=0` | [Quelle](../examples/templates/recursive-parity.prim) | [JSON](../examples/templates/recursive-parity.abstract.json) |
| `ISZERO<t>(a)` | 1 genau für a=0 | `ISZERO<4>(0)=1`, `ISZERO<4>(8)=0` | [Quelle](../examples/templates/recursive-iszero.prim) | [JSON](../examples/templates/recursive-iszero.abstract.json) |
| `REVERSE<t>(a)` | Kehrt die Reihenfolge aller t Bits um | `0011 → 1100`, also `3 → 12` | [Quelle](../examples/templates/recursive-reverse.prim) | [JSON](../examples/templates/recursive-reverse.abstract.json) |
| `MUX<t>(a,b,sel)` | sel=0 wählt a, sel=1 wählt b | `MUX<4>(3,12,1)=12` | [Quelle](../examples/templates/recursive-mux.prim) | [JSON](../examples/templates/recursive-mux.abstract.json) |
| `MIN<t>(a,b)` | Kleinerer der beiden Werte | `MIN<4>(9,6)=6` | [Quelle](../examples/templates/recursive-min.prim) | [JSON](../examples/templates/recursive-min.abstract.json) |
| `MAX<t>(a,b)` | Grösserer der beiden Werte | `MAX<4>(9,6)=9` | [Quelle](../examples/templates/recursive-max.prim) | [JSON](../examples/templates/recursive-max.abstract.json) |

PARITY und ISZERO liefern ein Ergebnisbit. REVERSE, MUX, MIN und MAX liefern
einen t-Bit-Port `c`. MUX hat zusätzlich zu den beiden t-Bit-Eingängen einen
1-Bit-Eingang `sel`. Die Eingangsreihenfolge ist `a`, danach gegebenenfalls `b`
und zuletzt `sel`.

## Generative Konstruktion

PARITY verknüpft die Paritäten beider Hälften mit XOR; der Basisfall liefert
das Eingangsbit. ISZERO verknüpft die beiden rekursiven Nulltests mit AND;
der Basisfall invertiert das Eingangsbit.

REVERSE kehrt beide Hälften rekursiv um und vertauscht ihre Positionen.
Die ganze Funktion besteht aus Verdrahtung und benötigt keine NAND-Gatter.
Für t=1 ist sie die Identität.

MUX halbiert beide Operanden rekursiv und reicht dasselbe Auswahlbit an beide
Teilinstanzen weiter. Der Basisfall ist `(a AND NOT(sel)) OR (b AND sel)`.
Die Vereinfachung teilt die Inversion von sel über alle Bits.

MIN und MAX setzen das vorhandene [GT-Template](GT.md) mit MUX zusammen:

```text
MIN<t>(a,b) = MUX<t>(a,b,GT<t>(a,b))
MAX<t>(a,b) = MUX<t>(b,a,GT<t>(a,b))
```

Der Vergleich entscheidet über den gesamten Operanden. Die Hälften werden
nicht unabhängig minimiert oder maximiert. Bei Gleichheit liefern beide
Funktionen den gemeinsamen Wert. Jedes abstrakte Template enthält seine
vollständige Quelle einschliesslich Hilfsfunktionen und ist separat importierbar.

## Erzeugte Instanzen

| Template | NANDs für t=1 / 2 / 4 | Vollständig geprüfte Eingaben für t=1 / 2 / 4 | Prüfbericht und Dateien |
| --- | --- | --- | --- |
| PARITY | 0 / 4 / 12 | 2 / 4 / 16 | [recursive-parity](../examples/circuits/recursive-parity/verification.json) |
| ISZERO | 1 / 4 / 10 | 2 / 4 / 16 | [recursive-iszero](../examples/circuits/recursive-iszero/verification.json) |
| REVERSE | 0 / 0 / 0 | 2 / 4 / 16 | [recursive-reverse](../examples/circuits/recursive-reverse/verification.json) |
| MUX | 4 / 7 / 13 | 8 / 32 / 512 | [recursive-mux](../examples/circuits/recursive-mux/verification.json) |
| MIN | 6 / 19 / 47 | 4 / 16 / 256 | [recursive-min](../examples/circuits/recursive-min/verification.json) |
| MAX | 6 / 19 / 47 | 4 / 16 / 256 | [recursive-max](../examples/circuits/recursive-max/verification.json) |

Jeder Ordner enthält pro Breite eine konkrete `.template.json`, die vollständige
Wahrheitstabelle `.vectors.json`, das geschlossene F-Box-Paket `.block.json`,
das vereinfachte flache NAND-Netz `.circuit.json` und eine lesbare `.nand.txt`.
Beispiel: [MUX<4> als F-Box](../examples/circuits/recursive-mux/mux-4.block.json),
[NAND-Netz](../examples/circuits/recursive-mux/mux-4.circuit.json) und
[vollständige Tabelle](../examples/circuits/recursive-mux/mux-4.vectors.json).

Alle 1170 Eingaben über die 18 Instanzen wurden gegen unabhängige Referenzen
geprüft: Quellauswertung, hierarchische Auswertung, Expansion, vereinfachtes
NAND-Netz und direkte Quellsynthese stimmen überein. Die Schaltungen entstehen
strukturell aus dem Programm bzw. den Bausteinen. Wahrheitstabellen dienen
anschliessend zur Prüfung. Die Gatterzahlen sind kein Minimalitätsnachweis.

## Bibliothek, Grenzen und Reproduktion

Beim Serverstart werden die sechs Templates und 18 konkreten Funktionen
einmalig unter **Beispiele → Rekursion** ergänzt. Die 18 F-Boxen erscheinen
unter **Unterprogramm-Bausteine**. Eigene Ordner, Beschreibungen und spätere
Verschiebungen bleiben erhalten; gelöschte Beispiele werden nicht wiederhergestellt.
PARITY<1>, REVERSE<1> und NumberOfOnes<1> haben dieselbe Wahrheitstabelle;
die Bibliothek kann deshalb dieselbe beste NAND-Implementierung verwenden.
Die Templates, konkreten Definitionen und F-Boxen bleiben separat verfügbar.

Der Referenzbereich reicht bis t=64; für MUX bis t=32, weil `2*t+1`
Eingangsbits insgesamt höchstens 128 sein dürfen. Für grössere Instanzen gilt
weiterhin die Grenze von 512 NAND-Gattern, auch vor der Vereinfachung einer
F-Box-Expansion. Die Tests prüfen t=8,16 zusätzlich mit Grenzfällen und festen
Zufallsstichproben, sowohl im Interpreter als auch als F-Box und direkte Synthese.
Eine vollständige Prüfung wird nur für t=1,2,4 beansprucht.

```powershell
python -m tools.export_generative
python -m unittest discover -s tests -p test_generative.py -v
```

Im Editor kann jedes Template mit `{"t": 1}`, `{"t": 2}` oder `{"t": 4}`
konkretisiert werden. Die Bedingungen lehnen ungültige Bitbreiten ab;
Assertions schützen auch direkte rekursive Unteraufrufe.

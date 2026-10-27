# GT: generatives GreaterThan-Template

Die [ausführbare Quelle](../examples/templates/recursive-gt.prim) und das
[abstrakte Template](../examples/templates/recursive-gt.abstract.json)
definieren `GT<t>(a,b)` für zwei vorzeichenlose t-Bit-Eingänge und ein
Ergebnisbit `c`. Es gilt `c=1` genau dann, wenn `a>b`; Gleichheit liefert 0.
`GreaterThan<t>(a,b)` ist als Alias ebenfalls aufrufbar.

## Parameter und Rekursion

Es gilt `t=2^w` mit `w ∈ ℤ`, `w ≥ 0`, also t=1,2,4,8,… . Der
Template-Parameter ist die Bitbreite **t**, nicht der Exponent w.

```text
GT<1>(a,b) = AND(a, NOT(b))

GT<t>(a,b) = GT<t//2>(Upper<t>(a), Upper<t>(b))
             OR (Equal<t//2>(Upper<t>(a), Upper<t>(b))
                 AND GT<t//2>(Lower<t>(a), Lower<t>(b)))     # t > 1
```

`Upper<t>` und `Lower<t>` erhalten die gesamte Eingangsbreite t und liefern
je t//2 Bits. Daher steht auch im Gleichheitstest `Upper<t>`; das in der
Anfrage dort notierte `Upper<t//2>` würde noch einmal halbieren und die
falschen Bits vergleichen. Bei LSB-first-Verdrahtung gilt:

```text
Lower<t>(a) = pack(bits(a,t)[:t//2])
Upper<t>(a) = pack(bits(a,t)[t//2:])
```

Die obere Hälfte entscheidet zuerst. Nur bei gleichen oberen Hälften
entscheidet der Vergleich der unteren Hälften. Die beiden Bedingungen für
das Ergebnis 1 werden mit OR verbunden. Der Quelltext schreibt das als
`hi | (eq & lo)`; alle drei Werte sind einzelne Bits. Datenabhängige
Verzweigungen werden für die NAND-Synthese dadurch vermieden.

Die Hilfsfunktion `Equal<t>` implementiert die bestehende
[EQU-Rekursion](EQU.md): `NOT(XOR(a,b))` für ein Bit, sonst AND der beiden
Teilgleichheiten. In den F-Boxen wird dafür der vorhandene EQU-Baustein
verwendet. Das Template-JSON enthält die vollständige Quelle und kann
ohne zusätzliche Bibliothek importiert werden.

Beispiele: `GT<4>(8,7)=1`, `GT<4>(7,8)=0`, `GT<4>(10,10)=0`,
`GT<4>(7,6)=1`. Im Basisfall ist nur `GT<1>(1,0)=1`.

## Generierte Instanzen und Verifikation

| t | Flache NANDs | Tiefe | Vollständig geprüfte Eingabepaare | F-Box-Paket | NAND-Netz | Lesbare NAND-Liste |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 3 | 3 | 4 | [Box](../examples/circuits/recursive-gt/gt-1.block.json) | [JSON](../examples/circuits/recursive-gt/gt-1.circuit.json) | [Text](../examples/circuits/recursive-gt/gt-1.nand.txt) |
| 2 | 12 | 6 | 16 | [Box](../examples/circuits/recursive-gt/gt-2.block.json) | [JSON](../examples/circuits/recursive-gt/gt-2.circuit.json) | [Text](../examples/circuits/recursive-gt/gt-2.nand.txt) |
| 4 | 34 | 8 | 256 | [Box](../examples/circuits/recursive-gt/gt-4.block.json) | [JSON](../examples/circuits/recursive-gt/gt-4.circuit.json) | [Text](../examples/circuits/recursive-gt/gt-4.nand.txt) |

Jede rekursive Box enthält zwei `GT<t//2>`-Instanzen, eine `EQU<t//2>`-Instanz
für die oberen Hälften und drei verbindende NANDs:
`NAND(NOT(hi), NAND(eq,lo))`. Upper/Lower sind reine Verdrahtung.
Die Pakete enthalten alle Abhängigkeiten mit festen Versionskennungen.

Vor der Vereinfachung benötigen die Hierarchien 3, 14 und 43 NANDs.
Die Vereinfachung teilt identische Gatter und entfernt doppelte Inversionen.
Eine minimale Gatterzahl ist damit nicht bewiesen.

Die [Prüfberichte](../examples/circuits/recursive-gt/verification.json)
und vollständigen `.vectors.json`-Tabellen stehen neben den Schaltungen.
Alle 276 Eingabepaare für t=1,2,4 wurden unabhängig gegen Ganzzahlvergleich
geprüft: Quellauswertung, F-Box-Auswertung, Expansion, vereinfachtes Netz
und direkte Quellsynthese stimmen überein.

Das Template unterstützt als Referenz t=1,2,4,8,16,32,64, entsprechend der
Grenze von insgesamt 128 Eingangsbits. Die direkte Quellsynthese funktioniert
bis t=32 (364 NANDs); t=64 überschreitet die Grenze von 512 NANDs.
Die unverkleinerte F-Box-Expansion funktioniert bis t=16; bei t=32 greift
ihre Gattergrenze bereits vor der Vereinfachung. Grössere Breiten werden
daher über das Template und die direkte Synthese erzeugt.

Die Tests prüfen zusätzlich t=8,16,32,64 mit gleichen Werten, Grenzfällen,
festen Zufallsstichproben und Unterschieden an jeder Bitposition in beiden
Richtungen. Ein höheres unterschiedliches Bit wird auch gegen ausschliesslich
entgegengesetzte niedrigere Bits geprüft. Bei t=64 wird die Referenzauswertung
getestet, bei t≤32 auch die direkte Synthese und bei t≤16 zusätzlich die
Hierarchie. Diese grösseren Breiten sind anhand von Stichproben geprüft.

## Bibliothek und Reproduktion

Beim nächsten Serverstart werden Template und Funktionen `GT<1>`, `GT<2>`,
`GT<4>` unter **Beispiele → Rekursion** ergänzt. Die drei F-Box-Pakete stehen
unter **Unterprogramm-Bausteine** bereit. Eigene Ordnerzuordnungen bleiben
erhalten; nach der Installation gelöschte Beispiele werden nicht erneut angelegt.

Im Template-Editor lässt sich etwa mit `{"t": 8}` eine weitere Breite
konkretisieren und direkt in NAND übersetzen. Bedingungen prüfen die Bitbreite
vor der Konkretisierung; Assertions schützen auch direkte Unteraufrufe.

```powershell
python -m tools.export_gt
python -m unittest discover -s tests -p test_gt.py -v
```

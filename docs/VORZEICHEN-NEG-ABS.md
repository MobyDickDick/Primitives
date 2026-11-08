# GEN-09: Vorzeichen, Negation und Absolutwert

`SIGN<t>(a)`, `NEG<t>(a)` und `ABS<t>(a)` interpretieren `a[t]` als
**Zweierkomplementzahl** im Bereich `-2**(t-1)` bis `2**(t-1)-1`.
Alle Bitarrays und Ports sind LSB-first. An der Programmschnittstelle werden
Bitmuster weiterhin als unsigned Ganzzahlen übertragen: bei t=4 steht 15
für -1 und 8 für -8. Das gilt auch für den Ergebnisport `c[t]`.

| Template | Ergebnis | Status |
| --- | --- | --- |
| SIGN | negative[1]: 1 genau bei a<0; für null 0 | kein zusätzlicher Status |
| NEG | c[t]: -a modulo 2**t | overflow[1]: 1 genau bei a=-2**(t-1) |
| ABS | c[t]: abs(a) modulo 2**t | overflow[1]: 1 genau bei a=-2**(t-1) |

SIGN ist ein Vorzeichenbit, keine dreistufige Signumfunktion. NEG und ABS
verwenden eine **modulare Ergebnisdarstellung mit separatem Overflowbit**.
Beim kleinsten negativen Wert bleibt das Eingangsbitmuster erhalten.
Dieses Ergebnis bleibt als signed Zahl negativ und ist bei gesetztem
Overflowbit kein darstellbarer positiver Absolutwert. Es gibt keine Sättigung
und keine implizite Verbreiterung.

Beispiele mit t=4 (signed Werte):

| a | SIGN | NEG: c / overflow | ABS: c / overflow |
| --- | --- | --- | --- |
| 0 | 0 | 0 / 0 | 0 / 0 |
| 7 | 0 | -7 / 0 | 7 / 0 |
| -1 | 1 | 1 / 0 | 1 / 0 |
| -7 | 1 | 7 / 0 | 7 / 0 |
| -8 | 1 | -8 / 1 | -8 / 1 |

Bei t=1 ist der signed Bereich {-1,0}. NEG und ABS geben für -1 das
Bitmuster 1 und overflow=1 aus, für null `[0,0]`. Alle drei Ein-Bit-Netze
brauchen nur direkte Leitungen.

## Editierbare Quellen und F-Boxen

Die eigenständig editierbaren Quellen
[signed-sign.prim](../examples/templates/signed-sign.prim),
[signed-neg.prim](../examples/templates/signed-neg.prim) und
[signed-abs.prim](../examples/templates/signed-abs.prim) sowie ihre abstrakten
`.abstract.json`-Templates verwenden feste Bitverdrahtung, boolesche Operationen
und Schleifen über die statische Breite. Die Eingabewerte werden weder als
Ganzzahl negiert noch mit einer eingabeabhängigen Verzweigung ausgewählt.

SIGN verdrahtet direkt das höchste Eingangsbit. `FlipAddOne<t>(a,flip)`
invertiert jedes Bit mit XOR und addiert das Steuerbit als initialen Carry.
Für flip=1 entsteht die Zweierkomplement-Negation, für flip=0 die Identität.
NEG verwendet konstant 1, ABS das Vorzeichenbit als Steuerung.
`MinNegative<t>(a)` erkennt ein gesetztes Vorzeichenbit bei ausschliesslich
nullen in den unteren Bits; die leere untere Hälfte bei t=1 ist abgedeckt.

NEG- und ABS-F-Boxen zeigen die beiden Unter-FBoxen **arithmetic** und
**overflow**. Sie lassen sich unabhängig bis zu den NANDs öffnen. Die
flachen Exportnetze entstehen durch Expansion und Vereinfachung; diese kann
gemeinsame Zwischenergebnisse über die Unter-FBox-Grenzen zusammenführen.

## Vollständige kleine Exporte

Für jede Operation sind t=1,2,4 mit allen 22 Bitmustern vollständig geprüft:
insgesamt **neun F-Boxen/NAND-Netze und 66 Eingabefälle**. Eine unabhängige
Ganzzahlreferenz prüft Quellprogramm, direkte Synthese, F-Box, expandiertes
und vereinfachtes Netz. Weitere Tests prüfen doppelte Negation,
ABS(-a)=ABS(a), ABS(ABS(a))=ABS(a), Null, beide Bereichsgrenzen und alle
Eingaben/Steuerbits der bedingten Negationsstufe.

| t | Eingabefälle je Operation | SIGN: NANDs / Tiefe | NEG: NANDs / Tiefe | ABS: NANDs / Tiefe |
| --- | --- | --- | --- | --- |
| 1 | 2 | 0 / 0 | 0 / 0 | 0 / 0 |
| 2 | 4 | 0 / 0 | 8 / 4 | 12 / 6 |
| 4 | 16 | 0 / 0 | 20 / 8 | 36 / 10 |

Tiefe bezeichnet die längste NAND-Abhängigkeit, keine gemessene Laufzeit.
Gatterzahl und Tiefe sind Konstruktionswerte ohne Minimalitätsnachweis.
Im [Exportordner](../examples/circuits/signed/verification.json) liegen je
Instanz `.template.json`, `.vectors.json`, `.block.json`, `.circuit.json`
und `.nand.txt` sowie der gemeinsame Prüfbericht.

## Grössere Referenzen und Grenzen

SIGN erlaubt `1<=t<=128`. NEG und ABS erlauben `1<=t<=127`, weil ihre
Ausgangsseite zusammen mit dem Overflowbit t+1 Bits benötigt. Diese Grenze
gilt auch für die internen gepackten Ergebnisse. Breiten ohne Zweierpotenz
sind erlaubt. Template- und direkte Funktionsaufrufe prüfen ihre Bedingungen.
Referenzen für 3,5,8,16,32,64,127 Bit und SIGN mit 128 Bit sind mit gezielten
Grenzfällen und reproduzierbaren Stichproben geprüft. Das unveränderte
Anweisungsbudget reicht auch für die maximalen Referenzbreiten.
Diese grösseren Eingaberäume sind **nicht vollständig geprüft**.

Die **512-NAND-Gattergrenze** gilt bereits während der Konstruktion, vor
der abschliessenden Vereinfachung:

| Operation | Letzte direkte Synthese | Letzte F-Box-Expansion (vereinfacht) |
| --- | --- | --- |
| SIGN | 128 Bit: 0 NANDs, Tiefe 0 | 128 Bit: 0 NANDs, Tiefe 0 |
| NEG | 85 Bit: 506 NANDs, Tiefe 170 | 57 Bit: 338 NANDs, Tiefe 114 |
| ABS | 43 Bit: 504 NANDs, Tiefe 88 | 43 Bit: 504 NANDs, Tiefe 88 |

Die jeweils nächste NEG-/ABS-Breite überschreitet das Konstruktionsbudget.
NEG hat bei getrennter Expansion von Ergebnis und Overflow mehr Gatter vor
der Vereinfachung; die spätere Zusammenführung kann die Grenze nicht
nachträglich umgehen. Referenzen oberhalb dieser Hardwaregrenzen bleiben
ausführbar, sind jedoch nicht als NAND-Netze bzw. F-Boxen exportierbar.
Ein Datensatz bleibt auf höchstens 65536 Vektoren beschränkt.

## Einmalige Bibliotheksmigration und Reproduktion

Beim nächsten Serverstart ergänzt `signed-v1` drei Templates und neun
vollständig geprüfte Funktionen unter **Beispiele → Grundrechenarten →
Vorzeichen, NEG & ABS** sowie neun wiederverwendbare F-Boxen. Vorhandene
Ordner, Namen, Beschreibungen, Zuordnungen (auch implizite Standardordner)
und gleich gute oder bessere Lösungen bleiben erhalten. Der Marker
verhindert das erneute Anlegen später gelöschter Funktionen, Templates und
F-Boxen. Die Tests prüfen unter anderem den Erhalt einer vorhandenen
7-NAND-Lösung für NEG<2> gegenüber dem generischen 8-NAND-Export.

HTTP-Tests prüfen Katalog, direkte Synthese, sämtliche 4-Bit-Eingaben und
Navigation in beide Unter-FBoxen. Server neu starten und Browserseite neu laden.

```powershell
python -m tools.export_signed
python -m unittest discover -s tests -p test_signed.py -v
```

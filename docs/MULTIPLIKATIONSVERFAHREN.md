# GEN-11: Array- und Wallace-Multiplikation

`ARRAY_MUL<p,q>(a,b)` und `WALLACE_MUL<p,q>(a,b)` berechnen das vollständige
**unsigned** Produkt zweier unabhängig breiter Eingänge `a[p]` und `b[q]`.
Der einzige Ausgang `c[p+q]` erfüllt immer `c=a*b`. Es gibt weder Sättigung
noch Overflow- oder Fehlerflags. Alle Bitarrays und Ports sind LSB-first.
Beispielsweise ergibt 15×15 bei 4/4 Bit den Wert 225, und 4×4 ergibt 16.

## Editierbare Quellen und Reduktionsverfahren

- [Array-Quelle](../examples/templates/array-mul.prim) und
  [abstraktes Template](../examples/templates/array-mul.abstract.json).
- [Wallace-Quelle](../examples/templates/wallace-mul.prim) und
  [abstraktes Template](../examples/templates/wallace-mul.abstract.json).

`MulRow<p,q,i>` bildet eine feste Teilproduktzeile: Bit `i+j` ist
`a[j] AND b[i]`, alle anderen Bits sind null. Der schmalere Operand bestimmt
die Zeilenzahl; bei p<q werden Eingänge und Parameter intern vertauscht.
Das ändert weder die externe Schnittstelle noch die Bitreihenfolge.

Ein `MulCSA<w>`-Kompressor reduziert drei Zeilen auf zwei:

```text
parity[i] = x[i] XOR y[i]
sum[i] = parity[i] XOR z[i]
carry[0] = 0
carry[i+1] = (x[i] AND y[i]) OR (parity[i] AND z[i])
```

Alle Stellen innerhalb einer Kompressorstufe arbeiten unabhängig voneinander.
Es gibt dort keine Übertragskette von Bit zu Bit. Die beiden Ergebniszeilen
werden als `sum + carry*2**w` in einem gepackten 2*w-Bit-Zwischenwert
transportiert; ihre arithmetische Summe ist dagegen `sum+carry`.
Allgemein gilt diese Identität modulo 2**w. Bei den Multiplikatoren ist jede
Zwischensumme eine Summe nichtnegativer Teilprodukte und höchstens das
vollständige Produkt. Sie passt daher in w=p+q Bits; das weggelassene oberste
Carry kann hier keinen Produktwert abschneiden.

Das **Array** beginnt mit zwei Teilproduktzeilen und nimmt je Stufe eine
weitere Zeile dazu. Es entstehen max(0,min(p,q)-2) hintereinander liegende
3:2-Kompressorstufen. Bei nur einer Zeile wird diese direkt ausgegeben.

Der **Wallace-Baum** gruppiert auf jeder Ebene jeweils drei vorhandene
Zeilen zu zwei neuen. Eine oder zwei übrige Zeilen werden unverändert
weitergereicht. Alle Kompressoren einer Ebene lesen ausschliesslich die
vorherige Ebene. Die Zeilenzahl folgt `n -> 2*(n//3)+n%3`, bis höchstens zwei
Zeilen übrig sind. Dies ist eine zeilenweise Carry-Save-Baumreduktion;
Nullstellen werden bei der Synthese vereinfacht. Es wird kein zusätzliches
spaltenweise optimiertes Wallace- oder Dadda-Packing behauptet.

Beide Verfahren verwenden zum Schluss denselben Ripple-Carry-Addierer
`MulFinish<w>`. Sämtliche Schleifen, Verzweigungen und Indizes hängen nur von
festen Parametern ab. Die eigentliche Datenverarbeitung besteht aus einzelnen
AND-, OR- und XOR-Bits; eine Wahrheitstabellensynthese wird nicht verwendet.

## Kleine Exporte und Kostenvergleich

Je Verfahren sind alle neun Kombinationen p,q=1,2,4 mit **484 Eingabepaaren**
vollständig unabhängig geprüft: zusammen **968 Fälle**, 18 wiederverwendbare
F-Boxen und 18 flache NAND-Netze. Die F-Boxen enthalten die direkt
synthetisierten NANDs; sie haben keine zusätzlichen verschachtelten
Kompressor-Unterboxen. Quelle, direkte Synthese, F-Box, Expansion und
vereinfachtes Netz werden gegen Python-Ganzzahlmultiplikation geprüft.
Auch die beiden Vergleichsverfahren werden auf allen kleinen Eingaben
gegen dieselbe Referenz geprüft.

Der Vergleich verwendet dieselben Eingänge und p+q Produktbits sowie dieselbe
strukturelle NAND-Synthese. Beim vorhandenen rekursiven Verfahren wird
`MUL_raw<w>` mit Nullerweiterung auf die nächste Zweierpotenzbreite verwendet.
Das öffentliche `MUL<w>` liefert bei Überschreiten von w Produktbits `[0,1]`
und wäre deshalb für diesen Vergleich nicht funktionsgleich. Die für den
vollen Produktvergleich unbenötigten oberen Nullbits werden entfernt.

| p | q | Fälle je Verfahren | Array: NANDs / Tiefe | Wallace: NANDs / Tiefe | Schiebe-Addier-Standard | Rekursiver Vollproduktkern |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 4 | 5 / 3 | 5 / 3 | 5 / 3 | 5 / 3 |
| 1 | 2 | 8 | 7 / 3 | 7 / 3 | 7 / 3 | 7 / 3 |
| 1 | 4 | 32 | 11 / 3 | 11 / 3 | 11 / 3 | 11 / 3 |
| 2 | 1 | 8 | 7 / 3 | 7 / 3 | 7 / 3 | 7 / 3 |
| 2 | 2 | 16 | 18 / 7 | 18 / 7 | 18 / 7 | 18 / 7 |
| 2 | 4 | 64 | 44 / 12 | 44 / 12 | 54 / 17 | 64 / 19 |
| 4 | 1 | 32 | 11 / 3 | 11 / 3 | 11 / 3 | 11 / 3 |
| 4 | 2 | 64 | 44 / 12 | 44 / 12 | 44 / 12 | 64 / 19 |
| 4 | 4 | 256 | 124 / 23 | 124 / 23 | 124 / 28 | 199 / 34 |

Bis vier Zeilen fallen die Reduktionspläne beider neuer Verfahren zusammen.
Der Standard verarbeitet die Operanden dagegen in ihrer ursprünglichen
Reihenfolge; deshalb unterscheiden sich dort 2/4 und 4/2.
Für grössere gleiche Breiten zeigen die Konstruktionswerte:

| p=q | Array: NANDs / Tiefe | Wallace: NANDs / Tiefe | Standard | Rekursiver Vollproduktkern | Prüfung der neuen Verfahren |
| --- | --- | --- | --- | --- | --- |
| 5 | 210 / 31 | 210 / 31 | 210 / 38 | 335 / 50 | Grenzfälle und Stichproben |
| 6 | 318 / 39 | 333 / 38 | 318 / 48 | Konstruktionsgrenze überschritten | Grenzfälle und Stichproben |

Bei sechs Zeilen ist der Baum eine NAND-Ebene flacher, braucht hier aber
15 zusätzliche NANDs. Tiefe bezeichnet die längste NAND-Abhängigkeit,
keine gemessene Laufzeit. Es gibt **keinen Minimalitätsnachweis** und keine
generelle Garantie, dass ein Verfahren weniger Gatter oder Tiefe benötigt.

Im [Exportordner](../examples/circuits/multipliers/verification.json) stehen
je Instanz `.template.json`, `.vectors.json`, `.block.json`, `.circuit.json`
und `.nand.txt`; der Prüfbericht enthält Gatterzahl, Tiefe und Vergleich.

## Parameter, grössere Referenzen und Grenzen

Für beide Templates gilt `p>=1`, `q>=1`, `p+q<=64`. Der interne Kompressor
transportiert 2*(p+q) Bits und erreicht damit maximal die **128-Bit-Arraygrenze**.
Die externen Eingangs- und Ausgangsseiten bleiben jeweils bei höchstens
64 Bits und damit unter der allgemeinen 128-Bit-Portgrenze.
Breiten ohne Zweierpotenz sind zulässig.

Beim Wallace-Template gilt zusätzlich `min(p,q)*(p+q)<=128`, weil alle
Teilproduktzeilen einer Ebene in einem flachen Bitarray gespeichert werden.
8/8 erreicht genau 128 Bits; 9/9 und 4/29 sind deshalb unzulässig.
Beim Array werden nur die beiden laufenden Zeilen und die nächste
Teilproduktzeile benötigt. Die öffentlichen Funktionsaufrufe prüfen dieselben
Bedingungen wie die Template-Spezialisierung.

Die **512-NAND-Gattergrenze gilt bereits während der Konstruktion**, vor
abschliessender Kompaktierung. Für gleiche Breiten sind 6/6 auf beiden Wegen
zulässig; 7/7 und 8/8 überschreiten die Grenze und werden weder als NAND-Netz
noch als F-Box ausgeliefert. Bei ungleichen Breiten gelten andere Kosten:
1/63 und 63/1 funktionieren mit 129 NANDs und Tiefe 3.

Die Referenzprogramme sind mit 3/5, 5/3, 5/5, 6/6, 7/7, 8/8, 16/4, 1/63
und 63/1 anhand von Grenzfällen und reproduzierbaren Stichproben geprüft.
Dabei werden auch mehrere Baumebenen und beide Restzeilenfälle geprüft.
Diese grösseren Eingaberäume sind **nicht vollständig geprüft**. Die
allgemeinen Schritt-, Iterations- und Gesamtbudgets gelten zusätzlich zu
den Breiten- und Gattergrenzen; eine formal zulässige Breite garantiert
keine beliebig grosse Referenzausführung.

## Bibliotheksmigration und Reproduktion

Beim nächsten Serverstart ergänzt `multipliers-v1` zwei Templates und
18 vollständig geprüfte Funktionen sowie 18 F-Boxen unter **Beispiele →
Grundrechenarten → Array- & Wallace-Multiplikation**. Bestehende Ordner,
Namen, Beschreibungen, explizite und implizite Zuordnungen sowie gleich gute
oder bessere Lösungen bleiben erhalten. Geprüft ist unter anderem eine
vorhandene 4-NAND-Lösung für 1/1 gegenüber dem generischen 5-NAND-Export.
Später gelöschte Funktionen, Templates und F-Boxen bleiben gelöscht.
Der ursprüngliche Beispielinstaller überlässt die Templates dieser Migration.

Nach dem Update den lokalen Server neu starten und die Browserseite neu laden.

```powershell
python -m tools.export_multipliers
python -m unittest discover -s tests -p test_multipliers.py -v
```

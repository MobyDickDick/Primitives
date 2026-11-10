# GEN-10: Signed Vergleiche und Grundrechenarten

`SCMP<p,q>`, `SADD<p,q>`, `SSUB<p,q>`, `SMUL<p,q>` und `SDIV<p,q>`
interpretieren `a[p]` und `b[q]` als unabhängig breite Zweierkomplementzahlen.
Der signed Wertebereich einer n-Bit-Zahl ist `-2**(n-1)` bis `2**(n-1)-1`.
Alle Arrays sind LSB-first. Die Ports übertragen **unsigned Bitmuster**:
bei vier Bits bedeutet 15 den Wert -1 und 8 den Wert -8. Die signed Semantik
ist ausdrücklich als Bitlogik im Template implementiert; der Synthesizer
benötigt dafür keine signed Ports.

## Ergebnisbreiten und Fehlerflags

Diese Semantik ist die gemeinsame Schnittstelle von Quelle, F-Box, NAND-Netz
und Referenz. Mit `w=max(p,q)` gilt:

| Template | Ergebnisports | Darstellung und Status |
| --- | --- | --- |
| SCMP | lt[1], eq[1], gt[1] | a<b, a==b, a>b; genau ein Bit ist gesetzt |
| SADD | c[w], overflow[1] | a+b modulo 2**w; Overflow bei nicht darstellbarer signed Summe |
| SSUB | c[w], overflow[1] | a-b modulo 2**w; Overflow bei nicht darstellbarer signed Differenz |
| SMUL | c[p+q] | vollständiges signed Produkt; kein Overflow möglich |
| SDIV | c[p], rest[q], valid[1], div0[1], overflow[1] | Quotient gegen null gerundet; Rest hat das Vorzeichen von a oder ist null |

Addition und Subtraktion erweitern schmalere Eingänge mit ihrem Vorzeichenbit
auf w Bits. `overflow` bedeutet Überschreiten des signed Ergebnisbereichs,
kein unsigned Carry oder Borrow. Es gibt keine Sättigung. Bei Multiplikation
reichen p+q Bits auch für das Produkt beider kleinster negativer Werte.

Bei gültiger Division gilt `a=c*b+rest` und `abs(rest)<abs(b)`.
Anders als Python `//` rundet SDIV **gegen null**. Beispiele mit p=q=4:

| a | b | c (signed) | rest (signed) | valid | div0 | overflow |
| --- | --- | --- | --- | --- | --- | --- |
| -7 | 3 | -2 | -1 | 1 | 0 | 0 |
| 7 | -3 | -2 | 1 | 1 | 0 | 0 |
| -7 | -3 | 2 | -1 | 1 | 0 | 0 |
| -8 | -1 | -8 (modulares Bitmuster) | 0 | 0 | 0 | 1 |
| -8 | 0 | 0 | 0 | 0 | 1 | 0 |

`MIN_p/-1` ist der einzige Quotientenüberlauf. Er hängt von der Breite p
des Dividenden ab, auch bei p!=q. Der Quotient bleibt modulo 2**p als MIN_p
erhalten, rest=0. Bei b=0 werden beide Ergebniswörter null; div0 hat Vorrang
und overflow bleibt 0. `valid=1` bedeutet bei SDIV, dass **kein** Fehlerflag
gesetzt ist. Für p=1 besteht der Eingangsbereich aus {-1,0}; -1/-1 läuft
im Ein-Bit-Quotienten über. Schon ein Ein-Bit-Divisor kann nur -1 oder 0 sein.

## Editierbare Quellen und Konstruktion

Die Quellen [signed-cmp.prim](../examples/templates/signed-cmp.prim),
[signed-add.prim](../examples/templates/signed-add.prim),
[signed-sub.prim](../examples/templates/signed-sub.prim),
[signed-mul.prim](../examples/templates/signed-mul.prim) und
[signed-div.prim](../examples/templates/signed-div.prim) sowie ihre
`.abstract.json`-Templates sind eigenständig editierbar.

SCMP erweitert beide Vorzeichen und invertiert das höchste Bit, wodurch
die unsigned Vergleichsreihenfolge der signed Reihenfolge entspricht.
Ein fester Vergleich von oben nach unten bildet die drei Relationen.
SADD/SSUB verwenden Ripple-Carry mit bedingter Invertierung des zweiten
Operanden und Carry-in 0 bzw. 1. Die Vorzeichen von Eingängen und Ergebnis
bestimmen das Overflowbit.

SMUL/SDIV bilden durch XOR und Carry die Beträge, verarbeiten diese unsigned
und stellen das Ergebnisvorzeichen durch bedingte Zweierkomplement-Negation
wieder her. Auch der Betrag von MIN passt als **unsigned** Wort in seine
ursprüngliche Breite; der Overflow von ABS ist hier kein Fehler.
SMUL verwendet p*q feste Teilproduktstellen, SDIV p feste Restoring-Stufen.
Der Rest übernimmt das Dividendenvorzeichen. Es gibt keine Ganzzahlarithmetik
auf Eingangswerten und keine eingabeabhängige Steuerverzweigung.

Die F-Boxen besitzen die genannten Ports und enthalten die direkt synthetisierte
NAND-Schaltung. Sie sind als eigenständige, wiederverwendbare Bausteine bis
zu ihren NANDs darstellbar; sie führen keine zusätzliche Unter-FBox-Hierarchie ein.

## Vollständige kleine Exporte

Alle neun Kombinationen p,q=1,2,4 sind je Operation vollständig geprüft:
**45 F-Boxen/NAND-Netze und insgesamt 2420 Eingabefälle**. Eine unabhängige
Ganzzahlreferenz prüft Quellprogramm, F-Box, Expansion, vereinfachtes Netz
und direkte Synthese. Die Tests dekodieren beide Eingänge unabhängig und
prüfen auch Division mit korrigierter Python-Floor-Division, Restidentität,
Restvorzeichen, Nullteiler, MIN/-1, Ein-Bit-Semantik und Bereichsgrenzen.

Für gleiche Breiten ergeben sich folgende Konstruktionskosten (NANDs / Tiefe):

| p=q | SCMP | SADD | SSUB | SMUL | SDIV |
| --- | --- | --- | --- | --- | --- |
| 1 | 11 / 6 | 11 / 8 | 16 / 10 | 18 / 11 | 37 / 13 |
| 2 | 23 / 12 | 20 / 11 | 26 / 14 | 75 / 21 | 120 / 33 |
| 4 | 49 / 16 | 38 / 15 | 46 / 18 | 253 / 46 | 376 / 75 |

Die Tiefe misst NAND-Abhängigkeiten, keine Laufzeit. Es gibt keinen
Minimalitätsnachweis. Der [Exportordner](../examples/circuits/signed-arithmetic/verification.json)
enthält je Instanz `.template.json`, `.vectors.json`, `.block.json`,
`.circuit.json` und `.nand.txt` sowie den gemeinsamen Prüfbericht.

## Referenz-, Port- und Gattergrenzen

Für SCMP/SADD/SSUB gelten `p>=1`, `q>=1` und `p+q<=128`.
Damit sind auch der w+1-Bit-Ausgang und die internen Wörter zulässig.
SMUL und SDIV begrenzen ihre Referenzbreiten zusätzlich auf **p,q<=16**,
damit die festen quadratischen Verfahren im unveränderten Budget von
100000 Anweisungen je Eingabe bleiben. Die Templatebedingungen prüfen
auch die Portgrenzen (SMUL p+q<=128; SDIV p+q+3<=128). Direkte öffentliche
Funktionsaufrufe prüfen dieselben effektiven Breitenbedingungen.
Ein Datensatz umfasst weiterhin höchstens 65536 Vektoren; bei grossen
Breiten oder ausgeschöpftem Gesamtbudget sind kleinere Stichproben nötig.

Referenzen für (3,5), (5,3), (8,8), (16,16) sind mit gezielten Grenzfällen
und reproduzierbaren Stichproben geprüft. Für SCMP/SADD/SSUB kommen (64,64),
(1,127) und (127,1) hinzu. Diese Eingaberäume sind **nicht vollständig geprüft**.
Die erlaubte Referenzbreite garantiert keinen NAND-Export.

Die Grenze von **512 NANDs gilt bereits während der Konstruktion**, vor der
abschliessenden Kompaktierung. Für p=q sind die letzten direkten Synthesen:

| Operation | Letzte gleiche Breite | NANDs / Tiefe nach Kompaktierung |
| --- | --- | --- |
| SCMP | 36 / 36 | 465 / 80 |
| SADD | 46 / 46 | 416 / 99 |
| SSUB | 42 / 42 | 426 / 94 |
| SMUL | 5 / 5 | 375 / 56 |
| SDIV | 4 / 4 | 376 / 75 |

Die jeweils nächste gleiche Breite überschreitet die Konstruktionsgrenze.
Bei ungleichen Breiten ändern sich die Kosten; die Gatterprüfung bleibt
verbindlich. Eine spätere Vereinfachung umgeht diese Grenze nicht.

## Bibliotheksmigration und Reproduktion

Beim nächsten Serverstart ergänzt `signed-arithmetic-v1` fünf Templates und
45 vollständig geprüfte Funktionen samt 45 F-Boxen unter **Beispiele →
Grundrechenarten → Signed Vergleiche & Grundrechenarten**. Bestehende Ordner,
Namen, Beschreibungen, explizite und implizite Zuordnungen sowie gleich gute
oder bessere Lösungen bleiben erhalten. Geprüft ist unter anderem eine
vorhandene 7-NAND-Lösung für SCMP<1,1> gegenüber dem generischen 11-NAND-Export.
Der Marker verhindert, dass später gelöschte Beispiele erneut erscheinen.
Der ursprüngliche Installer überlässt die neuen Templates dieser Migration.

HTTP-Tests prüfen die Migration, den Katalog, direkte Synthese aller fünf
4/4-Bit-Templates, Bausteinauswertung und Schaltungsansicht. Nach dem Update
den lokalen Server neu starten und die Browserseite neu laden.

```powershell
python -m tools.export_signed_arithmetic
python -m unittest discover -s tests -p test_signed_arithmetic.py -v
```

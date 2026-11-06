# GEN-07: Carry-Lookahead durch Parallelpräfix-Addition

`CLA<p,q>(a,b)` addiert zwei unabhängig breite **unsigned** Eingänge
`a[p]` und `b[q]`. Mit `w=max(p,q)` liefert die Schnittstelle `c[w]`
und `carry[1]`:

```text
c = (a+b) modulo 2**w
carry = 1 genau dann, wenn a+b >= 2**w
vollständige Summe = c + carry * 2**w
```

Der eingehende Carry ist fest 0. Der schmalere Operand wird oben mit Nullen
erweitert. Alle Ports und Bitarrays sind LSB-first. Es gibt weder Sättigung
noch eine Fehlerdarstellung: Beispielsweise liefert `CLA<4,4>(15,1)`
`[0,1]`, die vollständige Summe ist 16; `CLA<1,4>(1,15)` ebenso.

## Quelle und Generate-/Propagate-Netz

Die [editierbare Quelle](../examples/templates/parallel-prefix-add.prim)
und das [abstrakte Template](../examples/templates/parallel-prefix-add.abstract.json)
verwenden ausschliesslich feste Bitverdrahtung und boolesche Operationen.
Parameterbedingungen und direkte Funktionsbedingungen sind `1<=p,q<=64`.
Auch Breiten ohne Zweierpotenz sind zulässig.

Zunächst entstehen pro Bit `P[i]=a[i] XOR b[i]` und `G[i]=a[i] AND b[i]`.
Ein Gruppenpaar beschreibt die Carry-Funktion `G OR (P AND carry_in)`.
Benachbarte Gruppen werden assoziativ verbunden:

```text
G_neu[i] = G_alt[i] OR (P_alt[i] AND G_alt[i-d])
P_neu[i] = P_alt[i] AND P_alt[i-d]
```

Die festen Abstände sind `d=1,2,4,...<w` (Kogge-Stone-Präfixnetz).
Jede Stufe liest vollständig die **vorherige** Stufe; es gibt keine serielle
Überschreibung innerhalb einer Stufe. Nach `ceil(log2(w))` Stufen beschreibt
G[i] alle Bits 0 bis i und ist bei Carry-in 0 genau der Übertrag aus Bit i.
Das ursprüngliche P bleibt für die Summe erhalten:
`c[0]=P_original[0]`, `c[i]=P_original[i] XOR G[i-1]`, `carry=G[w-1]`.

Jede F-Box enthält `generate`, die vorhandenen `prefix_1`, `prefix_2`, ...
und `sum`. Die Präfixstufen haben sichtbare Propagate-/Generate-Busse und
lassen sich bis zu ihren NAND-Gattern öffnen. Bei w=1 gibt es keine Präfixstufe.
Die flachen Exporte entstehen durch Hierarchieexpansion und Vereinfachung.

## Vollständige kleine Exporte und Ripple-Carry-Vergleich

Alle neun Kombinationen p,q=1,2,4 sind mit insgesamt **484 Eingabepaaren**
vollständig geprüft. Die Referenz des Exporters verwendet Ganzzahladdition;
die Tests zählen je Volladdierer die gesetzten Bits unabhängig davon.
Quellprogramm, direkte Synthese, F-Box, expandiertes und vereinfachtes Netz
werden gegen dieselben Sollwerte geprüft. Zusätzlich werden die tatsächlichen
internen Carry-Signale für **jede Bitposition und jedes Eingabepaar** geprüft;
jeder Carry nimmt in diesen Tabellen sowohl 0 als auch 1 an.

Die Tabelle vergleicht den exportierten Präfix-Addierer mit dem vorhandenen
`Standardaddition<p,q>`-Ripple-Carry-Template. Beide berechnen dieselbe
vollständige Summe mit insgesamt w+1 Ausgangsbits, Carry-in 0 und gleichen
Eingangsbreiten; der Standard fasst Summe und Carry in einem Port zusammen.
Tiefe bedeutet die längste NAND-Abhängigkeit, keine gemessene Laufzeit.

| p | q | Eingabepaare | Präfix: NANDs / Tiefe | Ripple: NANDs / Tiefe |
| --- | --- | --- | --- | --- |
| 1 | 1 | 4 | 5 / 3 | 5 / 3 |
| 1 | 2 | 8 | 12 / 5 | 10 / 5 |
| 1 | 4 | 32 | 35 / 10 | 20 / 9 |
| 2 | 1 | 8 | 12 / 5 | 10 / 5 |
| 2 | 2 | 16 | 14 / 6 | 14 / 6 |
| 2 | 4 | 64 | 40 / 10 | 24 / 10 |
| 4 | 1 | 32 | 35 / 10 | 20 / 9 |
| 4 | 2 | 64 | 40 / 10 | 24 / 10 |
| 4 | 4 | 256 | 46 / 10 | 32 / 10 |

Bei diesen kleinen Instanzen überwiegt der Präfixaufwand. Für gleich breite
grössere Eingänge zeigt sich der Tausch zwischen Fläche und Tiefe:

| p=q | Präfix: NANDs / Tiefe | Ripple: NANDs / Tiefe | Prüfung |
| --- | --- | --- | --- |
| 8 | 130 / 12 | 68 / 18 | Grenzfälle und Stichproben |
| 16 | 338 / 14 | 140 / 34 | Grenzfälle und Stichproben |

Gatterzahl und Tiefe sind Konstruktionswerte ohne Minimalitätsnachweis.
Die direkte Synthese der gesamten Quelle kann Konstanten der Nullerweiterung
schon vor dem Aufbau der NANDs vereinfachen. Bei ungleichen Breiten ergeben
sich dadurch andere Kosten als beim Export aus separat synthetisierten F-Boxen:
1/2 und 2/1 ergeben direkt 10/5, 1/4 und 4/1 ergeben 26/7,
2/4 und 4/2 ergeben 32/10. Die Funktion bleibt identisch. Bei gleichen
Breiten stimmen beide Wege auch strukturell überein.

Im [Exportordner](../examples/circuits/parallel-prefix-add/verification.json)
stehen neun `.template.json`, `.vectors.json`, `.block.json`, `.circuit.json`
und `.nand.txt` sowie der Prüfbericht mit Kostenvergleich je Instanz.

## Grössere Referenzen und Grenzen

Die interne Zusammenfassung von P und G braucht `2*w` Bits. Daher begrenzt
dieses Template p und q jeweils auf 64, selbst wenn ein einzelner externer
Port breiter sein dürfte. Bei p=q=64 ist die gemeinsame Eingangsgrenze
von **128 Bits** genau erreicht; die Ausgänge brauchen 65 Bits.

Die **512-NAND-Gattergrenze** gilt auch während der Konstruktion, bevor
unbenutzte Zwischenergebnisse entfernt werden. Für gleiche Breiten sind
18/18 auf beiden Wegen geprüft (400 NANDs, Tiefe 16); 19/19 funktioniert
als F-Box (431 NANDs, Tiefe 16), überschreitet jedoch das Konstruktionsbudget
der direkten Synthese. Ab 20/20 überschreitet auch die Hierarchieexpansion
512 Gatter. Diese Aussagen betreffen gleiche Breiten; bei ungleichen Breiten
hängen die Kosten zusätzlich von der Nullerweiterung ab.

Referenzprogramme sind für 3/5, 5/3, 8/8, 16/16, 18/18, 19/19, 1/32,
32/1 und 32/32 mit Grenzfällen, Carry-Ketten jeder Länge und reproduzierbaren
Stichproben geprüft. Diese Eingaberäume sind **nicht vollständig geprüft**.
Die unveränderten Ausführungsbudgets gelten zusätzlich zur Portgrenze:
64/64 ist formal zulässig, erreicht aber bereits bei der Referenzausführung
das Limit von 100000 Anweisungsschritten je Eingabe. Es wird deshalb weder
als ausführbares grosses Beispiel noch als NAND-Netz ausgeliefert.
Datensätze bleiben auf 65536 Vektoren begrenzt.

## Einmalige Bibliotheksmigration und Reproduktion

Beim nächsten Serverstart ergänzt `parallel-add-v1` das Template und neun
vollständig geprüfte Funktionen unter **Beispiele → Grundrechenarten →
Parallelpräfix-Addition** sowie neun wiederverwendbare F-Boxen.
Vorhandene Ordner, Beschreibungen, Benennungen, Zuordnungen und gleich gute
oder bessere Lösungen bleiben erhalten. Der Marker verhindert, dass später
gelöschte Funktionen, Templates oder F-Boxen wieder angelegt werden.

Die Tests prüfen auch eine bestehende kleinere Ripple-Lösung, Neustart,
API-Katalog, direkte Synthese, Auswertung und Navigation in die Präfixstufen.
Server neu starten und Browserseite neu laden.

```powershell
python -m tools.export_parallel_add
python -m unittest discover -s tests -p test_parallel_add.py -v
```

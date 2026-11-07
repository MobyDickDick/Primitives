# GEN-08: Unsigned Sättigungsarithmetik

`SAT_ADD<p,q>(a,b)` und `SAT_SUB<p,q>(a,b)` verwenden unabhängig breite
**unsigned** Eingänge `a[p]`, `b[q]`. Die gemeinsame Rechenbreite ist
`w=max(p,q)`; schmalere Operanden werden oben mit Nullen erweitert.
Alle Bitarrays und Ports sind LSB-first.

| Template | Ergebnisport c[w] | Statusport (1 Bit) |
| --- | --- | --- |
| SAT_ADD | min(a+b, 2**w-1) | overflow=1 genau bei a+b >= 2**w |
| SAT_SUB | max(a-b, 0) | underflow=1 genau bei a<b |

Die exakte obere Grenze setzt **kein** Overflowbit: `SAT_ADD<4,4>(14,1)`
liefert `[15,0]`, `(15,1)` liefert `[15,1]`. Die Subtraktion `(5,5)`
liefert `[0,0]`, `(4,5)` dagegen `[0,1]`. Das Statusbit unterscheidet also
ein exaktes Grenzergebnis von einer tatsächlich begrenzten Rechnung.
Für ungleiche Breiten gilt beispielsweise `SAT_ADD<1,4>(1,15)=[15,1]`,
`SAT_SUB<1,4>(1,15)=[0,1]` und `SAT_SUB<4,1>(15,1)=[14,0]`.

## Editierbare Quellen und F-Boxen

Die Quellen [sat-add.prim](../examples/templates/sat-add.prim) und
[sat-sub.prim](../examples/templates/sat-sub.prim) und die zugehörigen
abstrakten `.abstract.json`-Templates verwenden feste Bitverdrahtung,
boolesche Operationen und Schleifen über die statische Breite.
Die Rechnung selbst enthält keine Ganzzahladdition/-subtraktion der
Eingabewerte und keine eingabeabhängige Verzweigung.

`SatAddRaw<p,q>` bildet eine Ripple-Carry-Summe, `SatSubRaw<p,q>` eine
Ripple-Borrow-Differenz. Die unteren w Bits sind zunächst modular;
das zusätzliche Bit ist Carry bzw. Borrow. `SatAddClamp<w>` verknüpft
jedes Ergebnisbit mit dem Carry durch OR und setzt es bei Überlauf auf 1.
`SatSubClamp<w>` verknüpft jedes Ergebnisbit mit dem invertierten Borrow
durch AND und setzt es bei Unterlauf auf 0. Das Statusbit bleibt erhalten.

Jede F-Box zeigt die beiden Unter-FBoxen **arithmetic** und **saturate**.
Beide lassen sich bis zu den NAND-Gattern öffnen. Die exportierten flachen
Netze entstehen durch Hierarchieexpansion und Vereinfachung.

## Vollständige kleine Exporte

Für jede Operation sind alle neun Kombinationen p,q=1,2,4 mit jeweils
484 Eingabepaaren vollständig geprüft: insgesamt **18 F-Boxen/NAND-Netze
und 968 Eingabefälle**. Eine unabhängige Ganzzahlreferenz prüft Quellprogramm,
direkte Synthese, F-Box, expandiertes und vereinfachtes Netz. Die Tests
prüfen zusätzlich die Begrenzungsstufen für jedes mögliche Rohwort und
beide Statuswerte, auch bei für bestimmte Operandenbreiten unerreichbaren
Kombinationen.

| p | q | Eingabepaare pro Operation | SAT_ADD: NANDs / Tiefe | SAT_SUB: NANDs / Tiefe |
| --- | --- | --- | --- | --- |
| 1 | 1 | 4 | 7 / 5 | 9 / 5 |
| 1 | 2 | 8 | 14 / 7 | 19 / 8 |
| 1 | 4 | 32 | 28 / 11 | 37 / 12 |
| 2 | 1 | 8 | 14 / 7 | 18 / 8 |
| 2 | 2 | 16 | 19 / 8 | 25 / 9 |
| 2 | 4 | 64 | 32 / 12 | 43 / 13 |
| 4 | 1 | 32 | 28 / 11 | 36 / 12 |
| 4 | 2 | 64 | 32 / 12 | 42 / 13 |
| 4 | 4 | 256 | 41 / 12 | 55 / 13 |

Tiefe bedeutet die längste NAND-Abhängigkeit, keine gemessene Laufzeit.
Gatterzahl und Tiefe sind Konstruktionswerte ohne Minimalitätsnachweis.
Im [Exportordner](../examples/circuits/saturating/verification.json) stehen
je Instanz `.template.json`, `.vectors.json`, `.block.json`, `.circuit.json`
und `.nand.txt` sowie der gemeinsame Prüfbericht.

## Grössere Referenzen und Grenzen

Template- und direkte Funktionsbedingungen sind `1<=p,q<=127` und
`p+q<=128`. Breiten ohne Zweierpotenz sind erlaubt. Der interne gepackte
Rohwert und das Gesamtergebnis brauchen w+1 Bits, daher ist w auf 127
begrenzt. Die gemeinsame Eingangsgrenze beträgt weiterhin **128 Bits**.

Die **512-NAND-Gattergrenze** gilt bereits während der Konstruktion,
vor der Entfernung unbenutzter Zwischenergebnisse. Für gleiche Breiten:

| Operation | Letzte direkte Synthese | Letzte F-Box-Expansion |
| --- | --- | --- |
| SAT_ADD | 39/39: 426 NANDs, Tiefe 82 | 46/46: 503 NANDs, Tiefe 96 |
| SAT_SUB | 30/30: 445 NANDs, Tiefe 65 | 34/34: 505 NANDs, Tiefe 73 |

Die jeweils nächste gleiche Breite überschreitet das Konstruktionsbudget.
Bei ungleichen Breiten hängen die Kosten zusätzlich von der Nullerweiterung
ab; die Tabelle beschreibt keine allgemeine Maximalbreite.

Grössere Referenzen für 3/5, 5/3, 8/8, 16/16, 32/32, 64/64, 1/64 und 64/1
sind mit reproduzierbaren Stichproben, Gleichheit, exakten Sättigungsgrenzen
und den ersten Über-/Unterläufen geprüft. Die Hardwaregrenzen sind ebenfalls
gezielt geprüft. Diese Eingaberäume sind **nicht vollständig geprüft**.
64/64 ist als Referenz ausführbar, überschreitet aber das NAND-Budget.
127/1 und 1/127 erreichen mit jeweils 128 Eingangs- und Ausgangsbits die
Portgrenzen, überschreiten jedoch bereits bei Eingabe null das unveränderte
Ausführungsbudget von 100000 Anweisungsschritten je Eingabe. Sie werden
deshalb nicht als ausführbare Beispiele ausgeliefert.
Datensätze bleiben auf 65536 Vektoren begrenzt.

## Einmalige Bibliotheksmigration und Reproduktion

Beim nächsten Serverstart ergänzt `saturating-v1` beide Templates und
18 vollständig geprüfte Funktionen unter **Beispiele → Grundrechenarten →
Sättigungsarithmetik** sowie 18 wiederverwendbare F-Boxen. Vorhandene Ordner,
Beschreibungen, Namen, Zuordnungen und gleich gute oder bessere Lösungen
bleiben erhalten. Der Marker verhindert, dass später gelöschte Funktionen,
Templates oder F-Boxen erneut angelegt werden.

Die Tests prüfen die Migration einer bestehenden Bibliothek, unveränderten
Neustart, API-Katalog, direkte Synthese, Auswertung und Navigation in die
Begrenzungsstufen. Server neu starten und Browserseite neu laden.

```powershell
python -m tools.export_saturating
python -m unittest discover -s tests -p test_saturating.py -v
```

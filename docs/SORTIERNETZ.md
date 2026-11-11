# GEN-12: Bitonisches Sortiernetz

`SORT_NET<k,n>(a)` sortiert **2^k unsigned Kanäle mit je n Bits** aufsteigend.
Die Schnittstelle besteht aus einem gepackten Eingangsbus `a[n*2**k]` und
einem gleich breiten Ausgangsbus `c[n*2**k]`. Kanal i liegt in den Bits
`[i*n:(i+1)*n]`, jedes Wort ist LSB-first. Kanal 0 enthält am Ausgang den
kleinsten Wert. Alle Werte einschliesslich ihrer Häufigkeiten bleiben erhalten;
Duplikate sind zulässig. Es gibt keine Statusbits und keine Vorzeichenbehandlung.
Für k=0 ist das Netz die Identität.

Beispiel für k=2, n=2: Die Kanalfolge `[3,1,3,0]` wird zu `[0,1,3,3]`.
Die gepackten Buswerte sind 55 bzw. 244. Eine Stabilitätsgarantie für zusätzliche
Nutzdaten wird nicht gegeben: Die Kanäle enthalten ausschliesslich Zahlenwerte.

## Quelle, feste Stufen und F-Boxen

Die [editierbare Quelle](../examples/templates/sort-network.prim) und das
[abstrakte Template](../examples/templates/sort-network.abstract.json) verwenden
den vorhandenen `SORT2<t>` aus Vergleich und zwei Multiplexern. Dessen lokale
Halbbreitenvariable heisst hier `half`, um den Template-Parameter k freizuhalten;
die resultierenden SORT2-NAND-Schaltungen sind für n=1,2,4 identisch geprüft.

Das bitonische Netz baut Teilfolgen der Länge 2,4,8,... auf. Innerhalb einer
solchen Ebene halbiert sich der Vergleichsabstand bis 1. Kanal i wird mit
`i XOR distance` gepaart. Nur i<j erzeugt einen Vergleich. Das statische Bit
`i AND size` bestimmt, ob Minimum und Maximum aufsteigend oder absteigend
verdrahtet werden. Die letzte Ebene richtet alle Kanäle aufsteigend aus.
Alle Paare einer Stufe sind disjunkt. Schleifen, Kanalindizes und Richtungen
hängen nur von den Parametern ab; Daten werden ausschliesslich durch SORT2
verarbeitet. Die Synthese benötigt keine Wahrheitstabelle.

Für m=2**k Kanäle entstehen `k*(k+1)/2` Vergleichsstufen und
`m*k*(k+1)/4` Zweier-Sortierer. Die F-Box enthält pro Vergleich eine sichtbare
SORT2-Unterbox; darunter bleiben Vergleich und Auswahlboxen navigierbar.
Die flache Ausgabe vereinfacht die expandierten NANDs. Die strukturelle
Direktsynthese der Quelle wird zusätzlich gegen dieselbe Referenz geprüft.

## Kleine Exporte und unabhängige Prüfung

| k | Kanäle | n | Eingabefälle | SORT2-Boxen | Flach: NANDs / Tiefe | F-Box expandiert: NANDs / Tiefe |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | 1 | 4 | 1 | 9 / 5 | 11 / 6 |
| 1 | 2 | 2 | 16 | 1 | 25 / 9 | 30 / 9 |
| 1 | 2 | 4 | 256 | 1 | 59 / 11 | 75 / 11 |
| 2 | 4 | 1 | 16 | 6 | 54 / 15 | 66 / 18 |
| 2 | 4 | 2 | 256 | 6 | 150 / 27 | 180 / 27 |

Zusammen sind **548 Eingabefälle vollständig geprüft**, einschliesslich Null,
Maximalwert, gleicher Werte und beider Eingangsreihenfolgen. Python-`sorted`
liefert die unabhängige Referenz. Zusätzlich wird die Erhaltung des
Eingabemultisets mit Häufigkeiten geprüft. Quelle, F-Box, Expansion,
vereinfachtes Netz und Direktsynthese werden miteinander abgeglichen.
Auch acht 1-Bit-Kanäle sind in den Tests vollständig geprüft (256 Fälle).
Es gibt keinen Minimalitätsnachweis; etwa binäres Minimum/Maximum lässt sich
mit AND/OR kleiner ausdrücken als der bewusst wiederverwendete SORT2.

Im [Exportordner](../examples/circuits/sort-network/verification.json) stehen
je kleiner Instanz `.template.json`, `.vectors.json`, `.block.json`,
`.circuit.json` und `.nand.txt`. Der Prüfbericht enthält Stufen, Vergleichszahl,
Gatterzahl, Tiefe und vollständigen Prüfstatus.

## Parameter, Stichproben und Grenzen

Zulässig sind ganzzahlige k von 0 bis 7, n als positive Zweierpotenz bis 64
und `n*2**k<=128`. Diese Bedingungen werden sowohl bei der Spezialisierung
als auch im öffentlichen Funktionsaufruf geprüft. Die SORT2-Abhängigkeit
begründet die Zweierpotenzbedingung für n. Ein- und Ausgang sowie das interne
Datenarray bleiben jeweils bei höchstens 128 Bits; SORT2 benötigt höchstens
2*n=128 Bits. Kanalzahl und Eingaberaum wachsen exponentiell mit k:
Es gibt `2**(n*2**k)` mögliche Eingabemuster.

Die 512-NAND-Grenze gilt bereits während Konstruktion und Expansion, vor der
abschliessenden Vereinfachung. Beispielsweise funktionieren 4 Kanäle à 4 Bits
(450 expandierte NANDs, nach Vereinfachung 354 mit Tiefe 33), 8 Kanäle à 1 Bit
(264 bzw. 216 NANDs) und 2 Kanäle à 16 Bits (415 bzw. 271 NANDs).
2 Kanäle à 32 Bits, 4 Kanäle à 8 Bits, 8 Kanäle à 2 Bits und 16 Kanäle à
1 Bit überschreiten dagegen auf beiden Wegen die 512-Gattergrenze.

Grössere Referenzen sind mit 2 Kanälen à 8/16/32 Bits, 4 Kanälen à 4/8 Bits,
8 Kanälen à 2/4 Bits und 16/32 Kanälen à 1 Bit anhand von Grenzfällen und
reproduzierbaren Stichproben geprüft. Geprüft werden dabei auch Duplikate,
umgekehrte und bereits sortierte Reihenfolgen sowie das höchste Wortbit.
Diese Eingaberäume sind **nicht vollständig geprüft**. Wo die Konstruktion
zulässig ist, werden auch NAND-Netz und F-Box geprüft. k=0 ist bis n=64 anhand
von Stichproben geprüft und benötigt keine Gatter.

Die allgemeinen Schritt-, Iterations- und Gesamtbudgets gelten zusätzlich.
Formal gültige 128-Bit-Instanzen wie k=1,n=64 oder k=7,n=1 überschreiten bei
der Referenzausführung bereits mit Eingang null das Anweisungsbudget von
100000 Schritten. Die Portbreite garantiert weder Referenzausführung noch
NAND-Konstruierbarkeit. Es werden dafür keine unvollständigen Exporte geliefert.

## Bibliotheksmigration und Reproduktion

Beim nächsten Serverstart ergänzt `sort-network-v1` das Template sowie fünf
Funktionen und fünf F-Boxen unter **Beispiele → Rekursion → Sortiernetze**.
Bestehende Ordner, Namen, Beschreibungen, explizite und implizite Zuordnungen
sowie gleich gute oder bessere Lösungen bleiben erhalten. Eine vorhandene
5-NAND-Lösung für zwei 1-Bit-Kanäle wird beispielsweise beibehalten.
Nach der Migration gelöschte Funktionen, Templates und F-Boxen bleiben gelöscht;
auch der ursprüngliche Beispielinstaller installiert das Template nicht erneut.
HTTP-Prüfungen decken Installation, Synthese, Auswertung und die Navigation
zur SORT2-Unterbox ab.

Nach dem Update den lokalen Server neu starten und die Browserseite neu laden.

```powershell
python -m tools.export_sort_network
python -m unittest discover -s tests -p test_sort_network.py -v
```

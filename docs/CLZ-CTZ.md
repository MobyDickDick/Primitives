# GEN-01: Führende und nachlaufende Nullbits

`CLZ<t>(a)` zählt Nullbits vom höchstwertigen Bit t−1 aus,
`CTZ<t>(a)` vom niederwertigsten Bit 0 aus. Der Eingang `a[t]` ist unsigned;
Bitarrays und Exporte ordnen Bit 0 zuerst an (LSB-first).
Der Ausgang `c[LOG2(t)+1]` enthält die Anzahl als unsigned Zahl.
`t` muss eine positive Zweierpotenz bis 128 sein. Für `a=0` liefern beide
Funktionen **t**, für jeden anderen Eingang einen Wert von 0 bis t−1.

| a[4], höchstes Bit links | CLZ<4> | CTZ<4> |
| --- | --- | --- |
| 0000 | 4 | 4 |
| 0001 | 3 | 0 |
| 0010 | 2 | 1 |
| 1000 | 0 | 3 |
| 1111 | 0 | 0 |

Die editierbaren Quellen sind [recursive-clz.prim](../examples/templates/recursive-clz.prim)
und [recursive-ctz.prim](../examples/templates/recursive-ctz.prim).
Die separat importierbaren abstrakten Templates enthalten jeweils die komplette
Quelle: [CLZ](../examples/templates/recursive-clz.abstract.json),
[CTZ](../examples/templates/recursive-ctz.abstract.json).

## Rekursive Konstruktion

Bei t=1 wird das Eingangsbit invertiert. Sonst ist k=t/2:
CLZ untersucht zuerst die obere Hälfte, CTZ zuerst die untere.
Beide Hälften werden rekursiv gezählt. Ist die erste Hälfte nicht null,
gilt deren Zählergebnis. Ist sie null, gilt k plus das Ergebnis der zweiten.
Ein rekursiver `ISZERO<k>` entscheidet über diese Auswahl.

`CountMerge<k>` verbindet Auswahl und Addition der konstanten Zweierpotenz k.
Die unteren LOG2(k) Bits werden mit einem MUX ausgewählt. Bei nuller erster
Hälfte wird das k-Bit der zweiten Zählung invertiert; dessen vorheriger Wert
wird zum Übertrag ins nächste Bit. So bleibt der Sonderfall beider nuller
Hälften korrekt: k+k=t. Dieser Helfer setzt gültige Teilzählungen in 0..k
und das zum ersten Teil passende Nullbit voraus.

Die `.prim`-Quellen verwenden feste Bitoperationen; die Schleife im Helfer
wird beim Übersetzen entrollt. Die F-Box-Pakete zeigen für t>1 zwei rekursive
Zähler, einen Nulltest und einen `CountMerge`-Baustein. Die flachen Netze
entstehen durch Expansion und logische Vereinfachung.

## Exporte und Prüfung

| Template | t | Ergebnisbits | NANDs | Tiefe | Vollständig geprüfte Eingaben |
| --- | --- | --- | --- | --- | --- |
| CLZ, CTZ jeweils | 1 | 1 | 1 | 1 | 2 |
| CLZ, CTZ jeweils | 2 | 2 | 6 | 3 | 4 |
| CLZ, CTZ jeweils | 4 | 3 | 19 | 5 | 16 |

Alle **44 Eingabefälle** über sechs Instanzen werden gegen eine unabhängige
Ganzzahlreferenz geprüft: Referenzprogramm, hierarchische Auswertung,
expandiertes Netz, vereinfachtes Netz und direkte strukturelle Übersetzung.
Die Tests prüfen zusätzlich mit einer unabhängigen Zeichenkettenreferenz.
Die Gatterzahlen sind keine Minimalitätsnachweise.

Die Ordner [recursive-clz](../examples/circuits/recursive-clz/verification.json)
und [recursive-ctz](../examples/circuits/recursive-ctz/verification.json)
enthalten je Breite `.template.json`, `.vectors.json`, `.block.json`,
`.circuit.json` und `.nand.txt` sowie einen Prüfbericht mit Gatterzahl und Tiefe.

Für t=8,16,32 werden Grenzfälle, einzelne gesetzte Bits und reproduzierbare
Stichproben auch gegen NAND-Netze und Hierarchien geprüft. Die direkt übersetzten
Netze benötigen jeweils 48, 109 und 234 NANDs. t=64 und t=128 sind als
Referenzprogramme nutzbar und mit Grenzfällen/Stichproben geprüft;
ihre direkte NAND-Übersetzung sowie die Hierarchieexpansion überschreiten die
512-Gattergrenze und werden ausdrücklich abgelehnt. Grössere Eingaberäume
werden damit nicht als vollständig geprüft bezeichnet. Die 128-Bit-Portgrenze
und die üblichen Vektorbudgets gelten weiterhin.

Reproduzierbar erzeugen und prüfen:

```powershell
python -m tools.export_zero_counts
python -m unittest discover -s tests -p test_zero_counts.py -v
```

Beim nächsten Serverstart ergänzt eine separate einmalige Migration die beiden
Templates und sechs Funktionen unter **Beispiele → Rekursion → Nullbits zählen
(CLZ & CTZ)** sowie sechs wiederverwendbare F-Boxen unter den Bausteinen.
Vorhandene Ordner, eigene Namen, Zuordnungen und bessere Schaltungen bleiben
erhalten. Der Marker `zero-counts-v1` verhindert, dass spätere Serverstarts
gelöschte Beispiele erneut anlegen. Server neu starten und Browserseite neu laden.

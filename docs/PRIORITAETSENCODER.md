# GEN-02: Prioritätsencoder für den niedrigsten Bitindex

`PE<t>(a)` liefert den **Index des niedrigsten gesetzten Bits** als unsigned
`c[max(1,LOG2(t))]` und ein `valid[1]`. Der Eingang `a[t]` und alle Bitarrays
sind LSB-first: Bit 0 ist das niederwertigste Bit. `t` muss eine positive
Zweierpotenz bis 128 sein. Es gibt keine weiteren Parameter.

- Für `a=0` gilt **c=0, valid=0**.
- Für `a!=0` gilt **valid=1**; bei mehreren gesetzten Bits gewinnt der kleinste Index.
- Bei `t=1` hat der Index trotzdem ein Bit und bleibt immer 0; `valid=a[0]`.

| a[4], höchstes Bit links | c | valid |
| --- | --- | --- |
| 0000 | 0 | 0 |
| 0001 | 0 | 1 |
| 0010 | 1 | 1 |
| 1000 | 3 | 1 |
| 1010 | 1 | 1 |
| 1111 | 0 | 1 |

Die editierbare Quelle ist [recursive-priority-encoder.prim](../examples/templates/recursive-priority-encoder.prim).
Das [abstrakte Template](../examples/templates/recursive-priority-encoder.abstract.json)
enthält dieselbe vollständige Quelle und lässt sich separat importieren.

## Rekursive Konstruktion und Gegenstück

Der Basisfall liefert den gepackten Wert `[0,a[0]]`. Sonst werden beide
Hälften mit `PE<t/2>` rekursiv ausgewertet. `PriorityMerge<t/2>` wählt bei
gültiger unterer Hälfte deren Index; sonst den oberen. Die Auswahl der oberen
Hälfte hängt deren Offset t/2 als höchstes Indexbit an. Bei zwei ungültigen
Hälften bleiben Index und valid null. Das gemeinsame valid-Bit ist das ODER
beider Teilflags. Der Helfer setzt voraus, dass ungültige Teilindizes null sind.

Alle Auswahloperationen verwenden feste Bitlogik. Bedingungen hängen nur von
Parametern ab, Schleifen werden beim Übersetzen entrollt. Die F-Boxen zeigen
für t>1 zwei rekursive Encoder und einen `PriorityMerge`-Baustein.

Das vorhandene [maximale Bitindex-Template `m<t>`](MAX-INDEX.md) ist das Gegenstück:
Es wählt das **höchste** gesetzte Bit und liefert t Indexbits sowie `err`,
während PE den **niedrigsten** Index mit kompakter Breite und `valid` liefert.
Für Nichtnullwerte gilt `PE<t>(a).c = t-1-m<t>(REVERSE<t>(a)).c` und
`PE.valid = 1-m.err`. Bei null gilt bei beiden Index 0, mit entgegengesetzten
Flags. Dieser Zusammenhang wird für alle kleinen Eingaben mitgeprüft.

## Exporte und Prüfung

| t | Indexbits | valid-Bits | NANDs | Tiefe | Vollständig geprüfte Eingaben |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 3 | 3 | 2 |
| 2 | 1 | 1 | 5 | 3 | 4 |
| 4 | 2 | 1 | 18 | 5 | 16 |

Alle **22 Eingabefälle** werden unabhängig gegen die Ganzzahlreferenz
`(a & -a).bit_length()-1` bei Nichtnull und `[0,0]` bei null geprüft.
Referenzprogramm, hierarchische Auswertung, expandiertes Netz, vereinfachtes
Netz und direkte strukturelle Übersetzung müssen übereinstimmen. Die Tests
verwenden zusätzlich eine unabhängige Schleife über die Bitpositionen.
Einzel- und Mehrfachbelegungen sowie die Null- und Maximalwerte sind enthalten.

Die Gatterzahlen sind keine Minimalitätsnachweise. Der Ein-Bit-Fall benötigt
in der NAND-Darstellung drei Gatter zur Erzeugung des konstanten Indexbits 0;
valid ist direkt mit dem Eingang verbunden.

Unter [recursive-priority-encoder](../examples/circuits/recursive-priority-encoder/verification.json)
liegen für jede kleine Breite `.template.json`, `.vectors.json`, `.block.json`,
`.circuit.json` und `.nand.txt` sowie der Prüfbericht mit Gatterzahlen und Tiefe.

Für t=8,16,32 werden alle einzelnen gesetzten Bits, Mehrfachbelegungen mit jeder
möglichen Gewinnerposition, Grenzfälle und reproduzierbare Stichproben geprüft,
auch gegen NAND-Netze und Hierarchien. Die vereinfachten Netze benötigen
47, 108 und 233 NANDs bei Tiefe 7, 9 und 11. Die grösseren Eingaberäume
werden damit ausdrücklich **nicht vollständig geprüft**.

t=64 und t=128 sind als Referenzprogramme mit denselben Arten von Grenzfällen
und Stichproben nutzbar. Ihre direkte strukturelle Konstruktion sowie die
Hierarchieexpansion überschreiten vor der abschliessenden Vereinfachung die
512-Gattergrenze und werden abgelehnt. Das behauptet keine Unmöglichkeit einer
kleineren alternativen Schaltung. Die 128-Bit-Portgrenze und Vektorbudgets
gelten weiterhin; der grösste Ausgang umfasst sieben Indexbits und ein valid-Bit.

Reproduzierbar erzeugen und prüfen:

```powershell
python -m tools.export_priority_encoder
python -m unittest discover -s tests -p test_priority_encoder.py -v
```

## Einmalige Bibliotheksmigration

Beim nächsten Serverstart ergänzt eine separate Migration das Template und
drei vollständig geprüfte Funktionen unter **Beispiele → Rekursion →
Prioritätsencoder** sowie drei wiederverwendbare F-Boxen unter den Bausteinen.
Bestehende Ordner, Namen, Beschreibungen, Zuordnungen und bessere Schaltungen
bleiben erhalten. Der Marker `priority-encoder-v1` verhindert, dass spätere
Starts gelöschte Beispiele erneut anlegen. Die Tests prüfen sowohl das Upgrade
einer alten Bibliothek als auch die API für Katalog, Synthese und F-Box-Auswertung.
Server neu starten und Browserseite neu laden.

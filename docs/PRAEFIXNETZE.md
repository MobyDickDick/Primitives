# GEN-06: Präfix-AND und Präfix-XOR

`PREFIX_AND<t>(a)` und `PREFIX_XOR<t>(a)` haben den Eingang `a[t]` und
den Ausgang `c[t]`. Ports und Bitarrays sind LSB-first. Beide Funktionen
bilden **inklusive Präfixe ab Bit 0**:

| Funktion | Ausgangsbit c[i] |
| --- | --- |
| PREFIX_AND | `a[0] & a[1] & ... & a[i]` |
| PREFIX_XOR | `a[0] ^ a[1] ^ ... ^ a[i]` |

Das erste Ausgangsbit ist immer a[0]; das letzte enthält AND bzw. XOR aller
Eingangsbits. Bei t=1 sind beide Funktionen die Identität und benötigen
keine NAND-Gatter. Null liefert null. Für lauter Einsen liefert Präfix-AND
lauter Einsen, Präfix-XOR das Bitmuster `[1,0,1,0,...]`.

Beispiel bei t=4: a=11 hat die Bits `[1,1,0,1]`. Präfix-AND liefert
`[1,1,0,0]` (3), Präfix-XOR `[1,0,0,1]` (9).

Die Orientierung entspricht dem vorhandenen `PREFIX_OR<t>`.
`UNGRAY<t>` zur Gray-Dekodierung bildet dagegen XOR über a[i] bis a[t-1].
Deshalb liefert `PREFIX_XOR<4>(1)=15`, aber `UNGRAY<4>(1)=1`.
Präfix-XOR lässt sich durch benachbarte Ausgangsbits zurückwandeln:
`a[0]=c[0]` und `a[i]=c[i]^c[i-1]` für i>0.

## Editierbare Quellen und Hierarchie

- [Präfix-AND-Quelle](../examples/templates/recursive-prefix_and.prim) und
  [abstraktes Template](../examples/templates/recursive-prefix_and.abstract.json).
- [Präfix-XOR-Quelle](../examples/templates/recursive-prefix_xor.prim) und
  [abstraktes Template](../examples/templates/recursive-prefix_xor.abstract.json).

Parameterbedingungen: `t>=1`, `t<=128`, `is_power_of_two(t)`.
Direkte Funktionsaufrufe prüfen dieselben Bedingungen. Die internen
`PrefixANDMerge<k>` und `PrefixXORMerge<k>` verlangen `1<=k<=64`.

Die rekursive Halbierung berechnet die Präfixe beider Hälften unabhängig.
Das letzte Präfix der unteren Hälfte wird anschliessend mit jedem Präfix
der oberen Hälfte verknüpft. Die unteren Präfixe bleiben unverändert.
Alle Schleifen und Indizes hängen nur von festen Parametern ab.

Jede F-Box ab t=2 enthält die sichtbaren Unter-FBoxen `lower`, `upper`
und `prefix`. Die ersten beiden sind rekursive Instanzen, die dritte
verknüpft den oberen Bus mit dem unteren Gesamtpräfix. Die Basisbox
verdrahtet a[0] direkt auf c[0]. Die flachen NAND-Exporte entstehen durch
Hierarchieexpansion und Vereinfachung.

## Exporte und unabhängige Prüfung

| t | Eingaben je Operation | AND: NANDs / Tiefe | XOR: NANDs / Tiefe |
| --- | --- | --- | --- |
| 1 | 2 | 0 / 0 | 0 / 0 |
| 2 | 4 | 2 / 2 | 4 / 3 |
| 4 | 16 | 8 / 4 | 16 / 6 |

Alle **44 Eingabefälle** sind vollständig und unabhängig geprüft:
Quellprogramm, hierarchische Auswertung, expandiertes Netz, vereinfachtes
Netz und direkte Quellsynthese stimmen überein. Der Export verwendet
Ganzzahlmasken und die Anzahl gesetzter Bits als Referenz; die Tests prüfen
zusätzlich durch serielle Akkumulation einzelner Bits. Die Tests vergleichen
jede exportierte Vektorzeile und prüfen De Morgan gegen `PREFIX_OR`, die
XOR-Rückwandlung und die Abgrenzung zur Gray-Dekodierung.

Die Ordner [recursive-prefix_and](../examples/circuits/recursive-prefix_and/verification.json)
und [recursive-prefix_xor](../examples/circuits/recursive-prefix_xor/verification.json)
enthalten jeweils drei `.template.json`, `.vectors.json`, `.block.json`,
`.circuit.json` und `.nand.txt` sowie einen Prüfbericht. Gatterzahlen sind
Konstruktionswerte; ein Minimalitätsnachweis wird nicht behauptet.

## Grössere Breiten und Grenzen

Referenzprogramme sind bis zur **128-Bit-Portgrenze** ausführbar. Für
t=8,16,32,64,128 prüfen die Tests Grenzfälle, jede einzelne gesetzte bzw.
gelöschte Bitposition und reproduzierbare Stichproben. Diese grösseren
Eingaberäume sind **nicht vollständig geprüft**.

Für diese Konstruktion benötigt Präfix-AND `t*LOG2(t)` NANDs bei Tiefe
`2*LOG2(t)`, Präfix-XOR doppelt so viele NANDs bei Tiefe `3*LOG2(t)`.
AND mit t=64 ergibt 384 NANDs bei Tiefe 12, XOR mit t=32 ergibt 320 NANDs
bei Tiefe 15; beide sind auch als F-Boxen und direkte Synthese geprüft.
AND mit t=128 sowie XOR ab t=64 überschreiten die **512-NAND-Gattergrenze**
bei beiden Übersetzungswegen. Die Referenzprogramme bleiben ausführbar.
Die vorhandenen Ausführungsbudgets und höchstens 65536 Vektoren je
Datensatz gelten weiterhin; grössere Wahrheitstabellen benötigen Stichproben.

Reproduzierbar erzeugen und prüfen:

```powershell
python -m tools.export_prefixes
python -m unittest discover -s tests -p test_prefixes.py -v
```

## Einmalige Bibliotheksmigration

Beim nächsten Serverstart ergänzt `prefixes-v1` zwei Templates und sechs
vollständig geprüfte Funktionen unter **Beispiele → Rekursion →
Präfix-AND & Präfix-XOR**, dazu sechs wiederverwendbare F-Boxen.
Bestehende Ordner, Beschreibungen, Benennungen, Zuordnungen und gleich gute
oder bessere Schaltungen bleiben erhalten. Der Marker verhindert, dass
später gelöschte Funktionen, Templates oder F-Boxen erneut angelegt werden.

Tests prüfen Migration, Neustart, API-Katalog, direkte Synthese, Auswertung
aller kleinen Eingaben und Navigation bis in eine verschachtelte
Präfix-Verknüpfung. Server neu starten und Browserseite neu laden.

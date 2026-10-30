# GEN-03: Decoder und One-Hot-Encoder

`DEC<w>(a, enable)` wandelt einen unsigned Code `a[w]` in `c[2**w]` um.
Bei `enable=1` ist genau `c[a]=1`; bei `enable=0` sind alle Ausgänge null.
Ohne Freigabesteuerung wird `enable` mit 1 verbunden. Alle Codes des w-Bit-Ports
sind gültig. Ports und Bitarrays sind LSB-first: Index 0 bezeichnet Bit 0.

Die Umkehrung `OHE<w>(a)` liest `a[2**w]` und liefert den Index `c[w]`,
`valid[1]` und `multiple[1]`:

| Belegung von a | c | valid | multiple |
| --- | --- | --- | --- |
| Kein Bit gesetzt | 0 | 0 | 0 |
| Genau Bit i gesetzt | i | 1 | 0 |
| Mindestens zwei Bits gesetzt | 0 | 0 | 1 |

`valid` bedeutet also **genau ein gesetztes Bit**. Anders als der
[Prioritätsencoder PE](PRIORITAETSENCODER.md) wählt OHE bei Mehrfachbelegung
keinen Gewinner. Auch bei einem ungültigen Muster mit gesetztem Bit 0 bleibt
der Ergebnisindex null und `multiple=1`.

Beispiel für w=2: `DEC(2,1)=0100`, `OHE(0100)=[2,1,0]`,
`OHE(0101)=[0,0,1]`, `OHE(0000)=[0,0,0]` (höchstes Bit links).
Der Rückweg erfüllt `OHE(DEC(code,1))=[code,1,0]`. Für genau ein gesetztes
Eingangsbit rekonstruiert `DEC(OHE(a).c,OHE(a).valid)` den Eingang;
ungültige Eingänge ergeben auf diesem Rückweg null.

## Quellen und Konstruktion

Die editierbaren Quellen und separat importierbaren abstrakten Templates sind:

- [recursive-decoder.prim](../examples/templates/recursive-decoder.prim) und
  [Decoder-Template](../examples/templates/recursive-decoder.abstract.json).
- [recursive-onehot-encoder.prim](../examples/templates/recursive-onehot-encoder.prim) und
  [One-Hot-Encoder-Template](../examples/templates/recursive-onehot-encoder.abstract.json).

Beide Templates verlangen ganzzahliges `1 <= w <= 7`, auch bei direkten
Funktionsaufrufen. w bezeichnet die **Codebreite**; die Zahl der One-Hot-Bits
wächst exponentiell als `2**w`. Insbesondere hat OHE<4> einen 16-Bit-Eingang.

DEC teilt anhand des höchsten Codebits die Freigabe auf zwei Zweige und ruft
für jeden Zweig `DEC<w-1>` auf. Die Ergebnisse werden als untere und obere
Ausgangshälfte verbunden. Der Basisfall bildet die beiden AND-Verknüpfungen
mit dem Codebit beziehungsweise dessen Negation.

OHE wertet beide Eingangshälften rekursiv aus. `OneHotMerge<r>` setzt
`multiple`, wenn eine Hälfte mehrfach belegt ist oder beide Hälften jeweils
gültig sind. `valid` wird nur bei genau einer gültigen Hälfte ohne
Mehrfachbelegung gesetzt. Die vereinigten Teilindizes und das Offsetbit der
oberen Hälfte werden mit diesem Flag maskiert. So bleiben ungültige Indizes
immer null. Der Basisfall mit zwei Eingangsbits verwendet XOR für `valid`
und AND für `multiple`.

Bedingungen und Schleifen hängen ausschliesslich von Parametern ab;
Datenoperationen verwenden feste Bitlogik. Die direkte Synthese entrollt
die Quelle strukturell nach NAND. Die F-Boxen zeigen ab w=2 jeweils zwei
rekursive Unterfunktionen und die Decoder-Aufteilung beziehungsweise den
`OneHotMerge`-Baustein.

## Exporte und vollständige Prüfung

| Funktion | Eingangsbits gesamt | Ausgangsbits gesamt | NANDs | Tiefe | Vollständig geprüfte Eingaben |
| --- | --- | --- | --- | --- | --- |
| DEC<1> | 2 | 2 | 5 | 3 | 4 |
| DEC<2> | 3 | 4 | 14 | 5 | 8 |
| DEC<4> | 5 | 16 | 64 | 9 | 32 |
| OHE<1> | 2 | 3 | 7 | 5 | 4 |
| OHE<2> | 4 | 4 | 25 | 10 | 16 |
| OHE<4> | 16 | 6 | 137 | 20 | 65536 |

Alle **65 600 Eingabefälle** sind beim Export gegen eine unabhängige
Ganzzahlreferenz geprüft: Referenzprogramm, hierarchische Auswertung,
expandiertes und vereinfachtes Netz sowie direkte Quellsynthese stimmen
überein. Die Tests kontrollieren sämtliche Vektorzeilen zusätzlich mit einer
unabhängigen Bitpositionssuche und prüfen alle flachen Hardwareformen gegen
die vollständigen Tabellen. Beide Rückwege, jede Einzelbelegung, sämtliche
Zweifachbelegungen der kleinen Instanzen sowie weitere Mehrfachbelegungen
werden zusätzlich gegen Referenzprogramm und F-Boxen getestet.

Unter [recursive-decoder](../examples/circuits/recursive-decoder/verification.json)
und [recursive-onehot-encoder](../examples/circuits/recursive-onehot-encoder/verification.json)
liegen jeweils drei `.template.json`, `.vectors.json`, `.block.json`,
`.circuit.json` und `.nand.txt` sowie ein Prüfbericht. Gatterzahlen sind
Konstruktionswerte und keine Minimalitätsnachweise.

## Grössere Instanzen und Budgets

Die 128-Bit-Grenze je Port und je Ein-/Ausgangsseite erlaubt w bis 7.
Die Referenztests decken zusätzlich w=3,5,6,7 ab. Decoder werden auch dort
für sämtliche Codes und beide Freigabewerte geprüft. Die grösseren
Encoder-Eingaberäume verwenden ausdrücklich **Grenzfälle und reproduzierbare
Stichproben**, einschliesslich jeder Einzelbelegung und über die Hälften
verteilter Mehrfachbelegungen; sie sind nicht vollständig geprüft.

- DEC<3>, DEC<5> und DEC<6> benötigen 31, 129 und 258 NANDs bei Tiefe 7, 11 und 13.
- OHE<3> und OHE<5> benötigen 62 und 288 NANDs bei Tiefe 15 und 25.
- DEC<7> sowie OHE<6> und OHE<7> überschreiten mit dieser Konstruktion bei
  Quellsynthese und Hierarchieexpansion die 512-NAND-Gattergrenze. Sie bleiben
  als Referenzprogramme nutzbar. Kleinere alternative Schaltungen sind damit
  nicht ausgeschlossen.

Pro Datensatz sind höchstens 65536 Vektoren erlaubt; zusätzlich gelten die
gemeinsamen Ausführungsbudgets bei Vektorerzeugung über Editor/API/CLI.
Eine erneute vollständige Vektorerzeugung aus dem rekursiven OHE<4>-Programm
überschreitet das Gesamtbudget von fünf Millionen Schritten. Dafür sind die
vollständige geprüfte Exporttabelle und gespeicherte Funktion vorhanden;
für interaktives Konkretisieren können beispielsweise 256 Stichproben verwendet
werden. Der Exportprüfer wertet jede Eingabe mit eigenem begrenztem Budget aus,
ohne die Budgets der normalen Vektorerzeugung zu verändern.

Reproduzierbar erzeugen und prüfen (die vollständige Exportprüfung dauert einige Minuten):

```powershell
python -m tools.export_onehot
python -m unittest discover -s tests -p test_onehot.py -v
```

## Einmalige Bibliotheksmigration

Beim nächsten Serverstart ergänzt die Migration `onehot-v1` zwei Templates,
sechs vollständig geprüfte Funktionen unter **Beispiele → Rekursion →
Decoder & One-Hot** und sechs wiederverwendbare F-Boxen unter den Bausteinen.
Bestehende Ordner, Benennungen, Beschreibungen, Zuordnungen und bessere
Schaltungen bleiben erhalten. Der Marker verhindert, dass spätere Starts
gelöschte Funktionen, Templates oder F-Boxen wieder anlegen.
Tests prüfen das Upgrade einer bestehenden Bibliothek, den API-Katalog,
direkte Synthese und F-Box-Auswertung. Server neu starten und Browserseite
neu laden.

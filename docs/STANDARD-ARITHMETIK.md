# Standardlösungen mit unabhängigen Eingangsbreiten

Die Quellen enthalten deutsche Kommentare zu Bitreihenfolge, Zwischenschritten
und Ergebnisflags. [Die Template-Sprache lesen](TEMPLATE-SPRACHE.md) ergänzt
eine Syntaxübersicht und rechnet die Division 13/3 Schritt für Schritt durch.
Beim nächsten Serverstart werden auch die bisher unveränderten Beispielquellen
in bestehenden Bibliotheken kommentiert. Eigene Quelltextänderungen und
Kommentare bleiben erhalten; gelöschte Beispiele werden nicht wiederhergestellt.

Vier generative Bit-Templates besitzen die Parameter `p` und `q` für
die vorzeichenlosen Eingänge `a[p]` und `b[q]`. Alle neun Kombinationen aus
`p=1,2,4` und `q=1,2,4` sind erzeugt: insgesamt **36 Standardlösungen**.
Der kleinere Operand wird bei Bedarf durch Verdrahtung mit Nullbits erweitert.

| Operation | Standardverfahren | Ausgänge |
| --- | --- | --- |
| Addition | Ripple-Carry, feste Volladdierstufen | `c[max(p,q)+1]`, vollständige Summe |
| Subtraktion | Ripple-Borrow | `c[max(p,q)]`, `borrow[1]` |
| Multiplikation | AND-Teilprodukte und Schiebe-Addier-Stufen | `c[p+q]`, vollständiges Produkt |
| Division | Restoring-Division, p feste Subtraktions-/Auswahlstufen | `c[p]`, `rest[q]`, `valid[1]`, `div0[1]` |

Bei der Subtraktion gilt `c=(a-b) modulo 2**max(p,q)` und `borrow=(a<b)`.
Bei der Division durch null sind Quotient, Rest und valid null, div0 ist eins.
Sonst gilt `a=b*c+rest` und `0 <= rest < b`, mit valid=1 und div0=0.
Diese Semantik unterscheidet sich von den rekursiven Fehlerbit-Varianten,
welche bei Überlauf bzw. Unterlauf das Ergebnis auf null setzen.

Beispiel: `p=2, q=4` erlaubt `a=0..3` und `b=0..15`. Für `a=3, b=15`
liefert die Addition 18 auf fünf Bits, die Multiplikation 45 auf sechs Bits,
die Subtraktion c=4 und borrow=1 und die Division c=0 und rest=3.

Die Definitionen stehen in `examples/templates/standard-*.abstract.json`;
lesbare Quellen in den gleichnamigen `.prim`-Dateien. Die Instanzen unter
`examples/circuits/standard-{add,sub,mul,div}/` enthalten je eine
konkrete Template-Definition, vollständige Wahrheitstabelle, flaches NAND-Netz,
lesbare `.nand.txt`-Datei und wiederverwendbaren Baustein. Der Baustein enthält
das konkrete NAND-Netz; eine Hierarchie einzelner Rechenstufen ist hier nicht
modelliert. `verification.json` enthält Gatterzahlen, Tiefe und Prüfstatus.

Alle **1936 Eingabefälle** (484 pro Operation) sind gegen unabhängige
Ganzzahlarithmetik geprüft, sowohl im Interpreter als auch im NAND-Netz und
Baustein. Die Standardkonstruktionen beanspruchen keine minimale Gatterzahl.
Grössere Breiten von 1 bis 16 und Nicht-Zweierpotenzen sind als Referenz
zulässig; bei der Synthese bleibt die Grenze von 512 NAND-Gattern bestehen.

Beim nächsten Serverstart ergänzt eine eigene einmalige Migration die vier
Templates, 36 Funktionen und 36 Bausteine unter
**Beispiele → Grundrechenarten → Standardlösungen (1, 2, 4 Bit)**.
Bestehende Beispiele und Ordner werden erhalten. Nach abgeschlossener
Migration werden gelöschte Einträge nicht erneut angelegt. Für identische
Wahrheitstabellen kann die Bibliothek vorhandene bessere NAND-Netze verwenden.

Im Template-Editor genügt beispielsweise `{"p": 2, "q": 4}`.
Symbolische Portbreiten unterstützen dafür jetzt auch `min(p,q)` und
`max(p,q)` mit jeweils genau zwei Argumenten. Bedingungen unterstützen
diese beiden Funktionen ebenfalls.

```powershell
python -m tools.export_standard_arithmetic
python -m unittest discover -s tests -p test_standard_arithmetic.py -v
```

Weitere generative Templates stehen als offene Aufgaben in
[GENERATIVE-AUFGABEN.md](GENERATIVE-AUFGABEN.md).

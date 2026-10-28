# Division: Rekursion, Evolution und Rückführung

Ja, Division besitzt generative, rekursive Algorithmen. Hier sind zwei davon
konkret implementiert und geprüft: die bereits vorhandene MSB-Ausrichtung
und eine neue Rekursion mit gemeinsamem Quotienten-/Restzustand. Der neue
Schritt lässt sich auch mit Registern wiederverwenden.

## Bedeutung von Resultat und Fehlerbit

Es gilt die bisherige Projektdefinition für natürliche beziehungsweise
nichtnegative Zahlen: `DIV(a,b) = [floor(a/b),0]` für `b>0` und `[0,1]`
für `b=0`. Ein verbleibender Rest ist kein Fehler. Ein Ausgang mit so vielen
Bits wie der Dividend reicht immer, weil `floor(a/b)<=a` für `b>=1`.

Für die ausdrücklich angefragten **Zahlenwerte** 1 bis 4 ergibt sich:

| a / b | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| 1 | [1,0] | [0,0] | [0,0] | [0,0] |
| 2 | [2,0] | [1,0] | [0,0] | [0,0] |
| 3 | [3,0] | [1,0] | [1,0] | [0,0] |
| 4 | [4,0] | [2,0] | [1,0] | [1,0] |

Die [CSV-Tabelle](../examples/experiments/division/values-1-to-4.csv) enthält
auch die drei Bit breiten Ein-/Ausgänge und den Kontrollrest. Alle Fehlerbits
sind hier null: Ohne Nullteiler kann die Suche die Fehlererkennung nicht lernen.

Zusätzlich werden **alle 16 Kombinationen der Bitbreiten** `1<=m,n<=4`
untersucht: `0<=a<2**m`, `0<=b<2**n`, Quotient mit m Bits und ein Fehlerbit.
Das sind insgesamt `(2+4+8+16)**2 = 900` Eingabepaare einschliesslich Nullteilern.
Die [Messresultate](../examples/experiments/division/report.md) verlinken die
Dateinamen; pro Kombination liegen CSV, importierbare JSON-Vektoren,
flaches NAND-Netz und das beste evolutionäre Ergebnis vor.

## Der vorgeschlagene Best-Fit-Schritt funktioniert

Wenn `c0` die grösste **beliebige natürliche Zahl** mit `c0*b<=a` sein soll,
ist `c0` bereits der gesuchte Quotient. Das verschiebt die ursprüngliche
Aufgabe in die Auswahl von c0. Gleichheit muss zugelassen werden.

Ein einfach bestimmbarer Anteil ist dagegen die grösste passende Zweierpotenz:

```text
DIVREM(a,b):                         # b > 0
    wenn a < b: return (0,a)
    d = bit_length(a) - bit_length(b)
    s = b << d
    wenn s > a:
        d = d - 1
        s = s >> 1
    (q,r) = DIVREM(a-s,b)
    return (2**d + q,r)
```

Damit gilt genau `DIV(a,b) = 2**d + DIV(a-b*2**d,b)` für den Quotienten.
Es gibt keine allgemeine Multiplikation im Schritt; `b*2**d` ist ein Shift.
Die Wahl erfordert nur die beiden höchsten Bitpositionen, einen Vergleich
und gegebenenfalls die Korrektur um eine Stelle.

**Die behauptete Verkleinerung ist beweisbar:** Mit `s=b*2**d` gilt
`s<=a<2*s`, sonst wäre eine grössere Zweierpotenz passend. Also ist
`a'=a-s<a/2`. Bei jedem tatsächlich ausgeführten Subtraktionsschritt sinkt
die Bitlänge mindestens um eins; spätestens nach der ursprünglichen
Dividendbitzahl endet die Rekursion. Der Endrest erfüllt `0<=r<b`.

Aus `a'<b*2**d` folgt ausserdem `floor(a'/b)<2**d`. Alle weiteren
Quotientenbits liegen unterhalb des aktuellen Bits: Die Quotientenanteile
können ohne Übertrag mit OR vereinigt werden.

Beispiel `40/6`: 48 ist zunächst zu gross; 24 passt, Rest 16 und Anteil 4.
Danach passt 12, Rest 4 und Anteil 2. Ergebnis ist Quotient 6, Rest 4.

Die ausführbare Python-Fassung ist `aligned_divmod` in
[investigate_division.py](../tools/investigate_division.py). Das bereits
vorhandene [MSB-Template](../examples/templates/recursive-msb-div.prim)
übersetzt diese Idee in feste, von der Breite abhängige NAND-Stufen; siehe
[dessen Beschreibung](REKURSIVE-DIVISION.md).

## Eine weitere Rekursion: Quotient und Rest gemeinsam weiterführen

Für einen besonders einfachen wiederverwendbaren Schritt zerlegen wir den
Dividend in den höheren Teil h und das nächste Bit x:

```text
a = 2*h + x,  x in {0,1}
(q,r) = DIVREM(h,b)
t = 2*r + x
z = 1, falls t >= b, sonst 0
DIVREM(a,b) = (2*q+z, t-z*b)
```

Der Basisfall ist `DIVREM(0,b)=(0,0)` für `b>0`. Jede Rekursion entfernt
ein Dividendbit. Weil `r<b` ist, gilt `t<2*b`; eine einzige bedingte
Subtraktion genügt. Der zweite Ausgang hält genau die Information bereit,
die der nächste Schritt benötigt. `z*b` bedeutet eine Auswahl zwischen
b und null; der Quotient wird durch Anhängen von z aufgebaut.

Es wird **einmal** rekursiv das gemeinsame Paar `(q,r)` berechnet. Die
Quotientenbits entstehen entlang dieser gemeinsamen Berechnung. Für die
gesamte Division pro Ausgangsbit gibt es keinen separaten Dividierer.

Das neue [Template](../examples/templates/recursive-stream-div.prim) bildet
diese Rekursion strukturell ab: `DIV_REM<m,n>` ruft genau einmal
`DIV_REM<m-1,n>` und danach `DIV_STEP<n>` auf. Der Schritt enthält einen
Subtrahierer mit Borrow und eine Auswahl. Der Borrow prüft den Vergleich;
ein zusätzliches vollständiges Vergleichsnetz entfällt. Alle Verzweigungen
der Templatequelle hängen ausschliesslich von festen Breiten ab. Die
Quelle enthält weder Laufzeitdivision noch `for` oder `while`.

Die Quellvorlage unterstützt Referenzauswertung für `1<=m,n<=8`. NAND-Export
bleibt an die vorhandene Grenze von 512 Gattern gebunden; vollständig
exportiert und geprüft wurden hier die Breiten 1 bis 4.

## While-Schleife und Registerrückführung

Auch eine While-Schleife funktioniert: Solange der aktuelle Rest mindestens
b ist, einen passenden Zweierpotenzanteil wählen, abziehen und im Quotienten
setzen. Einfach nur wiederholt b abzuziehen funktioniert ebenfalls, braucht
aber bei b=1 bis zu `2**m-1` Subtraktionen. Die Zweierpotenzauswahl vermeidet
diese exponentielle Schrittzahl in der Bitbreite.

Für Hardware ist die zweite Rekursion besonders gut planbar: Den Dividend
vom höchsten zum niedrigsten Bit lesen und **ein einziges Schrittnetz m-mal
verwenden**. Register speichern den Rest und den entstehenden Quotienten;
der Divisor bleibt während der Rechnung fest. Ein Zähler steuert das Ende.

```text
Register R, nächstes Dividendbit, fester Divisor B
                    |
                    v
             DIV_STEP NAND-Netz
                    |
                    v
            R_neu, Quotientenbit
                    |
              nächste Taktflanke
                    |
                    +----> R-Register / Quotienten-Schieberegister
```

Die Register trennen den alten vom neuen Zustand. Eine direkte Leitung vom
Ausgang zum Eingang eines kombinatorischen Netzes beschreibt keine definierte
While-Schleife; für die Iteration braucht es Zustand und eine Aktualisierungsregel.

Die Grössenordnungen dieser Konstruktion sind:

| Bauweise | Rechenlogik | Zustand | Schritte |
|---|---|---|---|
| vollständig entfaltete Rekursion | O(m*n) NANDs | keine internen Register | ein kombinatorischer Durchlauf |
| wiederverwendeter Schritt | O(n) NANDs | O(m+n) Registerbits und Zähler | m Rechenschritte |

Bei gleicher Operandbreite w ist das entfaltete Netz hier quadratisch,
die getaktete Bauweise linear gross. Der kombinatorische Durchlauf ist kein
konstanter Zeitaufwand: Seine Tiefe wächst ebenfalls. Die getaktete Bauweise
tauscht Gatterfläche gegen mehrere Aktualisierungen. Dieses Prinzip ist als
iterative Restoring-Division beschrieben, etwa in den
[MIT-Vorlesungsfolien, Seite 20](https://fpga.mit.edu/6205/_static/F24/lectures/L10.pdf)
und der [Ausarbeitung von Daniel Llamocca, Seite 6](https://www.secs.oakland.edu/~llamocca/dig_library/arith/Divider%20Implementation.pdf).

**Stand der Umsetzung:** Die NAND-Schrittnetze sind konkret exportiert.
`clocked_divide` simuliert die Registerrückführung mit diesen tatsächlichen
NAND-Netzen und prüft alle 900 Divisionen. Das bisherige `Circuit`-Format
bleibt ein azyklisches Netz; es wurde kein zyklischer Editor oder physisches
Registermodell hinzugefügt. Die gemessenen Schrittgatterzahlen enthalten
keine Register, Taktsteuerung, Ladeauswahl oder Nullteilererkennung.

## Was die Evolution tatsächlich erreicht hat

Die Untersuchung umfasst 63 Läufe mit drei festen Seeds, Population 24 und
je höchstens 200 Generationen beziehungsweise 4801 Bewertungen. Drei Läufe
betreffen genau die 16 Zahlenpaare, 48 die 16 vollständigen Divisionstabellen
und zwölf die Optimierung der vier Schrittnetze. Es gibt keine nachträgliche
Restfallkorrektur.

Die Suche aus Zufallsnetzen fand bei den vollständigen Tabellen nur für
`(m,n)=(1,1),(2,1),(3,1)` in mindestens einem Lauf eine exakte Lösung.
Bei den 16 Zahlenpaaren blieben im besten Lauf 10 falsche Ausgangsbits
von 64. Auch ein Erfolg auf diesen 16 Paaren würde keine allgemeine Division
oder eine korrekte Nullteilererkennung beweisen.

Für die Schrittnetze startete die Evolution dagegen ausdrücklich mit dem
korrekten konstruierten Netz und optimierte es bei fortlaufender vollständiger
Prüfung. Gemessen wurden:

| Divisorbreite n | Schritt konstruiert | nach Evolution |
|---|---|---|
| 1 | 13 NANDs | 8 NANDs |
| 2 | 29 NANDs | 24 NANDs |
| 3 | 45 NANDs | 38 NANDs |
| 4 | 61 NANDs | 55 NANDs |

Das neue vollständige 4/4-Bit-Netz benötigt 203 NANDs bei Tiefe 53, das
vorhandene MSB-Netz 283 bei Tiefe 60. Beide sind vollständig korrekt;
die Zahlen sind keine Minimalitätsnachweise. 55 NANDs bezeichnen dagegen
nur das wiederverwendete 4-Bit-Schrittnetz, keine vollständige Hardwaredivision.

Ein erfolgloser Suchlauf zeigt eine Grenze dieses Suchbudgets und der
gewählten Darstellung. Die Konstruktion und ihr Beweis liefern bereits einen
allgemeinen Algorithmus. Die heutige Evolution sucht bei einer festgelegten
Bitbreite nach NAND-Schaltungen; sie lernt aus diesen Tabellen keine
beliebig parametrisierte Rekursionsregel. Für dieses Projekt ist es daher
sinnvoll, die bewiesene Rekursionsstruktur vorzugeben und evolutionär die
kleinen, wiederverwendeten Übergangsfunktionen zu optimieren.

Alle Messungen und Prüfungen sind wiederholbar:

```powershell
python -m tools.investigate_division
python -m unittest discover -s tests -p test_division_investigation.py -v
```

Das Skript schreibt nach `examples/experiments/division/`; es verändert
keine Einträge der persönlichen Funktionsbibliothek. Die JSON-Dateien enthalten
die Suchkonfigurationen sowie die besten Schaltungen mit ihrer Abstammung.
Der [Messbericht](../examples/experiments/division/report.md) enthält die
vollständigen Ergebnisse, die
[Ablaufspur für 13/3](../examples/experiments/division/trace-13-div-3.json)
zeigt die vier Registeraktualisierungen bis zum Quotienten 4 und Rest 1.

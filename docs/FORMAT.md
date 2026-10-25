# Daten- und Programmformate

## Datensatz, Schema 1

```json
{
  "schema": 1,
  "name": "xor",
  "inputs": 2,
  "outputs": 1,
  "rows": [[0,0,0], [1,0,1], [0,1,1], [1,1,0]],
  "metadata": {"bit_order": "LSB-first"}
}
```

Die ersten N Stellen sind Eingaben, die folgenden M Stellen Ausgaben.
Nur ganzzahlige Werte 0 und 1 werden akzeptiert. Identische doppelte Zeilen werden
entfernt. Zwei verschiedene Ausgaben für dieselbe Eingabe führen zu einem Fehler,
auch wenn nur eines von mehreren Ausgangsbits abweicht. Die Reihenfolge der
gespeicherten Zeilen ist lexikographisch nach Eingabe; sie muss nicht der numerischen
Reihenfolge entsprechen. Das zusätzliche Exportfeld `exhaustive` wird beim Laden
neu berechnet und nicht als Behauptung übernommen.

Bei unvollständiger Tabelle sind nicht aufgeführte Eingaben frei. Eine gefundene
Schaltung legt dafür trotzdem Ausgaben fest; diese wurden durch die Tabelle
aber nicht überprüft.

## Benannte Ports und Breitenvarianten

Schema 1 bleibt gültig. Optional enthält `metadata.interface` die explizite
Schnittstelle, zum Beispiel für ADD(2,3,4):

```json
{
  "schema": 1,
  "bit_order": "LSB-first",
  "inputs": [
    {"name": "a", "bits": 2, "signed": false, "offset": 0},
    {"name": "b", "bits": 3, "signed": false, "offset": 2}
  ],
  "outputs": [
    {"name": "c", "bits": 4, "signed": false, "offset": 0, "overflow": "wrap"}
  ]
}
```

Portreihenfolge legt die fortlaufenden Offsets fest. Offsets beginnen pro Seite
bei 0; in einer Zeile stehen alle Eingänge vor allen Ergebnissen. Innerhalb
jedes Ports kommt das niederwertigste Bit zuerst. Im Beispiel lautet die Zeile
`a0,a1,b0,b1,b2,c0,c1,c2,c3`, mit N=5 und M=4. Offsets dürfen beim Erzeugen
weggelassen werden; angegebene Offsets werden geprüft. Summen müssen N/M
entsprechen, jede Seite hat 1–32 Bits. Portnamen sind auf beiden Seiten eindeutig,
beginnen mit einem ASCII-Buchstaben und enthalten höchstens 32 Buchstaben,
Ziffern oder Unterstriche. `x`, `x0…`, `pi`, Sprach- und Funktionsnamen sind reserviert.

`signed: false` kodiert 0…2^w−1, `signed: true` kodiert −2^(w−1)…2^(w−1)−1
im Zweierkomplement. Eingaben werden vor der Referenzrechnung entsprechend
dekodiert; die Zwischenrechnung verwendet mathematische Zahlen ohne implizites
Abschneiden. Pro Ergebnis legt `overflow` fest:

- `error` (Standard bei eigenen Ports): Ein nicht darstellbares oder nicht
  ganzzahliges Ergebnis bricht die gesamte Erzeugung ab. Keine Teilvektoren speichern.
- `wrap`: Ganzzahlige Ergebnisse modulo 2^w als Bits speichern. Bei signed
  werden dieselben Bits als Zweierkomplement interpretiert.

`metadata.expression` ist bei mehreren Ergebnissen eine Zuordnung
`{"c":"a+b", "valid":"a != 0"}`. Genau ein Ausdruck pro Ergebnisport ist
erforderlich; alle Ausdrücke sehen nur die Eingaben, die Rohbits `x0…`, das
gepackte unsigned `x` und `pi`. Es gibt keine Abhängigkeiten zwischen Ergebnissen.
Ohne Schnittstelle bleibt die alte automatische a/b-Halbierung und die alte
strikte Ergebnisprüfung vollständig erhalten.

Parametrisierte Operationen enthalten zusätzlich beispielsweise:

```json
{
  "definition": "ADD",
  "version": 1,
  "parameters": {
    "a_bits": 2, "b_bits": 3, "result_bits": 4,
    "signed": false, "overflow": "wrap", "flag": false
  }
}
```

Dieses Objekt steht in `metadata.operation`. Definition, Breitenvariante und
NAND-Implementierung sind getrennt: Die Definition existiert im Katalog, die
Variante in den Metadaten, eine gefundene Schaltung im Programm. Beim Import
müssen Operationsparameter, Schnittstelle und Referenzausdrücke zueinander passen.
Es werden keine Varianten vorab aufgezählt. Die alten `PRESETS` bleiben unverändert.

ADD, SUB und MUL rechnen a+b, a−b und a×b. Unterschiedliche Breiten sind erlaubt;
signed gilt bei diesen Operationen für beide Operanden und c. Standard ist
unsigned mit `wrap`. Optional hängt `flag: true` hinter c einen unsigned
Ein-Bit-Ausgang an (zählt zu M):

| Operation | unsigned | signed |
|---|---|---|
| ADD | `carry`: mathematisches Ergebnis > 2^result_bits−1 | `overflow`: Ergebnis ausserhalb des signed Ergebnisbereichs |
| SUB | `borrow`: a < b | `overflow`: Ergebnis ausserhalb des signed Ergebnisbereichs |
| MUL | `overflow`: Ergebnis ausserhalb des unsigned Ergebnisbereichs | `overflow`: Ergebnis ausserhalb des signed Ergebnisbereichs |

Borrow zeigt keine Abschneidung hoher positiver Bits an. Ein Statusausgang hebt
`error` nicht auf. NOT/NAND/AND/OR/XOR/NOR/XNOR wirken bitweise. Python-artige
unbegrenzte Bitwerte entsprechen Nullerweiterung bei unsigned und
Vorzeichenerweiterung bei signed. NOT/NAND/NOR/XNOR invertieren genau die
Ergebnisbreite und interpretieren sie gemäss dem Ergebnisvorzeichen; bei
AND/OR/XOR gilt anschliessend die gewählte Überlaufregel.

Für beliebige NAND-Schaltungen kann `metadata.reference_circuit` deren
unveränderte Gatterliste enthalten. Je ein benannter Port ersetzt einen
ursprünglichen Eingangs- bzw. Ausgangsanschluss. Jede NAND-Stufe wird als
bitweises `~(a & b)` auf den dekodierten Portwerten ausgeführt. Nur die
Ergebnisports begrenzen die Breite gemäss `overflow`, üblicherweise `wrap`.
Das ist eine bitweise Referenz zum Erzeugen neuer Vektoren; die arithmetische
Absicht einer flachen Bitverdrahtung lässt sich daraus nicht allgemein ableiten.

API:

- `GET /api/catalog` liefert feste `presets` und parametrisierbare `operations`.
  Seine `datasets` enthalten ausserdem `function_name` (etwa `ADD(4,4,5)`),
  `function_id`, `task_id` und die Referenz-`metadata`. `function_id` gruppiert
  Vektorsätze derselben Referenzfunktion unabhängig von Seed, Anzeigename und
  Stichprobengrösse. Operationsparameter einschliesslich Vorzeichen, Überlauf
  und Statusport gehören zur Funktionsidentität. `task_id` beschreibt weiterhin
  die konkrete Trainingsaufgabe mit ihren tatsächlichen N+M-Zeilen.
- `POST /api/operations/variant` nimmt das Operationsobjekt entgegen und liefert
  `operation`, `interface` und `expression` ohne Vektorerzeugung oder Speicherung.
- `POST /api/datasets` mit `{"operation": {...}, "samples": 256, "seed": 1}`
  erzeugt die Variante. `name` ist optional; N/M ergeben sich aus der Operation.
- Eigene Aufgaben senden `name`, `inputs`, `outputs`, `interface` und `expression`
  (String für einen Ausgang oder Zuordnung); alternativ `reference_circuit`.
- Import mit `rows` prüft und erhält die Metadaten. `exhaustive` wird stets
  aus den tatsächlichen Zeilen berechnet. Bibliotheksprogramme referenzieren
  ihren Datensatz und liefern zusätzlich dessen `dataset_metadata`.

Der Browser-Programmexport enthält den zugehörigen vollständigen `dataset`.
Beim Import dieses Exports übernimmt die Vektorimportfunktion den Datensatz.
Verschiedene Referenzmetadaten bei identischen N/M/Vektoren bleiben dieselbe
Suchaufgabe: Die Bibliothek behält die beste Schaltung und deren bisherigen
Datensatz; die neu angeforderte Schnittstelle wird als eigener Datensatz gespeichert.
Pro Anfrage entstehen höchstens 65536 Vektoren. Nur wenn alle 2^N Eingaben
enthalten sind, gilt die Tabelle als vollständig; sonst bleibt sie eine Stichprobe.

## Eigene arithmetische Formeln

Ein Erzeugungsauftrag mit `formula` und benannter `interface` verwendet die
arithmetische Formelsyntax. Beispiel mit N=8 und M=5:

```json
{
  "name": "Summe und Übertrag",
  "inputs": 8,
  "outputs": 5,
  "formula": "c = mod(a+b,2^4), e = div(a+b,2^4)",
  "interface": {
    "inputs": [{"name":"a","bits":4}, {"name":"b","bits":4}],
    "outputs": [{"name":"c","bits":4}, {"name":"e","bits":1}]
  },
  "samples": 256
}
```

Ein einzelner Ausdruck wie `a+b` definiert den ersten (und einzigen)
Ergebnisport. Mehrere Ergebnisse werden mit einfachen Zuweisungen definiert,
getrennt durch Zeilenumbrüche, Semikolon oder Komma ausserhalb von Klammern.
Jeder Name darf genau einmal vorkommen; sämtliche Ergebnisports benötigen eine
Formel. Die Oberfläche übernimmt die Ergebnisnamen in Textreihenfolge und
behält vorhandene Breiten gleicher Namen bei. Neue Ergebnisports beginnen mit
1 Bit. Ein- und Ausgangsnamen bleiben insgesamt eindeutig.

In Formelsyntax ist `^` Potenz mit der üblichen Potenzpriorität; `**` ist
ebenfalls gültig. `mod(a,b)` entspricht `a % b`, `div(a,b)` entspricht `a // b`
(Abrunden Richtung minus unendlich), `xor(a,b)` ist bitweises XOR. Bei negativen
Zahlen gilt beispielsweise `div(-7,4) = -2` und `mod(-7,4) = 1`. Division durch
null, nicht darstellbare Resultate bei `overflow: error`, unbekannte Variablen
und zu grosse Ausdrücke führen zu Fehlern ohne gespeicherten Teildatensatz.
Die bisherigen Mathematikfunktionen, Operatoren und Ausdruckslimits gelten
weiter. `mod`, `div`, `xor` sind in diesem Modus als Portnamen reserviert.

Alle Ergebnisformeln greifen ausschliesslich auf Eingaben, Rohbits, `x` und
`pi` zu; Ergebnisabhängigkeiten, Zuweisungsketten und Kontrollstrukturen sind
nicht Teil dieses Modus. Es wird der begrenzte AST-Interpreter verwendet,
ohne `eval`, Imports, Datei- oder Netzwerkzugriff. Mehrschrittige Programme
bleiben eine eigene Erweiterung nach PRIM-07.

Der gespeicherte Datensatz enthält die ursprüngliche Quelle als
`metadata.formula = {"version":1,"source":"…"}`, die Zuordnung der
Ergebnisausdrücke als `metadata.expression` und die kanonische Schnittstelle
als `metadata.interface`. Beim Import müssen Quelle, Ergebnisausdrücke und
Ports zusammenpassen. Die Syntaxversion gehört zur Funktionsidentität:
Ein historischer Ausdruck mit `^` wird niemals stillschweigend als Potenz
interpretiert. Ein Wechsel zwischen den Editoren übersetzt die Operatoren
ausdrücklich, etwa Python-XOR zu `xor(a,b)`.

- `POST /api/formulas/parse`: `formula` und optional `result_name`; liefert die
  Zuordnung `expression` ohne Vektorerzeugung.
- `POST /api/formulas/convert`: historische `expression`-Zuordnung; liefert
  eine semantisch entsprechende `formula`.
- `POST /api/formulas/expressions`: arithmetische `formula`; liefert eine
  semantisch entsprechende historische `expression`-Zuordnung.
- `POST /api/datasets`: erzeugt und speichert die Formel gemäss obigem Beispiel.

CLI: `generate --interface ports.json --inputs 8 --outputs 5 --formula
"c=mod(a+b,2^4), e=div(a+b,2^4)" --out vectors.json`. Alternativ liest
`--formula-file formula.txt` eine mehrzeilige UTF-8-Quelldatei. Formelquellen
sind mit den vorgegebenen Operations- und NAND-Referenzmodi nicht kombinierbar.

## NAND-Schreibweise

```text
1                        Eingangsbit 1 ohne Gatter
(1) ⊼ (2)                NAND von Eingangsbit 1 und 2
(1) ⊼ (1)                NOT von Eingangsbit 1
(1) ⊼ ((2) ⊼ (3))        NAND(x0, NAND(x1,x2))
```

Mehrfachverwendung von Eingängen ist erlaubt und für die funktionale Vollständigkeit
wichtig. NAND(a,b) ist 0, wenn beide Argumente 1 sind, andernfalls 1. Die Grammatik ist
`Ausdruck := Atom [ '⊼' Atom ]`, `Atom := Eingangsnummer | '(' Ausdruck ')'`.
Der Operator steht zwischen seinen beiden Argumenten. NAND ist nicht assoziativ;
weitere Verknüpfungen müssen deshalb ausdrücklich eingeklammert werden.
Auch `\bar{\wedge}` wird bei der Eingabe als Operator akzeptiert.
Das bisherige Klammerformat `(1,(2,3))` bleibt lesbar; Anzeige und Export verwenden
die Schreibweise mit `⊼`, auch bei bereits gespeicherten Programmen.
Identische, auch vertauschte NAND-Teilausdrücke werden beim Einlesen gemeinsam genutzt.

## Interne Schaltung

```json
{
  "inputs": 3,
  "gates": [[1,2], [0,3]],
  "outputs": [4]
}
```

Das entspricht `(1) ⊼ ((2) ⊼ (3))`. Alle Verweise beginnen hier bei 0:

- `0…N-1`: Eingänge.
- `N+i`: Ausgang des Gatters i.
- Gatter i darf nur auf Eingänge oder Gatter mit kleinerem Index verweisen.
- `outputs` enthält M Verweise; auch ein direkter Eingang ist zulässig.

Die Auswertung erfolgt in Listenreihenfolge. Es gibt keine impliziten Konstanten,
keine anderen Gatter und keine kombinatorischen Schleifen. Konstanten lassen sich
aus NAND ableiten. Nicht benötigte Gatter werden vor dem Speichern entfernt.
Ein Klammerexport kann gemeinsame Teilbäume stark vervielfachen; bei mehr als
10000 Zeichen wird stattdessen nur die Gatterliste angeboten.

## Gespeichertes Programm

Ein Bibliothekseintrag enthält `schema`, `id`, `name`, `created_at`, `circuit`,
`expressions`, `dataset_id`, `dataset_name`, `fitness` und `search`.

Wichtige Fitnessfelder:

| Feld | Bedeutung |
|---|---|
| `errors` | Anzahl falscher Ausgangsbits über alle gespeicherten Vektoren |
| `total_bits` | Anzahl Vektoren × M |
| `accuracy` | Anteil korrekter Ausgangsbits |
| `exact_on_dataset` | Kein Fehler auf den vorliegenden Vektoren |
| `verified_truth_table` | Kein Fehler und sämtliche 2^N Eingaben vorhanden |
| `gates` | Anzahl aktiver NAND-Gatter |
| `depth` | Längster Pfad von Eingang zu einem Ausgang, in Gattern |

Gleiche Schaltung und gleicher Datensatz erhalten dieselbe Kennung.
Bei erneutem Finden werden die Suchangaben durch den aktuellen Lauf ersetzt;
der erste Erstellungszeitpunkt bleibt erhalten. Es gibt noch kein separates Archiv
aller Suchläufe. Die Inhaltskennung verwendet die ersten zwölf Hex-Zeichen eines
SHA-256-Hashes und dient der praktischen Wiedererkennung.

`search.seed_library` nennt die fehlerfrei gespeicherten Bibliotheksquellen, die
beim Start vorlagen. `library_candidates` zählt die davon zum Budget und N passenden
Schaltungen. Das ist keine Aussage, dass jeder aufgeführte Baustein in der endgültigen
Lösung enthalten ist.

## Erlaubte Vektorausdrücke

Variablen: `x`, `a`, `b`, `x0…x(N-1)`, `pi`.
Operatoren: Arithmetik, ganzzahlige Division, Modulo, `& | ^ ~ << >>`, `**`,
Vergleiche, `and`, `or`, `not` und `wert if bedingung else anderer_wert`.
Funktionen: `sin`, `cos`, `sqrt`, `isqrt`, `floor`, `ceil`, `abs`, `min`, `max`, `round`.
Schiebeweiten und Exponenten liegen zwischen 0 und 32. Endliche Zwischenwerte
müssen betragsmässig höchstens 2^128 sein. Das Endergebnis muss eine ganze Zahl
zwischen 0 und 2^M−1 sein; ein Überlauf wird nicht stillschweigend abgeschnitten.
Gewünschten Überlauf explizit formulieren, etwa `(a+b) % 16`.


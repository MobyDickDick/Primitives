# Mehrschrittige Programme und Ablaufdebugger (PRIM-07/08)

Für symbolische Bitbreiten, eigene Funktionen wie `def add<w>(a,b):` und
rekursive Aufrufe `add<n>(a,b)` gibt es zusätzlich
[parametrierte Templates der Sprachversion 2](TEMPLATES.md).

**Mehrschrittiges Programm definieren** öffnet den Programmeditor. Ein- und
Ergebnisports erhalten eigene Namen, Bitbreiten, Vorzeichen und Überlaufregeln.
Die Beispiele **Summe for**, **Summe while**, **Auswahl if/else** und
**Bitreihenfolge umkehren**, **Summe · Rücksprung** und **Auswahl · Zero-Sprung**
lassen sich direkt einsetzen.
**Programm speichern & Vektoren erzeugen** speichert die
Funktion unter **Definierte Funktionen**, sobald alle angeforderten Eingaben
erfolgreich berechnet sind. **Funktion öffnen** stellt Quelle, Schnittstelle,
Budgets, Seed und Vektoranzahl wieder her. Export/Import erhält diese Daten.

**Vektorerzeugung abbrechen** beendet den laufenden Auftrag. Bei Abbruch,
ungültiger Ausgabe oder überschrittenem Budget wird kein neuer Datensatz
gespeichert. Ein bereits geöffneter Vektorsatz bleibt nutzbar. Die anschliessende
Evolution verwendet dieselben kombinatorischen N+M-Bitvektoren wie bisher.
Eine Programmreferenz ist sofort nutzbar, auch ohne gefundene NAND-Schaltung.

## Syntax der Sprachversion 1

Die Sprache verwendet Python-ähnliche Einrückung. Sie wird von einem eigenen
Interpreter ausgeführt; es wird kein Python-Programm mit `eval` oder `exec`
gestartet. Vier Leerzeichen pro Block sind empfohlen. Leerzeilen und
`# Kommentare` sind erlaubt, auch am Ende einer Anweisung. Kommentare bleiben
beim Speichern, Wiederöffnen und Export/Import im Quelltext erhalten und
verbrauchen keine Ausführungsschritte. Bezeichner beginnen mit einem ASCII-Buchstaben,
gefolgt von höchstens 31 Buchstaben, Ziffern oder Unterstrichen.

```text
Anweisung    := Name = Ausdruck
             | Name[Index] = Ausdruck  # einzelnes Bit setzen
             | Name += Ausdruck        # ebenso -=, *=, //=, %=, **=, &=, |=, ^=, <<=, >>=
             | Name[Index] ^= Ausdruck # z. B. einzelnes Bit invertieren
             | return Ausdruck [, Ausdruck ...]
             | if Ausdruck: Block [else: Block]
             | while Ausdruck: Block
             | for Name in range(Ausdruck [, Ausdruck [, Ausdruck]]): Block
Block        := eingerückte Anweisungen
```

Blöcke können verschachtelt werden; `elif` ist ebenfalls erlaubt. Jeder
ausgeführte Pfad muss mit `return` enden. Die Rückgabewerte entsprechen **der
Reihenfolge der Ergebnisports**. Für c und e z. B. `return s % 16, s // 16`.
Ein Portname ist eine Beschriftung, kein automatisch initialisierter Ergebniswert.

Eingänge sind schreibgeschützt. Eine Zuweisung legt eine lokale Variable an;
sie muss vor dem ersten Lesen auf dem tatsächlich genommenen Pfad zugewiesen
worden sein. Alle lokalen Variablen und Schleifenzustände werden **für jede
Eingabe neu angelegt**. Es gibt keine globalen Variablen oder Zustandsübernahme.

`for (i = 0; i < n; i++) { ... }` wird gleichwertig geschrieben:

```text
s = 0
for i in range(n):
    s += i
return s
```

`range(n)` zählt 0 bis n−1. `range(start, stop)` und
`range(start, stop, step)` erlauben andere Startwerte und negative Schritte.
Die Grenze `stop` ist ausgeschlossen; ein Schritt von 0 ist ein Fehler.
Grenzen und Schritt werden beim Eintritt in die Schleife einmal ausgewertet.
Die Schleifenvariable darf im Block geändert werden; die nächste Iteration
verwendet den nächsten Wert der ursprünglichen Zahlenfolge. Bei null Durchläufen
wird die Schleifenvariable nicht zugewiesen; eine vorherige Zuweisung bleibt erhalten.
Verschachtelte Schleifen zählen gemeinsam gegen das Iterationsbudget je Eingabe.

Dieselbe Summe mit `while`:

```text
s = 0
i = 0
while i < n:
    s += i
    i += 1
return s
```

Ein verschachteltes `if/else`:

```text
if n < 8:
    if n == 0:
        c = 1
    else:
        c = n * 2
else:
    c = n - 1
return c
```

Die [sechs Beispieltabellen](../examples/programs/) prüfen jeweils alle
16 Eingaben von n[4]. Ihre `.prim`-Quellen und `interface.json` liegen daneben;
`python tools/export_programs.py` erzeugt sie reproduzierbar neu.

## Zahlen und Ausdrücke

Eingänge werden gemäss Ports unsigned oder als Zweierkomplement dekodiert.
Lokale Zahlen sind ganze Zahlen im Bereich −2^128 bis 2^128; Zwischenrechnungen
werden nicht auf die Portbreite abgeschnitten. Erst die Ausgabe wird gemäss
Ergebnisport geprüft bzw. modulo 2^Breite abgeschnitten. LSB-first, maximal
32 Eingangs- und 32 Ausgangsbits sowie 65536 Vektoren gelten weiterhin.

Erlaubt sind Integer-/Bool-Literale, Variablen, Klammern und:

| Art | Schreibweise |
|---|---|
| Arithmetik | `+`, `-`, `*`, `//`, `%`, `**` |
| Bitweise | `&`, `\|`, `^`, `~`, `<<`, `>>` |
| Vergleiche | `==`, `!=`, `<`, `<=`, `>`, `>=`, auch verkettet |
| Bedingungen | `and`, `or`, `not`; `a if bedingung else b` |
| Funktionen | `abs(a)`, `min(a,b)`, `max(a,b)`, `div(a,b)`, `mod(a,b)`, `xor(a,b)` |
| Bit-Arrays | `[0, 1]`, `[0] * n`, `a + b`, `a[i]`, `a[start:stop:step]` |
| Arrayfunktionen | `bits(zahl, breite)`, `pack(a)`, `len(a)` |

`**` bedeutet Potenz, `^` bedeutet XOR. `//` und `div` runden ab, z. B.
−7 // 3 = −3 und −7 % 3 = 2. Das entspricht der bisherigen Ausdruckssyntax;
im separaten arithmetischen **Formelmodus** ist `^` weiterhin Potenz.
Division durch null ist ein Fehler. Schiebeweiten und Exponenten sind 0–32.
Boolesche Ergebnisse werden 0 oder 1, Bedingungen prüfen null/nicht null.
`and` und `or` liefern 0/1 und werten den zweiten Operanden nur bei Bedarf aus.
Funktionsnamen und `range` sind für Ports und lokale Namen reserviert.

### Bit-Arrays für kurze Funktionsbeschreibungen

Bit-Arrays sind eindimensional und enthalten ausschliesslich 0 oder 1
(auch `False`/`True`). Ein Array enthält höchstens 128 Bits; leere Arrays
sind erlaubt. Literale, Wiederholungen und Verkettungen erzeugen Arrays:
`a = [0, 1, 0]`, `a = [0] * 4`, `a + [1]`. Die Wiederholungsanzahl muss
nichtnegativ sein; die maximale Länge wird vor dem Anlegen geprüft.

`bits(n, breite)` zerlegt eine Zahl in 1–128 Bits, **LSB-first**:
`bits(6, 4)` ergibt `[0, 1, 1, 0]`. Index 0 ist das niederwertigste Bit.
Es werden die unteren Bits verwendet; negative Zahlen erscheinen im
Zweierkomplement, z. B. `bits(-2, 4)` ergibt `[0, 1, 1, 1]`.
`pack(a)` bildet die nichtnegative Zahl aus dem Array, `len(a)` dessen Länge.
`pack([])` ist 0. Für Ergebnisports weiterhin ganze Zahlen zurückgeben:
`return pack(a)`. Vorzeichen und Überlauf werden danach wie bisher anhand
des Ergebnisports geprüft; `pack` interpretiert kein Vorzeichen.

Einzelne Bits lassen sich mit `a[i]` lesen und mit `a[i] = 1` oder
`a[i] ^= 1` ändern. Indizes müssen zwischen 0 und `len(a)-1` liegen;
negative Einzelindizes sind Fehler. `b = a` verweist wie in Python auf
dasselbe Array; `b = a[:]` erstellt eine unabhängige Kopie.
Alle Arrays starten für jede Programmeingabe neu.

Ausschnitte folgen der Python-Schreibweise: `a[1:3]` nimmt die Bits 1 und 2,
`a[:2]` die ersten beiden Bits und `a[::-1]` kehrt die Reihenfolge um.
Negative Ausschnittgrenzen sind erlaubt; Grenzen werden auf die Arraylänge
begrenzt. Ein Schritt von 0 ist ungültig. Zuweisungen an ganze Ausschnitte,
verschachtelte Arrays und Methoden wie `append` sind nicht erlaubt.
Rechenoperatoren und Bedingungen erwarten Zahlen; Arraywerte vorher mit
`pack(a)` oder `len(a)` umwandeln. Schleifen verwenden `range(len(a))`.

Beispiel für n[4], das die Bitreihenfolge umkehrt (6 → 6, 3 → 12):

```text
# Vier Eingangsbits in umgekehrter Reihenfolge ausgeben
a = bits(n, 4)  # Index 0 ist das niederwertigste Bit
return pack(a[::-1])
```

Dasselbe mit einzeln gesetzten Bits:

```text
a = bits(n, 4)
r = [0] * len(a)
for i in range(len(a)):
    r[i] = a[len(a) - 1 - i]
return pack(r)
```

Nicht unterstützt sind Fliesskommazahlen, `/`, Strings als Rechenwerte, allgemeine Listen, Attribute,
Imports, eigene Funktionen und Rekursion in Version 1, I/O, `break`, `continue`, Schleifen-`else`,
Unterprogrammaufrufe und fehlerabhängige Sprünge.
Schleifen im Quelltext erzeugen keine Rückkopplung im NAND-Netz. Dauerhafter
Zustand benötigt das separat geplante Registermodell.

## Labels und Sprünge (PRIM-08)

Sprachversion 1 erlaubt folgende eigenständige Anweisungen. Die Klammernotation
ist Syntax des begrenzten Interpreters. Labels sind feste Zeichenketten mit
1–32 Zeichen: ASCII-Buchstabe, danach Buchstaben, Ziffern oder `_`.

| Anweisung | Wirkung |
|---|---|
| `label("ziel")` | Im ganzen Programm eindeutiges Sprungziel |
| `goto("ziel")` | Unbedingter Sprung |
| `jump_if(bedingung, "ziel")` | Springt bei einem Wert ungleich null |
| `jump_zero(a, "ziel")` | Springt bei a = 0 (TinyCPU: Zero) |
| `jump_nonzero(a, "ziel")` | Springt bei a ≠ 0 (TinyCPU: NotZero) |
| `jump_negative(a, "ziel")` | Springt bei a < 0 (TinyCPU: Negative) |

Die Bedingungen lesen den angegebenen Integer-Ausdruck, kein implizites
Flagregister. Negative Eingänge benötigen Zweierkomplement; lokale Zwischenwerte
können ebenfalls negativ sein. Ein Fehlerregister und Fehler-Sprungbefehle sind
nicht unterstützt. Die Zuordnung bedeutet keine vollständige TinyCPU-ISA-Kompatibilität.

```text
s = 0
i = 0
label("loop")
jump_if(i >= n, "done")
s += i
i += 1
goto("loop")
label("done")
return s
```

Dies berechnet die Summe 0 bis n−1, auch für n=0. Das zweite Beispiel nimmt
den Sprung bei n=0; bei n>0 wird die Eingabe unverändert zurückgegeben:

```text
jump_zero(n, "zero")
return n
label("zero")
return 42
```

Unbekannte/doppelte Labels, dynamische Ziele und ungültige Namen werden vor
dem Lauf abgelehnt, auch in unerreichbarem Code. Ein Ziel muss im selben oder
einem umgebenden Block liegen. Das Einspringen von aussen oder aus Nachbarblöcken
in `if`, `else`, `while` oder `for` ist verboten. Ein Rücksprung vor eine
`for`-Anweisung initialisiert deren range-Zustand neu. Lokale Variablen behalten
innerhalb einer Eingabe ihre Werte. Wird eine erste Zuweisung übersprungen,
liefert das Lesen der noch ungesetzten Variable einen Fehler mit Quellposition.
Genommene Rückwärtssprünge zählen zusätzlich als Iteration. Labels selbst sind
begrenzte Leerschritte. Dieselben Abbruchprüfungen und Budgets gelten wie bisher.

## Ablaufdebugger für eine Testeingabe

Unter **Programmablauf debuggen** eine unsigned Eingangsbitkombination `x`
eintragen. Sie kombiniert alle Eingangsports LSB-first gemäss Portreihenfolge;
die dekodierten Werte erscheinen unter **Variablen**. **Start** übernimmt Quelle,
Ports und Budgets und hält vor der ersten Anweisung. Änderungen im Editor oder
Eingabefeld gelten erst nach einem neuen Start. Die Debugquelle bleibt separat sichtbar.

- **Eine Programmanweisung** führt genau eine interne Anweisung aus.
- **Fortsetzen** arbeitet in Abschnitten von höchstens 100 Anweisungen bis
  zur Rückgabe, zum Fehler oder zu **Stoppen**. Der aktuelle Abschnitt endet
  vor dem Stoppen. Derselbe Zustand kann danach fortgesetzt werden.
- **Zurücksetzen** stellt dieselbe übernommene Eingabe und Quelle mit frischen
  Variablen, Arrays, Schleifenzuständen und Budgets wieder her.

Markiert wird die nächste Quellzeile; nach Rückgabe/Fehler bleibt die letzte
Anweisung sichtbar. PC ist der nullbasierte Index der internen Anweisung.
Strukturierte Kontrollen erzeugen interne Anweisungen (`test`, `jump`,
`iteration`, `range`, `next`), die dieselbe Quellzeile markieren können.
Labels erscheinen als `label`, explizite Sprünge als `branch`.
**Programmanweisungen** zählt diese Anweisungen; **Budgetschritte** zählt auch
Ausdrücke und Arrayarbeit. Grosse Integer werden exakt angezeigt. **Ergebnis**
zeigt die rohe Rückgabe und die kodierten Portwerte nach Breite/Überlaufregel.
Ein Ausgabeüberlauf wird als Fehler angezeigt. Direkte Ausführung und Debugger
verwenden denselben Interpreter. NAND-Gatterschritte im Schaltbild untersuchen
weiterhin separat die gefundene kombinatorische Schaltung.

Debuggen speichert keine Vektoren und ändert keine Funktion. Sitzungen sind
flüchtig und werden beim Serverneustart verworfen. Ein Server hält höchstens
32 Sitzungen; weitere Starts verdrängen die älteste Sitzung.

## Budgets und Fehler

| Parameter | Standard | Maximum |
|---|---:|---:|
| `steps` je Eingabe | 10000 | 100000 |
| `iterations` je Eingabe | 10000 | 100000 |
| `total_steps` über alle Vektoren | 1000000 | 5000000 |

Jede ausgeführte interne Anweisung und jeder besuchte Ausdrucksknoten verbraucht
einen Schritt. Schleifenprüfungen und interne Kontrollübergänge zählen mit;
eine leere bzw. endlose Schleife kann das Budget nicht umgehen. Jede tatsächlich
betretene Schleifeniteration und jeder genommene Rückwärtssprung verbrauchen zusätzlich eine Iteration. Auch
Rückgabeausdrücke zählen mit. Höhere Bitbreiten benötigen häufig Stichproben
oder angepasste Budgets. Eine erfolgreiche Stichprobe bleibt eine Stichprobe.

Jedes Bit eines ausgewerteten Arrayergebnisses verbraucht zusätzlich einen
Schritt, auch beim Lesen einer Arrayvariable, Kopieren oder Umwandeln mit `bits`.
Damit zählen auch Arrayoperationen gegen die Budgets und prüfen auf Abbruch.

Weitere feste Grenzen: 16000 Quellzeichen, 2000 Syntaxknoten, 64 lokale Namen,
128 Bits je Array,
16 verschachtelte Kontrollstrukturen und Ausdruckstiefe 32. Nicht unterstützte
Syntax wird vor der Ausführung geprüft, auch in unerreichbaren Zweigen.
Laufzeitfehler enthalten Eingabe x, dekodierte Portwerte und Quellzeile/-spalte;
Überlauffehler nennen Ergebnisport und Eingabe. Abbruch wird bei jedem
Anweisungs-/Ausdrucksschritt sowie vor dem Speichern geprüft.

## CLI, API und Speicherformat

```powershell
python -m primitives generate --name "Summe for" --inputs 4 --outputs 8 --interface examples/programs/interface.json --program-file examples/programs/sum-for.prim --out summe.json
```

Budgets lassen sich mit `--program-steps`, `--program-iterations` und
`--program-total-steps` überschreiben; `--samples`/`--seed` steuern die Auswahl.
Ctrl+C bricht vor dem Schreiben der Ausgabedatei ab. Fehler während der
Erzeugung überschreiben keine vorhandene Ausgabedatei.

`POST /api/datasets/generate` startet einen asynchronen Auftrag:

```json
{
  "name": "Summe for",
  "inputs": 4,
  "outputs": 8,
  "samples": 16,
  "seed": 1,
  "interface": {
    "inputs": [{"name": "n", "bits": 4}],
    "outputs": [{"name": "c", "bits": 8, "overflow": "error"}]
  },
  "program": {
    "version": 1,
    "source": "s = 0\nfor i in range(n):\n    s += i\nreturn s",
    "limits": {"steps": 10000, "iterations": 10000, "total_steps": 1000000}
  }
}
```

Die Antwort enthält `job_id` (HTTP 202). `GET /api/jobs/{id}` liefert
`queued`, `running`, `cancelling`, `cancelled`, `failed` oder `done` und
`kind: "dataset"`. Bei Erfolg enthält `result` die Datensatzkennung `id` und
`dataset`. `POST /api/jobs/{id}/cancel` mit `{}` bricht ab. Es läuft höchstens
ein manueller Such-/Erzeugungsauftrag gleichzeitig. Die Hintergrundsuche pausiert
währenddessen. Jobzustände sind flüchtig, fertige Datensätze bleiben gespeichert.

`POST /api/datasets` akzeptiert dieselbe Programmdefinition synchron für kurze
Aufrufe sowie wie bisher fertige Datensätze zum Import. Im Datensatz bleibt
`schema: 1`; `metadata.program` speichert Quelle, Sprachversion und kanonische
Budgets, `metadata.interface` die Ports und `metadata.seed` den Stichprobenseed.
Es wird keine zusätzliche Ausdrucks-/Operations-/Schaltungsreferenz behauptet.
Quelltext, Sprachversion und Schnittstelle bestimmen die Funktionsidentität;
Seed, Vektoranzahl und Ausführungsbudgets erzeugen keine weitere Funktion.

`POST /api/source-debug/start` mit `program`, `interface` und `x` liefert eine
Sitzungskennung `id` und den Anfangszustand. `POST /api/source-debug/{id}/{aktion}`
mit `{}` unterstützt `step`, `continue`, `stop`, `reset` und `close`.
`continue` führt maximal 100 Anweisungen aus. Zustände sind `paused`, `stopped`,
`done` oder `failed`; gestoppte Sitzungen können fortgesetzt werden. Antworten
enthalten PC, Quellzeile, Variablen, Zähler und gegebenenfalls Ergebnis/Fehler.
Validierungsfehler liefern HTTP 400, Laufzeitfehler stehen in `error`.
Integer-Variablen und rohe Rückgaben sind für exakte JSON-Darstellung
Dezimalstrings, Bit-Arrays bleiben Listen und kodierte Portwerte Zahlen.

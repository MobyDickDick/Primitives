# Mehrschrittige Programme als Vektorquelle (PRIM-07)

**Mehrschrittiges Programm definieren** öffnet den Programmeditor. Ein- und
Ergebnisports erhalten eigene Namen, Bitbreiten, Vorzeichen und Überlaufregeln.
Die Beispiele **Summe for**, **Summe while** und **Auswahl if/else** lassen sich
direkt einsetzen. **Programm speichern & Vektoren erzeugen** speichert die
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
`# Kommentare` sind erlaubt. Bezeichner beginnen mit einem ASCII-Buchstaben,
gefolgt von höchstens 31 Buchstaben, Ziffern oder Unterstrichen.

```text
Anweisung    := Name = Ausdruck
             | Name += Ausdruck        # ebenso -=, *=, //=, %=, **=, &=, |=, ^=, <<=, >>=
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

Die [drei Beispieltabellen](../examples/programs/) prüfen jeweils alle
16 Eingaben von n[4]. Ihre `.prim`-Quellen und `interface.json` liegen daneben;
`python tools/export_programs.py` erzeugt sie reproduzierbar neu.

## Zahlen und Ausdrücke

Eingänge werden gemäss Ports unsigned oder als Zweierkomplement dekodiert.
Lokale Werte sind ganze Zahlen im Bereich −2^128 bis 2^128; Zwischenrechnungen
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

`**` bedeutet Potenz, `^` bedeutet XOR. `//` und `div` runden ab, z. B.
−7 // 3 = −3 und −7 % 3 = 2. Das entspricht der bisherigen Ausdruckssyntax;
im separaten arithmetischen **Formelmodus** ist `^` weiterhin Potenz.
Division durch null ist ein Fehler. Schiebeweiten und Exponenten sind 0–32.
Boolesche Ergebnisse werden 0 oder 1, Bedingungen prüfen null/nicht null.
`and` und `or` liefern 0/1 und werten den zweiten Operanden nur bei Bedarf aus.
Funktionsnamen und `range` sind für Ports und lokale Namen reserviert.

Nicht unterstützt sind Fliesskommazahlen, `/`, Strings, Listen, Attribute,
Imports, eigene Funktionen, Rekursion, I/O, `break`, `continue`, Schleifen-`else`,
Labels und explizite Sprünge. Labels und Ablaufdebugger sind PRIM-08.
Schleifen im Quelltext erzeugen keine Rückkopplung im NAND-Netz. Dauerhafter
Zustand benötigt das separat geplante Registermodell.

## Budgets und Fehler

| Parameter | Standard | Maximum |
|---|---:|---:|
| `steps` je Eingabe | 10000 | 100000 |
| `iterations` je Eingabe | 10000 | 100000 |
| `total_steps` über alle Vektoren | 1000000 | 5000000 |

Jede ausgeführte interne Anweisung und jeder besuchte Ausdrucksknoten verbraucht
einen Schritt. Schleifenprüfungen und interne Kontrollübergänge zählen mit;
eine leere bzw. endlose Schleife kann das Budget nicht umgehen. Jede tatsächlich
betretene Schleifeniteration verbraucht zusätzlich eine Iteration. Auch
Rückgabeausdrücke zählen mit. Höhere Bitbreiten benötigen häufig Stichproben
oder angepasste Budgets. Eine erfolgreiche Stichprobe bleibt eine Stichprobe.

Weitere feste Grenzen: 16000 Quellzeichen, 2000 Syntaxknoten, 64 lokale Namen,
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

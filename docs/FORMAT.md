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


# Architektur und Entwurfsentscheidungen

## Sprachwahl

TinyLanguage ist als echte Suchsprache eingebunden: `tiny/evolve.tiny` steuert
Erzeugungsschritte, Mutation, Rekombination, Auswahl und Abbruch.
Die vorhandene Python-Implementierung von TinyLanguage macht einen kleinen
Python-Host sinnvoll. Go ist in dieser Umgebung nicht installiert; mit dem
verwendbaren TinyLanguage-Interpreter war ein Wechsel zu Go nicht nötig.

Die FFI erlaubt ausschliesslich `configure`, `specimen`, `score`, `trace` und
`finish` aus `primitives.tiny_bridge`. Die aufwendige Fitnessbewertung und das
Einsetzen gespeicherter Schaltungen laufen im Host. Die Laufzeit wird separat
unter `.runtime/tinylanguage/` eingerichtet, da der Interpreter selbst eine
zusammengesetzte Python-Datei in seinem Quellordner erzeugt.
TinyLanguage bleibt eine externe Abhängigkeit; sein Quellcode wird nicht als
Bestandteil dieses Projekts verteilt. Alternativ kann `TINYLANGUAGE_HOME` auf
einen eingerichteten, beschreibbaren TinyLanguage-Ordner zeigen.

```text
Browser (HTML / CSS / JavaScript, SVG)
    │ lokale JSON-Anfragen
Python HTTP-Server ─── Dataset ─── Bibliothek (JSON)
    │ asynchroner Suchauftrag
TinyLanguage-Prozess ─── explizite Python-FFI
    │                        │
Evolution                  Fitness / Bausteine
    └──────── Ergebnis ──────┘
```

## Dateien

| Datei | Aufgabe |
|---|---|
| `primitives/circuit.py` | NAND-Schaltung, Parser, Auswertung und Kompaktierung |
| `primitives/blocks.py` | Feste Bausteinversionen, verschachtelte Instanzen, Portverbindungen und NAND-Expansion |
| `primitives/dataset.py` | Vektoren, Konsistenz, Kodierung, Ausdrücke, Vorlagen |
| `primitives/ports.py` | Benannte Schnittstellen, Bitoffsets, Vorzeichen, Ergebnisüberlauf |
| `primitives/operations.py` | Operationsdefinitionen und konkrete Breitenvarianten als Referenzen |
| `tools/export_operations.py` | Kleine importierbare Standardtabellen des Operationskatalogs |
| `tools/verify_tinycpu.py` | Optionaler direkter Abgleich mit einem lokalen TinyCPU-Interpreter |
| `primitives/formula.py` | Eigene arithmetische Ergebnisformeln und explizite Syntaxübersetzung |
| `primitives/evolution.py` | Genom, Fitness, Bibliothekskomposition, Python-Backend |
| `tiny/evolve.tiny` | TinyLanguage-Evolution |
| `primitives/tiny_bridge.py` | Kleine FFI-Schnittstelle |
| `primitives/runner.py` | Auswahl des Backends und Prozessstart |
| `primitives/library.py` | Benennung, Laden und atomisches Speichern |
| `primitives/server.py` | Lokale API und Hintergrundauftrag |
| `web/` | Benutzeroberfläche mit SVG-Simulation |

Benannte Ports erweitern das Datensatzformat optional; die Evolution verarbeitet
weiter dieselben N+M-Bitvektoren. Operationsdefinition, konkrete Breitenvariante
und NAND-Implementierung haben getrennte Rollen. Beliebige bestehende
NAND-Schaltungen können als bitweise Busreferenz für eine neue Aufgabenvariante
dienen. Vorhandene mathematische Referenzen werden dafür bevorzugt. Eine
Breitenänderung erzeugt neue Sollvektoren und benötigt eine passende Schaltung.

## Evolution

Ein Genom enthält für jedes der G Gatter zwei Verweise und anschliessend M
Ausgangsverweise, also 2G+M Ganzzahlen. Die zulässigen Werte hängen von der Position
ab; dadurch entstehen auch bei Mutation und Rekombination keine Vorwärtsverweise.

Der erste Prototyp verwendet eine kompakte Steady-State-Variante mit zwei Eltern
und einer einstellbaren Zahl von Nachkommen pro Generation:

1. Zufällige Kandidaten oder neu verdrahtete Bibliotheksbausteine erzeugen.
2. Einen Kandidaten mit dem aktuellen Elternprogramm beginnen lassen.
3. Mit Wahrscheinlichkeit 35 % Gene vom zweiten Elternprogramm übernehmen.
4. Jedes Gen mit Wahrscheinlichkeit 1/(2G+M) durch einen zulässigen Verweis ersetzen.
5. In 15 % der Versuche stattdessen einen neuen zufälligen/Bibliothekskandidaten nutzen.
6. Gleich gute oder bessere Kandidaten übernehmen; das vorige Elternprogramm
   wird zum zweiten Elternprogramm. Gleichstände erlauben neutrale Veränderung.
7. Bei null Fehlern oder am Ende des Generationenbudgets stoppen.

Beide Eltern werden zunächst mit einem Kandidaten initialisiert; nur der erste wird
als Ausgangsbester bewertet. Das ist keine klassische grosse Elternpopulation.
Eine breitere Auswahlstrategie ist ausdrücklich eine Folgeaufgabe.

Die Fitness wird lexikographisch nach falschen Ausgangsbits, aktiven Gattern und
Gattertiefe bewertet. Implementiert ist die ganzzahlige Rangzahl
`Fehler*(G+1)^2 + aktive_Gatter*(G+1) + Tiefe`. Eine Verbesserung bei Fehlern
wiegt immer stärker als sämtliche Strukturkosten. Tote Gatter dürfen während der
Suche existieren, werden aber nicht als aktive Gatter berechnet.

Für die Bewertung stehen alle Vektoren als Bits in grossen Python-Ganzzahlen.
Ein NAND berechnet dadurch eine ganze Spalte parallel. Die eigentliche skalare
Bitsemantik bleibt dieselbe und wird unabhängig dagegen getestet.

Beim Einsetzen einer gespeicherten Schaltung werden ihre formalen Eingänge an
zufällig gewählte verfügbare Drähte angeschlossen. Bis zu zwei solche Schaltungen
werden nacheinander eingefügt; die zweite kann die Ergebnisse der ersten verwenden.
Die Schaltungen werden in NAND-Gatter expandiert. Die Suche kann anschliessend
auch innerhalb eines eingefügten Bausteins mutieren. In der separaten
Bausteinbibliothek bleiben Definitionen und verschachtelte Instanzen dagegen
über Inhaltskennungen unveränderlich gespeichert. Beide Suchbackends verwenden
deren Expansionen und geben flache Ergebnisse ohne Hierarchiebehauptung zurück.
`search.seed_blocks` nennt verfügbare Quellen, keine belegte Abstammung.
Die Paket-, Port- und Versionssemantik ist in [BAUSTEINE.md](BAUSTEINE.md) beschrieben.

Seeds sind für denselben Backendtyp, dieselbe Laufzeit, dieselbe Bibliothek und
dieselben Einstellungen reproduzierbar. TinyLanguage und Python verbrauchen
Zufallswerte unterschiedlich und liefern beim selben Seed nicht zwingend dieselbe
Schaltung. Bibliothekseinträge werden in stabiler Dateireihenfolge eingelesen.

## Lokalbetrieb und Aufträge

Der Webserver bindet ausschliesslich an `127.0.0.1`. Zustandsändernde API-Anfragen
erfordern JSON und lehnen fremde Browser-Origins ab. Ein Hintergrundthread
führt jeweils eine Suche aus. TinyLanguage läuft in einem eigenen Prozess mit
300-Sekunden-Zeitlimit; Python läuft im Hintergrundthread mit Kandidatenbudget.
Es gibt keine Cloudspeicherung, externe Skripte oder externen UI-Abhängigkeiten.

Jobzustände sind nur im Arbeitsspeicher vorhanden. Das fertige Ergebnis und seine
Vektoren werden vor der Erfolgsmeldung in der Bibliothek gespeichert.

## Geplante Rückkopplung

Eine reine NAND-Schleife ohne Verzögerung besitzt nicht zwingend einen eindeutigen
Wert. Für internen Zustand soll deshalb ein synchrones Registermodell gelten:

1. Externe Eingaben und der aktuelle Registerzustand bilden den Eingabevektor.
2. Die azyklische NAND-Schaltung wird vollständig ausgewertet.
3. Sichtbare Ausgaben werden bereitgestellt.
4. Alle gewählten Rückschreibungen werden gleichzeitig in den nächsten Zustand übernommen.

Zwei mögliche Rückschreibregeln:

- **Löschen und schreiben:** Der neue interne Eingabeblock beginnt mit null;
  danach werden ausgewählte Ausgangsbits auf ihre Ziele geschrieben.
- **Überschreiben:** Der bisherige interne Eingabeblock bleibt erhalten;
  nur explizit zugeordnete Stellen werden ersetzt.

Externe Eingänge werden dabei separat behandelt. Mehrere Ausgänge mit demselben
Rückschreibziel müssen beim Validieren abgelehnt werden. Ein Startzustand und
eine Taktzahl werden Pflichtangaben.

Für solche Maschinen reichen einzelne N+M-Vektoren nicht mehr aus. Geeignet sind
Folgen aus Eingang, Sollausgang und optional Anfangszustand. Dieselben externen
Eingaben mit unterschiedlichen Ausgaben sind dann zulässig, wenn der Zustand
verschieden ist. Widerspruchsfrei bleiben muss die Funktion aus vollständigem
Eingabe- und Zustandsvektor zum Ausgabe- und Folgezustandsvektor.


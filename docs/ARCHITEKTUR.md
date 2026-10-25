# Architektur und Entwurfsentscheidungen

## Sprachwahl

TinyLanguage ist als echte Suchsprache eingebunden: `tiny/evolve.tiny` steuert
Erzeugungsschritte, Mutation, Rekombination, Auswahl und Abbruch.
Die vorhandene Python-Implementierung von TinyLanguage macht einen kleinen
Python-Host sinnvoll. Go ist in dieser Umgebung nicht installiert; mit dem
verwendbaren TinyLanguage-Interpreter war ein Wechsel zu Go nicht nötig.

Die FFI erlaubt ausschliesslich `configure`, `specimen`, `score`, `trace`,
`finish`, `begin_restart`, `initial`, `observe` und `population_buffer` aus
`primitives.tiny_bridge`. Die aufwendige Fitnessbewertung und das
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
| `primitives/program.py` | Begrenzter Integer-Interpreter für Zuweisungen, return, if/else, while und for |
| `tools/export_programs.py` | Reproduzierbare vollständige Programmbeispiele samt Quellen |
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

Beide Backends verwenden eine Steady-State-Elternpopulation mit Turnierselektion.
`population` (2–256, Standard 24) bestimmt die Elternzahl und zugleich die maximale
Zahl von Nachkommen je Generation:

1. Die Elternpopulation mit zufälligen oder neu verdrahteten Bibliothekskandidaten
   füllen und jedes Mitglied bewerten. Beide Backends können mit der bisherigen Lösung beginnen.
2. Für jeden der beiden Eltern unabhängig bis zu drei Populationsmitglieder mit
   Zurücklegen ziehen und das beste gezogene Mitglied wählen. Bei gleicher Fitness
   gewinnt die erste Ziehung; bei Population 2 bestehen Turniere aus zwei Ziehungen.
3. Eine Kopie des ersten Elternprogramms erzeugen. Mit Wahrscheinlichkeit 35 %
   jedes Gen unabhängig mit Wahrscheinlichkeit 50 % vom zweiten Elternprogramm übernehmen.
4. Jedes Gen mit Wahrscheinlichkeit 1/(2G+M) durch einen zulässigen Verweis ersetzen.
5. In 15 % der Versuche stattdessen einen neuen zufälligen/Bibliothekskandidaten nutzen.
6. Ein zufällig gewähltes Mitglied mit schlechtestem Rang ersetzen, sofern der
   Nachkomme mindestens gleich gut ist. Dadurch bleiben bessere Eltern erhalten;
   Gleichstände erlauben neutrale Veränderung an unterschiedlichen Populationsplätzen.
7. Das beste gefundene Genom separat sichern. Bei null Fehlern oder ausgeschöpftem
   Generationen-/Kandidatenbudget stoppen. Der Python-Hintergrundmodus `optimize`
   sucht auch bei null Fehlern weiter und respektiert zusätzlich sein Zeitbudget.

Die Initialisierung zählt zum gesamten Bewertungsbudget
`min(500000, 1 + population * generations)`. Deshalb kann die letzte Generation
weniger Nachkommen enthalten. Frühe Fehlerfreiheit oder ein Zeitlimit dürfen die
Initialisierung beenden; mindestens der erste Kandidat wird bewertet, damit immer
ein Ergebnis vorhanden ist. Abbruch wird vor jeder Bewertung geprüft.
Gespeicherte Suchmetadaten nennen `selection`, `tournament_size`, die tatsächlich
initialisierte `parent_population` und `evaluation_budget`. Der Verlauf enthält
nur Verbesserungen des bisher besten Rangs, beginnend nach der Initialisierung.

### Unabhängige Starts und Inseln

`restarts` (1–32, Standard 1) bezeichnet die gesamte Zahl unabhängiger Starts,
einschliesslich des ersten. Alle teilen das unveränderte Kandidatenbudget B.
Start r (ab 0) darf bis zum kumulativen Limit `floor(B*(r+1)/restarts)` bewerten.
Bei B=64 und drei Starts sind das 21, 21 und 22 Bewertungen. Die Initialisierung
jedes Starts zählt mit; Konfigurationen mit weniger Budget als Eltern je Start
werden abgelehnt. Ein zusätzlicher Start erhöht das Gesamtbudget nicht.

Start r verwendet `(seed+r) mod 2^31`. Nur der erste Start darf die bisherige
Bibliothekslösung übernehmen; folgende Starts erhalten frisch initialisierte
Populationen und übernehmen keine Gewinner oder Zufallszustände vorheriger Starts.
Die unveränderten Bibliotheksbausteine bleiben in allen Starts verfügbar.
Das laufübergreifend beste Genom und sein monotoner Verbesserungsverlauf bleiben
separat erhalten. Manuelle Suchen enden beim ersten fehlerfreien Treffer; der
Python-Optimierungsmodus kann alle Starts ausschöpfen. Sein Zeitbudget gilt für
den gesamten Auftrag. Abbruch verwirft weiterhin den gesamten Auftrag.

`islands` (1–16, Standard 1) teilt die gesamte Elternpopulation möglichst gleich
auf; Restplätze gehen an die ersten Inseln. Jede Insel benötigt mindestens zwei
Eltern. Nachkommen werden reihum erzeugt, beide Eltern und das zu ersetzende
schlechteste Mitglied stammen dabei ausschliesslich von derselben Insel.
Nach jeweils `migration_interval` lokalen Generationen (1–20000, Standard 10)
wandert ein Elitegenom von Insel i nach `(i+1) mod islands`. Alle Quellgenome
werden vor dem Austausch kopiert. Ein Migrant ersetzt nur ein mindestens gleich
schlechtes Zielmitglied; zusätzliche Fitnessbewertungen entstehen nicht.
Die Inseln werden innerhalb des jeweiligen Backends nacheinander bearbeitet.

`runs` speichert pro tatsächlich ausgeführtem Start Seed, Bewertungen, besten Rang,
Inselgrössen, kumulative Generation und Anzahl übernommener Migranten.
`restarts_completed` zählt auch einen durch Treffer oder Zeitlimit verkürzten Start.
`diversity_history` enthält je Start die Anfangs- und Endpopulation, global und
pro Insel. `parent_population` nennt die tatsächlich gefüllte Grösse der letzten
Population. `diversity` bezeichnet die letzte Endpopulation, nicht den besten
Start. `unique_fraction` ist der Anteil verschiedener vollständiger Genome;
`mean_hamming` die mittlere Zahl unterschiedlicher Gene über alle ungeordneten
Genompaare, geteilt durch die Genomlänge. Bei weniger als zwei Genomen gilt 0.
Auch inaktive Gene zählen: Die Kennzahlen messen genotypische Vielfalt und
behaupten weder unterschiedliche Funktionen noch bessere Fitness.
Die Berechnung nutzt Genhäufigkeiten je Position und benötigt keine zusätzlichen
Fitnessbewertungen. Metadaten sind auf zwei Schnappschüsse je Start begrenzt.

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

Mehrschrittige Programmreferenzen werden im selben begrenzten manuellen
Auftragskanal erzeugt und sind über dessen Abbruch-API stoppbar. Die
Hintergrundsuche pausiert während der Erzeugung. Ein geprüfter AST wird in eine
kleine interne Anweisungsliste übersetzt, ohne Host-Code auszuführen. Jede
Eingabe erhält neue lokale Variablen und Schleifeniteratoren. Anweisungs- und
Iterationsbudgets je Eingabe sowie ein gemeinsames Gesamtbudget begrenzen die
Vektorerzeugung. Erst ein fertiger Datensatz wird gespeichert. Programmquelle,
Sprachversion, Budgets und Portsemantik sind im Datensatz enthalten; die
Evolution selbst erhält unverändert kombinatorische Bitvektoren.
[PROGRAMME.md](PROGRAMME.md) legt Grammatik, Semantik und Schnittstellen fest.

Labels und bedingte/unbedingte Sprünge werden vor dem Lauf in dieselbe
Anweisungsliste aufgelöst. Die Prüfung verhindert Sprünge in fremde oder tiefere
Blöcke. Ein Generator hält vor jeder internen Anweisung; direkte Ausführung
verbraucht ihn vollständig, Debugsitzungen halten ihn samt lokalen Variablen,
Iteratoren und Budget im Speicher. Die Debug-API führt maximal 100 Anweisungen
je Fortsetzen-Aufruf aus. Stoppen hält den Zustand an, Reset erzeugt ihn neu.
Höchstens 32 flüchtige Sitzungen verhindern unbegrenzte Ansammlung verlassener
Browserläufe. Debuggen speichert keine Vektoren und verändert keine NAND-Schaltung.

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


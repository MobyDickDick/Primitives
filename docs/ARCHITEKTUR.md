# Architektur und Entwurfsentscheidungen

## Sprachwahl

TinyLanguage ist als echte Suchsprache eingebunden: `tiny/evolve.tiny` steuert
Erzeugungsschritte, Mutation, Rekombination, Auswahl und Abbruch.
Die vorhandene Python-Implementierung von TinyLanguage macht einen kleinen
Python-Host sinnvoll. Go ist in dieser Umgebung nicht installiert; mit dem
verwendbaren TinyLanguage-Interpreter war ein Wechsel zu Go nicht nötig.

Die FFI erlaubt ausschliesslich `configure`, `specimen`, `score`, `trace`,
`finish`, `begin_restart`, `initial`, `observe`, `population_buffer`, `record`
und `migration` aus
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
| `primitives/templates.py` | Abstrakte Templates, Bedingungen und Konkretisierung mit symbolischen Ports |
| `tools/export_programs.py` | Reproduzierbare vollständige Programmbeispiele samt Quellen |
| `primitives/evolution.py` | Genom, Fitness, Bibliothekskomposition, Python-Backend |
| `primitives/ancestry.py` | Kandidatenidentitäten, Vorfahren, Quellenschnappschüsse und Nachbearbeitung |
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

### Neutrale Evolution mit getrennter Vereinfachung

`neutral` (bool, Standard `false`) wählt in beiden Backends das Suchziel
`errors_only`. Die Rangzahl ist dann ausschliesslich `Fehler*(G+1)^2`; die
Skalierung erhält die bestehenden Fehlerfreiheits- und Verlaufsberechnungen.
Gatterzahl und Tiefe beeinflussen weder Turniere, Ersatzentscheidungen, Migration
noch die Sicherung des besten Genoms. Gleiche Fehlerzahlen erlauben somit auch
grössere und tiefere Nachkommen. Das separat gesicherte Genom wird nur bei weniger
Fehlern ersetzt, bei Gleichstand bleibt der erste Treffer erhalten. Die laufende
Population darf auf diesem Plateau driften. Ohne `neutral` gilt unverändert die
gemeinsame Rangzahl aus Fehlern, aktiven Gattern und Tiefe.

Nach Abschluss aller tatsächlich ausgeführten Starts führt `Problem.result`
genau einmal die getrennte Vereinfachungsphase aus. Damit verwenden Python und
die TinyLanguage-FFI dieselben Regeln, auch bei einem Treffer in der Initialisierung,
ausgeschöpftem Kandidatenbudget oder einem Python-Zeitlimit. `Circuit.simplify`
verarbeitet die Gatter topologisch, kanonisiert die beiden NAND-Eingänge und
teilt gleiche Eingangs-Paare. `NAND(NAND(x,x), NAND(x,x)) = x` überbrückt doppelte
Negationen; anschliessende Kompaktierung entfernt unerreichbare Gatter. Direkte
Ausgänge und gemeinsam verwendete Zwischenergebnisse bleiben erhalten. Gatterzahl
und Tiefe nehmen dabei nicht zu. Der Durchlauf ist durch die Schaltungsgrösse
begrenzt, benötigt keine Fitnessbewertungen und prüft Abbruch vor, während und
nach dem Umschreiben. Die abgeschlossene Suche wird bei Abbruch nicht gespeichert.

Die Identitäten erhalten die vollständige Boolesche Funktion, ohne Sollvektoren
als Äquivalenzbeweis zu verwenden. Der Bezug zur Referenz bleibt trotzdem nur so
stark wie der ursprüngliche Datensatz: Eine passende Stichprobe bleibt eine
Stichprobe, und eine Annäherung behält ihre Fehler. Das Verfahren garantiert keine
globale Minimalität; weitere NAND-Identitäten und SAT-Prüfung bleiben mögliche
Erweiterungen. Der bestehende Python-Modus `optimize` kann auch in Kombination mit
`neutral` bei null Fehlern weitersuchen; Strukturkosten bleiben dann weiterhin
der anschliessenden Vereinfachung vorbehalten.

`search.objective` unterscheidet `errors_only` von `errors_gates_depth`.
`search.phases` ist ohne neutralen Modus leer und enthält sonst in dieser
Reihenfolge `neutral_evolution` und `simplification`. Gespeichert werden Fehler,
Gatter, Tiefe, Bewertungen sowie vorherige Struktur und entfernte Gatter der
Vereinfachung (`method: nand-identities-v1`). `search.history`, `runs.best_score`
und die Diversität beziehen sich ausschliesslich auf die Evolutionsphase;
Vereinfachung verbraucht null Bewertungen. Eine optionale Restfallkorrektur in
`runner.search` folgt erst danach. Die normale Bibliotheksentscheidung vergleicht
weiter Fehler, Gatter und Tiefe und kann die bisherige Version beibehalten.

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
`search.seed_blocks` nennt verfügbare Quellen. Die tatsächlich verwendeten Quellen
und Elternbeziehungen werden gesondert in `search.ancestry` belegt.
Die Paket-, Port- und Versionssemantik ist in [BAUSTEINE.md](BAUSTEINE.md) beschrieben.

### Tatsächliche Kandidatenabstammung

Jede Bewertung erhält als Kandidatenkennung ihre laufweite Bewertungsnummer
(ab 1). Die Populationen und das separat gesicherte beste Genom führen diese
Kennung mit. Identische Genome bleiben verschiedene Individuen; eine Migration
kopiert dagegen dieselbe Identität mit dem Genom und Rang. Beide Backends
sichern vor einer Ringmigration auch die Quellkennungen aller Inseln, damit
Genom und Herkunft selbst bei unmittelbar überschriebenen Quellplätzen zusammenpassen.

Der Host erfasst nach der Bewertung und vor einem möglichen Elternersatz den
konkreten Erzeugungsschritt. Für neue Zufalls-/Bibliothekskandidaten werden das
vollständige Genom und die tatsächliche Herkunft gesichert. Bibliothekskompositionen
enthalten pro eingesetzter Quelle Eingangsverdrahtung und Gatteroffset sowie einen
kompaktierten NAND-Schnappschuss der Quelle, mit Programm- oder Bausteinkennung.
Die bisherige Lösung ist eine explizite externe Ausgangsquelle, auch wenn sie nur
eine Annäherung ist. Unpassende oder bloss angebotene Quellen werden nicht als
Vorfahren behauptet. Bei TinyLanguage wird der vor einer Variation erzeugte, dann
überschriebene Bibliothekskandidat ausdrücklich nicht als Herkunft aufgezeichnet.

Nachkommen referenzieren den ersten Elternkandidaten und bei aktivierter
Rekombination den zweiten gewählten Elternkandidaten. Genpositionen protokollieren
die tatsächlich ausgeführten Übernahmen und Mutationsziehungen, auch wirkungslose
oder später durch Mutation überschriebene Übernahmen. Die endgültigen Unterschiede
zum ersten Elternteil stehen als dünn besetzte Änderungsliste daneben. Damit lässt
sich jedes Vorfahrengenom exakt rekonstruieren, einschliesslich inaktiver Gene.
Start, kumulative Generation, Geburtsinsel und tatsächlicher Bewertungsrang gehören
zu jedem Knoten. Übernommene Migranten werden als Ortswechsel mit unveränderter
Kennung protokolliert; neue Starts verknüpfen keine Eltern aus vorherigen Starts.

Während des Laufs ist das Protokoll durch das vorhandene Kandidatenbudget begrenzt.
Beim Abschluss wird der Vorfahrengraph des besten Suchkandidaten iterativ verfolgt;
nur seine erreichbaren Knoten, verwendeten Quellen und diese Kandidaten betreffenden
Migrationsereignisse gehen ins Ergebnis. Ein Ereignis kann auch nach der Geburt
des besten Kandidaten liegen. Andere Suchversuche werden nicht dauerhaft archiviert.
Die Erfassung verbraucht weder Zufallsziehungen noch weitere Fitnessbewertungen;
sie benötigt zusätzlichen Speicher und Rechenzeit. Zeitbegrenzte Läufe können
dadurch weniger Kandidaten bewerten. Abbruch verwirft weiterhin den Auftrag.

`search.ancestry.transformations` trennt die Genetik von der Nachbearbeitung:
Kompaktierung, optionale Vereinfachung, eine gegebenenfalls bessere bisherige
Lösung als Basis der Restfallkorrektur und die Korrektur selbst enthalten jeweils
die konkrete resultierende Schaltung. Der letzte Schnappschuss stimmt mit `circuit`
überein. Ein abgelehnter Bibliotheksretest liefert den früheren Gewinner samt dessen
unveränderter Abstammung zurück. Alte Einträge ohne Protokoll bleiben lesbar.
Die Aufzeichnung endet an externen Quellversionen; sie behauptet weder eine
laufübergreifend vollständige Genealogie noch erhaltene Bausteininstanzen oder
einen funktionalen Beitrag jedes geerbten Gens.

Die Oberfläche zeigt höchstens 100 Knoten; Bibliothek, API, CLI und JSON-Export
erhalten den gesamten erreichbaren Graphen. Das genaue Schema und die
Rekonstruktion stehen in [FORMAT.md](FORMAT.md#kandidatenabstammung).

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


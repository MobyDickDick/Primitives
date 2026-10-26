# Aufgabenliste

## Rekursive Multiplikation vom 26. Oktober 2026

- [x] `MUL<w>` aus vier vollständigen rekursiven Teilprodukten mit ADD/INC.
- [x] Fehlerdarstellung `[0,1]` ab `a*b >= 2**w`, Ein-Bit-Basis AND.
- [x] Instanzen für w=1,2,4 als verschachtelte F-Boxen und flache NAND-Netze.
- [x] Vollständiger Vergleich aller Eingaben mit unabhängiger Multiplikation.
- [x] Einmalige Bibliotheksmigration mit Template, Funktionen und Bausteinen.

## Bibliotheksbaum und Bit-Templates vom 26. Oktober 2026

- [x] Gemeinsamer Verzeichnisbaum für Templates und Funktionen mit Suche.
- [x] Ordner und Unterordner anlegen, beschreiben, umbenennen und verschieben.
- [x] Persistente Zuordnungen bei stabilen Funktions- und Template-Kennungen.
- [x] Vier konventionelle Bit-Templates samt vollständig geprüften 4-Bit-NAND-Beispielen.
- [x] Direkte strukturelle NAND-Übersetzung der festen Bit-Teilmenge mit Budgets und Gattergrenze.
- [x] Browserprüfung, 194 Python- und 29 JavaScript-Tests erfolgreich.

## Templates und Ergebnisbearbeitung vom 26. Oktober 2026

- [x] Abstrakte Templates separat speichern, exportieren und importieren.
- [x] Konkrete Instanzen mit Parameterwerten, symbolischen Breiten und `add<8>(a,b)`.
- [x] Bedingungen wie `is_power_of_two(n)` und Aufrufbedingungen mit `assert`.
- [x] Rekursive Funktionen, gemeinsame Budgets, Beispiel, CLI/API und Tests.
- [x] NAND-Gatterliste editieren, prüfen, anzeigen und als JSON/Baustein sichern.
- [x] [Editor und Logisim-Anbindung bewerten](docs/EDITIEREN-LOGISIM.md).
- [ ] `.circ`-Export mit Pins und NANDs implementieren und in Logisim praktisch prüfen.
- [ ] Rückimport des eigenen Exportprofils und funktionalen Roundtrip prüfen.
- [ ] Direkte Anschlussbearbeitung im Diagramm mit Undo/Redo ergänzen.

## Erweiterungs-Issues vom 25. Oktober 2026

Ausgearbeitete lokale Planungs-Issues mit Umfang, Abnahmekriterien und
Abhängigkeiten stehen in [docs/ERWEITERUNGEN.md](docs/ERWEITERUNGEN.md).
Die Kennungen sind Dokumentationskennungen; GitHub-Issues wurden noch nicht angelegt.

- [x] [PRIM-01: Zoom und Navigation](docs/ERWEITERUNGEN.md#prim-01).
- [x] [PRIM-02: Verbindungsdrähte verschieben und speichern](docs/ERWEITERUNGEN.md#prim-02).
- [x] [PRIM-03: Variable Operand- und Ausgangsbitbreiten](docs/ERWEITERUNGEN.md#prim-03).
- [x] [PRIM-04: TinyCPU-Operationen und gängige Beispiele](docs/ERWEITERUNGEN.md#prim-04).
- [x] [PRIM-05: Wiederverwendbare Unterprogramm-Bausteine](docs/ERWEITERUNGEN.md#prim-05).
- [x] [PRIM-06: Unterprogramm-Boxen und interaktives Debugging](docs/ERWEITERUNGEN.md#prim-06).
- [x] [PRIM-07: Mehrschrittige Programme mit if/else, while und for](docs/ERWEITERUNGEN.md#prim-07).
- [x] [PRIM-08: Labels, Sprungbefehle und Ablaufdebugger](docs/ERWEITERUNGEN.md#prim-08).

## Etappe 1 – lauffähige Spielwiese

- [x] Projekt starten und TinyLanguage-Eignung praktisch prüfen.
- [x] NAND-Programme als azyklische Gatterlisten darstellen und validieren.
- [x] Klammernotation für N:1 einlesen und ausgeben.
- [x] Gemeinsame Zwischenergebnisse und mehrere Ausgänge erlauben.
- [x] N+M-Vektoren validieren; Widersprüche ablehnen, Duplikate bereinigen.
- [x] Logische und kleine mathematische Vorlagen anbieten.
- [x] Datensätze aus Ausdrücken und eigenen Python-Oracles erzeugen.
- [x] Evolution mit Seed, Budget, Mutation, Rekombination und Selektion.
- [x] Vorhandene Programme als neu verdrahtbare Bausteine einsetzen.
- [x] Programme mit Namen, Datensatz, Fitness und Suchverlauf speichern.
- [x] Prüfstatus vollständig / Stichprobe / Annäherung unterscheiden.
- [x] Lokale Oberfläche mit Vektorimport, Bibliothek und Signalvisualisierung.
- [x] Automatische Kern- und HTTP-Integrationstests ergänzen.
- [x] Einstieg, Formate, Grenzen und Architektur dokumentieren.

## Etappe 2 – Suche robuster und aussagekräftiger machen

- [x] Elternpopulation mit Turnierselektion statt zwei laufender Eltern
      (Python und TinyLanguage; Initialisierung im Kandidatenbudget, bestes Ergebnis erhalten).
- [x] Mehrere unabhängige Neustarts, Inselpopulationen und Diversitätsmass
      (Python und TinyLanguage; gemeinsames Kandidatenbudget, Ringmigration,
      genotypische Vielfalt pro Start/Insel, CLI/API und Oberfläche).
- [x] Neutrale Evolution und anschliessende Vereinfachung als getrennte Phasen
      (Python und TinyLanguage; Fehlerzahl ohne Strukturkosten, danach
      funktionserhaltende NAND-Vereinfachung, CLI/API, Oberfläche und Phasenprotokoll).
- [x] Explizite Makroknoten mit benannten Ports und festen Abhängigkeitsversionen (PRIM-05;
      bei der Evolution bewusst in mutierbare NAND-Gatter expandiert).
- [x] Tatsächliche Abstammung einzelner Kandidaten speichern (Python und TinyLanguage;
      Kandidatenkennungen, Eltern, Genänderungen, konkrete Quellen und Inselwechsel;
      vollständige Vorfahren des Suchgewinners in Bibliothek und JSON-Export).
- [ ] Trainings- und Prüfvektoren getrennt behandeln, Gegenbeispiele nachführen.
- [ ] Numerische Fehlerfunktion und Gewichtung hoher Bits für Mathematik.
- [ ] Fehlerfreie Programme nach dem ersten Treffer weiter optimieren.
- [ ] SAT-/Äquivalenzprüfung für grosse Funktionen; optimale Lösungen nur mit Nachweis kennzeichnen.
- [ ] Fortschritt live anzeigen, Suchen pausieren/abbrechen und wiederaufnehmen.
- [ ] Gespeicherte Datensätze direkt auswählen; Programme importieren und verwalten.
- [ ] CLI für getrennte Prüfung eines Programms gegen neue Vektoren.

## Etappe 3 – Rechnen mit klarer Zahlensemantik

- [ ] Parametrisierte Vorlagen statt fester Beispielbreiten.
- [ ] Vorzeichen, Zweierkomplement, Festkomma, Rundung und Überlauf auswählbar.
- [ ] Addierer, Subtrahierer und Multiplizierer systematisch aus kleinen Bausteinen entwickeln.
- [ ] Grössere Division, Wurzeln und trigonometrische Approximationen untersuchen.
- [ ] Für Cosinus zwischen affiner und vorzeichenbehafteter Kodierung wählen.
- [ ] Prüfdatenfehler als Kurve über dem Zahlenbereich visualisieren.
- [ ] Codeexport nach TinyLanguage, Go, Python, JavaScript und gegebenenfalls Verilog.
- [ ] Reale Ausführung messen; Gatterzahl, Tiefe und gemessene Laufzeit getrennt optimieren.

## Etappe 4 – Zustand und Rückkopplung

- [ ] Modell aus kombinatorischer Schaltung plus Zustandsregistern ergänzen.
- [ ] Startzustand und Rückschreibziele explizit festlegen.
- [ ] Modus „vor jedem Takt löschen, dann rückschreiben“ präzisieren.
- [ ] Modus „gewählte Eingangsbits überschreiben“ implementieren.
- [ ] Alle Rückschreibungen gleichzeitig am Taktende anwenden.
- [ ] Zeitfolgen statt einzelner Vektoren als Trainingsdatensätze einführen.
- [ ] Zustandsübergänge visualisieren und mit Zähler / Toggle-Register testen.
- [ ] Evolution auf zeitabhängige Aufgaben erweitern.

Die acht Erweiterungspakete PRIM-01 bis PRIM-08 sind umgesetzt.
Nächster offener Entwicklungspunkt: Trainings- und Prüfvektoren getrennt behandeln
und Gegenbeispiele nachführen (Etappe 2).
Für die Suchentwicklung bleiben Suchrobustheit und unabhängige Prüfvektoren
vor einer starken Erhöhung der Zahlbreiten empfohlen.


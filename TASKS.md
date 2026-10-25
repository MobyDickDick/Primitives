# Aufgabenliste

## Erweiterungs-Issues vom 25. Oktober 2026

Ausgearbeitete lokale Planungs-Issues mit Umfang, Abnahmekriterien und
Abhängigkeiten stehen in [docs/ERWEITERUNGEN.md](docs/ERWEITERUNGEN.md).
Die Kennungen sind Dokumentationskennungen; GitHub-Issues wurden noch nicht angelegt.

- [x] [PRIM-01: Zoom und Navigation](docs/ERWEITERUNGEN.md#prim-01).
- [x] [PRIM-02: Verbindungsdrähte verschieben und speichern](docs/ERWEITERUNGEN.md#prim-02).
- [x] [PRIM-03: Variable Operand- und Ausgangsbitbreiten](docs/ERWEITERUNGEN.md#prim-03).
- [ ] [PRIM-04: TinyCPU-Operationen und gängige Beispiele](docs/ERWEITERUNGEN.md#prim-04).
- [ ] [PRIM-05: Wiederverwendbare Unterprogramm-Bausteine](docs/ERWEITERUNGEN.md#prim-05).
- [ ] [PRIM-06: Unterprogramm-Boxen und interaktives Debugging](docs/ERWEITERUNGEN.md#prim-06).
- [ ] [PRIM-07: Mehrschrittige Programme mit if/else, while und for](docs/ERWEITERUNGEN.md#prim-07).
- [ ] [PRIM-08: Labels, Sprungbefehle und Ablaufdebugger](docs/ERWEITERUNGEN.md#prim-08).

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

- [ ] Elternpopulation mit Turnierselektion statt zwei laufender Eltern.
- [ ] Mehrere unabhängige Neustarts, Inselpopulationen und Diversitätsmass.
- [ ] Neutrale Evolution und anschliessende Vereinfachung als getrennte Phasen.
- [ ] Explizite Makroknoten mit benannten Parametern und Abhängigkeitsversionen.
- [ ] Tatsächliche Abstammung einzelner Kandidaten speichern; aktuell nur Liste
      verfügbarer Bibliotheksquellen je Lauf, kein genealogischer Nachweis.
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

Empfohlene nächste Aufgabe: Suchrobustheit und unabhängige Prüfvektoren verbessern,
bevor die Zahlbreiten stark erhöht werden.


# Erweiterungs-Issues

Diese acht Arbeitspakete konkretisieren die Erweiterungswünsche vom
25. Oktober 2026. Sie sind lokale Planungs-Issues; auf GitHub wurden noch keine
Issues angelegt. PRIM-01 und PRIM-02 sind umgesetzt; die weiteren Arbeitspakete sind offen.

Die Kennungen PRIM-01 bis PRIM-08 sind Dokumentationskennungen, keine GitHub-Issue-Nummern.

## Übersicht

| Kennung | Thema | Wunsch | Abhängigkeiten |
|---|---|---|---|
| [PRIM-01](#prim-01) | Zoom und Navigation (umgesetzt) | 1 | Eigenständig |
| [PRIM-02](#prim-02) | Drähte verschieben und speichern (umgesetzt) | 2 | Zoom-Koordinaten aus PRIM-01 berücksichtigen |
| [PRIM-03](#prim-03) | Variable Bitbreiten | 5 | Grundlage für weitere Funktionen |
| [PRIM-04](#prim-04) | TinyCPU und Operationsbeispiele | 3 | PRIM-03; Kontrollfluss später ergänzen |
| [PRIM-05](#prim-05) | Wiederverwendbare Unterprogramm-Bausteine | 4 | PRIM-03 |
| [PRIM-06](#prim-06) | Unterprogramm-Boxen und Debugging | 4 | PRIM-05; PRIM-01/02 berücksichtigen |
| [PRIM-07](#prim-07) | Mehrschrittige Programme und Kontrollstrukturen | 6 | PRIM-03 |
| [PRIM-08](#prim-08) | Sprungbefehle und Ablaufdebugger | 6 | PRIM-07 |

Empfohlene Reihenfolge: PRIM-01 → PRIM-02 für die Bedienung; danach PRIM-03 als
Grundlage. Anschliessend können Operationsbeispiele (PRIM-04), Bausteine
(PRIM-05 → PRIM-06) und Programmausführung (PRIM-07 → PRIM-08) getrennt wachsen.
Eine Operationsvorlage darf bereits nutzbar sein, bevor eine passende verdrahtete
Schaltung existiert.

Die Ausgangslage wurde anhand der vorhandenen Implementierung und der verlinkten
TinyCPU-Quellen geprüft. Der konkrete TinyCPU-Commit ist bei der späteren
Übernahme festzuhalten.

<a id="prim-01"></a>

## PRIM-01 – Verdrahtungsschema: Zoom und Navigation ergänzen

**Status:** umgesetzt am 25. Oktober 2026.

### Ziel
Grosse Schaltungen im interaktiven SVG-Schaltbild bequem vergrössern, verkleinern und überblicken.

### Umfang
- Zoom über sichtbare Plus/Minus-Schaltflächen und eine dokumentierte Maus-/Touchpad-Geste; Prozentanzeige.
- „Alles einpassen“ und „100 %“; Verschieben des sichtbaren Ausschnitts, wenn die Schaltung nicht vollständig sichtbar ist.
- Zoom um den Mauszeiger bzw. einen stabilen Mittelpunkt; sinnvolle minimale/maximale Vergrösserung.
- Bildschirmkoordinaten korrekt in Schaltbildkoordinaten umrechnen, damit Boxen bei jeder Zoomstufe präzise gezogen und Eingänge angeklickt werden können.
- Ansicht bei Signaländerung und Simulationsschritten erhalten. Kameraposition und Zoom getrennt von den eigentlichen Boxpositionen behandeln.
- Tastaturbedienung und normale Seitennavigation berücksichtigen.

### Abnahme
- [x] Kleine und grosse Schaltungen lassen sich zoomen, verschieben und vollständig einpassen.
- [x] Boxen ziehen, Eingänge umschalten und Boxauswahl funktionieren bei mehreren Zoomstufen ohne Versatz.
- [x] Zoom verändert weder Schaltungsfunktion noch gespeicherte Boxpositionen.
- [x] Signaländerungen setzen die Ansicht nicht zurück.

### Ansatzpunkte
`web/viewport.js` kapselt Zoom, Einpassen und Verschieben als unabhängige Kamerageometrie.
`web/app.js` bindet diese an SVG-`viewBox`, Pointer-, Rad- und Tastaturereignisse an.
`web/index.html` und `web/style.css` ergänzen Bedienelemente und eine feste,
responsive Zeichenfläche. Boxpositionen und Layout-API bleiben vom Kamerazustand getrennt.

Geprüft mit sieben JavaScript-Tests (Routing/Kamerageometrie), sechs HTTP-Integrationstests
und einer Browser-Bedienprüfung. Details stehen in [VERIFIKATION.md](VERIFIKATION.md#zoom-und-navigation-prim-01).

Eigenständige erste Aufgabe; die spätere manuelle Leitungsführung soll dieselbe Koordinatenumrechnung nutzen.

<a id="prim-02"></a>

## PRIM-02 – Verdrahtungsschema: Verbindungsdrähte mit der Maus verschieben und speichern

**Status:** umgesetzt am 25. Oktober 2026.

### Ziel
Neben Boxen sollen auch die Verbindungsdrähte im Schaltbild von Hand verschoben werden können, um Kreuzungen und unübersichtliche Leitungswege zu verbessern.

### Umfang
- Leitungen mit ausreichend grosser unsichtbarer Trefferfläche auswählbar machen.
- Orthogonale Leitungssegmente ziehen bzw. Stützpunkte anlegen und verschieben; Endpunkte bleiben an ihren jeweiligen Anschlüssen.
- Dies ist eine Änderung der Leitungsführung: Die logische Verbindung zwischen Quelle und Ziel bleibt erhalten.
- Verbindungen eindeutig über Quelle, Ziel und Zieleingang identifizieren, auch wenn beide NAND-Eingänge dieselbe Quelle haben.
- Manuelle Wege beim Verschieben von Boxen sinnvoll anpassen; Verhalten bei Hindernissen und ungültigen Wegen sichtbar und nachvollziehbar festlegen.
- Manuelle Leitungswege zusammen mit dem Layout pro Schaltung speichern/laden. Alte Layouts mit ausschliesslich Boxpositionen bleiben lesbar.
- Rücksetzen einer Leitung und „Automatisch anordnen“ mit klarer Wirkung auf manuelle Wege.

### Abnahme
- [x] Leitung bzw. Segment kann unabhängig von Boxen bewegt werden, auch im gezoomten Schaltbild.
- [x] Anschlüsse, Ausgangswerte und Schaltungsidentität bleiben unverändert.
- [x] Manuelle Wege überstehen Signalwechsel, Simulationsschritte, erneutes Öffnen und Serverneustart nach „Layout speichern“.
- [x] Mehrfachverbindungen und verschobene Boxen werden korrekt behandelt.

### Umsetzung und Verhalten
Orthogonale Segmente sind über eine 14 Bildschirmpixel breite Trefferfläche
mit Maus/Touch und per Tab/Pfeiltasten bearbeitbar. Gerade Leitungen erhalten
beim Ziehen Knicke; die kurzen Anschlussstücke bleiben fest. Die Kennung
`Quelle:Ziel:logischer Eingang` bleibt beim visuellen Tauschen der NAND-Ports stabil.
Die logische Schaltung bleibt vom Layout getrennt.

Beim Boxverschieben bleiben innere Stützpunkte fest; die Enden werden neu
angeschlossen. Wege durch Boxen werden beim manuellen Ziehen abgelehnt.
Blockierte gespeicherte Wege werden orange gestrichelt automatisch umgangen;
ihre manuellen Stützpunkte bleiben bis zur Freigabe oder Rücksetzung erhalten.
„Leitung zurücksetzen“ bzw. Entf entfernt einen manuellen Weg, „Automatisch
anordnen“ entfernt alle manuellen Wege und ordnet die Boxen neu an.

Das Layoutformat mit `schema: 2` enthält `positions` und eine `wires`-Zuordnung
von Leitungskennungen zu orthogonalen Punktlisten. Alte Layouts ohne `wires`
werden weiterhin geladen. Die API prüft Leitungskennungen, Koordinaten,
Orthogonalität und das Limit von 128 Punkten pro Leitung vor dem Speichern.
Prüfergebnisse stehen in [VERIFIKATION.md](VERIFIKATION.md#manuelle-leitungswege-prim-02).

### Ansatzpunkte
`web/graph.js`: Routing; `web/app.js`: SVG-Pfade/Pointer; `primitives/library.py` und `primitives/server.py`: Layoutformat/API.

### Abhängigkeiten
Die Zoom-Koordinatenumrechnung aus [PRIM-01](#prim-01) wiederverwenden; Routing und Persistenz sind davon weitgehend unabhängig.

<a id="prim-03"></a>

## PRIM-03 – Operationen parametrisieren: variable Operand- und Ausgangsbitbreiten

**Status:** geplant, nicht implementiert.

### Ziel
Operationen wie ADD und MUL als Familien mit unterschiedlichen Bitbreiten anbieten. Eine Variante darf bereits als ausführbare Referenz/Vektorvorlage existieren, auch wenn noch keine passende verdrahtete Schaltung gefunden wurde.

### Ausgangslage
N und M sind bereits einstellbar, aber `a` und `b` werden in `primitives/dataset.py` automatisch aus zwei Hälften der Eingabe gebildet. Die Vorlagen haben feste Breiten. Unterschiedlich breite Operanden und zusätzliche Ein-/Ausgänge sind damit nicht ausdrücklich modelliert.

### Umfang
- Benannte Operanden mit eigener Breite und eindeutiger Bitzuordnung; benannte Ergebnisse mit eigener Breite. Bestehende LSB-first-Formate kompatibel halten.
- Parameter z. B. `ADD(a_bits=2,b_bits=3,result_bits=4)`, `ADD(4,4,4)`, `ADD(4,4,5)` sowie `MUL(2,2,4)`.
- Vorzeichen/unsigned und Zweierkomplement sowie Überlauf, Abschneiden, Carry/Borrow und Ergebnisbreite ausdrücklich definieren; keine stillschweigende Semantikänderung bestehender Vorlagen.
- Parametrisierte Operation über Oberfläche und API/CLI auswählen, validieren und samt Metadaten exportieren/importieren.
- Operationsdefinition, konkrete Breitenvariante und vorhandene NAND-Implementierung getrennt darstellen.
- Grössenlimits, vollständige Wahrheitstabellen und Stichproben beibehalten und sichtbar unterscheiden; kombinatorisches Wachstum nicht durch automatisches Erzeugen aller Varianten verschärfen.

### Abnahme
- [ ] ADD mit gleichen und unterschiedlichen Operandbreiten liefert definierte Ergebnisse, auch bei Überlauf.
- [ ] Eine Vorlage funktioniert ohne bereits vorhandene Schaltung und kann zur Suche verwendet werden.
- [ ] Breiten/Bitreihenfolge bleiben beim Speichern und Laden erhalten; bestehende Beispiele funktionieren weiter.

### Ansatzpunkte
`primitives/dataset.py`, Bibliotheksmetadaten, Katalog-API und Vorlagenauswahl. Grundlage für TinyCPU-Beispiele und Unterprogramm-Schnittstellen.

<a id="prim-04"></a>

## PRIM-04 – TinyCPU-Operationen und gängige Rechenoperationen als Beispiele übernehmen

**Status:** geplant, nicht implementiert.

### Ziel
So viele sinnvolle Operationen wie möglich aus [TinyCPU](https://github.com/MobyDickDick/TinyCPU) als wiederverwendbare Beispiele in Primitives anbieten. Nicht direkt darstellbare CPU-Befehle werden nachvollziehbar erfasst und den nötigen Folgearbeiten zugeordnet.

### Umfang
- Befehlsinventar anhand des [Maschinenformats](https://github.com/MobyDickDick/TinyCPU/blob/main/hardware/logisim/tinycpu-machine-v1.json) und des [Referenzinterpreters](https://github.com/MobyDickDick/TinyCPU/blob/main/src/tiny_cpu_vm.py) erstellen. Für jeden Befehl festhalten: direkt kombinatorisch umsetzbar, als Teiloperation umsetzbar, benötigt Zustand/Programmausführung oder vorerst zurückgestellt mit Begründung. Optionale Profile gesondert kennzeichnen.
- Priorität: ADD, SUB, MUL, DIV, AND, OR, XOR, NOT sowie ergänzend IsZero, IsNonZero, IsNegative, Gleichheit und Grössenvergleiche, ShiftLeft(n), ShiftRight(n), Inkrement/Dekrement und Auswahl/Multiplexer.
- IsZero und Schiebeoperationen als zusätzliche gewünschte Beispiele behandeln; nicht voraussetzen, dass sie eigene Opcodes im TinyCPU-Maschinenformat sind.
- Schiebeweite als Parameter und, wo sinnvoll, als Eingang anbieten. Logisches und arithmetisches Rechtsschieben unterscheiden; Schiebeweiten 0, Bitbreite und darüber ausdrücklich definieren.
- Für jede Operation eine ausführbare Referenz, kleine verständliche Standardvariante, parametrisierbare Breiten und importierbare Vektoren anbieten. Bereits vorhandene Vorlagen erweitern und Doppelungen vermeiden.
- TinyCPU arbeitet im Referenzmodell mit vorzeichenbehafteten Werten. Überlauf, Division durch null, negative Division und Gültigkeits-/Fehlerausgänge ausdrücklich abbilden oder Abweichungen dokumentieren. Python-`//` und TinyCPU-Division runden bei negativen Werten unterschiedlich.
- Adressierungsarten nicht mit neuen Rechenoperationen gleichsetzen. Speicher, Register, Sprünge, I/O und Halt benötigen zusätzliche Semantik; bei Bedarf kombinatorische Teilfunktionen extrahieren.
- Korrekte Referenz/Vektoren und tatsächlich gefundene NAND-Schaltung getrennt ausweisen; nicht für jede Breite eine fertige Verdrahtung voraussetzen.

### Abnahme
- [ ] Für jeden inventarisierten TinyCPU-Befehl ist der Übernahmestatus begründet dokumentiert.
- [ ] IsZero, beide Schieberichtungen und die priorisierten Rechen-/Logikoperationen sind als Beispiele auswählbar.
- [ ] Kleine Breiten werden vollständig, grössere Varianten mit klar gekennzeichneten Stichproben und Randfällen geprüft.
- [ ] Referenzwerte und vorhandene Schaltungen stimmen auf den ausgewiesenen Prüfvektoren überein.
- [ ] Herkunft, geprüfter TinyCPU-Stand und Semantikabweichungen sind dokumentiert.

### Abhängigkeiten
[PRIM-03](#prim-03); Kontrollfluss wird durch [PRIM-07](#prim-07) und [PRIM-08](#prim-08) ergänzt. Zustandsbehaftete CPU-Komponenten bleiben an das Registermodell aus der bestehenden Architekturplanung gebunden.

### Ansatzpunkte
`primitives/dataset.py`, `tools/seed_library.py`, `examples/`, Vorlagenkatalog und Dokumentation.

<a id="prim-05"></a>

## PRIM-05 – Unterprogramme als wiederverwendbare Bausteine mit definierten Ein-/Ausgängen modellieren

**Status:** geplant, nicht implementiert.

### Ziel
Gespeicherte Schaltungen und geeignete Unterprogramme als benannte Bausteine mit beliebig vielen unterstützten Eingangs- und Ausgangsports in grössere Schaltungen einsetzen.

### Ausgangslage
Die Evolution kann Bibliotheksschaltungen bereits einsetzen, expandiert sie aber in NAND-Gatter. Die Information über eine sichtbare Unterprogramm-Instanz bleibt dabei nicht erhalten.

### Umfang
- Bausteindefinition und konkrete Instanz unterscheiden; Name, stabile Kennung/Version sowie benannte Ports und Bitbreiten speichern.
- Eingangs-/Ausgangsbits eindeutig auf die internen Anschlüsse abbilden, einschliesslich mehrerer Ausgänge und unterschiedlich breiter Ports.
- Instanzen aus der Bibliothek in einer übergeordneten Schaltung verbinden; mehrere Instanzen desselben Bausteins unabhängig auswerten.
- Verschachtelte kombinatorische Bausteine unterstützen und zyklische Abhängigkeiten/rekursive Definitionen verständlich ablehnen.
- Für die bestehende NAND-Auswertung und Evolution eine geprüfte Expansion bereitstellen. Festlegen, ob eine Instanz unverändert bleibt oder intern mutierbar expandiert wird; veränderte Implementierungen nicht weiter als identische ursprüngliche Bausteine ausweisen.
- Hierarchie und Portzuordnung für Anzeige und Export erhalten; alte flache Schaltungen weiterhin laden.
- Instanzen an eine nachvollziehbare Implementierung binden, sodass eine neue beste Bibliotheksversion bestehende Schaltungen nicht stillschweigend verändert.
- Zunächst reine Funktionen ohne verborgenen Zustand. Mehrschrittige Quellprogramme nach [PRIM-07](#prim-07) können Referenzen liefern; ein als verdrahtet markierter Baustein benötigt eine passende Schaltungsimplementierung. Zustandsbehaftete Unterprogramme benötigen einen ausdrücklichen Zustandsvertrag.

### Abnahme
- [ ] Ein Baustein mit mehreren Eingängen und Ausgängen lässt sich zweimal instanziieren und verbinden.
- [ ] Hierarchische und expandierte Auswertung liefern dieselben Ergebnisse.
- [ ] Speichern/Laden erhält Definitionen, Versionen, Instanzen und Portzuordnung.
- [ ] Ungültige Breiten, fehlende Abhängigkeiten und Zyklen werden verständlich gemeldet.

### Abhängigkeiten
[PRIM-03](#prim-03); sichtbare Boxen und Debugging folgen in [PRIM-06](#prim-06).

### Ansatzpunkte
`primitives/circuit.py`, `primitives/library.py`, `primitives/evolution.py`, Export-/Importformat und API. Konkretisiert den bestehenden TASKS-Punkt zu expliziten Makroknoten.

<a id="prim-06"></a>

## PRIM-06 – Unterprogramme als klickbare Boxen im Verdrahtungsschema anzeigen und debuggen

**Status:** geplant, nicht implementiert.

### Ziel
Ein ganzes Unterprogramm erscheint als verständliche Box mit seinen Ein- und Ausgängen. Per Klick kann es untersucht und mit von Hand gesetzten Eingaben geprüft werden.

### Umfang
- Benannte Bausteine aus der Bibliothek im Schema einsetzen; Ports mit Namen, Breiten und aktuellen Werten darstellen.
- Eingeklappte Box und aufgeklappte interne Schaltung bzw. Detailansicht anbieten; zur übergeordneten Schaltung zurückkehren können.
- Ein Klick öffnet eine Debugansicht mit manuell editierbaren Eingangsbits bzw. Zahlenwerten und unmittelbar berechneten Ausgängen.
- Verbundene Eingänge im Gesamtschema bleiben durch ihre Quellen bestimmt. Handwerte zunächst in einer getrennten lokalen Testansicht verwenden; eventuelle spätere Overrides ausdrücklich markieren und zurücksetzbar machen.
- Testeingaben verändern weder die gespeicherte Bausteindefinition noch andere Instanzen.
- Auswertung innerhalb des Unterprogramms schrittweise nachvollziehen; bei verdrahteten Bausteinen interne Signale anzeigen. Vorlagen ohne Schaltung als Referenzausführung kennzeichnen.
- Boxen verschieben, zoomen und verbinden; Positionen und aufgeklappte Ansicht sinnvoll erhalten.

### Abnahme
- [ ] Ein mehrbitiger Baustein mit mehreren Ausgängen erscheint mit korrekten Ports und Werten.
- [ ] Ein Klick erlaubt lokale Handtests, z. B. ADD mit 0, Maximalwert und Überlauf.
- [ ] Zwei Instanzen desselben Unterprogramms bleiben unabhängig.
- [ ] Verlassen der Testansicht stellt die Sicht auf die tatsächlichen Eingangssignale wieder her.
- [ ] Schaltbild und Bausteinzuordnung bleiben nach Speichern/Laden korrekt.

### Abhängigkeiten
[PRIM-05](#prim-05), [PRIM-03](#prim-03); für Navigation und Leitungsführung [PRIM-01](#prim-01) und [PRIM-02](#prim-02) berücksichtigen.

### Ansatzpunkte
`web/graph.js`, `web/app.js`, Bibliotheksauswahl sowie Simulations-/Baustein-API.

<a id="prim-07"></a>

## PRIM-07 – Mehrschrittige Programme mit Variablen, if/else, while und for als Vektorquelle

**Status:** geplant, nicht implementiert.

### Ziel
Neben einem einzelnen Ausdruck sollen kurze deterministische Programme die Sollausgaben einer Aufgabe berechnen können: Zuweisungen, Zwischenergebnisse, Verzweigungen und Schleifen.

### Umfang
- Einen ausdrücklichen Programmmodus ergänzen; bisherige Ausdrücke bleiben gültig.
- Kleine dokumentierte Grammatik mit lokalen Variablen, Zuweisungen, mehreren Anweisungen, Ergebnisrückgabe, if/else, while und for. Syntax verbindlich festlegen; der Nutzerwunsch `for (i = 0; i < n; i++) { ... }` muss direkt oder über eine klar erklärte gleichwertige Schreibweise abgedeckt sein.
- Beispiel: Summe von 0 bis n-1 über eine for-Schleife; dieselbe Berechnung mit while; Auswahl eines Ergebnisses über if/else.
- Pro Eingabe vollständig frischen lokalen Zustand anlegen; Ein-/Ausgabeports und Zahlensemantik aus [PRIM-03](#prim-03) übernehmen.
- Einen begrenzten Interpreter verwenden, ohne beliebige Host-Code-Ausführung, Datei-/Netzwerkzugriff oder Imports.
- Anweisungs-/Iterationsbudget je Eingabe und Budget für die gesamte Vektorerzeugung, Grössenlimits sowie Abbruch unterstützen. Endlosschleifen liefern eine verständliche Fehlermeldung mit Eingabe und Quellposition; keine Teilergebnisse als gültigen vollständigen Datensatz speichern.
- Programmtext, Sprachversion und Parameter mit Datensatz speichern und über UI/API zugänglich machen.
- Ein terminierendes Programm kann zunächst eine Wahrheitstabelle für die vorhandene kombinatorische Suche liefern. Schleifen im Quelltext bedeuten nicht automatisch Rückkopplungen im NAND-Schema. Dauerhafter Zustand über Aufrufe bleibt eine eigene Registermodell-Erweiterung.

### Abnahme
- [ ] Mehrere Zuweisungen, verschachteltes if/else, while und for erzeugen korrekte Vektoren.
- [ ] Null Schleifendurchläufe, Grenzwerte, Überlauf und ungültige Programme sind nachvollziehbar behandelt.
- [ ] Endlosschleifen werden begrenzt und die Erzeugung lässt sich abbrechen.
- [ ] Ergebnisse entsprechen einer unabhängigen Referenz für kleine vollständig geprüfte Eingabebereiche.
- [ ] Alte Ausdrucksvorlagen und gespeicherte Datensätze funktionieren weiter.

### Abhängigkeiten
[PRIM-03](#prim-03); Labels und explizite Sprünge werden in [PRIM-08](#prim-08) ergänzt.

### Ansatzpunkte
Neues Parser-/Interpretermodul neben `primitives/dataset.py`, Erzeugungs-API und Programmeditor in `web/`.

<a id="prim-08"></a>

## PRIM-08 – Programmmodus: Labels, Sprungbefehle und schrittweise Ausführung ergänzen

**Status:** geplant, nicht implementiert.

### Ziel
Kurze Programme mit unbedingten und bedingten Sprüngen ermöglichen und ihren Ablauf beim Debuggen sichtbar machen.

### Umfang
- Auf dem Programmmodus eine kleine dokumentierte Sprungsyntax aufbauen: Labels, unbedingter Sprung und bedingter Sprung.
- Programmzähler bzw. ausführbare Zwischenrepräsentation definieren. Unbekannte/doppelte Labels und ungültige Ziele vor dem Lauf melden.
- Verhalten zusammen mit if/else und Schleifen festlegen, z. B. gemeinsame Übersetzung in eine Zwischenrepräsentation; Sprünge dürfen keine uneindeutigen lokalen Zustände erzeugen.
- Dieselben Ausführungsbudgets und Abbruchmöglichkeiten wie im strukturierten Programmmodus verwenden, auch bei Rückwärtssprüngen.
- Für eine einzelne Testeingabe Start, Einzelschritt, Fortsetzen, Stoppen und Zurücksetzen anbieten; aktuelle Anweisung, Variablen und Ergebnis anzeigen.
- Programm-Anweisungsschritte eindeutig von vorhandenen NAND-Gatter-/Simulationsschritten unterscheiden.
- Beispielprogramme mit genommenem/nicht genommenem bedingtem Sprung und einer durch Rücksprung gebildeten Schleife aufnehmen.
- TinyCPU-Sprungbedingungen sinnvoll zuordnen: z. B. Zero/NotZero/Negative. Fehlerabhängige Sprünge setzen ein ausdrücklich modelliertes Fehlerregister voraus und werden bis dahin als nicht unterstützt ausgewiesen. Keine vollständige TinyCPU-ISA-Kompatibilität aus einer ähnlichen Syntax ableiten.

### Abnahme
- [ ] Vorwärts-/Rückwärtssprünge sowie beide Pfade bedingter Sprünge funktionieren.
- [ ] Unbekannte Ziele und Endlosschleifen führen zu verständlichen, begrenzten Fehlern.
- [ ] Gesamtausführung und Einzelschritte liefern dasselbe Endergebnis.
- [ ] Reset stellt für dieselbe Eingabe denselben Anfangszustand her.

### Abhängigkeiten
[PRIM-07](#prim-07); die Befehlszuordnung ergänzt die Übernahmematrix aus [PRIM-04](#prim-04). Das in `docs/ARCHITEKTUR.md` geplante Registermodell bleibt für dauerhaft zustandsbehaftete Schaltungen erforderlich.

### Ansatzpunkte
Parser/Interpreter aus [PRIM-07](#prim-07), Debugansicht in `web/` und Ausführungs-API.



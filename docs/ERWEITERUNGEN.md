# Erweiterungs-Issues

Die Arbeitspakete PRIM-01 bis PRIM-08 konkretisieren die Erweiterungswünsche vom
25. Oktober 2026 und sind umgesetzt. PRIM-09 ergänzt den Wunsch nach mehr
Übersicht in Verdrahtungsschemen vom 30. Oktober 2026 und ist offen.
Sie sind lokale Planungs-Issues; auf GitHub wurden noch keine Issues angelegt.

Die Kennungen PRIM-01 bis PRIM-09 sind Dokumentationskennungen, keine GitHub-Issue-Nummern.

## Übersicht

| Kennung | Thema | Wunsch | Abhängigkeiten |
|---|---|---|---|
| [PRIM-01](#prim-01) | Zoom und Navigation (umgesetzt) | 1 | Eigenständig |
| [PRIM-02](#prim-02) | Drähte verschieben und speichern (umgesetzt) | 2 | Zoom-Koordinaten aus PRIM-01 berücksichtigen |
| [PRIM-03](#prim-03) | Variable Bitbreiten (umgesetzt) | 5 | Grundlage für weitere Funktionen |
| [PRIM-04](#prim-04) | TinyCPU und Operationsbeispiele (umgesetzt) | 3 | PRIM-03; Kontrollfluss später ergänzen |
| [PRIM-05](#prim-05) | Wiederverwendbare Unterprogramm-Bausteine (umgesetzt) | 4 | PRIM-03 |
| [PRIM-06](#prim-06) | Unterprogramm-Boxen und Debugging (umgesetzt) | 4 | PRIM-05; PRIM-01/02 berücksichtigen |
| [PRIM-07](#prim-07) | Mehrschrittige Programme und Kontrollstrukturen (umgesetzt) | 6 | PRIM-03 |
| [PRIM-08](#prim-08) | Sprungbefehle und Ablaufdebugger (umgesetzt) | 6 | PRIM-07 |
| [PRIM-09](#prim-09) | Übersicht durch Busse, Unter-FBoxen und Signalverfolgung (offen) | 30.10.2026 | PRIM-03/05/06; PRIM-01/02 berücksichtigen |

Empfohlene Reihenfolge: PRIM-01 → PRIM-02 für die Bedienung; danach PRIM-03 als
Grundlage. Anschliessend können Operationsbeispiele (PRIM-04), Bausteine
(PRIM-05 → PRIM-06) und Programmausführung (PRIM-07 → PRIM-08) getrennt wachsen.
Eine Operationsvorlage darf bereits nutzbar sein, bevor eine passende verdrahtete
Schaltung existiert.

Die Ausgangslage wurde anhand der vorhandenen Implementierung und der verlinkten
TinyCPU-Quellen geprüft. Der bei PRIM-04 übernommene Stand ist in
[TINYCPU.md](TINYCPU.md) mit Commit und Befehlsinventar festgehalten.

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

**Status:** umgesetzt am 25. Oktober 2026, einschliesslich Breitenvarianten für beliebige geöffnete Schaltungen.

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
- [x] ADD mit gleichen und unterschiedlichen Operandbreiten liefert definierte Ergebnisse, auch bei Überlauf.
- [x] Eine Vorlage funktioniert ohne bereits vorhandene Schaltung und kann zur Suche verwendet werden.
- [x] Breiten/Bitreihenfolge bleiben beim Speichern und Laden erhalten; bestehende Beispiele funktionieren weiter.

### Umsetzung
`primitives/ports.py` validiert benannte, fortlaufende LSB-first-Ports mit
unsigned/Zweierkomplement und Ergebnisüberlaufregeln. `primitives/operations.py`
trennt Operationsdefinitionen von konkreten Breitenvarianten. ADD, SUB, MUL und
die vorhandenen elementaren Logikoperationen sind parametrisiert; eigene
Ausdrücke unterstützen beliebig benannte zusätzliche Ein-/Ausgänge innerhalb
der bisherigen Gesamtlimits. UI, API und CLI erzeugen dieselben Metadaten.

Jede geöffnete Schaltung bietet **Neue Breitenvariante**. Vorhandene Referenzen
bleiben verwendbar; reine NAND-Schaltungen werden auf Wunsch bitweise auf
benannte Busports angewendet. Das ergibt eine Referenz für die neue Suche,
keine Behauptung einer bereits vorhandenen breiteren Arithmetikschaltung.
Eine einzelne bestehende Bitverdrahtung definiert keine allgemeine Rechenoperation.

Format und Semantik stehen in [FORMAT.md](FORMAT.md#benannte-ports-und-breitenvarianten),
die Prüfung in [VERIFIKATION.md](VERIFIKATION.md#variable-bitbreiten-prim-03).

Die Oberfläche führt eigenständige Breitenvarianten unter **Definierte Funktionen**,
einschliesslich Varianten ohne NAND-Implementierung. ADD(1,1,2), ADD(4,4,5) und
ADD(8,8,9) können gleichzeitig gespeichert und wieder geöffnet werden; auch
ADD(1,1,16) ist zulässig. Namen folgen automatisch der Breitenkombination.
Mehrere Stichproben derselben Funktion sind als einzelne Vektorsätze auswählbar.

Über **Eigene Formel definieren** können Rechenvorschriften direkt selbst
geschrieben werden: ein Ausdruck wie `a+b` oder mehrere Ergebnisse wie
`c=mod(a+b,2^4), e=div(a+b,2^4)`. Die Ports und Breiten sind frei einstellbar.
Formelquelle und Syntaxversion bleiben beim Speichern, Wiederöffnen und
Export/Import erhalten. Der Formelmodus verwendet `^` als Potenz und bietet
`mod`, `div` sowie explizites `xor`; bisherige Ausdrucksmodi bleiben kompatibel.

### Ansatzpunkte
`primitives/dataset.py`, Bibliotheksmetadaten, Katalog-API und Vorlagenauswahl. Grundlage für TinyCPU-Beispiele und Unterprogramm-Schnittstellen.

<a id="prim-04"></a>

## PRIM-04 – TinyCPU-Operationen und gängige Rechenoperationen als Beispiele übernehmen

**Status:** umgesetzt am 25. Oktober 2026.

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
- [x] Für jeden inventarisierten TinyCPU-Befehl ist der Übernahmestatus begründet dokumentiert.
- [x] IsZero, beide Schieberichtungen und die priorisierten Rechen-/Logikoperationen sind als Beispiele auswählbar.
- [x] Kleine Breiten werden vollständig, grössere Varianten mit klar gekennzeichneten Stichproben und Randfällen geprüft.
- [x] Referenzwerte und vorhandene Schaltungen stimmen auf den ausgewiesenen Prüfvektoren überein.
- [x] Herkunft, geprüfter TinyCPU-Stand und Semantikabweichungen sind dokumentiert.

### Umsetzung

26 Operationsdefinitionen, 29 importierbare Standardtabellen sowie Auswahl über
Oberfläche, API und CLI. DIV bietet Rundung gegen null und valid/div0-Ausgänge;
Schieber unterstützen feste und variable Weiten. Vergleiche, Null-/Vorzeichentests,
INC/DEC und MUX ergänzen die vorhandene Arithmetik und Wortlogik.
Grössere Stichproben enthalten gezielte Operand- und Schiebe-Randfälle.
Alle 50 Basisbefehle sowie drei optionale Systembefehle sind im
[Befehlsinventar](TINYCPU.md#vollständiges-befehlsinventar) einzeln eingeordnet.
Die Referenzen wurden mit 7424 tatsächlichen TinyCPU-VM-Schritten verglichen;
vorhandene NAND-Beispiele bleiben separat vollständig geprüft.
Details und Grenzen stehen in [TINYCPU.md](TINYCPU.md),
Prüfergebnisse in [VERIFIKATION.md](VERIFIKATION.md#tinycpu-operationen-prim-04).

### Abhängigkeiten
[PRIM-03](#prim-03); Kontrollfluss wird durch [PRIM-07](#prim-07) und [PRIM-08](#prim-08) ergänzt. Zustandsbehaftete CPU-Komponenten bleiben an das Registermodell aus der bestehenden Architekturplanung gebunden.

### Ansatzpunkte
`primitives/dataset.py`, `tools/seed_library.py`, `examples/`, Vorlagenkatalog und Dokumentation.

<a id="prim-05"></a>

## PRIM-05 – Unterprogramme als wiederverwendbare Bausteine mit definierten Ein-/Ausgängen modellieren

**Status:** umgesetzt am 25. Oktober 2026.

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
- [x] Ein Baustein mit mehreren Eingängen und Ausgängen lässt sich zweimal instanziieren und verbinden.
- [x] Hierarchische und expandierte Auswertung liefern dieselben Ergebnisse.
- [x] Speichern/Laden erhält Definitionen, Versionen, Instanzen und Portzuordnung.
- [x] Ungültige Breiten, fehlende Abhängigkeiten und Zyklen werden verständlich gemeldet.

### Umsetzung

`primitives/blocks.py` modelliert unveränderliche Definitionen mit vollständigen
Inhaltskennungen, Versionen und beliebig benannten Ports innerhalb der bisherigen
Bitgrenzen. Hierarchien können weitere Hierarchien enthalten. Separate rekursive
Auswertung und NAND-Expansion werden unabhängig verglichen; rekursive
Definitionsabhängigkeiten und zyklische Signalverbindungen werden abgelehnt.
Ein portables Paket enthält alle benötigten Definitionen.

Bibliothek, API und CLI speichern/importieren/exportieren diese Pakete.
Die Oberfläche übernimmt vorhandene Schaltungen, bereitet eine oder zwei
Instanzen vor und bietet einen JSON-Porteditor sowie eine Hierarchieliste.
Die drei Addiererbeispiele reichen bis zu Volladdierern mit verschachtelten
Halbaddierern und Logikbausteinen. Beide Evolutionsbackends verwenden geprüfte,
mutierbare Expansionen; ihre Ergebnisse beanspruchen keine Originalinstanzen.

Bedienung, Format und Grenzen stehen in [BAUSTEINE.md](BAUSTEINE.md),
Prüfergebnisse in [VERIFIKATION.md](VERIFIKATION.md#unterprogramm-bausteine-prim-05).

### Abhängigkeiten
[PRIM-03](#prim-03); sichtbare Boxen und Debugging folgen in [PRIM-06](#prim-06).

### Ansatzpunkte
`primitives/circuit.py`, `primitives/library.py`, `primitives/evolution.py`, Export-/Importformat und API. Konkretisiert den bestehenden TASKS-Punkt zu expliziten Makroknoten.

<a id="prim-06"></a>

## PRIM-06 – Unterprogramme als klickbare Boxen im Verdrahtungsschema anzeigen und debuggen

**Status:** umgesetzt am 25. Oktober 2026.

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
- [x] Ein mehrbitiger Baustein mit mehreren Ausgängen erscheint mit korrekten Ports und Werten.
- [x] Ein Klick erlaubt lokale Handtests, z. B. ADD mit 0, Maximalwert und Überlauf.
- [x] Zwei Instanzen desselben Unterprogramms bleiben unabhängig.
- [x] Verlassen der Testansicht stellt die Sicht auf die tatsächlichen Eingangssignale wieder her.
- [x] Schaltbild und Bausteinzuordnung bleiben nach Speichern/Laden korrekt.

### Umsetzung

Die Schaltbildprojektion ordnet jeden sichtbaren Anschluss einem exakten Signal
der geprüften NAND-Expansion zu. Instanzen erscheinen als Boxen mit Namen,
Version und benannten Bitanschlüssen. Die Höhe passt sich der Portanzahl an.
Klick oder Enter öffnet die interne Hierarchie bis hin zu einzelnen NAND-Gattern.
Bit- und Zahleneingaben, Reset und Gatterschritte arbeiten in einem eigenen
lokalen Testvektor. Beim Zurückkehren werden Eingangssignale, Schritt, Auswahl,
Kamera und Layout der übergeordneten Ansicht wiederhergestellt.

Gespeicherte Layouts sind an Paketkennung und Instanzpfad gebunden. Zwei Instanzen
derselben Definition teilen weder Layout noch Handwerte. Verbindungen werden
weiterhin im bestehenden benannten JSON-Porteditor festgelegt; Leitungswege sind
im Schema verschiebbar. Vorlagen ohne NAND-Implementierung bleiben als Funktionen
ohne Schaltung gekennzeichnet. Bedienung und Grenzen stehen in
[BAUSTEINE.md](BAUSTEINE.md#unterprogramm-boxen-und-lokales-debugging-prim-06),
die Prüfung in [VERIFIKATION.md](VERIFIKATION.md#unterprogramm-boxen-und-debugging-prim-06).

### Abhängigkeiten
[PRIM-05](#prim-05), [PRIM-03](#prim-03); für Navigation und Leitungsführung [PRIM-01](#prim-01) und [PRIM-02](#prim-02) berücksichtigen.

### Ansatzpunkte
`web/graph.js`, `web/app.js`, Bibliotheksauswahl sowie Simulations-/Baustein-API.

<a id="prim-07"></a>

## PRIM-07 – Mehrschrittige Programme mit Variablen, if/else, while und for als Vektorquelle

**Status:** umgesetzt am 25. Oktober 2026.

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
- [x] Mehrere Zuweisungen, verschachteltes if/else, while und for erzeugen korrekte Vektoren.
- [x] Null Schleifendurchläufe, Grenzwerte, Überlauf und ungültige Programme sind nachvollziehbar behandelt.
- [x] Endlosschleifen werden begrenzt und die Erzeugung lässt sich abbrechen.
- [x] Ergebnisse entsprechen einer unabhängigen Referenz für kleine vollständig geprüfte Eingabebereiche.
- [x] Alte Ausdrucksvorlagen und gespeicherte Datensätze funktionieren weiter.

### Umsetzung

`primitives/program.py` interpretiert eine geprüfte Integer-Sprache mit
Python-ähnlicher Einrückung, Zuweisungen, mehreren Rückgabewerten und
verschachtelten Kontrollstrukturen. `for i in range(n):` ist die dokumentierte
Entsprechung zu `for (i=0; i<n; i++)`. Der Interpreter verwendet frische lokale
Variablen je Eingabe und übernimmt die benannte Port-/Überlaufsemantik.
Anweisungs-, Iterations- und Gesamtbudgets sowie Abbruchprüfungen begrenzen die
Ausführung; es wird kein beliebiger Host-Code ausgeführt.

UI, asynchrone Erzeugungs-/Abbruch-API und CLI speichern Quelltext,
Sprachversion, Ports und Budgets mit den Vektoren. Fehler oder Abbruch erzeugen
keinen neuen Datensatz. Drei archivierte vollständige Beispiele enthalten
editierbare Quellen. Die Evolution verwendet unverändert kombinatorische
Vektoren. Syntax und Bedienung stehen in [PROGRAMME.md](PROGRAMME.md),
Prüfergebnisse in [VERIFIKATION.md](VERIFIKATION.md#mehrschrittige-programme-prim-07).

### Abhängigkeiten
[PRIM-03](#prim-03); Labels und explizite Sprünge werden in [PRIM-08](#prim-08) ergänzt.

### Ansatzpunkte
Neues Parser-/Interpretermodul neben `primitives/dataset.py`, Erzeugungs-API und Programmeditor in `web/`.

<a id="prim-08"></a>

## PRIM-08 – Programmmodus: Labels, Sprungbefehle und schrittweise Ausführung ergänzen

**Status:** umgesetzt am 25. Oktober 2026.

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
- [x] Vorwärts-/Rückwärtssprünge sowie beide Pfade bedingter Sprünge funktionieren.
- [x] Unbekannte Ziele und Endlosschleifen führen zu verständlichen, begrenzten Fehlern.
- [x] Gesamtausführung und Einzelschritte liefern dasselbe Endergebnis.
- [x] Reset stellt für dieselbe Eingabe denselben Anfangszustand her.

### Umsetzung

`label("ziel")`, `goto("ziel")`, `jump_if(bedingung, "ziel")` und die
Zahlbedingungen `jump_zero`, `jump_nonzero`, `jump_negative` erweitern
Sprachversion 1. Vor dem Lauf werden Namen, Ziele und Blockgrenzen geprüft.
Sprünge bleiben im selben Block oder verlassen ihn; das Einspringen in einen
anderen Block wird abgelehnt. Rückwärtssprünge zählen gegen Schritte und Iterationen.

Direkte Ausführung und Debugger verwenden dieselbe Zwischenrepräsentation und
denselben unterbrechbaren Interpreter. Der Programmeditor bietet Start,
Einzelschritt, Fortsetzen, Stoppen und Reset mit Quellzeile, PC, Variablen,
Budgetzählern und Ergebnis. Die Debugquelle bleibt von späteren Editoränderungen
unabhängig. Temporäre API-Sitzungen speichern keine Datensätze; Fortsetzen ist
auf 100 Anweisungen pro Aufruf begrenzt. Zwei zusätzliche vollständige Beispiele
zeigen eine Rücksprungschleife und beide Pfade einer Zero-Bedingung.
Fehlersprünge bleiben ohne Fehlerregister ausdrücklich nicht unterstützt.

Syntax und Bedienung stehen in [PROGRAMME.md](PROGRAMME.md), Prüfungen in
[VERIFIKATION.md](VERIFIKATION.md#labels-sprünge-und-ablaufdebugger-prim-08).

### Abhängigkeiten
[PRIM-07](#prim-07); die Befehlszuordnung ergänzt die Übernahmematrix aus [PRIM-04](#prim-04). Das in `docs/ARCHITEKTUR.md` geplante Registermodell bleibt für dauerhaft zustandsbehaftete Schaltungen erforderlich.

### Ansatzpunkte
Parser/Interpreter aus [PRIM-07](#prim-07), Debugansicht in `web/` und Ausführungs-API.

<a id="prim-09"></a>

## PRIM-09 – Verdrahtungsschema: Busse, Unter-FBoxen und Signalverfolgung

**Status:** offener Nutzerwunsch vom 30. Oktober 2026; noch nicht umgesetzt.

### Problem und Ziel

Bei grossen Verdrahtungsschemen geht die Übersicht über Gatter, Verbindungen
und deren Bedeutung verloren. Zoom, verschiebbare Boxen und manuelle
Leitungsführung helfen bei der Navigation; zusätzlich soll die Darstellung
auf die gerade relevante Ebene und den untersuchten Signalweg begrenzt werden.

**Bevorzugte Darstellung des Nutzers: Busse und verschachtelte Unter-FBoxen.**
Diese beiden Mittel haben bei der Umsetzung Vorrang. Signalverfolgung und
Fokusmodus ergänzen sie und sollen auch flache NAND-Netze untersuchbar machen.

### Umfang

1. **Mehrbitige Verbindungen als Busse bündeln.** Ein benannter Port wie
   `a[0…15]` erscheint als eine beschriftete Busleitung mit erkennbarer Breite.
   Einzelne Bits und ihre tatsächlichen Anschlüsse lassen sich bei Bedarf
   aufklappen und wieder bündeln. Besonders Verbindungen zwischen FBoxen sollen
   dadurch mit deutlich weniger sichtbaren Leitungen auskommen. Bitreihenfolge,
   Teilbereiche und abweichende Bitzuordnungen müssen nachvollziehbar bleiben.
2. **Hierarchische Funktionsblöcke als Unter-FBoxen zeigen.** Die Übersicht
   zeigt benannte Bausteine wie Addierer, Vergleicher oder Multiplexer samt
   ihren Schnittstellen. Ein Klick öffnet die interne Schaltung; weitere
   Unter-FBoxen können bis zu den NAND-Gattern untersucht werden. Ein klarer
   Instanzpfad und die Rückkehr zur übergeordneten Ebene erhalten die Orientierung.
   Auf den vorhandenen hierarchischen Bausteinen und dem lokalen Debugging aus
   PRIM-05/06 aufbauen und sie mit der Busdarstellung verbinden.
3. **Signale per Auswahl verfolgen.** Bei Auswahl eines Ausgangsbits alle
   Gatter und Leitungen hervorheben, die strukturell zu diesem Bit beitragen;
   die übrige Schaltung abblenden. Für interne Signale zusätzlich die Quellen
   sowie die davon abhängigen nachfolgenden Gatter und Ausgänge untersuchbar
   machen. Die Darstellung beantwortet damit konkret: „Wie entsteht dieses Bit?“
   Die Verfolgung soll auch ohne hinterlegte Bausteinhierarchie funktionieren.
4. **Fokusmodus anbieten.** „Nur den gewählten Ausgang und seine Abhängigkeiten
   anzeigen“ blendet unbeteiligte Teile vollständig aus. Auswahl und aktiver
   Filter bleiben erkennbar; eine sichtbare Aktion führt zur Gesamtschaltung
   zurück. Beim Wechsel zwischen Übersicht, Fokus und Hierarchie die vorhandenen
   Boxpositionen, manuellen Leitungswege und die vorherige Ansicht erhalten.

### Ausgangslage und Grenzen

Hierarchische Unterprogramm-Boxen, deren Öffnen und die Rückkehr zur Elternansicht
sind für ausdrücklich aufgebaute Bausteinpakete bereits vorhanden; siehe
[Bausteine und lokales Debugging](BAUSTEINE.md#unterprogramm-boxen-und-lokales-debugging-prim-06).
PRIM-09 erweitert diese Grundlage insbesondere um Busse und die gezielte
Beschränkung der sichtbaren Schaltung.

In evolutionär erzeugten flachen NAND-Netzen ist eine sinnvolle funktionale
Gliederung häufig nicht ausdrücklich hinterlegt. Die Bedeutung von Gruppen als
Addierer oder Multiplexer lässt sich aus der Verdrahtung allein nicht zuverlässig
zurückgewinnen. Vorhandene Hierarchien und benannte Schnittstellen verwenden;
automatisch erkannte Gruppen wären als Vorschläge zu kennzeichnen.
Signalverfolgung und Fokusmodus benötigen keine solche Bedeutungsrekonstruktion.
Die strukturelle Abhängigkeit eines Bits sagt zudem nicht aus, dass jede Quelle
bei der aktuellen Testeingabe den Ausgangswert tatsächlich beeinflusst.

### Priorität und Umsetzungsetappen

1. Busse und Unter-FBoxen als bevorzugte Übersicht gemeinsam nutzbar machen.
2. Signalverfolgung für Ausgänge und interne Signale ergänzen.
3. Den Fokus auf ausgewählte Abhängigkeiten mit einfacher Rückkehr anbieten.

Signalverfolgung bietet auch für flache NAND-Netze ohne hinterlegte Hierarchie
einen eigenständig nutzbaren Einstieg in die Untersuchung.

### Abnahme

- [ ] Mehrbitige Verbindungen zwischen FBoxen werden als benannte Busse mit Breite angezeigt; Einzelbits sind bei Bedarf zugänglich.
- [ ] Unter-FBoxen lassen sich über mehrere Ebenen öffnen; Instanzpfad und Rückkehr erhalten die Orientierung.
- [ ] Die Auswahl eines Ausgangs hebt genau dessen strukturelle Vorgänger und Verbindungen hervor; unbeteiligte Teile werden abgeblendet.
- [ ] Für interne Signale sind Quellen und abhängige Gatter/Ausgänge nachvollziehbar, auch bei gemeinsam genutzten Zwischensignalen und mehreren Ausgängen.
- [ ] Der Fokusmodus zeigt nur die gewählten Abhängigkeiten und bietet eine sichtbare Rückkehr zur Gesamtschaltung.
- [ ] Busauflösung und Signalverfolgung funktionieren auch bei direkten Durchleitungen und unterschiedlicher Bitzuordnung.
- [ ] Darstellung und Filter ändern keine logischen Verbindungen, Simulationsergebnisse oder gespeicherten Layouts; Signalwechsel und Simulationsschritte erhalten den Fokus.
- [ ] Hierarchische Beispiele und ein grosses flaches NAND-Netz werden praktisch geprüft, einschliesslich Zoom, Tastaturbedienung und Rückkehr zur vorherigen Ansicht.

### Abhängigkeiten und Ansatzpunkte

PRIM-03 liefert benannte mehrbitige Ports; PRIM-05/06 liefern Hierarchie und
Instanznavigation. Zoom und manuelle Leitungswege aus PRIM-01/02 berücksichtigen.
Ansatzpunkte sind `web/graph.js` für Graph und Leitungsdarstellung,
`web/app.js` für Auswahl und SVG, `web/block-debug.js` für Hierarchie und
Ansichtswiederherstellung sowie `web/index.html` und `web/style.css` für
Bedienelemente und Hervorhebung.



# Primitives
generate simple Programms

## Geplante Erweiterungen

Die [Erweiterungs-Issues](docs/ERWEITERUNGEN.md) beschreiben Zoom, verschiebbare
Leitungen, TinyCPU-Operationsbeispiele, variable Bitbreiten, Unterprogramm-Boxen
mit Debugging sowie mehrschrittige Programme mit Kontrollstrukturen und Sprüngen.
Die acht Arbeitspakete enthalten Umfang, Abnahmekriterien und Abhängigkeiten.
PRIM-01 (Zoom und Navigation) ist umgesetzt; die weiteren Aufgaben sind geplant.

## Beispiele anpassen

In der Browseroberfläche eine **Vorlage** auswählen, **Name**, **Eingangsbits N**,
**Ausgangsbits M** und **Ausdruck** bearbeiten, dann **Vektoren erzeugen** klicken.
Der Name ist eine Beschriftung; die Berechnung bestimmen die Bitanzahlen und der Ausdruck.

### MUL(2,2,4)

Die Vorlage **MUL(2,2,4)** ist direkt auswählbar. Alternativ diese Werte eintragen:

| Feld | Wert |
|---|---|
| Name | `MUL(2,2,4)` |
| Eingangsbits N | `4` (2 für a + 2 für b) |
| Ausgangsbits M | `4` (für c) |
| Ausdruck | `a*b` |
| Maximale Anzahl Vektoren | `16` oder mehr |

`a` und `b` sind die untere und obere Hälfte der Eingabe, jeweils 0–3.
Die Reihenfolge einer Vektorzeile ist `a0, a1, b0, b1, c0, c1, c2, c3`
(jeweils das niederwertigste Bit zuerst).
Alle 16 Eingabekombinationen werden erzeugt; der grösste Ausgang ist 3 × 3 = 9.
Tatsächlich erreichbar sind nur 0, 1, 2, 3, 4, 6 und 9. Auch 5, 7 und 8 sowie
10–15 kommen nie als Sollausgabe vor. Dafür braucht es keine zusätzlichen
Verbotszeilen: Eine auf allen 16 Eingaben korrekte Schaltung liefert diese Werte nie.

Die fertige Wahrheitstabelle lässt sich auch über **Eigene Vektoren importieren**
aus [`examples/mul-2-2-4.json`](examples/mul-2-2-4.json) laden.
Auf der Kommandozeile bleibt die Vorlage über `--preset mul` verfügbar.

## Retests und Bausteinbibliothek

NAND-Ausdrücke verwenden die Schreibweise `(1) ⊼ (2)`, mit dem Operator zwischen
den Argumenten. Verschachtelungen werden eingeklammert: `(1) ⊼ ((2) ⊼ (3))`.
Das ältere Format `(1,(2,3))` kann weiterhin eingelesen werden.

Während einer manuellen Programmgenerierung beendet **■ Suche abbrechen** den
laufenden Suchlauf, sowohl mit Python als auch mit TinyLanguage. Der abgebrochene
Lauf wird nicht gespeichert; bisherige Programme bleiben erhalten. Danach lässt
sich eine neue Evolution starten. Die automatische Hintergrundsuche läuft nach
dem Abbruch wieder weiter; sie lässt sich pro Aufgabe über **Frozen** stoppen.

Ein erneuter Suchlauf prüft das neue Programm gegen das bisher beste Programm
auf denselben Zuordnungsvektoren. Es gewinnt zuerst die kleinere Zahl falscher
Ausgangsbits, danach die kleinere Gatterzahl und schliesslich die geringere Tiefe.
Bei Gleichstand oder einem schlechteren Ergebnis bleibt die bisherige Version
erhalten. Die Oberfläche zeigt nach dem Retest beide Fehlerzahlen und die Auswahl.

Die Bibliothek zeigt pro Aufgabe nur die beste Version, auch bei bereits
vorhandenen Doppeleinträgen. Eine Aufgabe wird durch Eingangsbits, Ausgangsbits
und Zuordnungsvektoren bestimmt; Name und Seed ändern diese Identität nicht.
Andere Vektoren oder Bitbreiten bleiben eigenständige Aufgaben. Bereits gespeicherte
Versionen bleiben über ihre Kennung ladbar.

## Wenige Restfälle exakt korrigieren

Die Browseroberfläche aktiviert standardmässig **Wenige Restfälle exakt korrigieren**.
Nach einem Suchlauf werden bis zu vier fehlerhafte Eingaben korrigiert, sofern sie
höchstens 25 % der Testfälle ausmachen. Die Korrektur erkennt die genaue Eingabe
und erzwingt nur dort die Sollbits. Sie besteht aus normalen NAND-Gattern und
funktioniert deshalb auch im Schaltbild und im JSON-Export. Zusätzliche Gatter
zählen vollständig zur Gatterzahl und können das eingestellte Suchbudget
überschreiten; die Gesamtgrenze bleibt bei 512 Gattern.

Ein gespeichertes Programm lässt sich auch auswählen und direkt über
**Restfälle exakt korrigieren** ergänzen. Die Oberfläche zeigt die korrigierten
Eingaben und die zusätzlichen Gatter an. Alle vorhandenen Vektoren werden danach
erneut geprüft. Eine korrigierte Stichprobe bleibt eine Stichprobe und wird nicht
als vollständige Wahrheitstabelle bezeichnet.

## Interaktives Schaltbild

Das Schaltbild wird beim Öffnen vollständig eingepasst. **+** und **−** ändern
den Zoom, **100 %** stellt die Originalgrösse her und **Alles einpassen** zeigt
die gesamte Schaltung samt Leitungen. Der Zoombereich reicht von 0,1 % bis 400 %.
Mit **Strg + Mausrad** oder einer Touchpad-Zoomgeste wird um den Mauszeiger
gezoomt. Ohne Strg scrollt das Mausrad weiterhin die Seite.

Zum Verschieben des Ausschnitts eine freie Fläche ziehen oder die mittlere
Maustaste verwenden. Ist das Schaltbild selbst fokussiert, verschieben die
Pfeiltasten den Ausschnitt; **Shift** vergrössert die Schritte. **+ / −**, **0**
und **F** bedienen Zoom, Originalgrösse und Einpassen auch mit der Tastatur.
Bei einer ausgewählten Box verschieben die Pfeiltasten weiterhin die Box.
Zoom und Ausschnitt bleiben beim Umschalten von Signalen und bei Gatterschritten
erhalten. Sie verändern die gespeicherten Boxpositionen nicht und werden beim
Öffnen einer anderen Schaltung neu eingepasst. **Automatisch anordnen** passt
die neue Anordnung ebenfalls ein.

Alle Boxen sind eindeutig ab 0 nummeriert. Eine NAND-Box zeigt beispielsweise
`Box 2 ⊼ Box 3`; darunter steht separat ihr berechneter Signalwert. Anklicken
zeigt zusätzlich eine Erklärung der ausgewählten Box und ihrer Verknüpfung.
Ein Klick auf eine Eingangsbox schaltet deren Bit direkt zwischen 0 und 1 um.

Boxen lassen sich mit Maus oder Touch verschieben; die Zuleitungen folgen und
werden um andere Boxen herumgeführt. Die obere Quelle erhält den oberen
NAND-Eingang, damit sich die beiden Zuleitungen nicht unnötig kreuzen.
Überlagerungen von Boxen werden beim Verschieben verhindert.
Mit **Automatisch anordnen** wird die Anordnung neu berechnet.
Bei komplexen Schaltungen können Leitungskreuzungen weiterhin vorkommen.

**Layout speichern** sichert die Positionen pro Schaltung im Datenverzeichnis
des lokalen Servers. Sie werden beim erneuten Öffnen automatisch geladen und
bleiben nach einem Serverneustart erhalten. Änderungen der Eingangswerte oder
des Simulationsschritts verändern die Positionen nicht. Eine andere Schaltung
erhält ein eigenes Layout. Tastatur: Tab wählt eine Box, Pfeiltasten verschieben
sie, Leertaste oder Enter schalten Eingänge um.

## Hintergrundsuche und Frozen

Solange der Webserver läuft, sucht er automatisch reihum für alle Aufgaben der
Bibliothek weiter. Ein separater Python-Prozess läuft unter Windows mit
Idle-Priorität (ohne zusätzliches Fenster), unter Unix mit `nice +15`.
Jeder Durchgang hat höchstens 0,6 Sekunden für die Evolution und insgesamt
4 Sekunden inklusive Start, Bewertung und Korrektur. Danach folgen mindestens
5 Sekunden Pause. Es läuft höchstens ein Hintergrundprozess gleichzeitig.

Die Suche startet bei der bisherigen Lösung, sofern diese ins Gatterbudget passt,
und optimiert auch nach Erreichen von null Fehlern weiter. Neue Seeds variieren
die Durchgänge. Bessere Ergebnisse werden erst nach Gegenprüfung übernommen;
die Bibliothek zeigt weiterhin eine Version pro Aufgabe. Bei manuellen Suchläufen
wird der Hintergrundprozess abgebrochen und erst anschliessend wieder gestartet.

Die Checkbox **Frozen** an jedem Bibliothekseintrag stoppt den laufenden
Hintergrunddurchgang für diese Aufgabe und verhindert weitere automatische
Versuche. Die Einstellung gilt für die Aufgabe, bleibt beim Ersetzen der Version
und nach einem Neustart erhalten und lässt sich jederzeit wieder aufheben.
Explizite manuelle Suchläufe und Korrekturen bleiben möglich. Beim Beenden des
Servers wird auch der Hintergrundprozess beendet. Der Browser muss für die
Hintergrundsuche nicht geöffnet sein; eine geöffnete Seite aktualisiert den
Bibliotheksstatus alle fünf Sekunden.

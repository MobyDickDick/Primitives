# Verifikation des ersten Prototyps

Stand: 25. Oktober 2026. Geprüft mit Python 3.14.5 und der vorhandenen
TinyLanguage-Laufzeit unter Windows.

## Automatische Prüfungen

`python -m unittest discover -s tests -v`: **17 Tests erfolgreich**.

Die Tests prüfen widersprüchliche N:1- und N:M-Zuordnungen, Duplikate und
ungültige Bits, Zahlkodierung und mathematische Vorlagen, sichere Ausdrücke,
Sampling, NAND-Semantik, gemeinsame Teilbäume, ungültige Verweise, Kompaktierung,
die Übereinstimmung bitparalleler mit skalarer Fitness, Suchbudgets und Seeds,
Bibliothekskomposition, die Unterscheidung Stichprobe/vollständige Prüfung,
einen echten TinyLanguage-Suchlauf und den vollständigen HTTP-Weg bis zum
gespeicherten und erneut ausgewerteten Programm. Bei fehlender TinyLanguage-
Laufzeit wird der entsprechende Test ausdrücklich übersprungen.

`node --check web/app.js`: JavaScript-Syntaxprüfung erfolgreich.

## Zoom und Navigation (PRIM-01)

Geprüft am 25. Oktober 2026:

- `node --test tests/test_graph.js tests/test_viewport.js`: **7 Tests erfolgreich**.
  Neben dem bisherigen Routing prüfen sie Zoom um einen festen Mauspunkt,
  Zoomgrenzen, Verschieben bei verschiedenen Massstäben und vollständiges
  Einpassen breiter/hoher Schaltungen bei schmalen und breiten Ansichtsgrössen.
- `python -m unittest discover -s tests -p test_server.py -v`: **6 Tests erfolgreich**,
  einschliesslich Auslieferung von `viewport.js` und Layout-Persistenz. Die lokalen
  HTTP-Tests wurden ausserhalb der Sandbox ausgeführt, da diese Loopback-Verbindungen blockiert.
- `node --check web/app.js` und `node --check web/viewport.js`: erfolgreich.
- Browserprüfung auf einem temporären lokalen Server ohne Hintergrundsuche:
  Einpassen, 100 %, 125 %, Verschieben des Ausschnitts per Maus, Tastaturzoom,
  Boxziehen bei etwa 65 % und 125 %, Signalwechsel und Gatterschritte ohne
  Zurücksetzen der Ansicht sowie Speichern und erneutes Laden der Boxpositionen.
  Beim Ziehen um 35 Bildschirmpixel bei 125 % bewegte sich die Box korrekt um
  28 Schaltungskoordinaten; der Ausschnitt blieb unverändert.

Der Mausanker der Rad-Zoomfunktion ist durch die Geometrietests geprüft;
eine physische Touchpad-Zoomgeste wurde nicht manuell getestet.

## Manuelle Leitungswege (PRIM-02)

Geprüft am 25. Oktober 2026:

- `node --test tests/test_graph.js tests/test_viewport.js`: **11 Tests erfolgreich**.
  Neue Fälle prüfen Knicke in geraden Leitungen, feste Endpunkte, stabile logische
  Portkennungen, getrennte doppelte NAND-Eingänge, Anschlussanpassung bei
  Boxbewegungen, Hindernisse, temporäre automatische Führung und Wiederherstellung.
- `python -m unittest discover -s tests -v`: **46 Tests erfolgreich**, einschliesslich
  **7 HTTP-Tests**. Neue HTTP-Fälle prüfen Leitungswege nach einem tatsächlichen
  Serverneustart, Legacy-Layouts, getrennte Eingangskennungen und die Ablehnung
  ungültiger Wege ohne Überschreiben des zuvor gespeicherten Layouts.
  Wegen der Loopback-Sperre der Sandbox wurde die Python-Suite ausserhalb ausgeführt.
- `node --check web/app.js` und `git diff --check`: erfolgreich.
- Browserprüfung auf temporärem lokalem Server ohne Hintergrundsuche: gerade
  Leitung bei 125 % ziehen (60 Bildschirmpixel entsprechen 48 Schaltungseinheiten),
  per Tastatur weiter verschieben, Signal umschalten, speichern und erneut öffnen.
  Bei etwa 71 % wurde einer von zwei NAND-Eingangsdrähten derselben Quelle
  unabhängig verschoben (45 Pixel entsprechen rund 63,16 Einheiten). Anschliessend
  Box verschoben und Gatterschritte durchlaufen; manuelle Wege blieben erhalten.
  Entf sowie „Automatisch anordnen“ setzen die Wege zurück. Ein ungültiger Weg
  durch eine Box wird mit sichtbarer Meldung abgelehnt.

Maus und Tastatur wurden praktisch geprüft; Touch verwendet dieselben
Pointer-Ereignisse, wurde aber nicht an einem Touchgerät geprüft.

## Tatsächliche Suchergebnisse

Alle folgenden Programme wurden vom TinyLanguage-Backend gefunden und gegen
ihre vollständigen Wahrheitstabellen geprüft. Die Gatterzahlen beschreiben
die gefundenen Ergebnisse; sie behaupten keine Minimalität.

| Funktion | N:M | NAND-Gatter | Tiefe | Falsche Ausgangsbits |
|---|---:|---:|---:|---:|
| NOT | 1:1 | 1 | 1 | 0 |
| NAND | 2:1 | 1 | 1 | 0 |
| AND | 2:1 | 2 | 2 | 0 |
| OR | 2:1 | 4 | 3 | 0 |
| XOR | 2:1 | 4 | 3 | 0 |
| NOR | 2:1 | 8 | 6 | 0 |
| XNOR | 2:1 | 5 | 4 | 0 |
| Halbaddierer | 2:2 | 6 | 3 | 0 |

XOR ohne Startbibliothek: 8 Gatter Budget, 24 Nachkommen, 200 Generationen,
Seed 1. Gefunden nach 16 Generationen und 383 Bewertungen.

Halbaddierer mit den sieben zuvor gespeicherten Logikbausteinen: 12 Gatter
Budget, 24 Nachkommen, 1000 Generationen, Seed 1. Gefunden nach
204 Generationen und 4876 Bewertungen. Diese Angaben sind zusammen mit
den konkreten Schaltungen in `examples/library/` archiviert.

## Bedienprüfung

Im Browser geprüft: Vektoren erzeugen, TinyLanguage-Suche starten,
XOR-Ergebnis speichern und anzeigen, Eingangsbit umschalten, Ausgangsänderung
beobachten, schrittweise Gatteranimation abspielen sowie den N:M-Halbaddierer
aus der Bibliothek laden. Alle vier Halbaddierer-Zeilen werden korrekt angezeigt.

Zusätzlich wurden die Oracle-Kommandozeile und die vollständige Generierung
von 65536 Sinusvektoren mit 16 Eingangs- und 12 Ausgangsbits ausgeführt.
Damit wurde die **Vektorgenerierung**, nicht die Synthese einer vollständigen
Sinusschaltung nachgewiesen.


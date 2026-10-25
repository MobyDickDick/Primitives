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


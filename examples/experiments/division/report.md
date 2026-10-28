# Gemessene Divisionsexperimente

Erzeugt mit `python -m tools.investigate_division`.

`m,n` sind hier Bitbreiten; die separat angefragten Zahlenwerte 1 bis 4 stehen in `values-1-to-4.csv`.
Semantik: c=floor(a/b), err=0; bei b=0: c=0, err=1. Ein Rest ungleich null ist kein Fehler.

Zufallssuche: Python, Seeds [11, 29, 47], Population 24, höchstens 200 Generationen/Seed,
höchstens 4801 Bewertungen/Seed, Fehler/Gatter/Tiefe als Rang.
Keine Bibliothek, kein bekannter Dividierer als Start, keine Restfallkorrektur; Abbruch bei Fehlerfreiheit.
Das Suchgatterbudget ist min(128,max(8,strukturelle Gatter+8)); die JSON-Berichte enthalten jede Konfiguration.
Der beste von drei Läufen ist keine Erfolgswahrscheinlichkeit und ein Fehlschlag kein Unmöglichkeitsbeweis.

## Genau die Zahlenwerte 1 bis 4

Zusätzlich separat gesucht: nur die 16 angefragten Paare, 32 Suchgatter, drei Seeds, gleiche Population und Generationenzahl.
Diese Teilmenge enthält keinen Nullteiler; ihr Fehlerbit ist immer 0. Sie identifiziert daher keine allgemeine Division.
Die Gegenprüfung testet dieselbe gefundene Schaltung auf allen 64 Paaren zweier 3-Bit-Zahlen, einschliesslich Nullteilern.

| Seed | Bitfehler / 64 Sollbits (16 Paare) | Gegenprüfung: Bitfehler / 256 Sollbits |
|---|---|---|
| 11 | 10 | 81 |
| 29 | 10 | 67 |
| 47 | 11 | 103 |

## Alle Bitbreiten 1 bis 4

| m | n | Eingaben | NANDs konstruiert | Tiefe | Suchbudget Gatter | Beste Bitfehler / Sollbits | Such-NANDs | exakt / Läufe |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 4 | 5 | 4 | 13 | 0 / 8 | 4 | 3 / 3 |
| 1 | 2 | 8 | 12 | 8 | 20 | 1 / 16 | 5 | 0 / 3 |
| 1 | 3 | 16 | 17 | 10 | 25 | 3 / 32 | 3 | 0 / 3 |
| 1 | 4 | 32 | 22 | 12 | 30 | 3 / 64 | 3 | 0 / 3 |
| 2 | 1 | 8 | 20 | 9 | 28 | 0 / 24 | 6 | 2 / 3 |
| 2 | 2 | 16 | 39 | 17 | 47 | 5 / 48 | 8 | 0 / 3 |
| 2 | 3 | 32 | 58 | 21 | 66 | 9 / 96 | 12 | 0 / 3 |
| 2 | 4 | 64 | 77 | 25 | 85 | 11 / 192 | 6 | 0 / 3 |
| 3 | 1 | 16 | 35 | 14 | 43 | 0 / 64 | 8 | 2 / 3 |
| 3 | 2 | 32 | 70 | 27 | 78 | 16 / 128 | 15 | 0 / 3 |
| 3 | 3 | 64 | 105 | 33 | 113 | 31 / 256 | 23 | 0 / 3 |
| 3 | 4 | 128 | 140 | 39 | 128 | 43 / 512 | 17 | 0 / 3 |
| 4 | 1 | 32 | 50 | 19 | 58 | 16 / 160 | 6 | 0 / 3 |
| 4 | 2 | 64 | 101 | 37 | 109 | 63 / 320 | 15 | 0 / 3 |
| 4 | 3 | 128 | 152 | 45 | 128 | 104 / 640 | 23 | 0 / 3 |
| 4 | 4 | 256 | 203 | 53 | 128 | 160 / 1280 | 12 | 0 / 3 |

Alle 900 Eingabepaare wurden für die strukturellen Netze und die getaktete Simulation vollständig geprüft.
Die separaten CSV-Dateien enthalten lesbare Binärzahlen mit höchstem Bit links; JSON-Vektoren sind LSB-first.
Bei Nullteiler bleibt das CSV-Restfeld leer. Der Rest dient nur zur Kontrolle und gehört nicht zum DIV-Ausgang.

## Wiederverwendeter Schritt

Diese Evolution startet ausdrücklich vom korrekten konstruierten Schrittnetz und optimiert es weiter.
Die gesamte Wahrheitstabelle wird geprüft, auch Zustände ausserhalb r<b und b>0.
Dort lautet die definierte Restfunktion (2*r+digit-b*take) modulo 2**n mit take=(2*r+digit>=b).

| n | NANDs konstruiert | NANDs nach Evolution | geprüfte Schritt-Eingaben |
|---|---|---|---|
| 1 | 13 | 8 | 8 |
| 2 | 29 | 24 | 32 |
| 3 | 45 | 38 | 128 |
| 4 | 61 | 55 | 512 |

Schritt-NAND-Zahlen enthalten keine Register, Taktsteuerung oder Nullteilererkennung.
Die Rückführung wird in Python mit getrennten Registerzuständen simuliert; das Projektformat bleibt azyklisch.
Die Division braucht bei b>0 genau m Rechenschritte, zusätzlich zum Laden und Auslesen in realer Hardware.
Die JSON-Datei `trace-13-div-3.json` zeigt sämtliche Zustandsübergänge für 13/3.

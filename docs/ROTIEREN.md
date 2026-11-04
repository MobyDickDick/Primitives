# GEN-05: Rotieren

`ROL<t,s_bits>(a,s)` und `ROR<t,s_bits>(a,s)` haben die Eingänge `a[t]`,
`s[s_bits]` und den Ausgang `c[t]`. Ports und Bitarrays sind LSB-first.
`s` ist ein unsigned Abstand; `s_bits` ist die Breite dieses Ports.
Der wirksame Abstand ist immer **s modulo t**. Alle Datenbits bleiben erhalten.

Für `d=s%t` und `mask=2**t-1` gilt:

| Funktion | Ergebnis |
| --- | --- |
| ROL | `((a << d) \| (a >> (t-d))) & mask` |
| ROR | `((a >> d) \| (a << (t-d))) & mask` |

Beispiel bei t=4: `ROL(9,1)=3`, `ROR(9,1)=12`. Bei s=4 ist das
Ergebnis wieder 9; s=5 wirkt wie s=1. Abstand null und jedes Vielfache von t
sind die Identität. Bei **t=1** gilt dies für jeden darstellbaren Abstand.
Beide Rotationen sind invers: `ROR(ROL(a,s),s)=a` und umgekehrt.

## Editierbare Quellen und MUX-Stufen

- [ROL-Quelle](../examples/templates/rotate-rol.prim) und
  [abstraktes Template](../examples/templates/rotate-rol.abstract.json).
- [ROR-Quelle](../examples/templates/rotate-ror.prim) und
  [abstraktes Template](../examples/templates/rotate-ror.abstract.json).

Die Parameterbedingungen sind `t>=1`, `s_bits>=1` und `t+s_bits<=128`.
Zweierpotenzbreiten sind nicht erforderlich; direkte Funktionsaufrufe prüfen
dieselben Bedingungen. Die internen `ROLStage<t,k>`/`RORStage<t,k>` verlangen
`1<=t<=128` und `0<=k<t`.

Wie beim [Barrel-Shifter (GEN-04)](BARREL-SHIFTER.md) wählt ein Bit-MUX
`(x & (1 ^ sel)) | (y & sel)` zwischen Durchleitung und einer festen
Umverdrahtung. Das gemeinsame Verfahren lässt sich für beide Aufgaben nutzen;
die Vorlagen bleiben einzeln editierbar und ohne externe Quelldateien
importierbar. Die Rotationsstufen verdrahten zyklisch statt mit Füllbits.

Für Auswahlbit j hat die feste Stufe den Abstand `(2**j)%t`.
Die Summe der gewählten Abstände ergibt s modulo t. Alle Bedingungen,
Schleifen und Indizes hängen nur von festen Parametern ab; die Synthese
braucht keinen datenabhängigen Modulo-Baustein. Bei Zweierpotenzbreiten
entfallen hohe Auswahlbits, deren Stufenabstand null ist. Bei anderen Breiten
werden auch hohe Auswahlbits ausgewertet, beispielsweise t=3 und s=64.

Jede wirksame Stufe ist eine sichtbare Unter-FBox `rotate_j` mit einer
NAND-Implementierung. Stufen mit Abstand null entfallen vollständig;
die Ein-Bit-FBox enthält nur direkte Verbindungen. Die flachen Exporte
entstehen durch Hierarchieexpansion und anschliessende Vereinfachung.

## Exporte und vollständige Prüfung

Jede Tabellenzeile liegt für beide Richtungen vor: insgesamt **18 Instanzen**.
ROL und ROR haben hier dieselben Gatterzahlen und Tiefen.

| t | s_bits | Eingaben je Richtung | NANDs | Tiefe |
| --- | --- | --- | --- | --- |
| 1 | 1 | 4 | 0 | 0 |
| 1 | 2 | 8 | 0 | 0 |
| 1 | 4 | 32 | 0 | 0 |
| 2 | 1 | 8 | 7 | 3 |
| 2 | 2 | 16 | 7 | 3 |
| 2 | 4 | 64 | 7 | 3 |
| 4 | 1 | 32 | 13 | 3 |
| 4 | 2 | 64 | 26 | 5 |
| 4 | 4 | 256 | 26 | 5 |

Alle **968 Eingabefälle** sind gegen eine unabhängige Ganzzahlreferenz geprüft:
Quellprogramm, hierarchische Auswertung, expandierte und vereinfachte Netze
sowie direkte Quellsynthese stimmen überein. Die Tests prüfen alle
exportierten Vektorzeilen und Hardwareformen zusätzlich durch unabhängiges
Verschieben einzelner Bitpositionen. Rotations-Inversen, Periodizität und
Erhalt der Anzahl gesetzter Bits sind für t=1,2,3,4,5 mit den jeweiligen
kleinen Auswahlports vollständig geprüft, auch in den F-Boxen und der
direkten Synthese.

Die Ordner [rotate-rol](../examples/circuits/rotate-rol/verification.json) und
[rotate-ror](../examples/circuits/rotate-ror/verification.json) enthalten je
neun `.template.json`, `.vectors.json`, `.block.json`, `.circuit.json` und
`.nand.txt` sowie einen Prüfbericht. Gatterzahlen sind Konstruktionswerte;
ein Minimalitätsnachweis wird nicht behauptet.

## Grössere Breiten und Grenzen

Zusätzliche Referenztests verwenden `(t,s_bits)=(3,7),(5,4),(8,4),(16,4),
(32,6),(64,4),(127,1),(1,127)` mit Grenzfällen und reproduzierbaren
Stichproben. Diese Eingaberäume sind **nicht vollständig geprüft**.
Bis t=16 sowie für t=1 werden dabei auch direkte Synthese und F-Boxen
geprüft. Null, Maximalwerte, einzelne höchste Bits, Abstände null, t-1,
t, t+1 und das höchste Auswahlbit sind enthalten, soweit darstellbar.

Die letzten beiden Kombinationen erreichen die **128-Bit-Eingangsgrenze**.
Ein 128-Bit-Datenport lässt keinen Platz für den mindestens ein Bit breiten
Abstandsport. Die Ausgangsseite hat t Bits.

Die Konstruktionen für t=64, s_bits=6 überschreiten bei direkter Synthese
und Hierarchieexpansion die **512-NAND-Gattergrenze**; die Referenzprogramme
bleiben dort ausführbar. Die direkte Synthese begrenzt auch temporäre Gatter
vor der Kompaktierung. Deshalb scheitert dort bereits t=32, s_bits=6,
während die einzeln kompaktierten F-Box-Stufen zusammen 485 NANDs bei Tiefe 11
ergeben; diese Hierarchie wird mit gezielten Fällen geprüft.
Bei t=16, s_bits=4 liefern beide Wege 196 NANDs bei Tiefe 9.
Zulässige Portbreiten garantieren keine Ausführung
innerhalb aller Budgets: t=63, s_bits=65 überschreitet das Budget von
100000 Schritten je Eingabe. Die Grenzen von 65536 Vektoren und fünf
Millionen gemeinsamen Schritten bei der Vektorerzeugung gelten weiterhin.

Reproduzierbar erzeugen und prüfen:

```powershell
python -m tools.export_rotations
python -m unittest discover -s tests -p test_rotations.py -v
```

## Einmalige Bibliotheksmigration

Beim nächsten Serverstart ergänzt `rotations-v1` zwei Templates und
18 vollständig geprüfte Funktionen unter **Beispiele → Rekursion →
Rotationen**, dazu 18 wiederverwendbare F-Boxen. Bestehende Ordner,
Beschreibungen, Benennungen, Zuordnungen und gleich gute oder bessere
Schaltungen bleiben erhalten. Funktional identische Tabellen können denselben
Bibliotheksgewinner nutzen; beide Vorlagen und F-Boxen bleiben separat verfügbar.

Der Marker verhindert das erneute Anlegen später gelöschter Funktionen,
Templates oder F-Boxen. Tests prüfen den Erhalt vorhandener Bibliothekseinträge,
erneuten Start, API-Katalog, direkte Synthese, Bausteinauswertung und
Navigation in eine feste Rotationsstufe. Server neu starten und Browserseite
neu laden.

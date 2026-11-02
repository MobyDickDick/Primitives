# GEN-04: Barrel-Shifter

`SHL<t,s_bits>(a,s)`, `SHR<t,s_bits>(a,s)` und `SAR<t,s_bits>(a,s)`
haben die Eingänge `a[t]`, `s[s_bits]` und den Ausgang `c[t]`.
Ports und Bitarrays sind LSB-first. `s` ist immer ein **unsigned** Abstand;
`s_bits` bezeichnet seine Portbreite, nicht den Abstand selbst.

| Funktion | Ergebnis | Verhalten bei s >= t |
| --- | --- | --- |
| SHL | `(a * 2**s) mod 2**t` | 0 |
| SHR | `a // 2**s` | 0 |
| SAR | Zweierkomplementwert von a arithmetisch nach rechts, als t-Bit-Muster ausgegeben | Alle Bits gleich a[t-1] |

Hinausgeschobene Bits verfallen. SHL/SHR füllen mit Nullen auf; SAR führt das
Vorzeichenbit nach. Der Ausgang bleibt auch für negative SAR-Ergebnisse ein
unsigned gespeichertes Bitmuster. Beispiel bei t=4: `SHL(9,1)=2`,
`SHR(9,1)=4`, `SAR(9,1)=12` (1001 entspricht -7, 1100 entspricht -4).
Bei s=4 liefern SHL/SHR null und SAR liefert 15 für negative Werte bzw. 0
für nichtnegative Werte. Bei s=0 sind alle drei Operationen die Identität;
SAR mit t=1 ist für jeden Abstand eine reine Durchleitung.

## Editierbare Quellen und feste Stufen

- [SHL-Quelle](../examples/templates/barrel-shl.prim) und
  [abstraktes Template](../examples/templates/barrel-shl.abstract.json).
- [SHR-Quelle](../examples/templates/barrel-shr.prim) und
  [abstraktes Template](../examples/templates/barrel-shr.abstract.json).
- [SAR-Quelle](../examples/templates/barrel-sar.prim) und
  [abstraktes Template](../examples/templates/barrel-sar.abstract.json).

Die Parameterbedingungen sind `t>=1`, `s_bits>=1` und `t+s_bits<=128`.
Zweierpotenzbreiten sind nicht erforderlich. Direkte Funktionsaufrufe prüfen
dieselben Bedingungen. Interne `SHLStage<t,k>`/`SHRStage<t,k>`/`SARStage<t,k>`
verlangen `1<=k<=t<=128`.

Für jedes Auswahlbit j wird eine feste Stufe mit Abstand `min(2**j,t)`
erzeugt. Ein Bit-MUX wählt zwischen Durchleitung und fest verdrahteter
Verschiebung. Abstände ab t werden auf t begrenzt: jede solche Stufe füllt
das ganze Wort mit Nullen bzw. Vorzeichenbits. So werden auch hohe gesetzte
Schiebebits ausgewertet; der Abstand wird weder abgeschnitten noch modulo t
reduziert. Bedingungen und Schleifen hängen nur von Parametern ab.

Die direkte Synthese entrollt diese Bitlogik nach NAND. Jede F-Box enthält
`s_bits` sichtbare Unter-FBoxen `shift_0`, `shift_1`, … mit den festen Stufen.
Die Exporte verwenden die expandierte, anschliessend vereinfachte Hierarchie.
Das Vorzeichenbit von SAR wird direkt durchgeleitet.

## Exporte und vollständige Prüfung

Jede Tabellenzeile liegt für alle drei Operationen vor, insgesamt **27
Instanzen**. SHL und SHR haben hier dieselben Gatterzahlen und Tiefen.

| t | s_bits | Eingaben je Operation | NANDs SHL/SHR | NANDs SAR | Tiefe SHL/SHR | Tiefe SAR |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 4 | 3 | 0 | 3 | 0 |
| 1 | 2 | 8 | 6 | 0 | 5 | 0 |
| 1 | 4 | 32 | 12 | 0 | 9 | 0 |
| 2 | 1 | 8 | 6 | 4 | 3 | 3 |
| 2 | 2 | 16 | 11 | 8 | 5 | 5 |
| 2 | 4 | 64 | 21 | 16 | 9 | 9 |
| 4 | 1 | 32 | 12 | 10 | 3 | 3 |
| 4 | 2 | 64 | 23 | 19 | 5 | 5 |
| 4 | 4 | 256 | 41 | 35 | 9 | 9 |

Alle **1452 Eingabefälle** sind gegen eine unabhängige Ganzzahlreferenz
geprüft: Quellprogramm, hierarchische Auswertung, expandierte und vereinfachte
Netze sowie direkte Quellsynthese stimmen überein. Die Tests prüfen alle
Vektorzeilen und alle Hardwareformen zusätzlich mit einer unabhängigen
Zuordnung der einzelnen Bitpositionen. Null, Maximalwerte, beide Vorzeichen,
Abstand null, t-1, t und grössere Abstände sind damit vollständig abgedeckt,
soweit der jeweilige Schiebeport sie darstellen kann.

Die Ordner [barrel-shl](../examples/circuits/barrel-shl/verification.json),
[barrel-shr](../examples/circuits/barrel-shr/verification.json) und
[barrel-sar](../examples/circuits/barrel-sar/verification.json) enthalten je
neun `.template.json`, `.vectors.json`, `.block.json`, `.circuit.json` und
`.nand.txt` sowie einen Prüfbericht. Gatterzahlen sind Konstruktionswerte;
ein Minimalitätsnachweis wird nicht behauptet.

## Grössere Breiten und Grenzen

Zusätzliche Referenztests verwenden `(t,s_bits)=(3,3),(8,4),(16,4),(32,6),
(64,4),(127,1),(1,127)` mit gezielten Grenzfällen und reproduzierbaren
Stichproben. Diese grösseren Eingaberäume sind **nicht vollständig geprüft**.
Bis t=16 sowie bei t=1 werden auch die direkte Synthese und die F-Boxen
gegen diese Fälle geprüft. Die beiden letzten Kombinationen erreichen die
128-Bit-Grenze der Eingangsseite; ein 128-Bit-Datenport lässt keinen Platz
für den mindestens ein Bit breiten Schiebeport.

Für t=16, s_bits=4 benötigt die direkte Synthese 181 NANDs bei SHL/SHR
und 173 bei SAR. Bei t=64, s_bits=6 überschreiten alle drei Konstruktionen
die **512-NAND-Gattergrenze**, sowohl bei direkter Synthese als auch bei
Hierarchieexpansion. Die Referenzprogramme bleiben dort ausführbar.
Breitenbedingungen garantieren nicht die Ausführbarkeit innerhalb aller
Budgets: beispielsweise überschreitet t=64, s_bits=64 das Budget von
100000 Schritten je Eingabe. Die normalen Grenzen für Vektorerzeugung
(65536 Zeilen, fünf Millionen gemeinsame Schritte) bleiben bestehen.

Reproduzierbar erzeugen und prüfen:

```powershell
python -m tools.export_barrel_shifter
python -m unittest discover -s tests -p test_barrel_shifter.py -v
```

## Einmalige Bibliotheksmigration

Beim nächsten Serverstart ergänzt `barrel-shifter-v1` drei Templates und
27 vollständig geprüfte Funktionen unter **Beispiele → Rekursion →
Barrel-Shifter**, dazu 27 wiederverwendbare F-Boxen unter den Bausteinen.
Bestehende Ordner, Beschreibungen, Benennungen, Zuordnungen und bessere
Schaltungen bleiben erhalten. Der Marker verhindert das erneute Anlegen
später gelöschter Funktionen, Templates oder F-Boxen. Tests prüfen auch den
API-Katalog, direkte Synthese, Bausteinauswertung und die Navigation in
eine feste Schiebestufe. Server neu starten und Browserseite neu laden.

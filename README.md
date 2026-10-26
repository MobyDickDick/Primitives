# Primitives
generate simple Programms

## Übersichtliche Webseiten und Hilfe

Neu: **Parametriertes Template definieren** unterstützt symbolische Portbreiten,
eigene Funktionen und Rekursion, etwa `def add<w>(a,b):` mit `add<n>(a,b)`.
Das Beispiel eines rekursiven Addierers ist direkt einsetzbar.
[Templates und Beispiele](docs/TEMPLATES.md) beschreiben Syntax, Grenzen und CLI.

Unter **Schaltbild → NAND-Schaltung bearbeiten oder importieren** lassen sich
auch die tatsächlichen Gatteranschlüsse und Ausgänge im JSON bearbeiten und
erneut prüfen. Entwürfe können als JSON exportiert oder als Bausteine gespeichert
werden. Die [Bewertung von Editor und Logisim-Anbindung](docs/EDITIEREN-LOGISIM.md)
erklärt, was bereits funktioniert und welche Import-/Export-Erweiterungen folgen
sollten. Für die neuen Funktionen den Server neu starten und die Seite neu laden.

Die Navigation teilt die Oberfläche in **Funktionen**, **Editor**, **Evolution**,
**Schaltbild**, **Bausteine** und **Hilfe**. Seitenwechsel erhalten die aktuellen
Eingaben, Handtests und laufenden Aufträge. Oben steht immer, welche Vektoren
geladen sind; diese werden für die nächste Suche verwendet. Änderungen im Editor
müssen zuerst gespeichert werden. Nach einem Neuladen eine gespeicherte Funktion
erneut öffnen.

Unter **Funktionen → Name & Beschreibung** lassen sich Funktionen umbenennen und
mit einem mehrzeiligen Beschreibungstext versehen. Die Angaben gelten für alle
Vektorsätze derselben Referenz und bleiben nach einem Serverneustart erhalten.
Kennungen, Sollwerte und vorhandene Schaltungen bleiben erhalten. Auch neue
Funktionen haben im Editor ein Beschreibungsfeld. Namen dürfen 120 Zeichen,
Beschreibungen 4000 Zeichen enthalten. Die JSON-Exporte enthalten den aktuellen
Namen und die Beschreibung in `metadata.description`.

Die integrierte **Hilfe** enthält Einstieg, Formeln und Programme, Bitbreiten,
Prüfstatus, Evolution, Schaltbildbedienung, Bausteine sowie Export und Import.
Sie ist über die Hauptnavigation und den Link am Seitenende erreichbar.
Für diese Erweiterung den laufenden Webserver neu starten und die Browserseite
neu laden.

## Geplante Erweiterungen

Die [Erweiterungs-Issues](docs/ERWEITERUNGEN.md) beschreiben Zoom, verschiebbare
Leitungen, TinyCPU-Operationsbeispiele, variable Bitbreiten, Unterprogramm-Boxen
mit Debugging sowie mehrschrittige Programme mit Kontrollstrukturen und Sprüngen.
Die acht Arbeitspakete enthalten Umfang, Abnahmekriterien und Abhängigkeiten.
PRIM-01 (Zoom und Navigation), PRIM-02 (verschiebbare Leitungen) und PRIM-03
(variable Bitbreiten für Vorlagen, eigene Aufgaben und bestehende Schaltungen)
sind ebenso wie PRIM-04 (TinyCPU-Operationsbeispiele), PRIM-05 (wiederverwendbare
Unterprogramm-Bausteine) und PRIM-06 (Unterprogramm-Boxen und interaktives
Debugging) sowie PRIM-07 (mehrschrittige Programme) umgesetzt.
PRIM-08 ergänzt Labels, bedingte/unbedingte Sprünge und einen Ablaufdebugger.

## Mehrschrittige Programme

**Mehrschrittiges Programm definieren** öffnet einen Editor für lokale Variablen,
Zuweisungen, `return`, verschachteltes `if/else`, `while` und `for … in range(…)`.
Zum Beispiel mit n[4] und c[8]:

```text
s = 0
for i in range(n):
    s += i
return s
```

Das entspricht `for (i=0; i<n; i++)` und berechnet die Summe von 0 bis n−1.
Die Oberfläche bietet dasselbe Beispiel mit while und eine Auswahl mit if/else.
Kommentare mit `#` sowie Bit-Arrays wie `[0, 1, 0]` oder `[0] * 4` sind erlaubt.
Mit `bits(n, 4)` werden Zahlen in Bits zerlegt, mit `a[i]` gelesen bzw.
`a[i] = 1` geändert und mit `pack(a)` wieder als Zahl ausgegeben.
Index 0 ist das niederwertigste Bit. Das Editorbeispiel **Bitreihenfolge umkehren**
beschreibt die Funktion kurz als `return pack(bits(n, 4)[::-1])`.
Jede Eingabe startet mit frischem lokalem Zustand. Budgets begrenzen Anweisungen,
Iterationen und die gesamte Erzeugung; **Vektorerzeugung abbrechen** stoppt den
Auftrag. Fehler und Abbruch speichern keinen neuen Datensatz. Quelle, Sprachversion,
Ports und Budgets bleiben beim Wiederöffnen und Export/Import erhalten.

Die erzeugten Sollvektoren können direkt für die kombinatorische NAND-Suche
verwendet werden. [PROGRAMME.md](docs/PROGRAMME.md) beschreibt Syntax,
Zahlensemantik, Grenzen sowie CLI/API. [Sechs vollständige Beispiele](examples/programs/)
enthalten auch die editierbaren Programmquellen.

Im Programmeditor öffnet **Programmablauf debuggen** einen Lauf für eine
Testeingabe: **Start**, **Eine Programmanweisung**, **Fortsetzen**, **Stoppen** und
**Zurücksetzen** zeigen Quellzeile, Programmzähler, Variablen und Ergebnis.
`label("ziel")`, `goto("ziel")` sowie `jump_if(bedingung, "ziel")` erlauben Sprünge;
`jump_zero`, `jump_nonzero` und `jump_negative` prüfen explizite Zahlenwerte.
Die Beispiele **Summe · Rücksprung** und **Auswahl · Zero-Sprung** sind direkt
wählbar. Budgets begrenzen auch Sprungschleifen. Einzelheiten und Blockgrenzen
stehen in [PROGRAMME.md](docs/PROGRAMME.md#labels-und-sprünge-prim-08).

## Verschachtelte Unterprogramm-Bausteine

Unter **Unterprogramm-Bausteine** können geöffnete Schaltungen mit ihren benannten
Ports als feste Version gespeichert werden. **Als Unterbaustein einsetzen** und
**Zweimal einsetzen** bereiten übergeordnete Definitionen im JSON-Editor vor.
Jeder Baustein darf weitere Unterbausteine enthalten. Die Portverbindungen lassen
sich bitweise bearbeiten; falsche Breiten, fehlende Abhängigkeiten und Zyklen
werden beim Prüfen vor dem Speichern abgelehnt.

Die Hierarchieliste zeigt alle Instanzen mit Namen, Versionen und Ports.
**Baustein öffnen** erzeugt Referenzvektoren und zeigt klickbare Unterprogramm-Boxen;
**Bausteinpaket exportieren** erhält sämtliche eingebetteten Abhängigkeiten.
Spätere bessere Suchergebnisse ändern bestehende Bausteine nicht.
Die Evolution verwendet mutierbare Expansionen und liefert flache Schaltungen.

[Drei importierbare Beispiele](examples/blocks/) demonstrieren Halbaddierer,
Volladdierer und einen Zweibit-Addierer mit mehreren Verschachtelungsebenen.
[BAUSTEINE.md](docs/BAUSTEINE.md) erklärt Editor, CLI/API, Verbindungen,
Versionsbindung und Grenzen.

Eine Unterprogramm-Box zeigt benannte Bitanschlüsse, Breiten und aktuelle Werte.
Anklicken oder Enter öffnet die interne Schaltung mit einem **lokalen Handtest**:
Eingänge als Bits oder Zahlen ändern und die Ausgänge unmittelbar prüfen.
**Test zurücksetzen**, **Nächstes NAND-Gatter** und **Vollständig auswerten**
machen die internen Signale nachvollziehbar. **Zur übergeordneten Schaltung**
stellt deren tatsächliche Eingangssignale, Gatterschritt, Zoom und Layout wieder her.
Lokale Handwerte ändern weder andere Instanzen noch gespeicherte Definitionen.
**Layout speichern** sichert Boxpositionen und Leitungswege je Instanzpfad.

## TinyCPU-Operationen und weitere Rechenbeispiele

**Vorlage** und **Operationsdefinition** bieten jetzt 26 parametrisierte
Operationen. Neu sind DIV mit `valid`/`div0`, IsZero, IsNonZero, IsNegative,
EQ/NE/LT/LE/GT/GE, SHL/SHR/SAR, INC/DEC und MUX. Schiebeweiten können
als fester Parameter oder über den unsigned Eingang b vorgegeben werden.
MUX erhält zusätzlich den Ein-Bit-Eingang `select`.

DIV rundet gegen null (−3/2 = −1); bei Nullteiler gilt c=0, valid=0, div0=1.
Die Oberfläche startet DIV, SAR und IsNegative mit Zweierkomplement.
Die [29 vollständigen kleinen Beispieltabellen](examples/operations/) sind
über den Vektorimport verwendbar. `python tools/seed_library.py` übernimmt sie
in die Funktionsbibliothek. Sie benötigen keine bereits gefundene NAND-Schaltung.

Der geprüfte TinyCPU-Commit, alle 50 Basisbefehle, drei optionale Systembefehle,
Zahlensemantik und bewusste Abweichungen sind in [TINYCPU.md](docs/TINYCPU.md)
dokumentiert. Die bestehenden CLI-Vorlagen behalten ihre Semantik.

## Arithmetische Funktionen selbst definieren

**Eigene Formel definieren** öffnet einen Formeleditor mit frei benannten
Ein- und Ausgängen. Für eine eigene Addition genügt `a + b`, mit beispielsweise
je 4 Bits für a und b und 5 Bits für c. Für eine getrennte Summe und einen
Übertrag eingeben:

```text
c = mod(a+b,2^4)
e = div(a+b,2^4)
```

Die Eingänge a und b erhalten je 4 Bits, c erhält 4 Bits und e erhält 1 Bit.
**Ergebnisports aus Formel übernehmen** legt die benannten Ergebnisse an;
neu hinzugekommene Ports beginnen mit 1 Bit und lassen sich frei verbreitern.
Beim Speichern werden die Ports ebenfalls aus der Formel übernommen.
Mit **Beispiel: Summe und Übertrag** werden Formel und alle vier Portbreiten
direkt eingesetzt. Ergebnisse dürfen auch mit Komma oder Semikolon getrennt werden.

Im Formelmodus bedeutet `^` Potenz; `div` rundet den Quotienten nach unten,
`mod` berechnet den zugehörigen Rest. Bitweises XOR wird `xor(a,b)` geschrieben.
Alle Ergebnisformeln lesen dieselben Eingänge unabhängig voneinander. Die Breiten,
Vorzeichen und Überlaufregeln werden pro Port eingestellt. Die bisherigen
Ausdrucksmodi verwenden weiterhin `^` für XOR und `**` für Potenz.

**Funktion speichern & Vektoren erzeugen** speichert die eigene Formel zusammen
mit den Ports und Vektoren unter **Definierte Funktionen**. Sie lässt sich dort
wieder öffnen, bearbeiten, exportieren und für eine Evolution verwenden.
**Rechenvorschrift selbst bearbeiten** öffnet eine ausgewählte Standardoperation
als frei bearbeitbare Formel. Es ist keine vorhandene NAND-Schaltung erforderlich.

## Bitbreiten bei jeder Schaltung ändern

Unter **Definierte Funktionen** stehen gespeicherte Funktionen nebeneinander,
auch solange noch keine NAND-Schaltung gesucht wurde. Beispielsweise sind
**ADD(1,1,2)**, **ADD(4,4,5)** und **ADD(8,8,9)** drei eigenständige Funktionen.
Eine Operation wählen, die drei Breiten einstellen und **Funktion speichern &
Vektoren erzeugen** klicken. Der Name folgt automatisch den Breiten; er kann
auch von Hand geändert werden. **Funktion öffnen** lädt eine gespeicherte
Definition samt zugehörigen Vektoren wieder in den Editor und für die Evolution.
Auch **ADD(1,1,16)** ist erlaubt; die Zweckmässigkeit der gewählten Breiten
bleibt beim Nutzer. Es gelten nur die technischen Limits von je 32 Gesamtbits
für Eingänge bzw. Ausgänge.

Mehrere Vektorsätze derselben Funktion (etwa unterschiedliche Stichproben)
stehen in deren Auswahlfeld. Die Funktionsidentität hängt von der Referenz und
ihren Parametern ab; Seed und Vektoranzahl erzeugen keine weitere Funktion.
Vorzeichen, Überlaufregel und zusätzlicher Statusausgang unterscheiden dagegen
Definitionen auch bei gleichen Breiten. Grössere Funktionen sind ebenso
definiert, wenn für die Suche zunächst nur eine Stichprobe gespeichert wird.

Zum Aufräumen unter **Definierte Funktionen** auf **Funktion löschen** klicken.
Nach Bestätigung werden alle Vektorsätze dieser Funktion und ihre ausschliesslich
zugehörigen Schaltungen einschliesslich älterer Versionen dauerhaft entfernt.
Gemeinsam mit anderen Funktionen verwendete Schaltungen bleiben diesen zugeordnet;
separat gespeicherte Unterprogramm-Bausteine bleiben erhalten. Die Hintergrundsuche
wird während des Löschens gestoppt. Einen laufenden manuellen Auftrag vorher
abwarten oder abbrechen. Eine gerade gelöschte Funktion wird auch aus der
geöffneten Vektor-/Schaltungsansicht entfernt.

Eine Schaltung öffnen und **Neue Breitenvariante** wählen. Bei bekannten
Operationen erscheint deren parametrisierte Referenz, bei eigenen Ausdrücken
eine bearbeitbare Schnittstelle. Eine Schaltung ohne Rechenreferenz kann als
bitweise NAND-Referenz mit breiteren Anschlüssen verwendet werden. Anschliessend
die Breiten anpassen, **Funktion speichern & Vektoren erzeugen** und **Evolution starten** wählen.
Die neue Aufgabenvariante benötigt eine passende NAND-Implementierung; die bisherige
Verdrahtung wird durch die Breitenwahl nicht automatisch zu einem breiteren Addierer.

Unter **Aufgabendefinition** stehen auch unabhängig von einer vorhandenen Schaltung
**Operation mit variablen Bitbreiten** und **Eigene benannte Ein-/Ausgänge** bereit.
ADD, SUB, MUL und die vorhandenen elementaren Logikoperationen sind parametrisiert.
Eigene Schnittstellen erlauben zusätzliche Operanden und mehrere Ergebnisse,
jeweils mit Namen, Breite, Vorzeichen und einem eigenen Ergebnis-Ausdruck.
Eingangsbits N und Ausgangsbits M werden aus den Portbreiten berechnet.

Zahlen sind wahlweise unsigned oder als Zweierkomplement kodiert. **Abschneiden**
speichert das Ergebnis modulo 2^Ergebnisbreite; **Als Fehler ablehnen** bricht die
Vektorerzeugung beim ersten nicht darstellbaren Wert ab. ADD/SUB/MUL können ein
zusätzliches Statusbit ausgeben: Carry bei unsigned ADD, Borrow bei unsigned SUB,
sonst Overflow. Carry/Overflow zeigen ein Ergebnis ausserhalb des gewählten
Bereichs an; Borrow bedeutet `a < b`. Auch mit Statusbit bleibt die gewählte
Überlaufregel wirksam. Die vollständige Semantik steht in [FORMAT.md](docs/FORMAT.md).

**Vektoren exportieren** erhält Portnamen, Bitzuordnung und Referenzmetadaten;
der JSON-Programmexport enthält zusätzlich den zugehörigen Datensatz. Über
**Eigene Vektoren importieren** lassen sich beide Formen als Aufgaben laden.
Vollständige Tabellen und Stichproben bleiben klar unterschieden. Pro Seite sind
insgesamt höchstens 32 Bits und pro Datensatz höchstens 65536 Vektoren erlaubt.
Es werden nur angeforderte Varianten erzeugt.

CLI-Beispiel für unterschiedliche Operandenbreiten und einen Carry-Ausgang:

```powershell
python -m primitives generate --operation ADD --a-bits 2 --b-bits 3 --result-bits 4 --flag --out examples/add-2-3-4.json
```

Mit `--signed` gilt Zweierkomplement, mit `--overflow error` werden Überläufe
abgelehnt. Eigene Schnittstellen werden über `--interface ports.json`, mehrere
Ergebnisausdrücke über `--expressions expressions.json` geladen. Die Summen müssen
zu `--inputs` und `--outputs` passen. `--reference-circuit circuit.json` erlaubt
statt Ausdrücken eine vorhandene NAND-Schaltung als bitweise Referenz.
Vorhandene `--preset`-Aufrufe behalten ihre bisherige Semantik.

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

## Elternpopulation und Turnierselektion

Beide Suchbackends verwenden eine bewertete **Elternpopulation** (Standard 24,
einstellbar von 2 bis 256). Zwei unabhängige Turniere wählen die Eltern für
Mutation und Rekombination: jeweils die beste von drei zufälligen Ziehungen,
bei Population 2 von zwei Ziehungen. Ein mindestens gleich guter Nachkomme
ersetzt ein zufällig gewähltes schlechtestes Mitglied. Das beste gefundene
Ergebnis bleibt erhalten.

Pro Runde werden höchstens so viele Nachkommen wie Eltern bewertet.
Initialisierung und Nachkommen teilen sich das Kandidatenbudget
`min(500000, 1 + Elternzahl × Generationen)`. Fehlerfreiheit beendet einen
manuellen Lauf auch während der Initialisierung; die Hintergrundsuche kann
weiter optimieren. Mit gleichem Backend, Seed und denselben Startbedingungen
bleibt ein Lauf ohne Zeitlimit reproduzierbar. CLI: `--population 24`.

## Unabhängige Starts, Inseln und Diversität

Unter **Evolution** lassen sich **Unabhängige Starts** (1–32), **Inseln** (1–16)
und der Abstand des Austauschs einstellen. Ein Start und eine Insel bleiben der
Standard. Alle Starts teilen das bestehende Kandidatenbudget einschliesslich
ihrer Initialisierungen. Beispielsweise verteilen sich 64 Bewertungen auf drei
Starts als 21/21/22. Das Budget muss für die Elternpopulation jedes Starts reichen.

Die Elternpopulation wird auf die Inseln verteilt, mit mindestens zwei Eltern
je Insel. Mutation, Rekombination und Selektion bleiben innerhalb einer Insel.
Beim Austausch wandert je das beste Programm zur nächsten Insel im Ring und darf
dort ein mindestens gleich schlechtes Mitglied ersetzen. Der Standardabstand
beträgt zehn Generationen. Ein neuer Start verwendet frische Populationen und
den nächsten Seed; nur der erste kann mit der bisherigen Lösung beginnen.
Das beste Gesamtergebnis bleibt erhalten. Fehlerfreiheit beendet manuelle Läufe
auch vor weiteren Starts. Eine Garantie für ein besseres Ergebnis besteht nicht.

Die Suchzusammenfassung zeigt ausgeführte Starts, Inselzahl und die Diversität
der letzten Population: den Anteil unterschiedlicher Genome und ihre mittlere
Gendifferenz. Auch unbenutzte Gene zählen mit; Vielfalt bedeutet deshalb nicht
automatisch unterschiedliches Verhalten. JSON-Exporte enthalten zusätzlich Seeds,
Bewertungen, besten Rang, Migrationen und Anfangs-/Enddiversität je Start und Insel.
Bei gleichem Backend, Seed und denselben Startbedingungen bleibt die Suche ohne
Zeitlimit reproduzierbar. [ARCHITEKTUR.md](docs/ARCHITEKTUR.md#unabhängige-starts-und-inseln)
beschreibt Budgetaufteilung und Kennzahlen genau.

```powershell
python -m primitives evolve --preset xor --backend python --gates 8 --population 24 --generations 200 --restarts 3 --islands 4 --migration-interval 10
```

Dieselben Parameter funktionieren mit `--backend tiny` und in der JSON-API als
`restarts`, `islands` und `migration_interval`.

## Neutrale Evolution und getrennte Vereinfachung

Unter **Evolution** aktiviert **Neutral entwickeln, danach vereinfachen** zwei
getrennte Phasen, sowohl mit TinyLanguage als auch mit Python:

1. Die Evolution bewertet ausschliesslich die Zahl falscher Ausgangsbits.
   Gleich gute Nachkommen dürfen mehr aktive Gatter oder eine grössere Tiefe
   besitzen und trotzdem Eltern ersetzen. Das beste bisherige Ergebnis bleibt
   separat erhalten; bei gleicher Fehlerzahl bleibt der erste Treffer gesichert.
2. Anschliessend führt eine deterministische Vereinfachung gleiche NAND-Gatter
   zusammen, auch mit vertauschten Eingängen, überbrückt doppelte Negationen
   und entfernt dadurch unbenutzte Gatter. Beispielsweise werden drei NANDs
   für NAND → NOT → NOT zu einem NAND. Diese Identitäten erhalten die Funktion
   für **alle** Eingaben, auch ausserhalb einer Trainingsstichprobe.

Der Modus ist standardmässig ausgeschaltet. Ohne ihn bewertet die Suche weiter
Fehler, Gatterzahl und Tiefe gemeinsam. Kandidatenbudget, Starts, Inseln und Ende
beim ersten fehlerfreien Treffer bleiben gleich. Die nachgelagerte Vereinfachung
benötigt keine zusätzlichen Kandidatenbewertungen und läuft auch nach einem
ausgeschöpften Suchbudget. Sie ist abbrechbar und beansprucht keine Minimalität.
Der Prüfstatus gegenüber der Referenz bleibt unverändert: Eine Stichprobe wird
durch die Vereinfachung nicht zu einer vollständig geprüften Wahrheitstabelle.

Die Suchzusammenfassung zeigt beide Phasen mit Gatterzahl und Tiefe vor/nach der
Vereinfachung. Im JSON-Export stehen `search.objective` und `search.phases` mit
Bewertungszahlen und Ergebnissen. Der Suchverlauf beschreibt nur die Evolution;
eine gewählte Restfallkorrektur erfolgt danach und kann weitere Gatter ergänzen.

```powershell
python -m primitives evolve --preset xor --backend tiny --gates 8 --neutral
```

In der JSON-API wird `config.neutral` auf `true` gesetzt.

## Tatsächliche Abstammung der Suchergebnisse

Python und TinyLanguage speichern für neue Suchergebnisse die tatsächlichen
Vorfahren des besten Suchkandidaten. Unter **Schaltbild → Abstammung des
Suchergebnisses** stehen Kandidatenkennungen, Eltern, Mutationsstellen und die
konkret eingesetzten Bibliotheksprogramme oder Bausteinversionen. Die Tabelle
zeigt höchstens die jüngsten 100 Kandidaten; der **JSON-Programmexport** enthält
die gesamte Abstammung dieses Gewinners unter `search.ancestry`.

Auch genetisch identische Kandidaten erhalten eigene Kennungen. Rekombination
speichert beide gewählten Eltern und die übernommenen Genpositionen, Mutation
die betroffenen Stellen und tatsächlichen Genänderungen. Inselwechsel behalten
die Kandidatenkennung. Zufallsstarts beginnen eigene Linien. Quellen werden
mit ihren konkret verwendeten NAND-Schaltungen und Anschlusszuordnungen gesichert,
sodass der Export ohne die ursprünglichen Bibliotheksdateien lesbar bleibt.

Kompaktierung, neutrale Vereinfachung, eine Auswahl der bisherigen Lösung vor
der Korrektur und Restfallkorrekturen erscheinen als nachfolgende Schritte.
Ein abgelehnter Retest behält die Abstammung des bisherigen Bibliotheksgewinners.
Alte Programme erhalten keine nachträglich erfundene Abstammung; eine neue Suche
kann sie als benannte Ausgangsquelle erfassen. Die Aufzeichnung endet an den
Quellen dieses Laufs und behauptet keinen unveränderten Erhalt der Bausteine.
Unbeteiligte und verworfene Kandidaten werden nicht im Ergebnis exportiert.

[FORMAT.md](docs/FORMAT.md#kandidatenabstammung) beschreibt das Format und die
Rekonstruktion. Die vorhandenen Listen `seed_library` und `seed_blocks` nennen
weiterhin das Quellenangebot beim Start, unabhängig von tatsächlicher Verwendung.

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

Auch Leitungen lassen sich bearbeiten: Ein waagrechtes Segment nach oben/unten,
ein senkrechtes nach links/rechts ziehen. Bei einer geraden Leitung entstehen
dabei zusätzliche Knicke. Die kurzen Anschlussstücke bleiben an den Boxen fest.
Die breite unsichtbare Trefferfläche funktioniert auch beim Zoomen. Tab wählt
Leitungssegmente; die Pfeiltasten verschieben sie um 10, mit Shift um 40 Einheiten.
Die beiden NAND-Eingänge bleiben auch bei gleicher Quelle getrennt bearbeitbar.

Wege durch Boxen werden abgelehnt; der letzte gültige Weg bleibt erhalten.
Beim Boxverschieben bleiben die inneren Stützpunkte an ihrem Ort und die
Anschlussstücke werden angepasst. Ist der manuelle Weg dadurch blockiert,
erscheint die Leitung orange gestrichelt und wird vorübergehend automatisch
geführt. Die manuellen Stützpunkte bleiben erhalten und werden wieder verwendet,
sobald der Weg frei ist. **Leitung zurücksetzen** oder Entf am gewählten Segment
entfernt nur dessen manuellen Leitungsweg. **Automatisch anordnen** setzt alle
Boxen und manuellen Leitungswege zurück. Rücksetzungen mit **Layout speichern**
sichern, wenn sie nach erneutem Öffnen gelten sollen.

**Layout speichern** sichert Boxpositionen und manuelle Leitungswege pro Schaltung im Datenverzeichnis
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

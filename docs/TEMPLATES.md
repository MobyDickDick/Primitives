# Parametrierte Funktionen und rekursive Templates

Im Editor **Parametriertes Template definieren** wählen. Das Beispiel ist ein
rekursiver Addierer. Parameter stehen als JSON im eigenen Feld, zunächst
`{"n": 4}` für eine konkrete Verwendung `add<4>(a,b)`. Die Eingänge a und b haben die Breite `n`, Ergebnis c die Breite
`n+1`. Breitenfelder dürfen feste Zahlen oder Ausdrücke enthalten.

**Abstraktes Template speichern** sichert nur Parameternamen, Quelltext,
symbolische Schnittstelle, Budgets und Bedingungen unter **Funktionen →
Abstrakte Templates**. Es werden keine Parameterwerte, keine konkrete Funktion
und keine Vektoren gespeichert. Das Template lässt sich separat exportieren
und importieren. **Template öffnen & konkretisieren** lädt es in den Editor;
dort z. B. `{"n": 8}` setzen. Die Vorschau zeigt `add<8>(a,b)`.

**Konkretisierung & Breiten prüfen** berechnet die konkrete Schnittstelle.
**Programm speichern & Vektoren erzeugen** prüft nochmals und erzeugt die
angeforderte vollständige Tabelle oder Stichprobe. Danach kann die Evolution
eine passende NAND-Schaltung suchen. Beim erneuten Öffnen bleiben Quelltext,
Parameter, symbolische Breiten und Budgets editierbar. Ein Parameterwechsel
speichert eine weitere konkrete Funktion; Stichproben und Budgets gehören
nicht zur Identität der Funktion.

## Schreibweise mit spitzen Klammern

```text
def obereHaelfte<k>(a):
    return a // (2 ** k)

def untereHaelfte<k>(a):
    return a % (2 ** k)

def add<w>(a, b):
    assert w > 0 and (w & (w - 1)) == 0
    assert 0 <= a < 2 ** w and 0 <= b < 2 ** w
    if w == 1:
        return 2 * (a & b) + xor(a, b)
    k = w // 2
    a1 = obereHaelfte<k>(a)
    a2 = untereHaelfte<k>(a)
    b1 = obereHaelfte<k>(b)
    b2 = untereHaelfte<k>(b)
    c0 = add<w-k>(a1, b1)
    c1 = c0 + 1
    d0 = add<k>(a2, b2)
    rest = d0 % (2 ** k)
    carry = d0 // (2 ** k)
    if carry == 0:
        return c0 * (2 ** k) + rest
    else:
        return c1 * (2 ** k) + rest

return add<n>(a, b)
```

`n` bezeichnet hier die gesamte Operandenbreite. Beim ursprünglichen Fall
`add<2*n>` sind beide Hälften genau n Bits breit. Das gespeicherte Beispiel
verlangt Zweierpotenzen, damit alle rekursiven Hälften gleich gross sind.
Der Basisfall hat ein Bit, also `w == 1`. Für w Bits gilt
`0 <= a,b < 2**w`; die vollständige Summe braucht w+1 Bits.

Gegenüber der ursprünglichen Skizze wurden `c10` durch `c0`, die Addition
der unteren Hälften durch `add<k>(a2,b2)` und die doppelte Variable `d1`
durch `rest` und `carry` ersetzt. Im Basisfall muss das Summenbit XOR sein:
`1+1 = 2*(1&1) + xor(1,1) = 2`. OR würde fälschlich 3 ergeben.

Die zweite, bedingt gewählte obere Summe ist `c0+1`. Auch dafür könnte ein
weiteres Template aufgerufen werden; hier bleibt die Formulierung kurz.

## Bedingungen der abstrakten Parameter

Im Bedingungsfeld steht eine Bedingung pro Zeile, im Beispiel:

```text
n >= 1
is_power_of_two(n)
```

`is_power_of_two(n)` bedeutet exakt: Es existiert ein ganzzahliges m ≥ 0 mit
**n = 2^m**. Die Schreibweise n = 2^n in der ursprünglichen Nachricht ist als
Vertipper interpretiert. Zulässige Addiererbreiten sind damit 1, 2, 4, 8, 16.
`n=6` wird vor der Vektorerzeugung mit der nicht erfüllten Bedingung abgelehnt.
Die Bedingungen bleiben beim Speichern, Export/Import und erneuten Öffnen
erhalten und werden auch bei API-/CLI-Konkretisierung und Debugstart geprüft.

Bedingungen dürfen Parameter, ganze Zahlen, `+ - * // % ** & | ^`, Vergleiche,
`and`, `or`, `not` und `is_power_of_two` verwenden. Alle Bedingungen müssen
erfüllt sein. Ein explizites m als zweiter Parameter wäre ebenfalls möglich,
etwa mit `n == 2**m`; die Hilfsfunktion erspart diesen zusätzlichen Wert.

Zusätzlich legt `assert` in Version 2 eine Bedingung direkt am Funktionsaufruf
fest. Die Assertion im Beispiel schützt deshalb auch direkte Aufrufe mit
Literalen wie `add<6>(a,b)`, unabhängig von globalen Parameterwerten. Sie wird
bei jedem Aufruf vor der Addition ausgewertet und zählt zum Ausführungsbudget.
Frei formulierte Meldungen nach `assert` sind nicht Teil dieser Sprachversion.

## Funktionen und Grenzen

- Sprachversion 2 ergänzt die bisherigen Programme um `parameters`, eine
  symbolische `interface` und bis zu 16 eigene Funktionen auf oberster Ebene.
- Deklaration `def f<k>(a):`, Aufruf `f<n>(a)`. Mehrere Parameter sind erlaubt:
  `def f<k,q>(a):` und `f<n,2>(a)`. Die Schreibweisen `def f(k,a):`,
  `f(n,a)` und `f(n)(a)` bleiben gleichwertig. Die Klammergruppen sind
  Syntax für führende Ganzzahlargumente, keine erstklassigen Funktionswerte.
- Eigene Funktionen liefern jeweils eine ganze Zahl. Das Hauptprogramm kann
  weiterhin einen Wert je Ergebnisport zurückgeben. Argumente und globale
  Template-Parameter sind schreibgeschützt. Lokale Variablen sind je Aufruf
  getrennt; andere Eingangsports müssen ausdrücklich als Argumente übergeben
  werden. Gegenseitige und direkte Rekursion sind erlaubt.
- Bis zu 16 feste Parameter mit ganzzahligen Werten 0–32. Breitenausdrücke
  erlauben Parameter, Zahlen und `+ - * // % **`; Potenzexponenten 0–16.
  Ports brauchen je 1–32 Bits, die Summen je Seite dürfen 32 nicht überschreiten.
  Für den Addierer gilt deshalb `1 <= n <= 16`.
- Höchstens 32 verschachtelte Funktionsaufrufe. Alle Aufrufe teilen die
  Schritt-, Iterations- und Gesamtbudgets; sie werden bei Rekursion nicht
  zurückgesetzt. Abbruch gilt für den gesamten Erzeugungsauftrag.
- Der Ablaufdebugger behandelt einen Funktionsaufruf samt Unteraufrufen als
  Teil der aktuellen Hauptprogrammanweisung. Deren gesamte Arbeit zählt zum
  angezeigten Budget. Ein Einzelschritt innerhalb der Aufrufkette ist noch
  nicht implementiert.
- Die normale Auswertung erzeugt Referenzvektoren. Zusätzlich kann die unten
  beschriebene Bit-Teilmenge direkt in ein flaches NAND-Netz übersetzt werden.
  Eine strukturell rekursive NAND-Hierarchie wird dabei nicht erzeugt.
  Parameter, die selbst Funktionen/Templates sind,
  und automatische Imports fremder Template-Bibliotheken sind noch offen.

Spitze Klammern werden vor der AST-Prüfung in normale Aufrufe umgeschrieben.
Kommentare und gewöhnliche Vergleiche bleiben erhalten; Quellzeilen und
Spaltenpositionen ändern sich nicht. Es wird kein `eval` oder `exec` verwendet.
Sprachversion 1 behält ihre bisherige Syntax.

## Beispiele und CLI

[recursive-adder.abstract.json](../examples/templates/recursive-adder.abstract.json)
enthält die abstrakte, unter **Abstrakte Templates** importierbare Definition.
[recursive-adder.prim](../examples/templates/recursive-adder.prim) enthält die
editierbare Quelle, [recursive-adder.template.json](../examples/templates/recursive-adder.template.json)
die vollständige Template-Definition. Die Datei
[recursive-adder-n4.json](../examples/templates/recursive-adder-n4.json) enthält
alle 256 Vektoren für n=4 samt Template und lässt sich im Vektorimport öffnen.

```powershell
python -m primitives generate --template-file examples/templates/recursive-adder.template.json --samples 256 --out .jobs/add-template.json
python -m primitives generate --template-file examples/templates/recursive-adder.abstract.json --parameters '{"n":8}' --samples 256 --out .jobs/add-8.json
```

Die CLI berechnet N und M aus dem Template. Die vorhandenen Budgetargumente
`--program-steps`, `--program-iterations` und `--program-total-steps` gelten
auch hier. Parameter im JSON bearbeiten, um eine weitere Variante anzufordern.

API: `POST /api/templates` speichert ein abstraktes Template; `GET /api/templates/{id}`
lädt dessen portable Definition. `POST /api/templates/specialize` mit
`{"template_id":"…", "parameters":{"n":8}}` konkretisiert es. Die bisherige
Form mit `{"program": {...}}` akzeptiert eine bereits konkrete Definition und liefert
normalisierte Programmdefinition, konkrete `interface`, `inputs` und `outputs`.
Diese Felder können zusammen mit Name und Stichprobenparametern an
`POST /api/datasets/generate` übergeben werden. Das normale Dataset-JSON
enthält in `metadata.interface` die konkreten Ports und in
`metadata.program.interface` die unveränderten symbolischen Breiten.

## Bibliothek als Verzeichnisbaum

Die Seite **Bibliothek** enthält einen gemeinsamen, aufklappbaren Baum für
Templates und konkrete Funktionen. Jeder Ordner hat einen editierbaren Namen
und eine mehrzeilige Beschreibung. **Ordner anlegen**, **Unterordner anlegen**
und **Ordner bearbeiten** erlauben auch das Verschieben ganzer Teilbäume.
Einträge haben die Aktion **In Ordner verschieben**. Nur leere, selbst angelegte
Ordner können gelöscht werden. Die Standardordner Funktionen und Templates
nehmen neue Einträge auf und bleiben erhalten.

Die Ordnung liegt in `data/folders.json`; die inhaltsadressierten Template-,
Vektor- und Schaltungsdateien behalten ihre Kennungen und Speicherorte.
Verschieben oder Umbenennen ändert keine Referenzvektoren und trennt keine
vorhandenen Implementierungen ab. Alle Vektorsätze einer Funktion bleiben
zusammen. Die Suche zeigt passende Einträge samt ihren übergeordneten Ordnern.
Ein Treffer im Ordnernamen zeigt auch dessen gesamten Inhalt; eine Erwähnung
in der Ordnerbeschreibung macht fremde Einträge nicht zu Treffern.

Der Server installiert die mitgelieferten Beispiele einmalig:

```text
Bibliothek
├── Beispiele
│   ├── Grundrechenarten
│   │   ├── Templates
│   │   │   ├── Addition<n>
│   │   │   ├── Subtraktion<n>
│   │   │   ├── Multiplikation<n>
│   │   │   └── Division<n>
│   │   └── Funktionen (4 Bit)
│   │       └── Je eine Instanz mit 256 Vektoren und NAND-Schaltung
│   └── Rekursion
│       └── Rekursiver Addierer<n>
├── Funktionen
└── Templates
```

`data/example-installations.json` merkt sich die Installation. Neustarts
überschreiben keine Ordnerbeschreibungen oder Zuordnungen und stellen gelöschte
Beispiele nicht wieder her. Für isolierte Tests lässt sich die Installation
mit `make_server(..., seed_examples=False)` abschalten.

API: `POST /api/library/folders` mit `name`, `description`, `parent` (Kennung oder
`null`) legt einen Ordner an; mit zusätzlichem `id` wird er bearbeitet.
`POST /api/library/move` nimmt `kind` (`template` oder `function`), `id` und
`folder` entgegen. Funktionen werden über ihre `function_id` zugeordnet.
`POST /api/library/folders/delete` mit `id` löscht einen leeren Ordner.
Der Katalog enthält unter `tree` die Ordner und effektiven Eintragszuordnungen.

## Vier konventionelle Rechen-Templates

Alle vier Beispiele verwenden unsigned Eingänge `a[n]`, `b[n]` und benötigen
keine Zweierpotenz für n. Die Quellen liegen als `.prim` und abstraktes JSON in
`examples/templates/` und sind im Editor vollständig editierbar.

| Template | Verfahren | Ergebnisse | Parameterbereich der Referenz |
| --- | --- | --- | --- |
| `ripple-add` | Ripple-Carry, eine Volladdierstufe je Bit | `c[n+1] = a+b` | 1–16 |
| `ripple-sub` | Ripple-Borrow, eine Subtrahierstufe je Bit | `c[n] = (a-b) mod 2^n`, `borrow[1] = (a<b)` | 1–16 |
| `shift-add-mul` | AND-Teilprodukte mit versetzten Volladdierstufen | vollständiges Produkt `c[2*n]` | 1–16 |
| `restoring-div` | Schriftliche Binärdivision, n feste Subtraktions-/Mux-Stufen | `c[n]`, `rest[n]`, `valid[1]`, `div0[1]` | 1–15 |

Bei der Division durch null sind Quotient und Rest null, `valid=0`, `div0=1`.
Sonst gilt `a = b*c + rest`, `0 <= rest < b`, `valid=1`, `div0=0`.
Die Subtraktion gibt bewusst ein modulares Ergebnis plus Borrow zurück;
negative Differenzen werden damit ohne Zweierkomplement-Port dargestellt.

## Direkte strukturelle NAND-Synthese

**Direkt in NAND übersetzen & speichern** konkretisiert das Template und
übersetzt seinen tatsächlichen Quelltext. Es werden keine speziellen
Rechenoperationen anhand des Template-Namens erkannt und keine Wahrheitstabellen
zur Konstruktion der Schaltung verwendet. Anschliessend prüft die Anwendung
das Netz gegen die angeforderten Referenzvektoren und speichert es über dieselbe
Bestenauswahl wie evolutionäre Ergebnisse. Eine vorhandene bessere Schaltung
kann deshalb beim Speichern gewinnen.

Unterstützt werden unsigned Ports, feste Parameterarithmetik, Zuweisungen,
Bit-Arrays bis 128 Bits, konstante Indizes und Slices, `bits`, `pack`, `len`,
eigene Funktionen sowie feste Schleifen und Bedingungen. Inputabhängige Arbeit
wird durch einzelne `&`, `|`, `^` und `1 ^ bit` ausgedrückt. `bits` und `pack`
sind Verdrahtung; AND, OR und XOR werden aus NANDs aufgebaut. Wiederholte
NANDs werden geteilt, konstante Bitoperationen vereinfacht und unbenutzte Gatter
entfernt. Konstante Ausgänge benötigen keine zusätzlichen Eingänge.

Schleifenbedingungen, Verzweigungen, Arrayindizes und Ganzzahlarithmetik müssen
allein von festen Parametern und lokalen konstanten Werten abhängen. Ein
inputabhängiges `if a < b` oder `return a + b` wird mit einer Quellzeilenmeldung
abgelehnt; die neuen Beispiele schreiben Auswahl und Rechnen explizit als
Bitoperationen. Der ältere rekursive Addierer verwendet Ganzzahladdition auf
Eingangswerten und bleibt ein Beispiel für Referenzvektoren und Evolution.
Aufruf-, Schritt- und Iterationsbudgets gelten auch beim Übersetzen.

Die bestehende Schaltungsgrenze von **512 NAND-Gattern** gilt auch hier.
Der Referenz-Parameterbereich kann deshalb grösser als der direkt übersetzbare
Bereich sein; insbesondere wachsen Multiplikation und Division quadratisch.
Bei Überschreitung wird nichts gespeichert. Die 4-Bit-Beispiele brauchen
32 (Addition), 46 (Subtraktion), 124 (Multiplikation) und 240 (Division) Gatter.
Das ist eine konventionelle Konstruktion mit lokalen Vereinfachungen, kein
Nachweis minimaler Gatterzahl. Ein Stichprobentest bleibt als Stichprobe
gekennzeichnet; vollständige Verifikation wird nur bei vollständiger Tabelle
angezeigt. Für 1, 2, 3 und 4 Bits werden in den Tests alle Eingabepaare gegen
unabhängige Ganzzahlarithmetik geprüft, inklusive Borrow und Division durch null.

API: `POST /api/templates/synthesize` mit `template_id` und `parameters` oder
mit einer konkreten `program`-Definition; optional `name`, `description`,
`samples` (Standard 256), `seed`. Die Antwort enthält `id`, `dataset` und das
gespeicherte `result`. `synthesis.method = "structural-bitwise"` kennzeichnet
eine direkte Übersetzung ohne Suchverlauf.

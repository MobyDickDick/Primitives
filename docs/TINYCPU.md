# TinyCPU-Operationen (PRIM-04)

Geprüfter Stand am 25. Oktober 2026: TinyCPU-Commit
[`9d60c94189a997f661259156b138b7dac5c6d007`](https://github.com/MobyDickDick/TinyCPU/tree/9d60c94189a997f661259156b138b7dac5c6d007).
Die verwendeten Dateien der lokalen Kopie stimmen mit diesem Commit überein.
Quellen: [Maschinenformat](https://github.com/MobyDickDick/TinyCPU/blob/9d60c94189a997f661259156b138b7dac5c6d007/hardware/logisim/tinycpu-machine-v1.json),
[Referenzinterpreter](https://github.com/MobyDickDick/TinyCPU/blob/9d60c94189a997f661259156b138b7dac5c6d007/src/tiny_cpu_vm.py),
[Basisprofil](https://github.com/MobyDickDick/TinyCPU/blob/9d60c94189a997f661259156b138b7dac5c6d007/src/tiny_cpu_profiles.py)
und [optionales Systemformat](https://github.com/MobyDickDick/TinyCPU/blob/9d60c94189a997f661259156b138b7dac5c6d007/hardware/logisim/tinycpu-system-machine-v1.json).

## Auswählbare Beispiele

**Vorlage** und **Operationsdefinition** bieten 26 parametrisierte Referenzen:
ADD, SUB, MUL, DIV, NOT, NAND, AND, OR, XOR, NOR, XNOR,
IsZero, IsNonZero, IsNegative, EQ, NE, LT, LE, GT, GE, SHL, SHR, SAR, INC, DEC und MUX.
Die bisherigen mathematischen Vorlagen bleiben zusätzlich verfügbar.
Die 29 kleinen, vollständigen Tabellen in [`examples/operations/`](../examples/operations/)
lassen sich als JSON importieren. SHL/SHR/SAR haben je eine Variante mit Eingang b
und eine Variante mit festem n=1. DIV, SAR und IsNegative sind dort signed;
die Oberfläche wählt für diese Beispiele ebenfalls zunächst signed.
Die API verwendet ohne expliziten Parameter weiterhin unsigned.

Alle Beispiele funktionieren ohne bereits gefundene Schaltung. Eine Referenz
legt die Sollwerte fest; eine NAND-Implementierung wird separat gesucht und geprüft.
Die vorhandenen acht archivierten NAND-Beispiele bleiben erhalten und werden
weiter gegen ihre vollständigen Tabellen geprüft. Die neuen Tabellen behaupten
keine zusätzlichen fertigen Schaltungen.

```powershell
python -m primitives generate --operation DIV --a-bits 3 --b-bits 3 --result-bits 3 --signed --out examples/my-div.json
python -m primitives generate --operation SHL --a-bits 4 --result-bits 4 --shift 2 --out examples/my-shl.json
python -m primitives generate --operation SHR --a-bits 4 --b-bits 3 --result-bits 4 --out examples/my-shr.json
python tools/export_operations.py
python tools/seed_library.py
```

Der Exportgenerator erzeugt ausschliesslich die kleinen Standardbeispiele.
`seed_library.py` übernimmt sie als definierte Funktionen zusammen mit den
bisherigen archivierten Beispielen; identische Tabellen werden nicht dupliziert.
Andere Breiten werden erst auf Anforderung erzeugt. Insgesamt gelten weiterhin
32 Eingangsbits, 32 Ausgangsbits und höchstens 65536 Zeilen pro Datensatz.

## Zahlensemantik

Ports stehen LSB-first in der Reihenfolge a, b, gegebenenfalls select; Ausgänge
beginnen mit c. signed bedeutet Zweierkomplement. Unterschiedliche Breiten
werden pro Operand dekodiert. Abschneiden kodiert das Ergebnis modulo 2^c_bits,
Fehlerüberlauf lehnt die Vektorerzeugung mit Eingabe und Ergebnisport ab.

| Operation | Referenz und Sonderfälle |
|---|---|
| ADD, SUB, MUL | Mathematische Ganzzahlarithmetik; optional Carry/Borrow/Overflow wie bisher. |
| DIV | Ganzzahldivision mit Rundung gegen null, z. B. −3/2 = −1. Exakte Integer-Arithmetik ohne Gleitkomma. Immer zusätzliche unsigned Ein-Bit-Ausgänge `valid`, `div0`. Bei b=0: c=0, valid=0, div0=1; sonst valid=1, div0=0. |
| NOT, NAND, NOR, XNOR | Inversion auf c-Breite; signed interpretiert dieses Wort im Zweierkomplement. |
| AND, OR, XOR | Bitweise auf den dekodierten Operanden; negative Werte sind vorzeichenerweitert. |
| IsZero, IsNonZero, IsNegative | c ist genau ein unsigned Wahrheitsbit. IsNegative testet den Zahlenwert; unsigned liefert stets 0. |
| EQ, NE, LT, LE, GT, GE | Zahlenvergleich der unabhängig dekodierten Operanden; c ist ein unsigned Wahrheitsbit. |
| SHL | Im a-Wort nach links, hohe Bits entfallen. n=0 erhält das Wort, n≥a_bits ergibt 0. Anschliessend Kodierung auf c-Breite. |
| SHR | Im a-Wort logisch rechts mit Nullauffüllung. n=0 erhält das Wort, n≥a_bits ergibt 0. |
| SAR | Bitmuster von a als Zweierkomplement rechts mit Vorzeichenergänzung; n≥a_bits ergibt −1 bei gesetztem Vorzeichenbit, sonst 0. Bei unsigned wird der negative Wert mit Abschneiden auf c-Breite kodiert; Fehlerüberlauf lehnt ihn ab. |
| INC, DEC | a+1 bzw. a−1; optional Carry/Borrow bei unsigned, Overflow bei signed. |
| MUX | Zusätzlicher unsigned Ein-Bit-Eingang `select`: 0 wählt a, 1 wählt b. Ergebnisbreite und Überlaufregel gelten für den gewählten Zahlenwert. |

Bei SHL/SHR interpretiert signed das resultierende a-Wort im Zweierkomplement,
bevor es auf c-Breite kodiert wird. Bei gleichem a/c und n=0 bleibt dadurch
auch ein negatives Wort erhalten. SAR verwendet das Vorzeichenbit auch bei
unsigned a. Schiebeweite ist entweder der feste Parameter `shift` (0–32)
oder der stets unsigned Eingang b mit eigener Breite. Grosse Eingangswerte
werden vor der eigentlichen Verschiebung begrenzt; negative Weiten sind unmöglich.
Ein fester Parameter entfernt b aus der Schnittstelle und erscheint im Namen als `[n=…]`.

### Bewusste Unterschiede zum CPU-Zustandsmodell

TinyCPU verwendet im Basisprofil 16-Bit-Zahlen, Akkumulator-/Speicher-Gültigkeit
und dauerhaft gesetzte Fehlerflags. ADD/SUB/MUL-Überlauf setzt dort OVF,
löscht den Akkumulatorwert und macht ihn ungültig. Primitives bietet wahlweise
Abschneiden mit optionalem Statusbit oder die Ablehnung des gesamten Datensatzes.
Ein Overflow-Statusausgang ist kein gespeichertes CPU-Fehlerregister.

TinyCPU behandelt DIV durch null als DIV0 mit ungültigem Nullergebnis. Die
Primitives-Ausgänge valid/div0 bilden diesen Rechenschritt bei gültigen Operanden ab.
Weitere Eingangs-Gültigkeitsbits und persistente Fehler sind nicht Bestandteil
dieser reinen Funktionen. Bei DIV zeigt valid einen Nichtnullteiler an;
ein zu grosses Ergebnis folgt weiterhin der gewählten Überlaufregel.
Insbesondere min_signed/−1 wird bei gleicher Breite mit Abschneiden wieder
min_signed und valid=1; auch der geprüfte Interpreter setzt dabei kein OVF.
Python-`//` und der eigene Formeloperator `div` runden dagegen nach unten;
die historische CLI-Vorlage `--preset div` bleibt unverändert unsigned mit
Nullergebnis bei Nullteiler und ohne Statusports.

## Vollständiges Befehlsinventar

Die Tabelle erfasst alle 50 Opcodes des Basisformats und die drei zusätzlichen
Opcodes des optionalen Systemprofils. „Teiloperation“ bedeutet, dass der
Rechenkern verfügbar ist, während Lesen, Schreiben, Gültigkeit und Ablauf
weiterhin Zustand benötigen. Adressierungsarten ergeben keine neuen ALU-Funktionen.
Für Zustand ist das Registermodell in [ARCHITEKTUR.md](ARCHITEKTUR.md#geplante-rückkopplung)
vorgesehen, für Programmablauf [PRIM-07/08](ERWEITERUNGEN.md#prim-07).

| Code | Befehl | Übernahmestatus und Begründung |
|---|---|---|
| 0x00 | `ADD_CONST` | Teiloperation: ADD als Referenz; Konstante wird als Eingang b bereitgestellt, Akkumulator bleibt Zustand. |
| 0x01 | `ADD_ADDRESS` | Teiloperation: ADD als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. |
| 0x02 | `ADD_ADDRESS_REGISTER` | Teiloperation: ADD als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. |
| 0x03 | `ADD_ADDRESS_REGISTER_PLUS_OFFSET` | Teiloperation: ADD als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. Adressaddition entspricht ADD, mit zusätzlicher Adressprüfung. |
| 0x04 | `SUB_CONST` | Teiloperation: SUB als Referenz; Konstante wird als Eingang b bereitgestellt, Akkumulator bleibt Zustand. |
| 0x05 | `SUB_ADDRESS` | Teiloperation: SUB als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. |
| 0x06 | `SUB_ADDRESS_REGISTER` | Teiloperation: SUB als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. |
| 0x07 | `SUB_ADDRESS_REGISTER_PLUS_OFFSET` | Teiloperation: SUB als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. Adressaddition entspricht ADD, mit zusätzlicher Adressprüfung. |
| 0x08 | `MUL_CONST` | Teiloperation: MUL als Referenz; Konstante wird als Eingang b bereitgestellt, Akkumulator bleibt Zustand. |
| 0x09 | `MUL_ADDRESS` | Teiloperation: MUL als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. |
| 0x0a | `MUL_ADDRESS_REGISTER` | Teiloperation: MUL als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. |
| 0x0b | `MUL_ADDRESS_REGISTER_PLUS_OFFSET` | Teiloperation: MUL als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. Adressaddition entspricht ADD, mit zusätzlicher Adressprüfung. |
| 0x0c | `DIV_CONST` | Teiloperation: DIV als Referenz; Konstante wird als Eingang b bereitgestellt, Akkumulator bleibt Zustand. |
| 0x0d | `DIV_ADDRESS` | Teiloperation: DIV als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. |
| 0x0e | `DIV_ADDRESS_REGISTER` | Teiloperation: DIV als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. |
| 0x0f | `DIV_ADDRESS_REGISTER_PLUS_OFFSET` | Teiloperation: DIV als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. Adressaddition entspricht ADD, mit zusätzlicher Adressprüfung. |
| 0x10 | `AND_CONST` | Teiloperation: AND als Referenz; Konstante wird als Eingang b bereitgestellt, Akkumulator bleibt Zustand. |
| 0x11 | `AND_ADDRESS` | Teiloperation: AND als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. |
| 0x12 | `AND_ADDRESS_REGISTER` | Teiloperation: AND als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. |
| 0x13 | `AND_ADDRESS_REGISTER_PLUS_OFFSET` | Teiloperation: AND als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. Adressaddition entspricht ADD, mit zusätzlicher Adressprüfung. |
| 0x14 | `OR_CONST` | Teiloperation: OR als Referenz; Konstante wird als Eingang b bereitgestellt, Akkumulator bleibt Zustand. |
| 0x15 | `OR_ADDRESS` | Teiloperation: OR als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. |
| 0x16 | `OR_ADDRESS_REGISTER` | Teiloperation: OR als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. |
| 0x17 | `OR_ADDRESS_REGISTER_PLUS_OFFSET` | Teiloperation: OR als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. Adressaddition entspricht ADD, mit zusätzlicher Adressprüfung. |
| 0x18 | `XOR_CONST` | Teiloperation: XOR als Referenz; Konstante wird als Eingang b bereitgestellt, Akkumulator bleibt Zustand. |
| 0x19 | `XOR_ADDRESS` | Teiloperation: XOR als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. |
| 0x1a | `XOR_ADDRESS_REGISTER` | Teiloperation: XOR als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. |
| 0x1b | `XOR_ADDRESS_REGISTER_PLUS_OFFSET` | Teiloperation: XOR als Referenz; Speicherzugriff und Akkumulator benötigen Zustand. Adressaddition entspricht ADD, mit zusätzlicher Adressprüfung. |
| 0x1c | `NOT` | Direkt kombinatorischer Rechenkern NOT; Akkumulator und Gültigkeit bleiben Zustand. |
| 0x1d | `JUMP_ADDRESS` | Benötigt Programmablauf (PRIM-07/08) und einen Programmzähler. |
| 0x1e | `JUMP_ZERO` | Teiloperation: Bedingung IsZero verfügbar; PC und Gültigkeit benötigen PRIM-07/08. |
| 0x1f | `JUMP_NOT_ZERO` | Teiloperation: Bedingung IsNonZero verfügbar; PC und Gültigkeit benötigen PRIM-07/08. |
| 0x20 | `JUMP_NEGATIVE` | Teiloperation: Bedingung IsNegative verfügbar; PC und Gültigkeit benötigen PRIM-07/08. |
| 0x21 | `JUMP_ERROR` | Benötigt Programmablauf (PRIM-07/08) und gespeicherte Fehlerflags. |
| 0x22 | `JUMP_NOT_ERROR` | Benötigt Programmablauf (PRIM-07/08) und gespeicherte Fehlerflags. |
| 0x23 | `LOAD_CONST` | Benötigt Register-/Speicherzustand und Gültigkeitsbits; erst mit Registermodell. |
| 0x24 | `LOAD_ADDRESS` | Benötigt Register-/Speicherzustand und Gültigkeitsbits; erst mit Registermodell. |
| 0x25 | `LOAD_ADDRESS_REGISTER` | Benötigt Register-/Speicherzustand und Gültigkeitsbits; erst mit Registermodell. |
| 0x26 | `LOAD_ADDRESS_REGISTER_PLUS_OFFSET` | Benötigt Register-/Speicherzustand und Gültigkeitsbits; erst mit Registermodell. ADD als Adress-Teiloperation verfügbar, Bereichsprüfung zusätzlich nötig. |
| 0x27 | `LOAD_ADDRESS_REGISTER_CONST` | Benötigt Register-/Speicherzustand und Gültigkeitsbits; erst mit Registermodell. |
| 0x28 | `LOAD_ADDRESS_REGISTER_ADDRESS` | Benötigt Register-/Speicherzustand und Gültigkeitsbits; erst mit Registermodell. |
| 0x29 | `STORE_ADDRESS` | Benötigt Register-/Speicherzustand und Gültigkeitsbits; erst mit Registermodell. |
| 0x2a | `STORE_ADDRESS_REGISTER` | Benötigt Register-/Speicherzustand und Gültigkeitsbits; erst mit Registermodell. |
| 0x2b | `STORE_ADDRESS_REGISTER_PLUS_OFFSET` | Benötigt Register-/Speicherzustand und Gültigkeitsbits; erst mit Registermodell. ADD als Adress-Teiloperation verfügbar, Bereichsprüfung zusätzlich nötig. |
| 0x32 | `CLEAR_ERROR` | Benötigt persistente Fehlerflags und einen Zustandsübergang; Registermodell. |
| 0x33 | `INPUT` | Zurückgestellt: I/O, Warteschlange bzw. Ausgabeeffekt und Gültigkeit brauchen ein Ausführungsmodell. |
| 0x34 | `PRINT` | Zurückgestellt: I/O, Warteschlange bzw. Ausgabeeffekt und Gültigkeit brauchen ein Ausführungsmodell. |
| 0x35 | `PRINT_ADDRESS` | Zurückgestellt: I/O, Warteschlange bzw. Ausgabeeffekt und Gültigkeit brauchen ein Ausführungsmodell. |
| 0x36 | `HALT` | Benötigt Halt-/Fehlerzustand und Programmablauf (PRIM-07/08). |
| 0x37 | `HALT_ERROR` | Benötigt Halt-/Fehlerzustand und Programmablauf (PRIM-07/08). |

Optionales Profil `tinycpu-peripherals-16-12-v1` (AP-18), explizit zu wählen:

| Code | Zusätzlicher Befehl | Übernahmestatus und Begründung |
|---|---|---|
| 0x38 | `ENABLE_INTERRUPTS` | Zurückgestellt: Interruptfreigabe, Rücksprungadresse und Handlerzustand benötigen das Register- und Ausführungsmodell. |
| 0x39 | `DISABLE_INTERRUPTS` | Zurückgestellt: Interruptfreigabe, Rücksprungadresse und Handlerzustand benötigen das Register- und Ausführungsmodell. |
| 0x3a | `RETURN_FROM_INTERRUPT` | Zurückgestellt: Interruptfreigabe, Rücksprungadresse und Handlerzustand benötigen das Register- und Ausführungsmodell. |

Das optionale Profil ergänzt auch einen speicherabgebildeten Ausgabeport und
Interruptanforderungen. Diese sind Zustands-/I/O-Semantik, keine weiteren Rechenoperationen.

IsZero, IsNonZero, IsNegative, Vergleiche, Schieber, INC/DEC und MUX sind
zusätzliche Beispiele bzw. extrahierte Teilfunktionen. Sie sind keine neuen
Opcodes des geprüften TinyCPU-Basisformats. Unbelegte Codes 0x2c–0x31 und
0x38–0x3f sind dort reserviert; das optionale Profil belegt 0x38–0x3a.

## Prüfung

Kleine Beispiele werden vollständig gegen unabhängige Integer-Referenzen geprüft.
Grössere Datensätze bleiben ausdrücklich Stichproben. Sie enthalten bevorzugt
0, 1, Maximalwerte, Zweierkomplement-Grenzen, einzelne Operanden bei null sowie
Schiebeweiten direkt unter, auf und über der a-Breite; weitere Plätze sind
mit Seed reproduzierbar zufällig belegt. Bei sehr kleinem Vektorbudget kann
nur ein entsprechend begrenzter Teil dieser Randfälle enthalten sein.

Ein vorhandener TinyCPU-Checkout kann zusätzlich direkt ausgeführt werden:

```powershell
python tools/verify_tinycpu.py ../TinyCPU
```

Das Werkzeug verändert die TinyCPU-Quellen nicht. Es prüft ADD/SUB/MUL/DIV,
AND/OR/XOR in allen vier Adressierungsarten sowie NOT bei signed 16 Bit.
7424 Vergleiche bestanden am genannten Stand, darunter 1364 Überlauffälle,
bei denen Status und CPU-Ungültigkeit statt identischer Ergebniswerte geprüft werden.
Die VM ist eine optionale Prüfquelle und keine Laufzeitabhängigkeit von Primitives.

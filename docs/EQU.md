# EQU: generatives Gleichheits-Template

Die [ausführbare Quelle](../examples/templates/recursive-equ.prim) und das
[abstrakte Template](../examples/templates/recursive-equ.abstract.json)
definieren `EQU<w>(a,b)` für zwei w-Bit-Eingänge und ein Ergebnisbit `c`.
`c=1` gilt genau dann, wenn alle Bits von a und b übereinstimmen.

## Parameter und Rekursion

Der Index w bezeichnet die **Bitbreite**, wie in der vorgeschlagenen Rekursion.
Die Zweierpotenzbedingung lautet deshalb `w = 2^k`, `k ∈ ℤ`, `k ≥ 0`.
Zulässig sind mathematisch w=1,2,4,8,… . Falls stattdessen t=2^w die
Bitbreite bezeichnet, heissen die Aufrufe entsprechend `EQU<t>` und `EQU<t//2>`;
der Basisfall bleibt `EQU<1>`.

```text
EQU<1>(a,b) = NOT(XOR(a,b))

EQU<w>(a,b) = EQU<w//2>(Upper<w>(a), Upper<w>(b))
              AND EQU<w//2>(Lower<w>(a), Lower<w>(b))     # w > 1
```

`Upper<w>` und `Lower<w>` erhalten hier die **gesamte Eingangsbreite** w
und liefern jeweils w//2 Bits. Bei LSB-first-Verdrahtung gilt:

```text
Lower<w>(a) = pack(bits(a,w)[:w//2])
Upper<w>(a) = pack(bits(a,w)[w//2:])
```

Das entspricht der vorgeschlagenen Formel. Die bestehenden Hilfsfunktionen
`LOWER<k>` und `HIGHER<k>` anderer Templates verwenden dagegen die
**Ausgangsbreite** k als Parameter. Entsprechend wäre `Upper<w>(a)` dort
als `HIGHER<w//2>(a)` zu schreiben.

Im Ein-Bit-Basisfall ist `1 ^ (a0 ^ b0)` genau die Negation von XOR.
Die beiden rekursiven Ergebnisse sind ebenfalls einzelne Bits; `hi & lo`
bildet daher das logische `&&` ab. Die Hälften werden parallel verglichen.
Eine unterschiedliche Bitposition setzt genau einen Teilvergleich auf 0
und damit auch das Gesamtergebnis. Bei vollständiger Übereinstimmung
liefern alle Blätter und alle AND-Verknüpfungen 1.

Beispiele: `EQU<4>(10,10)=1`, `EQU<4>(10,11)=0`,
`EQU<1>(0,0)=1`, `EQU<1>(1,0)=0`. Das Ergebnis hat immer genau ein Bit.

## Generierte Instanzen und Verifikation

| w | NANDs | Tiefe | Vollständig geprüfte Eingabepaare | F-Box-Paket | NAND-Netz | Lesbare NAND-Liste |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 5 | 4 | 4 | [Box](../examples/circuits/recursive-equ/equ-1.block.json) | [JSON](../examples/circuits/recursive-equ/equ-1.circuit.json) | [Text](../examples/circuits/recursive-equ/equ-1.nand.txt) |
| 2 | 12 | 6 | 16 | [Box](../examples/circuits/recursive-equ/equ-2.block.json) | [JSON](../examples/circuits/recursive-equ/equ-2.circuit.json) | [Text](../examples/circuits/recursive-equ/equ-2.nand.txt) |
| 4 | 26 | 8 | 256 | [Box](../examples/circuits/recursive-equ/equ-4.block.json) | [JSON](../examples/circuits/recursive-equ/equ-4.circuit.json) | [Text](../examples/circuits/recursive-equ/equ-4.nand.txt) |

Für w>1 enthält jede Box zwei `EQU<w//2>`-Instanzen und eine `AND`-Box.
Das Aufteilen der Eingänge ist reine Verdrahtung. Die Pakete enthalten
alle Abhängigkeiten mit festen Versionskennungen.

Die Konstruktion benötigt `G(1)=5`, `G(w)=2*G(w//2)+2`, also
`G(w)=7*w-2` NANDs, bei einer Tiefe von `4+2*LOG2(w)`. Das ist eine
generative Konstruktion; eine minimale Gatterzahl ist damit nicht bewiesen.
Das Template unterstützt im Projekt w=1,2,4,8,16,32,64. Bei w=64 sind die
128 Eingangsbits und 446 NANDs innerhalb der Grenzen des Systems.

Die [Prüfberichte](../examples/circuits/recursive-equ/verification.json)
und vollständigen `.vectors.json`-Tabellen stehen neben den Schaltungen.
Alle Eingabepaare für w=1,2,4 wurden unabhängig gegen Ganzzahlgleichheit
geprüft: Quellauswertung, F-Box-Auswertung, Expansion, vereinfachtes Netz
und direkte Quellsynthese stimmen überein. Die Tests prüfen zusätzlich
w=8,16,32,64 mit Grenzfällen, festen Zufallsstichproben, gleichen Operanden
und Abweichungen an jeder einzelnen Bitposition in beiden Operanden.
Diese grösseren Breiten sind anhand von Stichproben geprüft.

## Bibliothek und Reproduktion

Beim nächsten Serverstart werden Template und Funktionen `EQU<1>`,
`EQU<2>`, `EQU<4>` unter **Beispiele → Rekursion** ergänzt. Die drei
F-Box-Pakete stehen unter **Unterprogramm-Bausteine** bereit.
Eigene Ordnerzuordnungen bleiben erhalten; nach der Installation gelöschte
Beispiele werden nicht erneut angelegt.

Im Template-Editor lässt sich mit `{"w": 8}` eine weitere Breite
konkretisieren und direkt in NAND übersetzen. Die Bedingungen werden vor
der Konkretisierung geprüft; Assertions schützen auch direkte Unteraufrufe.

```powershell
python -m tools.export_equ
python -m unittest discover -s tests -p test_equ.py -v
```

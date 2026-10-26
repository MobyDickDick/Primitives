# NumberOfOnes: Einsen eines Bitarrays zählen

Die [ausführbare Quelle](../examples/templates/recursive-number-of-ones.prim)
und das [generische Template](../examples/templates/recursive-number-of-ones.abstract.json)
definieren `NumberOfOnes<w>(a)`. `w` ist eine positive Zweierpotenz. Der Eingang
`a` hat `w` Bits, der unsigned Ausgang `c` hat `LOG2(w)+1` Bits. Bits und
Portverbindungen sind LSB-first; `a0` ist das niederwertigste Eingangsbit.

## Geprüfte Rekursion und Breiten

Mit `ADD_full<r>` als vollständiger Addition zweier r-Bit-Zahlen lautet die Formel:

```text
NumberOfOnes<1>(a) = a0

NumberOfOnes<w>(a) = ADD_full<LOG2(w)>(
    NumberOfOnes<w//2>(LOWER<w//2>(a)),
    NumberOfOnes<w//2>(HIGHER<w//2>(a))
)                                                       # w > 1
```

Die vorgeschlagene Rekursion ist also nach Korrektur der Klammern richtig,
sofern der Addierer seinen Übertrag erhält. Jede Teilzählung liegt zwischen
0 und `w//2` einschliesslich und benötigt deshalb `LOG2(w)` Bits. Die Summe
liegt zwischen 0 und `w` einschliesslich und benötigt `LOG2(w)+1` Bits.
Beispiel: `NumberOfOnes<4>(1111) = 4 = [0,0,1]`. Ohne das letzte Ergebnisbit
ginge gerade der Fall mit lauter Einsen verloren.

Das bestehende rekursive `ADD<r>` erlaubt nur Zweierpotenzbreiten r. Für w=1,2,4
ist das kein Hindernis: Der Basisfall verwendet keinen Addierer, danach sind
die Addiererbreiten 1 und 2. Bei w=8 wird jedoch r=3, bei w=32 wird r=5 benötigt.
Die neue Quelle verwendet dafür den lokalen `ADD_count<r>` mit beliebiger
positiver Breite und vollständigem r+1-Bit-Ergebnis. Er besteht aus festen
Ripple-Carry-Stufen und lässt sich direkt nach NAND übersetzen.

`LOWER<k>` liefert die unteren k Bits, `HIGHER<k>` die oberen k Bits des
2*k-Bit-Arguments. Das Aufteilen und das Zusammenführen der Ports sind reine
Verdrahtung. `LOG2(w)` ist ein exakter Ganzzahloperator für positive
Zweierpotenzen: `LOG2(1)=0`, `LOG2(2)=1`, `LOG2(4)=2`. Für andere Argumente
wird ein Fehler gemeldet. Er ist auch in symbolischen Portbreiten und
Template-Bedingungen verfügbar und wird bei der NAND-Synthese statisch
ausgewertet.

## Konkrete Instanzen

```text
NumberOfOnes<1>(a0)          = a0
NumberOfOnes<2>(a0,a1)       = ADD_count<1>(a0,a1)
NumberOfOnes<4>(a0,a1,a2,a3) = ADD_count<2>(
    NumberOfOnes<2>(a0,a1), NumberOfOnes<2>(a2,a3))
```

Die Schreibweise mit mehreren Einzelbits zeigt hier die Belegung des einen
Bitarray-Eingangs a. Die ausführbare Funktion hat stets genau ein Argument a.

| w | Ergebnisbits | F-Box-Paket | Flaches NAND-Netz | Lesbare NAND-Liste | NANDs | Tiefe | Geprüfte Eingaben |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | [Box](../examples/circuits/recursive-number-of-ones/number-of-ones-1.block.json) | [JSON](../examples/circuits/recursive-number-of-ones/number-of-ones-1.circuit.json) | [Text](../examples/circuits/recursive-number-of-ones/number-of-ones-1.nand.txt) | 0 | 0 | 2 |
| 2 | 2 | [Box](../examples/circuits/recursive-number-of-ones/number-of-ones-2.block.json) | [JSON](../examples/circuits/recursive-number-of-ones/number-of-ones-2.circuit.json) | [Text](../examples/circuits/recursive-number-of-ones/number-of-ones-2.nand.txt) | 5 | 3 | 4 |
| 4 | 3 | [Box](../examples/circuits/recursive-number-of-ones/number-of-ones-4.block.json) | [JSON](../examples/circuits/recursive-number-of-ones/number-of-ones-4.circuit.json) | [Text](../examples/circuits/recursive-number-of-ones/number-of-ones-4.nand.txt) | 24 | 8 | 16 |

Für w=1 ist `c0=a0` eine direkte Leitung. Für w=2 enthält die Wurzel zwei
`NumberOfOnes<1>`-Boxen und `ADD_count<1>`. Für w=4 enthält sie zwei
`NumberOfOnes<2>`-Boxen und `ADD_count<2>`; jede Teilzählbox enthält wiederum
ihre beiden Ein-Bit-Boxen und ihren Addierer. Jedes Paket enthält alle
Abhängigkeiten mit festen Versionskennungen.

Die flachen NAND-Netze entstehen aus der Expansion der Boxhierarchie mit
anschliessender Vereinfachung. Die Zahlen in der Tabelle gelten hier für
die expandierte und die vereinfachte Schaltung. Eine minimale Gatterzahl
ist damit nicht bewiesen.

Im selben Verzeichnis stehen die konkreten `.template.json`-Instanzen,
vollständige `.vectors.json`-Wahrheitstabellen und ein
[Prüfbericht](../examples/circuits/recursive-number-of-ones/verification.json).
Alle Eingaben wurden unabhängig mit der Einsenzählung der Ganzzahl verglichen:
Quellauswertung, F-Box-Auswertung, Expansion, flaches Netz und direkte
Quellsynthese stimmen überein. Tests prüfen zusätzlich w=8 vollständig und
w=16,32 anhand von Grenzfällen und festen Zufallsstichproben. Das Template
unterstützt w=1,2,4,8,16,32 innerhalb der bestehenden 32-Bit-Eingangsgrenze.

## Bibliothek und Reproduktion

Beim nächsten Serverstart werden das Template und die drei konkreten
Funktionen unter **Beispiele → Rekursion** einmalig ergänzt. Unter
**Unterprogramm-Bausteine** sind die drei F-Box-Pakete verfügbar. Mit
**Baustein öffnen** lassen sich die verschachtelten Unterfunktionen öffnen
und lokal testen. Bestehende Ordnerzuordnungen bleiben erhalten; nach dieser
Installation gelöschte Beispiele werden nicht erneut angelegt.

```powershell
python -m tools.export_number_of_ones
python -m unittest discover -s tests -p test_number_of_ones.py -v
```

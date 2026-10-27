# Maximaler gesetzter Bitindex: m<t>(a)

Für `w >= 0`, `t = 2**w` und `a = sum(a_k * 2**k, k=0..t-1)`
liefert `m<t>(a)` den grössten Index k mit `a_k=1`. Das Ergebnis ist das
Paar `[c,err]`: c hat t Bits, err hat ein Bit. Für `a=0` ist es genau
`[const<t>(0),1]`, sonst `[floor(log2(a)),0]`. Index 0 ist gültig und
wird durch err=0 vom Nullfehler unterschieden.

Die [generative Quelle](../examples/templates/recursive-max-index.prim)
und das [ausführbare Template](../examples/templates/recursive-max-index.abstract.json)
sind gespeichert. Die mathematische Konstruktion gilt für jede Zweierpotenz t.
Das gespeicherte Beispiel-Template beschränkt t ausdrücklich auf 1,2,4,8,16.
Die allgemeine Schnittstelle erlaubt inzwischen 128 Bits je Seite; die
Darstellung braucht t+1 Ausgangsbits. Eine Erweiterung der Template-Bedingung
auf t=32 oder t=64 ist damit möglich, unterliegt aber weiterhin den
Laufzeit- und Gatterbudgets.

## Rekursion und korrigierter Offset

Für t>1 setze k=t//2 und zerlege a in zwei k-Bit-Zahlen:

```text
Lower(a) = a mod 2**k
Upper(a) = a // 2**k

m<k>(Lower(a)) = [l,eL]
m<k>(Upper(a)) = [h,eH]

m<t>(a) = [h+k,0]   falls eH=0
          [l,eL]    falls eH=1

m<1>(a0) = [0, NOT(a0)]
```

Der Offset ist `t//2 = 2**(w-1)`, nicht w//2. Beispiel t=4, w=2:
Die obere Hälfte enthält a2 und a3; ihre lokalen Indizes 0 und 1 werden
zu 2 und 3. Bei t=1 wird keine Halbierung vorgenommen.

Diese Fallunterscheidung wird als kombinatorische Auswahl verdrahtet.
Mit s=NOT(eH) und w=LOG2(t) gilt bitweise:

```text
err       = AND(eL,eH)
c[i]      = OR(AND(s,h[i]), AND(eH,l[i]))   für 0 <= i < w-1
c[w-1]    = s
c[w..t-1] = 0
```

Das Anhängen von s realisiert bereits den Offset k, weil k=2**(w-1)
und die lokalen Indizes kleiner als k sind. Ein Addierer ist unnötig.
Auch ein gesondertes Netz für `Upper(a)>0` entfällt: eH zeigt bereits
an, ob die obere Hälfte Null ist. Der Nullfehler bleibt erhalten,
weil err genau dann 1 ist, wenn beide Hälften Null sind.

Alle Operatoren lassen sich generativ durch NAND ersetzen:

```text
NOT(x)       = NAND(x,x)
AND(x,y)     = NAND(NAND(x,y),NAND(x,y))
OR(x,y)      = NAND(NAND(x,x),NAND(y,y))
MUX(s,h,l)   = NAND(NAND(s,h),NAND(NAND(s,s),l))
```

LOWER/UPPER, Indexbit-Anhängen und Nullauffüllung sind Verdrahtung.
Die feste Null wird ohne zusätzliche Eingänge aus drei NANDs erzeugt:
`n=NAND(a0,a0)`, `one=NAND(a0,n)`, `zero=NAND(one,one)`.
Die Synthese teilt gleiche Gatter und vereinfacht die expandierte Hierarchie.

## Feste Instanzen t=1,2,4

In den folgenden Formeln sind die Bitlisten **LSB-first**. Das äussere
Paar besteht aus dem t-Bit-Index und dem Fehlerbit:

```text
m<1>(a0) = [[0], NOT(a0)]

m<2>(a0,a1) = [[a1,0], NOT(OR(a0,a1))]

u = OR(a2,a3)
v = OR(a3,AND(a1,NOT(a2)))
m<4>(a0,a1,a2,a3) = [[v,u,0,0], NOT(OR(a0,a1,a2,a3))]
```

Die Schreibweise mit Einzelbits zeigt die Belegung des einen Arguments a.
Die Formel für v ist eine boolesche Vereinfachung der rekursiven Auswahl.
Die gespeicherten NAND-Netze entstehen direkt aus der rekursiven Konstruktion;
eine minimale Gatterzahl ist nicht behauptet.

| t | Ausgang | NANDs flach | Tiefe | Vollständig geprüfte Eingaben | NAND-Liste | Hierarchie |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 Indexbit + err | 3 | 3 | 2 | [m-1.nand.txt](../examples/circuits/recursive-max-index/m-1.nand.txt) | [F-Box](../examples/circuits/recursive-max-index/m-1.block.json) |
| 2 | 2 Indexbits + err | 6 | 3 | 4 | [m-2.nand.txt](../examples/circuits/recursive-max-index/m-2.nand.txt) | [F-Box](../examples/circuits/recursive-max-index/m-2.block.json) |
| 4 | 4 Indexbits + err | 15 | 5 | 16 | [m-4.nand.txt](../examples/circuits/recursive-max-index/m-4.nand.txt) | [F-Box](../examples/circuits/recursive-max-index/m-4.block.json) |

Die Nullauffüllung ist in den Gatterzahlen enthalten. Nur w=LOG2(t)
Indexbits tragen Information; für t=1 ist der Index stets Null. Die
unvereinfachten Hierarchien enthalten 3, 9 und 24 NANDs. Jede F-Box für t>1
enthält zwei m<t//2>-Boxen sowie NANDs für Auswahl und Fehlerbit.

Die vollständigen Wahrheitstabellen lassen sich so zusammenfassen;
hier wird der Eingang wie üblich mit dem höchstwertigen Bit links gezeigt:

| t | Eingang a | Ergebnis [c,err] |
| --- | --- | --- |
| 1 | 0 | [0,1] |
| 1 | 1 | [0,0] |
| 2 | 00 | [0,1] |
| 2 | 01 | [0,0] |
| 2 | 1x | [1,0] |
| 4 | 0000 | [0,1] |
| 4 | 0001 | [0,0] |
| 4 | 001x | [1,0] |
| 4 | 01xx | [2,0] |
| 4 | 1xxx | [3,0] |

Dabei steht x für ein beliebiges Bit. Im
[Exportverzeichnis](../examples/circuits/recursive-max-index/) liegen ausserdem
die flachen `.circuit.json`-Netze, konkreten `.template.json`-Programme,
vollständigen `.vectors.json`-Tabellen und der
[Prüfbericht](../examples/circuits/recursive-max-index/verification.json).

## Prüfung und Bibliothek

Für t=1,2,4 wurden alle Eingaben gegen eine unabhängige Referenz mit
`a.bit_length()-1` und separater Nullprüfung verglichen: Quellauswertung,
F-Box-Auswertung, Expansion, vereinfachtes NAND-Netz und direkte Quellsynthese.
Die Tests prüfen zusätzlich t=8 vollständig sowie t=16 an allen einzelnen
gesetzten Bits, Zweierpotenzgrenzen, Null, lauter Einsen und festen
Zufallsstichproben. Auch Nullauffüllung und die Ablehnung ungültiger
Breiten werden geprüft.

Beim nächsten Serverstart werden Template und Funktionen unter
**Beispiele → Rekursion** einmalig ergänzt. Die drei verschachtelten
F-Boxen stehen unter **Unterprogramm-Bausteine** bereit. Bestehende
Ordnerzuordnungen und nach der Installation gelöschte Beispiele bleiben erhalten.

```powershell
python -m tools.export_max_index
python -m unittest discover -s tests -p test_max_index.py -v
```

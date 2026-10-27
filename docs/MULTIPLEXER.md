# Generative Multiplexer und Demultiplexer

Die Bezeichnungen sind:

| Template | Funktion | Datenports | Auswahlport |
| --- | --- | --- | --- |
| `MUX<n,w>(a,b)` | Wählt einen von `2**w` Eingängen: `c=a_b` | `a`: `n*2**w` Bits, `c`: `n` Bits | `b`: `w` Bits |
| `DEMUX<n,w>(a,b)` | Verteilt einen Eingang: `c_b=a`; alle anderen Kanäle sind 0 | `a`: `n` Bits, `c`: `n*2**w` Bits | `b`: `w` Bits |

`n` ist die Anzahl paralleler Datenleitungen **pro Kanal**. `w` ist unabhängig
davon die Anzahl Auswahlbits. `w=1,2,4` ergibt 2, 4 bzw. 16 Kanäle.
Die beiden Templates sind für beliebige positive Datenbreiten innerhalb der
Projektgrenzen parametrierbar; `n` muss keine Zweierpotenz sein.

Für `n=1,w=1` gilt genau:

```text
MUX:   b=0 → c=a0;        b=1 → c=a1
DEMUX: b=0 → (c0,c1)=(a,0); b=1 → (c0,c1)=(0,a)
```

Die generative Schnittstelle bündelt die Kanäle in einem benannten Bitarray.
Index 0 ist das niederwertigste Bit. Kanal `j` belegt den Ausschnitt
`[j*n:(j+1)*n]` in `a` beim MUX bzw. `c` beim DEMUX. Kanal 0 liegt also zuerst.
Für die Zahleneingabe gilt:

```text
MUX:   a = a0 + a1*2**n + a2*2**(2*n) + …
       c = (a >> (n*b)) & (2**n - 1)
DEMUX: c = a << (n*b)
```

Beispiel `n=2,w=2`: Die Eingangskanäle `[0,1,2,3]` werden als `a=228`
gepackt. MUX liefert bei `b=0,1,2,3` entsprechend `0,1,2,3`.
DEMUX mit `a=3,b=2` liefert `[0,0,3,0]`, gepackt `c=48`.
In einem Vektordatensatz stehen zuerst alle Bits von `a`, dann die Bits von `b`.

## Quellen und rekursive Konstruktion

| Template | Editierbare Quelle | Importierbares abstraktes Template |
| --- | --- | --- |
| MUX | [recursive-multiplexer.prim](../examples/templates/recursive-multiplexer.prim) | [JSON](../examples/templates/recursive-multiplexer.abstract.json) |
| DEMUX | [recursive-demultiplexer.prim](../examples/templates/recursive-demultiplexer.prim) | [JSON](../examples/templates/recursive-demultiplexer.abstract.json) |

Bei einem Auswahlbit verwendet MUX pro Datenbit
`(a0 & (1 ^ b)) | (a1 & b)`. DEMUX bildet `a & (1 ^ b)` und `a & b`.
Für mehrere Auswahlbits halbiert MUX die Kanalliste, wählt in beiden Hälften
rekursiv mit den unteren Auswahlbits und entscheidet mit dem höchsten
Auswahlbit zwischen den Ergebnissen. DEMUX teilt zuerst am höchsten
Auswahlbit und verteilt beide Ergebnisse rekursiv weiter.

Die F-Boxen bilden dieselbe Struktur mit zwei kleineren Teilinstanzen und einer
2-Kanal-Stufe ab. Die flachen Schaltungen entstehen durch Expansion und
boolesche Vereinfachung. Die direkte Synthese der Programmquelle wird separat
geprüft. Sämtliche Laufzeitentscheidungen bestehen aus Bitoperationen;
Rekursion, Schleifen und Indizes hängen nur von den Template-Parametern ab.

Das vorhandene `MUX<t>(a,b,sel)` mit zwei getrennten Datenports bleibt verfügbar.
`MUX<n,w>` ergänzt die freie Kanalzahl und nutzt dafür die gepackte Schnittstelle.

## Erzeugte Instanzen und Prüfstatus

Alle Kombinationen `n=1,2,4` und `w=1,2,4` sind erzeugt: neun MUX und neun DEMUX.

| Datenbreite n | MUX NANDs für w=1 / 2 / 4 | DEMUX NANDs für w=1 / 2 / 4 |
| --- | --- | --- |
| 1 | 4 / 11 / 49 | 5 / 14 / 64 |
| 2 | 7 / 20 / 94 | 9 / 26 / 124 |
| 4 | 13 / 38 / 184 | 17 / 50 / 244 |

Alle neun DEMUX-Instanzen und fünf MUX-Instanzen sind mit vollständigen
Wahrheitstabellen geprüft. Für MUX mit `(n,w)=(1,4),(2,4),(4,2),(4,4)` enthält
der Datensatz jeweils 256 Vektoren: verteilte Grenzfälle und reproduzierbare
Zufallsstichproben. Diese vier Datensätze sind ausdrücklich **nicht vollständig**.
Zusätzlich prüft der Export unabhängig jeden Kanal mit allen möglichen
Datenwerten bei sonst leeren und sonst gesetzten Eingängen sowie jedes einzelne
Eingangsbit für jeden Auswahlwert, jeweils auch invertiert. Die Tests ergänzen
weitere feste Zufallsstichproben und die Datenbreiten 3 und 7 sowie w=3 und w=6.

Prüfberichte mit Vektorzahlen und Status:
[MUX](../examples/circuits/recursive-multiplexer/verification.json),
[DEMUX](../examples/circuits/recursive-demultiplexer/verification.json).
Jeder Ordner enthält pro Parameterpaar `.template.json`, `.block.json`,
`.circuit.json`, `.vectors.json` und die lesbare `.nand.txt`.
Beispiel: [MUX<4,2> als F-Box](../examples/circuits/recursive-multiplexer/multiplexer-4-2.block.json),
[DEMUX<4,2> als NAND-Netz](../examples/circuits/recursive-demultiplexer/demultiplexer-4-2.circuit.json).
Die Gatterzahlen sind kein Minimalitätsnachweis.

## Bibliothek und Verwendung

Beim nächsten Serverstart werden die beiden Templates und 18 Funktionen
einmalig unter **Beispiele → Rekursion → Multiplexer & Demultiplexer** ergänzt.
Die 18 F-Boxen erscheinen unter **Unterprogramm-Bausteine**.
Verschiebungen, eigene Beschreibungen und spätere Löschungen bleiben erhalten.
Das Bibliotheksupdate ist unabhängig von den bisherigen Beispielinstallationen.

Im Template-Editor beispielsweise `{"n": 4, "w": 2}` eingeben: vier Datenbits
pro Kanal, zwei Auswahlbits, vier Kanäle. Die Grenzen bleiben 128 Bits je
Schnittstellenseite und 512 NAND-Gatter, auch bei der F-Box-Expansion vor der
Vereinfachung. Daher muss MUX `n*2**w+w<=128` und DEMUX `n*2**w<=128` sowie
`n+w<=128` erfüllen. `1<=w<=7` gilt generell; MUX erreicht höchstens w=6.
Gültige Portbreiten garantieren keine Synthese innerhalb des Gatterlimits:
DEMUX<1,7> ist als Referenz auswertbar, überschreitet beim NAND-Aufbau aber
512 Gatter und wird dort mit einer Fehlermeldung abgelehnt.

```powershell
python -m tools.export_routing
python -m unittest discover -s tests -p test_routing.py -v
```

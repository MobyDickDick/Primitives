# Rekursive Division durch MSB-Ausrichtung

Die [Quelle](../examples/templates/recursive-msb-div.prim) und das
[abstrakte Template](../examples/templates/recursive-msb-div.abstract.json)
implementieren `DIV<w>(a,b)` für unsigned Eingaben, LSB-first:

```text
b == 0: [const<w>(0), 1]
b != 0: [const<w>(a // b), 0]
```

Der Fehlerausgang steht hinter den w Quotientenbits. Insbesondere sind
`0/0` ein Fehler, `a<b` ein gültiges Nullergebnis und `a=b!=0` eine Eins.
Der Ein-Bit-Basisfall ist `[a0 AND b0, NOT b0]`.

## Mathematische Idee

Für `a>=b>0` seien `a_g` und `b_g` die nullbasierten Positionen der
höchstwertigen Eins. Dann gilt:

```text
d = a_g - b_g
s = b * 2**d
wenn s > a:
    d = d - 1
    s = s / 2
q = 2**d + Quotient(a-s, b)
```

Die Multiplikation mit `2**d` verschiebt zu höheren Bitpositionen.
Bei einer von links nach rechts geschriebenen LSB-first-Liste sieht das
wie ein Verschieben nach rechts aus. Entscheidend ist die Wertänderung.
Der Vergleich lautet `s <= a`, einschliesslich Gleichheit. Das gesetzte
Quotientenbit liegt bei `d` beziehungsweise `d-1`, nicht bei `b_g`.
Wenn `d=0`, kann die Korrektur nach unten für `a>=b` nicht auftreten.

Beispiel `40/6`: `a_g=5`, `b_g=2`, also zunächst `d=3` und `s=48`.
48 ist zu gross; mit `d=2` wird 24 subtrahiert. Das liefert Quotientenanteil
4 und Rest 16. Im nächsten Schritt ist 24 erneut zu gross, also wird 12
subtrahiert: Quotientenanteil 2 und Rest 4. Da 4 kleiner als 6 ist, endet
die Rechnung mit `4+2=6`.

Der gewählte Exponent ist der grösste mögliche: Entweder passt die
MSB-Ausrichtung unmittelbar oder genau eine Stelle darunter. Nach der
Subtraktion ist der Rest kleiner als `b*2**d`; alle weiteren
Quotientenbits liegen deshalb unterhalb von d. Ihre Summe kann als
bitweises OR ohne Addierer aufgebaut werden.

## Feste Rekursion statt datenabhängiger Aufrufe

Eine Schaltung kann ihre Gatterzahl nicht von Eingabewerten abhängig
machen. Deshalb führt `DIV_BITS<n,w>` feste Stufen für `n=w,...,1` aus.
`n` bezeichnet die mögliche Dividendbreite; `b` behält immer w Bits.

`HIGHEST<w>(b)` markiert einmalig die höchste Eins des Divisors als
One-hot-Vektor. `ALIGN<n,n-1>` wählt mit diesen Signalen die Verdrahtung,
die b an Position n-1 ausrichtet, sowie den zugehörigen Quotientenanteil.
Das ist ein Gatternetz aus fest verdrahteten Kandidaten und Masken,
kein eingabeabhängiger Arrayindex oder Schiebeoperator.

Wenn Dividendbit n-1 null ist, reicht die Stufe den Dividend unverändert
an die nächste Stufe weiter. Die erste aktive Stufe liegt somit genau
bei `a_g=n-1`, ohne einen weiteren kodierten MSB-Index zu benötigen.
Zwei Subtraktionsnetze berechnen die Differenzen zur vollen und zur
halbierten Ausrichtung. Borrow und Bitmasken wählen den passenden Rest
und Quotientenanteil aus. Höhere Divisorbits werden berücksichtigt:
Ein durch Abschneiden entstandener kleiner Divisor wird nie akzeptiert.

Bei der vollen Ausrichtung ist der Rest kleiner als `2**(n-1)`.
Wenn erst die halbe Ausrichtung passt, folgt aus der abgelehnten vollen
Ausrichtung sogar `Rest < halbe Ausrichtung < 2**(n-1)`.
Die nächste Stufe benötigt daher nur n-1 Dividendbits.
Wenn die aktuelle höchstwertige Dividend-Eins gesetzt ist, aber `a<b`
gilt, wird die verbleibende Quotientenberechnung mit Null fortgesetzt.
Ein Rest wird von dieser Schnittstelle nicht ausgegeben.

So sinkt n bei jedem Aufruf unabhängig von den Eingabewerten. Alle
`if`-Anweisungen prüfen ausschliesslich generische Parameter. Die Quelle
enthält weder `for` noch `while`, keine Division von Eingabewerten und
keine datenabhängige Verzweigung. Bei b=0 maskiert die öffentliche
Funktion den Quotienten auf null und setzt das Fehlerbit.

## NAND-Export und Grenzen

Die strukturelle Synthese übersetzt die Quelle unmittelbar in azyklische
NAND-Netze. Referenzvektoren werden erst zur Prüfung verwendet.

| w | NANDs | Tiefe | vollständig geprüfte Eingabepaare |
| --- | --- | --- | --- |
| 1 | 3 | 2 | 4 |
| 2 | 56 | 22 | 16 |
| 3 | 147 | 40 | 64 |
| 4 | 283 | 60 | 256 |

Die [Exporte](../examples/circuits/recursive-msb-div/) enthalten konkrete
Templates, flache Schaltungen, lesbare NAND-Listen, Referenzvektoren und
den Verifikationsbericht. Es handelt sich um eine konventionelle
Konstruktion mit lokalen Vereinfachungen, ohne Minimalitätsnachweis.

Der unterstützte Referenzbereich ist `1<=w<=8`, auch für ungerade Breiten.
Für w=5 bis 8 prüfen Tests Grenzfälle um skalierte Divisoren und feste
Zufallsstichproben. Die NAND-Synthese überschreitet bei diesen Breiten
die bestehende Grenze von 512 Gattern und lehnt den Export ab.
Die azyklische Struktur bedeutet keine lineare Gatterzahl in w.

Nach dem nächsten Serverstart ergänzt eine einmalige Migration das
Template und die vier geprüften Funktionen unter **Beispiele → Rekursion**.
Vorhandene Ordnertexte und Zuordnungen bleiben erhalten; nach der
Migration gelöschte Beispiele werden nicht erneut angelegt.

```powershell
python -m tools.export_recursive_div
python -m unittest discover -s tests -p test_recursive_div.py -v
```

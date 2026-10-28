# Die Template-Sprache lesen

Die `.prim`-Dateien verwenden eine eigene, eingeschränkte **Python-ähnliche
Sprache**. Die Anwendung wertet sie mit einem eigenen Interpreter aus.
Sie sind keine direkt mit Python ausführbaren Dateien: Template-Klammern
wie `subtract<4>(a,b)` und ein `return` auf oberster Ebene gehören zur
Sprache dieser Anwendung. Imports, Klassen und beliebige Python-Bibliotheken
sind nicht vorgesehen.

Die ausführlichen Sprachbeschreibungen stehen hier:

- [PROGRAMME.md](PROGRAMME.md#syntax-der-sprachversion-1): Einrückung,
  Zuweisungen, Schleifen, Bedingungen, Operatoren, Bitarrays und Rückgabewerte.
- [TEMPLATES.md](TEMPLATES.md#schreibweise-mit-spitzen-klammern): Sprachversion 2
  mit festen Parametern, eigenen Funktionen, Rekursion und symbolischen Portbreiten.
- [Direkte NAND-Synthese](TEMPLATES.md#direkte-strukturelle-nand-synthese):
  welche dieser Ausdrücke sich unmittelbar in eine Schaltung übersetzen lassen.

## Die wichtigsten Schreibweisen

| Schreibweise | Bedeutung | Beispiel |
| --- | --- | --- |
| `# Text` | Kommentar bis zum Zeilenende | `borrow = 0  # noch kein Leihbit` |
| Einrückung nach `:` | Inhalt eines Funktions-, Schleifen- oder Bedingungsblocks | Vier Leerzeichen pro Ebene |
| `def subtract<w>(a,b):` | Funktion mit fester Bitbreite w und zwei Datenargumenten | `subtract<4>(a,b)` |
| `bits(a,4)` | Die unteren vier Bits als Array, niedrigstes zuerst | `bits(6,4)` ergibt `[0,1,1,0]` |
| `pack(x)` | Ein Bitarray wieder als Zahl lesen | `pack([0,1,1,0])` ergibt 6 |
| `x[i]` | Bit an Index i; Index 0 ist die Einerstelle | `bits(6,4)[0]` ist 0 |
| `x[:q]` | Die ersten q Bits; Index q gehört nicht dazu | `[0,1,1,0][:2]` ergibt `[0,1]` |
| `[0] * p` | Array mit p Nullbits | `[0] * 3` ergibt `[0,0,0]` |
| `[bit] + x` | Arrays aneinanderhängen | `[1]+[0,1]` ergibt `[1,0,1]` |
| `x & y` | Bitweises AND | `1 & 0` ergibt 0 |
| `x \| y` | Bitweises OR | `1 \| 0` ergibt 1 |
| `x ^ y` | Bitweises XOR, unterschiedliche Bits ergeben 1 | `1 ^ 1` ergibt 0 |
| `1 ^ bit` | Ein einzelnes Bit umkehren | Aus 0 wird 1, aus 1 wird 0 |
| `2 ** w` | Potenz, also 2 hoch w | `2 ** 4` ergibt 16 |
| `a // b`, `a % b` | Ganzzahldivision und Rest | `13 // 3` ergibt 4, `13 % 3` ergibt 1 |
| `range(p-1,-1,-1)` | Rückwärts von p−1 bis einschliesslich 0 | Bei p=4: 3,2,1,0 |
| `return c, rest, valid, div0` | Je ein Wert pro Ergebnisport, in dessen Reihenfolge | Quotient, Rest und zwei Statusbits |

`w`, `p` und `q` werden vor der Schaltungserzeugung festgelegt. `a` und `b`
sind die später wechselnden Eingangswerte. Deshalb können Schleifen über
feste Bitbreiten in eine feste Zahl von Gatterstufen übersetzt werden.
Eingabeabhängige Berechnungen werden bei den Standardlösungen als Bitlogik
ausgeschrieben. Ein allgemeines `if a>=b` ist im Interpreter erlaubt,
für die direkte strukturelle NAND-Synthese jedoch nicht geeignet.

`^` bedeutet im Template-Quelltext **XOR**. Der separate Formeleditor verwendet
`^` für Potenzen; im Template schreibt man Potenzen mit `**`.
Die äusseren dreifachen Anführungszeichen aus einer Nachricht gehören nicht
in das Quelltextfeld. Für Erläuterungen im Template `# Kommentare` verwenden.

## Die Division aus dem Beispiel

Die ausführlich kommentierte Quelle steht in
[standard-div.prim](../examples/templates/standard-div.prim).
Die Funktion `subtract<w>` liefert die unteren w Differenzbits und darüber
ein Leihbit. Dieses letzte Bit ist 1, wenn die Subtraktion eine negative
Differenz ergeben würde.

Das Hauptprogramm arbeitet wie schriftliches Dividieren:

1. Das nächste Bit des Dividenden von oben herunterholen. Der neue Rest ist
   `2*alter_rest + nächstes_bit`.
2. Versuchsweise den Divisor abziehen.
3. Entsteht kein Leihbit, die Differenz übernehmen und das Quotientenbit setzen.
   Sonst den bisherigen Rest behalten und ein Quotientenbit 0 schreiben.
4. Bei Divisor 0 am Ende Quotient und Rest auf 0 setzen und `div0=1` melden.

Beispiel `13 / 3`, also `1101 / 0011`, mit vier Eingangsbits:

| Dividend-Bit | Rest nach Herunterholen | Passt 3 hinein? | Neuer Rest | Quotientenbit |
| --- | ---: | --- | ---: | ---: |
| 1 (höchstes Bit) | 1 | Nein | 1 | 0 |
| 1 | 3 | Ja | 0 | 1 |
| 0 | 0 | Nein | 0 | 0 |
| 1 (niedrigstes Bit) | 1 | Nein | 1 | 0 |

Von oben gelesen sind die Quotientenbits `0100`, also 4; der Rest ist 1.
Im LSB-first-Array steht derselbe Quotient als `[0,0,1,0]`.

## Wo die Sprache implementiert ist

- [primitives/program.py](../primitives/program.py): Umformung der
  Template-Klammern in `template_source`, Syntaxprüfung und eigener Interpreter
  in `Program`, erlaubte Operatoren und Funktionen in `BINOPS`, `FUNCTIONS` usw.
- [primitives/templates.py](../primitives/templates.py): abstrakte Templates,
  Parameterbedingungen und Konkretisierung.
- [primitives/synthesis.py](../primitives/synthesis.py): Übersetzung der
  festen Bitoperationen in NAND-Gatter.

Die Implementierung nutzt Pythons AST-Parser nach der Umformung der
Template-Klammern. Anschliessend akzeptiert und interpretiert sie nur die
ausdrücklich unterstützten Konstrukte; sie führt den Quelltext nicht mit
Python-`eval` oder `exec` aus.

# Aufgabenliste: weitere generative Templates

Diese Liste beschreibt mögliche nächste Implementierungen. Offene Punkte sind
noch nicht umgesetzt. Die Standardlösungen der vier Grundrechenarten für
unabhängige Eingangsbreiten sind in [STANDARD-ARITHMETIK.md](STANDARD-ARITHMETIK.md)
dokumentiert. Vorhandene rekursive Templates bleiben eigene Beispiele.

## Gemeinsame Abnahme für jedes neue Template

- [ ] Symbolische Schnittstelle, Parameterbedingungen und dokumentierte Semantik.
- [ ] Editierbare `.prim`-Quelle und abstraktes Template, strukturell nach NAND übersetzbar.
- [ ] Konkrete Instanzen für Datenbreiten 1, 2 und 4; bei mehreren unabhängig
  breiten Datenoperanden alle neun Kombinationen, soweit fachlich sinnvoll.
- [ ] Bei zusätzlichen Parametern passende kleine Kombinationen festlegen:
  beispielsweise Schiebeweite, Kanalzahl oder Polynombreite; ihre Bedeutung
  und mögliche exponentielle Grösse ausdrücklich dokumentieren.
- [ ] Wiederverwendbare F-Boxen und flache NAND-Netze mit Exporten und Gatterzahlen.
- [ ] Unabhängige Referenz und vollständige Eingabeprüfung der kleinen Instanzen,
  einschliesslich Null, Maximalwert und ungültiger Codes; grössere Instanzen
  nur mit ausdrücklich gekennzeichneten Stichproben und gezielten Grenzfällen.
- [ ] Einmalige Bibliotheksmigration mit Tests für bestehende Ordner,
  Benennungen, bessere Lösungen und gelöschte Beispiele.
- [ ] 128-Bit-Portgrenzen und 512-NAND-Gattergrenze beachten. Grössere Referenzen
  dürfen existieren; nicht übersetzbare Instanzen ausdrücklich kennzeichnen.

Die folgenden Prioritäten sind Vorschläge. Alle Aufgaben sind voneinander
getrennt umsetzbar, sofern die genannten Abhängigkeiten verfügbar sind.

## Priorität 1: Bitposition und Verschiebung

- [x] **GEN-01 – CLZ / CTZ:** Führende bzw. nachlaufende Nullbits durch rekursive
  Halbierung zählen. Für a=0 ist das Ergebnis t; `LOG2(t)+1` Ausgangsbits bei
  Zweierpotenzbreiten. Abhängigkeiten: ISZERO, Auswahl und Indexaddition.
  Umgesetzt: t=1,2,4 vollständig geprüft (44 Fälle), grössere Referenzen bis 128 Bit
  mit Grenzfällen/Stichproben. F-Boxen, NAND-Exporte und einmalige Migration vorhanden.
  Siehe [CLZ/CTZ](CLZ-CTZ.md).
- [x] **GEN-02 – Prioritätsencoder:** Index des niedrigsten gesetzten Bits plus
  valid-Bit; vorhandenes maximales Bitindex-Template als Gegenstück dokumentieren.
  Für a=0: Index=0, valid=0; Mehrfachbelegung wählt den kleinsten Index.
  Prüfen: t=1,2,4 mit allen Bitmustern; Ausgangsbreite mindestens ein Bit.
  Umgesetzt: `PE<t>` mit kompakter Indexbreite max(1,LOG2(t)); alle 22 kleinen
  Eingabefälle vollständig geprüft. Rekursive F-Boxen, NAND-Exporte, grössere
  Referenzen/Grenzfälle bis 128 Bit und einmalige Migration vorhanden.
  Siehe [Prioritätsencoder und Gegenstück m<t>](PRIORITAETSENCODER.md).
  Nächste offene Template-Aufgabe: GEN-03.
- [ ] **GEN-03 – Decoder / One-Hot:** w-Bit-Code ergibt 2**w Ausgangsbits,
  optional enable. Auch die Umkehrung mit valid und multiple für ungültige
  One-Hot-Eingaben definieren. Prüfen: w=1,2,4 und sämtliche Eingaben,
  einschliesslich Null- und Mehrfachbelegung beim Encoder.
- [ ] **GEN-04 – Barrel-Shifter:** SHL, SHR und vorzeichenerweiterndes SAR mit
  variablem Schiebeeingang über feste MUX-Stufen. Bei s>=t wird SHL/SHR null,
  SAR wiederholt das Vorzeichenbit. Prüfen: Datenbreite t=1,2,4 und
  Schiebeportbreite s_bits=1,2,4; alle neun Kombinationen vollständig.
- [ ] **GEN-05 – Rotieren:** ROL/ROR mit variablem Abstand modulo t;
  t=1 ist Identität. Gemeinsam nutzbare MUX-Stufen mit GEN-04 untersuchen.
  Prüfen: dieselben neun Breitenkombinationen und Rotations-Inversen.

## Priorität 2: Rechnen und Präfixnetze

- [ ] **GEN-06 – Präfix-AND / Präfix-XOR:** Ergänzung zum vorhandenen PREFIX_OR;
  jeweils inklusive Präfixe ab Bit 0. Präfix-XOR ist damit anders orientiert
  als die Gray-Dekodierung. Prüfen: t=1,2,4 vollständig.
- [ ] **GEN-07 – Carry-Lookahead / Parallelpräfix-Addition:** Generate-/Propagate-
  Netz mit vollständiger Summe und Carry; Vergleich von Tiefe und NAND-Zahl
  mit dem Ripple-Carry-Standard. Prüfen: alle neun Operandenbreiten und jeden Carry.
- [ ] **GEN-08 – Sättigungsarithmetik:** Unsigned SAT_ADD begrenzt auf
  `2**max(p,q)-1`, SAT_SUB auf 0; zusätzlich overflow bzw. underflow ausgeben.
  Prüfen: alle neun Breitenkombinationen einschliesslich exakter Grenze.
- [ ] **GEN-09 – Vorzeichen, NEG und ABS:** Zweierkomplement-Negation und
  Absolutwert; beim kleinsten negativen Wert ein Overflowbit vorsehen und
  die Ergebnisdarstellung festlegen. Prüfen: t=1,2,4 vollständig.
- [ ] **GEN-10 – Signed Vergleiche und Grundrechenarten:** Vorzeichenbehandlung
  als explizite Bitlogik; Division gegen null und der Sonderfall
  kleinster negativer Wert / -1. Vor Implementierung Ausgangsbreiten und
  Fehlerflags festlegen. Prüfen: alle neun Kombinationen aus 1,2,4 Bit.
- [ ] **GEN-11 – Andere Multiplikationsverfahren:** Array-/Wallace-Teilprodukt-
  Reduktion mit vollständigem Produkt; Gatterzahl und Tiefe gegen
  Schiebe-Addier-Standard und rekursive Multiplikation vergleichen.
  Prüfen: alle neun kleinen Breitenkombinationen, keine Minimalitätsbehauptung.

## Priorität 3: Komposition und Codes

- [ ] **GEN-12 – Sortiernetz:** Zweiwert-Sortierer zu einem Bitonic- oder
  Odd-Even-Netz für 2**k Kanäle à n Bits zusammensetzen. Kleine Kombinationen
  vollständig prüfen, etwa zwei Kanäle mit n=1,2,4 und vier Kanäle mit n=1,2;
  grössere Eingaberäume als Stichprobe kennzeichnen. Aufsteigende Ausgabe
  und Erhaltung des Eingabemultisets prüfen. Abhängigkeit: SORT2.
- [ ] **GEN-13 – Hamming-Distanz:** XOR zweier gleich breiter Datenwörter und
  NumberOfOnes; bei ungleichen Breiten Nullerweiterung auf max(p,q).
  Prüfen: alle neun Breitenkombinationen, Symmetrie und Abstand null.
- [ ] **GEN-14 – Paritätsgenerator und Paritätsprüfung:** Gerade/ungerade Parität
  als Codier-/Prüfpaket mit zusätzlichem Paritätsbit. Vorhandenes PARITY nutzen.
  Prüfen: t=1,2,4 vollständig und sämtliche einzelnen Bitfehler.
- [ ] **GEN-15 – Hamming-Code:** Zunächst explizites Hamming(7,4)-Template mit
  Syndrom und Einzelbitkorrektur; optionale SECDED-Erweiterung separat definieren.
  Alle 16 Nutzwörter und alle Einzelfehler prüfen; Mehrfachfehlergrenzen dokumentieren.
- [ ] **GEN-16 – CRC / LFSR-Schritt:** Feste XOR-Netze mit statischem Polynom,
  Registerbreite und klarer Bitreihenfolge. Zunächst kombinatorischer Einzelschritt,
  anschliessend feste Blocklänge; Zustand als Eingangs-/Ausgangsport.
  Prüfen: kleine Register- und Blockbreiten vollständig gegen unabhängige
  Polynomdivision. Keine getaktete Registerhardware im kombinatorischen Template.

## Bereits ergänzt

- [x] Vier Standardverfahren für unsigned Addition, Subtraktion, Multiplikation
  und Division mit Rest; unabhängige Eingänge a[p], b[q].
- [x] Alle 36 Instanzen für p,q=1,2,4 mit NAND-Netzen, Bausteinen, vollständigen
  Tabellen und unabhängiger Prüfung aller 1936 Eingabefälle.
- [x] Automatische einmalige Ergänzung unter Beispiele → Grundrechenarten →
  Standardlösungen (1, 2, 4 Bit).

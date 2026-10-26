# Schaltungen bearbeiten und Logisim anbinden

Prüfstand: 26. Oktober 2026. Die Codeprüfung erfasst die vorhandene
Verdrahtungsansicht, das NAND-Datenmodell und die Import-/Exportwege.
Für Logisim-evolution wurden die offiziellen Format- und Komponentensourcen
geprüft. Ein praktischer `.circ`-Roundtrip ist noch nicht implementiert oder
als bestanden getestet.

## Bereits verfügbar: das Ergebnis wirklich ändern

Unter **Schaltbild → NAND-Schaltung bearbeiten oder importieren** liegt ein
JSON-Editor für die geöffnete Schaltung. Dort können Gatteranschlüsse,
Gatterliste und Ausgangsverweise geändert werden. **Prüfen & im Schaltbild
anzeigen** prüft Struktur und, falls zugeordnet, sämtliche Sollvektoren.
Die simulierte Schaltung und der angezeigte Prüfstatus werden neu berechnet.

```json
{"inputs": 2, "gates": [[0, 1], [2, 2]], "outputs": [3]}
```

Hier sind 0 und 1 die Eingänge, Gatter 2 ist NAND(0,1), Gatter 3 ist
NAND(2,2); Ausgang 3 liefert AND. Alle Nummern sind nullbasiert.
Ein Gatter darf nur Eingänge und frühere Gatter verwenden. Höchstens
512 Gatter, 32 Eingangs- und 32 Ausgangsbits sind erlaubt. Beim Entfernen
oder Einfügen von Gattern müssen spätere Verweise entsprechend angepasst werden.

Die Änderung ist ein **manueller Entwurf**. Die bisher gespeicherte Suchlösung
bleibt erhalten. Ein altes Suchprotokoll, eine alte Abstammung, Korrekturangaben
oder eine unpassende Bausteinhierarchie werden dem Entwurf nicht zugeschrieben.
Eine Stichprobe bleibt eine Stichprobe. Der JSON-Export erhält die geänderte
Schaltung und ihren zugeordneten Datensatz; der separate Schaltungsimport unter
Schaltbild stellt sie wieder her und prüft erneut. Ohne Sollvektoren wird nur
die Struktur geprüft.

Zum dauerhaften lokalen Aufbewahren kann der Entwurf unter **Bausteine →
Geöffnete Schaltung als Baustein speichern** gesichert werden. Alternativ
JSON exportieren. Das Schliessen oder Neuladen der Browserseite verwirft
einen ungesicherten Entwurf. Der normale Vektorimport lädt weiterhin nur
die Aufgabe; für eine exportierte Schaltung den Schaltungsimport verwenden.

Das Ziehen von Boxen und Leitungssegmenten verändert weiterhin das Layout.
Ein direktes Umstecken im Diagramm ist eine eigene, noch offene Erweiterung.

## Bewertung und sinnvolle Reihenfolge

| Weg | Machbarkeit und Nutzen | Priorität |
|---|---|---|
| Gatterliste in der Anwendung editieren | Verwendet das vorhandene NAND-Modell, die Simulation und Vektorprüfung. Bereits umgesetzt; als erster Schritt sofort nutzbar. | 1 |
| Logisim-evolution `.circ` exportieren | Ein NAND wird eine NAND-Komponente; bitweise Pins erhalten feste Namen. Zunächst flach exportieren. Ermöglicht Bearbeitung mit dem bestehenden Logisim-Editor. | 2 |
| Begrenzter `.circ`-Rückimport | Zunächst das eigene Exportprofil: Pins, zweieingängige Ein-Bit-NANDs, Drähte und Tunnel. Netze rekonstruieren, Treiber prüfen, topologisch sortieren, danach Sollvektoren prüfen. Erst damit entsteht der vollständige externe Bearbeitungszyklus. | 3 |
| Anschlüsse direkt im Schaltbild umstecken | Für häufige kleine Korrekturen komfortabel. Braucht Anschlussauswahl, Zyklusprüfung, stabile Knotenkennungen, Rückgängig/Wiederholen und eine Entwurfsverwaltung. | 4 |
| Allgemeiner Logisim-Import | Weitere Gatter nach NAND übersetzen, Busse auflösen und Unterbausteine expandieren. Wesentlich mehr Komponenten- und Fehlersituationen. | später |

Für viele externe Änderungen sollte der begrenzte Rückimport gleich mit dem
Export folgen. Ein Export allein ermöglicht Bearbeitung in Logisim, aber noch
keine Rückübernahme in Primitives. Wer hauptsächlich einzelne Leitungen
korrigieren möchte, kann die direkte Anschlussbearbeitung vor den allgemeinen
Import ziehen.

## Warum Export einfacher ist als Import

Der offizielle [XmlWriter](https://github.com/logisim-evolution/logisim-evolution/blob/main/src/main/java/com/cburch/logisim/file/XmlWriter.java)
schreibt Bibliotheken, Schaltungen, Komponentenattribute und Drähte in die
Projektstruktur. Das ist ein geeignetes Zielformat für ein begrenztes Exportprofil.
Die offiziellen [NAND-Komponente](https://github.com/logisim-evolution/logisim-evolution/blob/main/src/main/java/com/cburch/logisim/std/gates/NandGate.java)
und [Gattergrundklasse](https://github.com/logisim-evolution/logisim-evolution/blob/main/src/main/java/com/cburch/logisim/std/gates/AbstractGate.java)
liefern die Komponentenkennung und die Anschlussgeometrie.

Ein Exporter kann bekannte Eingangspins, NAND-Gatter mit expliziter Breite,
Ausrichtung und Gattergrösse sowie Ausgangspins platzieren. Beschriftete Tunnel
würden komplexe Leitungsführung vermeiden. Die erste Version sollte jeden Port
bitweise mit eindeutigen Labels ausgeben; Bus-Splitter und optisch identische
Browserlayouts können später folgen. Die vorhandenen Hierarchien lassen sich
zunächst verlustfrei auf ihre NAND-Funktion abflachen, aber ihre Boxstruktur
wäre dabei nicht erhalten.

Ein Importer muss dagegen aus geometrischen Drähten und Anschlüssen das
elektrische Netz rekonstruieren. Dabei müssen Abzweigungen, Tunnel,
Bauteilausrichtungen, mehrfache Treiber, offene Pins, Pinreihenfolge und Zyklen
explizit behandelt werden. Fremde Komponenten dürfen nicht stillschweigend
ignoriert werden. Ein eigenes, dokumentiertes Exportprofil begrenzt diese Arbeit.
AND, OR, NOT und XOR können anschliessend über bekannte NAND-Identitäten
ergänzt werden. Externe Bibliotheken sollten zunächst abgelehnt werden.

Register, Flipflops, Takte, undefinierte bzw. hochohmige Signale und
Rückkopplungen passen nicht direkt zum aktuellen kombinatorischen 0/1-Modell.
Sie benötigen ein Zustands- und Zeitmodell oder eine klare Importablehnung.

## Abnahmekriterien für die nächste Logisim-Etappe

1. Exportierte Dateien in der lokal installierten Logisim-evolution-Version
   öffnen; doppelte NAND-Eingänge, direkte Ausgänge, Fan-out und mehrere
   Ausgangspins praktisch testen.
2. Für NAND, XOR und einen kleinen Addierer die Wahrheitstabellen vor Export
   und nach Rückimport vollständig vergleichen. Die offizielle
   [Testvektor-Spezifikation](https://github.com/logisim-evolution/logisim-evolution/blob/main/docs/test_vector.md)
   ermöglicht zusätzliche Prüfdateien mit denselben Pinlabels.
3. In Logisim tatsächlich Gatter umverdrahten, speichern, zurückimportieren
   und den geänderten Prüfstatus in Primitives nachweisen.
4. Unbekannte Bauteile, Zyklen, mehrere Treiber und Breitenkonflikte mit einer
   konkreten Fehlermeldung ablehnen; die geöffnete Schaltung dabei erhalten.
5. Ein solches Ergebnis als manuellen Entwurf speichern. Alten Suchstatus
   niemals aus dem ursprünglichen Export übernehmen.

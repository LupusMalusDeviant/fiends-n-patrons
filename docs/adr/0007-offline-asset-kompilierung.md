# ADR-0007: Offline-Asset-Kompilierung in binäre Packs (mit Dev-Hot-Swap über den Live-Link)

- **Status:** Akzeptiert
- **Datum:** 2026-09-14
- **Entscheider:** Lupus Malus Deviant (PO)
- **Bezug:** [PRD-0016](../prd/0016-tooling-suite.md), [PRD-0002](../prd/0002-grimoire-engine-architektur.md)

## Kontext

Assets entstehen in Quellformaten (glTF aus Blender-Skripten, `.sigil`, Templates, Tuning-Daten,
Texte, Audio-Rezepte). Die Engine könnte Quellformate zur Laufzeit laden (einfach, langsam,
Parser-Ballast) oder ausschließlich vorkompilierte Binärdaten (schnell, sauber, aber
Iterations-Frage). Gleichzeitig existiert ohnehin ein Live-Debug-Link zwischen Tooling und Engine.

## Anforderungen

- Schnelles, allokationsarmes Laden (Raumwechsel ohne Spike, Mobile-Zukunft).
- Validierung als hartes Gate VOR der Laufzeit (kein „Parse-Fehler beim Spielen").
- Iterationsschleife in Sekunden trotz Kompilierschritt.
- Klare Trennung: Parser/Import-Komplexität gehört ins Tooling, nicht in die Engine.

## Optionen

1. **Laufzeit-Laden der Quellformate** — kein Build-Schritt, aber glTF-/Parser-Ballast in der Engine, langsames Laden, Validierung erst zur Laufzeit.
2. **Hybrid (Dev lädt Quellen, Release lädt Packs)** — beste Iteration, aber zwei Ladepfade = doppelte Wahrheit, Dev/Release-Divergenz-Bugs.
3. **Nur Packs + Hot-Swap über Live-Link (gewählt)** — Engine kennt ausschließlich das Pack-Format; Iterationstempo liefert der Debug-Kanal, der einzeln kompilierte Assets in die laufende Engine injiziert.

## Entscheidung

Option 3. Der C#-Asset-Compiler validiert und kompiliert alle Quellen in versionierte Packs
(Manifest mit Hashes und Versionen); `grimoire_assets` lädt nur Packs. Im Dev-Modus kompiliert
das Tooling geänderte Einzel-Assets inkrementell und schiebt sie über den Live-Link (PRD-0002
FR-10/FR-11) in die laufende Engine — ein Ladepfad, trotzdem Sekunden-Iteration.

## Konsequenzen

- (+) Ein einziger, schneller Ladepfad in Dev und Release; Validierung ist CI-Gate; Engine bleibt frei von Import-Bibliotheken.
- (+) Pack-Manifest liefert Reproduzierbarkeit (Asset ↔ Rezept ↔ Renderer-Version, PRD-0012 NFR).
- (−) Ohne laufendes Tooling kostet eine Asset-Änderung einen Pack-Teilbuild (< 60 s Ziel) — akzeptiert.
- (−) Inkrementeller Compiler + Hot-Swap-Protokoll sind Zusatzaufwand im Tooling — bewusst dorthin verlagert, wo C#-Produktivität hilft.

# assets_src/

Generatoren für 3D-Modelle: Blender-Python-Skripte pro Asset-Typ (Charakter, Gegner, Boss, Props),
die headless glTF gemäß Stilbibel erzeugen (PRD-0016 FR-09, ab P3).

| Ordner | Inhalt |
|---|---|
| [`figures/`](figures/README.md) | Die drei geriggten Figuren (Imp, Verdammte Seele, Brute): Modell, Texturen, Backen, Export |
| [`figure_pack/`](figure_pack/README.md) | Konverter von geriggten `.glb` in das Pack-Format der Engine (PNG und JPEG, exaktes Verkleinern) |
| [`asset_import/`](asset_import/README.md) | Import fremd erzeugter Figuren (Hi3D, geriggte Kopien): Budget-Prüfung und Vorbereitung zur Spielfigur |
| [`textures/`](textures/README.md) | Materialpaket der Look-Testszene; Grundtexturen, auf denen die Figuren aufbauen |
| [`player_models/`](player_models/README.md) | Drei Entwürfe für Spielerfiguren mit Nahkampfwaffen |

Versioniert sind nur Skripte, Kataloge und Beschreibungen. Erzeugte Bilder, `.blend`- und
`.glb`-Dateien sind in jedem Ordner ignoriert.

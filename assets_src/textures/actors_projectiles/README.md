# Monster, Spieler und gotische Projektile

**Stand:** zwölf zusätzliche PBR-Materialien und acht neu gestaltete
Projektilsprites. Die Ausgabe liegt in **1024 × 1024 Pixeln** unter `master/`,
die kleine geprüfte Vorschau unter `preview_gothic/` in 128 Pixeln.

Die Projektile zeigen Gegenstände mit Naturmaterialien und Magieakzenten:
Holzschäfte, Rabenfedern, Stahlspitzen, Knochen, Metallfassungen und Alchemieglas.
Die Teamzuordnung ist ein Entwurf; sie legt keine Angriffsregeln fest.
Der bestehende petrolfarbene Spielerumhang bleibt unverändert.

## Vorschauen und Dateien

- `master/projectiles/projectile_sheet.png`: alle acht Entwürfe groß sowie
  bei 32, 48 und 64 Pixeln. Die kleinen Abbildungen bei 100 % Ansicht prüfen.
- `master/materials/actor_materials.png`: zwölf Oberflächen; links reine Farbe,
  rechts eine neutrale, beleuchtete Flächenstudie. Kein Blender-/Engine-Render.
- Je Figurenmaterial: BaseColor, OpenGL-Normalen, ORM, Parameter-JSON und
  eine exakte 2×2-Kachelvorschau.
- Je Projektil: transparentes RGBA-PNG und Parameter-JSON. Die vollständigen
  Dateilisten mit SHA-256 und Größen stehen in den beiden Manifesten.

Die frühere geometrische Projektilausgabe in `preview/` ist überholt.
Aktuell sind `master/` und `preview_gothic/`. `design_study/` enthält nur eine
lokale Zwischenansicht; für die Übergabe die aktuellen Master verwenden.

## Figurenmaterialien

| Verwendung | Material | Merkmal |
|---|---|---|
| Monster | `demon_horn` | Breite Wachstumsringe und Längsrillen |
| Monster | `plague_hide` | Unregelmäßige Schwellungen und Hautfalten, ohne helle Pustelpunkte |
| Monster | `charred_carapace` | Verkohlte Platten und breite Bruchfugen, ohne Glut |
| Monster | `exposed_sinew` | Gerichtete Sehnenbündel und querlaufende Gewebebänder |
| Monster | `void_hide` | Matte, kühle Membran mit weichen Spannungsfalten |
| Monster | `bone_armor` | Knochenlamellen und verwachsene Nähte |
| Spieler | `player_leather` | Gefärbtes Leder mit Druckfalten |
| Spieler | `player_wraps` | Überlappende, cremefarbene Stoffbänder |
| Spieler | `player_steel` | Bearbeiteter Rüstungsstahl |
| Spieler | `player_inner_cloth` | Dunkler Futterstoff mit breiten Falten |
| Spieler | `player_silver_trim` | Metallbeschläge mit flachen Gravuren |
| Spieler | `player_blade` | Klingenstahl mit gerichteten Schleifspuren |

Farben, Materialwerte, Seeds und physische Kachelgrößen stehen in
`catalog.json`. Alle Oberflächen sind Figurenmaterialien. Helle Metalle und
Stoffe daher nicht ungeprüft auf großen Umgebungsflächen einsetzen.
Rauheit und Relief werden auf mittlere Details begrenzt. Modellkonturen,
Hornform, Klingenfase und anatomische Volumen entstehen weiter im Blender-Mesh.

Für PBR gilt der Vertrag des Elternpakets: BaseColor ist reine Materialfarbe,
Normalen sind Tangentenraum/OpenGL/+Y, ORM enthält R=AO, G=Rauheit, B=Metall.
Keine Beleuchtung oder AO in BaseColor; glTF-Faktoren auf 1 belassen, da die
Werte bereits in den Bildern stehen. Alle Figurenmaterialien kacheln.

## Acht Projektilentwürfe

| ID | Motiv | Vorgeschlagenes Team | Signalakzent |
|---|---|---|---|
| `hunter_arrow` | Befiederter Jagdpfeil mit blattförmiger Stahlspitze | Spieler | Eis-Cyan |
| `barbed_arrow` | Pfeil mit rückwärts gerichteten Widerhaken | Gegner | Magenta |
| `crossbow_bolt` | Schwerer Bolzen mit verstärktem Schaft | Gegner | Limette |
| `bone_lance` | Gebundene Knochenlanze mit Markkanal | Gegner | Magenta |
| `plague_flask` | Pestphiole mit Eisenkäfig, Reagenz und Totenkopfsiegel | Gegner | Limette |
| `reliquary_bomb` | Sargförmiges Reliquiar mit Spitzbogenfenster und Wachssiegel | Gegner | Magenta |
| `censer_bomb` | Gotisches Räucherfass mit Kette und Glutfenstern | Gegner | Magenta |
| `alchemical_grenade` | Facettierte Glasampulle mit Stahlfassung und Alchemiesiegel | Spieler | Eis-Cyan |

### Darstellung und Alpha

Die Projektile sind **illustrierte Unlit-Sprites**, keine 3D-Modelle und keine
PBR-BaseColor-Texturen. Ihre gezeichneten Metallfacetten und Glasreflexe gehören
zum fertigen Spritebild. Diese gestalterische Schattierung wird nicht in die
PBR-Materialien übernommen. Für echte 3D-Projektile wären passende Meshes und
UVs sowie ein eigener PBR-Materialaufbau erforderlich.

- RGBA8: RGB in sRGB, Alpha als lineare Flächenabdeckung, **straight alpha**.
  Transparente Texel haben RGB=0. Filterung muss trotzdem alpha-aware erfolgen.
- Mindestens 8 % transparenter Rand, auf ganze Pixel aufgerundet. Kleine
  Ausgaben werden nach Lanczos-Filterung vom schwachen Rand-Ringing bereinigt.
- Clamp-to-edge, keine Kachelung. Noch keine Mipmaps, Atlanten oder Kompression.
- Pfeilspitzen zeigen nach +X. Bomben sind aufrechte Gegenstandsansichten ohne
  Flugrichtungsachse. Drehpunkt ist UV (0,5; 0,5).
- Der geschützte Projektilpass rendert nach Welt-Postprocessing, ohne weitere
  Szenenbeleuchtung und ohne globalen Bloom. Das ist ein Übergabevertrag;
  die Engine-Integration ist hier nicht implementiert.
- Die reservierten Teamfarben sitzen in Einlagen, Flüssigkeiten, Siegeln und
  Bombenkonturen. Sie sind ausschließlich für diese Projektilbilder gedacht.
- **48 Pixel Canvas-Ausdehnung** ist die vorläufige Mindestempfehlung für alle
  acht Entwürfe; 64 Pixel zeigen mehr Materialdetails. Bei 32 Pixeln werden
  besonders die Pfeilschäfte und schmalen Teamakzente sehr schwach. Die Tafel
  zeigt diese Grenze ausdrücklich. Padding zählt zur Canvas-Ausdehnung.
- Hitbox, Schaden, Flugkurve, Homing und Waffenverfügbarkeit werden nicht durch
  die Bilddateien festgelegt. Lesbarkeit in Bewegung ist noch zu prüfen.

## Wiederholbar erzeugen

Die Abhängigkeiten sind in der `requirements.txt` des Elternordners gepinnt.
Im Ordner dieser README ausführen:

```sh
python -B build.py
python -B build.py --master
```

Der erste Befehl erzeugt `preview_gothic/` mit 128 Pixeln; der zweite `master/`
mit 1024 Pixeln. Beide Läufe prüfen ihre eigene Ausgabe und ersetzen
vorhandene gleichnamige Build-Dateien. Die Erzeugung ist seriell, nutzt einen
numerischen Thread und unter Windows Idle-Priorität. Kein GPU-/Blender-Aufruf,
keine Downloads und keine externen Bilddienste.

`actor_surfaces.py` erzeugt die periodischen Oberflächen mit festem Seed.
`arrow_art.py` und `bomb_art.py` zeichnen die Objektformen deterministisch mit
Pillow/NumPy. `projectiles.py` enthält Motive, Teamfarben und den Alphavertrag.
`build.py` erzeugt PNGs, Vorschautafeln, Parameter, Manifeste und Prüfberichte.

## Prüfungen und Übergabe

128er-Preview und 1024er-Master haben bestanden:

- zwölf PBR-Materialien: RGB8, Kanalverträge, Normalenlänge, Zielmittelwerte,
  Randgradienten, Metall-Binärwerte, 2×2-Inhalte und Manifest-Prüfsummen;
- acht Sprites: RGBA8, transparenter Rand, deckende Flächen,
  Silhouettenabdeckung und bitidentische erneute Sprite-Erzeugung;
- zusätzlicher Alpharandtest der acht Motive bei 16, 24, 32, 48 und 64 Pixeln;
  dieser technische Test bestätigt keine Lesbarkeit in diesen Größen;
- alle PNGs: ausschließlich IHDR/IDAT/IEND und gültige CRCs.

Berichte stehen jeweils in `materials/validation.json`,
`projectiles/validation.json` und `build_info.json` unter dem Ausgabeordner.
`build_info.json` hält Auflösung und Quell-Prüfsummen fest. Es gibt keinen
Blender-/Spieltest und keine Garantie für Kontrast oder Flimmerfreiheit.
Die erneute identische Sprite-Erzeugung ist kein doppelter Build-Nachweis der
zwölf PBR-Materialien; deren Datei-Hashes sind im Manifest erfasst.

Alle Muster sind prozedurale Originale. `external_sources` ist leer; es gilt
der Verweis auf die Projektlizenz. Keine fremden Quellen werden als CC0
umdeklariert. Die Metadaten enthalten keine privaten Rechnerdaten oder
absoluten Pfade; es werden keine Blender-Dateien erzeugt.

Für einen geprüften Commit gehören zusätzlich zum Elternpaket diese Quellen
dazu: `.gitignore`, `actor_surfaces.py`, `arrow_art.py`, `bomb_art.py`,
`projectiles.py`, `build.py`, `catalog.json` und diese README. Alle genannten
Ausgabeordner sind ignoriert. Codex führt keinen Commit oder Push aus.

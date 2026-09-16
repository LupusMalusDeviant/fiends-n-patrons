# Drei Spielermodelle – Fiends n Patrons

Drei prozedurale **3D-Asset-Prototypen** mit eingebetteten PBR-Texturen,
gemeinsamem Skelett, vier ersten Bewegungsclips und lokalen Blender-Dateien.
Die Bilder sind echte Eevee-Render dieser Geometrie.

## Modelle

| Arbeitsname | Datei unter `generated/` | Visueller Schwerpunkt | Dreiecke |
|---|---|---|---:|
| Eiserner Büßer | `iron_penitent/iron_penitent.glb` | Breite Rüstung, geschlossener Helm, Bußketten und schwere Klinge | 17.760 |
| Aschenläufer | `ash_reaver/ash_reaver.glb` | Schmale Kapuze, Knochenmaske, kurzer asymmetrischer Umhang und Sichel | 13.668 |
| Schleierhüter | `veil_warden/veil_warden.glb` | Verhüllter Ritualkämpfer mit Knochengorget, langer Stola und Klingenstab | 16.692 |

Je Modell gibt es außerdem `<id>.blend`, `<id>.json` und Ansichten von vorne,
hinten und aus etwa 65 Grad. Die GLBs sind ohne separate Bilddateien importierbar.
Die `.blend` enthält gepackte Texturen, Rig und eine kleine Vorschau-Lichtbühne;
die Lichtbühne ist nicht im GLB enthalten. Alle generierten Dateien sind ignoriert.

Übersichten:

- `generated/player_models.png`: drei Figuren mit Rück- und Topdown-Ansichten.
- `generated/walk_cycle.gif`: kurze Laufstudie aus den Blender-Dateien.
- `generated/melee_poses.png`: fünf Posen des ersten Nahkampf-Blockings je Figur.

## Ableitung aus den Dokumenten

- [PRD-0005](../../docs/prd/0005-kampfsystem-spieler.md), FR-15/16:
  kuratierte Nahkampf-Presets mit unterschiedlicher Waffe und Silhouette;
  schwere Klinge und schnelle Sichel sind dort Beispiele.
- Das PRD nennt bisher **zwei** Figuren. Ihre Identitäten stehen in OF-5.1
  offen. Der Nutzer hat **drei Modelle** angefordert; der Klingenstab-Kämpfer
  ergänzt deshalb die beiden Kontrasttypen als dritter visueller Entwurf.
  Namen, dritte Rolle und Ausrüstung sind keine freigegebenen Klassenregeln.
- [PRD-0011](../../docs/prd/0011-narrativ-und-lore.md): düstere Aufstiegsgeschichte
  einer verdammten Seele. Masken, Bußketten und Reliquiare greifen diesen Rahmen
  auf; kein Modell legt Patronenzugehörigkeit oder endgültige Lore fest.
- [PRD-0003](../../docs/prd/0003-rendering-und-art.md) und
  [ADR-0014](../../docs/adr/0014-realistischer-3d-look-statt-toon.md): echte
  3D-Geometrie, PBR statt Toon, etwa 60–75 Grad Kamera und Lesbarkeit.
- [PRD-0016](../../docs/prd/0016-tooling-suite.md), FR-09: Blender-Python als
  reproduzierbare Quelle; glTF als Übergabeformat.

Die Grundformen sind bewusst klar und vereinfacht. Die Materialien verwenden
die vorhandenen 1024er-Texturen. Der petrolfarbene Umhang bleibt `#24505C`.
Rüstungsstahl bekommt eine ausdrücklich dokumentierte, kühle Eisentönung über
`baseColorFactor = [0.28, 0.30, 0.32, 1]`; die ursprünglichen Texturen bleiben
unverändert. Das ist eine Materialvariante, keine zweite Anwendung ihrer
ursprünglichen Grundfarbe. Es gibt keine Emission oder leuchtende Augen.

## Technischer Vertrag

- GLB 2.0, Meter; Blender +Z oben / -Y vorne, glTF +Y oben / +Z vorne.
- Je ein Skin mit **23 gleich benannten Knochen** und derselben Hierarchie.
  Körperproportionen und Bind-Positionen unterscheiden sich. Beim Übertragen
  von Animationen daher Rotation retargeten bzw. Bind-Matrizen berücksichtigen.
- Ein Mesh je Figur mit 8 bzw. 10 Material-Primitives. Körper und Waffen sind
  gemeinsam geskinnt; die Waffe ist dem Bone `weapon.R` zugeordnet. Ein separater
  Waffenwechsel benötigt später die Abtrennung dieser Geometrie.
- UVs, Normalen und normalisierte Gewichte; eingebettete PNGs in 1024 Pixeln.
  BaseColor sRGB, Tangentenraum-Normalen OpenGL/+Y, ORM linear mit R=AO,
  G=Rauheit, B=Metall. Material-AO ersetzt kein am Charakter gebackenes Kontakt-AO.
- `socket_weapon_r`: Griffrahmen für eine aufrechte GLB-Waffe mit +Y-Längsachse,
  einschließlich der vorgesehenen leichten Neigung nach außen. Metermaßstab.
- `socket_skillshot_l`: lokales glTF +Z zeigt in der Ruhepose nach vorne.
- Keine Mipmaps, LODs, Kompression, Kollisionsform oder Engine-Pack-Datei.
  Größen und Material-/Texturquellen stehen in den Modell-JSONs.

| Clip | Dauer | Stand |
|---|---:|---|
| `idle` | 2,00 s | Dezente Körper-/Kopf-/Stoffbewegung |
| `walk` | 1,00 s | Laufzyklus auf der Stelle |
| `melee` | 0,75 s | Erste Bewegungsskizze für Oberkörper und Waffenarm |
| `dash` | 0,50 s | Vorneigung und Beinstellung auf der Stelle |

Alle Clips beginnen bei Sekunde 0. Ihre Zeiten sind **keine Kampfparameter**.
Es fehlen finales Animationspolishing, Fuß-IK, echte Schwungbögen und
Hit-/Parade-Events. Stoff wird über Knochen bewegt; es gibt keine Stoffsimulation.
Die zwei Taschen zitieren das gemeinsame Zwei-Item-Kit, ohne Items festzulegen.

## Erzeugen und prüfen

Geprüft mit Blender **5.2.2 LTS**. Die normalen Python-Skripte nutzen die
Pillow-Version aus `../textures/requirements.txt`; der GLB-Validator verwendet
nur die Standardbibliothek. Zuerst müssen die beiden Textur-Masterpakete unter
`../textures/generated/` und `../textures/actors_projectiles/master/` existieren.

Im Ordner dieser README:

```sh
blender --background --factory-startup --threads 4 --python build.py -- --render
python -B validate.py
blender --background --factory-startup --threads 4 --python check_import.py
blender --background --factory-startup --threads 4 --python render_motion.py
python -B assemble.py
```

Ohne `--render` erzeugt `build.py` nur Modelle und Daten. `--character
iron_penitent` beschränkt den Build auf eine Figur; die Gesamtprüfung erwartet
weiterhin alle drei GLBs. Die Blender-Render nutzen die GPU. Wiederholte Läufe
überschreiben gleichnamige Ausgaben ausschließlich in `generated/`.

### Prüfungen

`validate.py` prüft GLB-Header/Buffer/Accessors, Dreiecksindizes, endliche
Koordinaten, Normalen, UVs, Skin-Gewichte, gemeinsame Knochenhierarchie,
Animationen, PNG-CRCs und PBR-Referenzen. Alle drei GLBs haben bestanden.

`check_import.py` importiert die tatsächlichen GLBs erneut in Blender und prüft
Rig, Bilder und deformierte Geometrie an fünf Zeitpunkten pro Clip. Sein
Prüfbericht enthält die Hashes der konkret geprüften GLBs. Die Prüfberichte
stehen in `generated/validation.json` und `generated/import_validation.json`.

`assemble.py` entfernt Metadaten aus den Render-PNGs, baut die Tafeln und
schreibt das Manifest mit Datei- und Quell-Prüfsummen. Für eine aktuelle
Übergabe diesen Schritt nach den Prüfungen ausführen. Bitidentische GLB-Builds
über verschiedene Blender-Versionen werden nicht zugesichert.

**Noch offen:** Grimoire-Import, Spielkamera-Kontrast in der tatsächlichen Arena,
Animationsfeinschliff, Stoff-/Rüstungsdurchdringungen in endgültigen Kampfposen,
Kollisionskapsel und Laufzeit-Budget. Die Studio-Render ersetzen diese Tests nicht.

## Quellen und Repository

Geometrie, Verzierungen und Texturen sind prozedurale Originale. Es werden keine
Modelle, Bilder oder CC0-Assets heruntergeladen. `external_sources` ist leer;
es gilt die Projektlizenz. Texturquellen und SHA-256 stehen je Modell in der JSON.

Nur `.gitignore`, Python-Skripte, `catalog.json` und diese README sind Quellen
für die spätere Prüfung durch Claude. Keine privaten Pfade oder Rechnerdaten
stehen in den Metadaten der distributierbaren Dateien. `.blend` und etwaige
Blender-Sicherungen sind lokale Arbeitsdateien und bleiben ignoriert; sie sind
vom distributierbaren Manifest ausgenommen. Kein Git-Add, Commit oder Push
wurde ausgeführt; die PRDs und Claudes andere Dateien bleiben unangetastet.

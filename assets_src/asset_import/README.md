# asset_import/

Import fremd erzeugter 3D-Figuren (Hi3D-Downloads, geriggte Arbeitskopien) in das Pack der Engine.
Vier Stufen, erprobt am Hexen-Pilot: **Prüfen** (Stufe 1), **Vorbereiten** (Stufe 2), Packen,
Nachweis in der Engine.

- **Prüfen** misst eine `.glb` gegen die Grenzen der Engine, die Regeln des Konverters in
  [`../figure_pack`](../figure_pack/README.md) und das Budget ihrer Rolle. Nur
  Python-Standardbibliothek; den glTF-Container liest `../figure_pack/glb_reader.py`.
- **Vorbereiten** macht aus der geriggten Arbeitskopie und ihrem hochaufgelösten Original eine
  Spielfigur im Budget (Abschnitt „Stufe 2: Vorbereiten“). Blender headless, numpy und Pillow.
- **Packen** übernimmt der Konverter in [`../figure_pack`](../figure_pack/README.md), der dafür
  JPEG-Texturen und exaktes Verkleinern gelernt hat (Abschnitt „Stufe 3: Packen“).

## Stufe 1: Prüfen

### Aufruf

```sh
python -B check_asset.py --role player <figur.glb>
python -B check_asset.py --role enemy --json-out <bericht.json> <figur.glb>
```

Rollen: `player`, `enemy`, `boss`, `prop`. `--budgets <datei>` ersetzt `budgets.json`.

- **Ausgabe:** eine Zeile je Prüfung (`PASS`, `WARN`, `FAIL`, `INFO`) mit Messwert und Grenze,
  danach Texturen, Maße, Blickrichtung und Clips. `--json-out` schreibt den vollständigen Bericht
  mit allen Messwerten; er nennt die Datei nur beim Namen, nie mit Pfad.
- **Exit-Code:** 0 ohne `FAIL` (Warnungen erlaubt), 1 mit mindestens einem `FAIL`, 2 wenn die
  Figur oder die Budgetdatei nicht lesbar ist.
- **Laufzeit:** 0,2 bis 3 Sekunden für einen Hi3D-Download mit 2 Mio. Dreiecken und zwei
  8K-Texturen (langsamer, wenn die Positionen verschränkt gespeichert sind). Texturen werden nicht
  dekodiert; Größe und Format stehen im PNG- oder JPEG-Kopf. Gelesen werden nur die Positionen
  (für die Blickrichtung) und die inversen Bindematrizen.

### Was geprüft wird

| Ebene | Prüfungen | Herkunft der Grenze |
|---|---|---|
| `engine.*` | Vertices und Indizes je Teil, Pixel und Kantenlänge je Textur, Knochen je Skin, vier Einflüsse je Vertex, nur Dreiecke | Grimoire `v0.4.0`: `figure_format.rs`, `stage3d.rs`, `mesh.rs`, `max_texture_dimension_2d` des Software-Adapters |
| `pipeline.*` | lesbar (keine Sparse-Accessoren, keine Pflicht-Erweiterungen wie Draco), Bildformat, Material je Teil, Normalen, Tangenten bei UVs, gültige Tangentenwerte, höchstens ein Skin | Konverter `figure_pack` |
| `budget.*` | Dreiecke, Vertices, Teile, Rig, Knochen, Texturanzahl und -kante, geschätzter GPU-Speicher, Normalenkarte (Warnung), Clip-Namen (Warnung) | `budgets.json`, Rolle |
| `convention.*` | Höhe, Fußpunkt im Ursprung, Mitte über dem Ursprung (Warnung), Blickrichtung, Ruhepose gleich Bindepose (Warnung) | `budgets.json`, Abschnitt `pipeline` |
| `info.*` | Texturkanten als Zweierpotenz (Warnung), unbenutzte Bilder | – |

**GPU-Speicher** ist eine Schätzung nach dem heutigen Upload der Engine: jede Textur als RGBA8 mit
voller Mip-Kette (4/3 der Grundfläche, eine 8192er-Textur also 341 MiB), jeder Vertex 72 Byte, jeder
Index 4 Byte. Eine Blockkompression (OF-3.4) würde den Texturanteil etwa vierteln.

**Clip-Namen** sind nur eine Warnung: Ob und wie die Engine Clips abspielt, entscheidet ein eigenes
ADR. Bis dahin zeigt die Prüfung, welche erwarteten Namen fehlen und welche unbekannt sind.

### Budgets

Die Rollenbudgets in `budgets.json` sind ein **Vorschlag** und eine offene PO-Frage. Die PRDs
nennen keine Zahlen für Dreiecke, Texturen oder Knochen. Bindend sind dort nur die Rahmen:
100 aktive Gegner (PRD-0007), 8–12 Gegner-Archetypen (PRD-0007 FR-02), GPU-Frame ≤ 8 ms bei voller
Szene auf Desktop-Mittelklasse (PRD-0002, PRD-0003) und eine Spielkamera mit rund 35–65 px/m
(Stilbibel, Texturen).

| Rolle | Dreiecke | Vertices | Teile | Knochen | Texturen | Kante | GPU-Speicher | Höhe |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `player` | 20.000 | 20.000 | 8 | 64 | 4 | 2048 | 96 MiB | 1,5–2,1 m |
| `enemy` | 12.000 | 12.000 | 8 | 48 | 4 | 1024 | 24 MiB | 0,5–3,0 m |
| `boss` | 50.000 | 50.000 | 12 | 128 | 6 | 2048 | 160 MiB | 2,0–10 m |
| `prop` | 5.000 | 5.000 | 4 | 16 | 3 | 1024 | 20 MiB | 0,05–8 m |

Begründung:

- **Dreiecke:** Bei 35–65 px/m ist eine 1,8 m große Spielerfigur höchstens rund 120 px hoch, ein
  1 m großer Gegner rund 65 px. Schon 20.000 Dreiecke ergeben dort weniger als einen Pixel je
  sichtbarem Dreieck. Mehr Dreiecke verbessern die Silhouette nicht mehr, sie kosten nur
  Vertex-Arbeit, und die zählt bei 100 Gegnern und einem Schattenpass doppelt. Oberflächendetail
  kommt aus der Normalenkarte. Die Figuren der Runde 4 liegen bei 9.300 bis 10.800 Dreiecken.
- **Vertices:** so hoch wie die Dreiecke. glTF teilt Vertices an UV-Nähten und harten Kanten; ein
  Netz mit zerstückelten UVs liegt schnell bei drei Vertices je Dreieck.
- **Texturen:** eine Figur braucht drei Karten (Grundfarbe, ORM, Normalen), die vierte bleibt als
  Reserve. 2048 für Spieler und Bosse lässt Platz für Nahaufnahmen (Kamera-Momente, PRD-0003
  FR-04); für die Spielkamera allein genügen deutlich kleinere Karten. Welche Kante die Hexe
  bekommt, entscheidet die Vorbereitungsstufe durch Messung an der Spielkamera.
- **GPU-Speicher:** vier volle Karten der Kante plus Netz. Zwölf Gegner-Archetypen mit je 24 MiB
  belegen rund 290 MiB, mit Blockkompression rund 72 MiB.
- **Knochen:** Engine-Grenze 256. Der Spieler braucht Reserve für Umhang, Haar und Sockel (die Hexe
  hat 31), Gegner weniger.
- **Höhe:** nach `../figures/spec.py` (Imp 1,0 m, Verdammte Seele 1,8 m, Brute 2,4 m).

### Blickrichtung

glTF legt fest: +Y ist oben, die Vorderseite eines Modells schaut nach +Z. Die Prüfung bestimmt
die Blickrichtung auf zwei unabhängigen Wegen:

1. **Knochennamen:** Liegen Knochen mit linker Seitenkennung (`hand.L`, `thigh_l`, `LeftArm`) bei +X,
   schaut die Figur nach +Z. Setzt voraus, dass das Rig die Seiten anatomisch benennt.
2. **Zehen:** Die unteren 3 % aller Vertices liegen im Mittel vor dem Knöchelband bei 10–14 % der
   Höhe, weil Zehen weiter nach vorn reichen als die Ferse nach hinten. Nur für ±Z. An zehn
   vorhandenen Netzen (Hi3D-Downloads, ihre geriggten Kopien, die Figuren der Runde 4) stimmte das
   Vorzeichen jedes Mal, mit 2,2 bis 12 % der Höhe; unter 1,5 % gilt es als unbestimmt. Bodenlange
   Gewänder, Vierbeiner und schwebende Figuren können den Hinweis verfälschen.

Stimmen beide überein, gilt die Richtung als gesichert. Widersprechen sie sich, schlägt die
Prüfung fehl, und ein Frontbild entscheidet.

**Gemessener Widerspruch (offen):** `budgets.json` erwartet +Z, den glTF-Standard. Das ist die
Richtung aller Hi3D-Downloads, und `facing_yaw` in `crates/fnp_game/src/arena/present.rs` nimmt sie
an („authored front towards -Y“ in Engine-Achsen entspricht glTF +Z). Die Figuren der Runde 4
schauen aber nach -Z: Knochennamen und Zehen stimmen überein, eine Punktansicht zeigt das Gesicht
von -Z aus, und das Engine-Testbild der Runde 4 zeigt Rücken und Schwanz des Imps zur Kamera.
Entweder dreht der Prototyp die Figuren falsch herum, oder der Kommentar in `present.rs` stimmt
nicht. Das klärt eine Sichtprüfung im Spiel; bis dahin fallen die Figuren der Runde 4 in dieser
Prüfung durch.

## Stufe 2: Vorbereiten

### Aufruf

```sh
python -B prepare_figure.py --rigged <geriggt.glb> --high <hi3d.glb> --out-dir <ziel>
    --name witch --role player --height 1.8 --triangles 12000 --texture-size 1024
    --blender <blender>
python -B prepare_figure.py --rigged <imp_rig.glb> --high <imp_hi3d.glb> --out-dir <ziel>
    --name imp --role enemy --height 1.0 --triangles 5000 --texture-size 512 --swap-sides
    --blender <blender>
```

(Je Aufruf eine Zeile.) Voraussetzungen: Blender 5.2 LTS (`--blender` oder Umgebungsvariable
`BLENDER`), Python mit numpy und Pillow nach [`../textures/requirements.txt`](../textures/requirements.txt).
Blender läuft mit `-b --factory-startup -t 1`, ohne Fenster und ohne Grafikkarte.

Ausgaben in `--out-dir`: `<name>.glb`, drei PNG-Texturen (Grundfarbe, Metallic-Roughness,
Normalen), `<name>_prepare.json` (Messwerte der Vorbereitung), `<name>_check.json` (Stufe-1-Prüfung
der fertigen Figur), `<name>_blender.log` und `manifest.json` mit den SHA-256 aller Ausgaben außer
dem Protokoll. Schlägt die Prüfung der fertigen Figur fehl, endet das Skript mit Exit-Code 1.
`--texture-variants 512,2048` schreibt zusätzliche Texturgrößen für Vergleiche.

### Ablauf

1. **Texturen** (`prepare_figure.py`): Grundfarbe und Metallic-Roughness der geriggten Datei werden
   mit einem exakten Kastenfilter verkleinert, die Grundfarbe in linearem Licht wie die Mip-Kette
   der Engine.
2. **Import** (`blender_prepare.py`): geriggte Arbeitskopie (Skin, Knochen, Clips) und das
   Hi3D-Original; Knotentransformationen des Originals werden eingerechnet.
3. **Seiten tauschen** (`--swap-sides`): Knochen mit `.L`/`_l` und `.R`/`_r` tauschen die Namen,
   samt Vertex-Gruppen und Animationskanälen. Beim Imp-Piloten liegen die `.L`-Knochen auf der
   rechten Körperseite; nach dem Tausch stimmen Knochennamen und Zehenrichtung überein.
4. **Verschweißen und glätten** beider Netze. Die geriggte Hexe kommt flach schattiert an, jede
   Dreiecksecke ein eigener Vertex (299.984 Vertices für 100.000 Dreiecke). Das lag nicht an
   zerstückelten UVs: Position und UV zusammen unterscheiden nur 70.638 Vertices.
5. **Reduzieren:** Das Hi3D-Original wird auf die Zieldreiecke reduziert (Collapse-Decimate), die
   Skin-Gewichte werden vom geriggten Netz übertragen (nächste Fläche, interpoliert), auf vier
   Einflüsse begrenzt und normiert. Grund: Die geriggten Arbeitskopien sind rissig. Nach dem
   Verschweißen hat die Hexe 38.462 offene Kanten in 307 Stücken (nächster Randvertex im Median
   0,2 mm entfernt), der Imp 16.036 offene Kanten; die Originale haben keine. Größere
   Schweißabstände schließen die Risse nicht, sie zerstören Flächen (bei 1 mm fallen 5 % der
   Dreiecke weg, 6.635 offene Kanten bleiben). `--lod-source rigged` reduziert trotzdem die
   Arbeitskopie.
6. **Skalieren und aufstellen:** gleichmäßige Skalierung auf die Zielhöhe, tiefster Punkt auf den
   Boden, Mitte über den Ursprung, gemessen an der reduzierten Figur. Angewendet auf Netzdaten,
   Ruhepose, Ortskanäle aller Clips und das Original, nie als Objekttransformation.
7. **Tangenten:** Flächen mit einer Ecke, deren MikkTSpace-Tangente null wird, werden flach
   schattiert. Das Reduzieren faltet einzelne schmale Dreiecke um (je eine Ecke bei Hexe und Imp);
   deren glatte Normale liegt fast in der Dreiecksebene, und der Konverter verwirft die
   Null-Tangente zu Recht. Die Stufe-1-Prüfung meldet solche Tangenten (`pipeline.tangent_values`).
8. **Formnormalen** vom Original auf die reduzierte Figur mit `../figures/shapenormal.py`
   (nächster Oberflächenpunkt je Texel, MikkTSpace-Tangentenraum, kein Cycles-Bake).
9. **Export** als `.glb` mit Tangenten, allen Clips und den drei PNG-Texturen.

### Ergebnisse des Pilots

| | Hexe | Imp |
|---|---|---|
| Quelle | Hi3D 2.000.000 Dreiecke; Rig 100.000 Dreiecke, 31 Knochen, 18 Clips | Hi3D 2.000.000 Dreiecke; Rig 70.000 Dreiecke, 26 Knochen, 2 Clips |
| Spielfigur | 11.996 Dreiecke, **12.236 Vertices** | 5.000 Dreiecke, **3.661 Vertices** |
| Engine-Grenzen je Teil | 12.236 von 1.000.000 Vertices, 35.988 von 3.000.000 Indizes | 3.661 von 1.000.000, 15.000 von 3.000.000 |
| Höhe, Fußpunkt, Blickrichtung | 1,800 m, 0,000 m, +Z | 1,000 m, 0,000 m, +Z |
| Texturen | 3 × 1024², GPU 16,0 MiB (vorher 2 × 8192², 682,7 MiB) | 3 × 512², GPU 4,0 MiB (vorher 682,7 MiB) |
| Abstand zum Original (p50 / p99) | 0,75 / 3,8 mm | 0,75 / 2,8 mm |
| Gewichtsübertragung (Abstand p99) | 2,3 mm, kein Vertex ohne Gewicht | 3,1 mm, kein Vertex ohne Gewicht |
| Normalenfehler gegen Original, Median ohne / mit Karte | vorn 28,8° / 10,3°, hinten 31,1° / 8,2° | vorn 20,6° / 7,6°, hinten 20,3° / 7,5° |
| Gegenprobe mit umgedrehtem Grünkanal | vorn 35,7°, hinten 37,7° | vorn 24,3°, hinten 23,8° |
| Stufe-1-Prüfung | PASS, 30 von 30 | PASS, 29 von 30 und 1 Warnung (fehlende Clips) |

### Entscheidungen, gemessen

**Dreiecke nach Silhouette.** `render_game_view.py` zeichnet Original und Spielfigur mit vier
Abtastungen je Pixel an der Spielkamera des Prototyps; gemessen wird der Anteil der Deckung, der
abweicht.

| | 1080p | 2160p |
|---|---:|---:|
| Hexe 8.000 | 6,3 % | 5,9 % |
| **Hexe 12.000** | **5,2 %** | **4,4 %** |
| Hexe 18.000 | 4,8 % | 3,8 % |
| Hexe 18.000 aus der rissigen Arbeitskopie | 7,0 % | 6,2 % |
| **Imp 5.000** | **11,3 %** | **6,7 %** |
| Imp 7.500 | 11,0 % | 6,1 % |
| Imp 10.000 | 10,7 % | 5,8 % |

Jenseits von 12.000 (Hexe) und 5.000 (Imp) Dreiecken bringt die Hälfte mehr unter einen
Prozentpunkt. Der Imp ist an der Spielkamera rund 52 px hoch; seine Abweichung sitzt fast ganz in
Krallen und Hörnerspitzen.

**Texturgröße nach Mip-Stufe.** `texel_footprint.py` bestimmt je Dreieck die Mip-Stufe, die der
Sampler der Engine wählt (trilinear, ohne anisotrope Filterung), über acht Drehungen der Figur.
Angegeben ist der Bildanteil, der Stufe 0 liest, also mit der halben Größe Detail verlöre:

| | 512 | 1024 | 2048 |
|---|---:|---:|---:|
| Hexe 1080p | 25,3 % | **1,0 %** | 0,1 % |
| Hexe 2160p | 72,5 % | 25,3 % | 1,0 % |
| Imp 1080p | **0,3 %** | 0,0 % | 0,0 % |
| Imp 2160p | 10,8 % | 0,3 % | 0,0 % |

Im Bild: Hexe mit 2048 gegen 1024 im Mittel 0,04 sRGB-Stufen Unterschied (1080p, höchstens 1) und
0,06 (2160p, höchstens 5); mit 512 bei 2160p bis 44 Stufen. Imp mit 1024 gegen 512 im Mittel 0,03
(1080p) und 0,05 (2160p, höchstens 3). Gewählt: **Hexe 1024, Imp 512.** 2048 lohnt nur für
Nahaufnahmen.

### Wiederholbarkeit

Zwei vollständige Läufe in getrennten Prozessen ergeben für Hexe und Imp dasselbe `manifest.json`,
also bytegleiche `.glb`, Texturen und Berichte. Mit mehreren Threads unterschieden sich 2 von 18.862
Tangenten um 1e-4 und ein Texel der Normalenkarte; deshalb `-t 1`. Nachgewiesen auf einem Rechner
mit Blender 5.2.2 LTS; zwischen Rechnern oder Blender-Fassungen ist es nicht geprüft (OF-16.3).

### Prüfwerkzeuge

- `verify_normal_map.py`: zeichnet Original, Spielfigur und Spielfigur mit Normalenkarte
  orthografisch von vorn und hinten und misst den Winkel zur Originalnormale, auch gemittelt über
  4 und 16 Pixel und mit umgedrehtem Grünkanal als Gegenprobe. Tangentenrahmen und
  Texturorientierung wie `mesh.wgsl` (glTF: `v = 0` ist die oberste Zeile).
- `texel_footprint.py`: Mip-Stufen an der Spielkamera je Texturgröße.
- `render_game_view.py`: Spielkamera-Ansicht mit vier Abtastungen je Pixel, Mip-Kette wie in der
  Engine und Lambert-Licht; Silhouettenvergleich und Texturvarianten nebeneinander. Eine Vorschau,
  kein Ersatz für das Engine-Bild aus Stufe 4.

### Bekannte Grenzen

- Die Formnormale nimmt je Texel den nächsten Punkt des Originals. Zeigt dessen Normale von der
  reduzierten Fläche weg (Haarsträhnen, Stofflagen), bleibt der Texel flach: Hexe 6,6 %, Imp 0,5 %.
- UV-Inseln überlappen nach dem Reduzieren auf rund 1 % der belegten Texel.
- Die Hexe ist sehr dunkel: Grundfarbe im Median HSV-Value 6,7 % (Imp 20,4 %); die Stilbibel nennt
  für den Boden rund 24 %. Ob sie sich an der Spielkamera noch vom Boden abhebt, zeigt das
  Engine-Bild in Stufe 4. Diese Stufe ändert keine Farben.
- Die Ergebnisse (`.glb`, Texturen, Berichte) liegen nicht im Repo.

## Stufe 3: Packen

Das Packen macht der vorhandene Konverter in [`../figure_pack`](../figure_pack/README.md); für den
Pilot kann er seit dieser Stufe JPEG-Texturen lesen, Texturen exakt verkleinern und Figuren aus
beliebigen Dateien packen:

```sh
cd ../figure_pack
python -B build_figure_pack.py --figure witch=<ziel>/witch.glb --figure imp_hi3d=<ziel>/imp.glb
    --out <nutzlasten>
cd ../..
cargo run --release -p fnp_content --bin figure_pack_builder --
    --index <nutzlasten>/index.json --out <pfad>/pilot.pack
```

(Je Aufruf eine Zeile.) Ergebnis des Pilots: `pilot.pack` mit Hexe (`witch`) und Imp (`imp_hi3d`),
14 Einträge, 16,3 MiB; `vergleich.pack` mit denselben beiden und den Figuren der Runde 4
(`soul`, `imp`, `brute`) für den Vergleich in Stufe 4, 79 Einträge, 122,1 MiB. Beide liegen
außerhalb des Repos.

Nachweise dieser Stufe:

- **Ein Weg für zwei Eingaben.** Dieselbe Hexe, einmal aus den vorbereiteten 1024er-PNG und einmal
  aus den 8192er-JPEG des geriggten Downloads mit `--max-texture-size 1024`, ergibt **bytegleiche
  Texturnutzlasten**. Die Vorbereitung (Stufe 2) benutzt denselben Kastenfilter wie der Konverter,
  deshalb ist es gleich, an welcher Stelle der Kette verkleinert wird.
- **Früher Fehler statt später Absturz.** Der geriggte Download mit zwei 8K-Texturen bricht in
  0,2 Sekunden ab, nennt alle vier zu großen Texturen beider Figuren und das passende
  `--max-texture-size`, bevor ein Pixel dekodiert wird.
- **Alte Ergebnisse unverändert.** Die Figuren der Runde 4 packen zu bytegleichen 65 Nutzlasten und
  einem bytegleichen `figures.pack` wie vor der Änderung.

## Stufe 4: Nachweis in der Engine

Die gepackten Figuren werden in der Engine selbst gezeichnet: eigener Hauptschleifen-Durchlauf,
eigener Renderer, MSAA 4x wie im Spiel, an den drei Kameravoreinstellungen der Arena. Offscreen,
mit dem Software-Adapter, ohne Fenster. Abspielen von Clips ist nicht Teil dieser Stufe; die Engine
hat noch kein Animationssystem, deshalb kommt die Pose aus einer Datei.

### Aufruf

```sh
# Eine Pose eines Clips offline abtasten (ohne Blender, liest die Keyframes aus der .glb)
python -B sample_pose.py --figure <ziel>/witch.glb --clip melee_1 --frame 6 --name witch
    --out ../../crates/fnp_app/tests/data/witch_melee_1_frame_6.pose

# Bild und Messwerte, aus dem Wurzelverzeichnis des Repos, immer mit Software-Adapter
FNP_PILOT_PACK=<pfad>/vergleich.pack FNP_PILOT_DIR=<ausgabe> FNP_PILOT_CAMERA=0
    FNP_PILOT_TAG=vergleich_kamera_a FNP_PILOT_JSON=<ausgabe>/vergleich_kamera_a.json
    GRIMOIRE_GPU_ADAPTER=software
    cargo test --release -p fnp_app --test pilot_showcase -- --ignored --nocapture

# Größe auf dem Bildschirm und Helligkeit gegen den Boden
python -B measure_capture.py --capture <ausgabe>/vergleich_kamera_a_01.ppm
    --floor <ausgabe>/boden_kamera_a_01.ppm --labels soul,imp,witch,witch_pose,imp_hi3d
    --png <ausgabe>/vergleich_kamera_a.png
```

(Je Aufruf eine Zeile.) Der Test liegt in `../../crates/fnp_app/tests/pilot_showcase.rs`, ist
`#[ignore]`t und braucht ein Figurenpaket; seine Umgebungsvariablen (`FNP_PILOT_SCENE`
`comparison|crowd|floor`, `FNP_PILOT_CAMERA`, `FNP_PILOT_SIZE`, `FNP_PILOT_FRAMES`,
`FNP_PILOT_FIGURES`, `FNP_PILOT_CROWD`, `FNP_PILOT_MSAA`, `FNP_PILOT_POSE`) stehen in seinem Kopf.
Bilder schreibt er als PPM wie die Arena-Aufnahme, die Messwerte als JSON.

`sample_pose.py` tastet einen Clip an einem Zeitpunkt ab und schreibt die lokalen Transformationen
aller Gelenke in der Gelenkreihenfolge des Pakets (`../figure_pack/skeleton.py`), mit der
Achskorrektur des Wurzelgelenks, die der Konverter auch der Ruhepose gibt. Interpolation wie glTF:
`LINEAR`, Slerp für Drehungen, `STEP` hält den vorigen Keyframe; `CUBICSPLINE` wird abgelehnt statt
genähert. Die abgetastete Pose der Hexe (`melee_1`, Bild 6 bei 24 fps) liegt als Testdatei im Repo.

### Größe auf dem Bildschirm

1080p, Figurenhöhe in Pixeln, gemessen an der Maske gegen eine Aufnahme des leeren Bodens:

| Figur | Kamera A (60°, 14,5 m) | Kamera B (52°, 12,5 m) | Kamera C (45°, 11 m) |
|---|---:|---:|---:|
| `soul` (Runde 4) | 136 px | 179 px | 221 px |
| `imp` (Runde 4) | 104 px | 130 px | 153 px |
| **Hexe, Ruhepose** | **132 px** | **173 px** | **216 px** |
| Hexe, abgetastete Pose | 130 px | 156 px | 189 px |
| **Imp (Hi3D)** | **92 px** | **107 px** | **127 px** |

Die neuen Figuren spielen also in der Größe der Figuren aus Runde 4: die Hexe bleibt mit 1,80 m
wenige Pixel unter der `soul` (1,96 m), der Imp ist mit seiner Zielhöhe von 1,0 m die kleinste
Figur im Bild. Die abgetastete Pose ist niedriger als die Ruhepose, weil die Hexe darin für den
Schlag nach vorn gebeugt steht — an der nächsten Kamera 27 px.

### Helligkeit gegen den Arenaboden

Der Boden der Arena ist vom Blickwinkel unabhängig (zwischen den Voreinstellungen unterscheidet er
sich um höchstens 1 sRGB-Stufe), seine relative Leuchtdichte liegt bei **0,0215**. Kontrast nach
WCAG, Median der Figurenpixel gegen den Boden daneben, Kamera A / B / C:

| Figur | Leuchtdichte (Median) | Kontrast zum Boden | hellstes Zehntel |
|---|---:|---:|---:|
| `soul` | 0,0154 | 1,10 : 1 | 1,11 : 1 |
| `imp` (Runde 4) | 0,0140–0,0146 | 1,11–1,12 : 1 | **1,51–1,53 : 1** |
| Hexe | 0,0095–0,0104 | **1,18–1,20 : 1** | 1,02–1,05 : 1 |
| Imp (Hi3D) | 0,0114–0,0116 | 1,16 : 1 | 1,08 : 1 |

Antwort auf die Frage aus Stufe 2: **die Hexe verschwindet nicht.** Sie ist dunkler als der Boden,
und gerade daraus entsteht ihr Kontrast — er ist sogar etwas höher als der der `soul`, die heute im
Spiel steht. Was ihr fehlt, ist ein heller Bereich: das hellste Zehntel der `soul` hebt sich mit
1,11 : 1 ab, das des Runde-4-Imps mit 1,51 : 1, das der Hexe nur mit 1,02–1,05 : 1. Sie liest sich
als Silhouette, nicht als Gestalt. Alle Werte liegen weit unter den 3 : 1, die WCAG für
unterscheidbare Flächen nennt; das ist eine Entscheidung über Beleuchtung und Spielstil, keine der
Asset-Pipeline (offene Frage an die PO).

### Kosten auf der CPU-Seite

Gedränge: 30 Imps und die Hexe in einer Pose, 1080p, MSAA 4x. Gemessen mit der Uhr des Testlaufs,
weil der Offscreen-Lauf die Profiler-Uhr selbst stellt und die Profiler-Bereiche dort 0 zeigen.

| Szene | Figuren | Netz-Instanzen | Gelenkmatrizen | Bytes je Bild | Extraktion Ø / max |
|---|---:|---:|---:|---:|---:|
| Vergleich, 1080p | 5 | 17 | 135 | 8.640 | 0,006 / 0,011 ms |
| **Gedränge, 1080p** | **31** | **32** | **811** | **51.904** | **0,011 / 0,032 ms** |
| eine Figur, 1080p | 1 | 2 | 31 | 1.984 | 0,001 / 0,003 ms |

Dieselbe Reihe bei 64×64 Pixeln, wo die Software-Rasterung nicht mehr ins Gewicht fällt, über die
Figurenzahl: 1 Figur 0,0005 ms, 11 Figuren 0,0015 ms, 31 Figuren 0,0030 ms, 61 Figuren 0,0063 ms.
Die Extraktion wächst also linear, rund 0,1 µs je Figur (bei 1080p rund 0,3 µs, dort steckt
Messrauschen der belasteten Maschine drin), und bleibt weit unter dem Budget von 0,5 ms je Bild aus
Plan 0002. Die Gelenkmatrizen sind der größere Posten: 64 Bytes je Gelenk und Bild, bei 30 Imps und
einer Hexe 51.904 Bytes, die in jedem Bild neu hochgeladen werden.

**Nicht gemessen und nicht messbar auf dieser Maschine:** die Zeit der GPU. Der Software-Adapter
hat keine Zeitstempel, die Zahl `renderer_ms` in den JSON-Dateien ist die Wanduhr des
Zeichenaufrufs, also fast ausschließlich Software-Rasterung (160–270 ms je Bild bei 1080p). Sie
sagt über eine echte GPU nichts aus und gehört in keinen Vergleich mit dem Bildbudget.

### MSAA 4x gegen keine Kantenglättung

Dieselbe Szene zweimal, einmal mit der Voreinstellung der Engine (`Msaa::X4`), einmal ohne:

- **29,6 %** aller Figurenpixel ändern sich, im Mittel um 1,6 sRGB-Stufen, höchstens um 84.
- Aufgeteilt: von den Randpixeln der Silhouette ändern sich **56,4 %** und im Mittel um 6,5 Stufen,
  von den inneren 27,7 % und im Mittel um 1,3 Stufen.
- Kosten in der Software-Rasterung, drei Läufe je Einstellung: 208–212 ms gegen 179–192 ms je Bild,
  also rund ein Zehntel bis ein Fünftel mehr. Auf einer GPU ist das Verhältnis ein anderes; das
  misst erst die Messsitzung auf dem Rechner der PO.

MSAA trifft genau das, was bei diesen Figuren dünn ist: Haarsträhnen, Stofffransen, Hörner. Die
Vorschau aus Stufe 2 (`render_game_view.py`, vier Abtastungen je Pixel in numpy) hat das ähnlich
gezeigt, aber **die Helligkeit gegen den Boden falsch herum**: dort war die Hexe mit 0,0181 heller
als ihr Boden mit 0,0111, in der Engine ist sie mit 0,0104 dunkler als der Boden mit 0,0215. Die
Vorschau kennt weder das Umgebungslicht noch die Bodenfarbe der Arena. Übertragbar war aus ihr nur
die Aussage über Texturgrößen und Mip-Stufen, nicht die über Helligkeit oder Kontrast.

### Texturgröße, in der Engine gegengeprüft

Die Entscheidung aus Stufe 2 (Hexe 1024) noch einmal im Engine-Bild mit MSAA 4x, Hexe mit 1024
gegen dieselbe Hexe mit 512:

| | geänderte Figurenpixel | größte Abweichung |
|---|---:|---:|
| Kamera A | 1,2 % | 8 sRGB-Stufen |
| Kamera C | 3,9 % | 22 sRGB-Stufen |

Die Abweichungen sitzen im mittleren Drittel der Figur, an Oberkörper und Gürtel: dort ändern sich
an Kamera C 7,6 % der Pixel, im oberen Drittel 2,4 %, im unteren 1,0 %. An Kamera A ist der
Unterschied mit höchstens 8 Stufen auf 1,2 % der Pixel im Bild nicht mehr zu sehen, an Kamera C mit
22 Stufen auf 3,9 % gerade noch. 1024 bleibt die richtige Wahl, aber knapp: fiele die Entscheidung über
Texturspeicher später anders aus, kostete 512 die Hexe an der nächsten Kamera wenig.

### Grenzen dieser Stufe

- Alle Zeiten dieser Stufe stammen aus der Software-Rasterung. Was auf dem Rechner der PO gemessen
  werden muss: die GPU-Zeit eines Bildes mit 30 gehäuteten Figuren und MSAA 4x gegen das Budget von
  8 ms aus Plan 0002, mit und ohne Schattenwürfe, und ob das Hochladen der Gelenkmatrizen (51.904
  Bytes je Bild) auffällt.
- Die Figuren stehen still. Ein Clip wird nicht abgespielt; die eine Pose ist offline abgetastet.
- Der Boden trägt nur sein eigenes Material und das Licht der Arena, keine Effekte, keine Geschosse.

## Tests

```sh
python -B -m unittest test_check_asset.py test_prepare_tools.py test_pose_and_capture.py
```

`test_check_asset.py` baut kleine `.glb`-Dateien im Speicher (Figur mit Skin, Zehen, Texturen und
Clips) und prüft Messung, Grenzen, Exit-Codes und Tangentenwerte. `test_prepare_tools.py` prüft die Teile von Stufe 2 ohne
Blender: Kastenfilter und Linearlicht, Materialbilder, Seitennamen, Tangentenrahmen und
Texturorientierung, Mip-Stufen und das Verwerfen von Rückseiten. `blender_prepare.py` selbst
prüfen die Pilotläufe über ihre Berichte und die Stufe-1-Prüfung der fertigen Figur.
`test_pose_and_capture.py` prüft Stufe 4 ohne Engine: Slerp und Abtastung der Animationskanäle
(`LINEAR`, `STEP`, abgelehntes `CUBICSPLINE`), die Achskorrektur des Wurzelgelenks in der
abgetasteten Pose, das Posenformat, das Lesen der PPM-Aufnahmen, Leuchtdichte und Kontrast sowie
das Zerlegen einer Aufnahme in Figurenbänder. Den Engine-Teil prüfen die Einheitentests in
`../../crates/fnp_app/tests/pilot_showcase.rs` (Posendatei, Reihenpositionen, Gedrängeraster); das
Bild selbst entsteht nur im `#[ignore]`ten Lauf.

# asset_import/

Prüfstufe für fremd erzeugte 3D-Figuren (Hi3D-Downloads, geriggte Arbeitskopien) auf dem Weg in
das Pack der Engine. Erste von vier Stufen des Hexen-Pilots: **Prüfen**, Vorbereiten, Packen,
Nachweis in der Engine. Die Prüfung misst eine `.glb` gegen die Grenzen der Engine, die Regeln des
Konverters in [`../figure_pack`](../figure_pack/README.md) und das Budget ihrer Rolle.

Nur Python-Standardbibliothek, kein Blender, kein numpy. Den glTF-Container liest
`../figure_pack/glb_reader.py`.

## Aufruf

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

## Was geprüft wird

| Ebene | Prüfungen | Herkunft der Grenze |
|---|---|---|
| `engine.*` | Vertices und Indizes je Teil, Pixel und Kantenlänge je Textur, Knochen je Skin, vier Einflüsse je Vertex, nur Dreiecke | Grimoire `v0.4.0`: `figure_format.rs`, `stage3d.rs`, `mesh.rs`, `max_texture_dimension_2d` des Software-Adapters |
| `pipeline.*` | lesbar (keine Sparse-Accessoren, keine Pflicht-Erweiterungen wie Draco), Bildformat, Material je Teil, Normalen, Tangenten bei UVs, höchstens ein Skin | Konverter `figure_pack` |
| `budget.*` | Dreiecke, Vertices, Teile, Rig, Knochen, Texturanzahl und -kante, geschätzter GPU-Speicher, Normalenkarte (Warnung), Clip-Namen (Warnung) | `budgets.json`, Rolle |
| `convention.*` | Höhe, Fußpunkt im Ursprung, Mitte über dem Ursprung (Warnung), Blickrichtung, Ruhepose gleich Bindepose (Warnung) | `budgets.json`, Abschnitt `pipeline` |
| `info.*` | Texturkanten als Zweierpotenz (Warnung), unbenutzte Bilder | – |

**GPU-Speicher** ist eine Schätzung nach dem heutigen Upload der Engine: jede Textur als RGBA8 mit
voller Mip-Kette (4/3 der Grundfläche, eine 8192er-Textur also 341 MiB), jeder Vertex 72 Byte, jeder
Index 4 Byte. Eine Blockkompression (OF-3.4) würde den Texturanteil etwa vierteln.

**Clip-Namen** sind nur eine Warnung: Ob und wie die Engine Clips abspielt, entscheidet ein eigenes
ADR. Bis dahin zeigt die Prüfung, welche erwarteten Namen fehlen und welche unbekannt sind.

## Budgets

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

## Blickrichtung

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

## Tests

```sh
python -B -m unittest test_check_asset.py
```

Die Tests bauen kleine `.glb`-Dateien im Speicher (Figur mit Skin, Zehen, Texturen und Clips) und
prüfen Messung, Grenzen, Exit-Codes und die Kopfleser für PNG und JPEG. Die JPEG-Beispiele sind nur
Dateiköpfe; die Prüfung dekodiert nie Pixel.

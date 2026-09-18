# figure_pack/

Konverter für geriggte Figuren aus Blender/glTF in das Pack-Format der Engine "Grimoire":
ursprünglich die drei Feindfiguren (`soul`, `imp`, `brute`), seit dem Hexen-Pilot auch Figuren aus
[`../asset_import`](../asset_import/README.md). Gemeinsame Festlegung mit der Engine-Seite:
`figuren-in-engine-spec.md` (siehe PR-Beschreibung für den vollständigen Text und die
festgestellte Abweichung bei den `AssetKind`-Werten und der Drehrichtung).

Zwei Stufen, damit das Pack-Containerformat weiterhin genau eine Umsetzung hat:

1. **Python** (dieser Ordner): liest die `.glb` der Figuren, dekodiert glTF-Accessoren und
   eingebettete PNGs von Hand, schreibt je Figur die Nutzlasten als einzelne Dateien plus eine
   `index.json`. Für PNG-Figuren ohne Verkleinerung genügt die Standardbibliothek; JPEG-Texturen
   brauchen Pillow, `--max-texture-size` braucht numpy (beide gepinnt in
   [`../textures/requirements.txt`](../textures/requirements.txt)).
2. **Rust** (`crates/fnp_content/src/bin/figure_pack_builder.rs`): liest `index.json` und baut
   mit dem vorhandenen `grimoire_assets::PackWriter` `figures.pack`.

## Ausführen

Quelle und Ausgabeordner werden als Argumente übergeben; im Quelltext steht kein lokaler Pfad.

```sh
python -B build_figure_pack.py --source <ordner-mit-den-glb-dateien> --out <ausgabeordner>
cargo run --release -p fnp_content --bin figure_pack_builder -- \
    --index <ausgabeordner>/index.json --out <pfad>/figures.pack
```

`--source` muss für jeden Namen aus `--figures` (Vorgabe `soul,imp,brute`) die Datei
`<name><suffix>` enthalten (Vorgabe `_r3b_low.glb`). Weitere Figuren aus beliebigen Dateien kommen
mit `--figure NAME=PFAD` hinzu (wiederholbar, auch ohne `--source`), etwa die vorbereiteten
Pilotfiguren:

```sh
python -B build_figure_pack.py --figure witch=<ziel>/witch.glb --figure imp_hi3d=<ziel>/imp.glb
    --out <ausgabeordner>
```

Erzeugte Dateien (Zwischenformate wie `index.json`/`*.bin` und `figures.pack`) gehören nicht ins
Repo; gemäß der Festlegung landen sie unter `_showcase/pack/` außerhalb beider Repos.

### Das Pack des Prototyps

Der Prototyp lädt genau zwei Figuren, `soul` (Spieler) und `imp` (Gegner); die Namen stehen in
`crates/fnp_app/src/figures.rs`, der Pfad des Packs kommt beim Start aus `--pack` oder
`FNP_FIGURE_PACK`. Das Pack mit den Figuren der PO entsteht so:

```sh
python -B build_figure_pack.py --figure soul=<ziel>/witch.glb --figure imp=<ziel>/imp.glb
    --clips soul=idle,walk --clip-events soul=<autorenbericht>.json --out <ausgabeordner>
cargo run --release -p fnp_content --bin figure_pack_builder --
    --index <ausgabeordner>/index.json --out <pfad>/figures_r5.pack
```

(Je Aufruf eine Zeile.) `soul` ist dabei die Hexe (1,8 m) und `imp` der Hi3D-Imp (1,3 m) — die
Namen sind die des Laders, nicht die der Figuren. Beide sind mit **+Z nach vorn** gebaut, anders
als die Figuren der Runden 3 und 4; der Lader dreht heute jede Pack-Figur mit der Konstanten
`PACK_FIGURES_FRONT = AuthoredFront::MinusZ` um 180°, was diese beiden von der Kamera wegdrehen
würde.

Tests: `python -B -m unittest test_figure_pack.py test_textures.py test_clips.py`.

## Clips (`FNP_CLIP`)

Seit der Engine-Fassung nach v0.5.0 gibt es ein Clip-Format: eine Pack-Nutzlast der Art `0x8005`
unter `figures/<figur>/clip/<clip>`, abgetastet Bild für Bild, mit Markierungen. Verbindlich ist
das Formatdokument der Engine (`docs/formats/figure-clip.md`, Fassung 1) samt Vertrag §6; dieser
Konverter ist die Autorenseite davon, `clips.py`. Abspielen ist Sache der Engine
(`grimoire_render::figure_clip`), nicht dieses Ordners.

```sh
python -B build_figure_pack.py --figure soul=<ziel>/witch.glb
    --clips soul=idle,walk --clip-events soul=<bericht>.json --out <ausgabeordner>
```

(Je Aufruf eine Zeile.) `--clips NAME=a,b` wählt die Clips einer Figur, `--clip-events NAME=PFAD`
nennt den Autorenbericht mit `clips[].events`, `--clip-rate` die Bildrate der Vorlage (Vorgabe 24).

Was der Konverter dabei festlegt:

- **Ein Wert je Bild.** Keine Schlüsselreduktion, keine Quantisierung. Eine Spur, die sich nie
  ändert, steht einmal da — das ist die ganze Kompression des Formats. Gemessen an der Hexe: von
  93 Spuren (31 Gelenke × 3) verändern sich in `idle` 5 und in `walk` 9.
- **Die Zeit beginnt bei null.** Die exportierten `.glb` setzen ihren ersten Schlüssel auf
  `1/24 s`, weil Blender ab Bild 1 zählt. Dieser Versatz ist Autorenbasis und wird abgezogen;
  Bild 0 der Nutzlast ist der erste Schlüssel.
- **Schleife wird gemessen, nicht eingestellt.** Ein Clip schleift, wenn sein letztes Bild das
  erste wiederholt (Format §3). `idle` und `walk` der Hexe tun das, `death` nicht. Für Drehungen
  zählt auch die andere Hemisphäre (`q` und `-q` sind dieselbe Drehung).
- **Markierungen sind nullbasiert.** Der Autorenbericht zählt Blender-Bilder ab 1, der Konverter
  zieht eines ab und weist eine Markierung außerhalb des Clips zurück, statt sie zu beschneiden.
  `idle` und `walk` haben keine; `melee_1` hätte `hit` auf Bild 6 (Nutzlast 5).
- **Die Wurzelkorrektur gilt auch für Clips.** Das Wurzelgelenk trägt in jedem Bild dieselbe
  Achskorrektur wie in der Ruhepose, sonst legt sich die Figur beim Abspielen hin.
- **Drehungen bleiben Einheitsquaternionen.** Zwischen zwei Schlüsseln wird mit Slerp
  interpoliert; der Konverter normiert einen Schlüssel nie stillschweigend nach, sondern bricht ab,
  wenn die Länge um mehr als `1e-3` abweicht — genau die Grenze, an der der Dekoder ablehnt.
- **Der Skelett-Fingerabdruck** (`StableHasher` v1 über Gelenkzahl und Elternindizes) wird hier
  nachgebildet, damit der Konverter ohne Engine-Code auskommt. `test_clips.py` prüft ihn gegen den
  im Formatdokument genannten Wert und die ganze Nutzlast gegen die handabgeleitete Golden-Datei
  der Engine (`figure_clip_v1.bin`, 190 Bytes): mit `FNP_GRIMOIRE_REPO=<engine-checkout>` wird
  zusätzlich Byte für Byte gegen die Datei selbst verglichen, sonst gegen die hier ausgeschriebene
  Herleitung.

Die zweite Stufe prüft eine Clip-Nutzlast noch einmal aus den rohen Bytes, bevor sie in das Pack
geht (Magic, Fassung, reservierte Flag-Bits, Gelenkzahl gegen das Skelett derselben Figur, Grenzen,
endliche Werte, Einheitsquaternionen, Markierungen in Reihenfolge und im Clip, keine überzähligen
Bytes) — bewusst eine zweite Umsetzung neben dem Dekoder der Engine.

**Alte Engine, neues Pack.** Ein Pack mit Clip-Einträgen lädt auch mit der noch gepinnten Fassung
v0.5.0: die Art `0x8005` wird dort schlicht nie angefragt. Erst das Abspielen braucht die neue
Engine.

## Texturen

Umgesetzt in `textures.py`, in dieser Reihenfolge:

1. **Grenzen zuerst, nur aus dem Dateikopf** (`image_headers.py`). Bevor ein Pixel dekodiert wird,
   prüft der Lauf jede von einem Material benutzte Textur aller Figuren gegen die Engine:
   höchstens 64 Mio. Pixel (`FNP_TEXTURE_RAW`) und höchstens 8192 Pixel je Seite
   (`max_texture_dimension_2d` des Software-Adapters). Eine zu große Textur beendet den Lauf sofort
   mit Figur, Bild, Größe und dem passenden `--max-texture-size`, alle Verstöße auf einmal. Beim
   geriggten Hexen-Download mit zwei 8K-JPEGs dauert das 0,2 Sekunden, statt dass die Engine das
   Pack später ablehnt.
2. **Dekodieren:** PNG wie bisher mit dem eigenen Dekoder (`png_decode.py`), JPEG mit Pillow
   (Graustufen und YCbCr; CMYK wird abgelehnt).
3. **Verkleinern** (`--max-texture-size N`): Ist die längere Seite größer als `N`, wird um die
   kleinste passende Zweierpotenz verkleinert, mit einem exakten Kastenfilter. Die Regel ist die der
   Mip-Kette der Engine (`average_texels` in `grimoire_render`): Farbe einer sRGB-Textur in linearem
   Licht gemittelt und in sRGB gerundet, Alpha und lineare Texturen direkt gemittelt. Gerechnet wird
   nur mit ganzen Zahlen: Die sRGB-Kurve steht als feste Tabelle in Einheiten von 2^-24 im Code, und
   ein Block bekommt den Code, dessen Rundungsschwelle sein exakter Mittelwert erreicht. So ergibt
   jede Plattform dieselben Bytes. Seiten, die sich nicht glatt teilen lassen, brechen ab.

PNG-Figuren ohne `--max-texture-size` ergeben dieselben Nutzlasten wie vorher: Die Figuren der
Runde 4 (`_r4_low.glb`) packen vor und nach der Änderung zu bytegleichen 65 Nutzlasten und einem
bytegleichen `figures.pack`.

## Achsen

glTF ist Y-oben, rechtshändig, Kamera blickt entlang -Z. Die Engine ist Z-oben, X-rechts,
Y-vom-Betrachter-weg (rechtshändig). Die Drehung sitzt **einmal**, im Ruhepose-Transform jeder
Skelett-Wurzel (`skeleton.correct_root_joint_transform`) — nie an den Mesh-Vertices, nie ein
zweites Mal in der Engine. Warum das ausreicht und warum es die Wurzel und nicht die Vertices
trifft, steht im Modul-Docstring von `build_figure_pack.py`; jeder Lauf beweist es zusätzlich an
echten Vertices (`_forward_kinematics_check`, Ausgabe "forward-kinematics check: ... max error").
Dieselbe Begründung gilt für `TANGENT.xyz` (Fassung 2, siehe unten): auch die Tangente bleibt im
Pack roh/ungedreht, exakt wie die Normale, und derselbe Lauf beweist die Äquivalenz zusätzlich an
echten Vertices ("forward-kinematics tangent check: ... max error", `rig_math.vector_transform`).

## FNP_MESH Fassung 2 (Tangenten)

Seit texturqualitaet-spec.md wechselt **nur `FNP_MESH`** auf `kind_version` 2 (72 statt 56 Byte je
Vertex: zusätzlich `tangent: f32[4]`); alle anderen Arten bleiben bei Fassung 1. Herkunft je
Primitiv:

- **Kein `TEXCOORD_0`** (Iris, Stab, Zähne): jeder Vertex bekommt `[0, 0, 0, 0]` — das vereinbarte
  Zeichen für "keine Tangente". Der einzige Ausweichweg der Festlegung.
- **`TEXCOORD_0` vorhanden, `TANGENT` vorhanden:** roh übernommen (keine Drehung, siehe oben).
- **`TEXCOORD_0` vorhanden, `TANGENT` fehlt, Material nutzt eine Normalenkarte:** Fehler, der Lauf
  bricht ab (`export_tangents=True` beim Blender-Export nachholen).
- **`TEXCOORD_0` vorhanden, `TANGENT` fehlt, keine Normalenkarte:** kein in der Festlegung
  vorgesehener Fall; der Lauf bricht trotzdem ab, statt einen dritten Ausweichweg zu erfinden
  (bislang bei keinem der drei Figuren beobachtet).

Gültige Tangente: `|xyz| = 1` und `w = +1` oder `-1` (Toleranz je 1e-3), sonst exakt `[0,0,0,0]`.

## Prüfungen

Jeder Lauf bricht mit Fehler ab, bevor irgendetwas geschrieben wird, wenn eine dieser Prüfungen
fehlschlägt (siehe `pack_payloads.py`, `skeleton.py`, `build_figure_pack.py`):

- Dreiecksanzahl (Indexanzahl) gegen die glTF-Quellaccessoren.
- Jeder Vertex-Index `< vertex_count`, jeder Knochenindex `< joint_count`.
- Gewichtssumme je Vertex auf 1 (Toleranz 1e-3).
- Texturgröße gleich `width * height * 4`; jede benutzte Textur vor dem Dekodieren gegen
  64 Mio. Pixel und 8192 je Seite (siehe „Texturen“).
- Eltern-Index jedes Knochens `< eigener Index` (durch den eigenen topologischen Sort erzwungen,
  nicht nur übernommen aus `skin.joints`).
- Forward-Kinematik-Stichprobe: echte Vertices, durch die volle Skinning-Formel (Knochenkette x
  inverse Bindematrix) transformiert, stimmen mit der direkt gedrehten Rohposition überein.
  Dieselbe Stichprobe prüft, wo vorhanden, auch `TANGENT.xyz` gegen die direkt gedrehte Rohtangente.
- Tangentengültigkeit je Vertex (siehe "FNP_MESH Fassung 2" oben): `[0,0,0,0]` oder Einheitslänge
  mit `w = +-1`.

`crates/fnp_content/src/bin/figure_pack_builder.rs` prüft Index-/Knochen-/Gewichts-/
Texturgrenzen und die Tangentengültigkeit ein zweites Mal, unabhängig, direkt aus den rohen Bytes,
bevor es sie an `PackWriter` übergibt.

## Bekannte Eigenheiten der Quelldaten

- `soul_staff` und `imp_teeth` referenzieren ein Material mit Texturen, tragen aber kein
  `TEXCOORD_0` (`texCoord: -1` im Quell-glTF, ein Blender-Exporter-Artefakt für "kein UV-Set").
  Der Konverter füllt UV mit `(0, 0)` und meldet das als Hinweis auf der Konsole.
- `KHR_materials_emissive_strength` (bei den Augen/Kugel-Materialien) ist in
  `figuren-in-engine-spec.md`s `MATERIAL`-Layout nicht vorgesehen; der Konverter multipliziert
  die Stärke in `emissiveFactor` hinein, statt sie stillschweigend zu verlieren.

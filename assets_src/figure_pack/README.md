# figure_pack/

Konverter für die drei gerigten Feindfiguren (`soul`, `imp`, `brute`) aus Blender/glTF in das
Pack-Format der Engine "Grimoire". Gemeinsame Festlegung mit der Engine-Seite:
`figuren-in-engine-spec.md` (siehe PR-Beschreibung für den vollständigen Text und die
festgestellte Abweichung bei den `AssetKind`-Werten und der Drehrichtung).

Zwei Stufen, damit das Pack-Containerformat weiterhin genau eine Umsetzung hat:

1. **Python** (dieser Ordner, nur Standardbibliothek): liest `<name>_r3b_low.glb`, dekodiert
   glTF-Accessoren und eingebettete PNGs von Hand, schreibt je Figur die Nutzlasten als
   einzelne Dateien plus eine `index.json`.
2. **Rust** (`crates/fnp_content/src/bin/figure_pack_builder.rs`): liest `index.json` und baut
   mit dem vorhandenen `grimoire_assets::PackWriter` `figures.pack`.

## Ausführen

Quelle und Ausgabeordner werden als Argumente übergeben; im Quelltext steht kein lokaler Pfad.

```sh
python -B build_figure_pack.py --source <ordner-mit-den-glb-dateien> --out <ausgabeordner>
cargo run --release -p fnp_content --bin figure_pack_builder -- \
    --index <ausgabeordner>/index.json --out <pfad>/figures.pack
```

`--source` muss `soul_r3b_low.glb`, `imp_r3b_low.glb` und `brute_r3b_low.glb` enthalten. Erzeugte
Dateien (Zwischenformate wie `index.json`/`*.bin` und `figures.pack`) gehören nicht ins Repo;
gemäß der Festlegung landen sie unter `_showcase/pack/` außerhalb beider Repos.

Tests: `python -B -m unittest test_figure_pack.py`.

## Achsen

glTF ist Y-oben, rechtshändig, Kamera blickt entlang -Z. Die Engine ist Z-oben, X-rechts,
Y-vom-Betrachter-weg (rechtshändig). Die Drehung sitzt **einmal**, im Ruhepose-Transform jeder
Skelett-Wurzel (`skeleton.correct_root_joint_transform`) — nie an den Mesh-Vertices, nie ein
zweites Mal in der Engine. Warum das ausreicht und warum es die Wurzel und nicht die Vertices
trifft, steht im Modul-Docstring von `build_figure_pack.py`; jeder Lauf beweist es zusätzlich an
echten Vertices (`_forward_kinematics_check`, Ausgabe "forward-kinematics check: ... max error").

## Prüfungen

Jeder Lauf bricht mit Fehler ab, bevor irgendetwas geschrieben wird, wenn eine dieser Prüfungen
fehlschlägt (siehe `pack_payloads.py`, `skeleton.py`, `build_figure_pack.py`):

- Dreiecksanzahl (Indexanzahl) gegen die glTF-Quellaccessoren.
- Jeder Vertex-Index `< vertex_count`, jeder Knochenindex `< joint_count`.
- Gewichtssumme je Vertex auf 1 (Toleranz 1e-3).
- Texturgröße gleich `width * height * 4`.
- Eltern-Index jedes Knochens `< eigener Index` (durch den eigenen topologischen Sort erzwungen,
  nicht nur übernommen aus `skin.joints`).
- Forward-Kinematik-Stichprobe: echte Vertices, durch die volle Skinning-Formel (Knochenkette x
  inverse Bindematrix) transformiert, stimmen mit der direkt gedrehten Rohposition überein.

`crates/fnp_content/src/bin/figure_pack_builder.rs` prüft Index-/Knochen-/Gewichts-/
Texturgrenzen ein zweites Mal, unabhängig, direkt aus den rohen Bytes, bevor es sie an
`PackWriter` übergibt.

## Bekannte Eigenheiten der Quelldaten

- `soul_staff` und `imp_teeth` referenzieren ein Material mit Texturen, tragen aber kein
  `TEXCOORD_0` (`texCoord: -1` im Quell-glTF, ein Blender-Exporter-Artefakt für "kein UV-Set").
  Der Konverter füllt UV mit `(0, 0)` und meldet das als Hinweis auf der Konsole.
- `KHR_materials_emissive_strength` (bei den Augen/Kugel-Materialien) ist in
  `figuren-in-engine-spec.md`s `MATERIAL`-Layout nicht vorgesehen; der Konverter multipliziert
  die Stärke in `emissiveFactor` hinein, statt sie stillschweigend zu verlieren.

# Asset-Import-Pilot: fremd erzeugte Figuren ins Spiel (parallel zu M3)

- **Stand:** 2026-09-17 (Agentenlauf)
- **Status:** Alle vier Stufen gemergt. Die **Rollenbudgets bleiben nach dem PO-Entscheid vom 2026-09-18 vorläufig** und werden nach der GPU-Messsitzung bestätigt; Texturgrößen sind seit Stufe 4 in der Engine belegt, und für Gegner gilt künftig eine Zielhöhe von 1,3 m. Die Werte in §2 und §3 sind gemessen, nicht geschätzt.
- **Bezug:** [Plan 0002](0002-phase-p1-sichtbarer-kern.md) (PO-Entscheide vom Abend des 2026-09-17, Meilenstein M3), [PRD-0003](../prd/0003-rendering-und-art.md) (Look, Kamera, Figuren), [PRD-0002](../prd/0002-grimoire-engine-architektur.md) (Budgets), Engine-Vertrag `crate-vertraege.md` §6 (`FNP_MESH`, Knochenverformung, Texturgrenzen) und §12 (Pack v1), Engine-Formatdoku `pack.md`.
- **Warum ein eigenes Dokument:** Der Pilot ist kein Arbeitspaket aus den P1-PRDs, sondern Spiel-Repo-Arbeit, die der PO am Abend des 2026-09-17 parallel zu M3 beauftragt hat. Plan 0002 verweist darauf (PO-Entscheide vom Abend des 2026-09-17), statt seine WP-Nummerierung zu dehnen; alle Werkzeuge liegen unter `assets_src/`, kein Rust ist betroffen.
- **Nicht getan:** Die vier Pilot-PRs ändern kein Rust und keinen Engine-Code (insbesondere nicht `crates/fnp_game/src/arena/present.rs` und nicht `crates/fnp_content/`; der Prototyp-Neubau in Spiel-PR #12 hat beides unabhängig davon angefasst); kein Blender und keine Grafikkarte in der CI; keine Messung auf Referenz-Hardware; die Ergebnis- und Bilddateien der Stufen 2 bis 4 liegen außerhalb des Repos, weil sie aus Quellen, Skripten und Manifest reproduzierbar sind.

## 1. Auftrag

Vier Stufen: **prüfen, vorbereiten, packen, in der Engine ansehen.** Eingaben sind fremd erzeugte Figuren — die Hi3D-Downloads der Hexe und des Imps mit je 2.000.000 Dreiecken sowie geriggte Arbeitskopien davon. Ziel ist je eine Spielfigur im Rollenbudget, byte-reproduzierbar aus Quelle, Skript und Manifest, gepackt als Pack v1 und danach im Engine-Bild gegen den echten Boden geprüft.

## 2. Stufen

### Stufe 1 — Budget-Prüfung (Spiel-PR #11, Merge-Commit `05d2db8`)

`assets_src/asset_import/check_asset.py` misst eine `.glb` ohne Blender und ohne numpy und prüft sie gegen die Engine-Grenzen von Grimoire `v0.4.0` (Vertices und Indizes je Teil, 64 Mio. Pixel je Textur, Kante 8192 am Software-Adapter, 256 Knochen, 4 Einflüsse je Vertex), gegen die Konverter-Regeln von `figure_pack` (Bildformat, Normalen, Tangenten bei UVs, ein Skin, lesbare Accessoren) und gegen die Rollenbudgets aus `budgets.json` (§4). Ausgabe: lesbare Zusammenfassung, JSON-Bericht ohne Pfade, Exit-Code 0/1/2.

**Befunde an den Pilot-Eingaben:** Hi3D-Hexe als `player` 13 FAIL (2.000.000 Dreiecke, 1.035.319 Vertices gegen höchstens 1 Mio. Vertices und 3 Mio. Indizes je Teil, zwei JPEG 8192² mit 67,1 Mio. Pixeln über der Engine-Grenze, keine Normalen, kein Skin); geriggte Hexe 9 FAIL (100.000 Dreiecke, 299.984 Vertices, 31 Knochen, alle 12 erwarteten und 6 optionalen Clips, geschätzt 704 MiB GPU, Ruhepose gleich Bindepose mit 1e-6 Abweichung); Imp-Rig-Pilot als `enemy` 9 FAIL (70.000 Dreiecke, 43.303 Vertices, 26 Knochen, nur `idle` und `walk`); Hi3D-Imp 11 FAIL. Die eigenen Figuren der Runde 4 verletzen das vorgeschlagene Texturbudget (10 statt 4 Texturen), Dreiecke, Knochen, Höhe und Fußpunkt passen.

**Zwei echte Widersprüche gefunden:** Das Imp-Rig legt die `.L`-Knochen auf die Seite −X eines Netzes, das nach +Z schaut — die Seitennamen sind gespiegelt, für ein statisches Bild belanglos, für jede Animationsübertragung nicht. Und die Blickrichtung ist offen: `budgets.json` und `facing_yaw` in `present.rs` erwarten +Z (glTF-Standard, so liefern alle Hi3D-Downloads), die Figuren der Runde 4 schauen gemessen nach −Z. Die Zehenregel für die Blickrichtung ist an zehn Netzen gemessen und jedes Mal mit einer Punktansicht von vorn und hinten bestätigt (Vorzeichen immer richtig, Betrag 2,2 bis 12 % der Höhe). **Entschieden und umgesetzt (2026-09-17) mit Spiel-PR #12 (`835117a`):** Die Konvention bleibt glTF +Z (glTF-Standard, alle Hi3D-Quellen); die Figuren-Packs der Runden 3 und 4 sind als `MinusZ` markiert und werden im Modellraum um eine halbe Drehung gedreht, bevor Blickrichtung und Treffer-Reaktion wirken. Vorher lief die Seele rückwärts und der Imp zeigte dem Spieler den Rücken; Nahaufnahmen auf dem Software-Adapter belegen beides vor und nach der Änderung, die Simulation blieb unberührt. Aus dem Piloten folgt daraus nur: **neue Importe liefern +Z und brauchen die Markierung nicht.**

### Stufe 2 — Vorbereiten (Spiel-PR #13, Merge-Commit `7a559f2`)

`prepare_figure.py` verkleinert die Texturen, ruft `blender_prepare.py` headless auf (Import, Seitentausch, Verschweißen, Reduktion mit Gewichtsübertragung, Aufstellen, Formnormalen, Export) und prüft das Ergebnis mit der Stufe-1-Prüfung. Ergebnis: Hexe **11.996 Dreiecke / 12.236 Vertices**, Imp **5.000 / 3.661**; Stufe-1-Prüfung Hexe PASS, Imp PASS mit der Clip-Warnung.

**Gemessen statt vermutet, drei Befunde:**

- **Die drei Vertices je Dreieck der geriggten Hexe kamen nicht von zerschnittenen UVs, sondern von flacher Schattierung** (jede Vertexnormale gleich der Flächennormale; Position und UV zusammen unterscheiden nur 70.638 Vertices). Verschweißen und Glätten genügt.
- **Die geriggten Arbeitskopien sind rissig:** Die Hexe hat nach dem Verschweißen 38.462 offene Kanten in 307 Stücken, der Imp 16.036; die Hi3D-Originale keine, und größere Schweißabstände schließen die Risse nicht. Deshalb wird **das Original reduziert und die Gewichte werden übertragen** (Abstand p99 2,3 mm Hexe, 3,1 mm Imp, kein Vertex ohne Gewicht); gegen die Reduktion der Arbeitskopie gewinnt dieser Weg bei Silhouette und Normalenfehler. `--lod-source rigged` bleibt als Option.
- **Dreieckszahl und Texturgröße sind aus Messungen gewählt,** nicht geraten: Silhouettenabweichung an der Spielkamera (Hexe 8.000/12.000/18.000 Dreiecke → 6,3/5,2/4,8 % bei 1080p; Imp 5.000/7.500/10.000 → 11,3/11,0/10,7 %) und Anteil der Pixel, die Mip-Stufe 0 lesen (Hexe 1024: 1,0 % bei 1080p, 25,3 % bei 2160p; Imp 512: 0,3 % / 10,8 %). Die Hälfte mehr Dreiecke bringt jeweils unter einen Prozentpunkt; im Bild unterscheiden sich Hexe 2048 und 1024 im Mittel um 0,04 sRGB-Stufen.

**Zwei Selbstkorrekturen, festgehalten:** Die erste Verifikation der Normalenkarte war falsch (sie las die Karte mit Blenders V-Richtung statt der von glTF) und hätte die Karte als unbrauchbar gezeigt; die Tests prüfen jetzt ausdrücklich, dass `v = 0` die oberste Zeile ist. Die Gegenprobe mit umgedrehtem Grünkanal ist messbar schlechter (Hexe 35,7° statt 10,3°), die Konvention der Karte stimmt also.

### Stufe 3 — Packen mit JPEG und exakter Verkleinerung (Spiel-PR #14, Merge-Commit `80e005a`)

Der Konverter in `assets_src/figure_pack` prüft jetzt **vor dem ersten dekodierten Pixel** jede von einem Material benutzte Textur aller Figuren nur aus dem Dateikopf gegen 64 Mio. Pixel und 8192 Pixel je Seite und bricht mit allen Verstößen auf einmal ab (der geriggte Hexen-Download in 0,2 s statt nach 8K-Dekodierung). Neu sind JPEG über Pillow (Graustufen und YCbCr, CMYK abgelehnt; PNG bleibt beim eigenen Dekoder, damit PNG-Figuren ohne Verkleinerung allein mit der Standardbibliothek packen), `--max-texture-size N` mit einem **exakten Kastenfilter nach der Mip-Regel der Engine** (sRGB in linearem Licht gemittelt, gerechnet nur mit ganzen Zahlen, sRGB-Kurve als feste Tabelle, damit keine `pow`-Implementierung ein Byte verschiebt) und `--figure NAME=PATH`.

**Nachweise:** Die Figuren der Runde 4 ergeben vor und nach der Änderung bytegleiche 65 Nutzlasten und ein bytegleiches `figures.pack`. Dieselbe Hexe ergibt **aus den vorbereiteten 1024er-PNG und aus den 8192er-JPEG des Downloads mit `--max-texture-size 1024` bytegleiche Texturnutzlasten** — das prüft JPEG-Dekodierung, Verkleinerung und Stufe 2 in einem Zug. Gepackt sind `pilot.pack` (Hexe und Hi3D-Imp, 14 Einträge, 16,3 MiB) und ein Vergleichspack mit den Figuren der Runde 4 für Stufe 4 (79 Einträge, 122,1 MiB); der Forward-Kinematik-Selbsttest läuft für beide Pilotfiguren durch (max. Fehler 1,3e-07 Position, 3,7e-07 Tangente).

**Nebenbefund aus Stufe 2, mit behoben:** Beide Stufe-2-Figuren hatten je **eine** Null-Tangente, die der Konverter zu Recht ablehnt (das Reduzieren faltet einzelne schmale Dreiecke um, MikkTSpace projiziert die Tangente dann auf null). `check_asset.py` prüft jetzt `pipeline.tangent_values`, `blender_prepare.py` schattiert solche Flächen flach und wiederholt, bis alle Tangenten gültig sind. Beide Figuren neu vorbereitet, je zweimal bytegleich, Messwerte unverändert.

### Python-Tests in der CI (Spiel-PR #15, Merge-Commit `dcc3e3b`)

Die 94 Python-Tests der Asset-Werkzeuge liefen bisher nirgends außer auf dem Entwicklungsrechner; jeder Fehler der Stufen 1 bis 3 fiel lokal auf, nicht in der CI. Der neue Job `asset tooling (python)` in `ci.yml` schließt die Lücke: Python 3.13, `pip install -r assets_src/textures/requirements.txt` (Pillow 12.3.0, numpy 2.4.4), dann `unittest discover` je Ordner — 59 Tests `figure_pack` und 35 Tests `asset_import`, zusammen 13 Sekunden, kein Blender und keine Grafikkarte.

**Der Job ist nachweislich scharf:** Ein absichtlich falscher Erwartungswert (`187` statt der korrekten `188` für halbes Weiß in linearem Licht) machte Lauf 35257719286 genau in diesem Job rot, während `rustfmt` und alle drei `test`-Jobs grün blieben; die Rücknahme ist in Lauf 35257974400 wieder grün. **Bewusste Abweichung von der Vorgabe:** Der Job läuft bei jedem Auslöser des Workflows statt nur bei Änderungen unter `assets_src/**`, weil GitHub Actions keinen Pfadfilter je Job kennt und ein Filter am Workflow für jede andere Änderung gar keinen Status melden würde — genau die Branch-Schutz-Falle aus `CONTRIBUTING.md`. Der saubere Weg zur Pfadbindung wäre ein eigener Workflow `assets.yml`; offen, ob der PO das will.

### Stufe 4 — Engine-Bild und Massentest (Spiel-PR #17, Merge-Commit `a4cd0de`)

Die gepackte Hexe und der Hi3D-Imp werden von der Engine selbst gezeichnet — offscreen, Software-Adapter, MSAA 4x, an allen drei Kamera-Vorgaben, neben den Figuren der Runde 4. Kein Fenster, keine echte GPU, kein Abspielen von Clips: die eine Pose ist offline abgetastet. Dazu zwei Werkzeuge ohne Engine und ohne Blender — `sample_pose.py` tastet ein Bild eines Clips in die Gelenkreihenfolge des Pakets ab (`LINEAR`, Slerp, `STEP`; `CUBICSPLINE` wird abgelehnt statt genähert), `measure_capture.py` misst eine Aufnahme gegen den leeren Boden — und 23 Tests für beide.

**Gemessen:**

- **Größe auf dem Bildschirm** (1080p, Figurenhöhe in Pixeln, Kamera A/B/C): **Hexe 132/173/216**, dieselbe Hexe in der abgetasteten Pose 130/156/189, **Hi3D-Imp 92/107/127**; zum Vergleich `soul` 136/179/221 und `imp` der Runde 4 104/130/153. Die neuen Figuren spielen in der Größe der alten.
- **CPU-Seite im Gedränge** (30 Imps plus Hexe = 31 Figuren, 32 Netz-Instanzen, 811 Gelenkmatrizen zu 51.904 Byte je Bild): **Extraktion 0,011 ms im Mittel**, 0,032 ms im Maximum, gegen das Budget von **0,5 ms**. Über die Figurenzahl wächst sie linear mit rund 0,1 µs je Figur.
- **Helligkeit gegen den echten Arenaboden** (Boden 0,0215): Die Hexe liegt bei 0,0095–0,0104 und hebt sich mit **1,18–1,20 : 1** ab, etwas besser als die `soul` mit 1,10 : 1 — sie verschwindet also nicht. Aber **ihr hellstes Zehntel kommt nur auf 1,02–1,05 : 1**, gegen 1,51 : 1 beim Imp der Runde 4: Sie liest sich als Silhouette, nicht als Gestalt.
- **Texturgröße gegengeprüft:** Hexe 1024 gegen 512 ändert an Kamera A 1,2 % ihrer Pixel (höchstens 8 sRGB-Stufen), an Kamera C 3,9 % (22 Stufen), am dichtesten an Oberkörper und Gürtel. **1024 bleibt richtig** — jetzt in der Engine belegt statt in einer Vorschau.
- **MSAA 4x gegen ohne:** 29,6 % der Figurenpixel ändern sich, am Silhouettenrand 56,4 % und dort im Mittel um 6,5 sRGB-Stufen, höchstens 84 — genau die dünnen Teile: Haarsträhnen, Fransen, Hörner.

**Die Vorschau aus Stufe 2 führte in die Irre:** Sie zeigte die Hexe **heller** als ihren Boden (0,0181 gegen 0,0111), in der Engine ist es **umgekehrt** (0,0104 gegen 0,0215) — die Helligkeitsbeziehung war also vertauscht. Die Vorschau kennt weder Umgebungslicht noch Bodenfarbe der Arena; übertragbar war aus ihr nur die Aussage über Texturgrößen und Mip-Stufen. Die Helligkeitsfrage ist damit erst in der Engine beantwortet, und Vorschauwerte gehören künftig nur noch zum Vergleich zweier Varianten, nie als absolute Aussage.

**Nicht gemessen:** Alle Renderer-Zeiten dieser Stufe sind Wanduhrzeiten der Software-Rasterung (160–270 ms je Bild bei 1080p) und sagen über eine GPU nichts. In Messsitzung 1 gehört gemessen: die GPU-Zeit eines Bildes mit 30 gehäuteten Figuren und MSAA 4x gegen das 8-ms-Budget aus Plan 0002, mit und ohne Schattenwürfe, und ob das Hochladen der Gelenkmatrizen auffällt.

**Entschieden (PO, 2026-09-18):** Die Rollenbudgets bleiben vorläufig (§4). Vor weiteren Importen werden **Gegner auf eine Zielhöhe von 1,3 m** gebracht — der Hi3D-Imp steht heute auf 1,0 m und misst an Kamera A nur 92 px. Die Lesbarkeit der Hexe wird **über das Licht gelöst, ein Rim-Light, nicht über die Figur**: Textur, Grundfarbe und Reduktion bleiben, wie sie sind.

Zwei Läufe des Aufnahmetests ergeben bytegleiche Bilder; Push-Lauf auf `main` 35268356586 grün.

## 3. Gemessene Werte der Vorbereitung (Stufen 2 und 3)

| | Hexe | Imp |
|---|---|---|
| Quelle | Hi3D 2.000.000 Dreiecke; Rig 100.000 Dreiecke / 299.984 Vertices, 31 Knochen, 18 Clips | Hi3D 2.000.000 Dreiecke; Rig 70.000 Dreiecke / 43.303 Vertices, 26 Knochen, 2 Clips |
| Spielfigur | **11.996 Dreiecke, 12.236 Vertices** | **5.000 Dreiecke, 3.661 Vertices** |
| gegen die Engine-Grenzen je Teil | 12.236 / 1.000.000 Vertices, 35.988 / 3.000.000 Indizes | 3.661 / 1.000.000, 15.000 / 3.000.000 |
| Texturen, GPU-Speicher | **3 × 1024², 16,0 MiB** (+ 1,0 MiB Netz) statt vorher 2 × 8192² mit **682,7 MiB** | 3 × 512², 4,0 MiB (+ 0,3 MiB Netz) |
| Höhe, Fußpunkt, Blickrichtung | 1,800 m, 0,000 m, +Z (beide Methoden) | 1,000 m, 0,000 m, +Z (nach dem Seitentausch) |
| Abstand zum Original p50 / p99 | 0,75 / 3,8 mm | 0,75 / 2,8 mm |
| **Normalenfehler gegen das 2-Mio.-Original, Median ohne → mit gebackener Karte** | **vorn 28,8° → 10,3°**, hinten 31,1° → 8,2° | vorn 20,6° → 7,6°, hinten 20,3° → 7,5° |
| Ein Weg, zwei Eingaben | Texturnutzlasten aus dem 1024er-PNG-Weg und aus dem 8192er-JPEG-Weg **bytegleich** (alle drei Texturen) | — |

**Wiederholbarkeit:** Zwei vollständige Läufe in getrennten Prozessen ergeben für beide Figuren dasselbe `manifest.json` (bytegleiche `.glb`, Texturen und Berichte). Mit mehreren Blender-Threads unterschieden sich 2 von 18.862 Tangenten um 1e-4 und ein Normalen-Texel; **deshalb läuft Blender einfädig (`-t 1`)**. Bytegleichheit ist mit Blender 5.2.2 LTS auf einem Rechner nachgewiesen, nicht zwischen Rechnern oder Fassungen (OF-16.3, §5).

## 4. Vorläufige Rollenbudgets (PO-Freigabe ausstehend)

Die PRDs nennen keine Zahlen je Rolle. `assets_src/asset_import/budgets.json` führt deshalb vorläufige Budgets, gegen die Stufe 1 prüft:

| Rolle | Dreiecke | Texturen | Kante | GPU-Speicher |
|---|---:|---:|---:|---:|
| `player` | 20.000 | 4 | 2048 | 96 MiB |
| `enemy` | 12.000 | 4 | 1024 | 24 MiB |
| `boss` | 50.000 | 6 | 2048 | 160 MiB |
| `prop` | 5.000 | 3 | 1024 | 20 MiB |

**Entschieden (PO, 2026-09-18):** Die Budgets bleiben **vorläufig**; bestätigt werden sie nach der GPU-Messsitzung. Sie gelten für neue Importe; die Figuren der Runde 4 werden dafür nicht umgebaut. Dazu gehört seit demselben Entscheid eine **Zielhöhe von 1,3 m für Gegner** — die Tabelle oben begrenzt Dreiecke, Texturen und Speicher, nicht die Größe im Bild, und Stufe 4 hat gezeigt, dass ein 1,0-m-Gegner an der Vorgabekamera nur 92 px hoch ist. **Umgesetzt (2026-09-18, Spiel-PR #24 `6bb2b81`):** Der Imp ist für 1,300 m neu vorbereitet worden, nicht beim Laden skaliert; die Stufe-1-Prüfung ist danach grün (Füße auf 0, Blickrichtung +Z nach beiden Messverfahren, Ruhepose-Abweichung 4,2e-07, GPU-Speicher 4,3 von 24 MiB).

## 5. Offene PO-Fragen (je mit Empfehlung)

1. **Rollenbudgets** aus §4 als vorläufige Werte übernehmen. *Entschieden (PO, 2026-09-18):* ja, sie bleiben vorläufig; bestätigt wird nach der GPU-Messsitzung, nicht schon nach Stufe 4.
2. **Blickrichtung +Z oder −Z.** *Erledigt (2026-09-17)* mit Spiel-PR #12 (`835117a`): Die Konvention bleibt +Z; die Packs der Runden 3 und 4 sind als `MinusZ` markiert und werden zur Darstellung gedreht, statt ihren Export zu ändern. Neue Importe liefern +Z.
3. **Zielhöhe der Hexe** — Hi3D normiert jede Figur auf 1,0 m. *Empfehlung:* 1,8 m wie die Verdammte Seele, damit Kapsel und Kamera unverändert passen; der Imp bleibt bei 1,0 m, der Fußpunkt beider kommt auf y = 0. *Nachtrag (PO, 2026-09-18):* Für **Gegner** gilt künftig eine Zielhöhe von **1,3 m**, bevor weitere Figuren importiert werden; die 1,8 m der Hexe bleiben.
4. **Gespiegelte Seitennamen im Imp-Rig.** *Empfehlung:* in der Vorbereitungsstufe `.L`/`.R` tauschen, nicht in den Quelldateien.
5. **Fehlende Clip-Namen** als Warnung oder Fehler. *Empfehlung:* Warnung, bis das Animations-ADR entschieden ist.
6. **Texturgrößen Hexe 1024, Imp 512** (gemessen, §2 Stufe 2). *Empfehlung:* so übernehmen; 2048 nur, wenn Nahaufnahmen der Spielerfigur geplant sind.
7. **Die Hexe ist sehr dunkel** (Grundfarbe im Median HSV-Value 6,7 %, Imp 20,4 %; die Stilbibel nennt für den Boden rund 24 %). *Entschieden (PO, 2026-09-18):* Die Lesbarkeit wird **über das Licht gelöst — ein Rim-Light —, nicht über die Figur**; keine Kanalverstärkung, keine neue Textur. Stufe 4 hat den Befund beziffert: 1,18–1,20 : 1 gegen den Boden, aber nur 1,02–1,05 : 1 im hellsten Zehntel. *Umgesetzt (2026-09-18):* Die Engine hat das Rim-Licht der Akteurs-Ebene (Engine-PR #68, Vertrag §6), das Spiel setzt `MeshRole::Actor` auf seine Figuren (Spiel-PR #26). **Im Prototyp gemessen** — andere Szene als Stufe 4, also eigene Grundwerte, Kamera A, derselbe Frame nur mit und ohne Akteursrolle: 9.645 geänderte Pixel, alle innerhalb der Figuren; das hellste Zehntel der Hexe steigt von 3,67:1 auf 4,26:1, das des Imps von 1,04:1 auf 1,28:1. Die Stärke steht noch auf der Vorgabe der Engine (offener Punkt für den PO).
8. **Speicherort der Ergebnisse.** *Empfehlung:* vorerst außerhalb des Repos; Git LFS erst, wenn das Pack in der CI aus ihnen gebaut werden soll.
9. **Rissige Arbeitskopien.** *Empfehlung:* vor dem Reduzieren nach Position verschweißen lassen; diese Stufe braucht es nicht mehr, Gewichtsmalerei und Animation auf einem geschlossenen Netz werden aber sauberer.
10. **Blender-Fassung (OF-16.3).** *Empfehlung:* 5.2 LTS pinnen, Manifest-Abweichungen nach einem Blender-Wechsel bewusst erneuern.
11. **Texturkompression (OF-3.4).** Das Pack trägt RGBA8 roh (Vergleichspack 122,1 MiB). *Empfehlung:* vorerst so lassen und BC7/KTX2 gemeinsam mit der Engine-Seite entscheiden; der Kastenfilter ist die Stelle, an der das später ansetzt.
12. **Zwei Imps im Vergleichspack** (`imp_hi3d` neben dem `imp` der Runde 4). *Empfehlung:* Namen behalten, bis entschieden ist, welcher Imp der Spiel-Imp ist.
13. **Pfadbindung des Python-Jobs** (eigener Workflow `assets.yml` statt Lauf bei jedem Auslöser). *Empfehlung:* so lassen, 13 Sekunden gegen einen Pflicht-Check, der auf „Expected“ stehen bliebe.

## 6. Referenzen

- [Plan 0002 Phase P1](0002-phase-p1-sichtbarer-kern.md) — PO-Entscheide vom Abend des 2026-09-17, Meilenstein M3
- [PRD-0003 Rendering & Art](../prd/0003-rendering-und-art.md) · [PRD-0002 Engine](../prd/0002-grimoire-engine-architektur.md) · [PRD-0016 Tooling](../prd/0016-tooling-suite.md)
- Werkzeuge im Repo: `assets_src/asset_import/` (Prüfung und Vorbereitung, `README.md` mit allen Messungen), `assets_src/figure_pack/` (Konverter), `assets_src/textures/requirements.txt` (gepinnte Python-Pakete)
- Spiel-PRs: #11 (`05d2db8`), #13 (`7a559f2`), #14 (`80e005a`), #15 (`dcc3e3b`), #17 (`a4cd0de`, Stufe 4), #24 (`6bb2b81`, Spielpack und Clip-Export), #26 (`a384d7b`, Rim-Licht im Prototyp)

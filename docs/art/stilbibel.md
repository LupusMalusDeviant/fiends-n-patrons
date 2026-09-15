# Stilbibel: Look, Paletten und Materialwerte (v0)

- **Status:** Vorläufig (v0) — Bestätigung durch das PO-Look-Review an M1 aussteht (P-11)
- **Datum:** 2026-09-15
- **Autor:** Lupus Malus Deviant (PO) / Claude (Ausarbeitung)
- **Bezug:** [Plan 0002](../plans/0002-phase-p1-sichtbarer-kern.md) (WP2.7, P-11) · [PRD-0003](../prd/0003-rendering-und-art.md) (Render-Ebenen, Regeln 1–5, FR-13, FR-15, NFR „Konsistenz") · [ADR-0014](../adr/0014-realistischer-3d-look-statt-toon.md) (realistischer 3D-Look, Vergleichsmessungen) · [PRD-0014](../prd/0014-ui-ux.md) (A11y, Farbfehlsichtigkeit FR-13) · [PRD-0016](../prd/0016-tooling-suite.md) (Kontrast-Checker) · [Musik-Prompts](musik-prompts-suno.md) (Arbeitstitel der Stages) · Engine-Vertrag `crate-vertraege.md` §6 (`BulletInstance`, Palettenräume, `RenderLayer`) · Look-Dev-Spike auf Engine-Branch `p1/wp2-look-dev-spike` (`spikes/look-dev`, `spikes/look-dev-blender`)

Dieses Dokument ist **vorläufig**. Es bündelt die Ergebnisse des Look-Dev-Spikes (ADR-0014) und der
Engine-Verträge zu einem ersten, verbindlich gemeinten, aber noch nicht abgenommenen Regelwerk. Alle
konkreten Werte (Bullet-Licht-Obergrenze, Telegraphie-Familie, Boden-Kalibrierziel u. a.) sind
**Vorschläge** und werden am Look-Review zu Meilenstein M1 (P-11) bestätigt oder korrigiert. Bis dahin
gilt es als Arbeitsgrundlage für WP2/WP3, nicht als abgenommener Standard.

**Harte Regeln (PRD-0003, zur Einordnung):**

1. Ebene 6 (Bullets) und Ebene 4 (Telegraphie) werden von keinem Effekt überdeckt, getönt oder geblurrt.
2. Bloom/Grading lösen sich vor Ebene 6 auf oder werden maskiert; Bullets halten ≥ 4,5:1 WCAG-Kontrast gegen jeden möglichen Hintergrund.
3. Bullet-Typen unterscheiden sich durch **Silhouette und Farbe**, nie nur Farbe.
4. Gegnerische und eigene Projektile liegen in getrennten Palettenräumen.
5. Licht aus Bullets oder Bullet-Wolken hat eine Obergrenze für seinen Beitrag zu Boden und Umgebung; die Umgebung bleibt im dunklen, entsättigten Palettenraum.

Der Engine-Vertrag (`crate-vertraege.md` §6) erzwingt Regel 3 (Silhouettenindex in `BulletInstance`)
und Regel 4 (`palette_space`-Prüfung im Bullet-Pass) bereits strukturell. Die aktuelle
Ebenenreihenfolge im Renderer (`RenderLayer::ORDER`: `World`, `Vfx`, `PostFxResolve`, `Telegraphy`,
`Bullets`, `PlayerMarker`, `DebugUi`) weicht in der Post-FX-Position vom neunstufigen Diagramm in
PRD-0003 ab (dort liegt Post-FX nach dem Spieler-Marker); das Nachziehen ist in WP11.6 vorgesehen und
ändert nichts an Regel 1/2.

## Ebenen und Farbräume

Jede Kategorie bekommt einen reservierten Bereich in Hue (Farbton), Sättigung und Value (HSV), damit
sich keine zwei Kategorien über Farbe verwechseln lassen — Silhouette und Kontext bleiben die zweite
Verteidigungslinie (Regel 3).

| Kategorie | Ebene(n) | Hue | Sättigung | Value | Bemerkung |
|---|---|---|---|---|---|
| Umgebung (Boden, Geometrie, Props) | 1, 2 | 200–240° | ≤ 25 % | ≤ 35 % | Moos-Akzent separat: Hue 90–110°, Sättigung ≤ 25 %, Value ≤ 25 % |
| Warmes Licht (Fackeln, Kerzen, Glut, Gegneraugen) | Lichtquellen auf 1–3 | 15–45° | frei (Emissive/HDR) | frei (HDR) | Nur Lichter und Flammen, nie ein Bullet |
| Ritualmagie | 1–3, Dekale | 255–275° | hoch | mittel–hoch | Ritualkreis, Rune, Stab-Orb-Familie |
| Gegnerische Bullets (HOSTILE) | 6 | 315–335° (Magenta) und 75–95° (Limette) | ≥ 80 % | ≥ 90 % | Weißglühender Kern + dunkler Rand, siehe „Bullets" |
| Eigene Projektile (FRIENDLY) | 3 (Sprite-/Mesh-Kanal, nicht Ebene 6) | 185–200° (Eisblau/Cyan) | 40–60 % | hoch, reduzierte Alpha | Silhouette länglich statt rund |
| Telegraphie (Vorschlag) | 4 | 48–62° (Bernstein/Gold) | ≥ 70 % | ≥ 80 % | Reservierte Familie, harte Kantenform statt weichem Glow — Abgrenzung zum violetten Ritualkreis (siehe Befunde und Offene Punkte) |
| Figuren (Spieler, Gegner) | 3 | frei | niedrig–mittel | niedrig–mittel | Bullets gewinnen immer gegen Figuren an Sättigung und Value |
| Spieler-Marker | 7 | 185–200° (Friendly-Familie, entsättigter/heller) | niedrig | sehr hoch | Unterscheidet sich von Friendly-Bullets über Ebene/Kontext, nicht über eine neue Hue |
| UI | 9 | kein eigener Anspruch in v0 | – | – | UI-Styleguide (P2, `docs/art/ui-styleguide.md`) legt Werte fest; bis dahin meidet UI die reservierten Gefahr-Familien |

## Bullets

**Silhouette und Farbe (Regel 3, Engine-Vertrag §6 `BulletInstance.silhouette`):** Jeder Bullet-Typ
trägt eine eigene Silhouette aus der Silhouettentabelle des Bullet-Passes; Farbe allein unterscheidet
nie den Typ. Für v0 stehen drei Grundformen aus dem Spike bereit: Orb (Kreis), Reis (länglich) und
Diamant. Ein neuer Typ braucht eine zusätzliche, klar unterscheidbare Silhouette, bevor eine weitere
Farbe hinzukommt.

**Rand, Kern und Glow:** Jeder Hostile-Bullet hat einen dunklen Rand `#0A0510`, Alpha 0,9, 1,5 px
breit, und einen weißglühenden Kern. Glow (`BulletInstance.glow`, 0–255, linear) zeichnet
ausschließlich der Bullet-Pass selbst — nie Post-FX (Regel 1).

**Palettenräume (Regel 4, Engine-Vertrag §6 `palette_space`):** Nur `palette_space::HOSTILE` (1)
durchläuft den geschützten Bullet-Pass (Ebene 6, `BULLET_PASS_PALETTE_SPACE`); jede andere Instanz
wird verworfen und gezählt (`bullets_rejected_palette_space`). Eigene Projektile laufen mit
`palette_space::FRIENDLY` (2) über die Sprite-/Mesh-Kanäle der Weltebene, nicht über Ebene 6.

Gegnerisch (HOSTILE, Palettenraum 1):

| Palette | Körper | Kern | Rand |
|---|---|---|---|
| H0 „Hexenmagenta" | `#FF2FB4` | `#FFE3F4` | `#0A0510`, Alpha 0,9, 1,5 px |
| H1 „Giftlimette" | `#B6FF2E` | `#F6FFE0` | `#0A0510`, Alpha 0,9, 1,5 px |

Eigene Projektile (FRIENDLY, Palettenraum 2):

| Palette | Körper | Kern | Bemerkung |
|---|---|---|---|
| F0 | `#8FE8FF` | `#FFFFFF` | Alpha 0,75, Silhouette länglich statt rund |

**Kontrastziel (Regel 2):** Bullets sollen ≥ 4,5:1 WCAG-Kontrast gegen jeden möglichen Hintergrund
erreichen. Der Look-Dev-Spike zeigt, dass das für den Körper allein nicht durchgängig gilt: H0
Hexenmagenta (Körper-Luminanz L = 0,266) erreicht 4,5:1 nur vor einem Hintergrund mit L < 0,020
(nahezu Schwarz); H1 Giftlimette (L = 0,817) bis L < 0,143. **H0s Lesbarkeit trägt der dunkle Rand,
nicht der Körper** — eine Eigenschaft der Palette, keine des Looks, gleich in allen drei verglichenen
Looks. Der Kontrast-Checker (PRD-0016) prüft deshalb Körper **oder** Rand, nicht nur den Körper.

**Farbfehlsichtigkeit (PRD-0014 FR-13):** H0/H1 unterscheiden sich neben dem Hue-Abstand (Magenta
315–335° gegen Limette 75–95°) vor allem durch die Silhouette (Regel 3) — das trägt die Hauptlast für
Protan-/Deutan-/Tritan-Modi, weil Rot-Grün-Fehlsichtigkeit Hue-Unterschiede in diesem Bereich
abschwächen kann. Der Kontrast-Checker simuliert alle drei Modi (PRD-0016, Werkzeug-Katalog); geprüfte
Alternativpaletten für v0 stehen noch aus (siehe Offene Punkte).

## Bullet-Licht-Obergrenze (Regel 5, FR-15)

Licht aus Bullet-Wolken darf Boden und Umgebung nur begrenzt aufhellen — sonst tönt es die Umgebung in
den geschützten Bullet-Farbraum und senkt den Bullet-Kontrast zusätzlich, weil der Hintergrund heller
wird.

**Messung im Spike:** Ohne Deckelung erreichten im Gewühl nur 13 % (Blender, realistischer Look) bzw.
22 % (Engine-Spike, Software-Adapter) der gegnerischen Bullets 4,5:1. Mit den Bullet-Cluster-Lichtern
auf 25 % ihrer Intensität stieg der Anteil in Blender auf 33 % — der stärkste einzelne Hebel, den der
Vergleich gefunden hat (ADR-0014).

**Vorschlag für v0:** Obergrenze 25 % der vollen Cluster-Licht-Intensität. Zusätzlich verwenden
Cluster-Lichter nie die Bullet-Körperfarbe (Magenta/Limette), sondern einen entsättigten Glutton — der
Engine-Spike nutzt `#B07850`. Ohne diese Entsättigung tönt sich der Boden direkt in Richtung des
geschützten Bullet-Palettenraums, selbst wenn `BulletInstance.palette_space` formal unberührt bleibt.

**Prüfung:** Der Kontrast-Checker (PRD-0016) bleibt Freigabe-Gate (ADR-0014). Er misst die
Boden-Luminanz unter Bullet-Clustern gegen das Kalibrierziel (siehe „Licht und Stimmung") und den
Bullet-Kontrast bei voller und gedeckelter Cluster-Intensität; eine Abweichung vom hier vorgeschlagenen
Wert braucht eine neue Messung, keine Bildbeurteilung.

Der Wert 25 % ist ein **Vorschlag**, keine Festlegung — Bestätigung am Look-Review (P-11).

## Umgebung und Materialien (realistisches PBR)

**Wertebereich:** siehe Farbraum „Umgebung" oben (Hue 200–240°, Sättigung ≤ 25 %, Value ≤ 35 %;
Moos-Akzent separat). Die Materialtabelle des Spikes erfüllt das bereits — Bodenstein `#33363D`
entspricht etwa Hue 228°, Sättigung 16 %, Value 24 %.

**Rauheit/Metall:** Nichtmetallische Umgebungsflächen liegen bei Rauheit 0,6–0,95 (glatter Basalt am
Altar, rauer Fugenmörtel); Metall = 0. Einzige metallische Referenz ist Bronze (Kohlebecken): Metall = 1,
Rauheit 0,35, mit eigenem F0 `#F2C28A` statt der dunklen Diffus-Albedo als Spekularfarbe (Spike-Korrektur
— sonst wirkt Bronze fast schwarz). Der Realistic-Shader braucht generell Rauheit ≥ 0,25 für das
geometrische Spekular-Anti-Aliasing (Kandidat für OF-3.5, siehe Offene Punkte).

**Referenzwerte je Material** (aus dem Spike, Albedo looks-übergreifend identisch):

| Material | Albedo | Rauheit | Metall | F0 (nur Metall) |
|---|---|---:|---:|---|
| Bodenstein | `#33363D` | 0,85 | 0 | – |
| Fugenmörtel | `#1A1C21` | 0,95 | 0 | – |
| Säulenstein | `#3E4047` | 0,75 | 0 | – |
| Sockel | `#2C2E34` | 0,85 | 0 | – |
| Ruinenwand | `#383A3F` | 0,85 | 0 | – |
| Moos (Akzent) | `#2E3A2A` | 0,85 | 0 | – |
| Schutt | `#45464A` | 0,85 | 0 | – |
| Altar (Basalt) | `#2A2528` | 0,6 | 0 | – |
| Kohlebecken (Bronze) | `#6B4A2A` | 0,35 | 1 | `#F2C28A` |
| Kerzenwachs | `#D8CDB4` | 0,85 | 0 | – |

Requisiten- und Figuren-Referenz (nicht Teil des Umgebungs-Farbraums, siehe „Figuren"): Umhang
`#24505C`, Kapuzeninnenseite `#0A0C0E`, Knochenmaske `#CFC3A8`, Stabholz `#4A3524`; Imp-Haut `#7A7068`,
Hörner `#C9BBA0`; Brute-Fleisch `#5E3530`, Schulterplatten `#3B3A3E`.

**Regel:** Große Umgebungsflächen (Boden, Wände, Säulen) bleiben im Umgebungs-Farbraum. Kleine
Requisiten und Metalle dürfen ihre reale Farbe tragen (warme Bronze, cremiges Wachs), aber nie im
Bullet-, Telegraphie- oder Friendly-Hue.

## Licht und Stimmung

| Quelle | Farbe |
|---|---|
| Mond | `#9AB0D8` |
| Fackel/Kohlebecken | `#FF9A4A` (Flamme `#FFB25A` ×6, Kern `#FFE2B0`) |
| Kerze | `#FFC07A` / `#FFB066` |
| Ritual/Rune | `#8A5CFF` |
| Stab-Orb | `#7FE3FF` ×4 |
| Glut (verstreut) | `#FF6A2A` / `#FF7A3A` / `#FF5A1F` |
| Glut, entsättigt (Bullet-Cluster-Cap) | `#B07850` |

**Kalibrierziel:** Boden-Median 0,18 (anzeigebezogen), linear ≈ 0,027 — in Engine- und Blender-Spike
gleichermaßen erreicht. Offene Frage aus dem Spike-Bericht: ob Dark Fantasy tiefer zielen sollte (z. B.
0,12); ein dunklerer Boden würde tendenziell auch den Bullet-Kontrast anheben (dunklerer Hintergrund →
höheres Kontrastverhältnis), siehe Offene Punkte.

**Schatten:** Technik offen (OF-3.2, WP2.6). Der Blender-Vergleich testete Shadow-Maps für Mond, die
8 Fackeln/Kohlebecken und den Stab-Orb, alle übrigen Lichter ohne Schatten — ein plausibler Kandidat für
die Key-Light-plus-begrenzte-Schattenwerfer-Technik aus PRD-0003. Preset „Low" bleibt bei Blob-Schatten
(Ebene 1, Decal-Pass).

**Bloom-Grenzen:** Post-FX (Bloom, Grading) wird vor Ebene 6 aufgelöst oder maskiert (Regel 1/2); kein
Effekt nach `PostFxResolve` tönt, blurrt oder überdeckt Ebene 4 (Telegraphie) oder Ebene 6 (Bullets).
Spike-Bloom-Parameter (gemeinsam für alle Looks, nicht bindend fürs Spiel): Schwelle 1,0, Knie 0,5,
4 Stufen, Stärke 0,08.

## Figuren

Ohne Outlines und ohne Rimlight (ADR-0014 lehnt beides ab) trennen sich Figuren nur über Licht,
Value-Kontrast und Schatten von der Umgebung. Figuren bleiben deshalb in niedriger bis mittlerer
Sättigung (siehe Farbraum-Tabelle), damit Bullets immer in Sättigung und Value gewinnen.

**Befund aus dem Spike:** Der realistische Look trennt Figuren im Gewühl schlechter als die
verglichenen Alternativen (Median-Kontrast 1,67, Minimum 1,19–1,24 gegen den Ring um die Silhouette).
Blob-Schatten wurden deshalb in der Polish-Runde von 45 % auf 60 % Abdunklung verstärkt. Echte
Schattenwürfe (OF-3.2) sollten diesen Wert weiter verbessern; das ist Teil der OF-3.2-Entscheidung, nicht
separat zu lösen.

**Spielerlesbarkeit:** Der Umhang `#24505C` (kühles Teal) verschwindet vor dem violetten Ritualglühen
(`#8A5CFF`-Familie, Hue 255–275°) — beide liegen nah beieinander in Hue und Value. Das ist ein offener
Punkt für das Look-Review (siehe unten), keine Entscheidung dieses Dokuments.

## Texturen

**Formate (PRD-0003 FR-13):** glTF Metallic-Roughness; Basisfarbe (Albedo) in sRGB, Normal Maps in
OpenGL-Konvention (+Y), Rauheit/Metall/Occlusion gepackt als ORM-Textur (Occlusion = R, Roughness = G,
Metallic = B, glTF-Konvention). Kompression und Auflösung sind OF-3.4, offen bis zur Blender-Pipeline
(P2, zusammen mit OF-16.3).

**Texel-Dichte und Mid-Scale-Regel:** Aus der Gameplay-Kamera (rund 35–65 px/m) lesen sich nur
mittelskalige Merkmale — Pro-Kachel-Variation, Risse, abgeplatzte Kanten, Schmutz in Fugen,
Rauheitskontrast zwischen ausgetretenen Pfaden und Fugenmörtel. Feines Rauschen flimmert als
Spekular-Aliasing und gehört nicht in Basisfarbe oder Normal Map. Figuren brauchen ein echtes
UV-Unwrapping mit angemessener Texel-Dichte, keine weltskalierte Box-Projektion — der erste
Textur-Test zeigte, dass eine box-projizierte Umhang-Textur auf der Figur praktisch unsichtbar blieb.

**CC0-Herkunftsnachweis (ADR-0014, FR-13):** Jede CC0-Textur (z. B. ambientCG, Poly Haven) steht mit
Quelle und Lizenz im Asset-Manifest. Prozedural in Blender gebackene Texturen brauchen keinen
Herkunftseintrag, nur die CC0-Anteile.

**Verboten in Texturen:**
- Helle, bulletartige Punkte oder Glanzlichter, die mit Bullets oder Telegraphen verwechselt werden können.
- Reservierte Hues (Hostile Magenta/Limette, Friendly Cyan, Ritual-Violett, Telegraphie-Familie, siehe oben) auf großen Umgebungsflächen.
- Textur-Variation, die eine Fläche außerhalb ihres Farbraum-Limits verschiebt — Basisfarbe **und** Textur-Variation zusammen müssen im Limit aus „Umgebung und Materialien" bleiben.

## Paletten je Biom (Vorschlag)

Biome und Patrone sind in den PRDs noch nicht benannt; die drei Arbeitstitel stammen aus den
Musik-Prompts. Die Werte sind ein **Vorschlag** — Unterscheidung über Akzent, Requisiten und Licht,
nicht über eine neue Umgebungs-Hue (die reservierten Räume bleiben für alle Biome verbindlich).

- **Krypta** (Stage 1, MUS-03 „Crypt of Tallow Saints"): Umgebungs-Hue wie Spike-Default (200–240°),
  Moos-/Flechten-Akzent (90–110°), warmes Talgkerzenlicht (15–45°) als Hauptlichtquelle.
- **Blutsumpf** (Stage 2, MUS-04 „Bloodmarsh Liturgy"): gleicher Umgebungs-Farbraum, Akzent auf
  gedecktes Rostrot/Fäulnisbraun in kleinen Requisiten (nie in reservierten Bullet-/Telegraphie-Hues),
  niedrigere Rauheit für feuchte Flächen.
- **Uhrwerk-Tempel** (Stage 3, MUS-05 „Clockwork Heresy"): gleicher Umgebungs-Farbraum, Akzent auf
  Messing-/Bronze-Requisiten (Metall = 1, F0 wie die Kohlebecken-Referenz) für Zahnräder- und
  Uhrwerk-Motive.

## Offene Punkte für das Look-Review (P-11)

| Punkt | Empfehlung |
|---|---|
| Telegraphie-Farbfamilie | Reservierte Familie Hue 48–62° (Bernstein/Gold) mit harter Kantenform statt weichem Glow bestätigen, um die Verwechslung mit dem violetten Ritualkreis auszuschließen |
| H0-Helligkeit (Hexenmagenta) | Rand-getragene Lesbarkeit akzeptieren und dokumentieren, oder Körper-Luminanz anheben — PO-Entscheidung, weil das von reiner Körper-WCAG-Prüfung abweicht |
| Umhangfarbe des Spielers | Weg vom Ritual-Violett (zu nah in Hue und Value): höheren Value-Kontrast oder andere Hue-Familie testen |
| Boden-Kalibrierziel | 0,12 statt 0,18 probeweise rendern und gegen den Bullet-Kontrast prüfen (dunklerer Boden hebt ihn tendenziell an) |
| Bullet-Licht-Obergrenze | 25 % (Vorschlag oben) im Kontrast-Checker gegen die Engine bestätigen (nicht nur gegen den Spike); ggf. niedriger, wenn das GPU-Budget es erlaubt |
| OF-3.2 Schatten | Key-Light-Shadowmap plus begrenzte Punktlicht-Schattenwerfer (Mond, Fackeln/Kohlebecken, Stab-Orb, wie im Blender-Vergleich getestet), Blob-Schatten für Preset „Low" |
| OF-3.4 Texturformat | KTX2 mit BC7 (Desktop) / ASTC (Mobile-Ziel P2) und Mipmaps, Entscheidung zusammen mit der Blender-Pipeline (P2) |
| OF-3.5 Kantenglättung Glanzlicht | Geometrisches Spekular-Anti-Aliasing (wie im Realistic-Shader des Spikes) statt TAA — günstiger, kein History-Buffer nötig, Ebene 4/6 ohnehin unberührt |

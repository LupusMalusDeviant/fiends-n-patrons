# ADR-0014: Realistischer 3D-Look statt Toon-Shading

- **Status:** Akzeptiert (2026-09-15; PO-Entscheidung nach Vergleichsbildern)
- **Datum:** 2026-09-15
- **Entscheider:** Lupus Malus Deviant (PO), vorbereitet durch Claude (Empfehlung war Option B)
- **Ändert:** [PRD-0003](../prd/0003-rendering-und-art.md): Ziel „Toon-2.5D-Look“, Nicht-Ziel „Kein PBR/Realismus“, FR-01 (Toon-Pass + Outlines), FR-13 (Toon-Material-Parameter), OF-3.1 (Outline-Technik) entfällt, OF-3.2 (Schatten) wird dringlich
- **Bezug:** [PRD-0003](../prd/0003-rendering-und-art.md) (Render-Ebenen, Regeln 1–4, Budgets), [PRD-0016](../prd/0016-tooling-suite.md) (FR-09 Blender-Pipeline, Kontrast-Checker), [ADR-0007](0007-offline-asset-kompilierung.md) (Offline-Asset-Kompilierung), [ADR-0012](0012-lizenz-alle-rechte-vorbehalten.md) (Lizenz), [Plan 0002](../plans/0002-phase-p1-sichtbarer-kern.md) (WP2), Look-Dev-Spike auf Branch `p1/wp2-look-dev-spike` im Engine-Repo

## Kontext und Problemstellung

PRD-0003 schreibt einen Toon-Look vor: Cel-Shading mit 2–4 Lichtbändern, Outlines und ausdrücklich
kein PBR. Vor dem Bau der Render-Bühne (Plan 0002, WP2) hat der PO erwogen, das Cel-Shading durch
einen 3D-Look zu ersetzen, und wollte vorher Vergleichsbilder sehen.

Dafür wurde eine Testszene festgelegt und in drei Looks gerendert, jeweils „ruhig“ (24 Lichter,
180 Bullets) und „Gewühl“ (232 Lichter, 2.000 Bullets): eine Steinarena mit Säulen, Ruinen, Altar,
Ritualkreis, Spieler und acht Gegnern. Die drei Looks waren **Toon** (3 Bänder, Outlines),
**stilisiertes 3D** (weiches Wrap-Licht, Schattentönung, Kantenlicht an Figuren) und **realistischer**
(GGX-Mikrofacetten, Rauheit/Metall, kein Kantenlicht). Geometrie, Lichter, Albedo und Kamera sind in
allen Looks gleich. Die Bullets werden unabhängig vom Look nach dem Post-Processing gezeichnet (Regel 1).
Jeder Look wird so kalibriert, dass der Median des Bodens gleich hell ist.

Gerendert wurde zweimal. Blender 5.2 mit Eevee rendert echtzeitnah mit Schatten und Kantenglättung;
das zeigt, wie der Look mit einem ausgereiften Renderer wirkt. Der Engine-Spike nutzt wgpu über den
Software-Adapter, ohne Schatten; das zeigt, was die Engine heute schafft, und gibt relative Kosten.

Messwerte aus Blender. Kontrast ist das WCAG-Kontrastverhältnis gegen einen Ring um das Objekt.
„Gewühl gedimmt“ ist das Gewühl mit den 70 Lichtern an den Bullet-Wolken auf 25 %.

| Look | Bullets ≥ 4,5:1 ruhig / Gewühl / Gewühl gedimmt | Figuren-Kontrast Median Gewühl / gedimmt |
|---|---|---|
| Toon | 50 % / 49 % / 50 % | 3,46 / 3,50 |
| Stilisiert | 30 % / 11 % / 26 % | 1,72 / 2,82 |
| Realistischer | 37 % / 13 % / 33 % | 1,67 / 2,15 |

Der Engine-Spike bestätigt die Richtung. Im Gewühl erreichen 33 % der Bullets bei Toon 4,5:1,
bei stilisiert und realistischer je 21 %. Die Kosten sind nur relativ und auf dem Software-Adapter
gemessen: Gewühl-Frame Toon 1,00, stilisiert 0,88, realistischer 0,81, weil der Outline-Pass entfällt.
Die Entwurfsschätzung für die Produktion mit geclustertem Licht sieht den GGX-Lichtterm dagegen beim
1,6- bis 2,0-fachen des Toon-Terms je Fragment.

**Kernfrage:** Mit welchem Look wird die 2.5D-Bühne gebaut, und was muss sich dafür an den
Anforderungen ändern?

## Anforderungen

### Funktional

- Lesbarkeit ist heilig (E18): Regeln 1–4 aus PRD-0003 bleiben unverändert und im Renderer erzwungen.
- Dynamisches Licht mit ≥ 256 Punktlichtern (FR-02), Dark-Fantasy-Stimmung durch Licht.
- Modelle kommen per Skript aus Blender als glTF (PRD-0016 FR-09); alles muss ohne Handarbeit des PO entstehen.

### Nicht-Funktional

- Budget GPU-Frame ≤ 8 ms bei Vollszene auf Referenz-Hardware; Preset „Low“ für Mobile ≤ 16 ms.
- Aufwand für generierte Assets (Modelle, Materialien, Texturen) bleibt für Agenten beherrschbar.
- Lizenzlage aller Asset-Quellen ist mit „Alle Rechte vorbehalten“ (ADR-0012) vereinbar.

## Betrachtete Optionen

### Option A: Toon wie in PRD-0003

Quantisierte Lichtbänder und Outlines, keine Texturen nötig.

**Positiv:**
- In beiden Renderern im Gewühl am besten lesbar; die Bänder deckeln die Helligkeit der Lichtkegel.
- Geschlossene Konturen trennen Figuren auch im Dunkeln.
- Kaum Texturarbeit, Materialien sind Farben und Parameter.

**Negativ:**
- Bei vielen Lichtern zerfällt der Boden in harte, laute Farbflecken; große Gegner wirken flach.
- Treppenstufen an Bandkanten und Outlines ohne Supersampling; zusätzlicher Outline-Pass.
- Gefällt dem PO im direkten Vergleich klar weniger als die 3D-Looks.

### Option B: Stilisiertes 3D

Weiches Licht ohne Stufen, Schattentönung, Kantenlicht an Figuren, vereinfachte Materialien.

**Positiv:**
- Wirkt wie ein fertiges Spiel; das Kantenlicht trennt Figuren auch in unbeleuchteten Bereichen.
- Braucht nur einfache, per Skript gut erzeugbare Texturen; günstiger für Mobile/Low.
- Gewinnt durch gedimmte Bullet-Lichter am meisten (Figuren-Kontrast 1,72 → 2,82).

**Negativ:**
- Im Gewühl deutlich schlechter lesbar als Toon (11 % bzw. 26 % gedimmt).
- In den Testbildern von Option C schwer zu unterscheiden, solange die Modelle keine Texturen haben.
- Das Kantenlicht wirkt an einfachen konvexen Platzhaltern besser als an detaillierten Modellen.

### Option C: Realistischer 3D-Look (PBR)

Physikalisch plausibles Licht (GGX, Rauheit/Metall) ohne Kantenlicht und Outlines.

**Positiv:**
- Glaubwürdige Lichtkegel, Schatten und Metallreflexe tragen die Dark-Fantasy-Stimmung.
- glTF bringt Metallic-Roughness-Materialien schon mit; Blender exportiert sie direkt.
- Freie CC0-Texturbibliotheken passen ohne Umbau zum Materialmodell.

**Negativ:**
- Im Gewühl ähnlich schlecht lesbar wie B (13 %, gedimmt 33 %); Figuren trennen sich nur über Licht und Kontrast.
- Ohne Texturen, Normalen-Details und Schatten wirken Modelle wie Plastik; volle Textursätze je Modell sind nötig.
- Teuerster Lichtterm je Fragment, Glanzlichter flimmern ohne TAA oder Spekular-AA; auf Mobile braucht die GGX-Verteilung hohe Präzision.

## Entscheidung

Gewählt: **Option C, realistischer 3D-Look mit PBR-Materialien**, Texturen **prozedural in Blender
gebacken und ergänzt durch CC0-Bibliotheken** (z. B. ambientCG, Poly Haven).

Der PO hat nach den Vergleichsbildern die 3D-Modelle klar über Toon gestellt und zwischen den beiden
3D-Looks den realistischeren gewählt. Die Lesbarkeitsverluste im Gewühl sind bekannt. Sie werden
nicht über den Look ausgeglichen, sondern über verbindliche Gegenmaßnahmen (siehe Konsequenzen).

## Konsequenzen

### Positiv

- Der Outline-Pass und der Spike OF-3.1 entfallen.
- Das Materialmodell entspricht glTF Metallic-Roughness; die Blender-Pipeline muss nichts übersetzen.
- CC0-Texturen verkürzen den Weg zu glaubwürdigem Stein, Holz und Metall.

### Negativ

- **Lesbarkeit braucht harte Regeln.** Diese Punkte gehen als Pflicht in PRD-0003 und die Stilbibel ein:
  - Licht, das von Bullets oder Bullet-Wolken ausgeht, wird in seinem Beitrag zum Boden begrenzt. Im Spike stieg der Anteil lesbarer Bullets allein dadurch von 13 % auf 33 %.
  - Die Umgebung bleibt dunkel und entsättigt, wie im Palettenraum der Stilbibel festgelegt.
  - Der Kontrast-Checker aus PRD-0016 bleibt Freigabe-Gate.
  - Die Regeln 1–4 bleiben unverändert.
- **Schatten werden Pflicht statt Option.** OF-3.2 wird zur Frage, welche Schatten-Technik im Budget bleibt (etwa Key-Light plus wenige Schattenwerfer, Low-Preset mit Blob-Schatten).
- **Kantenglättung für Glanzlichter.** TAA oder Spekular-AA ist nötig. Bullets und Telegraphie bleiben davon unberührt, weil sie nach dem Post-FX-Resolve gezeichnet werden.
- **Mehr Asset-Aufwand.**
  - Jedes Modell braucht Albedo, Normalen, Rauheit/Metall und AO.
  - Die Engine braucht komprimierte Texturen mit Mipmaps; das Format ist noch offen.
  - Die Packs werden größer.
- **Lizenzen dokumentieren.** Jede CC0-Quelle wird im Asset-Manifest mit Herkunft und Lizenz festgehalten. CC0 erlaubt die Weitergabe in den Packs; die Texturen selbst bleiben CC0.
- **Folgeänderungen in Plan 0002, WP2:**
  - WP2.2 bekommt ein PBR-Material statt `ToonMaterial`.
  - WP2.5 wird zum PBR-Pass mit Spekular-AA statt Toon und Outline-Spike.
  - WP2.6 entscheidet die Schatten-Technik.
  - WP2.7: Die Stilbibel regelt Materialwerte und Helligkeitsgrenzen statt Bänder und Outlines.
  - WP2.8 bekommt Testszenen für Materialien und Schatten statt `toon_bands` und `outline`.
- **Kostenrisiko.** Bei 256 Lichtern ist das 8-ms-Budget mit GGX und Schatten enger als mit Toon. Die P1-Messsitzung muss das früh zeigen.

## Weitere Informationen

- **Vergleichsmaterial:** Szene, Skripte und Messwerte liegen auf dem Engine-Branch `p1/wp2-look-dev-spike`, unter `spikes/look-dev` (wgpu) und `spikes/look-dev-blender` (Blender/Eevee). Bilder und Messwerte sind reproduzierbar; PNGs werden nicht versioniert.
- **Spike-Grenzen:** Es gab nur Platzhalter-Geometrie ohne Texturen, und genau das benachteiligt den realistischen Look am stärksten. Die Engine-Kosten stammen vom Software-Adapter und sind kein GPU-Budget.
- **Offene Folgefragen** (zur Entscheidung vor bzw. in WP2):
  - Schatten-Technik und Anzahl der Schattenwerfer.
  - Obergrenze für Bullet-Licht.
  - Texturformat und -auflösung.
  - TAA oder Spekular-AA.
- Review dieser Entscheidung nach dem ersten PBR-Stand in WP2 (Reality-Check nach 4–8 Wochen).

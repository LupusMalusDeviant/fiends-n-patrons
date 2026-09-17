# Agentenlauf 2026-09-17

- **Stand:** 2026-09-17
- **Bezug:** [Plan 0002](0002-phase-p1-sichtbarer-kern.md), [Stilbibel](../art/stilbibel.md), [Figuren-Quellen](../../assets_src/figures/README.md)

Fortsetzung des vorigen Agentenlaufs ([agentenlauf-2026-09-16.md](agentenlauf-2026-09-16.md)). Auftrag des PO
für die Nacht: Rendern, Engine, neue 3D-Modelle und ein erster spielbarer Prototyp; die Auswahl liegt beim
Lauf. Der Lauf arbeitet ohne Rückfragen und sammelt alles, was eine PO-Entscheidung braucht, mit Empfehlung.
Tags, Releases und Veröffentlichungen sind ausgenommen.

## Stränge

| Strang | Inhalt | Ziel bis zum Morgen | Grenze |
|--------|--------|---------------------|--------|
| Assets | Figuren Runde 4: eigenes UV-Layout je Material, Texturen im Objektraum, Formnormale ohne Cycles-Bake, Wiederholbarkeit | Gemergter Pull Request, Vorher-Nachher-Bilder in Nahaufnahme und Spielgröße | Nur Blender im Hintergrund, nur CPU |
| Engine | WP3.5 Bullet-Pass und WP5.3 Extraktion Sigil → Render | Pull Request mit grüner 3-OS-CI, danach Merge | Kein Tag; Vertragsänderungen nur additiv und als Stufe A markiert |
| Spiel | Erster spielbarer Prototyp: Seele, Imp, Sigil-Muster, Treffer, Neustart | Entwurfs-Pull-Request mit grüner CI, signierte ausführbare Datei außerhalb des Repos | Nicht nach `main`: der Zweig braucht Engine-Code ohne Release-Tag |

## Verhaltensregeln für alle Agenten

- Jeder Push, der eine CI auslöst, wird bis zum Ende beobachtet; rote Läufe werden sofort analysiert und die Ursache benannt.
- Render nur offscreen über den Software-Adapter; ein echtes Fenster nur als kurzer Rauchtest mit harter Bildgrenze.
- Nichts Privates in die öffentlichen Repos: keine lokalen Pfade, keine Mailadressen, keine Uhrzeiten, keine Angaben zu Hardware oder Arbeitsweise des PO.
- Kein Force-Push, keine Tags, kein Merge durch Agenten; gemergt wird nach festem Ablauf erst nach grünen Läufen.

## Ergebnisse

### Assets — Figuren Runde 4

Gemergt als Spiel-PR #4 (Absicherung, `166101e`) und #5 (Runde 4, `f9c9042`); Einzelheiten im
[Nachtrag zu Plan 0002](0002-phase-p1-sichtbarer-kern.md) und in der [README der Figuren](../../assets_src/figures/README.md).
Kurz: drei gemessene Ursachen (Grundmuster im UV-Raum, geteilte Texel nach dem Kacheln, umgekehrter Grünkanal
der Detail-Normalen), zwei beim Bauen gefundene Fehler (gemeinsames Packen aller Materialien, umgekehrte
Normalen aus dem Cycles-Bake) und eine Wiederholbarkeitslücke im eigenen Aufbau der Figuren. Zwei vollständige
Läufe ergeben seitdem bytegleiche Texturen und bytegleiche sparsame `.glb`.

### Spiel — erster spielbarer Prototyp

Entwurfs-PR #6, CI grün auf Windows, Linux und macOS. Eine beleuchtete Arena mit der Seele als Spielfigur
(WASD oder Pfeiltasten, die Kamera folgt), ein Imp feuert das Sigil-Muster `content/sigil/imp_volley.sigil`
über den Interpreter der Engine; ein Treffer wirft die Seele um, räumt die Geschosse und startet die Runde nach
kurzer Pause neu. Ein neuer Determinismustest mit eingefrorenem Hash deckt die Arena über 1, 2 und N Threads ab.
Vorläufig und im Code markiert: Geschosse als leuchtende Kugeln bis zum Bullet-Pass, eigene Treffererkennung bis
zum Adapter Sigil → Kollision, eigene Hauptschleife, weil `App::run` Plugins keinen Zugriff auf den Renderer gibt.
Der Zweig bindet die Engine an einen Commit auf `main` statt an einen Tag und bleibt deshalb ungemergt.

Nach dem Merge der Geschoss-Ebene wurde der Prototyp umgestellt: Die Geschosse kommen jetzt über den Adapter
Sigil → Render aus der Engine, und die Engine leitet ihre Lichter selbst ab. Dabei fiel eine echte Falle auf: Der
Sigil-Compiler nummeriert Paletten je Unit alphabetisch, der Bullet-Pass nach seiner Tabelle, und der Adapter
bildet per Identität ab – Magenta und Limette wären vertauscht gezeichnet worden, ohne dass ein Zähler anschlägt.
Die Paletten heißen jetzt wie in der Tabelle, ein Test prüft die Namen; der Arena-Hash änderte sich dadurch
einmal, belegt allein durch die Inhaltsidentität der Unit. Verworfene Geschosse im Offscreen-Lauf und im
Fenster-Rauchtest: 0. **Auf der Grafikkarte gemessen** (Vulkan, 900 Bilder, Fenster ohne Fokus): 6,9 ms je Bild
im Mittel, langsamstes Bild 17 ms; auf dem Software-Renderer rund 97 ms.

## Offene PO-Entscheidungen

Gesammelt mit Empfehlungen, außerhalb des Repos vorgelegt. Die wichtigsten: ein Engine-Release-Tag, damit der
Prototyp nach `main` kann; ein Fassaden-Haken, über den Plugins Assets beim Renderer anmelden; ein gemeinsamer
Katalog für Silhouetten und Paletten statt Nummerierung je Unit; die Bestätigung des neuen Arena-Hashes.

### Engine — WP3.5 und WP5.3

Gemergt als Engine-PR #29 (`a01495c`), CI auf `main` samt GIF-Job und Benchmark-Gate grün. Der Renderer hat jetzt
den fest verdrahteten Pass-Graph mit eigener Geschoss-Ebene: Billboards mit Distanzfeld-Silhouetten, Stilbibel-Paletten,
Kern, Rand und Leuchthof, gezeichnet nur im gegnerischen Palettenraum, dazu höchstens acht abgeleitete
Geschoss-Lichter über den einzigen erlaubten Weg. Der Fassaden-Adapter Sigil → Render extrahiert 10.000 Geschosse
in rund 0,04 ms auf dem CI-Runner. Einzelheiten und offene Punkte in den Einträgen WP3.5 und WP5.3 von
[Plan 0002](0002-phase-p1-sichtbarer-kern.md). 
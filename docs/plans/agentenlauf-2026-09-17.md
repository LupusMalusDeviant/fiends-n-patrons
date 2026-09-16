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

### Engine — WP3.5 und WP5.3

Läuft.

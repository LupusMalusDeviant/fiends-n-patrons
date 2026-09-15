# Agentenlauf 2026-09-16

- **Stand:** 2026-09-16
- **Bezug:** [Plan 0002](0002-phase-p1-sichtbarer-kern.md), [ADR-0014](../adr/0014-realistischer-3d-look-statt-toon.md), [Stilbibel](../art/stilbibel.md)

Fortsetzung des vorigen Agentenlaufs ([agentenlauf-2026-09-15.md](agentenlauf-2026-09-15.md)). Der Lauf
arbeitet ohne Rückfragen; alles, was eine PO-Entscheidung braucht, wird mit Empfehlung gesammelt und
später vorgelegt. Veröffentlichungen, Tags und Releases sind ausgenommen und bleiben liegen.

## Ausgangslage

WP1 ist abgeschlossen. Gemergt sind außerdem WP2.1 (Adapter-Bericht je Runner), WP2.2 (Render-Vertrag v1
mit `PbrMaterial`), WP2.3 (Mesh-Pass mit Tiefenpuffer), WP8.1 (Schema-Codegen) und WP6.2 (Benchmark-Gate
im Warnmodus). Sammelsitzung B ist entschieden: Sigil-Compiler-Hoheit, Sigil-Syntax „sigil 1“,
Schema-Codegen aus einer Quelle und die Benchmark-Strategie mit Callgrind-Instruktionszählung.

## Stränge

| Strang | Inhalt | Ziel bis zum Morgen | Grenze |
|--------|--------|---------------------|--------|
| Assets | Figuren mit durchgehender Topologie und echtem Skelett, Stoffsimulation, UV-Auspacken, glTF mit Skin | Belegbilder (Nah, Drahtgitter, Posen, Dreh, Spielkamera) und ehrliche Bewertung, ob die Qualität für eine Asset-Pipeline taugt | Keine Downloads, keine fremden Asset-Bibliotheken, nur Blender im Hintergrund |
| Engine | WP2.4 (Kamera) abschließen, danach WP2.5 (PBR-Shading mit Texturen) und Vorbereitung des Schattenentscheids (OF-3.2) | Gemergte Pull Requests mit grüner 3-OS-CI | Kein Tag, kein Release; Vertragsänderungen nur additiv und dokumentiert |
| Aufräumen | Trend-Publisher reparieren, Trenddaten-Branch nachweisen, Plan-Einträge, dieses Protokoll | `bench-trends` existiert mit Messwerten; Plan ist aktuell | — |

## Verhaltensregeln für alle Agenten

- Jeder Push, der eine CI auslöst, wird bis zum Ende beobachtet; rote Läufe werden sofort analysiert und die Ursache benannt (Code, Vorrichtung oder Fremdeinfluss).
- Keine Fenster, keine GUI-Programme, keine Beispiele mit Fenster; Render nur offscreen.
- Vor jedem GPU-Render prüft ein Wächter, ob der Entwicklungsrechner gerade anderweitig gebraucht wird; meldet er belegt, entfällt der Render und die CI übernimmt.
- Nichts Privates in die öffentlichen Repos: keine lokalen Pfade, keine fremden Mailadressen, keine Angaben zur Arbeitsweise des PO, keine Hardware.
- Vertragsänderungen folgen dem Änderungsprotokoll: Klarstellungen ohne Freigabe, additive und brechende Änderungen gesammelt zur Freigabe.

## Ergebnisse

Werden im Lauf ergänzt.

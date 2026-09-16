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

## Ergebnisse (Zwischenstand)

### Engine

- **WP2.4 Kamera** gemergt (Engine-PR #11, Merge-Commit `6e96ed6`): renderseitiges Following mit kritisch gedämpfter Feder und Vorausschau, Mauszielen mit deterministischer Quantisierung in die Eingabe-Achsen, Fassaden-Haken für Fokus und Bühnen-Extraktion. Das Replay-Gate belegt identische Simulations-Hashes unter zwei verschiedenen Kameraeinstellungen; alle Goldens unverändert. PO-Entscheide dazu: Vorausschau als Fokus-Geschwindigkeit mal einer Sekunde (begrenzt), Kamera nur nach ausdrücklicher Anmeldung durch das Spiel, Marker-Werte vorläufig bis zur Stilbibel.
- **WP6.2 Benchmark-Gate** vollständig dokumentiert. Der erste Lauf auf `main` war rot: ein Apostroph in einer Parameter-Ersetzung ließ im Trend-Skript ein Anführungszeichen offen, und der Job läuft nur bei Push auf `main`, war also in keinem Pull Request geprüft worden. Engine-PR #12 (`34689a0`) behebt das, prüft seitdem **jedes CI-Skript mit `bash -n` schon im Pull Request** und reicht die Runner-Bezeichnung über eine Umgebungsvariable statt als Ausdruck im Shell-Block durch. Seitdem ist das Gate auf `main` grün und der Trenddaten-Branch `bench-trends` existiert mit den ersten Messwerten.
- **WP8.2 Debug-Protokoll** liegt als Engine-PR #13 mit grüner CI vor: Nachrichten-Katalog mit Richtungsprüfung, Handshake nach PO-Entscheid V-13 (andere Engine-Version immer abgelehnt, anderer Build nur bei beidseitig bekanntem Hash, unbekannt mit Warnung), handgeleitete Byte-Fixtures. Der unabhängige Review fand zwei echte Fehler in neuem Code: die Verarbeitung nach dem Handshake war öffentlich aufrufbar und damit umgehbar, und der Empfang des ersten Frames verwarf stillschweigend alle weiteren im selben Abruf gelesenen Frames. Beide sind behoben und mit Tests abgesichert, dazu fünf kleinere Punkte. Gemergt als `d97cd21`, Push-CI auf `main` grün. Nacharbeit für WP8.4: der Schutz gegen zu große erste Frames fehlt am TCP-Transport noch. Die zunächst gemeldete \"neue Fehlervariante\" ist keine Vertragsänderung: §13 nennt sie bereits.
- **WP2.5 PBR-Shading** gemergt (Engine-PR #14, Merge-Commit `45deded`): GGX-Mikrofacetten mit Metall- und Rauheitswerten, Punktlichter durch denselben Term, analytischer Umgebungsterm, Textur-Registry mit den Farbräumen aus dem Vertrag und geometrisches Spekular-Antialiasing. Der Spike zu OF-3.5 misst dafür rund das 1,3-fache an Rechenzeit auf dem Software-Adapter; TAA wurde mangels Verlaufspuffer nur auf dem Papier bewertet. Ergebnis als Engine-ADR-Vorschlag „Spekuläres Anti-Aliasing statt TAA“, Annahme durch den PO offen.

### Assets mit Skelett

Runde 1 ist fertig und beantwortet die Kernfrage: Der Skript-Ansatz trägt, wenn die Fläche als **eine durchgehende Quad-Fläche** entsteht statt aus zusammengesetzten Grundkörpern. Belegt an drei Figuren (Spielerfigur, Imp, Brute): geschlossene Netze ohne fehlerhafte Kanten, saubere Kantenschleifen im Drahtgitter, Skelette mit 20 bis 27 Knochen, geprüfte Gewichtung ohne ungewichtete Punkte, Posen-Reihen als Nachweis der Verformung, Umhang aus einer Stoffsimulation mit echten Falten, UV-Auspacken mit gemessener Texeldichte und glTF-Export mit Skin.

Offene Mängel nach eigener Sichtprüfung der Bilder: der Stab hängt starr neben der Hand statt gegriffen zu werden, den Figuren fehlen Gesichter, der Imp hebt sich zu wenig vom Boden ab, die Figurentexturen sind zu flach (gemessener Albedo-Kontrast 1,12:1), und die Dreiecksmengen sind für den Spielbetrieb zu hoch. Runde 2 arbeitet genau daran, zusätzlich an einer sparsamen Spielstufe mit eingebackenen Normalen.

Zwei Werkzeugfallen sind dokumentiert: Ein Extrudieren lässt die Ausgangsflächen stehen, wodurch Blender die automatische Gewichtung **stillschweigend** verweigert; und das Angleichen der UV-Inseln meldet Erfolg, tut aber nichts.

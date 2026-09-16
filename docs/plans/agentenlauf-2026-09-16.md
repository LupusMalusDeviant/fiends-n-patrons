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

- **WP2.6 Schatten** gemergt (Engine-PR #15, Merge-Commit `315930d`): Schattenkarte fuer das Key-Light mit weicher Filterung, Blob-Schatten als guenstige Alternative, Modus umschaltbar. Gemessen kostet die Schattenkarte auf dem Software-Adapter etwa das Doppelte, Blob praktisch nichts. Engine-ADR-Vorschlag zu OF-3.2 liegt vor, Entscheid offen.
- **WP8.2 Debug-Protokoll** gemergt (Merge-Commit `d97cd21`).

- **WP2.8 Render-Testszenen und M1-Schaufenster** gemergt (Engine-PR #16, Merge-Commit `21734e6`): die Szenen `pbr_materials`, `shadows` und `camera_tilt` rendern offscreen auf dem Software-Adapter und werden mit einer Toleranzmetrik gegen versionierte Referenzbilder verglichen, zunaechst im Warnmodus; dazu das Schaufenster-Beispiel `pbr_stage` und ein Job, der daraus eine Bildfolge rendert und als GIF ablegt. Dieser Job wird bei Pull Requests uebersprungen - und wurde deshalb zweimal erst auf `main` rot. Erst suchte der Shell-Schritt die Einzelbilder im Wurzelverzeichnis, waehrend der Test sie relativ zum Paketverzeichnis schreibt (behoben in PR #17, `e0624e6`); dann fehlte ffmpeg, das der Job faelschlich als vorinstalliert annahm (behoben in PR #18, `48b90c7`). Seitdem ist er auf `main` gruen. Daraus folgt eine Regel fuer alles Weitere: Ein Job, den kein Pull Request ausfuehrt, wird vor dem Merge per `workflow_dispatch` auf dem Arbeitszweig nachgewiesen. Fuer PR #18 ist genau das geschehen, bevor er gemergt wurde - der Zweig-Lauf zeigte den GIF-Job gruen, und der anschliessende Lauf auf `main` bestaetigte es.

### Assets mit Skelett

Runde 1 ist fertig und beantwortet die Kernfrage: Der Skript-Ansatz trägt, wenn die Fläche als **eine durchgehende Quad-Fläche** entsteht statt aus zusammengesetzten Grundkörpern. Belegt an drei Figuren (Spielerfigur, Imp, Brute): geschlossene Netze ohne fehlerhafte Kanten, saubere Kantenschleifen im Drahtgitter, Skelette mit 20 bis 27 Knochen, geprüfte Gewichtung ohne ungewichtete Punkte, Posen-Reihen als Nachweis der Verformung, Umhang aus einer Stoffsimulation mit echten Falten, UV-Auspacken mit gemessener Texeldichte und glTF-Export mit Skin.

Offene Mängel nach eigener Sichtprüfung der Bilder: der Stab hängt starr neben der Hand statt gegriffen zu werden, den Figuren fehlen Gesichter, der Imp hebt sich zu wenig vom Boden ab, die Figurentexturen sind zu flach (gemessener Albedo-Kontrast 1,12:1), und die Dreiecksmengen sind für den Spielbetrieb zu hoch. Runde 2 arbeitet genau daran, zusätzlich an einer sparsamen Spielstufe mit eingebackenen Normalen.

Zwei Werkzeugfallen sind dokumentiert: Ein Extrudieren lässt die Ausgangsflächen stehen, wodurch Blender die automatische Gewichtung **stillschweigend** verweigert; und das Angleichen der UV-Inseln meldet Erfolg, tut aber nichts.

### Assets, zweite Runde

Die zweite Runde behebt die Maengel der ersten und liefert zusaetzlich eine sparsame Spielstufe.

- **Griff:** Der Stab sitzt jetzt zwischen den Fingern; der Fehler lag in der Ruhepose, nicht in der Bindung an das Skelett.
- **Gesichter:** Imp mit Schnauze, Mundfurche, Nuestern und leuchtenden Augen; Brute mit Kiefer, tieferen Augenhoehlen und leuchtenden Augen; die Maske der Spielerfigur mit dunklen Sehschlitzen. Die Augen mussten per Strahlenschnitt auf der tatsaechlichen Oberflaeche platziert werden, weil geschaetzte Positionen unter der Haut verschwanden.
- **Texturen:** eigens erzeugt, mit Merkmalen im Bereich von 10 bis 30 Zentimetern statt feinem Rauschen, das aus der Spielkamera flimmern wuerde. Kontrast der Imp-Haut von 1,10 auf 2,01, der Brute-Haut von 1,08 auf 1,74, mittlere Neigung der Normalen jeweils verdreifacht.
- **Spielstufe:** je Figur eine sparsame Variante mit eingebackenen Normalen (rund 7.000 bis 8.700 Dreiecke statt 28.000 bis 35.000), gleiche Knochen und Gewichte; die Spielansicht ist aus dieser Stufe gerendert.
- **Altfehler gefunden:** Beim Imp war die automatische Gewichtung in Runde 1 vollstaendig fehlgeschlagen und nur durch einen Notbehelf verdeckt. Runde 2 uebertraegt echte Gewichte und behebt das.

Eigene Sichtpruefung: Die Gesichter lesen sich jetzt auch aus der Spielkamera, vor allem ueber die leuchtenden Augen. Offen bleibt Handarbeit: Die Augen sitzen als flache Scheiben auf der Oberflaeche statt in ausmodellierten Hoehlen, die Koepfe sind weiterhin glatt, und die Texturen sind Rauschen statt erzaehlter Details.

### Assets, dritte Runde

Die dritte Runde arbeitet die drei Maengel der zweiten ab: flache Augenscheiben, glatte Koepfe, Texturen aus Rauschen. Gemessen ist der Fortschritt echt: die Augenhoehlen sind jetzt geschnitzte Kavitaeten mit Rand, Wand und Boden (12,0 mm beim Imp, 17,2 mm beim Brute) und bleiben auch bei stark gedrehtem Kopf offen; elf beziehungsweise acht neue Verformungen geben Brauenwulst, Jochbein, Kieferwinkel, Schlaefe und Hornansatz; der Texturkontrast stieg erneut (Imp-Haut 2,01 auf 2,29, Brute-Fleisch 1,74 auf 2,95, Umhang 1,31 auf 1,74), die Schulterplatten haben erstmals ein echtes Metallfeld statt eines konstanten Nullwerts, und das Backen der Normalen auf die sparsame Stufe gelang fuer alle Materialien aller drei Figuren.

**Eigene Sichtpruefung, und die faellt nuechterner aus als der Messbericht.** Die Kopfstruktur liest sich tatsaechlich besser: Schnauze, Brauenwulst und Wangenkante des Imps sind aus der Nahaufnahme klar erkennbar. Aber die Augen wirken weiterhin wie flache, ueberstrahlte Leuchtscheiben - die aufwaendig geschnitzte Hoehle ist im Bild nicht zu sehen, weil das Eigenleuchten sie vollstaendig ausfuellt. Das Horn des Imps liest sich als aufgeklebtes schwarzes Fremdteil, was zur eingeraeumten Panne passt: sein Texturbacken schlug fehl und fiel auf die Grundtextur zurueck. Der Brute glaenzt viel zu stark und wirkt wie nasses Plastik statt wie Fleisch, seine Schulterplatte wie eine aufgelegte Scheibe. Im Drahtgitter sind die Hoehlen mit Dreiecksfaechern eingesetzt statt mit sauberen Kantenschleifen; der uebrige Koerper bleibt Vierecksflaeche. Aus der Spielkamera dagegen funktioniert die Szene: die drei Figuren sind an Silhouette und Groesse klar unterscheidbar, Schatten und Lichtpfuetzen sitzen.

Zwei Werkzeugbefunde sind dokumentiert: das Backen ueber den Pfadverfolger liefert auf diesem Rechner bei gleichem Code unterschiedliche Ergebnisse je Lauf - im ausgelieferten Stand fehlen deshalb zwei Texturen -, und ein Vergleich von Knoten ueber die Objektidentitaet statt ueber den Namen liess zwischenzeitlich alle drei Figuren vollstaendig schwarz rendern. Der zweite Fehler ist behoben, der erste bleibt als Eigenschaft der Umgebung bestehen und verlangt eine Pruefung, die einen unvollstaendigen Lauf abbricht statt ihn auszuliefern.

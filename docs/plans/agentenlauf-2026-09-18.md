# Agentenlauf 2026-09-18

- **Stand:** 2026-09-18
- **Bezug:** [Plan 0002](0002-phase-p1-sichtbarer-kern.md), [Asset-Import-Pilot](0002-asset-import-pilot.md), [Figuren-Quellen](../../assets_src/figures/README.md)

Fortsetzung des vorigen Agentenlaufs ([agentenlauf-2026-09-17.md](agentenlauf-2026-09-17.md)). Der PO hat am Abend
**M3 gestartet** und einen Figuren-Import-Piloten parallel dazu beauftragt. Gearbeitet wurde in beiden Repos
gleichzeitig, ohne Rückfragen; alles, was eine Entscheidung braucht, ist mit Empfehlung gesammelt und im
Entscheidungsabschnitt von Plan 0002 vermerkt. Tags und Veröffentlichungen bleiben beim PO.

## Stränge

| Strang | Inhalt | Ergebnis |
|--------|--------|----------|
| Engine | Die M3-Pakete: Kollision v0, Vollvorhang-Bench, Replay v2, Subsystem-Hashes, Pack v1, Debug-Link, C#-Suite, `grimoire-link`, Asset-Compiler | Neun Pakete gemergt, Release `v0.5.0` |
| Spiel | Prototyp auf `v0.4.0` neu gebaut; danach Asset-Compiler-Gate und Pin auf `v0.5.0` | Zwei Pakete gemergt, das Gate ist scharf auf `main` |
| Assets | Asset-Import-Pilot: fremd erzeugte Hexe und Imp in vier Stufen bis ins Engine-Bild | Fünf Pakete gemergt, Stufe 4 in der Engine gemessen |
| Doku | Nachbuchung: Änderungsprotokoll der Verträge, Planeinträge, PO-Entscheide | Drei Pakete im Engine-Repo, zwei im Spiel-Repo |

## Verhaltensregeln für alle Agenten

- Jeder Push, der eine CI auslöst, wird bis zum Ende beobachtet; ein roter Lauf wird vor jeder Weiterarbeit
  analysiert und nach Code, Vorrichtung oder fremder Ursache benannt.
- Render nur offscreen über den Software-Adapter; kein Fenster auf dem Hauptbildschirm, keine echte Grafikkarte
  außerhalb einer Messsitzung.
- Nichts Privates in die öffentlichen Repos: keine lokalen Pfade, keine Mailadressen, keine Uhrzeiten, keine
  Angaben zu Hardware oder Arbeitsweise des PO.
- Kein Force-Push, keine Tags durch Agenten, kein Merge durch Agenten; gemergt wird erst nach grünen Läufen.

## Ergebnisse

### Engine — die M3-Pakete

| Paket | Engine-PR | Merge | Kern |
|---|---|---|---|
| WP7.1 Replay v2 | #52 | `521f3d7` | Swap-Markierung aufzeichnen, Build-Hash in den Workflows, Fixtures von der Tagesversion entkoppelt, Formatdoku `replay.md` |
| WP8.3 Pack v1 | #54 | `08c4a40` | Manifest über den generierten Codec, Store-Kennung im Handle, handhergeleitete Fixture, Adapter Assets → Sigil |
| WP6.5 Kollision v0 | #55 | `58d1c64` | Bench, Beispiel, Konformanz-Suite, Allokationsnachweis, Blockszene im Hash-Gate |
| WP7.2 Subsystem-Hashes | #56 | `509d053` | `grimoire_sim::trace` mit Divergenz-Diagnose, Spike-Messung, ADR-0018 |
| WP8.4 Debug-Link | #57 | `51129a0` | Engine-Server ohne Blockieren, TCP-Grenzen, Anzahlprüfung der Decoder, Konformanz-Suiten in der CI |
| WP6.6 Vollvorhang | #58 | `6de23ba` | Bench-Szene in vier Phasen, drei übersetzte Units |
| WP9.1 C#-Suite | #59 | `b72317b` | `tools/` mit `Grimoire.Formats` und `Grimoire.LiveLink`, CI auf drei Betriebssystemen |
| WP8.5 `grimoire-link` | #61 | `33d9a22` | CLI, Headless-E2E-Nachweis des Hot-Reloads, M3-Schaufenster-GIF |
| WP9.2 Asset-Compiler | #62 | `d31f97f` | `grimoire-ac` als Projekt der C#-Suite, Korpuslauf in der CI |

**Gemessen, alles auf CI-Runnern, nichts auf dem Rechner des PO:**

- **Kollision** (10.000 Geschoss-Kreise, 100 Gegner, Budgetlinie 1,5 ms je Tick): `collide_uniform` 0,6481 ms mit
  einem Thread und 0,5954 ms mit vier, `collide_cluster` 0,9316 ms und 0,9286 ms. Alle vier im Budget; ein Urteil
  auf der Instruktionszahl gibt es noch nicht, weil das Szenario keine angenommene Basis hat.
- **Vollvorhang** (rund 10.000 Geschosse, Wanduhr-Median je Tick): Simulation 0,3058 ms, Extraktion 0,1099 ms,
  Kollision 0,5748 ms, Render-Vorbereitung 0,2452 ms — zusammen 1,236 ms, alle vier im Budget. `render_stage` mit
  34,8 ms und die GPU-Zeit mit 34,0 ms bekommen **ausdrücklich kein Urteil**: Auf einem Software-Adapter rastert die
  CPU in genau diesem Aufruf, und die Timestamp-Queries belegen, dass 34,0 der 34,8 ms Adapter-Arbeit sind. Genau
  deshalb ist die Render-Messung in Vorbereitung (mit Budget) und `render_stage` (ohne) geteilt.
- **Subsystem-Hashes:** ein Welt-Hash alle 60 Ticks kostet die 1,03-fache Instruktionszahl eines Schritts, je System
  je Tick die 6,07-fache. Daraus ADR-0018: erkennen alle 60 Ticks, bei einer Abweichung nur das erste Fenster je
  System je Tick eingrenzen. Ein eingebauter Fehler in `collide.resolve` ab Tick 37 wird damit exakt gemeldet.
- **Hot-Reload:** Speichern einer `.sigil`-Datei wirkt ab der bestätigten Tick-Grenze — jeder Hash davor gleich dem
  Lauf ohne Link, jeder danach verschieden. Roundtrip 3,7 ms lokal über den In-Process-Transport bis 42,7 ms im
  CI-Schaufensterlauf, gegen die Vorgabe „unter einer Sekunde“. Das Schaufenster liegt als `hot_swap.gif` im
  CI-Artefakt.
- **Asset-Compiler:** 452 Quellen in 227 ms Wanduhr vollständig neu gebaut, 0,4 % des 60-s-Ziels.
- **C#-Suite:** 101 Tests je Betriebssystem, 0 fehlgeschlagen, auf Windows, Linux und macOS.

**Drei Befunde, die ohne diese Pakete unbemerkt geblieben wären:** Die Allokationszusagen der Kollision waren
verletzt (`rebuild_par` allozierte 849-mal statt konstant oft); die Konformanz-Suiten von `grimoire_assets` und
`grimoire_debug` liefen in der CI **leer**, weil kein Workspace-Mitglied ihr Feature einschaltete; und der
TCP-IO-Thread verwarf bei vollem Kanal eingehende Frames stillschweigend. Alle drei sind behoben und durch Tests
abgedeckt, die gegen den alten Code fehlschlagen.

### Engine — Release `v0.5.0`

Nach den Paketen geschnitten: Tag auf `484604d`, Release-Lauf grün, Release wie in P-14 festgelegt nur Quelltext.
Das Spiel ist mit demselben Lauf darauf gepinnt (unten).

### Spiel — Prototyp auf `v0.4.0`, umschaltbare Kamera

Spiel-PR #12 (`835117a`): Die Arena läuft wieder in der Hauptschleife der Engine, meldet ihre Figuren über den
Asset-Haken an, bekommt das Stats-Overlay auf F3, feuert neue Imp-Muster aus den Referenz-Patterns und hat einen
Vorhang-Modus auf `V` mit rund 10.300 Geschossen. Dazu drei umschaltbare Kamera-Vorgaben auf `C` — 60° / 14,5 m,
52° / 12,5 m und 45° / 11 m bei gleichbleibendem Blickwinkel von 42° —, damit der PO Figuren in Spielgröße
vergleichen kann: die Seele samt Trefferring ist bei 1080p 128, 184 und 248 Pixel hoch.

Zwei Dinge sind dabei gemessen statt vermutet worden. Erstens **die Blickrichtung:** Die Figuren der Runden 3 und 4
schauen entlang glTF −Z, die Darstellung nahm +Z an; im Spiel lief die Seele rückwärts und der Imp zeigte dem
Spieler den Rücken. Die Konvention bleibt +Z, die alten Packs sind als `MinusZ` markiert und werden im Modellraum
gedreht — die Simulation bleibt unberührt. Zweitens **die Kamera ist reine Darstellung:** Beide Goldhashes sind
unverändert, und ein Test spielt denselben Lauf unter allen drei Start-Vorgaben mit drei Wechseln mitten im Lauf
mit gleichen Hashes. Ein Nebenbefund bleibt offen: Die Taste liegt mangels Haken auf einem `InputMap`-Knopf und
steht damit in der aufgezeichneten Tick-Eingabe — die Engine hat den Haken inzwischen (§9.12), der Umzug folgt.

### Spiel — Asset-Compiler-Gate und Pin auf `v0.5.0`

Spiel-PR #18 (`dd84b80`) bringt beides zusammen, weil das Gate erst mit dem neuen Tag etwas auszuführen hat. Die CI
holt das öffentliche Engine-Repo an dem Tag, der in `Cargo.lock` steht, baut `sigilc` und `grimoire-ac` und
übersetzt `content/`: **2 Units, Pack 1011 Byte, Content-Hash `a9995a1d…`**, Gate-Job 43 s ohne Cache-Treffer.
Derselbe Content-Hash entsteht lokal mit denselben Werkzeugen aus dem Tag. Ein zweiter Job übersetzt ein bewusst
kaputtes Fixture und ist **nur dann grün, wenn der Compiler ablehnt** (Exit-Code 1, Diagnosen `SIG0006` und
`SIG0014`, kein Pack). Beim Pin blieben alle Goldens unverändert; die Bootstrap-Ausnahme für das Gate ist damit
verbraucht und gelöscht.

### Spiel — Content v0 (WP7.3)

Spiel-PR #20 (`f12f8bf`), gemergt noch in derselben Sitzung: fünf neue Patterns, je eines für eine Rolle aus dem
Gegner-Rollenraster, jedes aus einem Referenz-Pattern der Engine abgeleitet und jedes mit Bausteinen, die die
anderen nicht benutzen. Mit den beiden vorhandenen Imp-Mustern sind es **sieben Units**; damit sind alle sieben
Bausteine der Sprache im Content vertreten, ein `aimed`-Pattern und eine Kaskade darunter. Das Gate hat den Stand
gefahren: **7 Units, Pack 3400 Byte, Content-Hash `f2f073c8…`**, Exit-Code 0.

**Die Despawn-Falle aus WP6.6 ist hier gemessen worden, nicht vermutet:** Sigil v1 kennt kein Lebensdauer-Feld,
ein Geschoss verschwindet nur beim Verlassen der Box um die Arena — eine Drehrate, deren Kreis in der Box zugeht,
despawnt also nie und füllt auf einem endlosen Emitter den Pool. Deshalb hat nur ein Pattern überhaupt eine
Kurve (Wendekreis rund 52 Einheiten gegen eine Box von 13,5 × 10), und sein Emitter ist endlich; das einzige
endlose Pattern hat keinen drehenden Modifikator. Nachgewiesen über 900 Ticks je Pattern mit
`sigilc simulate --json`: vier Patterns enden bei **0** lebenden Geschossen, die endlosen schwingen sich ein,
**kein einziger verworfener Spawn**. Die Tabelle steht in `content/README.md`, der Aufruf daneben.

Die Arena spielt weiterhin nur die zwei Imp-Muster; welche Szene welches Pattern fährt, entscheidet WP7.4.

### Assets — Asset-Import-Pilot in vier Stufen

Fremd erzeugte Figuren in vier Stufen ins Spiel: prüfen (#11, `05d2db8`), vorbereiten (#13, `7a559f2`), packen
(#14, `80e005a`) und in der Engine ansehen (#17, `a4cd0de`); dazu der bis dahin fehlende Python-Testjob der
Asset-Werkzeuge (#15, `dcc3e3b`, 94 Tests, mit Negativnachweis). Einzelheiten und alle Messwerte stehen im
[Asset-Import-Piloten](0002-asset-import-pilot.md).

Kurz: Die Hexe kommt von 2.000.000 Dreiecken des Originals auf **11.996 Dreiecke und 12.236 Vertices** mit drei
Texturen zu 1024 und **16,0 MiB GPU-Speicher statt 682,7 MiB**, der Imp auf 5.000 Dreiecke bei 512. Der
Normalenfehler gegen das Original liegt im Median bei 28,8° ohne und **10,3° mit gebackener Normalenkarte**. Der
Weg ist reproduzierbar: Texturnutzlasten aus dem vorbereiteten 1024er-PNG und aus dem 8192er-JPEG des Downloads
sind bytegleich, und zwei Läufe in getrennten Prozessen ergeben dasselbe Manifest, solange Blender einfädig läuft.

In der Engine gemessen (Stufe 4, offscreen, Software-Adapter): Die Hexe ist an den drei Kamera-Vorgaben 132, 173
und 216 Pixel hoch, der Imp 92, 107 und 127 — die neuen Figuren spielen in der Größe der alten. Die Extraktion von
31 Figuren mit 811 Gelenkmatrizen kostet 0,011 ms im Mittel gegen ein Budget von 0,5 ms. Und die Lesbarkeit: Die
Hexe hebt sich mit 1,18–1,20 : 1 vom Arenaboden ab, **ihr hellstes Zehntel aber nur mit 1,02–1,05 : 1** — sie liest
sich als Silhouette, nicht als Gestalt. **Die Vorschau aus Stufe 2 hatte das Verhältnis vertauscht** und zeigte die
Hexe heller als ihren Boden; sie kennt weder Umgebungslicht noch Bodenfarbe der Arena. Übertragbar war aus ihr nur
die Aussage über Texturgrößen — die Stufe 4 bestätigt hat: 1024 bleibt richtig.

### Doku — Buchhaltung

Engine-PR #60 (`75ea6ad`) und #66 (`9fab671`) tragen die Vertragsänderungen aller M3-Pakete ins Änderungsprotokoll
§2b nach und vermerken die Freigaben des PO; #67 zieht die Abschnittstexte selbst nach, setzt Engine-ADR-0018 auf
angenommen und ergänzt die fünfte Gruppe des Plattform-Identitäts-Gates in der Formatdoku. Spiel-PR #16
(`a17df35`) und #19 (`cac8865`) schreiben die Arbeitspakete, die PO-Entscheide und den Piloten in Plan 0002 und in
das Piloten-Dokument; dieser Lauf hier zieht dazu das Beispiel in PRD-0018 von 600 auf 60 Ticks nach, weil die
Engine-ADR das so entschieden hat und die PRD im Spiel-Repo liegt.

Drei Abweichungen fielen dabei auf und sind festgehalten statt geglättet: Ein Paket meldete „Vertrag unverändert“
und hatte doch eine Formatdoku angefasst; eines zählte lokal 98 Tests, während die CI 101 meldet; und das
Identitäts-Gate übersetzte seit WP8.5 eine Gruppe, die in der Formatdoku fehlte.

### Aufräumen im Arbeitsstand

Nach den Merges ist der Arbeitsstand aufgeräumt worden — reine Hygiene, kein Inhalt hat sich geändert:

- Build-Ausgaben beider Repos und die verwaisten Ziele alter Worktrees entfernt, zusammen rund **46 GB**.
- **31 gemergte Zweige** lokal und auf GitHub gelöscht. Übrig bleiben `main`, der Datenzweig `bench-trends` und
  **drei bewusst behaltene Spike-Zweige** (`p1/wp1.4-sigil-syntax-spike`, `p1/wp2-look-dev-spike`,
  `p1/wp6.1-bench-spike`) samt ihren Messläufen.
- Blender-Versuchsdateien und die Einzelbild-Ordner der Animationsversuche gelöscht; die fertigen Rigs, die
  Vorschaubilder und die Berichte bleiben.
- Fünf ältere Schaufenster-Runden in einen Archivordner verschoben, mit einer README, die sagt, was dort liegt.
- **Zwei Ordner sind absichtlich geblieben,** weil eigene Skripte des PO auf sie zeigen; sie umzubenennen hätte die
  Skripte gebrochen.

## PO-Entscheide des Abends und der Nacht

Am Abend: **M3 ist gestartet**, der Asset-Import-Pilot läuft parallel dazu, und der Prototyp-Neubau bekommt die
umschaltbare Kamera. In der Nacht: **Engine-ADR-0017 angenommen** (Skelettanimation, alle neun Teilfragen wie
empfohlen), **Engine-ADR-0018 angenommen** (Subsystem-Hashes), **alle offenen Stufe-A-Punkte des Engine-Vertrags
freigegeben**, der Haken für reine Darstellungstasten und das Modul für die Clip-Abtastung freigegeben und der Tag
`v0.5.0` freigegeben. Die beiden ADRs tragen den Entscheid seitdem selbst, und das Beispiel in PRD-0018 steht
jetzt auf 60 statt 600 Ticks. Für den Piloten: Die Rollenbudgets bleiben **vorläufig**, Gegner kommen vor weiteren Importen
auf eine **Zielhöhe von 1,3 m**, und die Lesbarkeit der Hexe wird **über das Licht gelöst — ein Rim-Light —, nicht
über die Figur**.

Die Entscheide stehen mit ihren Folgen in den Abschnitten „Meilensteine“ und „Offene PO-Entscheidungen“ von
[Plan 0002](0002-phase-p1-sichtbarer-kern.md).

## Offen

- **Messsitzung 1 läuft und wartet auf die Zahlen des PO.** Bis sie vorliegen, sind alle Budgetaussagen dieses
  Laufs Runner-Werte und keine Referenz-Hardware. Zu messen sind dort unter anderem die GPU-Zeit eines Bildes mit
  30 gehäuteten Figuren und Multisampling gegen das 8-ms-Budget, mit und ohne Schattenwürfe, und ob das Hochladen
  der Gelenkmatrizen auffällt.
- Offen für M3 bleiben WP6.7 (Budget-Abgleich), WP7.4 und WP7.5 (Sim-Harness v1, Golden Master samt
  Nightly-Plattformvergleich). WP7.3 ist mit Spiel-PR #20 gemergt.
- Die Empfehlungen aus WP8.5, WP9.2 und WP9.3 sind noch nicht entschieden, darunter die beiden Gate-Checks als
  Pflicht-Checks des geschützten `main`.

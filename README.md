# Fiends n Patrons

2D-Topdown-Bullet-Hell-Roguelite im Dark-Fantasy-Setting mit 2.5D-Optik im realistischen 3D-Look: eine verdammte
Seele im Aufstieg, Melee-Kampf zwischen Bullet-Vorhängen und Pakte mit einem von fünf Patronen —
auf Kosten des Zorns der übrigen vier.

Das Spiel läuft auf der eigenen Engine **Grimoire** (eigenes Repo, gepinnte Release-Tags).

> Status: **erster spielbarer Prototyp**. Die Hexe läuft durch eine beleuchtete Arena, ein Imp
> feuert eines von sechs Sigil-Mustern, ein Treffer beendet die Runde, nach 1,5 s beginnt sie neu;
> ein Vorhang-Modus zeigt rund 10.000 Bullets. Das Spiel läuft in der Hauptschleife der Engine und pinnt Grimoire
> `v0.6.0` über einen Git-Tag ([ADR-0009](docs/adr/0009-engine-pin-ueber-git-tag.md)). Der
> Determinismus-Test friert die Endhashes der Arena und des Vorhangs für Seed 42 ein.

## Einstieg

- Produktanforderungen: [docs/prd/0000-index-fiends-n-patrons.md](docs/prd/0000-index-fiends-n-patrons.md) (bindendes Entscheidungsregister)
- Architekturentscheidungen: [docs/adr/](docs/adr/)
- Umsetzungspläne: [docs/plans/](docs/plans/)
- Arbeitsregeln, CI, Engine-Upgrade und Release: [CONTRIBUTING.md](CONTRIBUTING.md)

## Struktur

| Pfad | Inhalt |
|------|--------|
| `crates/fnp_app` | Ausführbares Spiel `fiends-n-patrons`: Kommandozeile, Laden des Figuren-Packs über den Asset-Haken der Engine, Darstellungs-Plugin der Arena |
| `crates/fnp_game` | Spielzustände und Run-Logik: Prototyp-Arena (`arena`) |
| `crates/fnp_content` | Gameplay-Plugins: Waffen, Patrone, Items, Gegner |
| `crates/fnp_sim_harness` | Headless-Bot-Läufe, Determinismus- und Balancing-Simulationen |
| `content/` | Quell-Content (Sigil-Patterns, Wellen, Texte, Audio-Rezepte) |
| `assets_src/` | Generatoren für Modelle (Blender-Skripte) |

## Bauen und starten

Die Engine [Grimoire](https://github.com/LupusMalusDeviant/grimoire) ist ein öffentliches
GitHub-Repo. Cargo holt sie ohne Zugangsdaten am gepinnten Tag, ein frischer Klon baut direkt:

```bash
cargo build --workspace --locked
cargo test --workspace --locked
cargo run --release -p fnp_app -- --pack <Pfad zu figures.pack> --seed 42
```

Das Spiel braucht ein Figuren-Pack mit einer Spieler- und einer Gegner-Figur (erzeugt von
`assets_src/figure_pack/`, nicht versioniert). Gesucht wird zuerst nach den Figuren `witch`
und `imp_hi3d`, sonst nach `soul` und `imp`; `FNP_PLAYER_FIGURE` und `FNP_ENEMY_FIGURE` wählen eine
andere. Wohin eine Figur schaut, sagt nicht ihr Name — die Packs benennen Figuren über
Generationen gleich —, sondern ihr eigenes Rig: Das Spiel misst es an den Zehen-, Fuß- oder
Hand-Gelenken der Ruhepose (`--figure-front auto`, Vorgabe) und schreibt das Ergebnis beim Start in
die Konsole. `--figure-front plusz|minusz` (oder `FNP_FIGURE_FRONT`) setzt es fest, falls ein Rig
einmal nichts hergibt. Das Spiel löst das auf, **bevor** ein Fenster aufgeht: Fehlt
das Pack oder hat es keine passende Figur, endet es mit einer Meldung, die sagt, welche Figuren das
Pack hat, und Exit-Code 2. Die Toolchain ist über `rust-toolchain.toml` gepinnt (1.98.1).
Im Spiel:

| Eingabe | Wirkung |
|---------|---------|
| `WASD` oder Pfeiltasten | Seele bewegen (mit leichtem Nachgleiten) |
| `P` | Muster des Gegners wechseln, reihum: `imp_volley`, `swarm_weave`, `shooter_rails`, `harrier_scatter`, `summoner_bloom`, `breaker_toll` (Wechsel löscht die Bullets des alten Musters) |
| `V` | Vorhang-Modus ein/aus: rund 10.000 Bullets, die Spielfigur ist dabei unverwundbar |
| `C` | Kamera-Voreinstellung wechseln: A (60°, 14,5 m, Vorgabe), B (52°, 12,5 m), C (45°, 11 m); Blickwinkel immer 42°, die aktive Voreinstellung steht im Fenstertitel. Reine Darstellungstaste: Sie läuft über `GamePlugin::presentation_input` (Vertrag §9.12) und steht in keiner Aufzeichnung |
| `F3` | Stats-Overlay der Engine ein/aus (Profiler-Scopes mit Budgetbalken) |
| `Escape` | Beenden |

Gamepads liest die Plattformschicht der Engine noch nicht; der linke Stick folgt, sobald sie es tut.

| Argument oder Umgebungsvariable | Wirkung |
|---------------------------------|---------|
| `--pack <Pfad>` oder `FNP_FIGURE_PACK=<Pfad>` | Figuren-Pack (Pflicht); das Argument gewinnt |
| `--seed <u64>` | Seed für Simulation, Raumkette, Bodenplatten und Pfützen (Standard 0); ungültige Werte beenden mit Fehlermeldung und Exit-Code 2 |
| `FNP_PLAYER_FIGURE=<Name>`, `FNP_ENEMY_FIGURE=<Name>` | Figur im Pack wählen; mit `:plusz` oder `:minusz` auch, wohin ihr Modell schaut |
| `--figure-front <auto\|plusz\|minusz>` oder `FNP_FIGURE_FRONT=<...>` | Blickrichtung der Pack-Figuren; Vorgabe `auto` (am Rig gemessen) |
| `FNP_ARENA_DISTRICT=crypt\|foundry\|ossuary` | Ersten Bodenbezirk für Art-Tests überschreiben; sonst bestimmt ihn der Seed |
| `FNP_ARENA_MODE=classic` | Ursprüngliche Muster-Demo mit einem Imp; Standard ist der Horden-Prototyp |
| `FNP_WORLD_PATCH_PREVIEW=0` | Ursprünglichen Raumboden zeigen; Standard ist ein 48 m Ausschnitt der 256 m Welt |
| `GRIMOIRE_EXAMPLE_MAX_FRAMES=<n>` | Lauf nach `n` Frames beenden |
| `GRIMOIRE_GPU_ADAPTER=software` | Software-Adapter der Plattform statt der Grafikkarte |
| `GRIMOIRE_WINDOW_MONITOR=secondary`, `GRIMOIRE_WINDOW_FOCUS=0` | Fenster auf dem Zweitmonitor und ohne Fokus öffnen (Konvention für Läufe auf dem Entwicklungsrechner) |

Das Spiel läuft über `App::run` der Engine: Das Plugin `ArenaStage` lädt die Figuren über den
Asset-Haken (`register_assets`, `load_figure_into`), `ArenaGame` ist die Simulation. Gespielt wird
standardmäßig mit dem Hordenmodus: drei verfolgende Imps zu Beginn, bis zu sieben mit zeitlichem
Nachschub und Kontaktgefahr. Der zentrale Imp schießt nur die gezielte Fünfer-Salve, ohne Ring
und Fächer. Pfützen liegen als Bildanteil auf jeweils einer 1-m-Bodenplatte, unter den Props.
Die 48-m-Bodentextur mischt angrenzende Untergründe über diagonal und sanft geschwungene
Grenzen; ihre Übergänge werden in Weltkoordinaten berechnet und treffen sich an Patchgrenzen.
`FNP_ARENA_MODE=classic` öffnet das Muster-Aufgebot (`ArenaGame::with_roster`,
`arena::playable_roster`): alle sechs Kampf-Muster aus `content/sigil/` auf `P`, dazu der Vorhang
auf `V`. Dieselbe Tabelle
(`fnp_game::arena::patterns::GamePattern`) nutzen die Szenen des Harness, damit gespielt und
gemessen dasselbe ist. Die Patterns nutzen nur Katalognamen, die der Bullet-Pass zeichnet.
`ArenaGame::new()` bleibt daneben die Arena des Imps allein — die Form, die die Goldmasters
`imp_arena` und `imp_curtain` festhalten. Bullets laufen über den Adapter
`grimoire::adapters::sigil_render` in den Bullet-Pass, der auch die Geschoss-Lichter ableitet.
Die Figuren tragen das Rim-Licht der Engine (`MeshRole::Actor`): Nur sie bekommen es, die Bühne
bleibt `Environment` und zeichnet unverändert. Bringt ein Pack Clips mit (`figures/<Figur>/clip/idle`
und `walk`), spielt das Spiel sie ab: Die Clip-Zeit ist `(Tick + alpha) / Tickrate`, die Überblendung
zwischen Stehen und Gehen eine reine Funktion der Geschwindigkeit — die Pose hängt damit nur von Welt
und `alpha` ab (Engine-ADR-0017), die Simulation zählt keine Animationszeit. Ohne Clips steht die
Figur in ihrer Ruhepose, wie bisher; der Imp tut das derzeit.

Die Kamera führt `ArenaStage` selbst (Voreinstellung, Folgefeder, Zug zum Imp), der Zielanker fürs
Mauszielen ist die Spielfigur. Die Kamera ist reine Darstellung: Die Taste `C` kommt über
`GamePlugin::presentation_input` (Vertrag §9.12) und nicht über die `InputMap`, taucht also in
keinem Tick und keiner Aufzeichnung auf. Ein Test spielt denselben Lauf unter allen drei
Voreinstellungen mit Wechseln mitten im Lauf und vergleicht den Zustands-Hash nach jedem Tick —
auch gegen denselben Lauf ganz ohne Kamera-Tasten ist jeder Hash gleich; ein zweiter prüft, dass
derselbe Bodenpunkt unter dem Mauszeiger unter jeder Voreinstellung dieselbe Zielrichtung ergibt.

Ohne Fenster läuft dieselbe Simulation über `fnp_sim_harness::run_arena(seed, ticks, input)`; der
Determinismus-Test liegt in `crates/fnp_sim_harness/tests/determinism.rs`. Eine Bildfolge eines
geskripteten Laufs rendert `crates/fnp_app/tests/offscreen_capture.rs` über `run_offscreen` der
Engine, ohne Fenster (Aufruf im Dateikopf; `FNP_CAPTURE_CAMERA=0|1|2` wählt die Voreinstellung).

## Lizenz

Copyright (c) 2026 Lupus Malus Deviant. Alle Rechte vorbehalten. Das Repo ist öffentlich einsehbar,
räumt aber keine Rechte zur Nutzung, Bearbeitung oder Weitergabe ein; das gilt für Code, Content und
Doku. Es gilt die Datei [LICENSE](LICENSE); die Entscheidung beschreibt
[ADR-0012](docs/adr/0012-lizenz-alle-rechte-vorbehalten.md). Die Engine Grimoire trägt im eigenen
Repo einen eigenen, gleichlautenden Vorbehalt.

# Fiends n Patrons

2D-Topdown-Bullet-Hell-Roguelite im Dark-Fantasy-Setting mit 2.5D-Optik im realistischen 3D-Look: eine verdammte
Seele im Aufstieg, Melee-Kampf zwischen Bullet-Vorhängen und Pakte mit einem von fünf Patronen —
auf Kosten des Zorns der übrigen vier.

Das Spiel läuft auf der eigenen Engine **Grimoire** (eigenes Repo, gepinnte Release-Tags).

> Status: **erster spielbarer Prototyp (Branch `proto/first-playable`)**. Die Seele läuft durch eine
> beleuchtete Arena, ein Imp feuert ein Sigil-Pattern, ein Treffer beendet die Runde, nach 1,5 s
> beginnt sie neu. Auf diesem Branch pinnt das Spiel einen Commit von Grimoire-`main` statt eines
> Tags (die Figuren-Packs brauchen Mesh-Fassung 2); vor einem Merge nach `main` braucht es einen
> Engine-Release-Tag ([ADR-0009](docs/adr/0009-engine-pin-ueber-git-tag.md)). Die P0-Demo
> „Beschwörungskreis“ bleibt als `FiendsGame` erhalten, ihr goldener Endhash (Seed 42, 3.600 Ticks)
> gilt unverändert.

## Einstieg

- Produktanforderungen: [docs/prd/0000-index-fiends-n-patrons.md](docs/prd/0000-index-fiends-n-patrons.md) (bindendes Entscheidungsregister)
- Architekturentscheidungen: [docs/adr/](docs/adr/)
- Umsetzungspläne: [docs/plans/](docs/plans/)
- Arbeitsregeln, CI, Engine-Upgrade und Release: [CONTRIBUTING.md](CONTRIBUTING.md)

## Struktur

| Pfad | Inhalt |
|------|--------|
| `crates/fnp_app` | Ausführbares Spiel `fiends-n-patrons`: Kommandozeile, Laden des Figuren-Packs, Hauptschleife |
| `crates/fnp_game` | Spielzustände und Run-Logik: Prototyp-Arena (`arena`), P0-Demo `FiendsGame` |
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

Das Spiel braucht ein Figuren-Pack mit den Figuren `soul` und `imp` (erzeugt von
`assets_src/figure_pack/`, nicht versioniert). Ohne `--pack` und ohne `FNP_FIGURE_PACK` endet es mit
einer Fehlermeldung und Exit-Code 2. Die Toolchain ist über `rust-toolchain.toml` gepinnt (1.98.1).
Im Spiel:

| Eingabe | Wirkung |
|---------|---------|
| `WASD` oder Pfeiltasten | Seele bewegen (mit leichtem Nachgleiten) |
| `Escape` | Beenden |

Gamepads liest die Plattformschicht der Engine noch nicht; der linke Stick folgt, sobald sie es tut.

| Argument oder Umgebungsvariable | Wirkung |
|---------------------------------|---------|
| `--pack <Pfad>` oder `FNP_FIGURE_PACK=<Pfad>` | Figuren-Pack (Pflicht); das Argument gewinnt |
| `--seed <u64>` | Seed der Simulation (Standard 0); ungültige Werte beenden mit Fehlermeldung und Exit-Code 2 |
| `GRIMOIRE_EXAMPLE_MAX_FRAMES=<n>` | Lauf nach `n` Frames beenden |
| `GRIMOIRE_GPU_ADAPTER=software` | Software-Adapter der Plattform statt der Grafikkarte |
| `GRIMOIRE_WINDOW_MONITOR=secondary`, `GRIMOIRE_WINDOW_FOCUS=0` | Fenster auf dem Zweitmonitor und ohne Fokus öffnen (Konvention für Läufe auf dem Entwicklungsrechner) |

Vorläufig im Prototyp: Bullets zeichnet das Spiel als leuchtende Meshes mit Blob-Schatten, bis der
Bullet-Pass der Engine (Plan 0002, WP3.5) gemergt ist (im Code `TEMPORARY(WP3.5)`); die
Figuren haben keine Animation, nur Ruhe- und Treffer-Pose.

Ohne Fenster läuft dieselbe Simulation über `fnp_sim_harness::run_arena(seed, ticks, input)`
(Prototyp) bzw. `fnp_sim_harness::run_seed(seed, ticks)` (P0-Demo); die Determinismus-Tests liegen in
`crates/fnp_sim_harness/tests/`. Eine Bildfolge eines geskripteten Laufs rendert
`crates/fnp_app/tests/offscreen_capture.rs` ohne Fenster (Aufruf im Dateikopf).

## Lizenz

Copyright (c) 2026 Lupus Malus Deviant. Alle Rechte vorbehalten. Das Repo ist öffentlich einsehbar,
räumt aber keine Rechte zur Nutzung, Bearbeitung oder Weitergabe ein; das gilt für Code, Content und
Doku. Es gilt die Datei [LICENSE](LICENSE); die Entscheidung beschreibt
[ADR-0012](docs/adr/0012-lizenz-alle-rechte-vorbehalten.md). Die Engine Grimoire trägt im eigenen
Repo einen eigenen, gleichlautenden Vorbehalt.

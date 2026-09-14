# Fiends n Patrons

2D-Topdown-Bullet-Hell-Roguelite im Dark-Fantasy-Setting mit 2.5D-Toon-Optik: eine verdammte
Seele im Aufstieg, Melee-Kampf zwischen Bullet-Vorhängen und Pakte mit einem von fünf Patronen —
auf Kosten des Zorns der übrigen vier.

Das Spiel läuft auf der eigenen Engine **Grimoire** (eigenes Repo, gepinnte Release-Tags).

> Status: **Phase P0 — Fundament**. Das Spiel pinnt Grimoire `v0.1.0` über einen Git-Tag
> ([ADR-0009](docs/adr/0009-engine-pin-ueber-git-tag.md)). Die P0-Demo „Beschwörungskreis“ belegt die
> Engine-Anbindung (Fenster, Eingabe, Fixed-Timestep-Simulation, interpolierte Sprites), noch kein
> Gameplay. Ein Determinismus-Test friert den Endhash für Seed 42 über 3.600 Ticks ein. Alle Rechte
> vorbehalten.

## Einstieg

- Produktanforderungen: [docs/prd/0000-index-fiends-n-patrons.md](docs/prd/0000-index-fiends-n-patrons.md) (bindendes Entscheidungsregister)
- Architekturentscheidungen: [docs/adr/](docs/adr/)
- Umsetzungspläne: [docs/plans/](docs/plans/)
- Arbeitsregeln, CI, Engine-Upgrade und Release: [CONTRIBUTING.md](CONTRIBUTING.md)

## Struktur

| Pfad | Inhalt |
|------|--------|
| `crates/fnp_app` | Ausführbares Spiel `fiends-n-patrons`: startet Grimoire mit dem Spiel-Plugin |
| `crates/fnp_game` | Spielzustände und Run-Logik; in P0 das Plugin `FiendsGame` (Demo „Beschwörungskreis“) |
| `crates/fnp_content` | Gameplay-Plugins: Waffen, Patrone, Items, Gegner |
| `crates/fnp_sim_harness` | Headless-Bot-Läufe, Determinismus- und Balancing-Simulationen |
| `content/` | Quell-Content (Sigil-Patterns, Wellen, Texte, Audio-Rezepte) |
| `assets_src/` | Generatoren für Modelle (Blender-Skripte) |

## Bauen und starten

Die Engine liegt in einem privaten GitHub-Repo. Cargo holt sie über die git-CLI
(`.cargo/config.toml` im Repo); die Zugangsdaten kommen einmalig von der GitHub CLI:

```bash
gh auth setup-git
cargo build --workspace --locked
cargo test --workspace --locked
cargo run --release -p fnp_app -- --seed 42
```

Die Toolchain ist über `rust-toolchain.toml` gepinnt (1.98.1). Im Spiel:

| Eingabe | Wirkung |
|---------|---------|
| `WASD` oder Pfeiltasten | Spieler bewegen (mit leichtem Nachgleiten) |
| `Leertaste` halten | Ritual kanalisieren: der Schwarm kreist schneller |
| `Escape` | Beenden |

| Argument oder Umgebungsvariable | Wirkung |
|---------------------------------|---------|
| `--seed <u64>` | Seed der Simulation (Standard 0); ungültige Werte beenden mit Fehlermeldung und Exit-Code 2 |
| `GRIMOIRE_EXAMPLE_MAX_FRAMES=<n>` | Lauf nach `n` Frames beenden |
| `GRIMOIRE_WINDOW_MONITOR=secondary`, `GRIMOIRE_WINDOW_FOCUS=0` | Fenster auf dem Zweitmonitor und ohne Fokus öffnen (Konvention für Läufe auf dem Entwicklungsrechner) |

Ohne Fenster läuft dieselbe Simulation über `fnp_sim_harness::run_seed(seed, ticks)`; die
Determinismus-Tests liegen in `crates/fnp_sim_harness/tests/determinism.rs`.

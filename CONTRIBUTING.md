# Mitwirken an Fiends n Patrons

Verbindliche Arbeitsregeln für Menschen und Coding-Agenten. Einstieg in Anforderungen und
Entscheidungen: [README](README.md), [docs/prd/](docs/prd/), [docs/adr/](docs/adr/). Das Spiel läuft
auf der Engine **Grimoire**, die als eigenes Repo mit gepinnten Tags eingebunden wird
([ADR-0002](docs/adr/0002-engine-eigenes-repo.md), [ADR-0009](docs/adr/0009-engine-pin-ueber-git-tag.md)).

## Grundsätze

- **Engine nur über Tags:** Das Spiel baut gegen einen getaggten Grimoire-Stand. Lokale Engine-Arbeit
  läuft über einen nicht versionierten `[patch]` (siehe unten); gemergt wird nur gegen Tags.
- **Gepinnte Werkzeuge:** Rust kommt aus `rust-toolchain.toml` (1.98.1 mit rustfmt und clippy,
  identisch zur Engine); `Cargo.lock` ist versioniert, CI baut mit `--locked`.
- **Keine Secrets im Repo.** Der Engine-Zugriff der CI läuft über ein GitHub-Secret, das
  Code-Signing-Zertifikat bleibt auf dem Entwicklungsrechner.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/de/v1.0.0/), Nachricht auf **Englisch**,
Imperativ, Betreff höchstens 72 Zeichen:

```text
<typ>(<scope>): <beschreibung>

<optionaler Rumpf: warum, nicht was>

<optionale Footer>
```

| Typ | Wofür | Abschnitt in den Release-Notes |
|-----|-------|--------------------------------|
| `feat` | neue Fähigkeit | Neue Funktionen |
| `fix` | Fehlerbehebung | Fehlerbehebungen |
| `build(engine)` | Grimoire-Tag heben | Engine-Upgrades |
| `perf` | Performance ohne Verhaltensänderung | Performance |
| `refactor` | Umbau ohne Verhaltensänderung | Umbauten |
| `docs` | Dokumentation, PRDs, ADRs | Dokumentation |
| `test` | Tests, Golden-Master | Tests |
| `build`, `ci` | Cargo, Abhängigkeiten, Workflows | Build und CI |
| `style` | reine Formatierung | Formatierung |
| `chore` | Wartung | Wartung |
| `revert` | Rücknahme | Zurückgenommen |

- **Scope** ist der Crate-Name ohne Präfix (`app`, `game`, `content`, `sim_harness`) oder ein
  Querschnittsthema (`engine`, `ci`, `release`, `deps`).
- **Inkompatible Änderungen** (etwa Save- oder Replay-Format) tragen ein `!` hinter Typ/Scope **und**
  einen Footer `BREAKING CHANGE: <was bricht, wie migrieren>`.
- `chore(release): vX.Y.Z` ist für Release-Commits reserviert und fehlt in den Release-Notes.
- **Agenten-Commits** enden mit einer Leerzeile und dem Trailer des tatsächlich arbeitenden Modells:

```text
feat(content): add radius grazer bot profile

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

## Lokale Pflichtprüfungen vor jedem Push

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo test --workspace --locked
cargo build --workspace --locked
```

Die Pflichtprüfungen laufen nur mit **auskommentiertem** `[patch]` in `<Arbeitsordner>\.cargo\config.toml`;
ein aktiver Patch lässt jeden `--locked`-Aufruf scheitern. Vor dem Commit zusätzlich prüfen, dass
`Cargo.lock` weder eine Pfad-Quelle für `grimoire` noch einen `[[patch.unused]]`-Eintrag enthält
(siehe „Lokale Engine-Entwicklung“).

## CI im Überblick

| Workflow | Auslöser | Inhalt |
|----------|----------|--------|
| `ci.yml` | Push auf `main`, Pull Request, manuell | `fmt`; `test` auf Windows/Linux/macOS mit clippy, Tests und Build |
| `nightly.yml` | täglich 02:47 UTC, manuell | Release-Build von `fiends-n-patrons` für drei Systeme als Artefakt (7 Tage), Kurz-Changelog im Job-Summary; geplante Läufe entfallen, wenn `main` 24 h nicht bewegt wurde (Push oder Merge laut Aktivitäts-API, nicht Commit-Datum) |
| `release.yml` | Tag `vX.Y.Z` | Versionsprüfung, Release-Builds für drei Systeme, **Entwurf** eines GitHub-Release mit git-cliff-Notes und Binaries |

- Commits, die nur Markdown oder `docs/` ändern, lösen `ci.yml` nicht aus. **Achtung Branch-Schutz:**
  Ein per Pfadfilter übersprungener Workflow meldet keinen Status; reine Doku-PRs bleiben bei
  Pflicht-Checks auf „Expected“ stehen und brauchen `gh workflow run ci.yml --ref <branch>` oder
  einen Admin-Merge.
- Ein neuer Push auf denselben Pull Request bricht dessen laufende CI ab. Läufe auf `main` werden
  **nie** abgebrochen; jeder `main`-Commit bekommt ein Ergebnis.
- Nightly-Binaries für Windows sind **unsigniert**; signiert werden nur Releases.
- **Kosten:** In privaten Repos zählen Linux-Minuten einfach, Windows doppelt, macOS zehnfach.

### Engine-Zugriff der CI

Alle Cargo-Jobs laufen über die lokale Action `.github/actions/engine-access`:

| Lage | Verhalten |
|------|-----------|
| Kein `Cargo.toml` referenziert `github.com/LupusMalusDeviant/grimoire` | Cargo-Schritte laufen normal. |
| Referenz vorhanden, Secret `GRIMOIRE_DEPLOY_KEY` gesetzt | Schlüssel wird per `webfactory/ssh-agent` geladen, `https://github.com/LupusMalusDeviant/` per `url.insteadOf` auf SSH umgelenkt, `CARGO_NET_GIT_FETCH_WITH_CLI=true`. |
| Referenz vorhanden, Secret fehlt | CI und Nightly: **Warnung** und übersprungene Cargo-Schritte (Job bleibt grün, hat aber nichts geprüft). Release: Abbruch. |

**Ein gelber Warnhinweis „Engine-Zugriff fehlt“ ist kein grüner Lauf.** Einmalige Einrichtung (lokal,
mit Admin-Rechten auf beiden Repos):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup-ci-deploy-key.ps1
```

Das Skript prüft `gh auth status`, `ssh-keygen` und beide Repos, erzeugt ein frisches ed25519-Paar
in einem temporären Ordner, hinterlegt den öffentlichen Teil als **Read-only-Deploy-Key** auf
`grimoire`, speichert den privaten Teil als Secret `GRIMOIRE_DEPLOY_KEY` in `fiends-n-patrons` und
löscht die Schlüsseldateien wieder. **Rotation:** dasselbe Skript mit `-ReplaceExisting`; es legt den
neuen Key an, setzt das Secret und entfernt erst danach die alten Keys gleichen Titels. Von `gh`
angelegte Deploy-Keys hängen am Token der GitHub CLI: Wird diese Autorisierung widerrufen, entfernt
GitHub den Key, und das Skript muss erneut laufen.

## CI-Überwachung (Pflicht)

**Ein Push ohne Nachsehen zählt nicht als fertig.** Jeder Push, der eine CI auslöst, wird überwacht,
bis der Lauf durch ist:

```bash
git push
run_id=$(gh run list --commit "$(git rev-parse HEAD)" --limit 1 --json databaseId --jq '.[0].databaseId')
gh run watch "$run_id" --exit-status
```

Ist der Lauf rot, wird **zuerst analysiert**, bevor irgendetwas anderes passiert:

```bash
gh run view "$run_id" --log-failed
```

Die Ursache wird benannt und zugeordnet: **Code**, **Vorrichtung** (Workflow, Cache, Deploy-Key,
Runner) oder **fremd** (Dienst gestört, Zeitfehler, Runner-Image). Auch eine fremde Ursache wird
festgehalten, zusammen mit der Antwort, ob der Test das künftig aushalten soll.

## Golden-Master und Referenzwerte

Golden-Master-Replays, Zustands-Hashes und später Render-Snapshots sind eingefrorene Erwartungen
(PRD-0018 FR-05). Erneuert wird **nur bewusst**:

1. **Ursache verstehen und benennen:** gewollte Gameplay-Änderung, Fehler oder Plattformeffekt? Nur
   der erste Fall rechtfertigt eine Erneuerung.
2. **Eigener Commit, direkt nach der verursachenden Änderung, im selben Push/PR:**
   `test(golden): renew <was> after <warum>`. Der Rumpf nennt *alt → neu* (bei Replays den ersten
   abweichenden Tick und das Subsystem) und die Begründung. Keine anderen Änderungen im selben Commit.
3. **Nie für eine einzelne Plattform** und **nie, um CI grün zu bekommen.** Agenten erneuern
   Golden-Master nicht eigenmächtig; die Entscheidung trifft der PO.
4. Ein Engine-Upgrade, das Golden-Master bricht, ist laut Engine-CHANGELOG eine inkompatible
   Engine-Änderung. Die Erneuerung gehört dann in den Upgrade-PR, mit Verweis auf den
   CHANGELOG-Eintrag.

## Engine-Anbindung

Die Engine steht als git-Dependency mit Tag im Workspace-Manifest (ab P0/WP6.3):

```toml
[workspace.dependencies]
grimoire = { git = "https://github.com/LupusMalusDeviant/grimoire", tag = "v0.1.0" }
```

`Cargo.lock` hält den Commit-Hash des Tags. Das Repo ist privat, also braucht auch Cargo lokal
Zugangsdaten. Am einfachsten lädt Cargo über die git-CLI, die dann die Anmeldung der GitHub CLI
nutzt:

```powershell
gh auth setup-git
```

und `git-fetch-with-cli` in der Cargo-Konfiguration (siehe nächster Abschnitt). **Auch mit aktivem
`[patch]`** muss Cargo das Original-Repo erreichen, solange es nicht im Cache liegt (am 2026-09-14 mit
Cargo 1.98.1 nachgeprüft: `--offline` scheitert dann).

## Lokale Engine-Entwicklung mit `[patch]`

Engine und Spiel liegen nebeneinander:

```text
<Arbeitsordner>\
├── .cargo\config.toml     ← nicht versioniert, gilt für alles unterhalb von <Arbeitsordner>\
├── grimoire\              ← Engine-Checkout
└── Prototype\             ← Spiel-Checkout
```

`<Arbeitsordner>\.cargo\config.toml`:

```toml
[net]
git-fetch-with-cli = true

# Nur während gemeinsamer Arbeit an Engine und Spiel einkommentieren (siehe Stolperfallen).
# [patch."https://github.com/LupusMalusDeviant/grimoire"]
# grimoire = { path = "grimoire/crates/grimoire" }
```

`[net]` darf dauerhaft aktiv bleiben. Der `[patch]`-Block ist ein **Schalter für die Iteration**:
einkommentieren, Engine und Spiel gemeinsam ändern, danach wieder auskommentieren.

Warum das so funktioniert (Cargo-Referenz, Kapitel „Configuration“ und „Overriding Dependencies“):

- **`[patch]` in Konfigurationsdateien ist stabil.** Das Format ist dasselbe wie im `Cargo.toml`; ein
  Patch in der Konfiguration hat Vorrang vor einem Patch im Manifest.
- **Fundort:** Cargo sucht `.cargo/config.toml` im aktuellen Verzeichnis und in allen
  Elternverzeichnissen. Ein Aufruf in `<Arbeitsordner>\Prototype\` findet also `<Arbeitsordner>\.cargo\config.toml`.
- **Relative Pfade** beziehen sich auf das Verzeichnis, **das den `.cargo`-Ordner enthält**, hier
  `<Arbeitsordner>\`. Richtig ist daher `grimoire/crates/grimoire`. Ein
  `../grimoire/crates/grimoire` zeigte auf `<Arbeitsordner>\..\grimoire` und scheitert (in einem
  Wegwerf-Workspace nachgeprüft).
- Patchen muss man nur Crates, die das Spiel **direkt** aus dem Git-Repo bezieht. Deren
  Pfad-Abhängigkeiten innerhalb der Engine (`grimoire_core` usw.) folgen automatisch dem lokalen
  Checkout. Zieht das Spiel später weitere Engine-Crates direkt, bekommt jedes eine eigene Zeile.

Prüfen, ob der Patch greift: `cargo tree -i grimoire` zeigt dann den lokalen Pfad statt der Git-URL.

Stolperfallen:

- **Ein aktiver Patch bricht `--locked` überall unter `<Arbeitsordner>\`.** Er gilt für jeden Cargo-Aufruf
  unterhalb von `<Arbeitsordner>\`, also auch im Engine-Repo, in allen Worktrees unter `<Arbeitsordner>\_wt\` und im
  Spiel, solange es die Engine noch nicht referenziert. Wo er ungenutzt ist, trägt Cargo ihn als
  `[[patch.unused]]` in `Cargo.lock` ein. Mit `--locked` endet jeder Aufruf mit „cannot update the
  lock file … because --locked was passed“, ohne `--locked` verändert sich das versionierte
  Lockfile (am 2026-09-14 mit Cargo 1.98.1 in einem Wegwerf-Workspace nachgeprüft).
- **Auch im Spiel scheitern die Pflichtprüfungen**, solange der Patch greift: Er ersetzt die Quelle
  von `grimoire` im Lockfile. Während der Iteration daher ohne `--locked` bauen und testen; die
  Pflichtprüfungen laufen erst nach dem Auskommentieren.
- **`Cargo.lock` mit aktivem Patch nie committen**, weder im Spiel (Pfad-Quelle) noch in der Engine
  (`[[patch.unused]]`); die CI bricht dank `--locked` ab. Vor dem Commit Patch auskommentieren und die
  Lockfile-Änderung mit `git restore Cargo.lock` verwerfen (im Spiel alternativ
  `cargo update -p grimoire`).
- Braucht das Spiel eine Engine-Änderung, gilt: Engine-PR mergen, Engine-Release taggen, dann im Spiel
  den Tag heben. Ein Spiel-Commit, der nur mit lokalem Patch baut, ist nicht fertig.

## Engine-Upgrade

1. Engine-CHANGELOG der Zielversion lesen, besonders Einträge **[inkompatibel]**.
2. Tag in `Cargo.toml` heben: `tag = "vX.Y.Z"`.
3. Lockfile nachziehen (ohne aktiven Patch):
   ```bash
   cargo update -p grimoire
   ```
4. Lokale Pflichtprüfungen; bei gebrochenen Golden-Mastern gilt die Golden-Master-Regel.
5. Commit `build(engine): bump grimoire to vX.Y.Z` mit `Cargo.toml` und `Cargo.lock`, pushen und den
   CI-Lauf überwachen.

## Release

Voraussetzung: Der letzte CI-Lauf auf `main` ist grün und der Engine-Pin zeigt auf einen Tag.

1. **Version heben** in `Cargo.toml` unter `[workspace.package]`, danach `cargo check --workspace`,
   damit `Cargo.lock` passt.
2. **Commit und Push:** `chore(release): vX.Y.Z`, CI-Lauf überwachen.
3. **Tag setzen und pushen:**
   ```bash
   git tag -a vX.Y.Z -m "Fiends n Patrons vX.Y.Z"
   git push origin vX.Y.Z
   ```
4. **Release-Lauf überwachen.** Er erstellt einen **Entwurf** mit den Binaries für drei Systeme:
   ```bash
   run_id=$(gh run list --workflow release.yml --limit 1 --json databaseId --jq '.[0].databaseId')
   gh run watch "$run_id" --exit-status
   ```
5. **Windows-Exe lokal signieren und ersetzen.** Die `.pfx` geht nie in die CI; signiert wird mit dem
   vorhandenen Zertifikat `CN=Lupus Malus Deviant` über das Signier-Skript des PO (im Befehl unten `<Signier-Skript>`):
   ```powershell
   $tag  = 'vX.Y.Z'
   $repo = 'LupusMalusDeviant/fiends-n-patrons'
   $dir  = Join-Path $env:TEMP "fnp-release-$tag"
   gh release download $tag --repo $repo --pattern '*-windows-x86_64.exe' --dir $dir
   $exe  = (Get-ChildItem $dir -Filter '*.exe' | Select-Object -First 1).FullName
   powershell -NoProfile -ExecutionPolicy Bypass -File "<Signier-Skript>" -Exe $exe
   Get-AuthenticodeSignature $exe | Format-List Status, SignerCertificate
   gh release upload $tag $exe --repo $repo --clobber
   ```
   Das Signier-Skript versucht einen Zeitstempel und signiert notfalls ohne. Die Ausgabe wird gelesen, bevor
   hochgeladen wird.
6. **Entwurf prüfen und veröffentlichen:**
   ```powershell
   gh release view $tag --repo $repo
   gh release edit $tag --repo $repo --draft=false
   ```

Scheitert die Versionsprüfung, wurde falsch getaggt: Tag lokal und remote löschen
(`git tag -d vX.Y.Z`, `git push origin :refs/tags/vX.Y.Z`), korrigieren, neu taggen. Das ist nur
erlaubt, solange kein veröffentlichtes Release zu dem Tag existiert.

## SemVer-Politik

- **Vor 1.0 (`0.MINOR.PATCH`):** Eine inkompatible Änderung hebt **MINOR** und braucht einen
  Eintrag in den Release-Notes (Commit mit `!` und `BREAKING CHANGE:`). Alles andere hebt **PATCH**.
- **Ab 1.0:** reguläres SemVer.
- **Als inkompatibel gilt:** alte Spielstände, Profile oder Replays sind nicht mehr ladbar
  (PRD-0015), Mod- oder Content-Formate ändern sich inkompatibel, Mindestanforderungen an Plattformen
  steigen.

## Versionen der GitHub Actions

Actions sind gepinnt: `actions/checkout@v7`, `actions/upload-artifact@v7`,
`actions/download-artifact@v8`, `Swatinem/rust-cache@v2`, `orhun/git-cliff-action@v4`,
`webfactory/ssh-agent@v0.10.0`. Diese Action veröffentlicht keine Major-Tags, deshalb ist die
Version exakt gepinnt. Aktuelle Stände prüfen mit
`gh api repos/<owner>/<repo>/releases/latest --jq .tag_name`. Ein Wechsel ist ein eigener
`ci:`-Commit, nachdem die Release-Notes gelesen wurden.

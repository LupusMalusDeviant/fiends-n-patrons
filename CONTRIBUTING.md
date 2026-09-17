# Mitwirken an Fiends n Patrons

Verbindliche Arbeitsregeln für Menschen und Coding-Agenten. Einstieg in Anforderungen und
Entscheidungen: [README](README.md), [docs/prd/](docs/prd/), [docs/adr/](docs/adr/). Das Spiel läuft
auf der Engine **Grimoire**, die als eigenes Repo mit gepinnten Tags eingebunden wird
([ADR-0002](docs/adr/0002-engine-eigenes-repo.md), [ADR-0009](docs/adr/0009-engine-pin-ueber-git-tag.md)).

## Beiträge von außen

Pull Requests von außen werden **derzeit nicht angenommen**. Das Repo steht unter „Alle Rechte
vorbehalten“ ([LICENSE](LICENSE), [ADR-0012](docs/adr/0012-lizenz-alle-rechte-vorbehalten.md)); ohne
eine Beitragsvereinbarung können an einem Beitrag keine Rechte eingeräumt werden. **Issues bleiben
offen:** Hinweise und Fehlerberichte sind willkommen.

## Grundsätze

- **Engine nur über Tags:** Das Spiel baut gegen einen getaggten Grimoire-Stand. Lokale Engine-Arbeit
  läuft über einen nicht versionierten `[patch]` (siehe unten); gemergt wird nur gegen Tags.
- **Gepinnte Werkzeuge:** Rust kommt aus `rust-toolchain.toml` (1.98.1 mit rustfmt und clippy,
  identisch zur Engine); `Cargo.lock` ist versioniert, CI baut mit `--locked`.
- **Keine Secrets im Repo.** Die Engine ist öffentlich; CI und lokale Builds holen sie ohne
  Zugangsdaten ([ADR-0013](docs/adr/0013-oeffentliche-repos-anonymer-engine-abruf.md)). Das
  Code-Signing-Zertifikat bleibt auf dem Entwicklungsrechner.
- **`main` ist geschützt:** Ein Ruleset verhindert Force-Push und Löschen von `main`. Direkte Pushes
  bleiben erlaubt; Pflicht-Checks gibt es nicht, deshalb gelten die lokalen Pflichtprüfungen vor jedem
  Push und die CI-Überwachung weiter.

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
cargo test --workspace --locked --no-fail-fast
cargo build --workspace --locked
```

Wer etwas unter `assets_src/` ändert, führt zusätzlich die Python-Tests der Werkzeuge aus (numpy
und Pillow nach `assets_src/textures/requirements.txt`; kein Blender, keine Grafikkarte nötig):

```bash
python -B -m unittest discover -s assets_src/figure_pack -t assets_src/figure_pack
python -B -m unittest discover -s assets_src/asset_import -t assets_src/asset_import
```

Wer etwas unter `content/` ändert, übersetzt den Content zusätzlich mit dem Asset-Compiler der
Engine (siehe „Asset-Gate" unten); die CI tut dasselbe bei jedem Push, und jede Diagnose bricht den
Lauf.

Die Pflichtprüfungen laufen nur mit **auskommentiertem** `[patch]` in `<Arbeitsordner>\.cargo\config.toml`;
ein aktiver Patch lässt jeden `--locked`-Aufruf scheitern. Vor dem Commit zusätzlich prüfen, dass
`Cargo.lock` weder eine Pfad-Quelle für `grimoire` noch einen `[[patch.unused]]`-Eintrag enthält
(siehe „Lokale Engine-Entwicklung“).

## CI im Überblick

| Workflow | Auslöser | Inhalt |
|----------|----------|--------|
| `ci.yml` | Push auf `main`, Pull Request, manuell | `fmt`; `assets` (Linux, Python-Tests von `assets_src/figure_pack` und `assets_src/asset_import`); `content` (Linux, Asset-Gate über `content/` und der Negativnachweis, je ein eigener Job); `test` auf Windows/Linux/macOS mit clippy, Tests (`--no-fail-fast`) und Build; unter Linux zusätzlich der Abgleich der `clippy.toml`-Kopien mit dem gepinnten Engine-Tag |
| `nightly.yml` | täglich 02:47 UTC, manuell | Asset-Gate auf Windows/Linux/macOS (beide Fälle), Determinismus-Test im Release-Profil, dann Release-Build von `fiends-n-patrons` für drei Systeme als Artefakt (7 Tage), Kurz-Changelog im Job-Summary; geplante Läufe entfallen, wenn `main` 24 h nicht bewegt wurde (Push oder Merge laut Aktivitäts-API, nicht Commit-Datum) |
| `release.yml` | Tag `vX.Y.Z` | Versionsprüfung, Determinismus-Test im Release-Profil und Release-Builds für drei Systeme, **Entwurf** eines GitHub-Release mit git-cliff-Notes und Binaries |

- Der Job `assets` läuft bei jedem Auslöser des Workflows, nicht nur bei Änderungen unter
  `assets_src/`: GitHub Actions kennt keinen Pfadfilter je Job, und ein Filter am Workflow würde für
  jede andere Änderung gar keinen Status melden (siehe „Achtung Branch-Schutz“ gleich darunter). Der
  Job dauert unter einer Minute. Die Blender-Stufe (`blender_prepare.py`) prüft er nicht; die deckt
  der Pilotlauf ab.
- Commits, die nur Markdown oder `docs/` ändern, lösen `ci.yml` nicht aus. **Achtung Branch-Schutz:**
  Ein per Pfadfilter übersprungener Workflow meldet keinen Status; reine Doku-PRs bleiben bei
  Pflicht-Checks auf „Expected“ stehen und brauchen `gh workflow run ci.yml --ref <branch>` oder
  einen Admin-Merge.
- **Erster Push eines neuen Branches:** Beobachtet am 2026-09-14 beim ersten Push von `main` in das
  leere Repository. Für den Pfadfilter zählte offenbar nur der letzte Commit des Pushes. War das ein
  reiner Doku-Commit (hier ein Doku-Merge), startete `ci.yml` nicht, obwohl der Push auch Code
  enthielt. Nach so einem Push mit `gh run list --commit "$(git rev-parse HEAD)"` prüfen und bei
  fehlendem Lauf `gh workflow run ci.yml --ref <branch>` auslösen.
- Ein neuer Push auf denselben Pull Request bricht dessen laufende CI ab. Läufe auf `main` werden
  **nie** abgebrochen; jeder `main`-Commit bekommt ein Ergebnis.
- Nightly-Binaries für Windows sind **unsigniert**; signiert werden nur Releases.
- **Kosten:** Das Repo ist öffentlich; die gehosteten Standard-Runner (Linux, Windows, macOS)
  verbrauchen keine Actions-Minuten. Größere Runner sind kostenpflichtig und werden nicht genutzt.
  Maßstab bleibt die Laufzeit: Standard-Push unter 15 Minuten pro Plattform (PRD-0017).
- **Pull Requests von außen** werden derzeit nicht angenommen (siehe „Beiträge von außen“). Ihre
  Workflows laufen trotzdem erst, nachdem ein Maintainer sie freigegeben hat (Repository-Einstellung),
  damit fremde Pull Requests keine Runner-Zeit binden.

### Engine-Zugriff der CI

Die Engine [`LupusMalusDeviant/grimoire`](https://github.com/LupusMalusDeviant/grimoire) ist ein
öffentliches Repo. Alle Cargo-Jobs holen sie **anonym über HTTPS**, genau unter der URL aus
`Cargo.toml` und am Commit aus `Cargo.lock`
([ADR-0013](docs/adr/0013-oeffentliche-repos-anonymer-engine-abruf.md), Pin weiter nach
[ADR-0009](docs/adr/0009-engine-pin-ueber-git-tag.md)). Es gibt **kein Secret, keinen Deploy-Key und
keine eigene Action** dafür.

- **Jeder Lauf baut und testet**, auch Pull Requests aus Forks und von Dependabot. Einen
  übersprungenen Cargo-Teil gibt es nicht mehr; ein grüner Lauf hat immer clippy, Tests und Build
  hinter sich.
- Jeder Cargo-Job hat einen eigenen Schritt **„Fetch dependencies (engine anonymously over HTTPS)“**
  (`cargo fetch --locked`). Scheitert genau dieser Schritt, liegt die Ursache fast nie am Code:
  - **Vorrichtung:** Die Engine ist nicht öffentlich erreichbar (Sichtbarkeit geändert, Repo
    umbenannt) oder der gepinnte Tag fehlt.
  - **Fremd:** GitHub ist gestört.
  - Die Workflows setzen `GIT_TERMINAL_PROMPT=0` und `GCM_INTERACTIVE=never`, damit so ein Fall
    sofort mit einer Fehlermeldung endet, statt auf eine Anmeldung zu warten.
- Prüfen, ohne eigene Zugangsdaten zu verwenden (sonst täuscht ein Credential-Helper Erfolg vor):

  ```bash
  git -c credential.helper= ls-remote https://github.com/LupusMalusDeviant/grimoire 'refs/tags/v*'
  ```

  Das dereferenzierte Tag (`refs/tags/vX.Y.Z^{}`) muss den Commit aus `Cargo.lock` nennen.
- **Nie** einen Token, Deploy-Key oder ein Secret zurückbringen, um einen roten Abruf grün zu
  bekommen. Soll die Engine wieder privat werden, braucht es ein neues ADR.
- Engine-Tags werden nie verschoben oder gelöscht (ADR-0009). Seit das Repo öffentlich ist, bräche
  ein fehlender Tag auch alle fremden Klone.

### Asset-Gate (Content)

Der Content des Spiels wird in der CI mit dem **Compiler der Engine am gepinnten Tag** übersetzt
(Plan 0002 WP9.3, [ADR-0010](docs/adr/0010-sigil-compiler-hoheit.md)): Der Job holt die Engine in
`engine/`, baut `sigilc` und den Asset-Compiler `grimoire-ac` und ruft ihn auf. **Jede Diagnose
bricht den Lauf**; ein Pack wird nur geschrieben, wenn es vollständig zu seinen Quellen passt.
`packs/` ist reines Build-Artefakt (7 Tage Aufbewahrung) und steht in `.gitignore`.

- **Zwei Jobs, zwei Fälle.** `asset compiler (content/)` übersetzt `content/`.
  `asset compiler (negative proof)` übersetzt `tests/fixtures/sigil-broken/` und ist **nur grün,
  wenn der Compiler ablehnt** und die in `expected-codes.txt` genannten Diagnosen meldet. Ohne
  diesen zweiten Job wäre das Gate auch dann grün, wenn gar kein Compiler liefe.
- **Pin.** Tag und Commit kommen aus `Cargo.lock` (`.github/scripts/engine-pin.sh`), nie aus dem
  Workflow: Ein `cargo update -p grimoire` bewegt das Gate mit dem Rest des Builds. Ein eigener
  Schritt prüft, dass der Tag genau auf den Commit aus `Cargo.lock` zeigt (Tags werden nie
  verschoben, [ADR-0009](docs/adr/0009-engine-pin-ueber-git-tag.md)).
- **Zugriff.** Der zweite `actions/checkout` holt das öffentliche Engine-Repo
  ([ADR-0013](docs/adr/0013-oeffentliche-repos-anonymer-engine-abruf.md)) — **kein Secret, kein
  Deploy-Key**, nur das automatische, lesende Workflow-Token, das nicht gespeichert wird
  (`persist-credentials: false`). Scheitert dieser Schritt, ist fast nie der Code schuld: Die Engine
  ist nicht öffentlich erreichbar oder der gepinnte Tag fehlt.
- **Cache.** Schlüssel ist der Engine-Tag plus der Hash von `Cargo.lock` und
  `engine/tools/global.json` — also genau die Angaben, die entscheiden, was gebaut wird. Der
  NuGet-Cache hängt an den Lock-Dateien der Werkzeug-Suite.
- **Voraussetzung am Pin.** Der gepinnte Engine-Tag muss den Asset-Compiler mitbringen; seit
  `v0.5.0` tut das jeder. Ein Pin auf einen älteren Tag ist ein Fehler mit klarer Meldung
  (`.github/scripts/asset-tools-ready.sh`), kein stillschweigend übersprungener Job.
- **Laufzeit (R13).** Erster scharfer Lauf am Tag `v0.5.0` mit leerem Cache: 41 s für den ganzen
  Job (Toolchain 7 s, `sigilc` 9 s, SDK 4 s, `grimoire-ac` 13 s), davon 53 ms fürs Übersetzen
  selbst. Richtwert bleibt R13: Standard-Push unter 15 Minuten pro Plattform. Die Zeit des
  Übersetzens steht als `grimoire-ac timings:` in jedem Job-Protokoll.

Lokal dasselbe (die Werkzeuge einmal aus dem gepinnten Tag bauen, danach nur noch das letzte
Kommando):

```bash
tag=$(bash .github/scripts/engine-pin.sh | sed -n 's/^tag=//p')
git -c credential.helper= clone --depth 1 --branch "$tag" https://github.com/LupusMalusDeviant/grimoire engine
cargo build --release -p grimoire_sigilc --bin sigilc --locked --manifest-path engine/Cargo.toml
dotnet build engine/tools/src/Grimoire.AssetCompiler/Grimoire.AssetCompiler.csproj -c Release

export GRIMOIRE_SIGILC="$PWD/engine/target/release/sigilc"
export GRIMOIRE_AC="$PWD/engine/tools/src/Grimoire.AssetCompiler/bin/Release/net10.0/grimoire-ac"
bash .github/scripts/asset-gate.sh content packs pass
bash .github/scripts/asset-gate.sh tests/fixtures/sigil-broken packs/negative fail tests/fixtures/sigil-broken/expected-codes.txt
```

`engine/` gehört nicht ins Repo; wer es dauerhaft braucht, legt es außerhalb ab und zeigt mit den
beiden Variablen darauf. Der Compiler selbst bleibt Sache der Engine: `grimoire-ac` entdeckt,
normalisiert, ruft auf und packt, kennt aber keine Sigil-Grammatik (ADR-0010).

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

Die Ursache wird benannt und zugeordnet: **Code**, **Vorrichtung** (Workflow, Cache, Engine-Abruf,
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

Die Engine steht als git-Dependency mit Tag im Workspace-Manifest (seit P0/WP6.3):

```toml
[workspace.dependencies]
grimoire = { git = "https://github.com/LupusMalusDeviant/grimoire", tag = "v0.1.1" }
```

`Cargo.lock` hält den Commit-Hash des Tags (Quelle
`git+https://github.com/LupusMalusDeviant/grimoire?tag=v0.1.1#<commit>`) für jedes bezogene
Engine-Crate. Das Engine-Repo ist öffentlich; Cargo holt es ohne Zugangsdaten, ein frischer Klon
baut ohne Einrichtungsschritt.

Die versionierte `.cargo/config.toml` des Spiel-Repos setzt `[net] git-fetch-with-cli = true`, damit
Cargo lokal wie in der CI über die git-CLI lädt. Zwingend ist das nicht; der eingebaute Git-Client
von Cargo holt ein öffentliches Repo genauso. In diese Datei gehört **nie** ein `[patch]`. **Auch mit
aktivem `[patch]`** muss Cargo das Original-Repo erreichen, solange es nicht im Cache liegt (am
2026-09-14 mit Cargo 1.98.1 nachgeprüft: `--offline` scheitert dann).

Prüfen, dass der Pin greift:

```bash
cargo tree -i grimoire --locked   # genau ein grimoire, Quelle ...grimoire?tag=v0.1.1#<commit>
```

## Lokale Engine-Entwicklung mit `[patch]`

Engine und Spiel liegen nebeneinander:

```text
<Arbeitsordner>\
├── .cargo\config.toml     ← nicht versioniert, nur während der Iteration anlegen
├── grimoire\              ← Engine-Checkout
└── Prototype\             ← Spiel-Checkout
```

`<Arbeitsordner>\.cargo\config.toml`:

```toml
# Nur während gemeinsamer Arbeit an Engine und Spiel einkommentieren (siehe Stolperfallen).
# [patch."https://github.com/LupusMalusDeviant/grimoire"]
# grimoire = { path = "grimoire/crates/grimoire" }
```

`[net] git-fetch-with-cli` steht bereits in der versionierten `.cargo/config.toml` des Spiels und
gehört nicht in diese Datei. Der `[patch]`-Block ist ein **Schalter für die Iteration**:
einkommentieren, Engine und Spiel gemeinsam ändern, danach wieder auskommentieren. Wer ihn gerade
nicht braucht, legt die Datei am besten gar nicht an.

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
  unterhalb von `<Arbeitsordner>\`, also auch im Engine-Repo und in allen Worktrees unter `<Arbeitsordner>\_wt\`. Wo er
  ungenutzt ist (Engine-Repo, Engine-Worktrees), trägt Cargo ihn als `[[patch.unused]]` in
  `Cargo.lock` ein. Mit `--locked` endet jeder Aufruf mit „cannot update the
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
   Cargo liest das `Cargo.lock` der Engine bei Git-Dependencies nicht. Das Spiel-Lockfile wurde beim
   ersten Pin aus dem Lockfile des Engine-Tags vorbelegt, damit die Drittanbieter-Versionen (wgpu,
   winit usw.) denen der Engine-CI entsprechen. Beim Upgrade die Versionen gegen
   `git show vX.Y.Z:Cargo.lock` im Engine-Repo vergleichen und Abweichungen mit
   `cargo update -p <crate> --precise <version>` angleichen.
4. Der Zieltag muss den Asset-Compiler mitbringen (Engine ab `v0.5.0`), sonst bleibt das Asset-Gate
   rot; die Meldung nennt den Grund.
5. Determinismus-Lints abgleichen (siehe „Determinismus-Lints“): Die `clippy.toml` der Fassade im
   Ziel-Tag muss mit jeder Kopie im Spiel übereinstimmen.
   ```bash
   git -C ../grimoire show vX.Y.Z:crates/grimoire/clippy.toml > /tmp/facade-clippy.toml
   for copy in crates/*/clippy.toml; do diff -u /tmp/facade-clippy.toml "$copy"; done
   ```
   Bei Abweichung die Datei aus dem Tag in jede Kopie übernehmen; sie gehört in den Upgrade-Commit.
   Neue Einträge können bestehenden Spiel-Code rot machen, das ist gewollt.
6. Lokale Pflichtprüfungen; bei gebrochenen Golden-Mastern gilt die Golden-Master-Regel.
7. Commit `build(engine): bump grimoire to vX.Y.Z` mit `Cargo.toml`, `Cargo.lock` und gegebenenfalls
   den `clippy.toml`-Kopien, pushen und den CI-Lauf überwachen.

## Determinismus-Lints

Der Engine-Vertrag (`grimoire/docs/architektur/crate-vertraege.md`, Abschnitt 3) verbietet
Simulationscode Wanduhrzeit, ungeordnete Hash-Container, Threads und die Plattform-libm. Durchgesetzt
wird das über `disallowed-types` und `disallowed-methods` in `clippy.toml`. Clippy liest diese Datei
nur aus dem Verzeichnis des jeweiligen Crates, deshalb trägt **jedes Spiel-Crate mit
Simulationscode** eine byte-identische Kopie von `crates/grimoire/clippy.toml` aus dem gepinnten
Engine-Tag: heute `fnp_game` und `fnp_sim_harness`, später etwa `fnp_content`, sobald es Systeme
oder Spawn-Logik enthält. Die Kopien werden nie von Hand geändert. Neue Verbote kommen über die
Engine und ein Engine-Upgrade. Die CI (`ci.yml`, Linux) vergleicht jede Kopie mit der Datei im
gepinnten Tag und bricht bei Abweichung ab.

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

Actions sind gepinnt: `actions/checkout@v7`, `actions/setup-python@v7`,
`actions/setup-dotnet@v6`, `actions/cache@v6`, `actions/upload-artifact@v7`,
`actions/download-artifact@v8`, `Swatinem/rust-cache@v2` (auf den
Commit, nicht nur das Tag), `orhun/git-cliff-action@v4`. Aktuelle
Stände prüfen mit `gh api repos/<owner>/<repo>/releases/latest --jq .tag_name`. Ein Wechsel ist ein
eigener `ci:`-Commit, nachdem die Release-Notes gelesen wurden.

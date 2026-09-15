# ADR-0009: Engine-Pin über Cargo-git-Dependency mit Tag (Deploy-Key in CI, lokaler `[patch]`)

- **Status:** Akzeptiert, umgesetzt (Spiel pinnt Grimoire `v0.1.0`, siehe „Umsetzung“); Teil 2 „CI-Zugriff über einen Read-only-Deploy-Key“ ist seit 2026-09-15 veraltet, Teil 1 (Pin) und Teil 3 (lokaler `[patch]`) gelten weiter
- **Teilweise ersetzt durch:** [ADR-0013](0013-oeffentliche-repos-anonymer-engine-abruf.md) (öffentliche Repos, anonymer Engine-Abruf, kein Deploy-Key)
- **Datum:** 2026-09-14
- **Entscheider:** Lupus Malus Deviant (PO), vorbereitet durch Claude
- **Bezug:** [ADR-0002](0002-engine-eigenes-repo.md), [PRD-0017](../prd/0017-plattform-ci-distribution.md) (OF-17.1, FR-04), [Plan-0001](../plans/0001-phase-p0-fundament.md) (WP6.3)

## Kontext

ADR-0002 trennt Engine und Spiel in zwei Repos und legt fest, dass das Spiel getaggte
Engine-Versionen pinnt. Offen blieb die Mechanik (OF-17.1). Beide Repos liegen privat unter
`LupusMalusDeviant` auf GitHub (`grimoire`, `fiends-n-patrons`). Der `GITHUB_TOKEN` einer
Actions-Ausführung sieht nur das eigene Repo, also braucht die Spiel-CI einen eigenen Weg zur
privaten Engine. Lokal liegen beide Checkouts nebeneinander unter `<Arbeitsordner>\`,
und Engine-Änderungen sollen sich im Spiel ausprobieren lassen, ohne vorher zu taggen (Risiko R7).

## Anforderungen

- Exakter, im Spiel-Repo versionierter Engine-Stand; ein Upgrade ist ein bewusster, sichtbarer Commit (US-04).
- Spiel-CI baut auf allen drei Plattformen ohne Handgriffe gegen die private Engine, mit minimalen Rechten.
- Lokale Engine-Iteration ohne Änderung an versionierten Dateien.
- Kein zusätzlicher Betrieb (Solo-Hobbyprojekt): kein Server, keine gehostete Registry.
- Builds aus sauberem Checkout reproduzierbar (PRD-0017 NFR).

## Optionen

1. **Private Cargo-Registry** (selbst gehostet oder als Dienst) — echte SemVer-Auflösung und `cargo publish`, aber ein Dienst mit Betrieb, Backups und Tokens in CI und lokal; `publish = false` müsste fallen. Für genau einen Konsumenten überdimensioniert.
2. **Git-Submodule** — Engine-Commit im Spiel-Repo, Anbindung per Pfad-Dependency. Der Submodule-Checkout braucht in CI denselben privaten Zugang, der Workflow ist fehleranfällig (detached HEAD, vergessenes `submodule update`), gepinnt wird ein Commit statt eines Tags — der SemVer-Bezug existiert nur per Konvention.
3. **Pfad-Dependency mit kombiniertem Checkout** — CI checkt beide Repos nebeneinander aus, Cargo nutzt `path = "../grimoire/..."`. Der Pin lebt dann in der Workflow-Datei statt in `Cargo.lock`; lokal baut das Spiel gegen den zufällig ausgecheckten Engine-Stand. Nicht reproduzierbar, untergräbt ADR-0002.
4. **Cargo-git-Dependency auf einen Branch** — einfach, aber jedes `cargo update` zieht Engine-HEAD nach. Das ist Option 2 aus ADR-0002 („Spiel folgt main"), dort bereits verworfen.
5. **Cargo-git-Dependency auf einen Tag (gewählt)** — `tag = "vX.Y.Z"` im Manifest, `Cargo.lock` hält den Commit-Hash; Upgrade = Tag ändern + `cargo update -p grimoire`.

## Entscheidung

Option 5, bestehend aus drei Teilen:

**1. Pin.** Das Spiel bindet die Engine im Workspace-Manifest an einen Release-Tag:

```toml
[workspace.dependencies]
grimoire = { git = "https://github.com/LupusMalusDeviant/grimoire", tag = "v0.1.0" }
```

Das Manifest nennt die HTTPS-URL (neutral gegenüber dem Transport). `Cargo.lock` wird committet;
CI baut mit `--locked`. Engine-Tags werden nach dem Release nie verschoben oder gelöscht. Das
Spiel-Repo versioniert eine `.cargo/config.toml` mit `[net] git-fetch-with-cli = true`, damit Cargo
lokal wie in CI über die git-CLI lädt; einen `[patch]` enthält diese Datei nie. *(Die beiden Sätze
zur `.cargo/config.toml` wurden bei der Umsetzung am 2026-09-14 ergänzt; ursprünglich war
`git-fetch-with-cli` als lokale Voraussetzung gedacht, siehe „Umsetzung“.)*

**2. CI-Zugriff über einen Read-only-Deploy-Key.** Der öffentliche Schlüssel liegt als Deploy-Key
**ohne Schreibrecht** auf `grimoire`, der private als Secret `GRIMOIRE_DEPLOY_KEY` in
`fiends-n-patrons`. Die lokale Action `.github/actions/engine-access` erkennt, ob ein `Cargo.toml`
die Engine referenziert, lädt den Schlüssel per `webfactory/ssh-agent`, lenkt
`https://github.com/LupusMalusDeviant/` per `git config --global url.<ssh>.insteadOf` auf
`git@github.com:LupusMalusDeviant/` um und setzt `CARGO_NET_GIT_FETCH_WITH_CLI=true`. Fehlt das
Secret, warnen CI und Nightly sichtbar und überspringen die Cargo-Schritte; der Release-Workflow
bricht ab. *(Bei der Umsetzung am 2026-09-14 verschärft: Seit das Spiel die Engine referenziert,
brechen auch CI und Nightly ab; nur Pull Requests ohne Secrets warnen noch, siehe „Umsetzung“.)* Einrichtung und Rotation übernimmt `scripts/setup-ci-deploy-key.ps1`. Ein Deploy-Key ist
einem persönlichen Token vorgezogen: Er gilt für genau ein Repo, nur lesend, und hat kein
Ablaufdatum. Weil er über `gh` angelegt wird, lebt er allerdings so lange wie die
GitHub-CLI-Autorisierung des Nutzers (siehe Konsequenzen).

**3. Lokale Iteration über `[patch]` in einer Cargo-Konfigurationsdatei außerhalb beider Repos.**
`<Arbeitsordner>\.cargo\config.toml` (nicht versioniert):

```toml
[patch."https://github.com/LupusMalusDeviant/grimoire"]
grimoire = { path = "grimoire/crates/grimoire" }
```

`[patch]` in Konfigurationsdateien ist stabiles Cargo (Cargo-Referenz „Configuration", Abschnitt
`[patch]`) und hat Vorrang vor einem `[patch]` im `Cargo.toml`. Relative Pfade in
Konfigurationsdateien beziehen sich auf das Verzeichnis, **das den `.cargo`-Ordner enthält** — hier
`<Arbeitsordner>\`. Deshalb lautet der Pfad `grimoire/crates/grimoire` und nicht
`../grimoire/crates/grimoire` (das zeigte auf `<Arbeitsordner>\..\grimoire`). Beides wurde am
2026-09-14 mit Cargo 1.98.1 in einem Wegwerf-Workspace nachgeprüft. Der `[patch]`-Block ist nur
während gemeinsamer Arbeit an Engine und Spiel aktiv und sonst auskommentiert (siehe Konsequenzen).

## Konsequenzen

- (+) Reproduzierbar: Tag im Manifest, Commit-Hash im Lockfile; ein Engine-Upgrade ist ein Zwei-Zeilen-Diff mit CHANGELOG-Bezug.
- (+) Keine Infrastruktur: GitHub, Cargo und ein Deploy-Key reichen.
- (+) Minimale Rechte in CI: Der Schlüssel kann die Engine nur lesen und kein anderes Repo erreichen.
- (+) Lokale Engine-Iteration ohne versionierte Änderung; gemergt wird weiterhin nur gegen Tags (ADR-0002).
- (−) Cargo löst bei git-Dependencies keine SemVer-Bereiche auf; jedes Upgrade ist Handarbeit (gewollt).
- (−) Auch mit aktivem `[patch]` muss Cargo die Original-Quelle erreichen, solange sie nicht im Cache liegt (nachgeprüft: `--offline` scheitert). Lokal braucht es daher Git-Zugangsdaten für das private Repo: `gh auth setup-git`. *(Ursprünglich stand hier „`gh auth setup-git` plus `net.git-fetch-with-cli = true`“; bei der Umsetzung am 2026-09-14 korrigiert:)* Die git-CLI ist dafür nicht zwingend, denn auch Cargos eingebauter Git-Client nutzt diesen Credential-Helper (siehe „Umsetzung“). `git-fetch-with-cli` steht trotzdem in der versionierten `.cargo/config.toml`, damit lokal und in CI derselbe Weg greift.
- (−) Ein aktiver Patch schreibt eine Pfad-Quelle in `Cargo.lock`. Dieses Lockfile darf nicht committet werden; die CI fällt dank `--locked` darauf auf.
- (−) Der Patch in `<Arbeitsordner>\.cargo\config.toml` gilt für jeden Cargo-Aufruf unterhalb von `<Arbeitsordner>\`, also auch im Engine-Repo und in Worktrees. Wo er ungenutzt ist, trägt Cargo `[[patch.unused]]` in `Cargo.lock` ein; jeder `--locked`-Aufruf (alle Pflichtprüfungen beider Repos) scheitert dann, ohne `--locked` verändert sich das Lockfile (nachgeprüft mit Cargo 1.98.1). Auch im Spiel scheitert `--locked`, solange der Patch greift. Deshalb ist der Patch ein bewusst ein- und wieder auszukommentierender Schalter und kein Dauerzustand.
- (−) Von `gh` angelegte Deploy-Keys hängen am Token der GitHub CLI: Wird diese Autorisierung widerrufen, entfernt GitHub den Key. Dann einmal das Setup-Skript erneut ausführen.
- (−) SSH über `webfactory/ssh-agent` auf Windows-Runnern ist laut Action-Doku noch wenig erprobt; der erste echte CI-Lauf mit Engine-Dependency ist die Verifikation.

## Umsetzung

Am 2026-09-14 in P0/WP6.3 umgesetzt, geprüft mit Cargo 1.98.1 unter Windows:

- `Cargo.toml` pinnt `grimoire` auf `tag = "v0.1.0"`. `Cargo.lock` hält für alle sieben bezogenen
  Engine-Crates (`grimoire`, `grimoire_core`, `grimoire_ecs`, `grimoire_gpu`, `grimoire_platform`,
  `grimoire_render`, `grimoire_sim`) die Quelle
  `git+https://github.com/LupusMalusDeviant/grimoire?tag=v0.1.0#93bed40d501632f6c722b9eeb56b927ae3bf4cdc`.
  Das ist der Commit des annotierten Tags, nicht das Tag-Objekt (`89e5aa4…`). `cargo tree -i grimoire
  --locked` zeigt genau ein `grimoire` aus dieser Quelle; eine Pfad-Quelle oder `[[patch.unused]]`
  kommt im Lockfile nicht vor.
- **Drittanbieter-Versionen:** Cargo liest bei Git-Dependencies das `Cargo.lock` der Engine nicht,
  sondern löst deren Abhängigkeiten neu auf („latest compatible“). Beim ersten Pin wurde das
  Spiel-Lockfile deshalb aus dem `Cargo.lock` des Engine-Tags vorbelegt. Alle Drittanbieter-Crates
  (wgpu, winit usw.) haben damit exakt die Versionen, die die Engine-CI für `v0.1.0` geprüft hat.
- **Korrektur der Annahme „lokal braucht Cargo `git-fetch-with-cli`“:** Die akzeptierte Fassung
  nannte unter „Konsequenzen“ `gh auth setup-git` **plus** `net.git-fetch-with-cli = true` als
  lokale Voraussetzung und sah die Einstellung damit neben dem `[patch]` in
  `<Arbeitsordner>\.cargo\config.toml`. Ein Probe-Workspace mit leerem `CARGO_HOME` holte das private Repo
  jedoch **auch ohne** `git-fetch-with-cli`, also über Cargos eingebauten Git-Client (libgit2). Der
  nutzt den von `gh auth setup-git` eingetragenen Credential-Helper ebenfalls. `git-fetch-with-cli`
  ist also keine Voraussetzung. Es bleibt aus Gründen der Einheitlichkeit mit der CI gesetzt, und
  zwar in einer versionierten `.cargo/config.toml` im Spiel-Repo statt in
  `<Arbeitsordner>\.cargo\config.toml`, sodass ein frischer Klon ohne weitere Datei auskommt. Die
  betroffenen Stellen in „Entscheidung“ und „Konsequenzen“ sind als Korrektur markiert.
- **CI:** `.github/actions/engine-access` erkennt die Referenz im Wurzel-`Cargo.toml`. Zum Zeitpunkt
  der Umsetzung waren weder das Secret `GRIMOIRE_DEPLOY_KEY` noch ein Deploy-Key auf `grimoire`
  eingerichtet. Die Verifikation des SSH-Wegs auf allen drei Runnern steht damit noch aus.
- **Kein weicher Modus mehr (Abweichung von „Entscheidung“, Teil 2):** Das Überspringen der
  Cargo-Schritte mit Warnung war für die Zeit gedacht, in der das Spiel die Engine noch nicht
  referenzierte. Seit WP6.3 referenziert jede Revision die Engine, ein fehlender Schlüssel ist also
  immer eine kaputte Einrichtung. Er bliebe sonst als dauerhaft grüner Leerlauf unbemerkt, etwa
  nach einem widerrufenen `gh`-Zugang, der den Deploy-Key entfernt. `ci.yml` übergibt deshalb
  `require` für Push, manuelle Läufe und Pull Requests aus dem eigenen Repo, `nightly.yml` immer.
  Nur Pull Requests ohne Secrets (Forks, Dependabot) warnen und überspringen weiterhin. Folge: Ohne
  `scripts/setup-ci-deploy-key.ps1` wird schon der erste Push rot. Das Skript muss also vorher
  laufen.

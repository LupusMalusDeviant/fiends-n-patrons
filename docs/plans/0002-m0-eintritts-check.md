# Plan-0002 · WP1.1: M0-Eintritts-Check, P0-Reste und Worktree-Konvention

- **Status:** Entwurf aus dem Agentenlauf, nicht committet; **nichts entschieden**, keine Issues angelegt
- **Datum:** 2026-09-15; unabhängig nachgeprüft (siehe „Nachprüfung“ am Ende)
- **Autor:** Claude (Agentenlauf, WP1.1)
- **Bezug:** [Plan 0002](0002-phase-p1-sichtbarer-kern.md) (WP1.1, „Meilensteine“ M0, „Abhängigkeiten“, „Arbeitsorganisation“, „Offene Punkte“), [Plan 0001](0001-phase-p0-fundament.md) („Umsetzungsstand“, „Abweichungen vom ursprünglichen Plan“, „Erfolgskriterien“), [Dossier Sammelsitzung A](0002-sammelsitzung-a-dossier.md), [Agentenlauf 2026-09-15](agentenlauf-2026-09-15.md), [CONTRIBUTING.md](../../CONTRIBUTING.md), grimoire `CONTRIBUTING.md`

> **Methode:** Jede Aussage unten ist, wo nicht anders vermerkt, während des Laufs mit lesenden Aufrufen
> nachgeprüft worden: `git rev-parse`, `git rev-list --left-right --count`, `git ls-remote`,
> `git worktree list`, `git log`/`git diff --stat` in beiden Repos sowie `gh run view`/`gh run list`,
> `gh pr list`, `gh release list`, `gh workflow list` und GET-Aufrufe auf die REST-API. Es wurde
> nichts gepusht, kein Lauf gestartet und nichts auf GitHub angelegt. Dass Läufe *überwacht* wurden,
> lässt sich über die API nicht belegen; geprüft ist nur ihr Ergebnis.

## 1. Eintritts-Check M0

Grundlage ist der Gate-Text in Plan 0002, „Meilensteine“, M0, aufgeteilt in einzeln prüfbare
Bedingungen. Links führen auf die GitHub-Läufe.

| # | Bedingung (Plan 0002, M0) | Status | Nachweis |
|---|---------------------------|--------|----------|
| 1 | Alle P0-Commits der **Engine** gepusht | erfüllt | `grimoire` lokal `main` = `origin/main` = `70a7fb0` (0 voraus, 0 zurück). Die einzigen weiteren lokalen Branches sind P1-Branches (`p1/wp1.0-scheduler`, `p1/wp1.4-sigil-syntax-spike`). |
| 2 | Alle P0-Commits des **Spiels** gepusht | erfüllt | `fiends-n-patrons` lokal `main` = `origin/main` = `640ab11` (0/0); kein weiterer lokaler Branch. |
| 3 | Zugehörige **Engine**-CI-Läufe grün auf 3 OS | erfüllt | [34883182308](https://github.com/LupusMalusDeviant/grimoire/actions/runs/34883182308) auf `0ef7696` und [34893513991](https://github.com/LupusMalusDeviant/grimoire/actions/runs/34893513991) auf `b5ba0fe` (`chore(release): v0.1.0`): alle Jobs `success` (rustfmt, Standalone-Gate, rustdoc, `test` auf Windows/Linux/macOS, Float-Vergleich). Die beiden späteren Commits `93bed40` (README, ADR-0004) und `70a7fb0` (drei Dateien unter `docs/adr/`) ändern nur Markdown bzw. `docs/` und lösen wegen `paths-ignore` in `ci.yml` keinen Lauf aus. Release-Lauf [34894065040](https://github.com/LupusMalusDeviant/grimoire/actions/runs/34894065040) auf Tag `v0.1.0`: `success` (nur Linux, wie vorgesehen). |
| 4 | Zugehörige **Spiel**-CI-Läufe grün auf 3 OS | erfüllt | [34903989101](https://github.com/LupusMalusDeviant/fiends-n-patrons/actions/runs/34903989101) auf `00d6683` und [34905253693](https://github.com/LupusMalusDeviant/fiends-n-patrons/actions/runs/34905253693) auf `8642f7d`: rustfmt und `test` auf Windows/Linux/macOS `success`. `640ab11` ändert nur `docs/plans/` (kein Lauf nötig). Im Log von 34903989101 meldet jeder der drei Test-Jobs „Engine-Git-Abhaengigkeit gefunden, Deploy-Key vorhanden: Zugriff ueber SSH.“ |
| 5 | Goldener Determinismus-Hash stimmt auf Windows, Linux und macOS überein | erfüllt, mit Einschränkung | **Engine:** `crates/grimoire_sim/tests/determinism.rs` (`TOTAL_TICKS = 10_000`, Test `double_run_gives_identical_hash_sequences`) ist Teil der Test-Jobs von 34893513991, grün auf drei OS. **Spiel:** Im Log von 34903989101 steht `test golden_final_hash_for_seed_42 ... ok` in allen drei Jobs (3.600 Ticks, Abweichung in Plan 0001 dokumentiert). **Einschränkung:** belegt nur im Debug-Profil; der Vergleich im Release-Profil (Nightly) ist nie gelaufen, siehe R-03/R-04. |
| 6 | Engine-ADR-0004 akzeptiert | erfüllt | `grimoire/docs/adr/0004-deterministische-gleitkommaarithmetik.md`, Statuszeile: „Akzeptiert (2026-09-14; Annahmekriterium im CI-Lauf 34893513991 auf Windows, Linux und macOS erfüllt)“. |
| 7 | OF-2.2 durch Engine-ADR-0006 entschieden, ADR-0003 abgelehnt | erfüllt | Statuszeilen: 0006 „Akzeptiert (2026-09-14; …freigegeben ist die Umsetzung erst mit dem Hash-Gate aus Baustein 7)“, 0003 „Abgelehnt (2026-09-14…)“; Index `grimoire/docs/adr/README.md` nennt 0003 „abgelehnt, ersetzt durch 0006“. Gepusht mit `70a7fb0` (einziger Commit zwischen Tag und `main`, laut `compare/v0.1.0...main` nur `docs/adr/`). Das Hash-Gate selbst gehört zu WP1.0, nicht zu M0. |
| 8 | P0-Review-Befunde gemergt | erfüllt, Vollständigkeit nicht prüfbar | In beiden Repos gibt es keinen Pull Request (`gh pr list --state all` leer) und keinen weiteren Remote-Branch mit P0-Stand; die Review-Korrekturen liegen direkt auf `main`, etwa Engine `a9adcaa`, `caf1093`, `8ca6fff`, `44461ce`, `30a5981`, `3fff4c3`, `6d07f05`, `5f3af92` („address verifier findings“) und Spiel `42b10bc`. Eine Befundliste, gegen die sich „alle gemergt“ abhaken ließe, habe ich nicht gefunden. |
| 9 | Engine-Tag `v0.1.0` remote | erfüllt | `git ls-remote`: `refs/tags/v0.1.0` (annotiert, `89e5aa4`) zeigt auf Commit `93bed40`; `gh release list`: „Grimoire v0.1.0“, *Latest*, 2026-09-14T20:39:26Z. `93bed40` unterscheidet sich vom CI-geprüften Release-Commit `b5ba0fe` nur in `README.md` und ADR-0004. |
| 10 | Engine-Abhängigkeit im Spiel-Manifest gemergt und auf den Tag gepinnt (P0-WP6.3) | erfüllt | `Cargo.toml` Zeile 18: `grimoire = { git = "https://github.com/LupusMalusDeviant/grimoire", tag = "v0.1.0" }`; `Cargo.lock`: Quelle `…grimoire?tag=v0.1.0#93bed40d501632f6c722b9eeb56b927ae3bf4cdc`; beides auf `origin/main`. `<Arbeitsordner>\.cargo\config.toml` existiert nicht, es ist also kein lokaler `[patch]` aktiv. |
| 11 | **PO-Sammelsitzung A:** OF-16.1 entschieden (Ort der C#-Suite oder „C#-Seite nach P2“) = P-1 | **offen** | Vorbereitet im [Dossier](0002-sammelsitzung-a-dossier.md), Abschnitt „P-1“ (Empfehlung `grimoire/tools/`, vorläufig). Weder `grimoire/tools/` noch `Prototype/tools/` existiert. |
| 12 | **PO-Sammelsitzung A:** Messsitzungs-Regeln und Referenz-Hardware abgestimmt = P-4 | **offen** | Vorbereitet im Dossier, Abschnitt „P-4“ (P-4a/P-4b). |

**Hinweis zur Abgrenzung.** Die Abhängigkeitstabelle von Plan 0002 (erste Zeile) nennt für M0 nur
„P0 gepusht, Tag `v0.1.0`, Pin, Engine-ADR-0004/0006 akzeptiert“; die Sammelsitzung A steht dort
in einer eigenen Zeile als Blocker für WP9/WP10 (P-1), WP6.5/WP11.2 (P-3) und WP3.3/WP11.5 (P-4).
Das Gate selbst verlangt aus der Sitzung nur P-1 und P-4. WP1.6 bündelt in Sammelsitzung A zusätzlich
P-3, P-5 bis P-9, P-13 und P-14. Das Dossier fragt außerdem OP-2 (Actions-Minuten) und OP-7
(Signierpflicht) ab, weil laufende Stränge daran hängen. Diese Punkte sind keine M0-Bedingungen, sind
aber ebenfalls offen.

### Was bis M0 bleibt

1. **PO-Sammelsitzung A** mit mindestens **P-1** und **P-4**. Danach kann M0 in Plan 0002 als
   erreicht vermerkt werden. Nach WP1.6 gehören in dieselbe Sitzung P-3, P-5 bis P-9, P-13, P-14
   sowie OP-2 und OP-7 (Fragenentwurf im Dossier).
2. **Keine M0-Bedingung, aber unmittelbar danach blockierend:** Die Freigabe von WP1.0 braucht ein
   grünes 3-OS-Hash-Gate (Engine-ADR-0006, Punkt 7) und damit CI-Minuten. Die Minutenfrage (OP-2,
   R-05 unten) steht deshalb in der Sitzung vor der Freigabe. `p1/wp1.0-scheduler` ist zum Prüfzeitpunkt
   **nicht** gepusht (kein Remote-Branch), der Workflow arbeitet noch.
3. Plan 0002 trägt weiterhin den Status „Entwurf“. Das Gate nennt keine Planabnahme; ob der PO sie
   mit M0 verbinden will, ist seine Sache.

## 2. P0-Reste als P1-Backlog

Aufgenommen ist jeder P0-Punkt, der nicht vollständig erledigt oder ausdrücklich verschoben ist,
sowie Dokumentationslücken aus P0, die Plan 0002 als offene Punkte führt. Die Entwürfe sind für die
nächste PO-Sitzung; **angelegt ist nichts**.

**Labels:** Beide Repos haben nur die GitHub-Standardlabels (`bug`, `documentation`, `enhancement`,
…; per `gh label list` geprüft). `p0-rest`, `needs-po`, `ci` und `render` müssten also erst angelegt
werden. Für Dokumentation wird das vorhandene Label `documentation` vorgeschlagen, damit kein
doppeltes `docs` entsteht.

| # | Titel | Repo | Labels | PO-Entscheidung |
|---|-------|------|--------|-----------------|
| R-01 | Run the window examples with a real GPU in a PO test session | `grimoire` | `p0-rest`, `needs-po`, `render` | ja |
| R-02 | Branch protection on main is unavailable on the current GitHub plan | `fiends-n-patrons` (betrifft beide Repos) | `p0-rest`, `needs-po`, `ci` | ja |
| R-03 | Engine nightly: release-profile cross-platform comparison has never run | `grimoire` | `p0-rest`, `needs-po`, `ci` | ja (Minuten) |
| R-04 | Game nightly: release-profile determinism gate has never run | `fiends-n-patrons` | `p0-rest`, `needs-po`, `ci` | ja (Minuten) |
| R-05 | Decide how to handle the GitHub Actions minutes quota | `fiends-n-patrons` (betrifft beide Repos) | `p0-rest`, `needs-po`, `ci` | ja |
| R-06 | Windows CI exceeds the 15-minute target with a cold cache | `grimoire` (Befund in beiden Repos) | `p0-rest`, `ci` | nein |
| R-07 | Document the engine checkout via the deploy key in ADR-0009 | `fiends-n-patrons` | `p0-rest`, `documentation` | nein |
| R-08 | Align CONTRIBUTING and plan texts with the P0 end state | `fiends-n-patrons` | `p0-rest`, `documentation` | nein |
| R-09 | Record the licence decision from P0-WP1.4 in both repositories | `fiends-n-patrons` (betrifft beide Repos) | `p0-rest`, `needs-po`, `documentation` | ja (Bestätigung); **erledigt** am 2026-09-15, [ADR-0012](../adr/0012-lizenz-alle-rechte-vorbehalten.md) |
| R-10 | Update the stale cross-platform note on the RNG golden test | `grimoire` | `p0-rest`, `documentation` | nein |

> **Nachtrag 2026-09-15 (Veröffentlichung):** Beide Repos sind inzwischen öffentlich. Dadurch sind R-02
> (Branch-Schutz im Free-Tarif), R-05 (Actions-Minuten) und R-07 (Deploy-Key in ADR-0009) in der
> beschriebenen Form überholt, und R-03/R-04 brauchen keine Minutenfreigabe mehr. R-08 Punkt 1
> (`webfactory/ssh-agent` in der Composite-Action) entfällt, weil die Action gelöscht ist
> ([ADR-0013](../adr/0013-oeffentliche-repos-anonymer-engine-abruf.md)); R-09 ist mit
> [ADR-0012](../adr/0012-lizenz-alle-rechte-vorbehalten.md) erledigt. Die Texte unten bleiben als
> Stand der Prüfung erhalten.

---

### R-01 — Run the window examples with a real GPU in a PO test session

- **Repo:** `grimoire` · **Labels:** `p0-rest`, `needs-po`, `render` · **PO-Entscheidung:** ja (Zustimmung zur Testsitzung, Zusammenhang mit P-4b)

**Kontext.** Plan 0001, „Umsetzungsstand“ WP4: „Der Fensterpfad mit echter GPU ist noch nie gelaufen
und wartet auf eine Testsitzung mit dem PO.“ In der CI werden die Beispiele nur gebaut; gerendert wird
ausschließlich offscreen (WARP unter Windows, lavapipe unter Linux, Metal unter macOS). WP3 vermerkt
nur, dass das Fenster-Beispiel unter Windows auf Bildschirm 2 geprüft wurde. Das P0-Erfolgskriterium
lautet „Fenster + instanzierte Sprites + fixed-timestep ECS-Loop laufen auf Win/Mac/Linux“, der
Meilenstein P0-M2 „Fenster + 10k instanzierte Sprites auf allen 3 Plattformen“.

**Was fehlt.**
- Die Beispiele `instancing` (`grimoire_render`) und `sim_loop` (`grimoire`) sind nie im Fenster auf
  einer Hardware-GPU gelaufen (Surface-Pfad, Present, `Lost`/`Outdated`-Wiederherstellung,
  Drosselung bei verdecktem Fenster).
- Auf echten macOS- und Linux-Geräten lief kein Fensterpfad (P0-R6 empfahl das ausdrücklich). Ob
  solche Geräte verfügbar sind, ist nicht bekannt.

**Akzeptanzkriterium.**
- In einer vom PO freigegebenen Sitzung laufen `window`, `instancing` und
  `sim_loop` auf dem Entwicklungsrechner mit `GRIMOIRE_WINDOW_MONITOR=secondary`,
  `GRIMOIRE_WINDOW_FOCUS=0` und `GRIMOIRE_EXAMPLE_MAX_FRAMES=<n>`. Alle drei Variablen gibt es in
  `v0.1.0` (per `git grep` im Tag geprüft).
- Jeder Lauf endet sauber ohne wgpu-Validierungsfehler. Adaptername und Backend stehen im Protokoll,
  dazu die FPS aus dem Fenstertitel als grober Wert (kein Budgetnachweis).
- Das Ergebnis steht im Umsetzungsstand von Plan 0001 (WP4) oder in einem Messprotokoll unter
  `grimoire/docs/messungen/`.
- Für macOS und Linux gibt es eine dokumentierte PO-Aussage: Gerät verfügbar und geprüft, oder der
  Nachweis wird nach E20 an das P3-Gate (PRD-0018 FR-06, Metal-Nachweis) verschoben.

**Bezug.** [Plan 0001, Umsetzungsstand WP3/WP4, Erfolgskriterien](0001-phase-p0-fundament.md#umsetzungsstand); [Plan 0002, Bildschirm- und GPU-Regel, WP3.3 Messsitzung 1](0002-phase-p1-sichtbarer-kern.md#arbeitsorganisation-agenten-stränge-und-bildschirmregel); Dossier P-4b. Vorschlag: mit Messsitzung 1 bündeln oder vorziehen; das entscheidet der PO.

---

### R-02 — Branch protection on main is unavailable on the current GitHub plan

- **Repo:** `fiends-n-patrons` (betrifft `grimoire` gleichermaßen) · **Labels:** `p0-rest`, `needs-po`, `ci` · **PO-Entscheidung:** ja

> *Nachtrag 2026-09-15:* Seit der Veröffentlichung antwortet GitHub nicht mehr mit 403. Entschieden:
> Ruleset auf `main` beider Repos gegen Force-Push und Löschen; direkte Pushes bleiben erlaubt, es gibt
> keine Pflicht-Checks, und die Ersatzregel gilt weiter.

**Kontext.** P0-WP2.4 und P0-M1 verlangen Branch-Schutz mit CI-Pflicht auf `main` in beiden Repos.
Plan 0001, „Abweichungen“: nicht umsetzbar, Ersatzregel „lokale Pflichtprüfungen vor jedem Push und
`gh run watch --exit-status` für jeden Push“ bis zur PO-Entscheidung. Im Lauf erneut geprüft:
`GET repos/LupusMalusDeviant/{grimoire,fiends-n-patrons}/branches/main/protection` **und**
`GET …/rulesets` antworten beide mit 403 „Upgrade to GitHub Pro or make this repository public to
enable this feature.“ Beide Repos sind privat und gehören einem Benutzerkonto (`owner.type = User`).

**Was fehlt.** Eine PO-Entscheidung zwischen den Möglichkeiten (nicht bewertet, nur gesammelt):
GitHub Pro; Ersatzregel dauerhaft als akzeptierte Abweichung festschreiben; Ersatzregel zusätzlich
technisch stützen (etwa ein lokaler `pre-push`-Hook mit den Pflichtprüfungen). Die Plan-Pflege hängt
davon ab: P0-M1 nennt „Branch-Schutz aktiv“ ohne Vermerk.

**Akzeptanzkriterium.**
- Die Entscheidung ist in Plan 0001 („Abweichungen“) und in beiden `CONTRIBUTING.md` vermerkt.
- Bei Pro: Schutzregel oder Ruleset auf `main` beider Repos mit Pflicht-Checks, per
  `gh api …/branches/main/protection` nachgewiesen. Außerdem ist dokumentiert, wie reine Doku-PRs
  durchkommen (Pfadfilter meldet keinen Status, siehe `CONTRIBUTING.md`, „CI im Überblick“).
- Ohne Pro: Die Ersatzregel ist als dauerhaft markiert, und P0-M1 trägt den Vermerk.

**Bezug.** [Plan 0001, WP2.4, Abweichungen, OP-1](0001-phase-p0-fundament.md#umsetzungsstand); hängt mit R-05 (Plan und Kontingent) zusammen.

---

### R-03 — Engine nightly: release-profile cross-platform comparison has never run

- **Repo:** `grimoire` · **Labels:** `p0-rest`, `needs-po`, `ci` · **PO-Entscheidung:** ja (CI-Minuten)

> *Nachtrag 2026-09-15:* Die Minutenfrage entfällt mit der Veröffentlichung, und geplante Nightlies
> werden nicht mehr abgebrochen. Offen bleibt der erste vollständige, überwachte Lauf.

**Kontext.** P0-WP5.6 und das P0-Erfolgskriterium verlangen den Cross-Plattform-Hash-Vergleich als
Nightly („Ergebnis dokumentiert, ggf. Fallback-ADR“); PRD-0018 FR-04 (b) verlangt ihn ausdrücklich
nightly. `grimoire/.github/workflows/nightly.yml` enthält dafür `test-release` (`cargo test
--workspace --release --locked --no-fail-fast` auf drei OS, Float-Sonden als Artefakt
`float-probe-release-<os>`) und `float-compare` („Release-Build (Nightly)“). Plan 0001, „Abweichungen“:
„Der Nightly-Workflow ist noch nie gelaufen“. Bestätigt: `gh run list --workflow nightly.yml` ist
leer. Die für heute geplanten Läufe (02:17 UTC) werden laut Agentenlauf-Log
(„Änderung — Actions-Minuten fast aufgebraucht“) beim Start abgebrochen, um Minuten zu sparen.

**Was fehlt.** Ein vollständiger Nightly-Lauf mit Ergebnis. Ohne ihn ist nicht belegt, dass die
Golden-Hashes und `dmath` auch mit Release-Optimierungen plattformgleich sind. Das ist die Annahme
hinter Engine-ADR-0004 für Release-Binaries.

**Akzeptanzkriterium.**
- Ein manueller Lauf `gh workflow run nightly.yml` auf `main`, bis zum Ende überwacht, alle Jobs grün.
- Das Ergebnis von `float-compare` (Job-Summary) steht mit Lauf-ID im Umsetzungsstand von Plan 0001
  oder Plan 0002.
- Bei rot: Analyse mit `gh run view --log-failed` und Einordnung als Code, Vorrichtung oder fremd.
  Weichen nur die Release-Hashes ab: Determinismus-Befund nach grimoire `CONTRIBUTING.md`
  („Golden-Master“, Regel 3), gegebenenfalls Folge-ADR zu ADR-0004.
- Der Zeitpunkt richtet sich nach der Minutenentscheidung (R-05). Kosten: ein 3-OS-Lauf, geschätzt
  14–87 abrechenbare Minuten; die Spanne ist nicht nachgemessen.

**Bezug.** [Plan 0001, WP5.6, Abweichungen, Erfolgskriterien](0001-phase-p0-fundament.md#umsetzungsstand) („Abweichungen vom ursprünglichen Plan“ ist ein fett gesetzter Absatz unter „Umsetzungsstand“, keine Überschrift, und hat daher keinen eigenen Anker); Agentenlauf „Anschlussarbeit“ Punkt 2 (entfällt heute wegen der Minuten).

---

### R-04 — Game nightly: release-profile determinism gate has never run

- **Repo:** `fiends-n-patrons` · **Labels:** `p0-rest`, `needs-po`, `ci` · **PO-Entscheidung:** ja (CI-Minuten)

> *Nachtrag 2026-09-15:* Die Minutenfrage entfällt mit der Veröffentlichung, und geplante Nightlies
> werden nicht mehr abgebrochen. Die Log-Zeile „Deploy-Key vorhanden“ im Akzeptanzkriterium gibt es
> nicht mehr, weil die Spiel-CI die Engine ohne Deploy-Key holt. Offen bleibt der erste vollständige,
> überwachte Lauf.

**Kontext.** Plan 0001, „Abweichungen“: „Der Determinismus-Test läuft zusätzlich im Release-Profil in
Nightly und Release.“ `nightly.yml` des Spiels führt je Plattform `cargo test --release --locked -p
fnp_sim_harness --test determinism` aus und baut danach `fiends-n-patrons` als 7-Tage-Artefakt. Es
gibt keinen eigenen Vergleichsjob; die Gleichheit ergibt sich daraus, dass
`golden_final_hash_for_seed_42` auf jedem OS gegen dieselbe Konstante prüft. Bestätigt:
`gh run list --workflow nightly.yml` und `--workflow release.yml` sind leer. Der für heute
geplante Lauf um 02:47 UTC wird laut Agentenlauf-Log beim Start abgebrochen.

**Was fehlt.** Ein grüner Nightly-Lauf mit Engine-Zugriff über SSH, der den goldenen Endhash im
Release-Profil auf drei OS belegt. Außerdem der erste reale Test des `changes`-Jobs (Aktivitäts-API
statt Commit-Datum) und der Artefakt-Pakete.

**Akzeptanzkriterium.**
- Ein manueller Lauf `gh workflow run nightly.yml` auf `main`, überwacht, grün auf drei OS. Im Log
  steht je Job „Engine-Git-Abhaengigkeit gefunden, Deploy-Key vorhanden“ und
  `golden_final_hash_for_seed_42 ... ok`.
- Lauf-ID und Laufzeit je OS stehen im Umsetzungsstand.
- Separat, beim nächsten *geplanten* Lauf nach einem `main`-Push: Der `changes`-Job entscheidet
  richtig. Ob das mit gesparten Minuten vereinbar ist, klärt R-05.

**Bezug.** [Plan 0001, Abweichungen](0001-phase-p0-fundament.md#umsetzungsstand); [CONTRIBUTING.md, CI im Überblick](../../CONTRIBUTING.md); PRD-0018 FR-04 (b).

---

### R-05 — Decide how to handle the GitHub Actions minutes quota

- **Repo:** `fiends-n-patrons` (Kontofrage, betrifft beide Repos) · **Labels:** `p0-rest`, `needs-po`, `ci` · **PO-Entscheidung:** ja

> *Nachtrag 2026-09-15:* Überholt. Der PO hat entschieden, beide Repos öffentlich zu machen; gehostete
> Standard-Runner verbrauchen dann keine Actions-Minuten. Nightlies werden nicht mehr manuell
> abgebrochen, und die Absätze „Kosten“ in beiden `CONTRIBUTING.md` sind angepasst. Plan 0002 schließt
> OP-2 und entschärft R21.

**Kontext.** P0-OP-1 („ausreichend Actions-Minuten für macOS-Matrix? In Woche 1 klären“, P0-R3) wurde
in P0 nicht abgeschlossen und lebt als Plan 0002 OP-2/R21 weiter. Stand laut GitHub-Meldung: 1.832
von 2.000 Minuten, Rücksetzung am 1. Oktober 2026; danach lief noch 34905253693 (3 OS). Das
Kontingent von 2.000 Minuten spricht für den Free-Plan; das ist abgeleitet, nicht gelesen. Im Lauf
geprüft: Das `gh`-Token hat die Scopes `gist`, `read:org`, `read:packages`, `repo`, `workflow`,
**nicht** `user`; Agenten können den Verbrauch nicht selbst lesen. Seit dem Lauf 34905253693 gilt: keine CI-Läufe
im Agentenlauf, geplante Nightlies werden manuell beim Start abgebrochen, die Workflows bleiben aktiv
(`gh workflow list`: CI, Nightly, Release in beiden Repos `active`).

**Was fehlt.**
- Die Entscheidung über Restminuten bis 1. Oktober, Planung ab Oktober und Verhalten bei
  Überschreitung. Optionen A–D mit Empfehlung (vorläufig) im Dossier, Abschnitt „OP-2“.
- Eine dauerhafte Regel für die Nightlies: manuell abbrechen, deaktivieren (eine Einstellung, die der
  PO selbst ändert) oder den Takt ändern.
- Geprüfte Gewichtung: Beide `CONTRIBUTING.md` sagen Windows ×2, macOS ×10; die GitHub-Doku nennt
  Minutenpreise (Windows ≈ ×1,7). Nicht geprüft.

**Akzeptanzkriterium.**
- Die PO-Entscheidung ist in Plan 0002 dokumentiert und OP-2 dort geschlossen oder präzisiert.
  Budget-Einstellung vom PO bestätigt (nicht von Agenten gesetzt).
- Die Nightly-Regel steht in beiden `CONTRIBUTING.md`, der Absatz „Kosten“ nennt geprüfte Faktoren
  oder den Hinweis „ungeprüft“.
- Bei einer Matrixänderung sind `ci.yml`/`nightly.yml` beider Repos angepasst und je ein Lauf bis
  zum Ende überwacht. Die betroffenen Plan-Texte (WP5.1, WP5.7, M2, Erfolgskriterien; siehe Dossier,
  „Konsequenzen“) sind nachgezogen.

**Bezug.** [Plan 0001, OP-1, R3, Abweichungen (Free-Tarif)](0001-phase-p0-fundament.md#offene-punkte); [Plan 0002, OP-2, R21](0002-phase-p1-sichtbarer-kern.md#offene-punkte); [Dossier, OP-2](0002-sammelsitzung-a-dossier.md#op-2--github-actions-minuten); [Agentenlauf, Änderung — Actions-Minuten fast aufgebraucht](agentenlauf-2026-09-15.md).

---

### R-06 — Windows CI exceeds the 15-minute target with a cold cache

- **Repo:** `grimoire` (derselbe Befund im Spiel; ein Issue genügt, Verweis im anderen Repo) · **Labels:** `p0-rest`, `ci` · **PO-Entscheidung:** nein, solange nur die Auslegung dokumentiert wird

**Kontext.** PRD-0017 NFR und das P0-Erfolgskriterium: „CI-Laufzeit Standard-Push < 15 Min pro
Plattform“. Plan 0001 WP2 nennt 15:46 min beim ersten Windows-Lauf mit kaltem Cache und 2,7 min mit
warmem Cache. Im Lauf aus den Job-Zeiten nachgerechnet:

| Lauf | Commit | Windows | Linux | macOS |
|------|--------|---------|-------|-------|
| Engine [34883182308](https://github.com/LupusMalusDeviant/grimoire/actions/runs/34883182308) | `0ef7696` | **15:46** | 8:35 | 3:51 |
| Engine [34893513991](https://github.com/LupusMalusDeviant/grimoire/actions/runs/34893513991) | `b5ba0fe` | 2:44 | 1:41 | 0:56 |
| Spiel [34903989101](https://github.com/LupusMalusDeviant/fiends-n-patrons/actions/runs/34903989101) | `00d6683` | 13:15 | 7:33 | 1:49 |
| Spiel [34905253693](https://github.com/LupusMalusDeviant/fiends-n-patrons/actions/runs/34905253693) | `8642f7d` | 1:51 | 0:48 | 0:27 |

**Was fehlt.** Eine festgelegte Auslegung, ob das Ziel für warmen Cache gilt. Außerdem eine Aussage,
wie oft der Cache kalt ist. Nach GitHub-Doku verfallen ungenutzte Caches nach 7 Tagen (nicht
nachgeprüft). Bei seltenen Pushes, wie sie die Minutenlage erzwingt, werden kalte Läufe also
häufiger und teurer.

**Akzeptanzkriterium.**
- PRD-0017-Auslegung (warmer Cache) in Plan 0001, Erfolgskriterien, und in beiden `CONTRIBUTING.md`
  vermerkt.
- Kalt-Laufzeiten werden im Umsetzungsstand je Meilenstein mitprotokolliert (passt zu Plan 0002 OP-5).
- Nur falls der PO den Kaltstart ins Ziel einbezieht: Optimierung (Cache-Schlüssel, Build-Umfang
  unter Windows) als eigener `ci:`-Commit mit überwachtem Lauf. Dann ja, `needs-po`.

**Bezug.** [Plan 0001, Umsetzungsstand WP2, Erfolgskriterien](0001-phase-p0-fundament.md#erfolgskriterien); Plan 0002 OP-5, R13.

---

### R-07 — Document the engine checkout via the deploy key in ADR-0009

- **Repo:** `fiends-n-patrons` · **Labels:** `p0-rest`, `documentation` · **PO-Entscheidung:** nein

> *Nachtrag 2026-09-15:* Überholt. Das Engine-Repo ist öffentlich, Deploy-Key und Secret sind gelöscht;
> der Engine-Checkout in WP9.3 braucht keine Zugangsdaten (Plan 0002, OP-6;
> [ADR-0013](../adr/0013-oeffentliche-repos-anonymer-engine-abruf.md)).

**Kontext.** Plan 0002 OP-6: Die Spiel-CI soll das Engine-Repo am gepinnten Tag über den vorhandenen
Deploy-Key auschecken (für `sigilc` im Asset-Compiler-Gate, WP9.3). ADR-0009 beschreibt den Key bisher
nur für den Cargo-Git-Fetch (Entscheidung §2, „Umsetzung“). Geprüft: Heute enthält kein Spiel-Workflow
einen `actions/checkout` des Engine-Repos. Alle Engine-Zugriffe laufen über
`.github/actions/engine-access` (`ci.yml` Zeile 64, `nightly.yml` 106, `release.yml` 86). Die Lücke
wird also erst mit WP9.3 wirksam.

**Was fehlt.** Im Umsetzungsteil von ADR-0009: dass derselbe Read-only-Key für `actions/checkout`
genutzt wird, welcher Ref (Tag aus `Cargo.toml`, nicht `main`), Cache-Schlüssel und gemessene
Laufzeit. Außerdem ein Satz in `CONTRIBUTING.md`, „Engine-Zugriff der CI“.

**Akzeptanzkriterium.**
- ADR-0009 „Umsetzung“ ist spätestens im PR von WP9.3 ergänzt. Der Workflow liest den Tag aus dem
  Manifest statt ihn doppelt zu pflegen.
- Cache-Schlüssel und Laufzeit des ersten Laufs sind im Umsetzungsstand von Plan 0002 notiert.
- Ein reiner Doku-Vorgriff vor WP9.3 ist möglich, dann klar als „geplant“ markiert.

**Bezug.** [Plan 0002, OP-6, WP9.3](0002-phase-p1-sichtbarer-kern.md#offene-punkte); [ADR-0009](../adr/0009-engine-pin-ueber-git-tag.md). Zeitpunkt hängt an P-1 nur indirekt, weil WP9 nach M2 startet.

---

### R-08 — Align CONTRIBUTING and plan texts with the P0 end state

- **Repo:** `fiends-n-patrons` · **Labels:** `p0-rest`, `documentation` · **PO-Entscheidung:** nein (reine Nachführung; nichts davon ändert eine Entscheidung)

**Kontext.** Beim Prüfen gefundene Stellen, die dem heutigen Stand widersprechen (alle nachgeprüft).
Reine Doku-Commits lösen keine CI aus (`paths-ignore`).

**Was fehlt.**
1. **`CONTRIBUTING.md`, „Versionen der GitHub Actions“** (Zeilen 342–344) nennt `Swatinem/rust-cache@v2`,
   `orhun/git-cliff-action@v4` und `webfactory/ssh-agent@v0.10.0` als Tag-Pins. Tatsächlich sind
   Commit-SHAs mit Versionskommentar gepinnt: `Swatinem/rust-cache@6323deb… # v2.9.2` (`ci.yml` 71,
   `nightly.yml` 113, `release.yml` 92), `orhun/git-cliff-action@3d96a18… # v4.9.0` (`release.yml` 139)
   und `webfactory/ssh-agent@e838748… # v0.10.0` — Letzteres nicht in einem Workflow, sondern in der
   Composite-Action `.github/actions/engine-access/action.yml` (Zeile 102). Die Engine hat den
   Abschnitt schon angepasst (`0233c4e`).
2. **Plan 0002, „Referenzen“ (letzte Zeile):** „Engine-ADRs 0001–0005“; es gibt 0001–0006 (0003
   abgelehnt, 0006 akzeptiert).
3. **PRD-0016, OF-16.1 (Zeile 105):** „PO-Entscheidung vor P0“; überholt, entschieden wird an M0
   (Plan 0002, P-1). Laut Plan in WP11.6 nachzuziehen; bis dahin genügt ein Vermerk.
4. **Plan 0001, „Erfolgskriterien“:** kein Abgleich je Kriterium. Vorschlag für eine kurze Tabelle:
   10.000 Ticks mit Doppellauf auf 3 OS (Engine) erfüllt; Nightly-Vergleich offen (R-03/R-04);
   Standalone-Gate erfüllt; Pin auf `v0.1.0` erfüllt; < 15 Min teilweise (R-06); Fenster auf drei
   Plattformen offen (R-01). Dazu P0-M1 „Branch-Schutz aktiv“ mit Verweis auf R-02 und P0-M2
   „erstes zeigbares GIF“ (in keinem Repo liegt ein GIF, hängt an R-01).
5. **Plan 0001, „Offene Punkte“:** OP-2 (eigener ADR-Zähler, umgesetzt: `grimoire/docs/adr/`) und
   OP-3 (strikt 2D in P0, Kipp in P1 laut Plan 0002 WP2) sind erledigt, aber nicht als geschlossen
   markiert; OP-1 verweist auf R-02/R-05.

**Akzeptanzkriterium.** Die fünf Stellen sind angepasst, in einem `docs:`-Commit im Spiel-Repo.
`CONTRIBUTING.md` und Workflows nennen dieselben Pins.

**Bezug.** [Plan 0001](0001-phase-p0-fundament.md), [Plan 0002, Referenzen](0002-phase-p1-sichtbarer-kern.md#referenzen), [CONTRIBUTING.md](../../CONTRIBUTING.md), PRD-0016 OF-16.1.

---

### R-09 — Record the licence decision from P0-WP1.4 in both repositories

- **Repo:** `fiends-n-patrons` (betrifft `grimoire` gleichermaßen) · **Labels:** `p0-rest`, `needs-po`, `documentation` · **PO-Entscheidung:** ja (Bestätigung des Lizenzentscheids; eine Rechtsfrage legt kein Agent fest)

**Kontext.** P0-WP1.4 verlangt „Lizenz-Entscheid (privat/All rights reserved) dokumentiert“. Der
Umsetzungsstand von Plan 0001 meldet WP1 als „erledigt“, erwähnt die Lizenz aber nicht. Geprüft
(Nachprüfung): Keines der beiden Repos hat eine `LICENSE`- oder `COPYING`-Datei; die
Workspace-`Cargo.toml` beider Repos setzen nur `publish = false`, kein `license`/`license-file`;
`README.md` und `CONTRIBUTING.md` beider Repos erwähnen weder Lizenz noch „All rights reserved“
(`grep -i "lizenz|licen|rights"`); kein Commit mit „licen“ im Betreff. Die Planformulierung nennt
nur die Empfehlung, keinen festgehaltenen Entscheid.

**Was fehlt.** Der vom PO bestätigte Lizenzentscheid, an einer auffindbaren Stelle je Repo.

**Akzeptanzkriterium.**
- Der PO bestätigt „privat / All rights reserved“ oder nennt eine andere Lizenz.
- Beide Repos tragen den Entscheid sichtbar (Abschnitt im `README.md` oder eine `LICENSE`-Datei) und,
  falls gewünscht, `license`/`license-file` in `[workspace.package]`.
- Plan 0001, Umsetzungsstand WP1, nennt den Entscheid mit Commit.
- Reine Doku-Änderungen lösen keine CI aus; eine Änderung an `Cargo.toml` schon (Minuten, R-05) —
  dann mit dem nächsten Code-Commit bündeln.

**Bezug.** [Plan 0001, WP1.4](0001-phase-p0-fundament.md#wp1-repo-fundament--projektskelett); [Plan 0001, Umsetzungsstand WP1](0001-phase-p0-fundament.md#umsetzungsstand).

**Erledigt (2026-09-15).** Der PO hat entschieden: Beide Repos bleiben „Alle Rechte vorbehalten“,
Rechteinhaber ist Lupus Malus Deviant, obwohl beide Repos öffentlich werden. Umgesetzt mit einer
`LICENSE`-Datei im Wurzelverzeichnis beider Repos, `license-file` in `[workspace.package]` und in
jeder Crate, einem Abschnitt „Lizenz“ in beiden `README.md`, [ADR-0012](../adr/0012-lizenz-alle-rechte-vorbehalten.md)
und Engine-ADR-0009 (Nummer vorläufig). Plan 0001 nennt den Entscheid im Umsetzungsstand WP1.
Korrektur zum Kontext oben: Beide `README.md` enthielten bereits den Satz „Alle Rechte vorbehalten“;
die Suche fand ihn nicht, weil sie nur englische Begriffe enthielt. Rechteinhaber, Jahr und
`LICENSE`-Datei fehlten allerdings tatsächlich.

---

### R-10 — Update the stale cross-platform note on the RNG golden test

- **Repo:** `grimoire` · **Labels:** `p0-rest`, `documentation` · **PO-Entscheidung:** nein (Kommentar, kein Golden-Wert)

**Kontext.** `crates/grimoire_sim/tests/rng.rs`, Zeilen 7–11: Die Golden-Folge `GOLDEN_5EED` sei
„Measured once on Windows x86_64“ und „(not yet verified on other platforms)“. Geprüft: Im Log von
Engine-Lauf [34893513991](https://github.com/LupusMalusDeviant/grimoire/actions/runs/34893513991)
steht `test golden_sequence_for_seed_5eed ... ok` in allen drei Test-Jobs (Windows, Linux, macOS).
Der Vorbehalt ist damit überholt. Die Suche nach `TODO`, `FIXME`, `XXX`, `HACK`, `todo!(` und
`unimplemented!(` in beiden Repos ergab sonst keine Treffer im Code (siehe „Geprüft, kein P0-Rest“).

**Was fehlt.** Der Kommentar nennt den Nachweis (Lauf-ID, drei OS) statt des Vorbehalts. Der
Golden-Wert selbst bleibt unverändert (grimoire `CONTRIBUTING.md`, „Golden-Master“, Regel 4).

**Akzeptanzkriterium.**
- Kommentar in `rng.rs` angepasst; `GOLDEN_5EED` und `SimRng::ALGORITHM_VERSION` unverändert.
- Die Datei liegt unter `crates/`, eine Änderung löst also die Engine-CI aus: mit dem nächsten
  Engine-Code-Commit bündeln (etwa im WP1.0-Branch nach dessen Freigabe), kein eigener Lauf.

**Bezug.** grimoire `crates/grimoire_sim/tests/rng.rs`; Lauf 34893513991; Plan 0001, Erfolgskriterien (Determinismus auf 3 Plattformen).

---

### Geprüft, kein P0-Rest

- **Golden-Run des Spiels über 3.600 statt 10.000 Ticks:** bewusste, dokumentierte Abweichung (Plan 0001,
  „Abweichungen“). Das 10.000-Tick-Gate mit Doppellauf existiert in der Engine
  (`grimoire_sim/tests/determinism.rs`).
- **Abweichende Trait-Namen (`AppHandler`/`PlatformContext` statt `EventPump`/`RawInputSource`) und
  Beispielorte je Crate:** dokumentiert, per Engine-ADR-0001 begründet.
- **Commit zwischen Tag und `main` ohne CI-Lauf:** `70a7fb0` ändert nur `docs/adr/`; der Tag-Commit
  `93bed40` weicht vom CI-geprüften `b5ba0fe` nur in `README.md` und ADR-0004 ab.
- **Engine-CHANGELOG `[Unreleased]` leer, obwohl ADR-0006 akzeptiert ist:** Laut grimoire
  `CONTRIBUTING.md` („Release“, Schritt 2) wird der Abschnitt beim nächsten Release aus den Commits
  gepflegt; kein Rest.
- **Deploy-Key hängt am Token der GitHub CLI:** bekanntes, in `CONTRIBUTING.md` und ADR-0009
  dokumentiertes Verhalten mit Wiederherstellungsweg (`setup-ci-deploy-key.ps1 -ReplaceExisting`).
  *Nachtrag 2026-09-15: entfällt, der Deploy-Key ist gelöscht.*
- **Spiel-Release und `release.yml` des Spiels nie gelaufen:** kein P0-Ziel (Spiel-Releases sind P3,
  PRD-0017).
- **TODO/FIXME-Kommentare:** `git grep -E "TODO|FIXME|XXX|HACK|todo!\(|unimplemented!\("` findet in
  beiden Repos nur zwei Doku-Zeilen über das `todo!()`-Verbot (grimoire `crate-vertraege.md` Regel 7,
  Plan 0002 WP1.3), keinen offenen Marker im Code.
- **Platzhalter-Crates** (`grimoire_assets`, `_audio`, `_collide`, `_debug`, `_sigil`, `_ui`): tragen
  „placeholder — implementation starts in phase P1/P2“; so in `crate-vertraege.md` §10 vorgesehen.
- **Zwei `#[ignore]`-Messtests** (`grimoire_ecs/tests/timing.rs`, `grimoire_render/tests/offscreen.rs`):
  bewusst manuell im Release-Profil; von der OF-17.3-Vorbereitung für WP6.1 aufgegriffen.
- **Clippy mit `-D warnings` (P0-WP2.1):** läuft im `test`-Job beider CI-Workflows (Engine `ci.yml`
  115, Spiel `ci.yml` 77).
- **10.000 Sprites (P0-Ziel, WP4.3):** `instancing.rs` setzt `SPRITE_COUNT = 10_000`; der Fensterlauf
  selbst fehlt (R-01).

### Bewusst nicht aufgenommen (P1-Themen, keine P0-Reste)

- Signierpflicht für Windows-Binaries (Plan 0002 OP-7, Dossier), Standalone-Gate für einen künftigen
  Ordner `tools/` (hängt an P-1), Hash-Gate und Freigabe von WP1.0 (Engine-ADR-0006, Punkt 7),
  Adapter-Tabelle und Metal auf macOS-Runnern (OP-3, WP2.1).

## 3. Worktree-Konvention

**Regel (Plan 0002, WP1.1 und „Arbeitsorganisation“):** Jeder Agenten-Strang arbeitet in einem eigenen
Git-Worktree unter

```text
<Arbeitsordner>\_wt\p1-<strang>
```

Plan 0001 („Abweichungen“) ergänzt: Die Worktrees sind **temporär** und werden nach Review in `main`
zusammengeführt.

**Strangnamen.** Plan 0002 nennt die Stränge nur als Wörter. Die Kurzformen unten sind ein
**Vorschlag** (klein, ASCII, ohne Umlaute), nicht entschieden:

| Strang (Plan 0002) | Paket | Vorgeschlagener Ordner |
|--------------------|-------|------------------------|
| Verträge | WP1 | `_wt\p1-vertraege` |
| Render-A | WP2 | `_wt\p1-render-a` |
| Messung | WP6 | `_wt\p1-messung` |
| Render-B | WP3 | `_wt\p1-render-b` |
| Sigil-Sprache | WP4 | `_wt\p1-sigil-sprache` |
| Sigil-Laufzeit | WP5 | `_wt\p1-sigil-laufzeit` |
| Pipeline-Rust | WP8 | `_wt\p1-pipeline-rust` |
| Absicherung | WP7 | `_wt\p1-absicherung` |
| Tooling | WP10 | `_wt\p1-tooling` |
| Pipeline-C# | WP9 | `_wt\p1-pipeline-cs` |
| Integration | WP11 | `_wt\p1-integration` |

Für eng umrissene Einzelschritte nennt der Plan selbst eigene Worktrees (WP1.0: `p1-scheduler`).
Beobachtete Branch-Namen folgen dem Muster `p1/wp<nr>-<thema>`.

**Regeln, die für alle Worktrees gelten** (aus den genannten Quellen, nicht neu):

- **Höchstens vier Stränge gleichzeitig aktiv** (Plan 0002, „Arbeitsorganisation“).
- **`[patch]` bleibt aus:** Ein aktiver `[patch]` in `<Arbeitsordner>\.cargo\config.toml`
  gilt für jeden Cargo-Aufruf unter `<Arbeitsordner>\`, also auch in **allen** Worktrees unter `_wt\`, und
  bricht dort `--locked` (beide `CONTRIBUTING.md`, ADR-0009). Zum Prüfzeitpunkt existiert die Datei
  nicht. In P1 pinnt das Spiel stattdessen Alpha-Tags (P-7, noch nicht entschieden).
- **Nur gegen gemergte Verträge bauen**; Vertragsänderungen als eigener Vertrags-PR (WP1.7).
- **ADR-Nummern erst beim Merge** vergeben (Plan 0002, „Arbeitsorganisation“). Der Syntax-Spike trägt
  vorläufig „Engine-ADR-0007“.
- **Merge nur nach adversarialem Review**, jeder Push mit CI bis zum Ende überwacht, der erste Push
  eines neuen Branches auf Pfadfilter-Lücken geprüft (Spiel-`CONTRIBUTING.md`).
- **Aufräumen** (`git worktree remove`) erst nach dem Merge bzw. nach der Entscheidung über einen
  Spike, und nur durch die Hauptsitzung.

**Offene Frage zur Konvention (keine PO-Entscheidung, für die Hauptsitzung):** Das Muster
unterscheidet nicht zwischen Engine- und Spiel-Worktrees. Braucht ein Strang beide Repos (etwa
Absicherung: Harness im Spiel, Replay v2 in der Engine), kollidieren die Ordnernamen. Möglich wäre
`p1-<strang>` für die Engine und `p1-<strang>-spiel` für das Spiel. Heute gibt es nur Engine-Worktrees.

### Bestehende Worktrees (Stand 2026-09-15)

Gelesen mit `git worktree list --porcelain` und `git branch -vv` aus den Hauptcheckouts. In den
Worktree-Ordnern selbst wurde nichts ausgeführt.

| Repo | Pfad | Branch | HEAD | Remote | Bemerkung |
|------|------|--------|------|--------|-----------|
| `grimoire` | `<Arbeitsordner>\grimoire` | `main` | `70a7fb0` | = `origin/main` | Hauptcheckout |
| `grimoire` | `<Arbeitsordner>\_wt\p1-scheduler` | `p1/wp1.0-scheduler` | `68a2811`, wenige Minuten später `6dcebfb` (bei der Nachprüfung unverändert) | **nicht gepusht** (kein Remote-Branch; `ls-remote refs/heads/p1/*` bei der Nachprüfung nur mit dem Spike-Branch) | WP1.0, Strang B des Agentenlaufs; ein Workflow arbeitet aktiv darin. Nicht anfassen. Endet laut Agentenlauf als gepushter Branch ohne PR. |
| `grimoire` | `<Arbeitsordner>\_wt\p1-sigil-spike` | `p1/wp1.4-sigil-syntax-spike` | `65e5288` | = `origin/p1/wp1.4-sigil-syntax-spike` | WP1.4, Strang D; ohne PR, ohne CI-Lauf; Bericht und Engine-ADR-0007 „Vorgeschlagen“. |
| `fiends-n-patrons` | `<Arbeitsordner>\Prototype` | `main` | `640ab11` | = `origin/main` | Hauptcheckout; keine weiteren Worktrees |

**Abweichung von der Konvention:** `p1-sigil-spike` ist kein Strangname. WP1.4 gehört zum Strang
Verträge; der Ordner ist ein Spike-Worktree wie `p1-scheduler`. Vorschlag: Name so lassen und den
Worktree nach der Entscheidung in Sammelsitzung B entfernen; der gepushte Branch bleibt als Referenz.

## Nicht geprüft oder nicht prüfbar

- Ob die CI-Läufe tatsächlich *überwacht* wurden (nur ihr Ergebnis ist über die API sichtbar).
- Vollständigkeit der P0-Review-Befunde (keine Befundliste gefunden, siehe M0-Bedingung 8).
- Genaues Restkontingent der Actions-Minuten, Plan des Kontos, Verhalten bei Überschreitung und die
  Windows-Gewichtung (Token ohne Scope `user`; siehe Dossier, „Nicht bestätigte Angaben“).
- Die Kostenspanne 14–87 Minuten je 3-OS-Lauf (Schätzung aus dem Agentenlauf, nicht nachgemessen).
- Die 7-Tage-Verfallsregel für Actions-Caches (GitHub-Doku, heute nicht abgerufen).
- Verfügbarkeit echter macOS- und Linux-Geräte für R-01.
- Ob der Lizenzentscheid (R-09) außerhalb der beiden Repos festgehalten ist (etwa in einer Notiz des PO). *(Gegenstandslos seit [ADR-0012](../adr/0012-lizenz-alle-rechte-vorbehalten.md).)*

## Nachprüfung (2026-09-15)

Unabhängig vom Entwurf erneut geprüft, nur lesend (`git rev-parse`/`rev-list`/`ls-remote`/`worktree
list`/`diff --stat`/`grep`, `gh run view` inklusive `--log`, `gh run list`, `gh pr list`,
`gh release list`, `gh label list`, `gh workflow list`, `gh auth status`, GET auf `branches/main/protection`,
`rulesets` und `repos/…`), dazu die zitierten Dateien gelesen. Nichts gepusht, kein Lauf, nichts angelegt.

**Bestätigt ohne Änderung:** alle zwölf M0-Status. Im Einzelnen: `main` = `origin/main` in beiden Repos
(0/0); Jobergebnisse, Commits und Jobzeiten der Läufe 34883182308, 34893513991, 34894065040,
34903989101 und 34905253693 (die Tabelle in R-06 stimmt auf die Sekunde); `double_run_gives_identical_hash_sequences`
auf drei OS im Log von 34893513991; „Engine-Git-Abhaengigkeit gefunden, Deploy-Key vorhanden“ und
`golden_final_hash_for_seed_42 ... ok` in allen drei Jobs von 34903989101 (ebenso 34905253693);
`GOLDEN_TICKS = 3_600`; Diffs `b5ba0fe..93bed40` (README, ADR-0004) und `v0.1.0..main` (drei Dateien
unter `docs/adr/`); `paths-ignore` für `**/*.md` und `docs/**` in beiden `ci.yml`; annotierter Tag
`89e5aa4` → `93bed40`; Statuszeilen ADR-0003/0004/0006 und ADR-Index; Review-Commits mit den genannten
Betreffen; `Cargo.toml` Zeile 18 und `Cargo.lock`; keine `<Arbeitsordner>\.cargo\`; keine PRs, nur
Standardlabels, 403 für Branch-Schutz und Rulesets, `private=true`, `owner=User`; Token-Scopes ohne
`user`; Nightly-Crons 02:17/02:47 UTC; M0-Gate-Text und Abhängigkeitszeilen in Plan 0002; OP-2, OP-5,
OP-6, R13, R21 und „Engine-ADRs 0001–0005“ in Plan 0002; PRD-0016 Zeile 105; PRD-0017 „< 15 Min“.

**Korrigiert:**
- R-07: Zeilennummern der Engine-Zugriffe waren falsch (`ci.yml` hat nur Zeile 64; `release.yml` ist
  Zeile 86, nicht 88).
- R-08 Punkt 1: `webfactory/ssh-agent` ist nicht in einem Workflow gepinnt, sondern in
  `.github/actions/engine-access/action.yml` Zeile 102; Fundstellen der übrigen SHA-Pins ergänzt.
- R-03: Der Link-Anker `#abweichungen-vom-ursprünglichen-plan` existiert nicht (fetter Absatz, keine
  Überschrift); ersetzt durch `#umsetzungsstand`.
- R-03/R-04: „PRD-0018 FR-04b“ gibt es als Kennung nicht; PRD-0018 führt FR-04 mit den Teilen (a)–(c).
  Jetzt „FR-04 (b)“.
- Worktree-Tabelle: Stand von `p1/wp1.0-scheduler` bei der Nachprüfung nachgetragen (weiter `6dcebfb`, nicht gepusht).

**Ergänzt:** R-09 (Lizenzentscheid aus P0-WP1.4 nirgends dokumentiert), R-10 (überholter
Plattform-Vorbehalt in `rng.rs`), P0-M2-GIF als Hinweis in R-08 Punkt 4, fünf weitere Punkte unter
„Geprüft, kein P0-Rest“ (TODO/FIXME-Suche, Platzhalter-Crates, `#[ignore]`-Messtests, Clippy, 10.000 Sprites).
Damit sind es zehn Issue-Entwürfe, sechs davon mit PO-Entscheidung.

# Vorbereitung Spike OF-17.3: Benchmark-Rauschen auf gehosteten Runnern (Plan 0002, WP6.1)

- **Stand:** 2026-09-15 (Agentenlauf, Arbeitsstrang E)
- **Status:** Vorbereitung — nichts davon ist gemessen, entschieden oder vom PO bestätigt. Alle Empfehlungen sind **vorläufig (PO-Bestätigung ausstehend)**.
- **Bezug:** [Plan 0002](0002-phase-p1-sichtbarer-kern.md) WP6.1/WP6.2/WP6.5–6.7, R10, R21, P-12, OP-2, OP-5, M2-Kriterium; [PRD-0017](../prd/0017-plattform-ci-distribution.md) FR-03 und OF-17.3; [PRD-0018](../prd/0018-teststrategie.md) (Benchmark-Trends ab P1, Kopplung OF-18.2, bewusste Erneuerung statt stiller Erwartungsänderung); Engine-ADR-0006 (Benches mit 1 und N Threads); Engine-`crate-vertraege.md` §2 Regel 4.
- **Nicht getan:** kein CI-Lauf, kein Push, kein Code, keine Runner-Messung. Gemessen wurde nur eine lokale Zeitprobe der vorhandenen P0-Tests auf dem Entwicklerrechner (§3.2, Grundlage der Richtwerte). Die Minutenangaben sind Schätzungen, die der erste Lauf ersetzen muss (OP-5).
- **Gegenprüfung:** Codex (gpt-6-astra, read-only) hat einen ersten Entwurf geprüft (§9.1). Eine zweite Prüfung auf Werkzeugfakten, Schätzungen, fehlende Kandidaten und flatternde Gate-Regeln steht in §9.2. Codex stand dabei zweimal nicht zur Verfügung; die Prüfung lief ohne Codex, mit Belegen aus dem Netz.

> **Nachtrag 2026-09-15 (Veröffentlichung):** Beide Repos sind öffentlich. Für diesen Vorschlag heißt
> das: Gehostete Standard-Runner verbrauchen keine Actions-Minuten; Minutenschätzungen und die Faktoren
> ×2/×10 sind nur noch als Laufzeitangaben zu lesen, die Kontingentgrenzen (OP-2, R21) entfallen. Die
> Runner öffentlicher Repos haben unter Linux und Windows 4 vCPUs mit 16 GB statt 2 vCPUs mit 8 GB;
> Rauschannahmen für 2-vCPU-Runner muss der Spike neu bestätigen. Actions-Artefakte werden höchstens
> 90 Tage aufbewahrt, GitHub Pages ist ohne Pro verfügbar, und alle Trenddaten sind öffentlich. Ein
> Self-Hosted-Runner hinge an einem öffentlichen Repo (§6.2).

## 1. Ausgangslage

**Anforderung.** PRD-0017 FR-03 verlangt Benchmark-Jobs mindestens auf Linux: Ergebnisse als Trend, und eine Regression über 10 % bricht den Lauf. Plan 0002 zieht das in WP6 zusammen:

- **WP6.1** ist der Spike: identischer Bench je 10× auf den Runnern, Variationskoeffizient der Wanduhr-Mediane gegen die Instruktionszählung, danach ein ADR zur Benchmark-Strategie.
- **WP6.2** baut das Gate: Warnmodus ab M1, scharf spätestens M2, Selbsttest-Job mit `GRIMOIRE_BENCH_INJECT_REGRESSION=1`.

R10 benennt die Gefahr: Fehlalarme führen dazu, dass das Gate abgeschaltet wird. R21 und OP-2 betreffen das Minutenkontingent. P-12 regelt die Trendablage und den Rückfall.

**Zwei verschiedene Fragen, die der Plan an „das Gate“ hängt.** Sie müssen getrennt beantwortet werden (siehe §4.4):

1. **Relative Regression:** Ist der Kandidat mehr als 10 % schlechter als die akzeptierte Basis? (PRD-0017 FR-03, WP6.2)
2. **Absolutes Budget:** Hält z. B. die Kollision ≤ 1,5 ms pro Tick? (WP6.5 „im Regressions-Gate“, WP6.7, PRD-0002)

**Was die Engine heute an „P0-Benches“ hat.** Ein eigenes Bench-Crate gibt es noch nicht; `grimoire_bench` entsteht erst in WP6.2. Als Bench-Grundlage taugen drei vorhandene P0-Stellen:

| P0-Quelle | Inhalt | Eignung |
|---|---|---|
| `crates/grimoire_ecs/tests/timing.rs` (`#[ignore]`, manuell) | Query über 10.000 Entities mit `(&mut Pos, &Vel)` (schreibend) und `(&Pos, &Vel)` (lesend), je 2.000 Runden; dazu die Referenz `Vec<(Pos, Vel)>` | kurzer, rechenlastiger Kern ohne Allokationen; die Referenzschleife misst nur das Runner-Rauschen |
| `crates/grimoire_sim/tests/determinism.rs` | Demo-Sim mit 2.000–3.000 Entities, Spawner/Despawner, Befehlspuffer, `SimRng`, skriptierten Eingaben; 10.000 Ticks; Snapshot bei Tick 4.000; goldener Endhash | realistischer „Sim-Step“ mit Allokationen und Strukturänderungen |
| `crates/grimoire/examples/sim_loop.rs` | 5.000 Entities auf Spiralen, 60 Hz, mit Fenster | nur optional und nur die Sim-Hälfte; kein Fenster |

**Randbedingungen der Runner.**

- **Hardware:** Seit der Veröffentlichung (2026-09-15) laufen die Jobs auf den Runnern öffentlicher Repos: `ubuntu-latest` und `windows-latest` mit 4 vCPUs und 16 GB, `macos-latest` mit 3 Kernen M1 (arm64) und 7 GB. Private Repos bekämen unter Linux und Windows nur 2 vCPUs mit 8 GB. `ubuntu-latest` entspricht Ubuntu 24.04; `ubuntu-26.04` ist als Public Preview gelistet [Q1]. Ein späterer Wechsel von `ubuntu-latest` tauscht glibc und das Valgrind-Paket aus. Windows- und Ubuntu-Runner laufen in Azure [Q1]. Der Pool mischt CPU-Modelle; ein Bericht nennt AMD EPYC 7763 (nur AVX2), Intel Xeon Platinum 8573C und AMD EPYC 9V45 (AVX-512) [Q37].
- **Toolchain:** Die Engine pinnt Rust `1.98.1`.
- **Trigger:** Die Engine-CI (`ci.yml`) startet nur bei Pushes auf `main`, bei PRs und bei `workflow_dispatch`. `workflow_dispatch` greift nur, wenn die Workflow-Datei auf dem Standard-Branch liegt. `push`-Workflows laufen dagegen auch von nicht gemergten Branches [Q33]. Der Spike-Workflow bekommt deshalb einen eigenen `push`-Trigger auf seinen Branch und löst `ci.yml` nicht aus.

## 2. Kandidaten

Minutenangaben: „Linux-Minuten“ zählen einfach. Für Windows und macOS gelten laut Aufgabenstellung und Drittquellen die Faktoren ×2 und ×10 gegen das Inklusivkontingent [Q15]. Die offizielle Abrechnungsseite nennt keine Faktoren [Q14]. Sie führt Minutenpreise: Linux (2 Kerne) 0,006 $, Windows 0,010 $, macOS 0,062 $ [Q14][Q30], nach einer Preissenkung zum 1. Januar 2026 [Q36]. Das Abrechnungs-Dashboard kann die Nutzung als Dollarbetrag zeigen [Q14]. Das Preisverhältnis beträgt damit ≈ 1,7 (Windows) und ≈ 10,3 (macOS). Wie das Inklusivkontingent Windows- und macOS-Minuten heute anrechnet, ist nicht dokumentiert. Die Faktoren ×2 und ×10 bleiben die vorsichtige Annahme. Zum Vergleich: Ein 3-OS-Engine-CI-Lauf kostet geschätzt 14–87 abrechenbare Minuten. Die Linux-Werte je Kandidat sind eigene Schätzungen für ein Crate, das nur `grimoire_core`, `grimoire_ecs` und `grimoire_sim` baut, mit warmem bzw. kaltem Cargo-Cache.

### K1 — Wanduhr-Median mit Wiederholungen gegen gespeicherte Basis

- **Misst:** verstrichene Zeit je Iteration. Je Bench gibt es Aufwärmphase, n Stichproben und daraus Median und MAD. Verglichen wird mit dem Wert eines früheren Laufs auf einer anderen VM.
- **Erwartetes Rauschen:** mehrere Prozent zwischen VMs.
  - Reichelt, Jung und van Hoorn finden für MooBench auf GitHub Actions eine Nachweisgrenze von 4,41 % bei sequentieller Last; Bare Metal kommt auf 1,94 % [Q9]. Das ist ein Anhaltspunkt, keine übertragbare Schranke für unsere Benches.
  - Eine Langzeitstudie auf AWS misst einen VK < 3,7 % für Anwendungsbenchmarks [Q10].
  - Die Criterion-FAQ warnt ausdrücklich vor dem Rauschen virtualisierter CI [Q7].
  - Die N-Thread-Benches (Engine-ADR-0006) sind auf 2 vCPUs besonders anfällig.
- **Runner:** alle drei OS.
- **Einrichtung:** gering. Eine eigene dünne Harness mit JSON-Ausgabe genügt. `Instant` braucht `#[allow(clippy::disallowed_methods)]` mit Begründung wie in `timing.rs`.
- **Minuten je Lauf:** Linux ≈ 5–8 (warm) bzw. 8–12 (kalt); Windows ×2; macOS ×10.
- **10-%-Gate:** als scharfes Gate voraussichtlich **nicht verlässlich**. Taugt für Trend und Warnung. Der Spike misst es mit.

### K2 — Criterion-Vergleich (`--save-baseline` / `--baseline`)

- **Misst:** wie K1, mit Bootstrap-Statistik. Voreinstellungen je Vergleich sind `significance_level = 0.05` und `noise_threshold = 0.01` [Q7][Q8]. Criterion 0.8.2 verlangt MSRV 1.86 und passt zu 1.98.1 [Q20].
- **Erwartetes Rauschen:** wie K1. Signifikanztests über VM-Grenzen erkennen Umgebung als „Änderung“ (Criterion-FAQ [Q7]). Die 0,05 gelten je Vergleich; sie sind nicht die Fehlalarmquote eines 10-%-Gates.
- **Runner:** alle drei OS.
- **Einrichtung:** gering bis mittel, bei größerem Abhängigkeitsbaum. Eine eigene Schwellenlogik auf den Schätzwerten unter `target/criterion` ist trotzdem nötig.
- **Minuten je Lauf:** Linux ≈ 6–10.
- **10-%-Gate:** nicht über gespeicherte Basen. Ob Criterions Statistik innerhalb eines verschränkten Jobs (K3) Vorteile gegenüber einer eigenen Harness bringt, ist **nicht untersucht**. Für den Spike genügt die eigene Harness.

### K3 — Basis und Kandidat im selben Job, verschränkt oder gleichzeitig

- **Misst:** das **Verhältnis** Kandidat/Basis auf derselben VM. Vier Varianten:
  1. **Sequentielle Prozess-Verschränkung** (eigene Harness): Quadrupel A‑B‑B‑A; Details in §3.3.
  2. **Duet (gleichzeitig):** Basis und Kandidat laufen parallel, je ein Prozess auf einer der 2 vCPUs (`taskset`), ausgewertet als Verhältnis. Das entspricht dem Verfahren, für das Bulej et al. in der Cloud eine Varianzminderung um den Faktor 2,3–12,5 (ScalaBench/DaCapo) bzw. 23,8–82,4 (SPEC CPU 2017) berichten [Q4]. Die Zahlen gelten für *gleichzeitige* Ausführung, nicht für Variante 1. Nur für einfädige Benches.
  3. **`tango-bench`:** Paired Benchmarking in einem Prozess, die Basis als dynamische Bibliothek. Das Projekt beansprucht, 1 % in 1 s in mindestens 9 von 10 Läufen zu erkennen — eine Herstellerangabe [Q5]. Läuft auf Linux, macOS und Windows.
  4. **`bench_diff`:** abwechselnde Paare, Welch-t-Test auf log-Latenzen, für µs–ms und nicht für ns [Q6]. Für Basis gegen Kandidat in einem Binary unhandlich.
- **Erwartetes Rauschen:** kleiner als K1, weil langsame Drift beide Seiten trifft; die Höhe auf privaten 2-vCPU-Runnern ist offen.
- **Runner:** alle drei OS (Duet und `taskset` nur Linux).
- **Einrichtung:** Varianten 1 und 2 ≈ 1 Tag; Variante 3 mittel bis hoch.
- **Minuten je Lauf:** Linux ≈ 10–16 (zwei Builds, doppelte Messzeit).
- **10-%-Gate:** **offen, der Spike entscheidet.** Beste Wanduhr-Option für Trend und Warnung.

### K4 — Instruktionszählung mit Valgrind über `gungraun` (vormals `iai-callgrind`)

- **Misst:** Instruktionen (`Ir`) unter Callgrind. Jeder Bench läuft nur einmal [Q2][Q3]. Callgrind und Cachegrind können zusätzlich Cache-Treffer und Sprungvorhersage **simulieren** (`--cache-sim=yes`, `--branch-sim=yes`) [Q34]. Das sind Modellwerte, keine Hardware-Zeiten.
- **Erwartetes Rauschen:** laut Projekt praktisch null, auch in virtualisierter CI [Q2] (Herstellerangabe). Rustls nutzt Cachegrind-Instruktionen aus demselben Grund [Q11]. Für unsere Benches ist das **unverifiziert**. Mögliche Restquellen:
  - CPU-abhängige Pfade in glibc und `std` (ifunc/CPUID);
  - Allokator-Verhalten;
  - Spin-Warten von Worker-Threads;
  - Build-Pfade und Debuginfo;
  - die glibc-Version des Images: Rust nutzt unter Linux standardmäßig den glibc-Allokator, und Sicherheitsupdates von `libc6` können `Ir` in `malloc` oder `memcpy` verschieben (unverifiziert).
- **CPU-Modell unter Valgrind:** Valgrind reicht die echte CPUID nicht durch. Auf AVX2-fähigen Hosts meldet es dem Programm eine feste CPU (Intel Core i7-4910MQ) und schaltet nur F16C, RDRAND, RDSEED und LZCNT je nach Host zu [Q39]. AVX-512 unterstützt Valgrind nicht [Q40]. glibc sollte seine ifunc-Pfade daher auf EPYC 7763, EPYC 9V45 und Xeon 8573C gleich wählen. Das ist aus dem Quelltext abgeleitet und im Spike zu bestätigen (§3.4 Nr. 1).
- **Grenzen:**
  - **Nur Linux.** Valgrind unterstützt Windows nicht und auf macOS nur Intel-Darwin bis 11.0, `macos-latest` ist aber arm64 [Q12].
  - **Threads werden serialisiert:** Valgrind lässt immer nur einen Thread laufen [Q13]. Benches mit N Threads liefern daher weder Skalierung noch stabile `Ir`. Gate nur für 1 Thread bzw. den sequentiellen `Executor`.
  - **`Ir` ist nicht Laufzeit:** 10 % mehr Instruktionen bedeuten nicht 10 % mehr Laufzeit (Rustls [Q11]).
  - **Valgrind-Version:** `gungraun` empfiehlt Valgrind ≥ 3.20 und verlangt ≥ 3.22 für Cachegrind [Q3]. Ubuntu 24.04 liefert 3.22.0 [Q16]; aktuell ist 3.27.1 [Q12].
  - **Rust 1.98:** DWARF-5-Debuginfo in Rust-Bibliotheken hat ältere Valgrind-Versionen gestört [Q17]. Ob 1.98.1 mit 3.22 sauber läuft, ist **unverifiziert** (Smoke-Job §3.2). Ohne Angabe versucht `setup-gungraun` zuerst vorgebaute Valgrind-Binaries aus `gungraun/valgrind-builder`, dann den Quellcode, dann den Paketmanager. `valgrind-strategy: source` erzwingt den Build aus dem Quellcode, `none` überspringt die Installation [Q18]. Vorgebaute Binaries sind Fremdartefakte: Version festschreiben und die Action per SHA pinnen.
  - **Debug-Symbole:** Pflicht (`debug = true` im Bench-Profil [Q3]). Vorschlag: eigenes Profil, das von `release` erbt, damit das Release-Profil der Determinismus-Gates unberührt bleibt.
  - **Versionskopplung:** `gungraun-runner` muss dieselbe Version wie die Bibliothek haben, sonst bricht der Lauf ab [Q18]. `setup-gungraun` erkennt die passende Runner-Version standardmäßig selbst (`runner-version: auto`) [Q18]; bei eigener Installation ist sie festzuschreiben.
  - **MSRV:** `gungraun` 0.19.4 verlangt Rust 1.85.1 und passt zu 1.98.1 [Q41].
- **Einrichtung:** mittel. Aufwand: Workspace-Abhängigkeit nur für `grimoire_bench` mit Begründung im Commit (Vertrag §2 Regel 4), Valgrind-Installation, Runner-Pinning, Bench-Profil. `gungraun` kennt eigene Grenzen (`--callgrind-limits='ir=10%'`, Regression als Fehler mit Exitcode 3 [Q19]). Vorgesehen ist trotzdem ein eigener Vergleicher über die JSON-Daten, weil Basisverwaltung und Exitcodes selbst festgelegt werden (§4.3).
- **Variante Cachegrind:** `gungraun` kann statt Callgrind auch Cachegrind nutzen (Valgrind ≥ 3.22 [Q3]). Cachegrind simuliert Cache und Sprünge standardmäßig nicht; mit `--instr-at-start=no` und Client-Requests misst es nur einen Ausschnitt [Q38]. Ob das die Laufzeit merklich senkt, ist nicht untersucht. Der Spike bleibt bei Callgrind, weil die Messzeit unter Valgrind nicht der Engpass ist (§3.2).
- **Minuten je Lauf:** Linux ≈ 6–12 mit apt- oder vorgebautem Valgrind (+ 5–10 für Valgrind aus dem Quellcode ohne Cache); mit Basis-Build im Job ≈ 10–18.
- **10-%-Gate:** **ja, erwartet** — der beste Kandidat für ein scharfes Gate auf **relative** Regressionen unter Linux.

### K5 — Hardware-Zähler über `perf stat` (`instructions:u`, `cycles:u`)

- **Misst:** echte PMU-Zähler, nativ.
- **Runner:**
  - **Belegt ist ein Einzelfall:** `perf_event_open failed: No such file or directory` auf einer „fully virtualized Microsoft Azure AMD EPYC 7763 VM“ trotz `perf_event_paranoid=-1`, berichtet am 2026-09-04 [Q21].
  - Die Meldung [Q22] betrifft nur Energie-Ereignisse (`power/`), nicht `instructions:u`.
  - Ob *alle* gehosteten Linux-Runner-Klassen keine Hardware-Zähler bieten, ist **nicht belegt**. Der Spike prüft es je Job und schreibt die Aussage nur für die beobachteten CPU-Modelle fest.
  - macOS und Windows scheiden aus.
- **Erwartetes Rauschen:** auf eigener Hardware gering (unverifiziert). Auch dort bleibt die Lücke zwischen Instruktionen und Laufzeit.
- **Einrichtung:** gering.
- **Minuten je Lauf:** Probe < 2 Min.
- **10-%-Gate:** auf gehosteten Runnern voraussichtlich nicht. Kandidat im **P-12-Rückfall „eigener Server“** (§6.2).

### K6 — `divan` als Wanduhr-Harness

- **Misst:** fastest, slowest, median, mean; dazu ein `AllocProfiler`. Version 0.1.21, MSRV 1.80 [Q23].
- **Vergleich:** Die gelesene Dokumentation beschreibt keinen eingebauten Basisvergleich. Für ein Gate gilt deshalb dasselbe wie für K1 bzw. K3.
- **Einrichtung:** gering.
- **10-%-Gate:** nur so gut wie K1/K3; Divan ist eine Harness-Alternative, keine eigene Metrik.

### K7 — Externe Dienste (nur zur Information, nicht Teil von P-12)

- **CodSpeed** bietet CPU-Simulation unter Valgrind und Wanduhr-Messung. Der Free-Tarif ist für private Repos bis 5 Nutzer frei und enthält laut Preisseite 600 Minuten im Monat auf Bare-Metal-„Macro Runners“ [Q24]. Eine Beschränkung der Macro Runners auf Organisationen nennen die heute gelesenen Seiten nicht; ob sie für ein persönliches Konto nutzbar sind, ist **unverifiziert**.
- **Bencher** bringt Schwellenmodelle (Prozent, z-Score, t-Test, IQR, Delta-IQR) und „Relative Continuous Benchmarking“ [Q25][Q26].
- **Drittanbieter-Runner** (z. B. Blacksmith, Namespace, RunsOn, WarpBuild) bieten gehostete Runner außerhalb von GitHub. Ob sie dedizierte Kerne und weniger Rauschen liefern, ist **nicht untersucht**. Sie brächten Engine-Code auf fremde Maschinen.

Alle drei bringen Code oder Messdaten des privaten Engine-Repos zu Drittanbietern und brauchen neue Konten und OAuth-Rechte. Das ist eine PO-Frage und wird **nicht empfohlen**.

### Übersicht

| Kandidat | Metrik | Erwartetes Rauschen (Runner) | OS | Einrichtung | Linux-Minuten je Lauf (Schätzung) | Scharfes 10-%-Gate |
|---|---|---|---|---|---|---|
| K1 Wanduhr-Median, gespeicherte Basis | Zeit | einige % zwischen VMs | 3 | gering | 5–12 | voraussichtlich nein |
| K2 Criterion-Vergleich | Zeit + Bootstrap | wie K1 | 3 | gering–mittel | 6–10 | nein (gespeicherte Basis) |
| K3 A/B im selben Job | Zeitverhältnis | kleiner als K1, Höhe offen | 3 (Duet: Linux) | mittel | 10–16 | offen |
| K4 `gungraun` / Callgrind | `Ir` (+ simulierte Cache-/Sprungwerte) | ≈ 0 erwartet, Restquellen offen | nur Linux | mittel | 6–12 (Basis im Job: 10–18) | **ja, erwartet** (relativ) |
| K5 `perf stat` | PMU-Zähler | im belegten Fall keine PMU | Linux | gering | Probe < 2 | voraussichtlich nein (nur Self-Hosted) |
| K6 Divan | Zeit | wie K1 | 3 | gering | 5–12 | wie K1/K3 |
| K7 CodSpeed/Bencher/Drittanbieter-Runner | Zeit/`Ir` | dienstabhängig | — | Konto nötig | — | PO-Frage |

## 3. Versuchsprotokoll WP6.1 (Vorschlag)

Der Spike ist eine **Pilot-Qualifikation**: Er zeigt, ob eine Metrik taugt und wie das Gate zu bauen ist. Mit 10 Wiederholungen beweist er keine Fehlalarm- oder Erkennungsquote. Die Bestätigung liefert der Warnmodus in WP6.2 (§4.5).

### 3.0 Voraussetzungen und Abbruchregeln

1. **OP-2:** geschlossen (2026-09-15, Repos öffentlich). Gehostete Standard-Runner verbrauchen keine Actions-Minuten; vor dem ersten Lauf ist keine Kontingentangabe mehr nötig.
2. **Ort:** Wegwerf-Code auf einem eigenen Engine-Branch `spike/of-17.3-bench-noise` in eigenem Worktree. Er berührt nie den Worktree `p1-scheduler` und nie `crate-vertraege.md`.
   - Das Spike-Crate liegt unter `spikes/of-17.3/` als **eigener Mini-Workspace** mit Pfadabhängigkeiten auf `grimoire_core`, `grimoire_ecs` und `grimoire_sim` (Stand `v0.1.0`).
   - `Cargo.lock` und `[workspace.dependencies]` der Engine bleiben unberührt. `gungraun` kommt erst in WP6.2 nach Vertrag §2 Regel 4 in `grimoire_bench`.
3. **Trigger:** Workflow `.github/workflows/spike-of-17.3.yml` mit `on: push: branches: [spike/of-17.3-bench-noise]` und `paths: [spikes/of-17.3/**, .github/workflows/spike-of-17.3.yml]`. Kein PR, kein Merge.
   - Die zwei Messblöcke (§3.2) sind **zwei getrennte Pushes** an verschiedenen Tagen und Tageszeiten.
   - Die Blocknummer steht in einer Datei `spikes/of-17.3/block.txt`, damit Harness und Benchparameter zwischen den Blöcken byte-gleich bleiben.
4. **Lokal vorher (0 Minuten):**
   - Harness, Vergleicher und Auswerteskript bauen;
   - Wanduhr-Teil einmal unter Windows als Funktionsprobe laufen lassen, nur CPU und ohne Fenster;
   - Unit-Tests des Vergleichers;
   - `cargo clippy` für Linux;
   - **Kalibrierung der Einspeisung festschreiben**, bevor gemessen wird (§3.1).
   - Valgrind-Teile lassen sich lokal nur unter Linux prüfen. Ob WSL dafür genutzt wird, entscheidet der Tagbetrieb.
5. **Laufzeitschutz:**
   - eigener Smoke-Job (§3.2), von dem die Matrix per `needs` abhängt;
   - `timeout-minutes: 45` je Job und `timeout-minutes` je Messschritt (Richtwerte §3.2); die teuren Wanduhr-Schritte laufen zuletzt, damit ein Zeitlimit die `Ir`-Daten nicht mitreißt;
   - Upload der Rohdaten mit `if: always()`;
   - `fail-fast: true` für Messumgebungsfehler.
   - Dauern die ersten beiden Wiederholungen je > 35 Minuten → Block anhalten, die Stichproben von K3 kürzen und neu pushen.
   - Jeder Lauf wird bis zum Ende überwacht (`gh run watch --exit-status`); rote Läufe werden mit `gh run view --log-failed` analysiert und die Ursache benannt (Code, Vorrichtung, fremd).

### 3.1 Benches und Einspeisung

| ID | Quelle | Messbereich | Wanduhr | `Ir` |
|---|---|---|---|---|
| B0 `raw_vec_10k` | Referenzschleife aus `timing.rs` | 10.000 × `pos += vel` auf `Vec<(Pos, Vel)>` | 2.000 Runden je Stichprobe | 100 Runden |
| B1 `ecs_query_10k_write` | `timing.rs` | `query_mut::<(&mut Pos, &Vel)>` über 10.000 Entities | 2.000 Runden je Stichprobe | 100 Runden |
| B2 `ecs_query_10k_read` | `timing.rs` | `query::<(&Pos, &Vel)>` mit Summe über `black_box` | 2.000 Runden je Stichprobe | 100 Runden |
| B3 `sim_demo_600` | Demo-Sim aus `determinism.rs` | 600 Ticks; **vor jeder Wiederholung** wird der Zustand aus einem Snapshot bei Tick 4.000 wiederhergestellt (außerhalb des Messbereichs) | 10 Wiederholungen je Stichprobe | 1 Durchlauf |

**Rolle der Benches.** B0 misst nur Runner und Compiler (Rauschreferenz). Rauschen durch Allokation, Speicherzugriffe oder Planung quantifiziert B0 nicht; dafür steht B3. Alle Benches laufen mit einem Thread (`v0.1.0`, sequentieller Scheduler). Die N-Thread-Benches nach Engine-ADR-0006 kommen in WP6.2 hinzu.

**Gleiche Arbeit.** Jeder Bench gibt ein Ergebnis über `black_box` aus (Summe bzw. Zustands-Hash), damit nichts wegoptimiert wird. Der Endhash von B3 wird außerhalb des Messbereichs gegen einen festen Wert geprüft. Er sichert nur die *Ausgabe*, nicht die ausgeführte Arbeit; die Arbeitsmenge prüft die `Ir`-Messung selbst.

**Eingespeiste Regressionen** (nur im Spike-Crate, nie in Engine- oder Determinismus-Crates), gesteuert über `GRIMOIRE_BENCH_INJECT_REGRESSION=<prozent>`:

- **+5, +12, +15 und +20 % nominell:** zusätzliche ganze Runden derselben Arbeit innerhalb des Messbereichs (bei 100 Runden 5, 12, 15 bzw. 20 Runden).
  - Bei B3 ist es ein zusätzlicher **lesender** Query-Durchlauf über eine feste Entity-Teilmenge pro Tick, der den Zustand nicht ändert (Hash bleibt gleich).
  - Der Anteil wird lokal so kalibriert, dass `Ir` um den Nennwert steigt, und vor dem ersten CI-Lauf festgeschrieben.
  - +12 % liegt knapp über der Schwelle; das zeigt das Verhalten nahe 10 %.
- **„Cache-feindlich“ (nur B1):** Zugriffe über eine fest gemischte Indexpermutation. Wie sich `Ir` und Wanduhr dabei ändern, ist ein **Messergebnis**, keine Annahme. Erwartet wird: `Ir` ändert sich wenig, die simulierten Cache-Fehlzugriffe und die Wanduhr deutlich.

**Echter Zwei-Commit-Vergleich.** Auf dem Spike-Branch liegen zwei vorbereitete Commits: C1 als Basis und C2 mit einer +15-%-Änderung im Spike-Code *ohne* Laufzeit-Variable. In den Wiederholungen 1 und 6 wird der Produktionspfad geprobt:

1. `git worktree add` für C1 und C2;
2. getrennte `target`-Verzeichnisse, beide gebaut und gemessen;
3. JSON-Extraktion;
4. Vergleicher mit Exitcode.

Als Kontrolle wird **derselbe** Commit ein zweites Mal in einem anderen Verzeichnis unabhängig gebaut und gemessen: Er muss dieselben `Ir` liefern, sonst beeinflussen Build-Pfade das Ergebnis.

### 3.2 Aufbau der Läufe

**Smoke-Job** (einmal je Push, ≈ 5 Min): Fingerabdruck erfassen, Valgrind und `gungraun-runner` installieren, B0 unter Callgrind einmal ausführen, `perf`-Probe. Scheitert Callgrind, endet der Lauf mit „Messumgebung defekt“; die Matrix startet nicht.

**Messblöcke:** zwei Pushes, je Matrix `rep: [1..5]` bzw. `[6..10]`, `max-parallel: 1`, auf `ubuntu-24.04`: fest statt `ubuntu-latest`, damit kein Image-Wechsel in die Messblöcke fällt. Jeder Wiederholungsjob, in dieser Reihenfolge:

1. **Fingerabdruck** als JSON: `lscpu` (Modellname, Flags), `nproc`, `uname -r`, `ImageOS`/`ImageVersion` (ob gesetzt, unverifiziert), glibc-Version (`ldd --version`), die von Valgrind erkannten Host-Fähigkeiten (`hwcaps`-Zeile aus `valgrind -v`), `rustc -Vv`, `valgrind --version`, `gungraun-runner --version`, `RUSTFLAGS`, `.cargo/config.toml`-Hash, Profil- und Feature-Liste, Benchparameter (Runden, Ticks, Stichproben), Hash des Spike-Crates.
2. **Build** im Release- und im Bench-Profil mit Debug-Symbolen; `Swatinem/rust-cache` per SHA gepinnt wie in `ci.yml`.
3. **Reihenfolge der Varianten** (0, +5, +12, +15, +20, cache-feindlich) je Job per fest geseedeter Permutation mit der Wiederholungsnummer als Seed. So vermischt sich keine Variante systematisch mit Tageszeit oder Job-Phase.
4. **K4 `Ir`:** `gungraun` auf B0–B3 je Variante, plus simulierte Cache-/Sprungwerte für B1. Richtwert ≤ 5 Min.
5. **Nur Wiederholungen 1 und 6:** Zwei-Commit-Probe und unabhängiger Doppel-Build (§3.1). Richtwert zusätzlich 3–6 Min.
6. **`perf`-Probe (`continue-on-error`, ≤ 2 Min):** Installation, `perf_event_paranoid`, `perf list`, `perf stat -e instructions:u,cycles:u` auf B0. Protokolliert werden Ergebnis oder Fehlermeldung je CPU-Modell.
7. **K1 Wanduhr:** je Bench und Variante 3 s Aufwärmen, 30 Stichproben, Rohwerte gespeichert. Richtwert ≈ 2–3 Min.
8. **K3 Duet:** A und B gleichzeitig mit `taskset -c 0` bzw. `-c 1`, 10 Durchgänge mit je 10 Stichproben, bei jedem zweiten Durchgang Kerne getauscht; nur die Wanduhr-Variantenmenge (unten). Richtwert ≈ 2–4 Min.
9. **K3 sequentiell:** zwei byte-gleiche Binary-Kopien A und B, nur die Wanduhr-Variantenmenge. 10 Quadrupel A‑B‑B‑A; jeder Aufruf wärmt 0,3 s auf, misst 10 Stichproben und meldet deren Median (Prozessstart außerhalb der Messung). Richtwert ≈ 7–13 Min.
10. **Upload** aller JSON- und Rohdaten (`if: always()`), Aufbewahrung 30 Tage.

**Wanduhr-Variantenmenge (K3).** K3 misst nur 0 (A/A), +5 %, +20 % und die cache-feindliche Variante von B1, also 13 statt 21 Bench-Varianten-Kombinationen. Damit erreicht K3 im Spike höchstens „Warn-fähig“ (§3.5). Das genügt der Rolle der Wanduhr in §4.4. K1 misst alle Varianten, weil es billig ist.

**Grundlage der Richtwerte.** Lokale Zeitprobe am 2026-09-15 auf dem Entwicklerrechner (nativ, Release-Profil, keine Runner-Messung):

- `timing.rs`: 0,22 / 1,04 / 0,87 ns je Entity (Referenz / schreibend / lesend), also ≈ 4 / 21 / 17 ms je Stichprobe aus 2.000 Runden;
- `determinism.rs`: sechs Tests mit mehreren 10.000-Tick-Läufen in 0,41 s, also höchstens ≈ 20 µs je Tick und ≈ 0,1 s je B3-Stichprobe;
- kalter Build von `grimoire_ecs` und `grimoire_sim` samt Tests: 10 s mit allen Threads des Entwicklerrechners.

Für den 2-vCPU-Runner angesetzt: Faktor 2–3 auf Messzeiten, Faktor ≈ 8 auf Builds. Der ursprüngliche Plan hätte K3 sequentiell auf alle 21 Kombinationen mit 1 s Aufwärmen je Aufruf angewandt. Allein dieser Schritt hätte ≈ 21–31 Min gebraucht und das Job-Limit von 30 Min gesprengt. Unter Callgrind sind die Benches dagegen kurz (B3 nativ ≈ 6–12 ms für 600 Ticks); die Messzeit unter Valgrind ist nicht der Engpass.

Die Auswertung läuft lokal über `gh run download` und das Auswerteskript und kostet keine Minuten.

**Minutenbudget (Schätzung):** Ein Wiederholungsjob kostet ≈ 17–34 Min: Einrichtung (Checkout, Toolchain, Cache, Valgrind, Runner) 2–4, Build 1–2 (kalt 3–6), dann die Richtwerte der Schritte 4–10. Dazu kommen die Wiederholungen 1 und 6 mit je 3–6 Min für die Doppel-Builds, die kalten ersten Jobs je Block und 2 Smoke-Jobs ≈ 10. Zusammen ≈ **190–370 abrechenbare Linux-Minuten**. Der größte Hebel ist K3 sequentiell (≈ 7–13 Min je Job). Unter GitHub Free mit 2.000 Inklusivminuten wären das 9,5–18,5 % des Monats [Q14]; der Tarif des PO ist nicht bestätigt (OP-1/OP-2). Windows und macOS sind **nicht** Teil des Spikes (R21):

- 3 Windows-Wiederholungen nur mit K1 und K3 sequentiell (je ≈ 15–29 Min): ≈ 90–175 abrechenbare Minuten mit Faktor ×2;
- 3 macOS-Wiederholungen (je ≈ 12–20 Min): ≈ 360–600 mit Faktor ×10.

Ob sie nachgeholt werden, entscheidet sich nach den Linux-Ergebnissen.

### 3.3 Statistiken

Je Bench *b* und Metrik *m* entsteht ein Jobwert (j = 1…10):

- **K1:** *v_j* = Median der 30 Stichproben; dazu die Streuung im Job als MAD/Median.
- **K3 sequentiell:** je Quadrupel *q* = (t_B1 + t_B2) / (t_A1 + t_A2); *r_j* = Median der 10 *q*.
- **K3 Duet:** *r_j* = Median der 10 Verhältnisse t_B / t_A.
- **K4:** *v_j* = `Ir`.

Alle Abweichungen werden **symmetrisch als Log-Verhältnis** angegeben: d = |ln(x / y)|. Damit wirken +10 % und −9,1 % gleich. Die Umrechnung auf Prozent ist e^d − 1.

1. **Streuung über Jobs:** robuster VK = 1,4826 · MAD(v) / Median(v), zusätzlich klassischer VK und Spannweite (max − min) / Median. Der Faktor 1,4826 macht die MAD bei Normalverteilung mit der Standardabweichung vergleichbar; er ist keine Konfidenzschranke. Ist MAD = 0 und die Spannweite > 0, zählt die Spannweite.
2. **Rauschband B:**
   - *gespeicherte Basis* (K1, K4): B = max d über alle 45 Jobpaare, zusätzlich getrennt nach gleichem und verschiedenem CPU-Modell. Die 45 Paare sind **keine 45 unabhängigen Versuche**; sie beschreiben nur die 10 Jobwerte.
   - *im selben Job* (K3, K4 mit Basis im Job): B = max_j d(r_j, 1) aus den A/A-Läufen.
3. **Erkennung nahe der Schwelle:** Für +12 %, +15 % und +20 % der Anteil der Jobs über der Schwelle; für +5 % der Anteil darunter (K3 nur +5 % und +20 %, §3.2). Bei 10 von 10 Treffern liegt die einseitige 95-%-Untergrenze der Erkennungswahrscheinlichkeit nur bei ≈ 74 % (0,05^(1/10)). Das ist ein Pilotwert.
4. **Worst-Case-Maskierung:** Aus B folgt die kleinste Regression, die im ungünstigsten Fall noch unter der Schwelle bleibt: 1,10 · e^B − 1. Beispiel B = 3,3 % → eine Regression von bis zu ≈ 13,7 % kann durchrutschen. Das wird im ADR offen ausgewiesen.
5. **Blinder Fleck:** Effekt der cache-feindlichen Variante in `Ir`, simulierten Cache-Fehlzugriffen und Wanduhr (K3).
6. **Produktionspfad:** Ergebnis der Zwei-Commit-Probe (Exitcode, erkannte Benches) und Gleichheit der `Ir` beim Doppel-Build.

### 3.4 Was der Spike beantworten muss

1. Ist B für `Ir` über alle Jobpaare ≈ 0, auch über CPU-Modelle hinweg (erwartet wegen der festen Valgrind-CPUID, §2 K4)? Dann ist eine gespeicherte Basis bei gleichem Umgebungs-Fingerabdruck zulässig (billig), sonst Basis im Job.
2. Liefert der unabhängige Doppel-Build dieselben `Ir`? Funktioniert der Zwei-Commit-Pfad?
3. Wie groß ist B für K3 sequentiell und Duet gegenüber K1? Trägt eine davon eine Warnung bei 10 %?
4. Funktioniert Valgrind mit Rust 1.98.1, und in welcher Bezugsart (vorgebaut über `setup-gungraun`, 3.22 aus apt oder aus dem Quellcode) mit welcher festgeschriebenen Version?
5. Liefert `perf` auf den beobachteten Runner-CPU-Modellen Hardware-Zähler?
6. Wie viele Linux-Minuten kostet ein Gate-Lauf tatsächlich (OP-5, R21)?

### 3.5 Entscheidungsverfahren

| Ergebnis für eine Metrik | Bedingung | Folge |
|---|---|---|
| **Gate-fähig (Pilot)** | B ≤ 1 % (bei `Ir` erwartet); kein A/A-Wert über der Schwelle; +12 %, +15 % und +20 % in 10/10 erkannt; +5 % in 10/10 darunter; Zwei-Commit-Probe korrekt; Doppel-Build gleich | Gate im Warnmodus starten, scharf nach §4.5 |
| **Gate-fähig mit ausgewiesener Unschärfe** | 1 % < B ≤ 3,3 %; sonst wie oben, aber +12 % darf fehlen | wie oben; ADR nennt die Maskierungsgrenze (§3.3 Nr. 4); PO-Hinweis |
| **Warn-fähig** | B ≤ 10 % und +20 % in ≥ 8/10 erkannt | nur Annotation und Trend |
| **Nur Trend** | sonst | nur Trendablage |
| **Nicht qualifiziert trotz kleinem B** | +5 % reißt die Schwelle, +15/+20 % werden verfehlt, Zwei-Commit-Probe falsch oder Doppel-Build ungleich | Ursache beheben (Einspeisung, Harness, Build-Pfade) und **nur die betroffenen Wiederholungen** wiederholen; bleibt es so → wie „Nur Trend“ |
| **Nicht aussagekräftig** | Messumgebung wiederholt defekt oder weniger als 8 auswertbare Wiederholungen | fehlende Wiederholungen nachholen; ist das Kontingent erschöpft → Gate bleibt im Warnmodus, P-12-Rückfall wird an M2 vorgelegt |

Erreicht **keine** Metrik „Gate-fähig“, greift der P-12-Rückfall (§6.2).

## 4. Empfohlene Gate-Metrik und Regeln (vorläufig, PO-Bestätigung ausstehend)

### 4.1 Metrik und Umfang

**Metrik:** Callgrind-Instruktionen (`Ir`) über `gungraun` auf einem fest benannten Image (`ubuntu-24.04`; ein Wechsel ist eine bewusste Änderung mit neuer Basis per `accept`), nur für einfädige Benches. Voraussetzung: „Gate-fähig“ im Spike.

**Inventar:**

- WP6.2: die P0-Benches B1–B3;
- ab M2: Interpreter-, Extraktions- und **Licht**-Benches, wie im M2-Kriterium von Plan 0002 genannt;
- ab WP6.5: Kollision mit sequentiellem `Executor`.

N-Thread-Benches und alle Budgetaussagen laufen über die Wanduhr (§4.4).

### 4.2 Akzeptierte Basis statt „letzter Push“

Auf `main` fehlt Branch-Schutz. Ein roter Push landet trotzdem auf `main`. Würde der nächste Push gegen seinen Vorgänger vergleichen, wäre die Regression „normalisiert“. Deshalb:

- Die Trendablage (§6.1) trennt **Messhistorie** (jede Messung mit Status) und **akzeptierte Basis** (je Bench der zuletzt akzeptierte Wert mit Commit-SHA).
- Verglichen wird der Kandidat (`github.sha`) immer mit der **akzeptierten Basis**, nie mit `github.event.before`. `before` ist nur der vorherige Branch-Stand; bei Pushes mit mehreren Commits wird das Ergebnis dem letzten Commit zugeordnet.
- **Beförderung:** Die Basis rückt nur vor, wenn das **Urteil** des Gate-Laufs grün ist (Vergleicher-Exitcode 0, Messung vollständig), oder durch einen **bewussten, protokollierten Ein-Kommando-Akt** (z. B. `grimoire_bench accept <sha> --reason "..."`, im Datenzweig als Eintrag mit Begründung). Das folgt PRD-0018 („bewusster, geloggter Akt, nie still“). Im Warnmodus ist der Job immer grün; befördert wird trotzdem nur bei Urteil 0, sonst würde der Warnmodus Regressionen normalisieren.
- **Sonderfälle:**
  - rote oder unvollständige Messungen werden gespeichert, aber nie befördert;
  - bei einem Force-Push auf `main` (laut CONTRIBUTING ohnehin ausgeschlossen) und beim allerersten Lauf gibt es keine Basis → Messung ohne Urteil, Beförderung nur per `accept`;
  - manuelle Läufe messen, befördern aber nicht.
- **Schleichende Verschlechterung:** Zwei aufeinanderfolgende +6 % würden je einzeln passieren, weil die Basis nach dem ersten grünen Lauf vorrückt. Dagegen wird zusätzlich gegen die Basis des letzten Alpha-Tags verglichen: kumuliert > 10 % → Warnung; an Meilensteinen im Budget-Abgleich (WP6.7) zu begründen oder zu beheben. Die Warnung soll nicht bis zum nächsten Tag in jedem Lauf wiederkehren und abstumpfen (R10). Deshalb erscheint sie als Annotation nur beim ersten Überschreiten je Bench und danach als Zeile im Job-Summary. Ein `accept --drift <bench> --reason "..."` quittiert sie mit Begründung und setzt den Drift-Bezug neu.

### 4.3 Vergleich, Fingerabdruck, Schwelle, Exitcodes

**Ort der Basismessung.**

- **Umgebungs-Fingerabdruck:** Valgrind- und `gungraun`-Version, Image-Name (`ubuntu-24.04`), glibc-Version und die von Valgrind erkannten Host-Fähigkeiten (`hwcaps`). Stimmt er mit dem der akzeptierten Basis überein, und hat der Spike B ≈ 0 für diese Konstellation gezeigt, wird gegen den gespeicherten Wert verglichen.
- **Nur protokolliert, nicht abgeglichen:** `ImageVersion` und CPU-Modell. Die Image-Version wechselt mit jeder Image-Aktualisierung (etwa wöchentlich, unverifiziert), und der Pool mischt CPU-Modelle [Q37]. Stünden beide im Abgleich, fiele das Gate zufällig mal auf die gespeicherte Basis, mal auf die Basis im Job: schwankende Kosten und zwei Codepfade. Zeigt der Spike eine Abhängigkeit vom CPU-Modell, kommt es in den Abgleich, oder die Basis wird immer im Job gemessen.
- Andernfalls wird der Basis-Commit im selben Job in eigenem Worktree gebaut und gemessen (in §3.1 geprobter Pfad).
- **Code-seitige Einflüsse** gehören zum Commit, nicht zum Fingerabdruck: Toolchain (`rust-toolchain.toml`), `RUSTFLAGS`, `.cargo/config.toml`, Profile, Features, Benchparameter. Basis und Kandidat werden jeweils mit **ihrer eigenen** Toolchain gebaut. Ein Toolchain-Wechsel ist damit eine messbare Änderung und wird nicht versteckt. Weichen die *Benchparameter* ab (Runden, Ticks), ist ein Vergleich unzulässig → Messung ohne Urteil, neue Basis nur per `accept`.
- Auch gleiche Fingerabdrücke garantieren keine Fehlalarmfreiheit; sie senken nur die bekannten Störquellen.

**Schwelle:**

1. **Rot:** Für mindestens einen Gate-Bench gilt `Ir_Kandidat / Ir_Basis > 1,10`, ganzzahlig geprüft als `10 · Ir_Kandidat > 11 · Ir_Basis` (128 Bit), damit die Grenzfälle in §5 nicht an Gleitkomma-Rundung hängen. Die Schwelle ist durch PRD-0017 FR-03 fest. Das ADR weist aus, bis zu welcher Regression das Gate im ungünstigsten Fall blind ist (§3.3 Nr. 4).
2. **Warnung** (Job grün, Annotation im Job-Summary): `Ir_Kandidat / Ir_Basis > 1 + w` mit **w = 3 %** bei B ≤ 1 %, sonst w = min(3 · B, 9 %). B und w sind Konstanten aus dem ADR bzw. der Gate-Konfiguration und werden nicht aus laufenden Messungen nachgeführt, sonst verschöbe jede Messung die Warnschwelle. Eine Änderung ist ein protokollierter Akt wie `accept`.
3. **Verbesserung** > 10 %: Hinweis; die Basis rückt nur über einen grünen Lauf nach.

**Exitcodes des Vergleichers** (eigenes Kommando, z. B. `grimoire_bench compare`). Das Jobsignal ist allein sein Exitcode, nicht der von `cargo bench`, das Fehlercodes eigener Art liefert:

- `0` — keine Regression (Warnungen möglich);
- `3` — Regression;
- `2` — Messfehler: fehlender Bench, Wert 0 oder NaN, Messumgebung defekt, abweichende Benchparameter, Einspeisungs-Flag in Basis oder Kandidat außerhalb des Selbsttests.

Exitcode 2 ist kein Regressionsbefund. Er wird wie jeder rote Lauf analysiert (Ursache Code, Vorrichtung oder fremd), einmal neu gestartet und im Umsetzungsstand vermerkt. Wiederholt er sich fremdbedingt, gehört die Frage „soll der Job das aushalten?“ ins ADR.

**Pfadfilter** des Gate-Jobs: alles, was die Messung beeinflusst — `crates/**`, `Cargo.toml`, `Cargo.lock`, `rust-toolchain.toml`, `.cargo/**`, der Gate-Workflow selbst, Bench-Crate, Vergleicher, Fixtures. Nur Doku-Pfade werden ausgenommen. Eine übersprungene Messung wird nachgeholt: Der nächste Lauf vergleicht ohnehin gegen die akzeptierte Basis, nicht gegen den Vorgänger.

### 4.4 Relative Regression gegenüber absolutem Budget

- **`Ir`-Gate:** fängt *relative* Mehrarbeit in einfädigem Code. Cache-, Sprung- und SIMD-Effekte sieht es nur als simulierte Werte und Parallelisierungsverluste gar nicht.
- **Wanduhr-Trend (K3, nightly, Linux):** dieselben Benches plus alle N-Thread-Benches und die Budget-Szenarien (WP6.5 Kollision ≤ 1,5 ms, WP6.6 „Vollvorhang“). Stuft der Spike K3 als warn-fähig ein, gibt es eine Warnung ab > 10 % gegenüber der akzeptierten Wanduhr-Basis.
- **Absolute Budgets** (ms pro Tick) sind auf geteilten gehosteten Runnern (in öffentlichen Repos 4 vCPUs) kein verlässliches hartes Gate. Sie werden als Trend mit Budgetlinie geführt und laut WP6.7 mit dem Faktor aus Messsitzung 1 auf Referenz-Hardware umgerechnet.
- **Plan-Konflikt:** WP6.5 formuliert „≤ 1,5 ms im Regressions-Gate“. Das ADR muss das auflösen — Vorschlag: Budget als Trend mit Warnung, harte Budgetaussage nur aus Messsitzungen. Das ist vorbereitet, nicht entschieden (§8).
- Windows und macOS messen die Wanduhr höchstens nightly (R21: keine Minutenkosten mehr, aber begrenzte Zahl gleichzeitiger Jobs).

### 4.5 Warnmodus und Schärfung

- Ab M1 meldet das Gate nur.
- **Scharf** wird es, wenn *alle* folgenden Punkte erfüllt sind, spätestens an M2:
  - mindestens **20 Gate-Läufe auf `main` über mindestens 14 Tage**;
  - jeder Alarm klassifiziert (echte Regression, Messfehler, Fehlalarm), **kein** Fehlalarm;
  - mindestens ein grüner Selbsttest-Lauf (§5);
  - Zählregel: Ein Fehlalarm setzt Laufzahl und 14-Tage-Frist zurück, sobald seine Ursache behoben ist. Ein Messfehler (Exitcode 2) mit fremder Ursache zählt nicht als Fehlalarm und setzt nichts zurück.
- Ist das an M2 nicht erreicht, bleibt das Gate begründet im Warnmodus und der P-12-Rückfall wird vorgelegt.
- Die Zahlen 20 und 14 sind Vorschläge.

**Kosten im Betrieb (Schätzung):** ≈ 6–12 Linux-Minuten je relevantem `main`-Push mit gespeicherter Basis, ≈ 10–18 mit Basis im Job.

**Inhalt des ADR** (Engine-Repo, nächste freie Nummer; der Sigil-Spike kann parallel eine beanspruchen): Gate-Metrik und Inventar; Schwelle mit Rauschband und Maskierungsgrenze; akzeptierte Basis und Beförderung; Fingerabdruck; Exitcodes; Warnmodus und Schärfungskriterium; Rolle der Wanduhr und der Budgets; Trendablage (P-12); Umgang mit fremden Ursachen.

## 5. Selbsttest-Job mit eingespeister Regression (für WP6.2)

**Unit-Tests des Vergleichers** laufen im normalen `cargo test`, ohne Valgrind und ohne Zusatzminuten. Erwartete Exitcodes:

| Eingabe | Exitcode |
|---|---|
| +15 % | 3 |
| +10,0 % | 0 (Regel „> 10 %“) mit Warnung |
| +10,01 % | 3 |
| +2 % bei w = 3 % | 0 ohne Warnung |
| +4 % bei w = 3 % | 0 mit Warnung |
| −20 % | 0 mit Hinweis |
| fehlender Bench, 0, NaN, abweichende Benchparameter | 2 |
| Einspeisungs-Flag in der Basis | 2 |
| roter Lauf | Basis wird nicht befördert |
| `accept` | Basis wird mit Begründung befördert |

**Job `bench-selftest`** in `nightly.yml`, hinter dem vorhandenen Änderungs-Gate (`needs.changes.outputs.run == 'true'`), plus `workflow_dispatch` nach dem Merge von WP6.2. Er ruft **dasselbe Kommando** wie der Gate-Job auf (gleiche Prozessgrenze, gleiche Exitcode-Weitergabe) und baut einmal. Grün ist er nur, wenn **alle** Erwartungen eintreffen:

| Fall | Einstellung | Erwartung |
|---|---|---|
| A/A | Kandidat = Basis, keine Einspeisung | Exitcode 0, keine Warnung |
| Bruch | `GRIMOIRE_BENCH_INJECT_REGRESSION=1` (= +15 % nominell) | Exitcode 3; der Bericht nennt genau die eingespeisten Benches |
| Nahe Schwelle | Einspeisung +12 % | Exitcode 3 |
| Unter der Schwelle | Einspeisung +5 % (Variablenname für den Prozentwert vorläufig) | Exitcode 0; Warnung genau dann, wenn 5 % > w |
| Messfehler | ein Bench aus der Kandidaten-JSON entfernt | Exitcode 2 |
| Verdeckung | Einspeisung in der **Basis** | Exitcode 2 (Vergleich verweigert) |

**Sicherungen:**

- Die Einspeisung existiert nur in `grimoire_bench`, nie in Engine- oder Determinismus-Crates, und steht in der Ergebnis-JSON.
- Der Selbsttest schreibt nie in die akzeptierte Basis.
- Ein roter Selbsttest heißt „das Gate ist kaputt“ und wird wie ein roter CI-Lauf behandelt.

**Laufzeit:** ≈ 6–12 Linux-Minuten je Nacht mit Änderungen; bei etwa 20 solchen Nächten 120–240 Minuten im Monat, seit der Veröffentlichung ohne Minutenkosten. Staut sich die Warteschlange: wöchentlich und an Meilensteinen (R21; Meldung an den PO).

## 6. Trendablage und P-12-Rückfall

### 6.1 Trendablage (P-12, erster Teil)

| Option aus P-12 | Eigenschaften | Bewertung |
|---|---|---|
| **Datenzweig** `bench-data` im Engine-Repo | Zwei Dateiarten: Messhistorie (JSON-Lines) und akzeptierte Basis je Bench. Pushes mit `GITHUB_TOKEN` erzeugen keine neuen Workflow-Läufe [Q32]; `ci.yml` reagiert ohnehin nur auf `main`. Unbegrenzt aufbewahrt, diff- und lokal auswertbar. Details unten. | **empfohlen** (vorläufig) |
| **Actions-Artefakte** | Keine Einrichtung; Aufbewahrung standardmäßig und in öffentlichen Repos höchstens 90 Tage (private Repos: bis 400 Tage) [Q27]. Als Trend nur über Download-Skripte nutzbar. | **ergänzend** für Rohdaten (Callgrind-Ausgaben, Wanduhr-Rohwerte) und als Zwischenpuffer für den Datenzweig |
| **GitHub Pages** | Bei GitHub Free nur für öffentliche Repos [Q28]; seit der Veröffentlichung (2026-09-15) also für das Engine-Repo verfügbar. Die Seite ist öffentlich, ebenso Datenzweig und Artefakte eines öffentlichen Repos. | **verfügbar, nicht bewertet**; mit P-12 neu einzuordnen |

**Schreibsemantik des Datenzweigs:**

- **Idempotente Einträge** mit Schlüssel `commit-SHA + run_id + run_attempt`; doppelte Schreibversuche ändern nichts.
- **Lookup** der akzeptierten Basis über den exakten SHA-Eintrag, nie über „letzte Zeile“.
- **Nur ein Job hat Schreibrecht** (`contents: write`), und nur auf `main`-Pushes. Er holt die Messdaten als Artefakt des Mess-Jobs.
- **Warteschlange ausdrücklich einschalten:** In einer Concurrency-Gruppe bricht ein neuer wartender Lauf standardmäßig den bisher wartenden ab (`queue: single`). Mit `queue: max` warten bis zu 100 Läufe in FIFO-Reihenfolge; das ist nicht mit `cancel-in-progress: true` kombinierbar [Q35]. Der Schreibjob nutzt eine eigene Gruppe mit `queue: max`. Zusätzlich gilt `fetch` → anhängen → `push` mit höchstens 5 Wiederholungen (Rebase bei Konflikt), falls ein Lauf außerhalb der Gruppe schreibt oder die Warteschlange voll ist.
- **Nachholen:** Scheitert das Schreiben endgültig, trägt der nächste Schreiber fehlende SHAs aus den noch vorhandenen Artefakten nach.
- **Rote und unvollständige Messungen** werden mit Status gespeichert und nie befördert.

**Darstellung:** Jeder Gate-Lauf schreibt eine Markdown-Tabelle (akzeptierte Basis, Kandidat, Δ, Warnung) ins Job-Summary. Je Meilenstein erzeugt ein kleines Skript aus dem Datenzweig die Trendtabelle für WP6.7. `github-action-benchmark` kann Daten in einen Branch schreiben, hat aber eine voreingestellte Alarmschwelle von 200 % und kennt keine akzeptierte Basis [Q29]; eine eigene Ablage passt besser. Vorläufig.

### 6.2 Rückfall (P-12, zweiter Teil)

**Auslöser**, einer genügt (festzuhalten im ADR, spätestens an M2):

1. Keine Metrik erreicht im Spike „Gate-fähig“ (§3.5), auch nach Behebung behebbarer Ursachen.
2. Valgrind läuft auch aus dem Quellcode nicht zuverlässig mit dem gepinnten Toolchain.
3. Die Schärfung (§4.5) scheitert bis M2 an Fehlalarmen.
4. Das ADR verlangt ein hartes Wanduhr-Gate (etwa für Budgets), weil der blinde Fleck von `Ir` zu groß ist, und K3 ist nicht warn- oder gate-fähig.

**Optionen laut P-12:**

| Option | Wirkung auf das Rauschen | Kosten | Risiken und Voraussetzungen |
|---|---|---|---|
| **Eigener Server ohne GPU** als Self-Hosted-Runner (nie der Entwicklungsrechner) | Bare Metal oder dedizierte Kerne. Dazu CPU-Governor `performance`, SMT aus, ASLR aus für Benchmarks (Vorbild Rustls [Q11]). Hardware-Zähler (K5) werden möglich. | Actions-Nutzung auf Self-Hosted-Runnern ist laut Abrechnungsseite kostenlos [Q14]; eine im Dezember 2025 angekündigte Plattformgebühr von 0,002 $/Min für Self-Hosted-Runner wurde verschoben, nicht aufgehoben [Q36]; 1–2 Tage Einrichtung plus Wartung | Das Engine-Repo ist seit 2026-09-15 öffentlich: nur `push` auf `main` und `workflow_dispatch`, nie Pull Requests. GitHub rät von Self-Hosted-Runnern an öffentlichen Repos ab; diese Option braucht deshalb eine eigene Sicherheitsprüfung. Ephemerer Runner, ein Job gleichzeitig. Andere Dienste erzeugen Rauschen, daher feste Ruhefenster. Vor Übernahme dasselbe Protokoll (§3) dort fahren. Auswahl des Servers: PO. |
| **Größerer kostenpflichtiger Runner** | 4 bzw. 8 Kerne; weiterhin eine VM, geringeres Rauschen nicht belegt. Nützt vor allem N-Thread-Benches. | Linux 4-Core 0,012 $/Min, 8-Core 0,022 $/Min; **nie** aus dem Inklusivkontingent [Q14][Q30]. Beispiel: 100 Läufe × 15 Min × 0,012 $ ≈ 18 $/Monat | Zahlungsentscheidung PO; Rauschgewinn vorher mit §3 messen |

**Empfehlung (vorläufig):** Der eigene Server ist der erste Rückfall, der größere Runner nur Übergang. Bis zur Umsetzung bleibt das Gate begründet im Warnmodus (M2-Kriterium).

## 7. Abgleich mit R10, R21 und OP-5

- **R10:** `Ir` schließt die bekannten Umgebungsstörungen strukturell aus; die akzeptierte Basis verhindert, dass rote Pushes zur neuen Norm werden. Schwelle mit Rauschband und Maskierungsgrenze, Warnmodus mit messbarem Schärfungskriterium und Selbsttest sind wie im Plan vorgesehen. Die Wanduhr bleibt Trend. Restrisiko: Pilotdaten aus 10 Wiederholungen beweisen keine Quoten; die Bestätigung kommt aus dem Warnmodus.
- **R21/OP-2:** Der Spike braucht ≈ 190–370 Linux-Minuten Laufzeit, nur Linux, in zwei Blöcken, mit Smoke-Job und Zeitlimits; seit der Veröffentlichung (2026-09-15) ohne Minutenkosten. Der Selbsttest läuft nur in Nächten mit Änderungen, bei Engpass wöchentlich.
- **OP-5:** Der Spike liefert die tatsächliche Minutenzahl. Der Gate-Job kommt als eigener Job mit Pfadfilter, nicht in die 3-OS-Standardmatrix.

## 8. Offene Punkte (vorbereitet, nicht entschieden)

1. **Freigabe (PO):** den Spike freigeben (≈ 190–370 Linux-Minuten Laufzeit); die Kontingentfrage OP-2 ist seit der Veröffentlichung geschlossen.
2. **P-12, Teil Ablage (PO):** Datenzweig plus Artefakte bestätigen, oder GitHub Pages (seit der Veröffentlichung ohne Pro möglich; alle Varianten sind öffentlich).
3. **P-12, Teil Rückfall (PO):** Server für einen möglichen Self-Hosted-Runner benennen, bzw. Budget für größere Runner.
4. **Plan 0002, WP6.5 (Planpflege, im ADR aufzulösen):** „≤ 1,5 ms im Regressions-Gate“ gegenüber der Trennung in relatives `Ir`-Gate und Budget-Trend (§4.4).
5. **Ausdrücklich nicht empfohlen:** externe Dienste (K7). Falls gewünscht, ist das eine eigene PO-Entscheidung.

## 9. Gegenprüfung

### 9.1 Erste Prüfung durch Codex

Codex (gpt-6-astra, read-only, ein Lauf) hat 15 Einwände zum ersten Entwurf erhoben. Die Belege wurden, soweit Dokumentation betroffen war, nachgelesen.

**Übernommen:**

| Einwand | Umsetzung |
|---|---|
| Die 45 Jobpaare sind keine unabhängigen Versuche; Verhältnisse sind asymmetrisch | §3.3: Log-Verhältnisse, Paare nur beschreibend |
| Sicherheitsfaktor 3 beweist keine Zuverlässigkeit | Pilot-Status; Einspeisung +12 %/+20 %; Maskierungsgrenze und 74-%-Untergrenze ausgewiesen (§3.3, §3.5) |
| Vergleich gegen den Vorgänger-Push normalisiert rote Pushes; `github.event.before` ist nur der Branch-Stand | akzeptierte Basis mit Beförderung (§4.2) |
| Fingerabdruck unvollständig; Toolchain-Wechsel würden versteckt | Trennung Umgebung/Code, eigene Toolchain je Commit (§4.3) |
| Der Spike prüft den Zwei-Commit-Pfad nicht | Zwei-Commit-Probe und unabhängiger Doppel-Build (§3.1) |
| Arbeitsgleichheit und Kalibrierung der Einspeisung unklar | Snapshot vor jeder Wiederholung, lesende Einspeisung, ganze Runden, Kalibrierung vorab (§3.1) |
| Aggregation der ABBA-Messung und Reihenfolge der Varianten unklar | Quadrupel-Formel, geseedete Reihenfolge (§3.2, §3.3) |
| Selbsttest widersprach der Warnregel; Exitcodes über `cargo bench` unklar | eigene Vergleicher-Exitcodes, Erwartung „Warnung genau dann, wenn 5 % > w“ (§4.3, §5) |
| `Ir`-Gate deckt keine absoluten Budgets; Licht-Benches fehlten; Callgrind kann Cache und Sprünge simulieren | §4.1, §4.4, §8 Nr. 4 |
| Zwei Blöcke und Minutenschutz nicht operationalisiert | zwei Pushes, Smoke-Job, Zeitlimits, `if: always()`; Budget auf 130–210 angehoben (§3.0, §3.2) |
| Datenzweig ohne Schreibsemantik; `concurrency` verdrängt standardmäßig wartende Läufe | §6.1 mit `queue: max` und Push-Wiederholung (nach [Q35] geprüft) |
| Pfadfilter ließen Messsystem-Änderungen aus | §4.3 |
| Literatur zu stark verallgemeinert (MooBench, Duet ist gleichzeitig, Tango-Herstellerangabe, Criterion-Signifikanz je Vergleich) | §2 K1–K3; Duet als eigene Variante in den Spike aufgenommen |
| `perf`-Ausschluss zu stark belegt | §2 K5 |
| Entscheidungsverfahren unvollständig; „zwei Wochen“ ohne Mindestzahl | §3.5, §4.5 |

### 9.2 Zweite Prüfung: Werkzeugfakten, Schätzungen, Kandidaten, Gate-Regeln

Codex (gpt-6-astra, read-only) sollte den Stand nach §9.1 gezielt auf vier Punkte prüfen: falsche Werkzeugfakten, unrealistische Rausch- oder Minutenschätzungen, fehlende Kandidaten und Gate-Regeln, die flattern würden. Beide Läufe brachen ab, bevor Einwände vorlagen. Die Prüfung lief deshalb ohne Codex entlang derselben vier Punkte. Jede Aussage wurde an der Quelle nachgelesen (abgerufen am 2026-09-15) und die Minutenschätzung an einer lokalen Zeitprobe nachgerechnet.

**Übernommen:**

| Befund | Beleg | Umsetzung |
|---|---|---|
| K3 sequentiell über alle 21 Kombinationen mit 1 s Aufwärmen je Aufruf braucht allein ≈ 21–31 Min. Das 30-Min-Job-Limit war nicht haltbar, das Budget von 130–210 Min zu niedrig. | lokale Zeitprobe, Rechnung in §3.2 | Wanduhr-Variantenmenge für K3, 0,3 s Aufwärmen, `Ir` zuerst, Job-Limit 45 Min, Budget ≈ 190–370 Min; Windows und macOS neu geschätzt (§3.0, §3.2, §7, §8) |
| Die offizielle Abrechnung nennt keine Faktoren ×2/×10, sondern Minutenpreise (Verhältnis ≈ 1,7 und ≈ 10,3) | [Q14], [Q30], [Q36] | §2 Vorbemerkung; die Faktoren bleiben vorsichtige Annahme |
| „Self-Hosted kostenlos“ ohne Hinweis auf die verschobene Plattformgebühr | [Q36] | §6.2 |
| `setup-gungraun` holt Valgrind standardmäßig vorgebaut und erkennt die Runner-Version selbst; die MSRV von `gungraun` 0.19.4 ist 1.85.1 | [Q18], [Q41] | §2 K4, §3.4 Nr. 4; Unverifiziert Nr. 5 gekürzt |
| `ubuntu-latest` kann auf 26.04 wechseln (als Preview gelistet), ein Wechsel tauscht glibc und Valgrind | [Q1] | Spike und Gate fest auf `ubuntu-24.04` (§3.2, §4.1) |
| Ein Fingerabdruck mit Image-Version und CPU-Modell hätte zwischen gespeicherter Basis und Basis im Job hin- und hergeschaltet | CPU-Mischung [Q37]; feste Valgrind-CPUID [Q39][Q40] | §4.3: Abgleich ohne `ImageVersion` und CPU-Modell, dafür mit glibc und `hwcaps`; §2 K4: glibc als Restquelle |
| Im Warnmodus ist jeder Job grün; „Beförderung bei grünem Lauf“ hätte Regressionen normalisiert | Regelprüfung §4.2 | Beförderung hängt am Urteil (Exitcode 0), nicht an der Jobfarbe |
| Die Drift-Warnung gegen den Alpha-Tag wäre bis zum nächsten Tag in jedem Lauf wiedergekehrt (Abstumpfung, R10) | Regelprüfung §4.2 | einmalige Annotation, Quittung per `accept --drift` |
| B und w ließen sich als laufend nachgeführt lesen, die Warnschwelle wäre gewandert | Regelprüfung §4.3 | Konstanten aus ADR bzw. Konfiguration |
| Der Grenzfall +10,0 % hängt bei Gleitkomma-Division an Rundung | Regelprüfung §4.3, §5 | ganzzahliger Vergleich |
| Schärfungskriterium ohne Zählregel nach einem Fehlalarm | Regelprüfung §4.5 | Rücksetzregel |
| CodSpeed: Die Beschränkung der Macro Runners auf Organisationen ist auf den aktuellen Seiten nicht belegt; der Free-Tarif enthält 600 Macro-Runner-Minuten | [Q24] | §2 K7 abgeschwächt und als unverifiziert markiert |
| Fehlende Kandidaten: Cachegrind statt Callgrind in `gungraun`; Drittanbieter-Runner | [Q3], [Q38] | §2 K4 (Variante), §2 K7 (nur zur Information) |
| Die Tango-Angabe lautet „mindestens 9 von 10“ | [Q5] | §2 K3 |

**Verworfen:**

| Prüfpunkt | Begründung |
|---|---|
| Klippe der Warnregel bei B = 1 % | Es gibt keine: Bei B = 1 % ergibt min(3 · B, 9 %) ebenfalls 3 %; die Regel ist stetig. |
| Exitcode 2 nicht neu starten | Ein einmaliger Neustart ist billig und fängt fremde Ausfälle ab; die Analysepflicht bleibt. |
| QEMU-TCG-Plugin zur Instruktionszählung | kein Rust-Werkzeug mit Basisvergleich; unter Linux kein Vorteil gegenüber Callgrind; Windows und macOS löst es nicht |
| `hyperfine` | misst ganze Prozesse; für µs–ms-Kerne mit Aufwärmen im Prozess passt die eigene Harness (K1/K3) besser |
| das ursprüngliche `iai` | Vorgänger von `gungraun` ohne zusätzlichen Nutzen |
| `criterion-perf-events`, `rdpmc` | brauchen Hardware-Zähler und fallen damit unter K5 |
| `ubuntu-slim` (1 vCPU) für das `Ir`-Gate | Job-Limit 15 Min, unprivilegierter Container, ein Kern für den Build [Q1][Q42] |
| Faktenprüfung ohne Befund | Criterion 0.8.2 mit MSRV 1.86 [Q20]; Divan 0.1.21 mit MSRV 1.80 [Q23]; Valgrind 3.27.1 und seine Plattformen [Q12]; Ubuntu 24.04 mit Valgrind 3.22.0 [Q16]; Hardware privater Runner [Q1]; Exitcode 3 und `--callgrind-limits='ir=10%'` [Q19]; `queue: max` [Q35]; Artefakt-Aufbewahrung 90 bzw. 400 Tage [Q27]; größere Runner 0,012 bzw. 0,022 $, nie aus dem Inklusivkontingent, Rechenbeispiel 18 $ [Q30]; `github-action-benchmark` mit 200 % [Q29]; `bench_diff` [Q6]. Bestätigt, keine Änderung. |

## Quellen

Abgerufen am 2026-09-15.

- [Q1] GitHub Docs: GitHub-hosted runners reference — https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- [Q2] gungraun (vormals iai-callgrind), Repository und Beschreibung — https://github.com/gungraun/gungraun
- [Q3] gungraun Guide, Prerequisites — https://gungraun.github.io/gungraun/latest/html/installation/prerequisites.html
- [Q4] Bulej, Horký, Tůma, Farquet, Prokopec: Duet Benchmarking: Improving Measurement Accuracy in the Cloud, arXiv:2001.05811 — https://arxiv.org/abs/2001.05811
- [Q5] tango-bench (Paired Benchmarking) — https://github.com/bazhenov/tango
- [Q6] bench_diff, Dokumentation — https://docs.rs/bench_diff/latest/bench_diff/
- [Q7] Criterion.rs FAQ (Cloud-CI-Rauschen) — https://bheisler.github.io/criterion.rs/book/faq.html
- [Q8] Criterion.rs, Kommandozeilenoptionen und `Criterion`-Konfiguration — https://bheisler.github.io/criterion.rs/book/user_guide/command_line_options.html, https://docs.rs/criterion/latest/criterion/struct.Criterion.html
- [Q9] Reichelt, Jung, van Hoorn: Overhead Measurement Noise in Different Runtime Environments, arXiv:2411.05491 — https://arxiv.org/abs/2411.05491
- [Q10] When Should I Run My Application Benchmark? Studying Cloud Performance Variability for the Case of Stream Processing Applications, arXiv:2504.11826 — https://arxiv.org/abs/2504.11826
- [Q11] Bencher: Rustls Continuous Benchmarking Case Study — https://bencher.dev/learn/case-study/rustls/
- [Q12] Valgrind: Supported Platforms — https://valgrind.org/info/platforms.html
- [Q13] Valgrind User Manual, Core, „Support for Threads“ — https://valgrind.org/docs/manual/manual-core.html
- [Q14] GitHub Docs: GitHub Actions billing (Inklusivminuten, größere Runner, Self-Hosted kostenlos) — https://docs.github.com/en/billing/concepts/product-billing/github-actions
- [Q15] Drittquellen zu Minutenfaktoren Windows ×2, macOS ×10, z. B. https://dev.to/maclessdev/github-actions-free-macos-minutes-explained-33p7 und https://cicdpipelinecost.com/github-actions-pricing
- [Q16] Ubuntu Packages: valgrind in noble (24.04) — https://packages.ubuntu.com/noble/valgrind
- [Q17] rust-lang/rust Issue #98746 (DWARF5 in libcompiler-builtins) und Debian-Bug #1049349 (Valgrind und DWARF5) — https://github.com/rust-lang/rust/issues/98746, https://groups.google.com/g/linux.debian.bugs.dist/c/tAGUK4Ysyo0
- [Q18] gungraun Guide, Installation des Runners und CI (`setup-gungraun`) — https://gungraun.github.io/gungraun/latest/html/installation/gungraun.html, https://gungraun.github.io/gungraun/latest/html/installation/ci.html
- [Q19] gungraun Guide, Performance-Regressionen (`--callgrind-limits`, Exitcode 3) — https://gungraun.github.io/gungraun/latest/html/regressions.html
- [Q20] crates.io API: criterion (0.8.2, rust_version 1.86) — https://crates.io/api/v1/crates/criterion
- [Q21] matteopolak/vaco Issue #663 (perf_event_open auf GitHub-gehostetem Azure-Runner) — https://github.com/matteopolak/vaco/issues/663
- [Q22] actions/runner-images Issue #11789 (`perf stat` und power-PMU auf Linux-Runnern) — https://github.com/actions/runner-images/issues/11789
- [Q23] divan, Dokumentation — https://docs.rs/divan/latest/divan/
- [Q24] CodSpeed: Walltime-Instrument, Macro Runners, Preise — https://codspeed.io/docs/instruments/walltime, https://codspeed.io/docs/features/macro-runners, https://codspeed.io/pricing
- [Q25] Bencher: Thresholds — https://bencher.dev/docs/explanation/thresholds/
- [Q26] Bencher: Track Benchmarks in CI (Relative Continuous Benchmarking) — https://bencher.dev/docs/how-to/track-benchmarks/
- [Q27] GitHub Docs: Aufbewahrung von Artefakten und Logs — https://docs.github.com/en/organizations/managing-organization-settings/configuring-the-retention-period-for-github-actions-artifacts-and-logs-in-your-organization
- [Q28] GitHub Docs: GitHub's plans / What is GitHub Pages — https://docs.github.com/get-started/learning-about-github/githubs-products, https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages
- [Q29] benchmark-action/github-action-benchmark — https://github.com/benchmark-action/github-action-benchmark
- [Q30] GitHub Docs: Actions runner pricing — https://docs.github.com/en/billing/reference/actions-runner-pricing
- [Q31] The Rust Performance Book, Benchmarking — https://nnethercote.github.io/perf-book/benchmarking.html
- [Q32] GitHub Docs: Triggering a workflow (`GITHUB_TOKEN` erzeugt keine neuen Läufe, Ausnahmen `workflow_dispatch`/`repository_dispatch`) — https://docs.github.com/en/actions/using-workflows/triggering-a-workflow
- [Q33] GitHub Docs: Events that trigger workflows (`workflow_dispatch` nur mit Datei auf dem Standard-Branch; `push` auch für nicht gemergte Workflows) — https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- [Q34] Valgrind User Manual, Callgrind (`--cache-sim`, `--branch-sim`) — https://valgrind.org/docs/manual/cl-manual.html
- [Q35] GitHub Docs: Control workflow concurrency — https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
- [Q36] GitHub Changelog, 2025-12-16: Update to GitHub Actions pricing (Preissenkung gehosteter Runner zum 2026-01-01; Plattformgebühr für Self-Hosted-Runner verschoben) — https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/
- [Q37] javi11/par2go Pull Request #10, 2026-09-05 (CPU-Modelle im Pool von `ubuntu-latest`/`windows-latest`; Einzelbericht) — https://github.com/javi11/par2go/pull/10
- [Q38] Valgrind User Manual, Cachegrind (`--cache-sim`, `--branch-sim`, `--instr-at-start`) — https://valgrind.org/docs/manual/cg-manual.html
- [Q39] Valgrind-Quelltext `VEX/priv/guest_amd64_helpers.c`, `amd64g_dirtyhelper_CPUID_avx2` — https://sourceware.org/git/?p=valgrind.git;a=blob;f=VEX/priv/guest_amd64_helpers.c
- [Q40] KDE Bugzilla 383010: Add support for AVX-512 instructions (Valgrind) — https://bugs.kde.org/show_bug.cgi?id=383010
- [Q41] crates.io API: gungraun (0.19.4, rust_version 1.85.1) — https://crates.io/api/v1/crates/gungraun
- [Q42] GitHub Changelog, 2026-01-22: 1 vCPU Linux runner generally available (`ubuntu-slim`, Job-Limit 15 Minuten) — https://github.blog/changelog/2026-01-22-1-vcpu-linux-runner-now-generally-available-in-github-actions/

## Unverifizierte Angaben

1. Alle Minutenschätzungen je Kandidat, Spike, Gate- und Selbsttest-Job (§2–§5); der erste Lauf ersetzt sie.
2. Die Faktoren ×2 (Windows) und ×10 (macOS) gegen das Inklusivkontingent: Die offizielle Abrechnungsseite nennt nur Minutenpreise (Verhältnis ≈ 1,7 und ≈ 10,3); die Faktoren stammen aus Drittquellen [Q15].
3. Dass der PO-Account im Free-Tarif mit 2.000 Inklusivminuten ist (abgeleitet aus der 403-Antwort in P0; das Kontingent ist nicht lesbar). *(Nachtrag 2026-09-15: für die öffentlichen Repos ohne Belang.)*
4. Rauscharmut von `Ir` für *unsere* Benches, insbesondere über verschiedene Azure-CPU-Modelle und Build-Verzeichnisse hinweg.
5. Dass Valgrind (vorgebaut über `setup-gungraun` oder 3.22.0 aus Ubuntu 24.04) die Debuginfo von Rust 1.98.1 fehlerfrei liest.
6. Die Größe des Rauschbands von K3 (sequentiell und Duet) auf den 4-vCPU-Runnern der öffentlichen Repos; die Duet-Zahlen [Q4] stammen aus anderen Umgebungen.
7. Ob gehostete Linux-Runner generell keine Hardware-PMU bieten; belegt ist ein Einzelbericht [Q21].
8. Dass die Umgebungsvariablen `ImageOS`/`ImageVersion` auf den Runnern gesetzt sind.
9. Dass größere gehostete Runner nicht rauschärmer sind.
10. Dass Divan keinen eingebauten Basisvergleich hat und welche Plattformen genau unterstützt sind (nur die Startseite der Dokumentation gelesen).
11. Die Aussagen „praktisch ohne Umgebungsrauschen“ (gungraun [Q2]) und „1 % in 1 s“ (tango [Q5]) sind Herstellerangaben.
12. Die Callgrind-Optionen `--cache-sim`/`--branch-sim` [Q34] wurden in diesem Lauf nicht nachgelesen (bekannte Valgrind-Optionen).
13. Eigene Vorschläge ohne Literaturbeleg: B ≤ 1 % bzw. ≤ 3,3 % als Klassengrenzen, w = 3 %, „20 Läufe über 14 Tage“, 5 Schreibwiederholungen, `taskset`-Aufteilung für Duet auf 2 vCPUs.
14. Die Richtwerte je Messschritt (§3.2): lokale Zeitprobe auf dem Entwicklerrechner, mit angenommenem Faktor 2–3 (Messung) bzw. ≈ 8 (Build) auf den 2-vCPU-Runner übertragen.
15. Dass die feste Valgrind-CPUID [Q39] `Ir` über die CPU-Modelle des Pools gleich hält; aus dem Quelltext abgeleitet, nicht gemessen.
16. Die CPU-Mischung des Pools (Einzelbericht [Q37]) und die Aktualisierungsfrequenz der Runner-Images („etwa wöchentlich“).
17. Dass Sicherheitsupdates von `libc6` `Ir` messbar verschieben.
18. Ob CodSpeed-Macro-Runners mit einem persönlichen Konto nutzbar sind [Q24].
19. Eigene Vorschläge der zweiten Prüfung ohne Literaturbeleg: 0,3 s Aufwärmen je Aufruf, Wanduhr-Variantenmenge für K3, Job-Limit 45 Min, Abbruch bei > 35 Min, Drift-Quittung, Rücksetzregel der Schärfung.

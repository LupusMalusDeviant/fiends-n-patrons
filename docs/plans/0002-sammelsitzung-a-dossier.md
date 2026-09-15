# Dossier Sammelsitzung A (Plan 0002, M0)

- **Status:** Vorbereitet für die Fragenrunde, **nichts entschieden**; nach der Gegenprüfung überarbeitet (jeder Kritikpunkt gegen die Quellen geprüft)
- **Datum:** 2026-09-15 (Agentenlauf, Strang C)
- **Autor:** Claude (Ausarbeitung), Gegenprüfung der Empfehlungen durch Codex (gpt-6-astra, read-only), jede übernommene Codex-Aussage gegen die Dateien geprüft
- **Für:** Lupus Malus Deviant (PO) — nur auswählen, nichts schreiben
- **Bezug:** [Plan 0002](0002-phase-p1-sichtbarer-kern.md) (WP1.6, M0, „Offene PO-Entscheidungen“, „Offene Punkte“, R20–R23), [Agentenlauf 2026-09-15](agentenlauf-2026-09-15.md), [Vorbereitung OF-17.3](0002-vorbereitung-of-17.3.md)

> **So ist das Dossier gedacht:** Oben der Überblick, dann je Entscheidung Kontext, Optionen und
> Empfehlung zum Nachlesen. Am Ende steht der **Fragenentwurf**: vier Fragerunden mit höchstens vier
> Fragen und dazwischen die Freigabe von WP1.0, direkt als `AskUserQuestion` verwendbar. Die
> empfohlene Option steht immer zuerst. Alle Empfehlungen sind **vorläufig** und gelten erst mit
> PO-Bestätigung.

## Überblick

| ID | Frage in einem Satz | Empfehlung | Blockiert | Runde |
|----|---------------------|------------|-----------|-------|
| P-8 | Replay-Format v2 schon in P1? | Ja | WP1.2 (Vertrag), WP7.1, WP7.5; bestimmt die Versionsnummer in P-7 | 1 |
| P-7 | Wie pinnt das Spiel die Engine während P1? | Vorabversionen `v0.2.0-alpha.N` | Release von WP1.0, Pin-Hebung aller Stränge | 1 |
| P-1 | Wo liegt die C#-Tooling-Suite? | `grimoire/tools/` | M0-Gate, WP8.1 (C#-Zielpfad), WP9, WP10 | 1 |
| P-3 | Kommt `grimoire_collide` v0 in P1? | Ja, ohne Gameplay, mit Cluster-Szene | WP1.2/1.3 (Kollisionsvertrag), WP6.5, WP11.2 | 1 |
| OP-2 | Wie werden die restlichen Actions-Minuten verteilt, und was passiert bei Überschreitung? | Budget $0, Rest bis 1. Oktober für das WP1.0-Hash-Gate, danach Sparmatrix | WP1.0-Hash-Gate (3 OS), WP6.1 (Linux-Spike ≈ 130–210 Min), WP4.4, WP9.1, GIF-Jobs, Alpha-Tags (P-7) | 2 |
| P-4a | Welche Referenz-Hardware gilt für die Budgets? | Eigener Rechner mit geschätztem Faktor als vorläufige Einordnung; Abnahme nur mit Referenzmessung oder geändertem Kriterium | M0-Gate, WP3.3, WP6.7, WP11.5 | 2 |
| P-4b | Zustimmung zu den Messsitzungen? | Ja, Sitzung 1 und Abschluss, Regeln wie im Plan | WP3.3, WP8.4 (lokale Socket-Tests), WP11.5, M1/M2-Gates | 2 |
| OP-7 | Welche Windows-Binaries werden signiert? | Jede Binary, die `target/` verlässt oder von einem Menschen gestartet wird, plus jeder lokale Release-Build | Jeder lokale Build der Agenten | 2 |
| — | Freigabe WP1.0 (gepushter Branch paralleler Scheduler) | Nach grüner 3-OS-CI freigeben, vorläufige Entscheidungen wie umgesetzt | alle Stränge mit Simulationssystemen | nach Runde 2 |
| P-9 | Wo liegt die Format-Dokumentation? | Beim Eigentümer des Formats | WP4.1, WP8.2, WP8.3 | 3 |
| P-5 | Wie viele Referenz-Patterns in P1? | 12 in P1, 8 in P2, Abnahme über Abdeckungsmatrix | WP4.5, WP5.7 | 3 |
| P-6 | Umfang Sigil-Editor-MVP und Rückfall? | Wie geplant, Frühwarnung nach WP10.3, Auslöser WP9+WP10 | WP10, E20-Rückfall | 3 (entfällt bei P-1 = D) |
| P-13 | .NET-SDK- und Avalonia-Version? | .NET 10 LTS + Avalonia 12.1, exakt gepinnt | WP9.1, WP10.1 | 3 (entfällt bei P-1 = D) |
| P-14 | Werkzeug-Binaries am Engine-Release? | Nein, P1 bleibt quelltext-only | WP11.7 | 4 |

**Nicht in dieser Sitzung:**

- **P-2** (Projekt-ADR-0010 „Sigil-Compiler-Hoheit“) gehört in **Sammelsitzung B** am Ende von WP1 (Plan 0002, WP1.6 und „Offene PO-Entscheidungen“).
- **P-10** (Abnahme der Spike-ADRs) hat zwei Teile mit eigenen Entscheidungsstellen: Sigil-Syntax OF-4.1 und Schema-Codegen OF-16.2 in **Sammelsitzung B**; Outline-Technik OF-3.1, Bullet-Darstellung OF-3.3, Licht-Culling und Go/No-Go **an M1** (Plan 0002, P-10). Der Syntax-Spike aus dem Agentenlauf (Strang D) liefert für Sammelsitzung B nur Material.
- **P-11** (OF-3.2 Schatten, Stilbibel v0) fällt **an M1**, **P-12** (Benchmark-Trendablage und Rückfall) **mit dem OF-17.3-ADR, spätestens an M2** (Plan 0002, „Offene PO-Entscheidungen“).

**Hinweis zur Sitzungsabgrenzung:** Das M0-Gate im Plan nennt ausdrücklich nur P-1 und P-4
(Plan 0002, „Meilensteine“, M0), WP1.6 bündelt dagegen P-1, P-3 bis P-9, P-13 und P-14 in
Sammelsitzung A. Dieses Dossier folgt WP1.6. P-2 fehlt in WP1.6s Liste für A zu Recht; P-3 bis P-9
schließt P-4 bis P-8 ein. OP-2 und OP-7 sind offene Punkte, keine P-Entscheidungen, werden aber mit
abgefragt, weil laufende Stränge daran hängen.

## Ausgangslage

> **Nachtrag 2026-09-15 (nach der Sitzung):** Der PO hat entschieden, beide Repos öffentlich zu machen.
> Gehostete Standard-Runner verbrauchen dann keine Actions-Minuten. Die Angaben unten zu Kontingent,
> Restminuten, Free-Plan, Kosten je Lauf und „Beide Repos sind privat“ beschreiben nur den Stand vor der
> Veröffentlichung. Die Spiel-CI holt die Engine seitdem ohne Deploy-Key.

- **P0** ist auf der Engine-Seite abgeschlossen (Tag `v0.1.0`, Engine-ADR-0004 akzeptiert). Das Spiel pinnt `v0.1.0`; seine CI hat seit dem 2026-09-15 Engine-Zugriff über den Deploy-Key ([Agentenlauf](agentenlauf-2026-09-15.md), „Bereits erledigt“).
- **Engine-ADR-0006** (paralleler Scheduler, akzeptiert 2026-09-14) macht den Scheduler zum ersten P1-Schritt WP1.0. Er wird im Agentenlauf umgesetzt und endet als **gepushter Branch mit lokalem Gate und Review, ohne Draft-PR und ohne CI-Lauf**, ohne Merge und ohne Tag ([Agentenlauf](agentenlauf-2026-09-15.md), „Änderung — Actions-Minuten fast aufgebraucht“).
- **GitHub-Actions-Minuten:** GitHub meldete **1.832 von 2.000 Minuten** dieses Abrechnungszeitraums verbraucht, **Rücksetzung am 1. Oktober 2026**; danach lief noch der Abschluss-Lauf 34905253693 (3 OS). Bis zum 1. Oktober bleiben also **höchstens 168 Minuten**, tatsächlich weniger. Ein Kontingent von 2.000 Minuten entspricht laut GitHub-Doku dem **Free-Plan** (Pro: 3.000). Seit dem Abschluss-Lauf gilt: in diesem Lauf keine CI-Läufe mehr (ebd.).
- **GitHub-Konto:** Beide Repos sind privat und gehören einem **Benutzerkonto** (`LupusMalusDeviant`, Typ `User`, über die API gelesen). Plan und Verbrauch sind über die API nicht lesbar, weil dem `gh`-Token der Scope `user` fehlt; die Zahlen oben stammen aus der GitHub-Meldung.
- **Entwicklungsrechner:** CPU und GPU liegen weit über der PRD-Referenz GTX 1060 / Apple M1 (PRD-0001 NFR, PRD-0002 NFR). Das ist für P-4a entscheidend.

---

## Runde 1 — Verträge und M0-Gate

### P-8 — Replay-Format v2 in P1

**Frage:** Bekommt das Replay-Format schon in P1 Version 2 mit Engine-Version, Build-Hash, Content-Manifest-Hash, Swap-Markierung und Anwendungs-Metadaten?

**Warum jetzt, was blockiert:** Replay v2 ist Teil des Vertrags-PR in WP1.2, der direkt nach M0 beginnt; WP7.1 (Umsetzung) und WP7.5 (Golden Master mit Content-Bezug) hängen daran. P-8 steht vor P-7, weil die Antwort bestimmt, welche Versionsnummer die Engine-SemVer-Politik für P1 verlangt.

**Kontext:** PRD-0017 FR-07 verlangt Build-Metadaten (git-Hash, Engine-Pin) in Save- und Replay-Headern; PRD-0018 FR-05 verlangt, dass Golden Master unerklärte Abweichungen erkennen. Mit Hot-Swap (PRD-0004 FR-09) laufen Sessions mit wechselndem Content, die als nicht golden markiert sein müssen (Plan 0002, WP1.2 „Hot-Swap-Semantik“). PRD-0015 FR-04 (Version-Guard) nutzt dieselbe Idee später für Suspend-Saves. v1 bleibt lesbar (WP7.1). **v2 gilt in P1 für Headless- und Harness-Replays:** Die Frame-Schleife zeichnet heute kein `InputLog` auf, ein Fensterlauf ist nicht als Replay speicherbar; der Aufzeichnungs-Hook ist spätestens mit dem Rewind-Spike in P2 geplant (grimoire `docs/architektur/crate-vertraege.md`, Einschränkung zu FR-14). **Einwand (Codex, eingeschränkt richtig):** Content-Änderungen ließen sich auch mit einer Hülle um unveränderte v1-Replays erkennen. Das verlagert die Metadaten aber nur in ein zweites Format.

**Optionen:**

| Option | Positiv | Negativ |
|--------|---------|---------|
| **A: Ja, Replay v2 in P1**, v1 bleibt lesbar | Golden Master erkennen Content- und Build-Wechsel; Swap-Sessions sind maschinell erkennbar; PRD-0017 FR-07 früh erfüllt | Ein geändertes Replay-Format gilt nach der Engine-SemVer-Politik als **inkompatibel** und hebt MINOR (`v0.2.0`), mit CHANGELOG-Eintrag und Migrationshinweis; dass v1 lesbar bleibt, ändert an dieser Einstufung nichts (grimoire `CONTRIBUTING.md`, „SemVer-Politik“) |
| **B: v1 plus separate Metadaten-Datei** neben jedem Master | Kein Formatwechsel | Zwei Dateien, die auseinanderlaufen können; Replay-Viewer (P3) muss beide lesen; Swap-Markierung lebt außerhalb des Replays; die Sidecar-Datei ist selbst ein neues Format |
| **C: Replay v2 erst in P3** (mit Saves) | Weniger P1-Arbeit | Golden Master in P1 können Content-Wechsel nicht von Regressionen unterscheiden (R12 wird schlimmer); Hot-Swap-Sessions sind nicht erkennbar |

**Empfehlung: A.** Golden Master ohne Content-Bezug sind in einem Content-getriebenen P1 blind für die häufigste Änderungsursache. Der Aufwand steckt ohnehin in WP7.1 (9 Tage WP7 gesamt).

**Konsequenzen:** A — Vertrag WP1.2 wie geplant; CHANGELOG-Eintrag als inkompatible Änderung; P1 endet nach SemVer-Politik mit `v0.2.0` (P-7). B — WP7.5 definiert ein Sidecar-Format; WP1.2 ohne Replay-Teil. C — WP7.1 ins P3-Backlog, Swap-Markierung entfällt in P1; WP11.4 (Red-Team) kann „Swap-Sessions nicht golden“ nicht prüfen.

### P-7 — Pin- und Versionspolitik in P1

**Frage:** Pinnt das Spiel während P1 Vorab-Tags `v0.2.0-alpha.N` (für WP1.0 und je Meilenstein), mit `v0.2.0` als Abschluss?

**Warum jetzt, was blockiert:** WP1.0 endet laut Plan mit dem Release `v0.2.0-alpha.1`, und das Spiel hebt danach den Pin. Ohne Pin-Politik kann der Scheduler nach der Freigabe nicht getaggt werden. Alle parallelen Stränge bauen dann gegen einen unklaren Stand, und die `--locked`-Falle des lokalen `[patch]` droht (ADR-0009, Konsequenzen).

**Kontext:** ADR-0009 bindet die Engine an einen Release-Tag (ADR-0009, Entscheidung §1); ein lokaler `[patch]` bricht jeden `--locked`-Aufruf unter `<Arbeitsordner>\`, auch in Worktrees (ADR-0009, „Konsequenzen“; Spiel-`CONTRIBUTING.md`). Plan 0002 WP1.6 und „Arbeitsorganisation“ („Pins“) sehen deshalb Alpha-Tags statt `[patch]` in parallelen Worktrees vor. Die Release-Pipeline kann das schon: `release.yml` der Engine setzt bei Versionen mit Bindestrich `--prerelease` (grimoire `.github/workflows/release.yml`, Job `release`). **Versionsnummer (geprüft):** Die Engine-SemVer-Politik vor 1.0 sagt: Eine inkompatible Änderung hebt **MINOR**, kompatible Funktionen und Fehlerbehebungen heben **PATCH**; als inkompatibel gelten unter anderem „geänderte Formate (Snapshots, Replays, Packs)“ (grimoire `CONTRIBUTING.md`, „SemVer-Politik“). **Mit P-8 = A verlangt P1 also ohnehin MINOR; `v0.2.0` ist wörtlich richtig, und die Politik braucht keinen Zusatz.** Nur wenn P-8 ≠ A ist und P1 sonst nichts Inkompatibles enthält, wäre wörtlich `v0.1.x` fällig. **Kosten je Tag:** Der Release-Ablauf der Engine verlangt einen gepushten Release-Commit `chore(release): vX.Y.Z` mit überwachtem CI-Lauf (grimoire `CONTRIBUTING.md`, „Release“, Schritt 3); dieser Commit ändert mehr als Markdown und löst deshalb die 3-OS-CI der Engine aus (`ci.yml`, `paths-ignore` nur für `**/*.md` und `docs/**`). Der Tag startet `release.yml` (nur Linux), und die Pin-Hebung im Spiel (`Cargo.toml`, `Cargo.lock`) löst die 3-OS-CI des Spiels aus.

**Optionen:**

| Option | Positiv | Negativ |
|--------|---------|---------|
| **A: Vorabversionen `v0.2.0-alpha.N`** für WP1.0, je Meilenstein und bei Bedarf dazwischen; `v0.2.0` am Ende | Zwischenstände sind als Vorabversion gekennzeichnet (Prerelease-Semantik) und dienen den parallelen Worktrees als gemeinsame, per `--locked` reproduzierbare Integrationspunkte; Prerelease-Mechanik existiert; mit P-8 = A deckungsgleich mit der SemVer-Politik | Je Alpha-Tag ≈ ein 3-OS-Engine-CI-Lauf (Release-Commit) + ein Linux-Release-Lauf + ein 3-OS-Spiel-CI-Lauf (Pin-Hebung), bei geschätzt 14–87 Minuten je 3-OS-Lauf (OP-2) |
| **B: Patch-Tags `v0.1.N`** je Meilenstein | Keine neue Versionslinie | Nur zulässig, wenn P-8 ≠ A und P1 nichts Inkompatibles enthält; kein Prerelease-Status: Zwischenstände sehen aus wie fertige Releases; gleiche CI-Kosten je Tag wie A |
| **C: Nur `v0.2.0` am Ende**, dazwischen Pins auf Commits (`rev = …`) | Keine Zwischen-Releases, weniger CI-Läufe | Weicht von ADR-0009 ab (Tag-Pin) und bräuchte ein Folge-ADR; Commits ohne Changelog; kein Release-Lauf prüft sie |
| **D: `[patch]` in den Worktrees** bis zum Ende | Kein Release-Aufwand | Ungeeignet für parallele Stränge: ein Patch unter `<Arbeitsordner>\` trifft alle Worktrees gleichzeitig (ADR-0009); das Iterieren ohne `--locked` mit Pflichtprüfungen nach dem Auskommentieren (Spiel-`CONTRIBUTING.md`) funktioniert nur für einen Strang zur Zeit |

**Empfehlung: A.** Vorabversionen kennzeichnen unfertige Zwischenstände ehrlich und geben den parallelen Worktrees feste gemeinsame Integrationspunkte, ohne dass ein lokaler Patch alle Stränge zugleich trifft. Mit P-8 = A passt `v0.2.0` ohne Regeländerung zur SemVer-Politik. „Bei Bedarf dazwischen“ fängt R23 ab: Überzieht WP1.0, bekommen Zugriffs-API und sequentieller Executor ihr eigenes Alpha-Tag. Die CI-Kosten je Tag gehören in die Minutenplanung (OP-2).

**Konsequenzen:** A — WP1.0 kann nach Freigabe und grünem 3-OS-Hash-Gate `v0.2.0-alpha.1` taggen; keine Änderung der SemVer-Politik; jeder Alpha-Tag wird in der Minutenplanung (OP-2) eingeplant. B — Die Plan-Texte zu `v0.2.0-alpha.N` (WP1.0, WP11.1, M1–M3) werden auf `v0.1.N` umgestellt; setzt P-8 ≠ A voraus. C — Folge-ADR zu ADR-0009 vor dem ersten Pin-Wechsel. D — Parallele Stränge müssen serialisiert werden oder blockieren sich gegenseitig; mit der Strang-Organisation des Plans nicht vereinbar.

### P-1 — OF-16.1: Repo-Ort der C#-Tooling-Suite

**Frage:** Wo entsteht die C#/Avalonia-Suite (Live-Link-Client, Asset-Compiler, Sigil-Editor)?

**Warum jetzt, was blockiert:** P-1 ist laut Plan die **einzige Entscheidungsstelle** und Teil des M0-Gates (Plan 0002, P-1, M0, R1). Ohne Ort startet WP9 nicht (Strang Pipeline-C# braucht „M2 + P-1 entschieden“), WP10.5 hängt an WP9.1, und der Schema-Generator in WP8.1 braucht einen Zielpfad für die C#-Ausgabe. R1 ist mit hoch × hoch das teuerste Organisationsrisiko des Plans.

**Kontext:** PRD-0016 empfiehlt `grimoire/tools/`, weil Debug-Protokoll und Formate engine-versioniert sind und ein Repo weniger gepinnt werden muss (PRD-0016, OF-16.1; dort noch als „PO-Entscheidung vor P0“ terminiert, das ist überholt). ADR-0008 legt **eine einzige Avalonia-Solution** für die gesamte Suite fest, einschließlich spielspezifischer Werkzeuge wie Stage-Editor und Balancing-Dashboard, und verweist für den Ort auf OF-16.1 (dort mit der Empfehlung `grimoire/tools/`, ADR-0008, „Kontext“ und „Entscheidung“). PRD-0000 §4 skizziert ein eigenes Verzeichnis `grimoire-tools\`, alternativ einen Unterordner im Engine-Repo (offene Frage OF-2). Heute existiert weder `grimoire/tools/` noch `Prototype/tools/` (Verzeichnis geprüft). **Einwand (Codex, geprüft):** Das Standalone-Gate der Engine sucht `fnp_` nur in `Cargo.toml` und `crates/**` (grimoire `CONTRIBUTING.md`, „Lokale Pflichtprüfungen“). C#-Code unter `tools/` wäre ungeprüft. **Abhängigkeit zu P-2:** Die Ortswahl entscheidet nicht über die Compiler-Hoheit. Lehnt der PO ADR-0010 in Sammelsitzung B ab, braucht die C#-Seite eigenen Parser, Validator und Vorschau (R20, geschätzt +8–10 Tage), und zwar am hier gewählten Ort.

**Optionen:**

| Option | Positiv | Negativ |
|--------|---------|---------|
| **A: `grimoire/tools/`** (engine-gebundene Teile: Formate, Live-Link, Asset-Compiler, Sigil-Editor); Standalone-Gate auf `tools/` erweitert | Formate, Protokoll und Client liegen in einem Commit mit dem Rust-Gegenstück; Golden-Fixtures und generierter Code ohne Repo-Grenze; ein Pin weniger | Engine-CI bekommt einen .NET-Job (Pfadfilter nötig, Minuten, OP-2); Engine-Repo wächst um eine zweite Sprache; spielspezifische Editoren (P2/P3) gehören nach ADR-0008 in dieselbe Solution; wer die Suite später aufteilt, braucht eine ADR-0008-Änderung |
| **B: Eigenes Repo `grimoire-tools`** | Saubere Trennung; eigene CI nur bei Tool-Änderungen | Drittes Repo mit eigenem Pin auf die Engine und zweitem Deploy-Key; Formatänderungen brauchen zwei koordinierte PRs |
| **C: `Prototype/tools/`** (Spiel-Repo) | Nahe am Content; spielspezifische Editoren passen natürlich | Engine-Formate werden gegen einen Engine-Tag gebaut, Protokolländerungen erreichen die Tools erst nach dem nächsten Alpha-Tag; die Spiel-CI trägt .NET und `sigilc` (R13) |
| **D: C#-Seite nach P2** (WP9 + WP10 verschoben) | P1 spart ≈ 17 Tage Aufwand plus Reserven; DoD hängt nicht daran (`grimoire-link`, Plan 0002 „Sanity-Check“) | Beantwortet die Ortsfrage nicht, sondern verschiebt sie nach P2; kein Asset-Compiler-Gate und kein Editor in P1; PRD-0016- und PRD-0017-P1-Abnahmen nur teilweise erfüllt (E20: verschoben, nicht gestrichen); schließt den kleineren Schnitt P-6 C ein |

**Empfehlung: A** (unter der Annahme P-2 = ja, also Rust-Compiler-Hoheit). Dann hängen die P1-Werkzeuge ausschließlich an Engine-Formaten (Sigil-Units, Pack, Debug-Protokoll) und gehören an denselben Commit wie ihre Rust-Wahrheit. Das Standalone-Risiko ist mit einer Zeile im Gate behoben. Wird P-2 abgelehnt, bleibt der Ort richtig, der Aufwand wächst aber nach R20.

**Konsequenzen:** A — WP8.1 schreibt C# nach `grimoire/tools/`; Engine-CI bekommt einen .NET-Job mit Pfadfilter (WP9.1); Standalone-Gate um `tools/**` erweitern; ADR-0008 (Ort nachtragen) und PRD-0000 §4/§8 OF-2 in WP11.6 nachziehen. B — Neues Repo, Deploy-Key-Setup analog ADR-0009, Pin-Politik für drei Repos; +Aufwand in WP9.1. C — `grimoire-ac` liegt im Spiel-Repo, der zweite Engine-Checkout für `sigilc` in der Spiel-CI bleibt nötig (WP9.3); jede Protokolländerung braucht einen Alpha-Tag, bevor die Tools sie sehen. D — WP9/WP10 wandern ins P2-Backlog; M3 und M4 verlieren die C#-Kriterien (Plan 0002, M3 „sofern die C#-Seite in P1 ist“); die Ortsfrage wird in P2 erneut gestellt; P-6 und P-13 entfallen in Runde 3 (siehe Fragenentwurf).

### P-3 — `grimoire_collide` v0 in P1

**Frage:** Baut P1 die Kollision v0 (Grid, Kreis/Kapsel, Layer-Masken, Graze-Ring-Query) als Budget-Nachweis, ohne Gameplay-Anbindung?

**Warum jetzt, was blockiert:** Der Vertrag in WP1.2 enthält „Kollision v0 (Signaturen)“, WP1.3 den Trait `CollisionQuery` mit Null-Implementierung. Beides beginnt direkt nach M0. Danach hängen WP6.5 und der Fassaden-Adapter WP11.2 daran (Plan 0002, Abhängigkeiten).

**Kontext:** Die P1-Abnahme in PRD-0002 verlangt, dass der 10k-Stresstest die Budgets hält, und das Budget enthält „Kollision ≤ 1,5 ms bei 10k Bullets + 100 Gegnern“ (PRD-0002, NFR und Akzeptanz). PRD-0000 §5 ordnet „Kollision + Game-Feel“ allerdings P2 zu. Der Plan löst das, indem er in P1 nur die Datenstruktur und den Budgetnachweis baut, die Wirkung (Treffer, Graze-Ökonomie, Parade) bleibt P2 (Plan 0002, „Bewusst verschoben“, PRD-0004 FR-07). R11 hält das Budget für wahrscheinlich haltbar. WP11.2 umfasst neben dem Kollisionsteil (Broadphase, Graze-Query) auch die Anbindung an die Extraktion aus WP5.3 und das Mauszielen über `Camera25D::screen_to_ground`; `stress_10k` (WP11.3) hängt an WP11.2. **Einwand (Codex):** Eine gleichmäßig verteilte Szene sagt wenig über Worst Cases; dichte Cluster gehören in den Bench.

**Optionen:**

| Option | Positiv | Negativ |
|--------|---------|---------|
| **A: Ja, collide v0 ohne Gameplay**, Bench mit repräsentativer **und** einer dichten Cluster-Szene | P1-Abnahme vollständig; Kollisionskosten früh bekannt, bevor P2 Gameplay darauf baut; Graze-Ring für Harness und Bots nutzbar | ≈ Teil von WP6 (10 Tage gesamt); Risiko von P2-Sog (R18) |
| **B: Ja, wie im Plan** (nur repräsentative Szene) | Etwas weniger Bench-Arbeit | Worst Case unbekannt bis P2/P3 |
| **C: Nein, Kollision nach P2** | WP6 und WP11.2 schrumpfen | P1-Abnahme nur als Teilnachweis (Plan 0002, P-3); das Kollisionsbudget wird erst mit Gameplay gemessen, wenn Umbauten teurer sind |

**Empfehlung: A.** Die P1-Abnahme verlangt den Nachweis, und ein Budget ohne Worst-Case-Szene verschiebt die unangenehme Überraschung nur. Die zusätzliche Szene ist ein Bench-Szenario, kein neues Feature.

**Konsequenzen:** A — WP6.5 bekommt ein zweites Bench-Szenario (Cluster), sonst wie geplant. B — Plan unverändert. C — WP6.5 und **nur der Kollisionsteil von WP11.2** (Broadphase, Graze-Query) ins P2-Backlog; Extraktions- und Mauszielen-Adapter aus WP11.2 bleiben in P1, und die Abhängigkeit WP11.2 → WP11.3 gilt nur noch für diese Teile; `stress_10k` läuft ohne Broadphase, Erfolgskriterium „Kollision ≤ 1,5 ms“ wird als verschoben dokumentiert; WP1.2 schneidet trotzdem den Trait (kostet wenig, spart später einen Vertrags-PR).

---

## Runde 2 — CI-Minuten, M0-Gate-Rest und laufende Stränge

### OP-2 — GitHub-Actions-Minuten

> **Nachtrag 2026-09-15:** Durch die Veröffentlichung beider Repos überholt; keine der Optionen A–D
> wurde umgesetzt, und bis zur Veröffentlichung wurden keine weiteren Minuten verbraucht. Die Auflage
> „nur private Repos“ für einen eigenen Runner gilt so nicht mehr, weil das Engine-Repo öffentlich ist;
> sie wird mit P-12 neu bewertet.

**Frage:** Wie werden die restlichen Actions-Minuten bis zum 1. Oktober 2026 verteilt, wie wird ab Oktober mit dem 2.000-Minuten-Kontingent geplant, und was soll bei Überschreitung passieren?

**Warum jetzt, was blockiert:** Das Restkontingent reicht bis zum 1. Oktober für höchstens wenige 3-OS-Läufe. Die Freigabe von WP1.0 braucht vorher ein grünes 3-OS-Hash-Gate (Engine-ADR-0006, Entscheidung Punkt 7), deshalb steht OP-2 **vor** der Freigabefrage. WP6.1 startet nach M0 und soll laut Plan „vorher OP-2 prüfen und zunächst nur Linux fahren“; der Spike braucht ≈ 130–210 Linux-Minuten (Vorbereitung OF-17.3, §7 und §8.1). Das Unit-Identitäts-Gate (WP4.4), dotnet auf 3 OS (WP9.1), die GIF- und Selbsttest-Jobs und jeder Alpha-Tag (P-7) vervielfachen die Last (Plan 0002, OP-2, R21, Abhängigkeiten).

**Kontext — Fakten:**

- **Verbrauch:** 1.832 von 2.000 Minuten, Rücksetzung am 1. Oktober 2026; danach lief noch der 3-OS-Lauf 34905253693 ([Agentenlauf](agentenlauf-2026-09-15.md), „Änderung — Actions-Minuten fast aufgebraucht“). Rest bis 1. Oktober: **höchstens 168 Minuten**, tatsächlich weniger.
- **Plan:** 2.000 inklusive Minuten entsprechen laut GitHub-Doku dem **Free-Plan** (Pro: 3.000) für private Repos ([GitHub Docs: About billing for GitHub Actions](https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions)). Über die API ist der Plan nicht lesbar (Token ohne Scope `user`); die Zuordnung ist aus der Kontingentgröße abgeleitet.
- **Überschreitung:** Die Agentenlauf-Notiz hält fest, dass Verbrauch über das Kontingent hinaus **berechnet** wird, sofern kein **Budget von $0** gesetzt ist; die früher abgerufene GitHub-Doku nennt eine **Sperre**, wenn kein Zahlungsmittel hinterlegt ist. Ob ein Zahlungsmittel oder ein Budget hinterlegt ist, ist nicht bekannt. Ein Budget von $0 ist die Einstellung, die sicher sperrt statt abzurechnen. **Das genaue Verhalten von GitHub ist nicht geprüft.**
- **Gewichtung** laut beiden `CONTRIBUTING.md` („Kosten“): Linux ×1, Windows ×2, macOS ×10. Die aktuelle GitHub-Doku nennt statt Faktoren Minutenpreise (Linux 0,006 $, Windows 0,010 $, macOS 0,062 $). Das entspricht bei Windows eher ×1,7; ob die Inklusivminuten für Windows noch ×2 abgebucht werden, ist nicht geprüft.
- Ein 3-OS-Lauf kostet **geschätzt 14–87 abrechenbare Minuten** ([Agentenlauf](agentenlauf-2026-09-15.md), Verhaltensregeln). Bei gleicher Laufzeit je OS entfallen **10/13 ≈ 77 %** der Kosten auf macOS (aus den Faktoren gerechnet).
- **Rechenbeispiel:** Die höchstens 168 Restminuten reichen für **1 bis 12** 3-OS-Läufe (teurer bzw. günstiger Fall); 2.000 Minuten im Monat für etwa 23 bzw. 142.
- **WP1.0-Hash-Gate:** Engine-Goldens und Spiel-Harness auf 3 OS sind mindestens ein 3-OS-Lauf je Repo, also geschätzt **28–174 Minuten**. Das kann das Restkontingent übersteigen.
- Pro Repo laufen heute `ci.yml` (3 OS je Push auf `main` und je PR, ohne reine Markdown-/`docs/`-Änderungen), `nightly.yml` (3 OS, nur wenn `main` sich bewegt hat) und `release.yml` (Engine: nur Linux; Spiel: 3 OS) (Workflow-Dateien beider Repos).
- **Eigener Runner:** Actions-Nutzung auf Self-Hosted-Runnern ist kostenlos; die OF-17.3-Vorbereitung beschreibt einen eigenen Server ohne GPU (nie den Entwicklungsrechner) mit Einrichtung in 1–2 Tagen und Sicherheitsauflagen (nur private Repos, keine Fork-PRs, ephemerer Runner) als **Rückfall für die Benchmarks** (P-12, Vorbereitung OF-17.3 §6.2). Ein allgemeiner Linux-CI-Runner wäre eine davon getrennte Entscheidung, auch wenn derselbe Server in Frage kommt.
- **Grobe Schätzung (Codex, Annahmen nicht geprüft):** Bei 20 aktiven Tagen, drei CI-Auslösern pro Repo und Tag, Nightlies und den geplanten P1-Zusatzjobs ergäben sich etwa 4.800–20.700 Minuten im Monat. Das läge deutlich über dem Free-Kontingent.
- **Einwand (Codex, geprüft):** Der Rückfall in R21 („Windows/macOS nightly statt pro Push“) widerspricht PRD-0017, das Build und Tests auf allen drei OS „bei jedem Push“ als Ziel und in US-01 nennt (PRD-0017, Ziele und US-01; FR-01 legt die Matrix fest, ohne Push-Takt). Er braucht deshalb eine PO-Freigabe, eine bloße Meldung an den PO genügt nicht. PRD-0018 FR-04b verlangt den plattformübergreifenden Hash-Vergleich dagegen ausdrücklich nur **nightly**.

**Optionen:**

| Option | Positiv | Negativ |
|--------|---------|---------|
| **A: Budget $0 und Sparmatrix:** PO setzt oder prüft das Budget von $0 (Sperre statt Rechnung). Restminuten bis 1. Oktober vorrangig für das WP1.0-Hash-Gate; WP6.1-Spike nach dem 1. Oktober. Ab Oktober: pro Push Linux + Windows, macOS nightly, vor Vertrags-Merges und vor Tags; teure Zusatzjobs (Identitäts-Gate 3 OS, GIF, Selbsttest, dotnet 3 OS) nur nightly bzw. an Meilensteinen | Keine Kosten; spart bis zu ≈ 77 % je Lauf; PRD-0018 FR-04b bleibt erfüllt; macOS-Befunde spätestens nach 24 h | Weicht für P1 von PRD-0017 (Ziele, US-01) ab (dokumentiert); macOS-Fehler werden bis zu einen Tag später sichtbar; ist das Kontingent trotzdem leer, steht die CI bis Monatsende; der Spike startet erst im Oktober |
| **B: Volle Matrix, Zahlungsmittel plus Budget-Limit** | PRD-0017 unverändert; keine Sperre bis zum Limit; Spike und Hash-Gate sofort möglich | Laufende Kosten (macOS 0,062 $/min); Budget muss gepflegt werden; Zahlungsentscheidung des PO |
| **C: Wie A, zusätzlich eigener Linux-Runner** auf einem eigenen Server (nie der Entwicklungsrechner) für Linux-Jobs; Windows und macOS bleiben gehostet | Linux-Jobs verbrauchen keine Inklusivminuten; Bench-Spike und Linux-Gates ohne Minutendruck | 1–2 Tage Einrichtung plus Wartung; Sicherheitsauflagen wie im OF-17.3-Vorschlag; Serverwahl durch den PO; getrennt vom späteren P-12-Rückfall für Benchmarks zu entscheiden (dort gelten Ruhefenster gegen Messrauschen) |
| **D: Volle Matrix, Budget $0** | Keine Kosten, PRD-0017 formal unverändert | Das Kontingent ist nach wenigen Läufen leer und sperrt **alle** Läufe bis Monatsende; die Überwachungspflicht ist dann nicht erfüllbar, und `main` bleibt ungeprüft (PRD-0018 „nie länger als 24 h rot“) |

**Empfehlung: A** (vorläufig, gilt schon jetzt im Agentenlauf sinngemäß). Das Kontingent ist die harte Grenze, und Mehrverbrauch darf nicht unbemerkt Geld kosten. Eine gesperrte CI verletzt die wichtigste Arbeitsregel des PO, und macOS verbraucht den Löwenanteil. C ist die sinnvolle Erweiterung, wenn ein geeigneter Server bereitsteht.

**Hinweis außerhalb der Frage:** Damit Agenten den Verbrauch selbst lesen können, müsste der PO dem `gh`-Token einen weiteren Scope geben; ob `user` für die Billing-API genügt, ist nicht geprüft. Das ist eine Kontoeinstellung und keine Auswahl in dieser Runde; es löst das Mengenproblem auch nicht.

**Konsequenzen:** A — `ci.yml` beider Repos bekommt eine Matrix-Regel (macOS nur bei Schedule, Tag oder Label/Dispatch); WP4.4, WP9.1 und die GIF-Jobs werden nightly/meilensteinweise geplant; WP6.1 startet nach dem 1. Oktober; WP5.1 und WP5.7 („pro Push auf 3 OS“) werden zu „pro Push auf 2 OS, nightly auf 3 OS“, ebenso der M2-Gate-Text („goldene Pattern-Hashes pro Push auf 3 OS“) und das Erfolgskriterium „≥ 12 Referenz-Patterns laufen als goldene Tests auf 3 OS grün“ (präzisiert: 3 OS nightly); PRD-0017 (Ziele, US-01) erhält in WP11.6 eine P1-Anmerkung; jeder Alpha-Tag (P-7) wird eingeplant. B — Plan unverändert, Kostenposition außerhalb des Plans. C — Wie A, plus Einrichtungsaufgabe für den Runner (1–2 Tage) mit eigener Sicherheitsprüfung; Linux-Jobs wechseln auf `runs-on: self-hosted`. D — Plan unverändert, Risiko R21 steigt auf „hoch“.

### P-4 — Referenz-Hardware und Messsitzungen

Zwei Fragen, die zusammenhängen: P-4a A, B und D brauchen Messsitzungen, P-4b legt fest, welche es gibt. „Keine Messsitzungen“ passt nur zu P-4a C (Referenz auf den Entwicklungsrechner geändert) oder macht P-4a gegenstandslos; diese Option wird daher im Fragenentwurf nicht angeboten.

**P-4a Frage:** Auf welcher Hardware gelten die P1-Budgets (60 FPS, Sim ≤ 4 ms, GPU ≤ 8 ms) als nachgewiesen?

**P-4b Frage:** Stimmt der PO den Messsitzungen zu (Messsitzung 1 nach WP3.3, spätestens an M2; Abschluss-Messsitzung in WP11.5; optional an M2)?

**Warum jetzt, was blockiert:** Das M0-Gate verlangt „Messsitzungs-Regeln und Referenz-Hardware (P-4) abgestimmt“ (Plan 0002, M0). WP3.3 (Go/No-Go mit Faktor Runner↔Referenz), WP6.7 (Budget-Abgleich), WP8.4 (lokale Socket-Tests erst nach der Firewall-Prüfung in Messsitzung 1) und WP11.5 (60-FPS-Nachweis) hängen daran; R9 ist hoch. Die Meilensteine M1 („Messsitzung 1 mit dem PO terminiert“) und M2 („Messsitzung 1 durchgeführt“) setzen Messsitzung 1 voraus (Plan 0002, „Meilensteine“).

**Kontext:** PRD-0001 und PRD-0002 nennen als Desktop-Referenz **GTX 1060 / Apple M1**, PRD-0002 ausdrücklich als „harte Messlatte ab P1“ (PRD-0001 NFR, PRD-0002 NFR). Der Entwicklungsrechner liegt mit CPU und GPU deutlich über dieser Referenzklasse. Ein 60-FPS-Nachweis auf ihm belegt die GTX-1060-Klasse also nicht. Der Plan misst CPU-Budgets headless auf dem Linux-Runner, und „Budgetaussagen ‚auf Referenz-Hardware‘ stützen sich nur auf Messsitzungen“ (Plan 0002, WP6.7; ebenso WP3.3, „Bildschirm- und GPU-Regel“). Ein aus öffentlichen Vergleichswerten geschätzter Faktor ist deshalb **kein Abnahmebeleg**. Die Regeln stehen fest: zweiter Monitor, ohne Fokus, begrenzte Frame-Zahl, nur zu vom PO freigegebenen Zeiten und mit ausdrücklicher Zustimmung (ebd.). **Einwand (Codex):** Ein einziger Faktor Runner↔Referenz überträgt sich nicht sauber auf CPU- und GPU-Last zugleich.

**P-4a Optionen:**

| Option | Positiv | Negativ |
|--------|---------|---------|
| **A: Eigener Rechner mit geschätztem Faktor als vorläufige Einordnung:** getrennte Faktoren für CPU und GPU gegenüber GTX 1060 / M1 (aus öffentlichen Vergleichswerten, als Schätzung gekennzeichnet) für den laufenden Budget-Abgleich; für die **Abnahme** in WP11.5 entweder eine Messung auf einem Referenzgerät (B, Pflicht, sobald die geschätzte Luft eines Budgets kleiner ist als die in WP6.7 ausgewiesene Unsicherheit des Faktors) oder eine ausdrückliche PO-Entscheidung, das Abnahmekriterium zu ändern (PRD-Update wie C) | Keine Anschaffung vorab; frühe Einordnung; ehrlich über die Lücke | Faktor ist Schätzung, kein Messwert und kein Abnahmebeleg; die eigentliche Abnahmefrage kommt an WP11.5 zurück, gegebenenfalls mit Beschaffung |
| **B: Echtes Referenzgerät** (GTX-1060-Klasse leihen oder gebraucht kaufen, oder ein M1-Mac) | Direkter Nachweis gegen die PRD-Referenz | Kosten und Beschaffung; Messsitzungen auf einem zweiten Gerät; ohne Mac kein Metal-Beleg |
| **C: Eigener Rechner ohne Faktor**, PRD-Referenz auf „Entwicklungsrechner“ geändert | Einfach, sofort messbar | Weicht von PRD-0001/0002 ab (PRD-Update nötig); Budgets verlieren ihre Aussage für Mittelklasse-Spieler |
| **D: Entscheidung bis Messsitzung 1 vertagen** | Mehr Information aus WP3.2 | M0-Gate bleibt formal offen; WP3.3 läuft ohne Referenzbezug |

**P-4a Empfehlung: A** (vorläufig). Sie hält die PRD-Referenz fest, kostet vorab nichts und macht die Unsicherheit sichtbar. **Wichtig für die Auswahl:** A allein beweist die Budgets auf Referenz-Hardware nicht. Die Abnahme braucht entweder eine Messung auf einem echten Referenzgerät (verpflichtend, wenn ein Budget knapp ist) oder die ausdrückliche Zustimmung des PO zu einem geänderten Abnahmekriterium.

**P-4b Optionen:**

| Option | Positiv | Negativ |
|--------|---------|---------|
| **A: Ja, Messsitzung 1 und Abschluss-Messsitzung**, optionale Zwischensitzung an M2 nach Ansage; Regeln wie im Plan | Frühwarnung für das 8-ms-GPU-Budget; Firewall-Dialog-Prüfung (R8) früh; lokale Socket-Tests danach freigegeben; M1/M2-Gates unverändert | PO muss zwei bis drei Termine für Messsitzungen freihalten |
| **B: Nur die Abschluss-Messsitzung** | Ein Termin | GPU-Überraschungen erst am Ende (R2); lokale Socket-Tests bleiben die ganze P1 gesperrt; die Gate-Kriterien von M1 und M2 müssen geändert werden; WP3.3-Faktor und WP6.7 laufen ohne Referenzwert |
| **C: Keine Messsitzungen in P1** | Kein Eingriff am Entwicklungsrechner | 60-FPS-Nachweis und GPU-Budget der P1-DoD fehlen (PRD-0000 §5); Abnahme nur mit Runner-Werten; passt nur zu P-4a C |

**P-4b Empfehlung: A.** Messsitzung 1 ist die einzige frühe Stelle, an der GPU-Budget und Firewall-Verhalten real geprüft werden; beides wird teurer, je später es auffällt, und M1/M2 bauen auf ihr auf.

**Konsequenzen:** P-4a A — WP6.7 bekommt eine Tabelle mit CPU- und GPU-Faktor, als Schätzung gekennzeichnet und mit ausgewiesener Unsicherheit; WP11.5 enthält den Entscheidungspunkt „Referenzmessung oder geändertes Abnahmekriterium“. B — Beschaffung als externe Abhängigkeit vor WP11.5; Messprotokoll nennt beide Geräte. C — PRD-0001/0002 NFR und PRD-0003 Budgets werden in WP11.6 umformuliert. D — M0 wird mit offenem Punkt übergeben. P-4b A — Plan unverändert. B — M1 und M2 bekommen geänderte Gate-Kriterien; WP8.4 bleibt lokal auf In-Process-Transport; WP3.3 und WP6.7 ohne Referenzfaktor bis zum Ende. C — P1-DoD „@60 FPS“ gilt als nicht belegt und wird nach E20 in P2 verschoben; M1/M2-Kriterien entfallen.

### OP-7 — Signierpflicht für Windows-Binaries (Regelkonflikt)

**Frage:** Welche Windows-Binaries werden mit dem Zertifikat `CN=Lupus Malus Deviant` signiert?

**Warum jetzt, was blockiert:** Agenten bauen täglich lokal. Solange der Konflikt offen ist, gilt vorläufig die strengste Lesart, und die ist bei `cargo test`-Läufen praktisch unerfüllbar (Plan 0002, OP-7).

**Kontext:** Die Signierregel des PO verlangt, nach jedem Build einer Windows-Binary das Signier-Skript des PO anzuwenden. PRD-0000 §6.6 spricht nur von Release-Builds. PRD-0017 FR-05 und die Spiel-`CONTRIBUTING.md` („Release“, Schritt 5) signieren lokal beim Release; WP11.7 signiert lokal gebaute Werkzeug-Binaries. Nightly-Binaries sind ausdrücklich **unsigniert**, liegen aber 7 Tage als herunterladbare Artefakte bereit (Spiel-`CONTRIBUTING.md`, „CI im Überblick“). Der Satz in OP-7, CI-Builds „werden nicht weitergegeben“, stimmt deshalb nur, solange niemand diese Artefakte teilt; PRD-0017 US-02 plant genau das ab P3. Die Anleitung zum Signier-Skript des PO verlangt, die ausgelieferte Datei nach dem Kopieren nach `dist/` zu signieren (Schritt 3). Das Zertifikat liegt nur lokal, also kann die CI nicht signieren (Spiel-`CONTRIBUTING.md`, Grundsätze).

**Optionen:**

| Option | Positiv | Negativ |
|--------|---------|---------|
| **A: P1-Regel: jede Binary, die `target/` verlässt oder von einem Menschen gestartet wird, sowie jeder lokale Release-Build** (also Kopie nach `dist/`, Weitergabe, Release, Messsitzungs-Binary, lokal genutzte Werkzeuge); Test-, Beispiel- und Zwischenbinaries, die nur Tests ausführen, bleiben unsigniert | Deckt sich mit Schritt 3 der Anleitung zum Signier-Skript; alles, was ein Mensch startet oder bekommt, ist signiert; weitergegebene Nightlies fallen ebenfalls darunter; keine hunderte Signaturläufe pro Testlauf | Der PO sollte seine Signierregel präzisieren (Wortlaut „jeder Build“) |
| **B: Jede lokal gebaute Windows-Binary** (vorläufige Lesart laut OP-7), inklusive Test-Executables | Wörtlich regeltreu | Jeder `cargo test` erzeugt Dutzende Executables; jede Signatur ruft den DigiCert-Zeitstempeldienst; bei jedem Neubau verloren; kein Sicherheitsgewinn |
| **C: Nur Release-Builds** (PRD-0000 §6.6 wörtlich) | Minimaler Aufwand | Widerspricht der Signierregel des PO; lokal gebaute Werkzeuge (`sigilc`, Editor) liefen unsigniert auf dem Rechner des PO |

**Empfehlung: A.** Sie trifft die Absicht beider Regeln („was ausgeliefert oder gestartet wird, trägt die Signatur“) und entspricht der Anleitung zum Signier-Skript. Die Signierregel wird dabei **nicht** von Agenten geändert; der PO kann den Wortlaut selbst präzisieren. Wie Nightlies vor einer Weitergabe an Tester signiert werden, ist eine P3-Frage (OF-17.4) und wird hier nicht gestellt.

**Konsequenzen:** A — PRD-0000 §6.6 wird in WP11.6 auf „jede Binary, die `target/` verlässt oder von einem Menschen gestartet wird, sowie jeder lokale Release-Build“ angeglichen; WP11.7 bleibt (lokale Werkzeug-Binaries signiert); Merkposten P3: Ablauf für weitergegebene Nightlies. B — Agenten-Aufträge müssen nach jedem Build Signaturschritte vorsehen; lokale Testläufe werden merklich langsamer. C — Die Signierregel des PO und das Projekt widersprechen sich dauerhaft; WP11.7 signiert nur beim Release.

---

## Freigabe WP1.0 (paralleler Scheduler, gepushter Branch)

**Stand nach dem Agentenlauf (Strang B):**

- **Branch:** `p1/wp1.0-scheduler` in `grimoire`, Kopf `f5c9bf5`, 19 Commits auf `70a7fb0`, 45 Dateien (+6.290 / −327 Zeilen). Gepusht ohne PR und ohne CI-Lauf. Die fertige PR-Beschreibung liegt unter `<Arbeitsordner>\_wt\wp1.0-pr-body.md`.
- **Umgesetzt** sind alle sieben Bausteine von Engine-ADR-0006: Zugriffsdeklaration, `ParallelSystem` mit `parallel_system_fn`, Stufenplanung mit Diagnose `Schedule::stages()` und dem Referenzmodus `StageMode::Isolated`, Befehlspuffer je System (neu `set`, Ressourcenbefehle, `append`), Panic-Regel (Stufe verworfen, niedrigster Index gewinnt), `Executor`-Trait mit sequentieller und permutierter Implementierung, `World::par_blocks`/`par_blocks_mut`, `derive_block_rng`, die neue Crate `grimoire_exec` (rayon 1.12.0, eigener Pool) und `AppBuilder::executor`. Die P0-API bleibt unverändert. Der Vertrag ändert sich in §1, §3, §7, §8, §9 und einem neuen §10.
- **Lokales Gate** (Windows x86_64, zweimal grün, zuletzt in einem frischen Target-Verzeichnis): fmt; Clippy für Windows, Linux und macOS; alle Tests mit Software-Adapter; rustdoc; Standalone-Gate; identische `clippy.toml`; kein neues `unsafe`; keine rayon-Abhängigkeit in Determinismus-Crates; das P0-Szenario erreicht `GOLDEN_FINAL_HASH` mit sequentiellem, isoliertem, permutiertem und umgekehrtem Executor sowie mit Pools aus 1, 2, 4 und 6 Threads; der goldene Spiel-Hash besteht mit der Branch-Engine.
- **Review:** Determinismus, Vertrag, Sicherheit/Performance: fünf Befunde bestätigt, alle mit Regressionstests behoben (einer mittel: die Debug-Zugriffsprüfung beschuldigte bei zwei Welten auf einem Pool das falsche System). Das Codex-Review fiel aus und wird nachgeholt.
- **Offen:** der CI-Lauf auf drei Betriebssystemen; der neue Golden `GOLDEN_PARALLEL_FINAL_HASH` (bisher nur unter Windows gemessen); der Thread-Source-Check mit `--target all`; die Timing-Schranken (nur in einer Messsitzung messbar); das Spiel-Harness-Gate mit 1, 2 und N Threads (erst nach Alpha-Tag und Pin-Hebung).

**Vorläufige Entscheidungen auf dem Branch** (je mit Empfehlung, sie beizubehalten):

1. **Zugriffsmengen:** schedule-lokale Registrierungsnummern, `ComponentId` bleibt privat. Alternative: öffentliche Welt-IDs, deren Registrierung die gehashten Zählwerte ändert.
2. **Executor auf `World`:** ein Feld außerhalb des Zustands (nicht gehasht, nicht im Snapshot, bleibt bei `restore`). Alternative: explizite Übergabe an `Schedule::run_with`, exklusive Systeme und Blockabfragen — bricht keine P0-Signatur, macht aber jedes schwere System umständlicher.
3. **Blockgröße:** `QUERY_BLOCK_SIZE = 1024` je Archetyp bis zum P1-Benchmark. Eine spätere Änderung erneuert die blockabhängigen Goldens; der endgültige Wert blockiert `v0.2.0`, nicht das Alpha.
4. **Zufallsströme:** Engine-Ströme setzen Bit 63, Spiel-Ströme nicht.
5. **Abhängigkeitsregel streng:** Auch Dev-Abhängigkeiten von Determinismus-Crates auf rayon oder `grimoire_exec` sind verboten; die Gate-Tests liegen in `grimoire_exec/tests`.
6. **Thread-Einstellung der Fassade:** nur Injektion über `AppBuilder::executor`; ein Feature `parallel` oder eine feste Abhängigkeit würde Baustein 6 widersprechen.
7. **Namen und Gate-Umfang:** Crate `grimoire_exec` mit `ThreadPoolExecutor`, Gate mit N = 4; das Gate deckt das P0-Szenario in paralleler Form, das neue parallele Szenario und die Fassaden-Szenarien ab, nicht die ecs- und core-Goldens (die keinen Schedule ausführen). Name und Kanten gehören ins Crate-Map-ADR (WP1.3).

**Release-Gate (Engine-ADR-0006, Entscheidung Punkt 7):** Die goldenen Determinismus-Tests der Engine
**und** die Spiel-Harness laufen mit **1, 2 und N Threads (N ≥ 3)** auf **Windows, Linux und macOS**.
Jeder Checkpoint-Hash muss mit dem 1-Thread-Lauf und den bestehenden Goldens übereinstimmen. Ohne
grünes Gate wird kein Release getaggt, das den parallelen Executor enthält. Ein lokales Gate auf dem
Entwicklungsrechner genügt dafür **nicht**; es ist Voraussetzung für Merge und `v0.2.0-alpha.1`.

**Ablauf in der Sitzung:**

1. **Nach Runde 2 stellen.** Die Freigabe setzt P-7 (Runde 1, Pin-Politik und Versionsnummer) und OP-2 (Runde 2, CI-Minuten) voraus.
2. **CI-Minuten für das 3-OS-Hash-Gate freigeben** (Teil von OP-2): mindestens ein 3-OS-Lauf der Engine und einer des Spiels, geschätzt 28–174 Minuten; das kann das Restkontingent bis zum 1. Oktober übersteigen. Je nach OP-2 läuft das Gate sofort, nach Budgetfreigabe oder nach dem 1. Oktober.
3. **Freigabefrage nach WP1.7:** Merge, `v0.2.0-alpha.1` und Pin-Hebung im Spiel (ein weiterer 3-OS-Spiel-Lauf), jeweils erst nach grünem 3-OS-Gate.

Weil die Freigabe alle Stränge mit Simulationssystemen entblockt (WP1.3 Spieler-Proxy, WP5, WP6.5,
WP11.2), wird sie direkt nach Runde 2 und vor Runde 3 gestellt.

---

## Runde 3 — Nach WP1

### P-9 — Ablageort der Format-Dokumentation

**Frage:** Wo liegen die Formatdokumente (Sigil, Pack, Debug-Protokoll, später Templates, Tuning, Rezepte)?

**Warum jetzt, was blockiert:** WP4.1 schreibt `docs/formats/sigil.md`, WP8.2 `debug-protocol.md`, WP8.3 `pack.md`; alle drei starten nach WP1 (Plan 0002).

**Kontext:** PRD-0016 FR-10 verlangt „Alle Datei-Formate der Pipeline in `docs/formats/` dokumentiert“, ohne das Repo zu nennen. Der Plan liest das als Spiel-Repo und schlägt `grimoire/docs/formats/` mit Verweis aus dem Spiel vor (Plan 0002, P-9). **Einwand (Codex, geprüft):** Wörtlich ist das keine Abweichung, weil FR-10 kein Repo nennt. Außerdem sind Templates, Tuning und Texte spielspezifische Formate (PRD-0016 FR-10, FR-01), die nicht in die Engine gehören. `grimoire/docs/formats/` existiert heute noch nicht (geprüft). E17 verlangt offene Formatdoku für Modding (PRD-0000 §2).

**Optionen:**

| Option | Positiv | Negativ |
|--------|---------|---------|
| **A: Beim Eigentümer des Formats:** Engine-Formate (Sigil, Pack, Debug-Protokoll) in `grimoire/docs/formats/`, Spiel-Formate ab P2 in `Prototype/docs/formats/`; ein Index im Spiel verlinkt beide mit Engine-Tag | Doku ändert sich im selben Commit wie ihr Format; Engine bleibt spielfrei; Modder finden alles über einen Index | Zwei Orte |
| **B: Alles in `grimoire/docs/formats/`** | Ein Ort | Spielspezifische Formate im Engine-Repo verletzen den Standalone-Gedanken (PRD-0001 Akzeptanz) |
| **C: Alles in `Prototype/docs/formats/`** | Ein Ort nahe am Content | Engine-Formate werden getrennt vom Code gepflegt und laufen auseinander; die Engine wäre ohne Spiel-Repo nicht dokumentiert (Standalone) |

**Empfehlung: A.** In P1 gibt es nur Engine-Formate. A heißt heute also konkret `grimoire/docs/formats/` wie im Plan und legt nur fest, wohin die Spiel-Formate später gehen.

**Konsequenzen:** A — WP4.1/8.2/8.3 wie geplant; in WP11.6 ein Index `Prototype/docs/formats/README.md` mit Verweis auf den gepinnten Tag. B — Engine-Repo bekommt ab P2 spielbezogene Doku, das Standalone-Gate sollte `docs/formats/` auf `fnp_` prüfen. C — WP4.1/8.2/8.3 schreiben ins Spiel-Repo; jede Formatänderung braucht zwei PRs.

### P-5 — Umfang der Referenz-Patterns

**Frage:** Liefert P1 12 Referenz-Patterns (8 weitere in P2) oder alle 20, jeweils mit Abnahme über eine Abdeckungsmatrix?

**Warum jetzt, was blockiert:** WP4.5 (Engine-Fixtures) und WP5.7 (goldene Hashes pro Push) starten nach WP1; WP7.3 leitet den Spiel-Content daraus ab.

**Kontext:** PRD-0004 fordert „20 Referenz-Patterns (P1/P2)“, die jeden Baustein und jede Transformation abdecken (PRD-0004, Akzeptanz). Der Plan sieht ≥ 12 in P1 mit voller Abdeckung aller 7 Bausteine, Modifikatoren und Transformationen vor, der Rest folgt in P2 (Plan 0002, WP4.5, „Bewusst verschoben“). Weil PRD-0004 selbst „P1/P2“ sagt, ist das **keine Abweichung** (von Codex bemerkt, geprüft). **Einwand (Codex):** Eine Stückzahl belohnt Feigenblatt-Abdeckung; entscheidend ist eine Abdeckungsmatrix, auch für Kombinationen. Die Matrix wird deshalb für **jede** Option zum Nachweisstandard; offen ist nur die Stückzahl in P1.

**Optionen:**

| Option | Positiv | Negativ |
|--------|---------|---------|
| **A: 12 in P1, 8 in P2**, Abnahme über die Abdeckungsmatrix (Baustein × Modifikator × Transformation, Matrix im Repo) | Abdeckung prüfbar statt gezählt; P1 bleibt schlank | Matrix ist ein kleines Zusatzartefakt; PRD-Stückzahl erst in P2 erreicht |
| **B: Alle 20 in P1**, Abnahme über die Abdeckungsmatrix | PRD-Kriterium früh voll erfüllt | Mehr Golden-Master-Churn in P1 (R12); geschätzt +1–2 Tage in WP4.5 (nicht belegt) |

**Empfehlung: A.** Die Zahl 12 bleibt Planungsgröße, die Matrix macht die Abdeckung abnehmbar. Das kostet wenige Stunden und schützt WP5.7 vor Scheinabdeckung; weitere Patterns bringen in P1 vor allem Pflegeaufwand.

**Konsequenzen:** A — WP4.5 erzeugt zusätzlich eine Abdeckungstabelle, WP11.4 prüft sie; Patterns 13–20 ins P2-Backlog. B — WP4.5 +≈ 1–2 Tage (Schätzung), Abdeckungstabelle wie A; mehr Master in WP7.5.

### P-6 — Umfang des Sigil-Editor-MVP und Überzugsregel

**Frage:** Liefert P1 den Editor mit Text, Parameter-Panel, Vorschau und Push, und wann greift der Rückfall „Editor nach P2“?

**Warum jetzt, was blockiert:** WP10 startet etwa ab Tag 28 (Plan 0002, Aktivierungsreihenfolge). Der Umfang muss vorher feststehen, damit R14 (Scope-Creep) greifbar bleibt. **Entfällt, wenn P-1 = „C#-Seite nach P2“.**

**Kontext:** PRD-0016 FR-04 verlangt visuelles Komponieren, Text-Ansicht, Tool-interne Vorschau, Validierung und Hot-Swap mit einem Roundtrip unter 1 s; P1-Akzeptanz ist ein „Sigil-Editor MVP mit Preview“ (PRD-0016). Der Plan nimmt Text, Parameter-Panel (`sigilc set`), Vorschau über `sigilc simulate` und Push in P1 auf, Knoten-Komponieren nach E20 in P2; das < 1-s-Gate aus WP10.5 ist formal P2 (Plan 0002, WP10, P-6). Der Rückfall lautet bisher: „Überschreitet der Tooling-Anteil (WP9–WP10) seine Schätzung inklusive Reserve deutlich“ (Plan 0002, „Rückfall bei Engpass“). Schätzung inklusive Reserve: WP9 8 + 2 Tage, WP10 9 + 1 Tag, zusammen 20 Tage (Plan 0002, „Aufwand“). Nur WP10.5 (≈ 1 Tag) liegt auf dem kritischen Pfad; WP10.1–10.4 laufen ab Ende WP4 vor, also meist vor WP9 (Plan 0002, „Kritischer Pfad“). **Einwand (Codex, geprüft):** „Deutlich“ ist keine prüfbare Schwelle.

**Optionen:**

| Option | Positiv | Negativ |
|--------|---------|---------|
| **A: MVP wie geplant, mit Frühwarnung und prüfbarem Auslöser:** Der Plan-Auslöser für WP9+WP10 bleibt und wird präzisiert: Ist die gemeinsame Schätzung inklusive Reserve (20 Tage) aufgebraucht, entscheidet der PO über den Rückfall. Zusätzlich Frühwarnung nach WP10.3: Sind mehr als 60 % der WP10-Schätzung inklusive Reserve (6 von 10 Tagen) verbraucht, wird der PO sofort gefragt. Asset-Compiler-Gate, Live-Link und `grimoire-link` bleiben in jedem Fall P1 | Umfang wie abgestimmt; ein WP9-Überzug bleibt sichtbar; der Rückfall wird rechtzeitig ausgelöst statt am Ende | Beide Schwellen (60 %, „Reserve aufgebraucht“) sind Vorschläge, keine Erfahrungszahlen |
| **B: Schmaler MVP:** Text, Diagnosen, Vorschau, Push; Parameter-Panel und Scrubbing nach P2 | ≈ weniger Aufwand; `sigilc set` bleibt trotzdem als CLI | Parameter-Tuning, der Kern von US-01 (PRD-0016), fehlt in P1 |
| **C: Editor komplett nach P2** | ≈ 9 fokussierte Arbeitstage weniger Aufwand | Durchlaufzeit von P1 kaum kürzer (nur WP10.5 liegt auf dem kritischen Pfad); PRD-0016-P1-Akzeptanz nur teilweise; kein Werkzeug-Feedback vor P2 |
| **D: Zusätzlich Knoten-Komponieren in P1** | Ergänzt das visuelle Komponieren aus PRD-0016 FR-04; FR-04 vollständig erst mit dem < 1-s-Gate (P2) | Größter Treiber von R14; Eigenbau-Controls laut ADR-0008 |

**Empfehlung: A.** Der Umfang ist gut begründet (kein zweiter Parser in C#, unter der Annahme P-2 = ja), es fehlte nur ein prüfbarer Auslöser. Der gemeinsame WP9+WP10-Auslöser fängt auch einen WP9-Überzug; die Frühwarnung nach WP10.3 greift früher, weil WP10.1–10.3 meist vor WP9 laufen.

**Konsequenzen:** A — WP10.3 bekommt die Frühwarnung als Gate; der Rückfalltext in Plan 0002 („deutlich“) wird durch „Schätzung inklusive Reserve aufgebraucht“ ersetzt; R14-Mitigation wird konkret. B — WP10.3/WP10.4 schrumpfen, Scrubbing und Regler ins P2-Backlog. C — WP10 ins P2-Backlog, M4 ohne Editor-Kriterium (E20 dokumentiert). D — WP10 +mehrere Tage (nicht geschätzt), R14 steigt.

### P-13 — .NET-SDK- und Avalonia-Version

**Frage:** Welche .NET-SDK- und Avalonia-Version werden für die Suite gepinnt?

**Warum jetzt, was blockiert:** WP9.1 pinnt das SDK über `global.json`, WP10.1 die Avalonia-Version, UI-Tests laufen über Avalonia.Headless auf 3 OS (Plan 0002). Entschieden wird „mit P-1“, gebraucht ab M2. **Entfällt, wenn P-1 = „C#-Seite nach P2“.**

**Kontext — Fakten:**

- **.NET 10** ist LTS und wird vom 11. November 2025 bis 14. November 2028 unterstützt; **.NET 11** erscheint als STS am 10. November 2026 und wird bis 9. November 2028 unterstützt (STS seit 2025 24 Monate), also praktisch zeitgleich mit .NET 10; .NET 8 und 9 enden am 10. November 2026 ([.NET Support Policy](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core); [.NET Blog: STS releases supported for 24 months](https://devblogs.microsoft.com/dotnet/dotnet-sts-releases-supported-for-24-months/); [endoflife.ai](https://endoflife.ai/article-dotnet-eol)).
- **Avalonia 12.0** erschien am 7. April 2026, **Avalonia 12.1** am 8. Juli 2026 ([Avalonia 12](https://avaloniaui.net/blog/avalonia-12); [Avalonia 12.1](https://avaloniaui.net/blog/release-12-1)). Avalonia 12 streicht .NET Framework und netstandard2.0; Mindestziel ist **.NET 8**, die Vorlagen bieten net8.0, net9.0 und net10.0 mit **net10.0 als Standard** ([Avalonia Discussion #18606](https://github.com/AvaloniaUI/Avalonia/discussions/18606); [Avalonia.Templates](https://github.com/AvaloniaUI/avalonia-dotnet-templates)).
- `Avalonia.Headless.XUnit` liegt als **12.1.2** (2. September 2026) auf NuGet, 12.1.0 und 12.1.1 ebenfalls ([NuGet](https://www.nuget.org/packages/Avalonia.Headless.XUnit), direkt geprüft). Paketverfügbarkeit ist nicht dasselbe wie ein getesteter Headless-Lauf auf 3 OS; der steht aus.
- Der Plan schlägt „aktuelle LTS“ vor, nennt aber keine Versionen. **Einwand (Codex):** „Aktuelle LTS“ ist kein reproduzierbarer Pin.

**Optionen:**

| Option | Positiv | Negativ |
|--------|---------|---------|
| **A: .NET 10 LTS (exakter SDK-Patch in `global.json`, `rollForward: latestFeature` nur nach PO-Freigabe) + Avalonia 12.1.x exakt** | Support bis November 2028; Avalonia 12 unterstützt .NET 8–10, Standardvorlage `net10.0`; Headless-Paket 12.1.x verfügbar | Avalonia 12 ist jünger als 11; einzelne Umbenennungen gegenüber älteren Beispielen; 3-OS-Headless-Lauf noch ungetestet |
| **B: .NET 11 (STS) + Avalonia 12.x ab November 2026** | Neueste Sprachfunktionen | Support endet praktisch zeitgleich mit .NET 10, also kein Gewinn; zum M2-Start sehr frisch; CI-Images müssen .NET 11 führen (nicht geprüft) |
| **C: .NET 10 + Avalonia 11.x** | Größeres Ökosystem an Beispielen | Avalonia 11 ist die Vorgängerlinie; späterer Umstieg auf 12 absehbar |

**Empfehlung: A.** LTS plus die aktuelle Avalonia-Linie, deren Standardvorlage auf .NET 10 zielt. Exakte Pins erfüllen PRD-0016 NFR („Versionen gepinnt“) und PRD-0017 NFR (Reproduzierbarkeit). Die konkrete SDK-Patchnummer legt WP9.1 beim Anlegen fest.

**Konsequenzen:** A — WP9.1/WP10.1 wie geplant mit festen Versionen; ein Upgrade ist ein eigener Commit (Muster aus den `CONTRIBUTING.md`); WP9.1 prüft den Headless-Lauf auf 3 OS früh. B — Start erst nach dem 10. November 2026; CI-Images müssen .NET 11 führen (nicht geprüft). C — Späterer Major-Umstieg als Backlog-Punkt.

---

## Runde 4 — Abschluss

### P-14 — Werkzeug-Binaries am Engine-Release

**Frage:** Veröffentlicht der Engine-Release in P1 Werkzeug-Binaries (`sigilc`, `grimoire-link`, `grimoire-ac`, Editor), oder bleibt er quelltext-only?

**Warum jetzt, was blockiert:** Betrifft WP11.7 und die Frage, ob `release.yml` in P1 geändert wird. Früh entschieden, damit niemand vorsorglich Release-Jobs baut (Minuten, OP-2).

**Kontext:** `release.yml` der Engine erzeugt nur Quelltext-Releases („The engine ships source only, no binaries“, grimoire `.github/workflows/release.yml`, Kopfkommentar); grimoire `CONTRIBUTING.md` beschreibt das ebenso. Das Zertifikat liegt nur im lokalen Speicher, die CI kann nicht signieren (Spiel-`CONTRIBUTING.md`, Grundsätze). PRD-0017 terminiert signierte Distribution, Nightlies und Crash-Handling auf P3 (Plan 0002, „Bewusst verschoben“). Die Spiel-CI baut `sigilc` für das Asset-Gate aus dem Engine-Tag (WP9.3). Ist P-1 = „C#-Seite nach P2“, betrifft die Frage in P1 nur `sigilc` und `grimoire-link`. **Hinweis (Codex):** Vorgebaute interne Artefakte könnten diese CI-Zeit sparen; das ist eine Build-Optimierung, keine Distribution.

**Optionen:**

| Option | Positiv | Negativ |
|--------|---------|---------|
| **A: P1 quelltext-only**; Werkzeuge werden aus dem Tag gebaut, lokal genutzte Windows-Werkzeuge nach OP-7 signiert; signierte Werkzeug-Binaries mit der Distribution in P3 per Engine-ADR | Keine Workflow-Änderung; kein Signatur-Umweg über lokale Uploads | Jeder Nutzer baut selbst (heute nur der PO und Agenten) |
| **B: Lokaler Build, Signier-Skript des PO, `gh release upload`** schon in P1 | Fertige Werkzeuge am Tag | Manueller Schritt je Alpha-Tag; Release-Ablauf wird länger; ohne Konsumenten in P1 |
| **C: Unsignierte CI-Binaries am Release** | Automatisch | Widerspricht OP-7-Absicht (weitergegebene Binaries signiert); macOS-/Windows-Builds kosten Minuten (OP-2) |

**Empfehlung: A.** In P1 gibt es keinen Konsumenten außerhalb des Entwicklungsrechners. Die Distributionsfragen (Signatur, Hosting OF-17.4) gehören gebündelt in P3.

**Konsequenzen:** A — Plan unverändert (WP11.7), Merkposten Engine-ADR in P3. B — WP11.1-Release-Ablauf bekommt Signier- und Upload-Schritt, `CONTRIBUTING.md` der Engine wird angepasst. C — `release.yml` bekommt eine Build-Matrix, Engine-ADR vor dem ersten Alpha-Tag mit Binaries.

---

## Fragenentwurf

**Reihenfolge:** Runde 1 entblockt den Vertrags-PR WP1.2 und das M0-Gate (P-8 vor P-7, weil das
Replay-Format die Versionsnummer bestimmt). Runde 2 beginnt mit den CI-Minuten, weil das
Restkontingent bis zum 1. Oktober knapp ist und die WP1.0-Freigabe davon abhängt, und schließt M0.
**Danach folgt die Freigabe WP1.0** als eigener Aufruf (Inhalt aus Strang B, siehe oben). Runde 3
betrifft die Pakete nach WP1, Runde 4 das Phasenende. Jede Runde ist ein `AskUserQuestion`-Aufruf mit
`multiSelect: false`; jede Frage beginnt mit der praktischen Wirkung, Pfade und Befehle stehen im
Dossiertext.

**Regeln für die Durchführung:**

- **Überspringen:** Wählt der PO bei P-1 „C#-Werkzeuge erst in P2“, entfallen in Runde 3 die Fragen „Editor-MVP“ (P-6) und „SDK-Version“ (P-13); Runde 3 hat dann zwei Fragen. In Runde 4 lautet die Beschreibung der empfohlenen Option dann „`sigilc` und `grimoire-link` werden aus dem Tag gebaut, fertige Werkzeug-Binaries kommen mit der Distribution in P3.“
- **P-4b:** „Keine Messsitzungen“ wird nicht angeboten, weil es nur zur Referenzänderung passt; der PO kann es über die freie Antwort wählen.
- **P-7/P-8:** Beide Fragen stehen im selben Aufruf. Wählt der PO „Patch-Versionen 0.1.x“ zusammen mit „Ja, schon in P1“, ist das nach der SemVer-Politik unvereinbar und wird direkt nachgefragt.

### Runde 1 — Verträge und M0-Gate

```json
{
  "questions": [
    {
      "header": "Replay v2",
      "question": "Sollen Aufzeichnungen schon in P1 Build- und Content-Angaben mitspeichern, damit Tests Content-Änderungen von echten Fehlern unterscheiden?",
      "multiSelect": false,
      "options": [
        {"label": "Ja, schon in P1 (Empfohlen)", "description": "Tests erkennen geänderten Content und Build, alte Aufzeichnungen bleiben lesbar. Formatwechsel, daher Engine-Version 0.2.0."},
        {"label": "Angaben in Zusatzdatei", "description": "Kein Formatwechsel, dafür eine zweite Datei je Aufzeichnung, die auseinanderlaufen kann."},
        {"label": "Erst in P3", "description": "Weniger Arbeit in P1, aber Tests können Content-Änderungen nicht von Fehlern trennen."}
      ]
    },
    {
      "header": "Pin-Politik",
      "question": "Gegen welche festen Zwischenstände der Engine soll das Spiel während P1 bauen?",
      "multiSelect": false,
      "options": [
        {"label": "Vorabversionen 0.2.0-alpha (Empfohlen)", "description": "Feste, reproduzierbare Stände für alle parallelen Stränge, als Vorabversion gekennzeichnet. Jeder Stand kostet einige CI-Läufe."},
        {"label": "Patch-Versionen 0.1.x", "description": "Nur zulässig, wenn P1 nichts Inkompatibles bringt, also nicht zusammen mit Replay v2 in P1."},
        {"label": "Commit-Stände ohne Version", "description": "Weniger CI-Läufe, aber ohne Versionsnummer und Changelog. Braucht ein neues ADR zum Engine-Pin."},
        {"label": "Lokale Verknüpfung", "description": "Kein Release-Aufwand, aber eine lokale Verknüpfung trifft alle parallelen Arbeitskopien gleichzeitig."}
      ]
    },
    {
      "header": "C#-Suite",
      "question": "Wo sollen die C#-Werkzeuge (Editor, Asset-Compiler, Live-Link) entstehen?",
      "multiSelect": false,
      "options": [
        {"label": "Im Engine-Repo (Empfohlen)", "description": "Werkzeuge und Engine-Formate ändern sich im selben Schritt. Die Engine-Prüfungen decken den Werkzeugordner mit ab."},
        {"label": "Eigenes drittes Repo", "description": "Saubere Trennung, aber ein weiteres Repo mit eigenem Engine-Pin und eigenem Zugangsschlüssel."},
        {"label": "Im Spiel-Repo", "description": "Nahe am Spiel-Content, Engine-Änderungen erreichen die Werkzeuge erst mit der nächsten Engine-Version."},
        {"label": "C#-Werkzeuge erst in P2", "description": "P1 spart etwa 17 Tage Aufwand, Editor und Asset-Compiler fehlen. Der Ort wird dann in P2 entschieden."}
      ]
    },
    {
      "header": "Kollision",
      "question": "Soll P1 die Treffererkennung schon als Leistungsnachweis bauen, noch ohne Wirkung im Spiel?",
      "multiSelect": false,
      "options": [
        {"label": "Ja, mit Worst-Case-Test (Empfohlen)", "description": "Wie geplant, zusätzlich ein Leistungstest mit dicht gedrängten Geschossen als schlimmster Fall."},
        {"label": "Ja, wie im Plan", "description": "Nur der normale Test mit 10.000 Geschossen und 100 Gegnern."},
        {"label": "Nein, erst in P2", "description": "Die Leistung der Treffererkennung wird erst mit Gameplay gemessen, P1-Abnahme nur teilweise."}
      ]
    }
  ]
}
```

### Runde 2 — CI-Minuten, M0-Gate-Rest und laufende Stränge

```json
{
  "questions": [
    {
      "header": "CI-Minuten",
      "question": "Wie sollen die knappen GitHub-Actions-Minuten (höchstens 168 bis 1. Oktober, danach 2.000 im Monat) verteilt werden, und was soll bei Überschreitung passieren?",
      "multiSelect": false,
      "options": [
        {"label": "Sparen mit $0-Budget (Empfohlen)", "description": "Keine Kosten, Rest bis 1. Oktober für den 3-OS-Test des Schedulers, Mac-Läufe nur nightly und vor Versionen, Bench-Spike ab Oktober."},
        {"label": "Bezahlen mit Budget-Limit", "description": "Alle Plattformen bei jedem Push, Mehrverbrauch kostet Geld bis zum Limit (Mac-Minute etwa 0,062 $)."},
        {"label": "Sparen plus eigener Linux-Runner", "description": "Wie empfohlen, zusätzlich Linux-Jobs kostenlos auf einem eigenen Server, nie dem Entwicklungsrechner. 1 bis 2 Tage Einrichtung."},
        {"label": "Volle Matrix, $0-Budget", "description": "Keine Kosten, aber das Kontingent ist nach wenigen Läufen leer und die CI steht bis Monatsende still."}
      ]
    },
    {
      "header": "Ref-Hardware",
      "question": "Wie soll belegt werden, dass das Spiel auf Mittelklasse-Rechnern (GTX 1060 oder M1) flüssig läuft?",
      "multiSelect": false,
      "options": [
        {"label": "Schätzen, bei Knappheit nachmessen (Empfohlen)", "description": "Laufend auf deinem Rechner mit geschätztem Faktor. Die Schätzung ist kein Abnahmebeleg: knappe Budgets vor dem Abschluss auf echtem Referenzgerät messen."},
        {"label": "Echtes Referenzgerät beschaffen", "description": "GTX-1060-Klasse oder M1 leihen oder kaufen, direkter Nachweis gegen die PRD-Vorgabe."},
        {"label": "Referenz auf Entwicklungsrechner ändern", "description": "Einfach, aber PRD-Änderung, und die Budgets sagen nichts mehr über Mittelklasse-Rechner."},
        {"label": "Bis Messsitzung 1 vertagen", "description": "Mehr Information abwarten, das M0-Gate bleibt dann formal offen."}
      ]
    },
    {
      "header": "Messsitzung",
      "question": "Welchen Messsitzungen an deinem Entwicklungsrechner stimmst du für P1 zu?",
      "multiSelect": false,
      "options": [
        {"label": "Sitzung 1 und Abschluss (Empfohlen)", "description": "Nach WP3.3 und in WP11.5, optional an M2 nach Ansage, zweiter Monitor, ohne Fokus, nur zu freigegebenen Zeiten."},
        {"label": "Nur Abschluss-Messsitzung", "description": "Ein Termin, aber Grafik- und Firewall-Probleme fallen erst am Ende auf, und M1/M2 müssen umgeplant werden."}
      ]
    },
    {
      "header": "Signieren",
      "question": "Welche selbst gebauten Windows-Programme sollen mit deinem Zertifikat Lupus Malus Deviant signiert werden?",
      "multiSelect": false,
      "options": [
        {"label": "Alles, was genutzt wird (Empfohlen)", "description": "Jede Binary, die target/ verlässt oder von einem Menschen gestartet wird, plus jeder lokale Release-Build. Reine Test- und Zwischenbinaries nicht."},
        {"label": "Jede lokal gebaute Binary", "description": "Wörtlich nach der Signierregel des PO, inklusive aller Test-Programme jedes Testlaufs."},
        {"label": "Nur Release-Builds", "description": "Minimaler Aufwand, aber lokal genutzte Werkzeuge liefen unsigniert auf deinem Rechner."}
      ]
    }
  ]
}
```

### Freigabe WP1.0 — nach Runde 2

Setzt die Antwort zu den CI-Minuten aus Runde 2 voraus. Merge, `v0.2.0-alpha.1` und Pin-Hebung
folgen in jedem Fall erst nach grünem 3-OS-Gate.

```json
{
  "questions": [
    {
      "header": "Scheduler",
      "question": "Darf der parallele Scheduler (Branch p1/wp1.0-scheduler) mit allen vorläufigen Entscheidungen gemergt und als v0.2.0-alpha.1 getaggt werden, sobald die CI auf Windows, Linux und macOS grün ist?",
      "multiSelect": false,
      "options": [
        {"label": "Nach grüner CI freigeben (Empfohlen)", "description": "PR öffnen, CI-Lauf abwarten, bei Grün mergen und taggen; danach hebt das Spiel den Pin und prüft seinen Hash mit 1, 2 und 4 Threads."},
        {"label": "Freigeben, Einzelpunkte ändern", "description": "Wie empfohlen, aber die in den folgenden Fragen gewählten Änderungen werden vorher eingebaut."},
        {"label": "Erst nach Benchmark", "description": "Merge wartet, bis der P1-Benchmark die Blockgröße festlegt; alle Stränge mit Simulationssystemen warten mit."}
      ]
    },
    {
      "header": "Blockgröße",
      "question": "Welche Blockgröße sollen parallele Abfragen bis zum P1-Benchmark verwenden (eine spätere Änderung erneuert die blockabhängigen goldenen Hashes)?",
      "multiSelect": false,
      "options": [
        {"label": "1024 vorläufig (Empfohlen)", "description": "So umgesetzt und getestet; der Benchmark bestätigt oder ändert den Wert vor v0.2.0."},
        {"label": "256 vorläufig", "description": "Feinere Aufteilung wie im Codex-Entwurf; Umbau und neuer paralleler Golden nötig."},
        {"label": "Wert erst nach Benchmark", "description": "Parallele Abfragen bleiben bis zur Messsitzung ungenutzt."}
      ]
    },
    {
      "header": "Executor",
      "question": "Soll der Thread-Pool an der Spielwelt hängen, sodass normale Systeme ohne zusätzliche Parameter parallel rechnen können?",
      "multiSelect": false,
      "options": [
        {"label": "Ja, an der Welt (Empfohlen)", "description": "So umgesetzt; der Pool gehört nicht zum gehashten Zustand und bleibt bei Snapshots außen vor."},
        {"label": "Nein, explizit übergeben", "description": "Sauberer getrennt, aber jedes schwere System braucht einen zusätzlichen Parameter; Umbau vor dem Merge."}
      ]
    },
    {
      "header": "Abhängigk.",
      "question": "Dürfen die Determinismus-Crates die Thread-Bibliothek wenigstens in ihren Tests benutzen?",
      "multiSelect": false,
      "options": [
        {"label": "Nein, auch Tests nicht (Empfohlen)", "description": "So umgesetzt; die Thread-Tests liegen in grimoire_exec und binden die Szenarien ein, die Regel aus ADR-0006 gilt ohne Auslegung."},
        {"label": "In Tests erlaubt", "description": "Thread-Tests liegen direkt bei den Crates; die CI-Prüfung erfasst dann nur normale Abhängigkeiten."}
      ]
    }
  ]
}
```

Zugriffsmengen, Stromkonvention, Crate-Name und Gate-Umfang (vorläufige Entscheidungen 1, 4, 6 und 7)
sind in der ersten Frage mit freigegeben; wählt der PO „Freigeben, Einzelpunkte ändern“, werden sie bei
Bedarf einzeln nachgefragt.

### Runde 3 — Nach WP1

Bei P-1 = „C#-Werkzeuge erst in P2“ entfallen „Editor-MVP“ und „SDK-Version“.

```json
{
  "questions": [
    {
      "header": "Formatdoku",
      "question": "Wo soll die Beschreibung der Dateiformate für Modder und Werkzeuge liegen?",
      "multiSelect": false,
      "options": [
        {"label": "Beim Eigentümer des Formats (Empfohlen)", "description": "Engine-Formate im Engine-Repo, Spiel-Formate ab P2 im Spiel-Repo, ein Index verlinkt beide."},
        {"label": "Alles im Engine-Repo", "description": "Ein Ort, aber spielspezifische Formate landen in der eigenständigen Engine."},
        {"label": "Alles im Spiel-Repo", "description": "Ein Ort am Content, Engine-Formate werden getrennt vom Engine-Code gepflegt."}
      ]
    },
    {
      "header": "Patterns",
      "question": "Sollen in P1 12 oder alle 20 Referenz-Muster entstehen, jeweils mit einer Abdeckungstabelle als Abnahme?",
      "multiSelect": false,
      "options": [
        {"label": "12 jetzt, Rest P2 (Empfohlen)", "description": "Die Tabelle belegt, dass alle Bausteine, Modifikatoren und Transformationen abgedeckt sind. 8 weitere Muster in P2."},
        {"label": "Alle 20 in P1", "description": "PRD-Vorgabe früh voll erfüllt, dafür mehr Pflege an den Vergleichstests und etwa 1 bis 2 Tage mehr."}
      ]
    },
    {
      "header": "Editor-MVP",
      "question": "Welchen Umfang soll der Muster-Editor in P1 haben, und wann wird er notfalls nach P2 verschoben?",
      "multiSelect": false,
      "options": [
        {"label": "Wie geplant, mit Frühwarnung (Empfohlen)", "description": "Text, Regler, Vorschau, Push. Frühwarnung nach WP10.3, Entscheidung spätestens, wenn die Werkzeugpakete ihre Reserve aufgebraucht haben."},
        {"label": "Schmaler MVP", "description": "Text, Fehlermeldungen, Vorschau und Push, Parameter-Regler und Scrubbing folgen in P2."},
        {"label": "Editor komplett nach P2", "description": "Etwa 9 Arbeitstage weniger Aufwand, P1 wird kaum kürzer. Asset-Compiler und Live-Link bleiben in P1."},
        {"label": "Plus Knoten-Editor", "description": "Ergänzt das visuelle Zusammensetzen schon in P1, größter Treiber für wachsenden Umfang."}
      ]
    },
    {
      "header": "SDK-Version",
      "question": "Welche .NET- und Avalonia-Version sollen die C#-Werkzeuge fest verwenden?",
      "multiSelect": false,
      "options": [
        {"label": ".NET 10, Avalonia 12.1 (Empfohlen)", "description": "Langzeitsupport bis November 2028, Avalonia-Standardvorlage zielt auf .NET 10, beide exakt festgeschrieben."},
        {"label": ".NET 11, Avalonia 12", "description": "Neuestes .NET ab November 2026, Support endet aber praktisch zeitgleich mit .NET 10, zum M2-Start sehr frisch."},
        {"label": ".NET 10, Avalonia 11", "description": "Ältere, breit dokumentierte Avalonia-Linie, späterer Umstieg auf 12 absehbar."}
      ]
    }
  ]
}
```

### Runde 4 — Abschluss

```json
{
  "questions": [
    {
      "header": "Tool-Release",
      "question": "Sollen Engine-Versionen in P1 fertig gebaute Werkzeug-Programme mitliefern?",
      "multiSelect": false,
      "options": [
        {"label": "Nein, nur Quelltext (Empfohlen)", "description": "Werkzeuge werden aus der Version gebaut, signierte fertige Programme kommen mit der Distribution in P3."},
        {"label": "Lokal signiert hochladen", "description": "Nach jeder Version lokal bauen, signieren und an das Release anhängen, ein manueller Schritt mehr."},
        {"label": "Unsignierte CI-Binaries", "description": "Automatisch aus der CI, aber unsigniert und mit zusätzlichen Actions-Minuten."}
      ]
    }
  ]
}
```

## Quellen

- Spiel-Repo: [Plan 0002](0002-phase-p1-sichtbarer-kern.md), [Agentenlauf 2026-09-15](agentenlauf-2026-09-15.md) (insbesondere „Änderung — Actions-Minuten fast aufgebraucht“), [Vorbereitung OF-17.3](0002-vorbereitung-of-17.3.md) (§6.2, §7, §8), [PRD-0000](../prd/0000-index-fiends-n-patrons.md), [PRD-0001](../prd/0001-vision-und-scope.md), [PRD-0002](../prd/0002-grimoire-engine-architektur.md), [PRD-0004](../prd/0004-sigil-bullet-system.md), [PRD-0015](../prd/0015-persistenz-und-saves.md), [PRD-0016](../prd/0016-tooling-suite.md), [PRD-0017](../prd/0017-plattform-ci-distribution.md), [PRD-0018](../prd/0018-teststrategie.md), [ADR-0007](../adr/0007-offline-asset-kompilierung.md), [ADR-0008](../adr/0008-avalonia-fuer-tooling.md), [ADR-0009](../adr/0009-engine-pin-ueber-git-tag.md), [CONTRIBUTING.md](../../CONTRIBUTING.md), `.github/workflows/`
- Engine-Repo `grimoire`: `CONTRIBUTING.md` („SemVer-Politik“, „Release“, „Lokale Pflichtprüfungen“), `.github/workflows/ci.yml`, `nightly.yml`, `release.yml`, `docs/adr/0006-paralleler-scheduler-deterministische-zusammenfuehrung.md` (Entscheidung Punkt 7), `docs/architektur/crate-vertraege.md` (Einschränkung zu FR-14)
- Signierregel und Signier-Skript des PO (lokal beim PO, nicht im Repo)
- Web (abgerufen 2026-09-15): [GitHub Docs: About billing for GitHub Actions](https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions), [.NET Support Policy](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core), [.NET Blog: STS releases supported for 24 months](https://devblogs.microsoft.com/dotnet/dotnet-sts-releases-supported-for-24-months/), [endoflife.ai: .NET End of Life](https://endoflife.ai/article-dotnet-eol), [HeroDevs: .NET EOL Dates](https://www.herodevs.com/blog-posts/net-end-of-life-eol-dates-what-you-need-to-know), [Avalonia 12](https://avaloniaui.net/blog/avalonia-12), [Avalonia 12.1](https://avaloniaui.net/blog/release-12-1), [Avalonia Discussion #18606](https://github.com/AvaloniaUI/Avalonia/discussions/18606), [Avalonia.Templates](https://github.com/AvaloniaUI/avalonia-dotnet-templates), [NuGet: Avalonia.Headless.XUnit](https://www.nuget.org/packages/Avalonia.Headless.XUnit)
- Gegenprüfung: Codex (gpt-6-astra, read-only); übernommen wurden nur Einwände, die sich an den genannten Dateien bestätigen ließen.

## Nicht bestätigte Angaben

- Kostenspanne 14–87 abrechenbare Minuten je 3-OS-Lauf und daraus 28–174 Minuten für das WP1.0-Hash-Gate: Schätzung aus dem Agentenlauf-Auftrag, nicht nachgemessen.
- Monatsverbrauch 4.800–20.700 Minuten: Codex-Schätzung auf nicht geprüften Annahmen (Auslöser pro Tag, Joblaufzeiten).
- Verbrauch nach der GitHub-Meldung (Lauf 34905253693) und damit das genaue Restkontingent: nicht bekannt. Der Free-Plan ist aus dem 2.000-Minuten-Kontingent abgeleitet, nicht direkt gelesen.
- Verhalten bei Überschreitung (Abrechnung ohne $0-Budget laut Agentenlauf-Notiz, Sperre ohne Zahlungsmittel laut früher abgerufener Doku) und ob ein Zahlungsmittel oder Budget hinterlegt ist: nicht geprüft.
- Abbuchung von Windows-Minuten gegen das Inklusivkontingent: `CONTRIBUTING.md` sagt ×2, die GitHub-Doku nennt Preise (≈ ×1,7); was heute gilt, ist offen.
- Kostenlose Nutzung von Self-Hosted-Runnern und 1–2 Tage Einrichtung: aus der OF-17.3-Vorbereitung übernommen, hier nicht erneut geprüft.
- Ob ein weiterer `gh`-Scope (etwa `user`) den Verbrauch über die API lesbar macht: nicht geprüft.
- Supportende .NET 11 am 9. November 2028: aus Sekundärquellen (endoflife.ai, HeroDevs) und der 24-Monats-Regel, nicht in den Release-Notes von .NET 11 nachgelesen.
- Aktuelle Patch-Version des .NET-10-SDK und ein Headless-Lauf mit Avalonia 12.1.x auf 3 OS: nicht geprüft.
- Leistungsfaktoren des Entwicklungsrechners gegenüber GTX 1060/M1 und deren Unsicherheit: nicht ermittelt, Option P-4a A setzt sie erst in WP6.7 fest.
- Mehraufwand „alle 20 Patterns in P1“ (≈ 1–2 Tage), die 60-%-Frühwarnung und die Lesart „Reserve aufgebraucht“ in P-6: eigene Vorschläge, keine Erfahrungswerte.
- Verfügbarkeit von .NET 11 auf den GitHub-Runner-Images ab November 2026: nicht geprüft.

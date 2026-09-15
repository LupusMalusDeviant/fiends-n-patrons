# Agentenlauf 2026-09-15

- **Stand:** 2026-09-15 (Start)
- **Auftrag des PO:** Deploy-Key einrichten und prüfen, danach die nächsten Schritte autonom; Last über Codex (gpt-6-astra) verteilen; bis zur nächsten PO-Sitzung keine PO-Entscheidungen.
- **Bezug:** [Plan 0002](0002-phase-p1-sichtbarer-kern.md), Engine-ADR-0006

## Abschlussbericht

**Kurzfassung**

- **P0 ist abgeschlossen.** Spiel-CI grün auf Windows, Linux und macOS, Engine-Zugriff über den Deploy-Key belegt, goldener Spiel-Hash auf allen drei Plattformen identisch.
- **CI steht still.** GitHub meldete 1.832 von 2.000 Actions-Minuten. Nach dem Abschluss-Lauf 34905253693 wurde nichts mehr ausgelöst; alle Ergebnisse des Laufs sind **nur lokal** geprüft (inklusive Clippy für Linux und macOS). Die Nightlies sind gar nicht gestartet, verbraucht wurde nichts; eine Überwachung bricht verspätete Starts ab.
- **Engine-Branches** (gepusht, ohne PR):

  | Branch | Stand | Inhalt |
  |--------|-------|--------|
  | `p1/wp1.0-scheduler` | `548a30a` | Paralleler Scheduler nach ADR-0006 vollständig; lokales Gate grün mit 1, 2 und N Threads; 7 Review- und Codex-Befunde behoben |
  | `p1/wp1.2-contracts-draft` | `f9765dd` | P1-Vertragsentwurf (§1–§16) und ADR-Vorschlag 0008 „Crate-Map-Erweiterung P1“; eingearbeitet: 21 Review-, 9 Codex- und 11 Kompilierprüfungs-Befunde |
  | `p1/wp1.4-sigil-syntax-spike` | `d5956ed` | Syntax-Spike mit Prototyp-Parsern; Empfehlung `sigil 1`; ADR-Vorschlag 0007 |

- **Spiel-Repo (`main`):** Dossier Sammelsitzung A, M0-Eintritts-Check (10 von 12 erfüllt), OF-17.3-Vorbereitung, spielseitiger Vertragsentwurf, Fragenrunde zur Vertragsfreigabe.

**Was von dir gebraucht wird, in dieser Reihenfolge**

1. **CI-Minuten** — erste Frage in Runde 2 des [Dossiers](0002-sammelsitzung-a-dossier.md). Ohne diese Entscheidung kann kein Gate (Scheduler, Verträge, Nightlies) nachgewiesen werden.
2. **Sammelsitzung A** — 13 Fragen in vier Runden ([Dossier](0002-sammelsitzung-a-dossier.md)); schließt M0.
3. **Freigabe WP1.0** — 4 Fragen, direkt nach Runde 2 des Dossiers.
4. **Vertragsfreigabe WP1.2** — 21 Fragen in sechs Runden ([Fragenrunde](0002-vertragsfreigabe-wp1.2.md)); die letzte Frage übernimmt 116 vorläufige Entscheidungen pauschal.

Zusammen 38 Fragen, jede mit Erklärung und Empfehlung; sie lassen sich auf mehrere Sitzungen verteilen. Sagst du „los“, stelle ich sie per Auswahl.

**Hinweise**

- Codex war zweimal nicht verfügbar. Dadurch fehlt nur noch der unabhängige Namens-Abgleich des Vertrags durch Codex; alle anderen Codex-Prüfungen wurden nachgeholt.
- Befund zur Werkzeugkette: Ein gemeinsam genutztes Cargo-Target-Verzeichnis kann veraltete Artefakte liefern; Gates liefen danach mit frischem Target.
- Letzter autonomer Schritt läuft noch: Projekt-ADR-Vorschläge 0010 (Sigil-Compiler-Hoheit) und 0011 (Schema-Codegen, OF-16.2) für Sammelsitzung B. Danach ist ohne deine Entscheidungen oder CI-Minuten nichts Sinnvolles mehr offen.

## Bereits erledigt

- Deploy-Key auf `grimoire` angelegt (id 163303281, nur lesen), Secret `GRIMOIRE_DEPLOY_KEY` in `fiends-n-patrons` gesetzt und über die API bestätigt, der unbrauchbare Key 163301443 entfernt (`scripts/setup-ci-deploy-key.ps1 -ReplaceExisting`).
- 13 Spiel-Commits auf `main` gepusht (`00d6683`); Spiel-CI-Lauf 34903989101 wird überwacht.

## Stränge

| Strang | Inhalt | Ziel bis zur nächsten PO-Sitzung | Grenze |
|--------|--------|---------------------|--------|
| A — P0-Abschluss | Spiel-CI bis zum Ende überwachen; im Log „Engine-Git-Abhaengigkeit gefunden, Deploy-Key vorhanden“ auf allen drei OS belegen; P0-WP6.3 in Plan 0001 schließen | P0 abgeschlossen oder ein analysierter Fehler | nur Doku-Commits auf `main` des Spiel-Repos |
| B — WP1.0 Paralleler Scheduler | Workflow: drei unabhängige Entwürfe (zwei Claude-Blickwinkel, ein Codex-Entwurf) → Richter-Synthese → Umsetzung im Worktree `_wt/p1-scheduler` → unabhängiges lokales Gate → Review mit drei Claude-Linsen und Codex, jeder Befund gegengeprüft → Draft-PR und höchstens zwei CI-Läufe | Draft-PR mit grünem Gate und überwachtem CI-Lauf | kein Merge, kein Tag: die Vertragsänderung braucht die PO-Freigabe (WP1.7) |
| C — Dossier Sammelsitzung A | P-1, P-3 bis P-9, P-13, P-14, OP-7 und Actions-Minuten mit Kontext, Optionen, Empfehlung und fertigem Fragenentwurf; Codex fordert die Empfehlungen heraus | Fragenrunde in der nächsten PO-Sitzung ohne Vorarbeit startbar | nichts wird entschieden |
| D — Spike Sigil-Syntax (OF-4.1, WP1.4) | Codex entwirft den Korpus (5 Patterns, 10 Fehler) in RON und eigener Grammatik; Claude baut Prototyp-Parser und misst Fehlermeldungen, Text↔Parameter-Roundtrip und Generierbarkeit; Bericht und Engine-ADR-Vorschlag | Branch `p1/wp1.4-sigil-syntax-spike` mit Bericht und ADR „Vorgeschlagen“ | Entscheidung erst in Sammelsitzung B; kein PR, keine CI-Minuten |
| E — Vorbereitung Benchmark-Rauschen (OF-17.3, WP6.1) | Kandidaten-Metriken, Versuchsprotokoll, Minutenkosten, Rückfall P-12 | Vorschlag als Grundlage für WP6.1 | keine CI-Läufe |

## Verhaltensregeln für alle Agenten

- **Keine Rückfragen.** Gibt ein ADR, der Vertrag oder Plan 0002 eine Empfehlung, wird sie angewendet und als *vorläufig, PO-Bestätigung ausstehend* protokolliert. Was ein akzeptiertes ADR, den Plan-Umfang oder eine P0-API brechen würde, unterbleibt und wird als Frage mit Optionen und Empfehlung notiert.
- **Git:** Arbeit nur in eigenen Worktrees und Branches; kein Push auf `main` der Engine, kein Merge, kein Tag, kein Release, kein Force-Push.
- **Actions-Minuten sparen:** Ein 3-OS-Lauf kostet geschätzt 14–87 abrechenbare Minuten (macOS zählt zehnfach). Das Kontingent ist über die API nicht lesbar, weil dem `gh`-Token der Scope `user` fehlt. Deshalb wird zuerst lokal geprüft (inklusive Clippy für Linux und macOS). Der Scheduler-PR bekommt höchstens zwei CI-Läufe, Spike-Branches keinen PR.
- **Bildschirm und GPU:** keine Fenster, keine Hardware-GPU-Tests (nur `GRIMOIRE_GPU_ADAPTER=software`), keine neuen Shell- oder WSL-Prozesse.
- **Zugangsdaten:** keine Keys, Secrets oder GitHub-Einstellungen anfassen.
- **Codex** läuft nur mit Sandbox `read-only`; Claude prüft jede Codex-Aussage gegen den Code, bevor sie verwendet wird.
- **CI-Pflicht:** Jeder Push mit CI wird bis zum Ende überwacht, ein roter Lauf mit `gh run view --log-failed` analysiert und die Ursache (Code, Vorrichtung, extern) benannt.

## Änderung — Actions-Minuten fast aufgebraucht

GitHub meldete: **1.832 von 2.000 Actions-Minuten** dieses Abrechnungszeitraums verbraucht (Rücksetzung am 1. Oktober 2026). Danach lief noch der Abschluss-Lauf 34905253693. Verbrauch über das Kontingent hinaus wird berechnet, sofern kein Budget von $0 gesetzt ist. Deshalb gilt ab sofort bis zur PO-Entscheidung:

- **In diesem Lauf keine CI-Läufe mehr.** Über die Restminuten entscheidet der PO in der nächsten Sitzung.
- **Strang B endet mit einem gepushten Branch, ohne Draft-PR** (ein PR würde die CI auslösen). Der Workflow wurde dafür angehalten und mit geändertem Abschlussschritt fortgesetzt; Entwurf, Umsetzung, Gate und Review bleiben unverändert.
- **Nightlies:** Die geplanten Läufe (Engine 02:17 UTC, Spiel 02:47 UTC) werden gleich beim Start abgebrochen, solange nur der kurze `changes`-Job läuft. Die Workflows werden nicht deaktiviert, weil das eine Einstellung ist, die der PO selbst ändern soll.
- Anschlussarbeit 2 und 3 unten entfallen, soweit sie CI-Minuten brauchen.
- Neue PO-Frage für die nächste Sitzung: Umgang mit dem Kontingent (Budget $0, Bezahlung, Matrix verkleinern, eigener Runner ohne GPU).

## Zeitfenster und Anschlussarbeit

Sind die Stränge fertig, bevor der PO wieder verfügbar ist, geht es ohne Rückfrage weiter, in dieser Reihenfolge und jeweils nur, soweit keine PO-Entscheidung nötig ist:

1. Befunde der Stränge nacharbeiten (rote CI-Läufe analysieren, bestätigte Review-Befunde beheben).
2. P0-Reste schließen, die nur Minuten kosten: Nightly-Läufe beider Repos einmal manuell starten und überwachen; P0-Reste als Backlog-Liste (WP1.1).
3. WP6.1 nach dem Vorschlag aus Strang E, zuerst nur auf Linux-Runnern (günstig).
4. Vorarbeit zu WP1.2 (Vertragsentwurf) gegen die Empfehlungen, nur auf einem Branch, erst nachdem der Scheduler-Entwurf steht (Konflikte in `crate-vertraege.md` vermeiden).

Wird der Lauf unterbrochen, wird danach dort weitergemacht, wo die Workflows standen.

## Für die nächste PO-Sitzung

Bericht mit Ergebnissen je Strang, allen vorläufigen Entscheidungen und der vorbereiteten Fragenrunde (Sammelsitzung A und Freigabe des WP1.0-Draft-PR). Die Ergebnisse werden unten nachgetragen.

## Ergebnisse

### Strang A — P0-Abschluss (erledigt)

- Spiel-CI-Lauf [34903989101](https://github.com/LupusMalusDeviant/fiends-n-patrons/actions/runs/34903989101) auf `00d6683`: rustfmt und `test` auf Windows, Linux und macOS grün.
- Engine-Zugriff belegt: Alle drei Test-Jobs melden „Engine-Git-Abhaengigkeit gefunden, Deploy-Key vorhanden: Zugriff ueber SSH.“, der SSH-Agent-Schritt endet jeweils mit `success`.
- `golden_final_hash_for_seed_42` besteht auf allen drei Plattformen: Der goldene Endhash des Spiels ist plattformübergreifend identisch.
- P0-WP6.3 und damit Phase P0 sind abgeschlossen; von M0 ist nur die PO-Sammelsitzung A offen.
- Abschluss-Commit `8642f7d` (Plan-Status, Kommentar zum goldenen Hash): CI-Lauf [34905253693](https://github.com/LupusMalusDeviant/fiends-n-patrons/actions/runs/34905253693) grün auf allen drei Plattformen.

### Strang C — Dossier Sammelsitzung A (fertig)

- [`0002-sammelsitzung-a-dossier.md`](0002-sammelsitzung-a-dossier.md): zwölf Entscheidungen (P-7, P-1, P-3, P-8, P-4a/b, OP-2, OP-7, P-9, P-5, P-6, P-13, P-14) mit Kontext, Optionen, vorläufiger Empfehlung und Folgen; 13 Fragen in vier Runden als fertiger Fragenentwurf. Die Codex-Gegenprüfung lieferte 28 Punkte, alle gegen die Quellen geprüft und eingearbeitet (unter anderem der Minutenstand).
- Offen: Der Abschnitt „Freigabe WP1.0“ wird nach Abschluss von Strang B ergänzt.
- Auffälligkeiten: Der Entwicklungsrechner liegt weit über der PRD-Referenz; die SemVer-Regel der Engine vor 1.0 passt nicht zu `v0.2.0` (eine Zeile Ergänzung nötig); das Standalone-Gate prüft einen künftigen Ordner `tools/` noch nicht.

### Strang D — Spike Sigil-Syntax OF-4.1 (fertig, Branch gepusht)

- Branch `p1/wp1.4-sigil-syntax-spike` (`65e5288`), ohne PR und ohne CI-Lauf: Korpus mit fünf Patterns und zehn Fehlern je Syntax, handgeschriebene Prototyp-Parser für RON (ron 0.12.2 plus eigener verlustfreier Scanner) und `sigil 1`, alle Messungen reproduzierbar (`cargo test`, 7 von 7 grün).
- Fehlermeldungen (je höchstens 30 Punkte, RON / `sigil 1`): Position 27 / 30, Knotenpfad 28 / 30 (automatisch gemessen); Ursache 22 / 30, Fix-Hinweis 19 / 29 (manuell bewertet, vorläufig).
- Wert an einem Knotenpfad setzen: `sigil 1` behält alle Kommentare und ändert genau eine Zeile.
- Vorschlag (vorläufig): eigene Grammatik `sigil 1`; Bericht `docs/spikes/of-4.1-sigil-quelltextsyntax.md` und Engine-ADR-0007 im Status „Vorgeschlagen“ auf dem Branch. Entschieden wird in Sammelsitzung B.
- Lücken: Codex stand zeitweise nicht zur Verfügung. Korpus und Parser hatten deshalb keine Zweitmodell-Prüfung, der Generierbarkeitsvergleich fehlt zur Hälfte, und die manuellen Bewertungen stammen nur von Claude. Eine CI-Änderung (`spikes/**` in `paths-ignore`) bleibt dem PO überlassen.

### Strang E — Vorbereitung Benchmark-Rauschen OF-17.3 (fertig)

- [`0002-vorbereitung-of-17.3.md`](0002-vorbereitung-of-17.3.md): Vorschlag (vorläufig) — das Regressions-Gate misst Instruktionszählungen mit Callgrind (über gungraun) auf `ubuntu-latest` für Single-Thread-Benches; Wanduhrzeiten nur als Trend. Die Minutenschätzung für den Spike wurde nach einer lokalen Zeitmessung nach oben korrigiert. Nichts wurde ausgeführt, keine CI.

### Anschlussarbeit — M0-Eintritts-Check (WP1.1) und Gliederung WP1.2

- [`0002-m0-eintritts-check.md`](0002-m0-eintritts-check.md): 10 von 12 M0-Bedingungen erfüllt und mit Belegen nachgeprüft (48 Prüfungen, sieben Korrekturen an Belegen, kein Status geändert). Offen sind nur die PO-Punkte P-1 und P-4 aus Sammelsitzung A. Das Determinismus-Kriterium gilt mit Einschränkung: plattformübergreifend belegt ist bisher nur das Debug-Profil.
- Zehn P0-Reste als Issue-Entwürfe (nicht angelegt), sechs davon brauchen eine PO-Entscheidung: echter GPU-Fensterlauf, Branch-Schutz im Free-Tarif, Release-Profil-Nightlies beider Repos, Actions-Minuten, Windows-CI mit kaltem Cache über 15 Minuten, OP-6-Dokumentation, Doku-Abgleich, Lizenzentscheidung aus P0-WP1.4, veralteter Kommentar zu `GOLDEN_5EED`.
- Gliederung für den Vertragsentwurf WP1.2 (14 Abschnitte) liegt als Arbeitsgrundlage vor. Wichtigste Befunde für die nächste PO-Sitzung:
  - Der Entwurf muss auf dem Scheduler-Branch aufsetzen, weil beide die Abschnitte 3, 7, 8 und 9 von `crate-vertraege.md` ändern.
  - Auf dem Scheduler-Branch können Ressourcen wie `BulletPool` und `SpatialGrid` weder parallel geschrieben noch blockweise bearbeitet werden. Für die Budgets der Bullets (1,0 ms) und der Kollision (1,5 ms) braucht es dafür voraussichtlich eine Ergänzung.
  - Die Blockgröße ist vorläufig (1024). Goldene Hashes für Sigil und Kollision sollten erst nach dem Bench eingefroren werden.
  - Weitere Punkte: `u64`-Hashes als JSON-Zahlen verlieren in C# und JavaScript Genauigkeit; die Thread-Regel aus ADR-0006 braucht eine Ausnahme für den IO-Thread des Debug-Links; `RenderFrame` ist nicht `#[non_exhaustive]`, neue Kanäle wären also nicht rein additiv.

### Strang B — WP1.0 Paralleler Scheduler (fertig, Branch gepusht)

- Branch `p1/wp1.0-scheduler` (`f5c9bf5`, aufbauend auf `70a7fb0`), gepusht ohne PR und ohne CI-Lauf. Die PR-Beschreibung liegt bereit unter `<Arbeitsordner>\_wt\wp1.0-pr-body.md`.
- Entwurf: Drei unabhängige Entwürfe (zwei von Claude, einer von Codex) wurden bewertet; Grundlage ist der Entwurf mit der kleinsten Schnittstelle, ergänzt um die besten Teile der anderen (Panic-Behandlung je Aufgabe, Referenzmodus, `CommandBuffer::set`, feste Thread-Zahl N = 4 im Gate).
- Umgesetzt: Zugriffsdeklaration; `ParallelSystem` mit `parallel_system_fn`; Stufenplanung mit Diagnose `Schedule::stages()` und dem Referenzmodus `StageMode::Isolated`; Befehlspuffer je System (neu: `set`, Ressourcenbefehle, `append`); bei einem Panic wird die ganze Stufe verworfen und der Panic mit dem niedrigsten Index weitergereicht; `Executor`-Trait mit sequentieller und permutierter Implementierung; `World::par_blocks`/`par_blocks_mut` mit `QUERY_BLOCK_SIZE = 1024`; `derive_block_rng`; neue Crate `grimoire_exec` (rayon mit eigenem Pool); `AppBuilder::executor` in der Fassade; CI-Prüfung, dass keine Determinismus-Crate von rayon abhängt; Vertragstext in §1, §3 und §7–§10.
- Lokales Gate zweimal grün (vor und nach dem Review): fmt, Clippy für Windows, Linux und macOS, alle Tests mit Software-Adapter, rustdoc, Standalone-Gate, identische `clippy.toml`, unveränderte goldene Hashes, Hash-Gate mit 1, 2 und N Threads, kein neues `unsafe`, keine rayon-Abhängigkeit in Determinismus-Crates, goldener Spiel-Hash mit der Branch-Engine.
- Review: vier Linsen, sechs Befunde bestätigt (einer mittel — die Debug-Zugriffsprüfung beschuldigte bei zwei Welten auf einem Pool das falsche System —, fünf niedrig), alle behoben. Das Codex-Review fiel aus und wird nachgeholt.
- Offen: CI auf drei Plattformen (Minuten); der neue Golden `GOLDEN_PARALLEL_FINAL_HASH` ist nur lokal unter Windows gemessen; Timing-Schranken sind ungemessen (nur in einer Messsitzung); das Spiel-Harness-Gate mit 1, 2 und N Threads folgt erst nach dem Alpha-Tag. Acht vorläufige Entscheidungen und sieben PO-Fragen stehen im Dossier-Abschnitt „Freigabe WP1.0“.

### Anschlussarbeit — Vertragsentwurf WP1.2 (fertig, Branch gepusht)

- Branch `p1/wp1.2-contracts-draft` (`d19860f`, aufbauend auf dem Scheduler-Branch), gepusht ohne PR und ohne CI-Lauf (geprüft). Nur Dokumentation, kein Crate-Code.
- `crate-vertraege.md`: §1 Crate-Karte neu; §2 Regeln 9–15; neu §2a Trait-Entscheid je Subsystem und §2b Vertragsänderungs-Protokoll; §3 ergänzt (`grimoire_sigilc` in der Determinismus-Menge, abschließende Liste der Nicht-Sim-Threads); §6 Bühnen-Frame, Ebenenreihenfolge und Bullet-Kanal; §7 Blöcke über Nicht-Query-Daten, `SystemObserver`, Snapshot-Lesezugriff; §8 Replay v2, `restore_checked`, Vergabe der Zufallsstrom-Nummern; §9 Fassade mit Abhängigkeiten, Features, Spieler-Proxy und Mauszielen; neu §11 `grimoire_sigil`-Laufzeit v1 mit Hot-Swap und Content-Epoche, §12 Pack v1, §13 Debug-Protokoll v1, §14 Kollision v0, §15 Bench- und Golden-Master-Schemata. Jeder neue Abschnitt ist als „Entwurf WP1.2 — PO-Freigabe ausstehend“ markiert.
- Engine-ADR-Vorschlag 0008 „Crate-Map-Erweiterung P1“ (Status „Vorgeschlagen“).
- Spielseitiger Entwurf `docs/architektur/spiel-vertraege-entwurf.md` (Szenen, Bot-Profile, Harness-Bericht).
- Review mit vier Linsen: 21 Befunde bestätigt (drei hoch: `replace_unit` war aus der Fassade nicht erreichbar; der blockierende TCP-IO-Thread des Debug-Links konnte beim Beenden hängen; die Crate-Karte verbot die Kante, die `sigilc simulate` braucht), 4 widerlegt; alle bestätigten Befunde eingearbeitet.
- 37 vorläufige Entscheidungen und 17 PO-Fragen für die Vertragsfreigabe nach WP1.7 (unter anderem Hot-Swap-Verhalten fliegender Bullets, Breite des Content-Manifest-Hashes, harter Abbruch im Debug-Handshake, Budget-Gate für die dichte Kollisionsszene).

### Anschlussarbeit — Codex-Reviews und Sigil-Nachmessung (fertig)

- **Scheduler-Branch:** Codex fand zwei Punkte, beide gegengeprüft und bestätigt (niedrig): Exklusive Systeme, die in einem parallelen System laufen, erbten dessen Debug-Zugriffskontext; die Prüfung der Thread-Quelle übersah rayon hinter optionalen Features. Beide behoben (Regressionstest bzw. Negativkontrolle), lokales Gate grün, Branch jetzt `548a30a`.
- **Vertragsentwurf:** Codex fand 13 Punkte, 9 bestätigt und eingearbeitet (4 mittel): Im Golden-Master-Format fehlten Algorithmus-Versionen; Programmindex und Kaskadentiefe bei `BulletSpawn` waren unvalidiert; der Emitter-Index war nach einem Hot-Swap, der eine Unit verkleinert, unvalidiert; `PackReader::open` las die Datei vor der Größenprüfung. Drei neue PO-Fragen: verkleinernder Hot-Swap, Größenprüfung vor dem Laden über eine Ergänzung des P0-Traits `FileSystem`, Koordinatengrenze `MAX_COORD`. Der neue Scheduler-Stand ist in den Vertragsbranch gemergt (`5eebd0d`, ein Konflikt in §3 aufgelöst).
- **Sigil-Spike:** Codex schrieb G1–G3 in beiden Syntaxen, ohne Claudes Fassungen zu sehen; alle sechs Dateien prüfen fehlerfrei und ergeben dasselbe Modell. Die blinde Zweitbewertung der Fehlermeldungen weicht in keinem Fall um 2 oder mehr Punkte ab. Die Empfehlung `sigil 1` bleibt; Branch `d5956ed`.
- **Befund zur Werkzeugkette:** Das gemeinsame Target-Verzeichnis `grimoire/target` wurde auch von Scratch-Kopien genutzt, und Cargo hielt dadurch einmal ein fremdes Build-Artefakt für aktuell. Das Gate wurde nach erzwungenem Neubau wiederholt. Künftige Agentenläufe sollten eigene Target-Verzeichnisse verwenden.

### Anschlussarbeit — Kompilierprüfung des Vertragsentwurfs (fertig)

- Alle 33 Rust-Blöcke aus `crate-vertraege.md` wurden in einem eigenen Workspace (13 Crates, eigenes Target-Verzeichnis) gegen die Crates des Vertragsbranches kompiliert. Ergebnis nach den Korrekturen: `cargo check` und Clippy mit den Determinismus-Regeln fehlerfrei, alle Feature-Kombinationen grün, alle neuen Traits als `dyn` nutzbar, keine Crate-Kante verletzt §1. P0-Aufrufer (eigene `Renderer`- und `GamePlugin`-Implementierungen, `FileSystem`, Struct-Literale) kompilieren unverändert — die Erweiterungen sind additiv.
- 12 Befunde, 11 bestätigt und im Vertrag korrigiert (4 mittel): `sample_aim` und der Kameratyp in §9 waren nirgends definiert; `AssetEntry`/`AssetSource` widersprachen den Regeln 12 und 13; `FrameProfile` passte nicht zu `SystemInfo`; Nachrichtentypen und `to_stats` im Debug-Protokoll fehlten. Zwei neue PO-Fragen: Dev-Kanten für das Hash-Gate (§11.7) und Sigil-Typen im Prelude (§9.2).
- Die Prüfung liegt reproduzierbar als Spike `spikes/contract-check/` auf dem Branch (`f9765dd`). Sie prüft nur Signaturen und ist nicht WP1.3; die Skelette folgen erst nach der PO-Freigabe der Verträge.
- Codex konnte nicht mitprüfen: erneut nicht verfügbar.

### Anschlussarbeit — Fragenrunde zur Vertragsfreigabe (fertig)

- [`0002-vertragsfreigabe-wp1.2.md`](0002-vertragsfreigabe-wp1.2.md): 23 Rohfragen aus Entwurf, Review, Codex und Kompilierprüfung, zusammengeführt zu 21 Fragen (V-1 bis V-20 plus eine Pauschalfrage) in sechs Runden; 116 vorläufige Entscheidungen einzeln aufgelistet. Eine zweite Prüfung gegen den Vertragstext korrigierte 14 Stellen; das Frageformat ist maschinell geprüft (keine Fehler).
- Auswirkungen der Antworten aus Sammelsitzung A (P-3, P-7, P-8, P-9) auf einzelne Fragen sind vermerkt.

### Anschlussarbeit — Projekt-ADR-Vorschläge 0010 und 0011 (läuft)

- WP1.5: ADR 0010 „Sigil-Compiler-Hoheit“ und ADR 0011 „Schema-Codegen aus einer Quelle“ (OF-16.2) als Vorschläge mit neutralem Optionsvergleich und gegnerischer Prüfung; Entscheidung in Sammelsitzung B.

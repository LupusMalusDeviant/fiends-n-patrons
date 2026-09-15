# Agentenlauf 2026-09-15

- **Stand:** 2026-09-15 (Start)
- **Auftrag des PO:** Deploy-Key einrichten und prüfen, danach die nächsten Schritte autonom; Last über Codex (gpt-6-astra) verteilen; bis zur nächsten PO-Sitzung keine PO-Entscheidungen.
- **Bezug:** [Plan 0002](0002-phase-p1-sichtbarer-kern.md), Engine-ADR-0006

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

*(Strang B folgt)*

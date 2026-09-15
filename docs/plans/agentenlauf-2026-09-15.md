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

*(weitere Stränge folgen)*

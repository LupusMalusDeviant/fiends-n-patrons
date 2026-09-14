# ADR-0005: Voll deterministische Simulation (Fixed-Timestep, Seed-RNG, Snapshots)

- **Status:** Akzeptiert
- **Datum:** 2026-09-14
- **Entscheider:** Lupus Malus Deviant (PO)
- **Bezug:** [PRD-0002](../prd/0002-grimoire-engine-architektur.md), [PRD-0018](../prd/0018-teststrategie.md)

## Kontext

Auffällig viele gewünschte Features hängen an einer Eigenschaft: Seed-reproduzierbare Runs,
3s-Rewind-Item, Run-Suspend, Todesscreen-Pattern-Replay, Golden-Master-Tests, Bot-Balancing —
und als Fernziel Online-Co-op via Lockstep. Alle sind Konsumenten von Determinismus. Die Frage
war, wie hart die Garantie ausfällt.

## Anforderungen

- Gleicher Seed + gleiche InputFrames ⇒ identischer Verlauf (mindestens pro Plattform, Ziel: plattformübergreifend).
- Kompletter Sim-Zustand snapshot- und wiederherstellbar (bit-identische Fortsetzung).
- Rendering darf variabel schnell sein (144+ FPS), ohne die Sim zu beeinflussen.

## Optionen

1. **Nicht deterministisch (variable Timesteps)** — einfachster Start, aber Rewind/Replay/Seeds werden Attrappen; Fernziel Lockstep unmöglich.
2. **Best-Effort-Determinismus** — Fixed-Timestep + Seed-RNG ohne harte Garantie; driftende Replays vergiften Golden-Master (Flaky-Tests).
3. **Voll deterministisch (gewählt)** — Determinismus als getestete Engine-Garantie mit Disziplinregeln und CI-Beweisen.

## Entscheidung

Option 3. Die Sim läuft mit Fixed-Timestep (60 Hz), konsumiert ausschließlich serialisierte
InputFrames und ein seedbares Stream-RNG (`grimoire_sim`). Disziplinregeln (verbindlich, per
Lint/Review durchgesetzt, PRD-0018 FR-09):

- Kein Wallclock-, Datei- oder OS-Zustand in Sim-Systemen; Zeit = Tick-Zähler.
- Keine Iteration über unsortierte Hash-Container in der Sim; deterministische Entity-Ordnung.
- `thread_rng`/globale RNGs verboten; RNG-Streams pro System, vom Seed abgeleitet.
- Parallelität in der Sim nur mit fester Reduktionsreihenfolge (bis dahin: single-threaded Scheduler).
- Rendering/Audio lesen Sim-Zustand, schreiben nie zurück.

Cross-Plattform-Bit-Gleichheit (f32-Frage) wird per Spike verifiziert (OF-2.1); scheitert sie,
wird per Folge-ADR auf Fixed-Point für Sim-Positionen ODER „Garantie pro Plattform" entschieden —
die Garantie **pro Plattform** ist unverhandelbar.

## Konsequenzen

- (+) Rewind, Suspend, Replays, Golden-Master und Bot-Balancing werden triviale Konsumenten einer Kernfähigkeit; Debugging wird reproduzierbar („Seed + Log anhängen").
- (+) Lockstep-Co-op bleibt als Fernziel technisch offen.
- (−) Dauerhafte Disziplinkosten in jedem Sim-System (Reviews, Lints, Tests); manche Rust-Idiome (HashMap-Iteration) sind in der Sim tabu.
- (−) Fixed-Timestep erfordert Interpolations-Schicht im Renderer — einmalige Architekturkosten, bereits eingeplant (PRD-0002 FR-04).

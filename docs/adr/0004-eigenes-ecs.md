# ADR-0004: Eigenes ECS statt Fertig-Bibliothek

- **Status:** Akzeptiert
- **Datum:** 2026-09-14
- **Entscheider:** Lupus Malus Deviant (PO)
- **Bezug:** [PRD-0002](../prd/0002-grimoire-engine-architektur.md), [ADR-0005](0005-voll-deterministische-simulation.md)

## Kontext

10.000 Bullets, 100 Gegner, Partikel-Logik und deterministische Systeme verlangen datenorientierte
Speicherung und kontrollierte Ausführungsreihenfolge. Reife Rust-ECS-Bibliotheken existieren
(hecs, flecs-rs, bevy_ecs) — aber das Projekt ist explizit ein From-scratch-Lernprojekt, und die
Determinismus-/Snapshot-Anforderungen greifen tief in die ECS-Interna.

## Anforderungen

- Deterministische System-Ausführungsreihenfolge und Iteration (ADR-0005).
- Voll-Snapshots des gesamten Welt-Zustands als Kern-Feature (Rewind/Suspend/Replay) — muss ins Speicherlayout hineindesignt sein.
- Cache-freundliche Massen-Iteration (SoA/Archetypen) für das Bullet-Budget.
- Lernwert: ECS-Bau ist eines der erklärten Lernziele.

## Optionen

1. **bevy_ecs/hecs einbetten** — spart Monate, aber Snapshot-/Determinismus-Garantien müssten um fremde Interna herumgebaut werden; From-scratch-Anspruch verletzt.
2. **Klassisches OOP + Manager** — vertrauter Einstieg, führt bei 10k-Entities ohnehin zur Datenorientierung, nur später und schmerzhafter.
3. **Eigenes Archetyp-ECS (gewählt)** — Welt, Komponenten-Speicher, Queries, Scheduler selbst; Snapshot-Serialisierung als Entwurfsziel Nummer eins.

## Entscheidung

Option 3. `grimoire_ecs` wird ein eigenes, archetyp-basiertes ECS mit deterministischem Scheduler.
Der Funktionsumfang bleibt bewusst schlank (keine Relationen-Engine, keine Query-Magie über das
Gebrauchte hinaus): Es ist das ECS **dieses** Spiels. Start single-threaded-deterministisch;
Parallelisierung nur mit fester Reduktionsreihenfolge (OF-2.2 klärt den Zeitpunkt).

## Konsequenzen

- (+) Snapshots, Hashing (Golden-Master-Diagnostik) und deterministische Iteration sind Kern-Designziele statt Nachrüstungen.
- (+) Maximaler Lerneffekt; keine Fremd-Breaking-Changes im Herzstück.
- (−) Wochen an Grundlagenarbeit vor dem ersten Gameplay; Risiko von Eigenbau-Bugs im Fundament — Gegenmittel: die ECS-Testsuite und Property-Tests entstehen mit dem ECS selbst (PRD-0018 FR-01).
- (−) Performance-Reife eines optimierten Fertig-ECS wird anfangs nicht erreicht — akzeptiert; Budgets (PRD-0002) sind die Messlatte, nicht Bibliotheks-Benchmarks.

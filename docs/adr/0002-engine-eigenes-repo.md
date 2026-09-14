# ADR-0002: Grimoire als eigenständige Engine im eigenen Repo (from scratch, SemVer)

- **Status:** Akzeptiert
- **Datum:** 2026-09-14
- **Entscheider:** Lupus Malus Deviant (PO)
- **Bezug:** [PRD-0002](../prd/0002-grimoire-engine-architektur.md), [PRD-0017](../prd/0017-plattform-ci-distribution.md)

## Kontext

Der PO will maximale Fertigungstiefe als Lernziel: keine Fertig-Engine, kein Fertig-ECS, keine
Physik-Lib. Gleichzeitig gilt Interface-First als Architekturprinzip. Die Frage war, wie stark
Engine und Spiel getrennt werden — vom Modul im selben Repo bis zum eigenständigen Produkt.

## Anforderungen

- „Keine Spielentwicklung, die eine Engine braucht, ohne die Engine" (O-Ton PO): Die Engine muss allein stehen können.
- Erzwungene, nicht nur vereinbarte Layer-Grenzen (Game → Engine → Platform, nie rückwärts).
- Kontrollierte Upgrade-Momente statt permanenter Breaking-Change-Durchschläge.

## Optionen

1. **Monorepo, Engine als Crate-Gruppe** — einfachste Iteration, aber die Grenze erodiert erfahrungsgemäß; Standalone-Anspruch unbeweisbar.
2. **Eigenes Repo, Spiel folgt main** — echte Trennung, aber Engine-HEAD-Brüche schlagen sofort ins Spiel durch.
3. **Eigenes Repo + SemVer-Releases, Spiel pinnt Tags (gewählt)** — Engine ist Produkt mit Versionsvertrag; Spiel hebt Versionen bewusst per Commit.

## Entscheidung

Option 3. `grimoire` ist ein eigenes Repo mit eigener CI, eigenen Beispielen, eigenen Tests und
getaggten SemVer-Releases. Das Spiel-Repo (`Prototype`) konsumiert die Engine über gepinnte
Tags (Mechanik: OF-17.1, empfohlen Cargo-git-Dependency mit Tag). Die Engine kennt das Spiel nicht;
Engine-CI läuft ohne jede `fnp_*`-Referenz (Standalone-Gate, PRD-0002 FR-01).

## Konsequenzen

- (+) Layer-Regeln werden vom Compiler und der Repo-Grenze gehütet; die Engine ist portfolio-fähig als eigenes Produkt.
- (+) Breaking Changes werden zu bewussten, dokumentierten Upgrade-Commits (CHANGELOG-Pflicht).
- (−) Overhead: zweigleisige CI, Release-Disziplin, gelegentlich „Engine-Feature erst taggen, dann nutzen" — für schnelle Iterationsphasen wird mit Pfad-Override lokal gearbeitet (cargo patch), gemergt wird nur gegen Tags.
- (−) Gefahr der vorauseilenden Generalisierung („Engine für alle Fälle") — Gegenmittel: Engine-Features entstehen nur auf konkreten Bedarf des Spiels (PRD-0002 Non-Goals).

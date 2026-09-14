# ADR-0006: Sigil-Daten-DSL für Patterns, kein eingebettetes Scripting

- **Status:** Akzeptiert
- **Datum:** 2026-09-14
- **Entscheider:** Lupus Malus Deviant (PO)
- **Bezug:** [PRD-0004](../prd/0004-sigil-bullet-system.md), [PRD-0016](../prd/0016-tooling-suite.md)

## Kontext

Der Content-Kern des Spiels (Bullet-Patterns, Wellen, Verhalten) braucht eine Definitionsebene
außerhalb von Rust — für Iterationstempo, Tooling und massenhafte (auch KI-gestützte) Generierung.
Zur Wahl standen eingebettete Skriptsprachen (Lua/Rhai), reine Rust-Definitionen oder eine
deklarative Daten-DSL.

## Anforderungen

- Hunderte Patterns ohne Recompile erstell-, validier- und hot-swappbar.
- Deterministische, budgetierte Ausführung (10k Bullets, ≤ Sim-Budget) — keine unbeschränkte Logik pro Bullet.
- Visuell editierbar (Sigil-Editor) und statisch prüfbar (CI-Gate).
- Maschinell generierbar mit verlässlicher Validierung (Agenten-Workflow).

## Optionen

1. **Skriptsprache (Lua/Rhai)** — maximale Ausdruckskraft, aber: VM-Integration, Debugging-Aufwand, schwer statisch zu validieren, Determinismus- und Budget-Garantien pro Skript kaum beweisbar.
2. **Alles in Rust** — volle Compiler-Sicherheit, aber jede Pattern-Iteration braucht Build+Neustart; Tooling-Editierbarkeit praktisch null.
3. **Deklarative Daten-DSL „Sigil" (gewählt)** — komponierbare Bausteine + Modifikatoren + Transformationen als Daten; Interpreter mit festem Kostenmodell; Rust-`BulletBehavior`-Trait als seltener Escape-Hatch.

## Entscheidung

Option 3. Patterns, Wellen und verwandter Content sind Daten (`.sigil` u.a.), kompiliert zu einem
Binärformat und interpretiert von `grimoire_sigil`. Es gibt **keine** eingebettete Skript-VM.
Nicht Ausdrückbares wandert als benanntes Rust-Plugin hinter den `BulletBehavior`-Trait
(Richtwert: < 10% der Patterns nutzen den Escape-Hatch; wird er überschritten, ist das ein
Signal, die DSL zu erweitern — per Folge-ADR).

## Konsequenzen

- (+) Statische Validierung als CI-Gate; Hot-Swap < 1 s; visuelles Tooling wird machbar; Determinismus und Budgets sind Eigenschaften des Interpreters, nicht jedes einzelnen Contents.
- (+) Offene, dokumentierte Formate ⇒ Modding-by-documentation fällt gratis ab.
- (−) DSL-Design ist ein eigenes Projekt (Syntax, Compiler, Interpreter, Doku) mit Versionierungspflicht.
- (−) Ausdrucksgrenzen sind real: Manche Boss-Ideen erfordern Trait-Plugins oder DSL-Erweiterungen — bewusst als kontrollierter Prozess statt Skript-Wildwuchs.

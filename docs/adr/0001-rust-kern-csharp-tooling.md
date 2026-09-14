# ADR-0001: Rust als Kernsprache, C# für die Tooling-Suite

- **Status:** Akzeptiert
- **Datum:** 2026-09-14
- **Entscheider:** Lupus Malus Deviant (PO)
- **Bezug:** [PRD-0000 §2 E01](../prd/0000-index-fiends-n-patrons.md), [PRD-0016](../prd/0016-tooling-suite.md)

## Kontext

Engine und Spiel werden from scratch gebaut (ADR-0002); Ziel sind 10.000 deterministische Bullets
bei 60 FPS auf drei Desktop-Plattformen, später Mobile. Parallel entsteht eine umfangreiche
Editor-/Pipeline-Werkzeugkette. Zur Wahl standen .NET und Rust als Kernsprache (Vorgabe des PO).

## Anforderungen

- Vorhersagbare Frame-Zeiten ohne GC-Pausen bei Massen-Entities (Sim-Budget ≤ 4 ms).
- Erstklassiges Cross-Compiling Win/Mac/Linux + Mobile-Fähigkeit.
- Produktive UI-Entwicklung für Desktop-Werkzeuge.
- Lernwert für den PO als erklärtes Projektziel.

## Optionen

1. **Alles Rust** — ein Ökosystem, aber Desktop-Tool-UIs in Rust (egui et al.) sind deutlich zäher für Editor-Suiten.
2. **Alles .NET** — schnellste Entwicklung, aber GC-Management bei 10k+-Entity-Simulation wird zum Dauerthema; from-scratch-Engine gegen den Strich.
3. **Rust-Kern + C#-Tooling (gewählt)** — Engine/Spiel in Rust (Performance, Determinismus, Cross-Compiling), Werkzeuge in C#/Avalonia (UI-Produktivität); Kopplung über Dateiformate + IPC statt FFI.

## Entscheidung

Option 3. Grimoire und Fiends n Patrons entstehen in Rust; die gesamte Editor-/Pipeline-Suite in
C# mit Avalonia (ADR-0008). Die Grenze verläuft über wohldefinierte Datenformate und das
Debug-IPC-Protokoll — bewusst **kein** In-Process-FFI.

## Konsequenzen

- (+) Jede Seite nutzt die Stärke ihres Ökosystems; die IPC-Grenze erzwingt saubere, dokumentierte Formate (nützt auch Modding-by-documentation).
- (+) Kein GC in der Frame-Loop; Cross-Compiling-Pfad für Mobile bleibt realistisch.
- (−) Zwei Toolchains (cargo + dotnet) in CI und lokal; Schema-Synchronisation Rust↔C# braucht eine Lösung (OF-16.2, Codegen empfohlen).
- (−) Kontextwechsel-Kosten für Entwickler/Agenten zwischen zwei Sprachen — gemildert durch klare Repo-/Aufgaben-Trennung.

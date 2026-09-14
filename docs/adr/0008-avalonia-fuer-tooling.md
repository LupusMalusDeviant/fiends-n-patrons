# ADR-0008: Avalonia als UI-Framework der Tooling-Suite

- **Status:** Akzeptiert
- **Datum:** 2026-09-14
- **Entscheider:** Lupus Malus Deviant (PO)
- **Bezug:** [PRD-0016](../prd/0016-tooling-suite.md), [ADR-0001](0001-rust-kern-csharp-tooling.md)

## Kontext

Die Tooling-Suite (Sigil-Editor, Stage-Editor, Balancing-Dashboard, Audio-Werkstatt u.a.) entsteht
in C# (ADR-0001). Entwickelt wird primär auf Windows, aber Engine und Spiel zielen auf
Win/Mac/Linux — Werkzeuge sollten überall dort laufen, wo entwickelt und getestet wird.

## Anforderungen

- Desktop-UI mit Canvas-lastigen Editoren (Pattern-Preview, Kurven, Graphen, Timeline).
- Cross-Platform Win/Mac/Linux ohne Doppel-Implementierung.
- Reifes MVVM-/XAML-Modell für schnelle, wartbare Editor-Entwicklung.

## Optionen

1. **WPF/WinUI (Windows-only)** — reichstes Ökosystem, aber Tools liefen nur auf Windows; Mac-/Linux-Entwicklungssessions blieben werkzeuglos.
2. **Blazor/Web-UI lokal** — flexibel, aber Canvas-intensive Editoren (60-FPS-Pattern-Preview, Scrubbing) werden im Browser-Stack mühsamer; zusätzlicher Prozess-/Hosting-Klimbim.
3. **Avalonia (gewählt)** — XAML/MVVM nahe an WPF, echtes natives Cross-Platform-Rendering (Skia), gute Canvas-Performance.

## Entscheidung

Option 3. Die gesamte Suite entsteht als eine Avalonia-Solution (Repo-Ort: OF-16.1, Empfehlung
`grimoire/tools/`). Gemeinsame Basis-Bibliotheken: Live-Link-Client, Formate/Schemata,
Editor-Shell (Docking, Projekt-Kontext); die Einzel-Tools sind Module dieser Shell.

## Konsequenzen

- (+) Ein UI-Stack für alle Werkzeuge auf allen Dev-Plattformen; WPF-Wissen überträgt sich.
- (+) Skia-Canvas trägt die Pattern-/Kurven-Editoren ohne Browser-Umweg.
- (−) Avalonia-Ökosystem ist kleiner als WPF (weniger Fertig-Controls) — für Spezial-Controls (Kurveneditor, Node-Graph) ist Eigenbau eingeplant.
- (−) Kein Mobile-/Web-Zugriff auf die Tools — irrelevant, Zielgruppe ist der Entwickler-Desktop.

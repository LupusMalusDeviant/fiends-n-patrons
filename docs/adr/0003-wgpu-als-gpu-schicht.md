# ADR-0003: wgpu als GPU-Abstraktionsschicht (Renderer-Logik komplett eigen)

- **Status:** Akzeptiert
- **Datum:** 2026-09-14
- **Entscheider:** Lupus Malus Deviant (PO)
- **Bezug:** [PRD-0002](../prd/0002-grimoire-engine-architektur.md), [PRD-0003](../prd/0003-rendering-und-art.md)

## Kontext

„From scratch" braucht eine Untergrenze: Irgendwo beginnt die Plattform. Der Renderer soll
vollständig selbst entstehen (Toon-Pass, Clustered Lighting, Instancing, Post-FX, Frame-Graph) —
die Frage war, ob darunter rohe native APIs (Vulkan/Metal/DX12) liegen oder eine dünne
portable Schicht.

## Anforderungen

- Vier Zielplattform-Familien (Windows, macOS, Linux, später iOS/Android) mit einem Shader-Dialekt.
- Der Lernwert soll in Renderer-Architektur fließen, nicht in API-Boilerplate ×3.
- Solo-Hobby-Zeitbudget: erste sichtbare Ergebnisse in Wochen, nicht Quartalen („Sichtbares zuerst").

## Optionen

1. **Direkt Vulkan (ash) + MoltenVK** — maximale Tiefe, aber wochenlange Infrastruktur bis zum Dreieck, Mac/iOS über Translationsschicht mit eigenen Fallen.
2. **Eigene RHI mit 3 nativen Backends** — das AAA-Lernprogramm; realistisch viele Monate reine Abstraktionsarbeit vor jedem Spiel-Pixel.
3. **wgpu als GPU-Schicht (gewählt)** — portable, moderne API (WGSL), Backends Vulkan/Metal/DX12 inklusive; alles darüber (Frame-Graph, Passes, Materialien, Culling, Instancing) bleibt Eigenbau.

## Entscheidung

Option 3. `grimoire_gpu` kapselt wgpu; `grimoire_render` implementiert den kompletten Renderer
selbst. Kein Engine-Code oberhalb von `grimoire_gpu` spricht wgpu-Typen direkt an (Austauschbarkeit
als Trait-Vertrag — sollte je der Wunsch nach einem nativen Backend entstehen, ist die Schnittstelle da).

**Präzisierung (P0, 2026-09-14):** Die Kapselungsgrenze liegt am datenorientierten
Renderer-Vertrag. wgpu-Typen sind innerhalb von `grimoire_gpu` und `grimoire_render` sichtbar;
oberhalb davon (Fassade, Spiel) nie. Eine zusätzliche RHI-Hülle zwischen den beiden Crates hätte
kaum Wert, weil wgpu selbst bereits die Hardware-Abstraktion ist. Details:
Engine-Repo `grimoire/docs/adr/0002-gpu-kapselungsgrenze.md`.

## Konsequenzen

- (+) Ein Shader-Dialekt (WGSL) für alle Plattformen; Mobile-Pfad ist derselbe Code.
- (+) Lernenergie fließt in die interessanten Probleme (Clustered Lights, Toon, 10k-Instancing, Frame-Graph).
- (−) wgpu-Versionssprünge sind gelegentlich Breaking — gemildert durch Kapselung in `grimoire_gpu` und gepinnte Versionen.
- (−) Weniger „bare metal"-Tiefe als Roh-Vulkan; bewusst akzeptiert. Ein späteres natives Backend bleibt über den Trait-Vertrag möglich (kein v1.0-Ziel).

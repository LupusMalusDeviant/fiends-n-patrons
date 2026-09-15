# PRD-0001: Vision & Scope — Fiends n Patrons

- **Status:** Entwurf
- **Datum:** 2026-09-14
- **Autor:** Lupus Malus Deviant (PO) / Claude (Ausarbeitung)
- **Stakeholder:** Lupus Malus Deviant (PO), Coding-Agenten (Umsetzung)
- **Index:** [PRD-0000](0000-index-fiends-n-patrons.md)

## Problem / Motivation

Der PO will sein **erstes vollwertiges Spiel** entwickeln — nicht als Klick-Zusammenbau in einer
Fertig-Engine, sondern als **Lern- und Portfolioprojekt mit maximaler Fertigungstiefe**: eigene
Engine (Rust, from scratch), eigenes Tooling (C#), alle Assets generiert. Ohne ein verbindliches
Zielbild zerfasert ein solches Projekt erfahrungsgemäß in Tech-Demos; dieses PRD fixiert das Spiel,
für das die ganze Technik gebaut wird ("Do-Nothing-Szenario": Engine ohne Spiel = totes Repo).

Marktdruck existiert nicht (E19: Hobby, offenes Ende) — der Gegner ist Scope-Drift und
Motivationsverlust. Deshalb: klare Phasen, früh Sichtbares, ein unverhandelbares Zielbild.

## Ziele

- Ein vollständig spielbarer **Mini-Run-Vertical-Slice** (Phase P3): 1 Stage mit Raum-Kette, Upgrades, Shop, Altar, Boss — auf Grimoire, ohne Fremd-Engine.
- **v1.0 Desktop** (Phase P6): kompletter Run (2–3 Stages, ~20 Min), 5 Patrone, 3 Bosse, 2 Charaktere, DE+EN, signierte Builds für Win/Mac/Linux.
- Die Engine **Grimoire** ist zu jedem Zeitpunkt standalone lauffähig (eigenes Repo, eigene Beispiele/Tests, SemVer) — messbar: Engine-CI grün ohne das Spiel-Repo.
- Jede Kern-Innovation des Designs (Melee-Bullet-Hell, Patron-Zorn, Stage-Verwandlung) ist im Slice bzw. P4 erlebbar, nicht nur spezifiziert.

## Non-Goals

- **Kein kommerzieller Launch-Druck:** Verkauf (Steam/Mobile-Stores) ist Phase-2+-Option, kein v1.0-Ziel; zunächst Builds für Freunde, ohne Store (öffentlich abrufbar).
- **Kein Multiplayer in v1.0:** Lokaler Co-op später denkbar, Online-Co-op nur Fernziel (E16). Es wird keine Netzwerk-Schicht vor P7 gebaut — nur die Determinismus-Tür offen gehalten.
- **Keine Fremd-Engine, kein Fertig-ECS, keine Physik-Lib:** Lerneffekt ist Produktbestandteil (E02, E04, E10).
- **Kein Editor-im-Spiel:** Alle Werkzeuge leben in der C#-Tooling-Suite (PRD-0016).
- **Keine wählbaren Schwierigkeitsgrade** (E14) und **kein Trainingsmodus** — das Spiel selbst ist die Schule.

## Zielgruppen / Personas

### Persona A: „Der Erbauer" (der PO selbst)
- Entwickelt als Hobbyprojekt; will jedes Subsystem verstehen, weil er es (mit Agenten) selbst gebaut hat.
- Pain Point: Fertig-Engines verstecken die interessanten Probleme; Tutorials enden vor der Ziellinie.

### Persona B: „Der Freundeskreis-Tester"
- Bekommt Nightly-/Release-Builds über einen direkten Link (öffentlich abrufbar, ohne Store); spielt Sessions von 20–40 Minuten, kennt Roguelites (Hades, Gungeon), nicht zwingend Danmaku.
- Pain Point: Unfaire, unlesbare Bullet-Hells frustrieren; braucht faire Telegraphie und den „noch ein Run"-Sog.

### Persona C: „Der Coding-Agent"
- Setzt PRDs/Pläne in Code um; braucht eindeutige, maschinenlesbare Vorgaben, Diagramme, feste Entscheidungsregister und Testkriterien.
- Pain Point: implizites Wissen in Köpfen statt in Dokumenten.

## Funktionale Anforderungen

| ID | Anforderung | Priorität |
|----|-------------|-----------|
| FR-01 | Ein Run besteht aus 2–3 prozedural generierten Stages und dauert im Schnitt ~20 Minuten. | Must |
| FR-02 | Der Spieler wählt vor dem Run: Charakter (Bewaffnungs-Preset + Signature-Ultimate) und ggf. Ultimate-Perk. | Must |
| FR-03 | Im Run kann genau ein Pakt mit einem von 5 Patronen geschlossen werden; er ist für den Run bindend. | Must |
| FR-04 | Tod ist endgültig (Permadeath); Fortschritt fließt in Meta-Systeme (Unlocks, Reputation). | Must |
| FR-05 | Ein laufender Run ist unterbrech- und fortsetzbar (Run-Suspend, siehe PRD-0015). | Must |
| FR-06 | v1.0 enthält 2 spielbare Charaktere mit kontrastierenden Spielstilen. | Must |
| FR-07 | Läufe sind über Seeds exakt reproduzierbar (Grundlage: E05). | Must |
| FR-08 | Das Spiel läuft in v1.0 nativ auf Windows, macOS und Linux. | Must |
| FR-09 | Die Architektur hält lokalen Co-op offen (Input-Slots, keine Singleton-Spieler-Annahmen im Kern). | Should |
| FR-10 | Alle Datenformate (Sigil, Wellen, Items) sind offen dokumentiert (Modding by documentation, E17). | Should |

## Nicht-Funktionale Anforderungen

- **Performance:** 60 FPS fix auf Desktop-Mittelklasse (Referenz: GTX 1060 / Apple M1) bei 10k Bullets; Rendering entkoppelt, 144+ FPS-fähig (Details PRD-0017).
- **Fairness:** Jeder Treffer muss aus Spielersicht erklärbar sein (Telegraphie-Grammatik PRD-0007, Lesbarkeits-Regeln PRD-0003).
- **Projektnachhaltigkeit:** Jede Phase endet mit einem lauffähigen, getesteten Zustand (CI grün, Golden-Master aktuell); keine "lange dunkle Integrationsphase".

## User Stories

- **US-01:** Als Erbauer möchte ich nach Phase P1 bereits 10.000 Bullets über den Schirm fließen sehen, damit die Motivation die lange Engine-Strecke trägt.
- **US-02:** Als Freundeskreis-Tester möchte ich einen Run nach ~20 Minuten mit einem klaren Ergebnis (Sieg/hämischer Nachruf + Statistik) abschließen, damit sich jede Session rund anfühlt.
- **US-03:** Als Coding-Agent möchte ich jede Grundsatzentscheidung im Entscheidungsregister (PRD-0000 §2) nachschlagen können, damit ich nie raten oder umentscheiden muss.
- **US-04:** Als Erbauer möchte ich, dass die Engine ohne das Spiel kompiliert, testet und Beispiele rendert, damit sie ein echtes eigenständiges Produkt ist.

## Akzeptanzkriterien / Success Metrics

- Phase P3 („Mini-Run") ist spielbar: ein externer Tester schafft ohne mündliche Erklärung einen kompletten Stage-Durchlauf; alle FR-Must dieses PRDs, die den Slice betreffen (FR-01 reduziert auf 1 Stage, FR-04, FR-05, FR-07), sind erfüllt und testabgedeckt.
- v1.0-Kriterium: alle FR-Must erfüllt; CI-Matrix (Win/Mac/Linux) grün; ein kompletter Run per Headless-Bot in <5 Min Simulationszeit reproduzierbar durchspielbar.
- Engine-Standalone-Kriterium: `grimoire`-Repo baut + testet grün ohne jede Referenz auf `fnp_*`-Crates, dauerhaft ab P0.
- Motivations-Proxy (weich): pro Phase mindestens ein „zeigbares" Artefakt (GIF/Clip/Build), das ohne Erklärung beeindruckt.

## Offene Fragen

- **OF-1.1:** Zweiter Charakter — welcher Spielstil-Kontrast konkret (schwer/langsam vs. schnell/fragil)? Klärung: Design-Session vor P4, festgehalten in PRD-0005.
- **OF-1.2:** Wird der Freundeskreis-Test formalisiert (Feedback-Formular im Spiel?) — Entscheidung vor P6.

## Referenzen

- [PRD-0000 Index](0000-index-fiends-n-patrons.md) — Entscheidungsregister, Phasenplan
- Genre-Referenzen (Design-Sprache): Hades (Meta/Story-Rhythmus), Enter the Gungeon (Arena-Gefühl), Touhou (Boss-Danmaku), Nuclear Throne (Tempo)

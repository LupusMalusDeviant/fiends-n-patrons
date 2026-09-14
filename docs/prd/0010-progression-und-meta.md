# PRD-0010: Progression im Run & Meta-Progression

- **Status:** Entwurf
- **Datum:** 2026-09-14
- **Autor:** Lupus Malus Deviant (PO) / Claude (Ausarbeitung)
- **Stakeholder:** Lupus Malus Deviant (PO), Coding-Agenten
- **Index:** [PRD-0000](0000-index-fiends-n-patrons.md)

## Problem / Motivation

Zwei Progressionsuhren müssen ineinandergreifen: **im Run** (Build wächst über ~20 Minuten aus
Drops, Shop und Altären zu etwas Eigenem) und **zwischen Runs** (Unlocks + Patron-Reputation geben
dem Scheitern Sinn — ohne Machtinflation). Läuft die Run-Ökonomie leer, wird der Hybrid zäh;
wächst die Meta in Stats, stirbt der Skill-Vergleich (bewusst dagegen entschieden: Unlocks
erweitern den **Pool**, nie die Basiswerte).

## Ziele

- Run-Progression aus drei Quellen mit klaren Rollen: **Mob-Drops** (Tempo), **Shop zwischen Stages** (Planung), **Altäre** (Patron-Achse + Risiko).
- **Explizite Synergien** (E-Antwort): benannte Kombo-Effekte mit Entdecker-Momenten.
- Meta ohne Power-Creep: **permanente Unlocks** (Pool-Erweiterung) + **Patron-Reputation** (Beziehung, Content-Freischaltung).
- Jede Ökonomie-Stellschraube ist Daten + im Balancing-Dashboard simulierbar.

## Non-Goals

- Keine permanenten Stat-Upgrades (kein Hades-Spiegel) — bewusste Entscheidung für fairen Skill-Vergleich über Seeds.
- Kein Echtgeld, keine zweite Premium-Währung, kein Battle-Pass — nichts dergleichen, je.
- Keine Item-Rarity-Farbleiter als Kernsystem (kein „Legendary-Gefühl über Farbe"); Wert entsteht über Synergie-Potenzial.
- Kein Auto-Levelup-System (kein XP-Balken wie Vampire Survivors) — Progression kommt aus Raum-Belohnungen, nicht aus Kill-XP.

## Ökonomie-Modell

```mermaid
graph TD
    KILLS[Gegner-Kills] --> DROPS[Drops: Upgrades klein, Heilung, Items, Währung]
    ROOMS[Raum-Clear] --> REWARD[Raum-Belohnung: Upgrade-Wahl aus 3]
    DROPS --> GOLD[Run-Währung „Obol"]
    GOLD --> SHOP[Shop zwischen Stages:<br/>Upgrades, Items, Bomben, Heilung]
    ALTAR[Altäre 1-2/Stage] --> PACT[Pakt-Level:<br/>Patron-Achsen-Upgrades]
    REWARD & SHOP & PACT --> BUILD[Build des Runs]
    BUILD --> SYN[Explizite Synergien<br/>benannt, entdeckbar]
    RUNEND[Run-Ende Sieg/Tod] --> META[Meta: Unlock-Punkte „Seelenglut" + Patron-Reputation]
    META --> POOL[Pool-Erweiterung: Waffen, Ultis, Items,<br/>Charakter-Freischaltungen, Patron-Content]
    POOL -.erweitert künftige.-> DROPS & SHOP
```

*(Währungsnamen „Obol"/„Seelenglut" = Arbeitsstand, final mit PRD-0011.)*

## Funktionale Anforderungen

### Im Run

| ID | Anforderung | Priorität |
|----|-------------|-----------|
| FR-01 | Upgrade-Wahl: nach definierten Raum-Clears erscheint eine Wahl aus 3 Optionen (gewichtete Ziehung aus freigeschaltetem Pool + Patron-Achse ab Pakt). | Must |
| FR-02 | Mob-Drops: Währung, seltene Klein-Upgrades, Heilung, Einmal-Items — Drop-Tabellen als Daten, seed-deterministisch. | Must |
| FR-03 | Shop zwischen Stages: Angebot aus 4–6 Slots (Upgrades, Items, Bomben-/HP-Refill), Preise skalieren mit Stage; Reroll-Mechanik optional (Could). | Must |
| FR-04 | Altar-Interaktion levelt den Pakt und öffnet Patron-Achsen-Upgrades (PRD-0006 FR-03); Altäre sind die einzige Quelle der Achsen-Vertiefung. | Must |
| FR-05 | Upgrades modifizieren das Kit tief (E-Antwort „tief modifizierbar"): Melee-Form/Procs, Skillshot-Verhalten, Dash-/Graze-/Ulti-Regeln — als stapelbare Modifikatoren auf Kit-Parametern (PRD-0005 FR-14). | Must |
| FR-06 | Explizite Synergien: kuratierte Kombinationsliste; bei Erfüllung wird die Synergie benannt eingeblendet und im Run-Inventar erklärt; v1.0-Ziel ≥ 15 Synergien. | Must |
| FR-07 | Einmal-Item-Ökonomie: 2 Slots (PRD-0005 FR-06); Items droppen/kaufbar; v1.0-Pool ≥ 8 Items (Healthpot, Slowdown, 3s-Rewind + weitere). | Must |
| FR-08 | Run-Inventar-Übersicht: jederzeit einsehbar — aktive Upgrades, Synergien, Pakt-Stand, Item-Slots (UI in PRD-0014). | Must |

### Meta

| ID | Anforderung | Priorität |
|----|-------------|-----------|
| FR-09 | Unlock-System: Runs verdienen Unlock-Punkte (leistungsabhängig); Punkte schalten neue Pool-Einträge frei (Waffen-Varianten, Ultimates, Items, Synergien, 2. Charakter falls nicht Start-Content). | Must |
| FR-10 | Signature-Ultimate-Freischaltung: definierte Erfolge (z.B. „Boss 2 mit Charakter A besiegt") machen As Signature-Ulti für Charakter B wählbar (PRD-0005 FR-17). | Must |
| FR-11 | Patron-Reputation: pro Patron ein Beziehungsstand, wächst durch Runs mit diesem Pakt; Stufen schalten frei: neue Pakt-Stufen/Achsen-Optionen, Hub-Dialoge, kosmetische Gunstzeichen. | Must |
| FR-12 | Keine Meta-Freischaltung erhöht Basiswerte des Spielers (Verfassungs-Regel; Code-Review-Kriterium). | Must |
| FR-13 | Meta-Zustand ist Teil des Profils (PRD-0015); Unlock-Regeln sind Daten. | Must |
| FR-14 | Lokale Statistiken: Bestzeiten, Kills, Grazes, Paraden, Synergie-Entdeckungen, pro Patron/Charakter — Grundlage für Todesscreen und Statistik-Panel. | Should |

## Nicht-Funktionale Anforderungen

- **Ökonomie-Balance messbar:** Standard-Bot-Profile erreichen Stage-3-Boss mit definiertem Build-Powerband (Ziel-Korridor als Datenwert); Ausreißer-Seeds < 5%.
- **Entdeckungs-Rhythmus:** In den ersten 10 Runs im Schnitt ≥ 1 neue Freischaltung ODER Synergie-Entdeckung pro Run (Sog-Messlatte, aus Playtests/Bot-Nährung geschätzt).
- **Determinismus:** Alle Ziehungen (Wahl aus 3, Shop, Drops) aus dem Seed-RNG — gleicher Seed, gleiche Angebote.

## User Stories

- **US-01:** Als Spieler möchte ich nach jedem Raum eine knappe, interessante Wahl treffen, damit mein Build eine Geschichte aus Entscheidungen ist.
- **US-02:** Als Spieler möchte ich beim Zusammenkommen von „Aschespur" + „Kettenklinge" eine benannte Synergie entdecken, damit Experimentieren belohnt wird.
- **US-03:** Als wiederkehrender Spieler möchte ich, dass mein 30. Run aus einem sichtbar größeren Pool schöpft als mein erster — aber mein Charakter nicht stärker startet.
- **US-04:** Als Balancing-Agent möchte ich Drop-Tabellen und Preise patchen und die Auswirkung auf 1.000 Bot-Runs sehen, bevor etwas gemergt wird.

## Akzeptanzkriterien / Success Metrics

- P3 (Slice): Wahl-aus-3, Mob-Drops, 1 Shop, 1 Altar-Achse, ≥ 4 Synergien, ≥ 4 Items funktionsfähig.
- P5: Vollausbau — ≥ 15 Synergien, ≥ 8 Items, Unlock-Baum, Reputation über ≥ 3 Stufen pro Patron; FR-12-Audit bestanden (kein Stat-Creep im Code/Daten).
- Ökonomie-Korridor-Messung in CI (Sim-Harness-Report pro Merge in Balancing-Daten).
- Playtest-Signal (P5): Tester können nach 5 Runs mindestens 2 Synergien aus dem Gedächtnis benennen.

## Offene Fragen

- **OF-10.1:** Verdienstformel für Unlock-Punkte (Zeit? Stages? Stil-Boni wie Paraden?) — Entwurf in P4, Feintuning P5.
- **OF-10.2:** Shop-Reroll und/oder „Opfer-Angebot" (HP statt Gold zahlen)? Passt zum Setting; Entscheidung P4.
- **OF-10.3:** Startet v1.0 mit beiden Charakteren frei oder ist Charakter 2 ein früher Unlock? Empfehlung: früher Unlock (Sog). PO-Entscheidung.
- **OF-10.4:** Finale Währungs-/Ressourcennamen (mit PRD-0011).

## Referenzen

- [PRD-0005 Kampfsystem](0005-kampfsystem-spieler.md) · [PRD-0006 Patron](0006-patron-und-pakt-system.md) · [PRD-0011 Narrativ](0011-narrativ-und-lore.md) (Hub-Dialoge, Namen) · [PRD-0014 UI/UX](0014-ui-ux.md) (Wahl-/Shop-/Inventar-UI) · [PRD-0016 Tooling](0016-tooling-suite.md) (Balancing-Dashboard)

# content/

Quell-Content des Spiels, der vom Asset-Compiler (C#-Tooling) in binäre Packs übersetzt wird:
Sigil-Patterns (`.sigil`), Raum- und Wellen-Templates, Tuning-Daten, Texte (DE/EN), Audio-Rezepte.
Formate sind in `docs/formats/` dokumentiert, sobald sie entstehen (ab P1).

Die CI übersetzt dieses Verzeichnis bei **jedem** Push mit `grimoire-ac` und dem `sigilc` des in
`Cargo.lock` gepinnten Engine-Tags; **jede Diagnose bricht den Lauf** (CONTRIBUTING, „Asset-Gate").
Entdeckt wird jede `.sigil`-Datei unterhalb dieses Verzeichnisses, gleich in welchem Unterordner;
Dateinamen und Ordner müssen deshalb gültige Asset-Pfade sein (ASCII `[a-z0-9_.-]` und `/`), weil
die `UnitId` aus genau diesem Pfad entsteht. Absichtlich kaputte Dateien gehören nie hierher,
sondern nach `tests/fixtures/sigil-broken/`. Das erzeugte `packs/` ist Build-Artefakt und wird nicht
eingecheckt.

| Ordner | Inhalt |
|---|---|
| `sigil/` | Bullet-Patterns in Sigil (`sigil 1`), siehe die Tabelle unten. Nur Silhouetten und Paletten, die der Bullet-Pass zeichnet (Visual-Katalog der Engine). Übergangsweise übersetzt das Build-Skript von `fnp_content` sie beim Bauen mit dem Compiler der Engine (`grimoire_sigilc`) und bettet die Units ein; der kanonische Content-Pfad ist der Pfad relativ zu `content/` |

## Format

Die Sprache beschreibt **`docs/formats/sigil.md` im Engine-Repo, am gepinnten Tag** — nicht hier,
denn das Format gehört der Engine (Projekt-ADR-0010):

```bash
tag=$(bash .github/scripts/engine-pin.sh | sed -n 's/^tag=//p')
git -c credential.helper= clone --depth 1 --branch "$tag"   https://github.com/LupusMalusDeviant/grimoire engine   # falls noch nicht da
${PAGER:-less} engine/docs/formats/sigil.md
```

Die Abschnitte, die beim Schreiben von Patterns zählen:

| Abschnitt | Inhalt |
|---|---|
| §3, §4 | Header `sigil 1`, Grammatik: ein Member je Zeile, `bullet`/`emitter`/`meta`/`import` |
| §6 | Diagnoseform; genau das, was das Asset-Gate ausgibt |
| §10.3–§10.9 | Was ein Baustein, ein Modifikator und eine Transformation wirklich bedeuten |
| §10.10 | **Visual-Katalog**: erlaubte Silhouetten- und Palettennamen; nur `orb`, `rice`, `diamond` und die Paletten `hex_magenta`, `poison_lime` werden gezeichnet |
| §11.3 | Statische Prüfungen, darunter die Lesbarkeitsregeln aus PRD-0003 (eigene Silhouette je Bullet-Typ, nur der Gegner-Palettenraum) |
| §13 | `sigilc check|build|simulate` — dieselben Kommandos, die das Gate fährt |

Bausteine: `ring`, `spiral`, `fan`, `aimed`, `wave`, `line`, `scatter`. Modifikatoren:
`accelerate`, `sine_offset`, `rotate`, `mirror`, `speed_curve`, `curve`. Transformationen:
`burst`, `become_emitter`, `change_type`, `reverse` (Kaskadentiefe höchstens 3).

## Patterns (Stand WP7.3)

Jedes Pattern gehört zu einer Rolle aus dem Gegner-Rollenraster (PRD-0007) und ist aus den
Referenz-Patterns der Engine (`crates/grimoire_sigilc/tests/reference/`) abgeleitet.

| Datei | Rolle | Bausteine und Kniffe | Abgeleitet aus |
|---|---|---|---|
| `imp_volley.sigil` | Schütze | `aimed`, `fan`, `ring`, `sine_offset`, `accelerate` | `03-aimed-fan`, `01-opening-ring` |
| `imp_curtain.sigil` | Vorhang-Träger | zwei gegenläufige `spiral`, `rotate`; rund 10.000 Bullets | `02-spiral-curtain` |
| `swarm_weave.sigil` | Schwärmer | `wave` mit `curve`, `fan` mit `accelerate`; acht endliche Wellen | `04-bending-wave` |
| `shooter_rails.sigil` | Schütze | zwei versetzte `line` mit `speed_curve`, schmaler `fan` in der Gasse | `05-rail-sweep` |
| `harrier_scatter.sigil` | Störer | `scatter` mit Seed und `speed_jitter`, dazu ein langsamer `ring`; läuft endlos | `06-seeded-scatter` |
| `summoner_bloom.sigil` | Beschwörer | **Kaskade**: `become_emitter` (Sub-Emitter) und `change_type`, Tiefe 2 von 3 | `11-seed-bloom`, `09-shatter-orbs` |
| `breaker_toll.sigil` | Tank/Brecher | `ring` mit `reverse`, `fan` mit `mirror` | `08-returning-needles`, `07-mirror-bloom` |

### Regeln, die beim Schreiben wirklich wehtun

- **Eigene Silhouette je Bullet-Typ** einer Unit (PRD-0003 Regel 3, `SIG0020`) und nur der
  Gegner-Palettenraum (Regel 4, `SIG0021`). Gezeichnet werden bisher drei Silhouetten, also hat eine
  Unit höchstens drei sichtbare Bullet-Typen.
- **Despawn gibt es nur über die Grenzen.** Sigil v1 kennt kein Lebensdauer-Feld; ein Bullet
  verschwindet, wenn es die Box um die Arena verlässt (`ARENA_HALF` + 3u, also 13,5u × 10u um die
  Arenamitte). Daraus folgt die Regel, die die Engine in WP6.6 gemessen hat: **eine `curve`- oder
  `rotate`-Drehrate, deren Kreis innerhalb dieser Box zugeht, despawnt nie.** Auf einem Emitter mit
  `repeat = forever` füllt das den Pool. Wer dreht, rechnet den Radius nach (`r = speed / turn`, mit
  `turn` in rad/t) und hält ihn deutlich über der Box — oder nimmt ein endliches `repeat`.
- **Endlos heißt beobachtet.** `sigilc simulate --json` zeigt je Tick die lebenden Bullets; ein
  Endlos-Pattern muss auf einen Wert einschwingen, ein endliches muss auf 0 zurückgehen.

```bash
engine/target/release/sigilc simulate --json --root content --ticks 900   --bounds -13.5,-13.5,13.5,13.5 --capacity 16384 --target 0,-7.5   -- content/sigil/swarm_weave.sigil
```

Gemessen am Stand dieses Commits (900 Ticks, Bullets im Höchststand → am Ende): `swarm_weave`
128 → 0, `shooter_rails` 48 → 0, `breaker_toll` 84 → 0, `summoner_bloom` 66 → 0,
`harrier_scatter` 104 → 93 (endlos, eingeschwungen), `imp_volley` 97 → 88 (endlos),
`imp_curtain` 12.488 → 12.472 (endlos, Stresstest; Pool-Kapazität 16.384). Kein Pattern verwirft
Spawns, und jedes Despawn geht über die Grenzen.

# Spiel-Verträge (Entwurf) — Harness `fnp_sim_harness`, Phase P1

*Entwurf WP1.2 — PO-Freigabe ausstehend.*

> **Agenten-Hinweis:** Dieses Dokument ist die Schnittstellen-Spezifikation der Sim-Harness im Spiel-Repo. Es
> ergänzt die Engine-Verträge (`grimoire/docs/architektur/crate-vertraege.md`, Entwurfsstand auf dem Engine-Branch
> `p1/wp1.2-contracts-draft`), die bewusst nichts vom Spiel wissen (Standalone-Gate). Bezüge auf die Engine nennen
> nur deren öffentliche Namen und Abschnitte: `Replay`, `ReplayHeader`, `ContentManifestHash` (§8.1),
> `grimoire_sim::stream::app_stream` (§8.3), JSON-Regeln (§2 Regel 11), `GoldenMaster`, `GoldenRun`, `compare`
> (§15.2), Quantisierung der Zielachsen (§9.4). Anforderungs-Hintergrund: PRD-0018 FR-02/03/05/08, PRD-0013 FR-10,
> PRD-0017 FR-07, Plan 0002 WP1.2, WP7.4, WP7.5.

## 0. Einordnung

- Plan 0002 WP1.2 nennt die Trait-Verträge `Scene`, `BotProfile` und `HarnessReport` als Teil der P1-Verträge. Das
  Engine-Dokument darf das Spiel nicht nennen; diese Verträge leben deshalb hier (vorläufig, PO-Bestätigung
  ausstehend). Änderungen folgen sinngemäß dem Vertragsänderungs-Protokoll der Engine (§2b).
- Das Dokument ist nicht committet und hat keinen eigenen Umsetzungsstand; die Skelette entstehen in WP1.3.

## 1. Rolle und Grenzen

- `fnp_sim_harness` führt **Szenen** headless aus: Seed + Pattern-Set + Bot-Profil, `NullRenderer`, keine Uhr im
  Ergebnis.
- Ergebnis ist ein `HarnessReport` als JSON, optional ein Replay v2 und der Abgleich mit Golden Mastern.
- Die Harness baut gegen einen Engine-Alpha-Tag. Den Content kompiliert sie über `grimoire_sigilc` als Bibliothek
  (Plan 0002 WP7.4; setzt P-2 voraus).
- Standard-Suite unter 5 Minuten (PRD-0018 P1).
- Alles hier ist Simulations-Nähe: Szenen- und Bot-Code zieht Zufall nur über `derive_rng`/`derive_block_rng` mit
  Anwendungs-Strömen (Bit 63 gelöscht, Abschnitt 5), keine Wanduhr, keine `HashMap`-Iteration.

## 2. `Scene`

```rust
pub trait Scene {
    fn id(&self) -> &'static str;                 // [a-z0-9_]{1,64}, stabil; Schlüssel für Golden Master und Report
    fn seed(&self) -> u64;
    fn ticks(&self) -> u64;                       // ≥ 1
    fn hash_every(&self) -> u64 { HASH_EVERY }    // 60
    fn patterns(&self) -> &[&'static str];        // kanonische Content-Pfade (Engine §11.1): AssetPath mit Endung .sigil,
                                                  // relativ zu content/sigil/, streng aufsteigend, ohne Duplikate
    fn bot(&self) -> &'static str;                // BotProfile::id
    fn build(&self, sim: &mut Simulation, content: &SceneContent) -> Result<(), HarnessError>;
    fn check(&self, sim: &Simulation, out: &mut Vec<InvariantViolation>) {}   // szenenspezifische Invarianten je Tick
}
pub struct SceneContent;      // geladene Units der Szene + content_manifest: ContentManifestHash (Engine §8.1, §11.8); nur lesend
pub struct InvariantViolation { pub invariant: &'static str, pub tick: u64, pub detail: String }   // Clone, Eq, Debug
pub enum HarnessError;        // #[non_exhaustive], thiserror: UnknownScene, UnknownBot, Content(String), Io(String), Schema(String)
pub fn scenes() -> Vec<Box<dyn Scene>>;          // Registry in fester, nach id sortierter Reihenfolge
```

**Semantik:**
- `build` legt Komponenten, Ressourcen, Systeme, Start-Entities und Emitter an. Danach verändert die Szene die
  Simulation nicht mehr; jede Wirkung pro Tick läuft über Systeme in der Welt. Das folgt der Engine-Regel „Zustand
  nur in der Welt“, damit Snapshot, Hash und Replay stimmen.
- `check` läuft nach jedem `step`, liest nur und darf den Hash nicht beeinflussen.
- **Content-Pfade:** Die Harness reicht die Pfade aus `patterns` unverändert an `grimoire_sigilc` weiter. Dieselben
  Zeichenketten bilden die Pack-Einträge des Asset-Compilers; so ergeben Harness, Pack und `grimoire-link watch`
  dieselben `UnitId`s und denselben Content-Manifest-Hash (vorläufig, PO-Bestätigung ausstehend).
- **Eingaben einer Szene** sind ausschließlich `seed`, `patterns` (über `SceneContent.content_manifest` im Report und
  Replay festgehalten) und die Frames des Bots. Gleiche Eingaben ergeben auf Windows, Linux und macOS dieselben
  Checkpoints.
- Die Harness prüft neben `check` immer die Standard-Invarianten:
  - `no_nan`: An jedem Hash-Punkt speist die Harness in jedem Build Tick, Seed und `World::stable_hash` genau wie
    `Simulation::state_hash` (Engine §8) in einen eigenen `StableHasher`. Meldet `saw_nan()` ein NaN, schlägt die
    Invariante mit `first_violation_tick` fehl, die Szene stoppt, und ein Teilbericht wird geschrieben;
    `state_hash`, das im Debug-Build bei NaN panict (Engine §3), wird dann nicht mehr aufgerufen. Nicht endliche
    Metriken zählen ebenfalls als Verletzung (vorläufig, PO-Bestätigung ausstehend).
  - `no_panic`: Die Harness führt jede Szene unter `catch_unwind` aus. Jeder andere Panic (etwa die Debug-Prüfung
    des Bullet-Pools, Engine §11.3) beendet diese Szene mit einem Teilbericht: Invariante `no_panic` verletzt, Tick
    und Meldung in `detail`, `golden = None`. Die Suite läuft weiter und endet mit einem Exitcode ungleich 0.
  - `pool_limits`: Bullet-Anzahl ≤ Pool-Kapazität, `dropped_spawns` wird gemeldet (Engine §11.3).
  - `clear_within_one_tick`: Ein Bullet, das zum Zeitpunkt einer Clear-Anforderung lebt und vom `ClearFilter`
    erfasst wird, ist spätestens nach dem Tick, in dem `sigil.clear` die Anforderung anwendet, nicht mehr lebendig;
    für seine `BulletId` liegt ein `BulletEvent` mit `DespawnCause::Clear` vor. Eine Anforderung aus einer früheren
    Stufe wirkt im selben Tick, sonst im nächsten (Engine §11.4). Danach neu gespawnte Bullets, etwa von einem weiter
    aktiven Emitter, zählen nicht. Praktische Prüfung: Eine `ClearRequest`-Entity, die bei `check` nach Tick `t`
    lebt, ist am Ende von Tick `t + 1` verschwunden, und die erfassten `BulletId`s aus Tick `t` haben ein
    Clear-Ereignis oder leben nicht mehr.

## 3. `BotProfile`

```rust
pub trait BotProfile {
    fn id(&self) -> &'static str;                 // [a-z0-9_]{1,64}; P1: "idle", "random_dodger"
    fn reset(&mut self, seed: u64);               // genau einmal vor Tick 0
    fn input(&mut self, tick: u64, world: &World) -> InputFrame;   // Slot 0 des TickInput von `tick`
}
pub fn bot(id: &str) -> Result<Box<dyn BotProfile>, HarnessError>;
pub const BOT_STREAM_OWNER: u16 = 0x0001;          // Anwendungs-Eigentümer „Bots“, Ströme über app_stream
```

**Semantik:**
- `input` wird je Tick genau einmal vor `step` mit dem Weltzustand nach dem Vortick aufgerufen und liest nur.
- Gleiche Seeds und gleiche Folge von Weltzuständen ergeben dieselben Frames. Innerer Zustand ist erlaubt, wenn er
  allein aus `reset` und dieser Folge entsteht.
- Die erzeugten Frames landen im `InputLog` des Replays. Ein Replay spielt deshalb ohne Bot ab (PRD-0013 FR-10: Bots
  sind Erstklass-Eingabequelle, formatkompatibel).
- Zufall nur über `derive_rng(seed, tick, app_stream(BOT_STREAM_OWNER, <lokal>))`.
- **Achsen:**
  - Bewegung über Achsen 0/1 als `i16` (±32767).
  - Zielrichtung über Achsen 2/3 schreibt ein Bot direkt quantisiert, ohne Kamera. Er folgt derselben
    Quantisierungsregel wie die Fassade (`grimoire::quantize_aim`, Engine §9.4: Normieren, Runden, sättigender Cast,
    degenerierte Richtung → `(0, 0)`).
- **P1-Profile:**
  - `idle`: immer `InputFrame::default()`.
  - `random_dodger`: geseedete Bewegung des Spieler-Proxys über Achsen 0/1, Richtungswechsel in festen
    Tick-Intervallen, Richtung je Intervall aus dem Bot-Strom.
- Weitere Profile aus PRD-0018 FR-03 (Radius-Grazer, Aggressiver Parierer, Pattern-Kenner) folgen ab P2 unter
  demselben Trait.

## 4. `HarnessReport`

**Trait-Entscheid (Abweichung, begründet):** `HarnessReport` ist ein **konkreter, serialisierbarer Typ** und kein
Trait. Der Bericht ist reine Daten ohne austauschbares Verhalten, und seine Verbraucher (CI, Balancing-Dashboard,
Golden-Master-Werkzeug) hängen am JSON-Schema, nicht an einer Implementierung. Das entspricht der Abweichung für
ECS-Ressourcen in den Engine-Verträgen (§2a, konkrete Datentypen statt Traits). Austauschbar bleiben Szene und Bot.

```rust
pub const REPORT_SCHEMA: &str = "fnp.harness.report";
pub const REPORT_SCHEMA_VERSION: u32 = 1;
pub struct HarnessReport {
    pub scene: String,
    pub bot: String,
    pub seed: u64,                                // JSON: Hash-String (16 Hex)
    pub ticks: u64,
    pub build: BuildMeta,                         // game_version, game_git, engine_pin, engine_version, engine_build
    pub content_manifest: ContentManifestHash,    // JSON: 16 Hex (Engine §8.1)
    pub replay: Option<String>,                   // relativer Pfad der Replay-v2-Datei (Pfadregel Engine §15)
    pub golden_eligible: bool,
    pub metrics: Vec<Metric>,                     // name [a-z0-9_.]+, unit, value (endliche Zahl); Reihenfolge fest je Szene
    pub invariants: Vec<InvariantResult>,         // name, passed, first_violation_tick: Option<u64>, violations: u64, detail
    pub hashes: HashSection,                      // hash_every, checkpoints: Vec<Checkpoint> (Form wie grimoire_bench, Engine §15.2)
    pub events: Vec<EventRecord>,                 // tick, kind [a-z0-9_.]+, data: BTreeMap<String, String>
    pub events_truncated: bool,                   // Event-Log ist auf MAX_EVENTS = 10 000 begrenzt
    pub golden: Option<GoldenVerdictJson>,        // Ergebnis von compare, falls ein Master existiert
}                                                 // Clone, PartialEq, Debug; to_json() -> Result<String, HarnessError>,
                                                  // from_json(&str) -> Result<HarnessReport, HarnessError>
```

**Semantik:**
- **JSON-Regeln der Engine gelten** (§2 Regel 11): `u64`-Hashes und Seeds als Strings aus 16 Hex-Kleinbuchstaben,
  Ganzzahlen als Zahl nur ≤ 2⁵³ − 1, kein NaN. Eine nicht endliche Metrik ist kein Wert, sondern eine verletzte
  Invariante `no_nan`.
- **Leser** (vorläufig, PO-Bestätigung ausstehend): `from_json` ist streng wie die Engine-Schemata (Engine §15,
  §2 Regel 9) und liefert bei fehlerhafter Eingabe `HarnessError::Schema`, nie einen Panic. Es prüft vor dem Parsen
  die Eingabelänge (≤ 64 MiB) und danach jede Anzahl und Textlänge: `metrics` ≤ 1024, `invariants` ≤ 256,
  `events` ≤ `MAX_EVENTS`, `data` je Event ≤ 32 Einträge, Checkpoints und Subsystem-Hashes wie Engine §15, freie
  Texte (`detail`, Schlüssel, Werte) ≤ 1024 Byte. `replay` folgt der Pfadregel aus Engine §15 (Segmentregeln von
  `AssetPath`), relativ zum Verzeichnis des Reports.
- `hashes.checkpoints` hat exakt die Form der Golden-Master-Checkpoints (inklusive optionaler Subsystem-Hashes). Ein
  Report kann damit per Erneuerungskommando zum Master werden.
- **Deterministischer Inhalt:** Metriken, Invarianten, Hashes und Events hängen nur von Szene, Seed, Bot und Content
  ab, nie von Wanduhr, Executor oder Thread-Anzahl. Laufzeitmessungen gehören in `BenchResult`, nicht in den Report.
  Zwei Läufe ergeben byte-identische Report-JSONs bis auf `build`.
- **`build`:**
  - `game_version` = Paketversion.
  - `game_git` = Commit (40 Hex oder `"unknown"`).
  - `engine_pin` = Tag aus `Cargo.toml` plus Commit aus `Cargo.lock`.
  - `engine_version`/`engine_build` aus der Engine (`ENGINE_VERSION`, `ENGINE_BUILD`).

  Dieselben Werte schreibt die Harness in `ReplayHeader.app_metadata` unter `app.name`, `app.version`, `app.git`,
  `app.engine_pin` (PRD-0017 FR-07).
- **Replay:** Die Harness schreibt Replay v2 mit `ReplayHeader::for_this_build(content_manifest)` und den Metadaten.
  Szenen ohne Hot-Swap sind immer `golden_eligible`.

## 5. Zufallsströme des Spiels

- Das Spiel nutzt ausschließlich Ströme mit gelöschtem Bit 63, empfohlen über `app_stream(owner, local)`.
- Eigentümer-Nummern des Spiels: `0x0001` Bots, `0x0002` `fnp_game`, weitere per Änderung dieses Dokuments.
- Bestehende P0-Konstanten des Spiels (etwa der Schwarm-Spawn-Strom) bleiben unverändert, damit der P0-Golden-Hash
  gilt. Neue Ströme folgen der Aufteilung.

## 6. Golden Master im Spiel

- **Verzeichnis:** `Prototype/tests/golden/` mit `<scene>.golden.json` (Engine-Format `grimoire.golden` v1),
  `replays/<scene>.grimrepl` (Replay v2) und `renewals.jsonl`.
- **Abgleich:**
  - Spiel-CI pro Push auf Linux.
  - Plattformübergreifender Hash-Vergleich nightly auf 3 OS.
  - Nur `Match` besteht. `ContentChanged` und `Diverged` machen den Lauf rot (vorläufig; PO-Frage zur Behandlung
    von `ContentChanged`). `NotEligible` ist ein Fehler der Suite, weil Standard-Szenen keine Swaps enthalten.
  - `ShapeMismatch` (geänderter Seed, Tick-Takt, Hash-Intervall, Tick-Liste oder Algorithmusversion) und jede
    künftige Variante des `#[non_exhaustive]`-Enums `GoldenVerdict` machen den Lauf ebenfalls rot und stehen mit
    Verdikt im Report.
- **Erneuerung** nur per `fnp_sim_harness golden renew <scene> --reason "…"` in eigenem Commit nach CONTRIBUTING
  „Golden-Master und Referenzwerte“. Agenten erneuern nicht eigenmächtig.
- Die bestehende Konstante `GOLDEN_FINAL_HASH` in `tests/determinism.rs` bleibt als P0-Gate erhalten.

## 7. Konformanz

- `Scene`/`BotProfile`: Test je registrierter Szene und je Bot, Doppellauf mit gleichem Seed ergibt identische
  Reports.
- `idle` und `random_dodger` sind reine Funktionen von Seed und Weltfolge; ein Replay ohne Bot reproduziert die
  Checkpoints.
- `HarnessReport`: Rundreise, Hash-Strings, Ablehnung von NaN, jedes Maximum + 1 liefert einen Fehler, Proptest mit
  beliebigen und veränderten Eingaben ohne Panic.
- Standard-Invarianten: Eine Szene, die absichtlich NaN in den Zustand schreibt, ergibt in Debug und Release einen
  Bericht mit verletztem `no_nan` am richtigen Tick; eine panicende Szene ergibt `no_panic` verletzt, und die Suite
  läuft weiter. Eine Szene mit weiter aktivem Emitter und Clear besteht `clear_within_one_tick`.
- Standard-Suite-Laufzeit wird gemessen und im Umsetzungsstand protokolliert (nicht im Report).

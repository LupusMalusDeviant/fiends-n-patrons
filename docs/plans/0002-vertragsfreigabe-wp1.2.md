# Fragenrunde Vertragsfreigabe WP1.2 (Plan 0002, WP1.7)

- **Status:** Vorbereitet für die Fragenrunde, **nichts entschieden**
- **Datum:** 2026-09-15 (Agentenlauf, Anschlussarbeit)
- **Autor:** Claude (Ausarbeitung aus dem Branch-Text und den Agentenlauf-Ergebnissen; Codex nicht beteiligt)
- **Für:** Lupus Malus Deviant (PO) — nur auswählen, nichts schreiben
- **Bezug:** [Plan 0002](0002-phase-p1-sichtbarer-kern.md) (WP1.2, WP1.3, WP1.7), [Dossier Sammelsitzung A](0002-sammelsitzung-a-dossier.md), [Agentenlauf 2026-09-15](agentenlauf-2026-09-15.md), [Spiel-Verträge (Entwurf)](../architektur/spiel-vertraege-entwurf.md)

> **So ist das Dokument gedacht:** Oben stehen der Überblick und die Reihenfolge. Danach folgt je Frage ein kurzer
> Abschnitt mit Kontext, Optionen und Empfehlung zum Nachlesen, dann die Liste aller vorläufigen Entscheidungen zur
> Freigabe im Ganzen. Am Ende steht der **Fragenentwurf**: sechs `AskUserQuestion`-Aufrufe mit höchstens vier Fragen,
> die empfohlene Option jeweils zuerst. Alle Empfehlungen sind **vorläufig** und gelten erst mit PO-Bestätigung.

## Worum es geht

**Was freigegeben wird:** der Vertragsentwurf auf dem Engine-Branch `p1/wp1.2-contracts-draft` (Kopf `f9765dd`,
gepusht, ohne PR und ohne CI-Lauf) mit

- `docs/architektur/crate-vertraege.md`: alle Abschnitte mit dem Vermerk *Entwurf WP1.2 — PO-Freigabe ausstehend*
  (§1 Crate-Karte, §2 Regeln 9–15, §2a Trait-Entscheid, §2b Änderungsprotokoll, Ergänzungen in §3, §5–§10, neu §11
  Sigil-Laufzeit, §12 Pack, §13 Debug-Protokoll, §14 Kollision, §15 Bench- und Golden-Master-Schemata);
- dem Engine-ADR-Vorschlag `docs/adr/0008-crate-map-erweiterung-p1.md` („Crate-Map-Erweiterung P1“, Status
  „Vorgeschlagen“, Nummer vorläufig);
- dem spielseitigen Entwurf `Prototype/docs/architektur/spiel-vertraege-entwurf.md` (Szenen, Bot-Profile,
  Harness-Bericht; nicht committet).

Der Entwurf ist nur Dokumentation. Er wurde im Lauf dreimal geprüft: ein Review mit vier Blickwinkeln
(21 Befunde bestätigt und eingearbeitet), ein Codex-Review (9 von 13 Punkten bestätigt und eingearbeitet) und eine
Kompilierprüfung aller 33 Rust-Blöcke als Signatur-Spike (11 Befunde korrigiert). Aus diesen Schritten stammen die
Fragen unten.

**Was die Freigabe entblockt:**

1. **WP1.3:** Die Vertrags-Skelette entstehen auf dem Branch: kompilierende Typen, Null-Implementierungen,
   Konformanz- und Vertragstests, der Spieler-Proxy als einzige echte Implementierung und der CI-Kanten-Check.
2. **Vertrags-PR und WP1.7-Gate:** Text und Skelette gehen gemeinsam in einen PR (reine Doku-Commits lösen keine
   CI aus). Das Gate verlangt ein adversariales Review dieses PR, die PO-Freigabe und eine **überwachte, grüne
   CI auf Windows, Linux und macOS**. Diesen 3-OS-Lauf gibt es erst, wenn Actions-Minuten dafür frei sind
   (OP-2; laut Dossier bis zum 1. Oktober höchstens 168 Minuten, vorrangig für das WP1.0-Hash-Gate).
   *Nachtrag 2026-09-15: Seit der Veröffentlichung beider Repos kostet der 3-OS-Lauf keine
   Actions-Minuten; die Minutenbedingung entfällt, das Gate selbst bleibt.*
3. **Danach die parallelen Stränge**, die nur gegen gemergte Verträge bauen: Render-A (WP2.2 ff.), Sigil-Laufzeit
   (WP5), Messung und Kollision (WP6), Replay und Harness (WP7), Dev-Link und Pack (WP8), später die C#-Seite.

**Voraussetzungen:** Der Vertragsbranch baut auf dem Scheduler-Branch auf (Stand `548a30a`, eingemergt als
`5eebd0d`). Die **Freigabe WP1.0** aus dem Dossier kommt deshalb zuerst. Mehrere Fragen setzen außerdem Antworten aus
Sammelsitzung A voraus (siehe Spalte im Überblick und Abschnitt „Einfluss der Sammelsitzung A“). Der Entwurf wurde mit
den Dossier-Empfehlungen P-1 A, P-3 A, P-4a/b A, P-7 A, P-8 A, P-9 A, P-14 A und OP-2 A geschrieben, dazu P-2 = ja
(Sammelsitzung B).

## Überblick

| ID | Abschnitt | Frage in einer Zeile | Empfehlung | Blockiert | Hängt an Sammelsitzung A | Runde |
|----|-----------|----------------------|------------|-----------|--------------------------|-------|
| V-1 | ADR-0008, §1, §11.7 | Eigene Crates für Compiler, Benchmarks und Link-Werkzeug, samt Test-Kanten des Thread-Gates? | Option 2 mit Dev-Kanten `exec → sigil/collide` | WP1.3-Skelette, Kanten-Check, WP4.3, WP6.2, WP8.5, Thread-Gate für Sigil und Kollision | P-3 (Kante zu `collide`); P-1, P-14 nur als Einträge; P-2 aus Sitzung B | 1 |
| V-2 | §2a | Dürfen Spielsysteme Pool und Kollisionsgitter mit angemeldetem Lesezugriff direkt lesen? | Ja, lesen über die API der besitzenden Crate, schreiben nur Systeme dieser Crate oder der Fassade | WP5.1, WP6.5, WP11.2, P2-Combat-Kit | nein | 1 |
| V-3 | §6, §2a, §9.2 | Wie kommt der Kugel-, Marker- und Debug-Kanal zum Renderer? | Eigener `StageFrame` neben unveränderten P0-Typen | WP2.2 (Render-A), WP3.5, WP5.3 | P-7/P-8 (schwach) | 1 |
| V-4 | §8, §8.3 | Aufteilung der Zufallsstrom-Nummern in Engine, Eigentümer und lokale Nummer? | Bitfelder 1/15/48 | WP1.3 (Fixtures, Bots), WP5.1, WP6.5, Pattern-Goldens | nein (setzt WP1.0-Freigabe voraus) | 1 |
| V-5 | §7.1 | Gemeinsamer Blockläufer für Pool und Gitter? | Internes `run_blocks` öffentlich machen | WP5.1, WP6.5; Scheduler-Abschnitt §7 | nein (WP1.0) | 2 |
| V-6 | §8.1, §11.8 | Breite und Verfahren des Content-Manifest-Hashes? | `u64` über `StableHasher` | WP7.1, WP7.5, WP8.3, WP8.4 | P-8 | 2 |
| V-7 | §11.4, §11.8 | Was passiert beim Live-Tausch mit fliegenden Kugeln und entfallenen Emittern? | Kugeln despawnen, entfallene Emitter ruhen | WP5.5, WP8.4, WP8.5 | P-8 (schwach) | 2 |
| V-8 | §9.2 | Welche Sigil-Typen stehen im Prelude der Fassade? | Kleine Auswahl von sechs Typen | WP1.3 Fassaden-Skelett, Beispiele | P-3 (schwach) | 2 |
| V-9 | §8.1, §11.8 | Was halten Replays über Live-Tausche fest? | Liste aus Tick und Content-Hash | WP7.1, WP7.5, WP8.4 | P-8 | 3 |
| V-10 | §8.1 | Genügt ein „unbekannter“ Build-Hash in lokalen Builds? | Ja, die CI setzt ihn immer | WP7.1, WP7.4, Abnahme WP11 | P-8, P-7 | 3 |
| V-11 | Spiel-Entwurf §6, §15.2 | Wie reagiert die CI auf `ContentChanged`? | Rot, Erneuerung per Ein-Kommando-Werkzeug | WP7.5 | P-8 | 3 |
| V-12 | Spiel-Entwurf §4 | Darf `HarnessReport` ein konkreter JSON-Typ statt Trait sein? | Ja, dokumentierte Abweichung | WP1.3 Harness-Skelett, WP7.4 | nein | 3 |
| V-13 | §13 | Weist der Debug-Handshake fremde Engine-Versionen und Builds ab? | Abweisen, wo prüfbar; „unknown“ mit Warnung annehmen | Engine-ADR „Debug-Link v1“ (WP8.2), WP8.5, WP9.1 | P-7 (P-1) | 4 |
| V-14 | §2 Regel 14, §9.1 | Darf `debug-link` in einem lokalen Release-Build aktiv sein? | Ja, nie in Distributions-Builds | WP8.2, WP11.4, WP11.5 | nein | 4 |
| V-15 | §13 | Rechnet die Engine in P1 eine Muster-Vorschau (`SigilPreview`)? | Nein, Antwort `NotSupported`, Vorschau über `sigilc simulate` | WP8.2, WP10.4 | nein (P-2 aus Sitzung B, P-1) | 4 |
| V-16 | §5, §12 | Wird ein zu großes Pack vor dem Laden abgewiesen? | Ja, über `FileSystem::read_limited` | WP8.3; P0-Trait `FileSystem` im Skelett | nein | 4 |
| V-17 | §14 | Gilt das 1,5-ms-Budget auch für die Cluster-Szene als hartes Gate? | Nein, Cluster nur als Trend | WP6.5, WP11.3, WP11.5 | P-3 | 5 |
| V-18 | §14 | Reicht `MAX_COORD = 1.0e9` als Weltgrenze? | Eingetragenen Wert bestätigen | WP1.3 Kollisions-Skelett, WP6.5 | P-3 | 5 |
| V-19 | §9.4 | Genügt in P1 die Zielrichtung ohne Entfernung? | Ja, nur Richtung | nichts in P1; P2-Combat-Kit, PRD-0013 FR-03 | nein | 5 |
| V-20 | §2b | Welche späteren Vertragsänderungen braucht eine PO-Freigabe? | Stufe A und I gebündelt, Klarstellungen ohne | Abschluss §2b vor dem WP1.7-Gate | P-7 | 5 |
| — | alle | Alle übrigen vorläufigen Entscheidungen übernehmen? | Ja, Merge erst nach Review und grüner 3-OS-CI | WP1.3 insgesamt | P-9 (Ort der Formatdokumente) | 6 |

**Reihenfolge:** Runde 1 betrifft Crate-Schnitt, Zugriffsregel, Render-Kanal und Zufallsströme, weil WP1.3 und die
zuerst startenden Stränge (Render-A, Sigil, Kollision) daran hängen. Runde 2 klärt die Grundlagen der
Sigil-Laufzeit, Runde 3 Replay, Golden Master und Harness (WP7), Runde 4 Dev-Link und Pack (WP8), Runde 5 Kollision,
Zielen und das Änderungsprotokoll. Runde 6 gibt den Rest im Ganzen frei.

## Erledigt oder zusammengeführt

Quellen: `wp1.2-result.json` (17 PO-Fragen), eine weitere Frage aus dem Review-Schritt desselben Laufs (Handshake,
§13), `codex-followups-result.json` (3), `contract-check-result.json` (2), zusammen 23 Einträge. Maßgeblich war der
Text auf dem Branch.

- **Zusammengeführt zu V-13:** Die ursprüngliche Handshake-Frage (Empfehlung damals: nur Protokollversion und
  Token prüfen) und die neue §13-Frage aus dem Review. Das Review hatte gefunden, dass die Einengung Plan WP8.2
  widerspricht, ohne als PO-Frage gestellt zu sein. Der Branch setzt jetzt Schritt 7 um (harter Reject, „unknown“
  mit Warnung angenommen); die **Empfehlung hat sich damit geändert**. Nicht mehr angeboten wird die Zwischenstufe
  des ersten Entwurfs „nur abweichende Engine-Version abweisen, Build-Hash nur protokollieren“; der Vertrag nennt
  sie nicht mehr, sie bleibt über die freie Antwort wählbar.
- **Zusammengeführt zu V-1:** Die Frage nach den Dev-Kanten des Hash-Gates (§11.7) gehört zur selben Kantentabelle
  (§1) wie die Crate-Karte. Die Variante „keine neue Dev-Kante“ ist in V-1 eine eigene Option.
  **Hinweis:** ADR-0008 Baustein 5 nennt als Dev-Kanten von `grimoire_exec` bisher nur `grimoire`, `grimoire_sim`
  und `grimoire_core`, §1 zusätzlich `sigil` und `collide` (vorläufig). Bei Option A muss das ADR nachgezogen werden.
- **Zusammengeführt zu V-7:** „Was passiert mit fliegenden Kugeln beim Hot-Swap“ (WP1.2-Lauf) und „verkleinernder
  Swap“ (Codex, §11.8) betreffen denselben Ablauf von `replace_unit` und blockieren dieselben Pakete. Nicht als
  eigene Option angeboten wird „Kugeln mit neuem Layout weiterlaufen lassen“ (kann Indizes außerhalb des Bereichs
  erzeugen); sie bleibt über die freie Antwort wählbar.
- **Durch den Branch-Text erledigt:** keine. Keine der 23 Fragen ist im Text entschieden. Als ausdrückliche
  PO-Frage mit Optionen stehen im Vertrag nur fünf: §9.2 (V-8), §11.7 (V-1), §11.8 (V-7), §12 (V-16) und §13
  (V-13). Kurze Vermerke ohne Optionen tragen §2a (V-2) und §8 (V-4, beide „PO-Bestätigung ausstehend“), §11.4
  (V-7), §14 (V-17 „PO-Frage“, V-18 „vorläufig“), §2b (V-20 „PO-Entscheidung ausstehend“) und der Spiel-Entwurf §6
  (V-11). Für V-3, V-5, V-6, V-9, V-10, V-12, V-14, V-15 und V-19 gilt nur der Abschnittsvermerk *Entwurf WP1.2 —
  PO-Freigabe ausstehend*; die Frage selbst steht in `wp1.2-result.json`. Die Agentenlauf-Notiz nannte „17
  PO-Fragen“; die übrigen kamen durch die späteren Prüfschritte hinzu.

---

## Runde 1 — Crate-Schnitt und Grundregeln

### V-1 — Crate-Karte P1 (ADR-Vorschlag 0008) und Test-Kanten des Thread-Gates

**Frage:** Entstehen Sigil-Compiler, Benchmarks und das Link-Werkzeug als eigene Crates, und dürfen die Thread-Tests
Sigil und Kollision direkt einbinden?

**Kontext:** P1 bringt einen Compiler (`sigilc`), Benchmarks mit Wanduhr und Threads und die CLI `grimoire-link`.
Für keinen davon hat die P0-Karte Platz. Die Determinismus-Sperren gelten auch für Benches in Simulations-Crates, und
der Parser darf nicht in den Laufzeitpfad (Projekt-ADR-0007). Das Thread-Gate `grimoire_exec/tests/hash_gate.rs`
bindet Szenarien anderer Crates per `#[path]` ein und braucht dafür je Crate eine Dev-Kante. Der Branch weicht in
einem Punkt vom Plan-Wortlaut ab: `grimoire_sigilc` hängt zusätzlich an `sim` und `ecs`, weil `sigilc simulate`
(WP5.6) den Laufzeit-Interpreter ausführt.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Option 2 mit Dev-Kanten `exec → sigil`, `exec → collide`** | Drei neue Crates (`grimoire_sigilc` in der Determinismus-Menge mit siebter `clippy.toml`, `grimoire_bench`, `grimoire_link`), neue Laufzeitkante `sigil → ecs`; Compiler strukturell außerhalb der Laufzeit; plattformabhängige Rechnungen fallen im lokalen Clippy-Lauf auf; längere Builds (OP-5) |
| **B: Option 2 ohne neue Dev-Kanten** | Gate-Szenarien nennen Sigil und Kollision nur über `grimoire::sigil`/`grimoire::collide`; `grimoire_sigil/tests` bräuchte dann eine Dev-Kante zur Fassade, die selbst an `sigil` hängt |
| **C: Option 3** (Compiler ohne `clippy.toml`) | Freiere Compiler-Implementierung; plattformabhängige Units fallen erst im 3-OS-Identitäts-Gate (WP4.4) auf, das Minuten kostet; widerspricht PRD-0018 FR-09 im Plan-Umfang |
| **D: Option 1** (alles in bestehenden Crates) | Keine neuen Crates; Parser hinter einem Feature im Laufzeit-Crate; `grimoire-link` bräuchte die verbotene Kante `debug → sigil`, ein Bench mit N Threads eine Dev-Kante einer Determinismus-Crate auf `grimoire_exec` (ADR-0006 verbietet beides) |

C und D betreffen nur den Crate-Schnitt; die Test-Kanten des Thread-Gates bleiben dabei wie in A. Eine andere
Kombination ist über die freie Antwort wählbar. Option 4 (gemeinsame Format-Crate) ist nicht als Auswahl vorgesehen; der ADR-Vorschlag will sie nach ADR-0011
(Schema-Codegen, Sammelsitzung B) neu bewerten. Sie bleibt über die freie Antwort wählbar.

**Empfehlung: A.** Der Laufzeitpfad kann den Compiler durch Konstruktion nicht erreichen, und Determinismusfehler im
Compiler fallen lokal ohne CI-Minuten auf. Die Dev-Kanten liegen außerhalb der Determinismus-Menge und lassen die
Szenarien ohne Fassade laufen.

### V-2 — Zugriff auf konkrete Ressourcen

**Frage:** Dürfen Spielsysteme den Kugel-Pool und das Kollisionsgitter direkt lesen, wenn sie den Zugriff anmelden?

**Kontext:** Plan WP1.2 sagt, Konsumenten greifen auf `BulletPool` und `SpatialGrid` „nur über Systeme der Fassade“
zu. Der Satz stammt aus der Zeit vor Engine-ADR-0006, das parallele Systeme mit deklariertem Lesezugriff erlaubt.
§2a präzisiert ihn (PO-Bestätigung ausstehend): Zustandsbehaftete Ressourcen haben keine öffentlichen Felder, gelesen
wird über die API der besitzenden Crate mit `Access::read_resource`, verändert nur von Methoden dieser Crate in
Systemen, die sie selbst oder die Fassade registriert, oder über Anforderungen wie `ClearRequest`.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Lesen mit Anmeldung** (Branch-Text) | Keine Kopie des 10k-Pools je Tick; jede Veränderung bleibt in einer Crate; reine Datenressourcen dürfen öffentliche Felder haben |
| **B: Wörtlich nur Fassaden-Systeme** | Spiele erhalten nur Kopien oder Ereignisse; Kopierkosten je Tick; §2a, §11.6 und §9.6 werden umgeschrieben |
| **C: Je Ressource im eigenen Abschnitt** | Plan-Wortlaut bleibt; keine gemeinsame Regel, jede Crate entscheidet selbst |

**Empfehlung: A.** Sie passt zum Zugriffsmodell aus ADR-0006, kostet keine Kopien und hält trotzdem jede Mutation in
einer Crate.

### V-3 — Render-Kanal für Kugeln, Marker und Debug

**Frage:** Wie bekommt der Renderer die neuen Kanäle, ohne bestehenden Code zu brechen?

**Kontext:** `RenderFrame` und `RenderStats` aus P0 haben nur öffentliche Felder und kein `#[non_exhaustive]`. Ein
neues Feld bräche jede Konstruktion per Struct-Literal, eine neue Pflichtmethode jede fremde `Renderer`-Implementierung.
Plan WP2.2 verspricht unveränderte P0-Typen. Der Branch führt deshalb `StageFrame` und `StageStats` als Nachbartypen
ein, dazu die bereitgestellten Methoden `supports_stage`/`render_stage` und `GamePlugin::extract_stage` (Arbeitsname).
Die Kompilierprüfung bestätigte, dass P0-Aufrufer unverändert kompilieren.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Eigener Bühnen-Frame** (Branch-Text) | Rein additiv; zwei Frame-Typen nebeneinander; WP2.2 ergänzt Kamera, Meshes und Lichter als weitere `StageFrame`-Felder |
| **B: `RenderFrame` direkt erweitern** im MINOR-Sprung `v0.2.0` | Ein Frame-Typ; bricht Struct-Literale in Engine und Spiel; widerspricht dem WP2.2-Wortlaut |
| **C: Separater Aufruf `submit_bullets`** vor `render` | Alter Frame bleibt; koppelt Aufrufreihenfolge und Zustand im Renderer |

**Empfehlung: A.** Sie hält die Plan-Zusage und ist nach SemVer additiv; B wäre einfacher, bricht aber bestehenden
Code, C erzeugt versteckten Zustand.

### V-4 — Vergabe der Zufallsstrom-Nummern

**Frage:** Wird die Strom-Nummer so aufgeteilt, dass Engine-Teile und Spiel nie denselben Zufall ziehen?

**Kontext:** Der Scheduler-Branch legt vorläufig nur fest, dass Engine-Ströme Bit 63 setzen und Spiel-Ströme nicht
(Teil der WP1.0-Freigabe). §8.3 verfeinert das bitkompatibel: Bit 63 Bereich, Bits 62..48 Eigentümer, Bits 47..0
lokale Nummer, mit `engine_stream`/`app_stream` und einer Eigentümer-Tabelle (`SIM`, `FACADE`, `SIGIL`, `COLLIDE`).
Das Spiel nutzt `app_stream` mit Eigentümer `0x0001` für Bots und `0x0002` für `fnp_game`. P0-Goldens bleiben
unverändert.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Bitfelder je Eigentümer** (Branch-Text) | Kollisionsfrei durch Aufbau; ein Test je Crate prüft Eindeutigkeit und Eigentümer |
| **B: Nur Bit 63 festlegen** | Wie der Scheduler-Branch; jede Crate teilt formlos auf; Kollisionen fallen nur im Review auf |
| **C: Zentrale Tabelle ohne Bitfelder** | Eine Liste aller Ströme mit Eindeutigkeitstest; jede neue Nummer ändert die zentrale Tabelle |

**Empfehlung: A.** Sie schließt Kollisionen konstruktiv aus, ist leicht zu prüfen und ändert keinen bestehenden Hash.
Eine spätere Änderung wäre nach §2b inkompatibel, deshalb gehört die Entscheidung vor die Pattern-Goldens.

---

## Runde 2 — Grundlagen der Sigil-Laufzeit

### V-5 — Gemeinsamer Blockläufer für Ressourcen-Daten

**Frage:** Nutzen Kugel-Pool und Kollisionsgitter denselben Parallel-Mechanismus wie die ECS-Abfragen?

**Kontext:** Der Scheduler zerlegt ECS-Abfragen in feste Blöcke (`par_blocks`, `QUERY_BLOCK_SIZE`). Pool und Gitter
sind keine Archetypen, sondern Ressourcen mit eigenen Spalten. §7.1 macht das interne `run_blocks` öffentlich und
ergänzt `slice_block_ranges`, rein additiv nach dem WP1.0-Hash-Gate. Die Scheduler-Abschnitte §7/§8 werden damit
nachträglich erweitert; der Eigentümer des Scheduler-Vertrags sollte zustimmen (offener Punkt aus dem Agentenlauf).

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Internes `run_blocks` öffentlich** (Branch-Text) | Eine Implementierung der Panic-, Reihenfolge- und Debug-Regeln; Hash-Gate unberührt |
| **B: Kopie in `grimoire_sigil` und `grimoire_collide`** | Keine Änderung an §7; drei Kopien derselben Regeln, die auseinanderlaufen können |
| **C: Neue Welt-Methode** (etwa `World::par_resource_blocks_mut`) | Direkter Zugriff; größerer Eingriff in den Scheduler-Vertrag |

**Empfehlung: A.** Eine gemeinsame Implementierung verhindert abweichende Regeln und bleibt additiv.

### V-6 — Content-Manifest-Hash der Sitzung

**Frage:** Wie genau soll die Kennung des geladenen Contents sein?

**Kontext:** Replay v2, Golden Master, Content-Epoche, Harness-Bericht und Debug-Nachrichten brauchen eine Kennung
des geladenen Contents. Die Teilentwürfe widersprachen sich (64 Bit gegen 32 Byte SHA-256). Der Branch nimmt
`ContentManifestHash(u64)`, berechnet von `grimoire_sigil` mit `StableHasher` über den Registry-Fingerprint und die
sortierten Unit-Hashes. Der SHA-256-`ContentHash` eines Packs bleibt davon getrennt.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: `u64` über `StableHasher`** (Branch-Text) | Keine neue Abhängigkeit und kein Formattyp in Determinismus-Crates; gleiches Verfahren wie der Zustands-Hash |
| **B: 32 Byte SHA-256** über ein kanonisches Manifest, Typ in `grimoire_core` | Stärker gegen Kollisionen; braucht `sha2` oder Formattypen in Determinismus-Crates und eine geänderte Lesart von ADR-0005 |
| **C: Beides** (`u64` im Zustand, SHA-256 zusätzlich in Replay-Metadaten) | Mehr Felder; lässt sich später ohne Bruch zu A ergänzen |

**Empfehlung: A.** 64 Bit genügen zur Identifikation von Content, und A hält die Determinismus-Crates schlank; C
bleibt später additiv möglich.

### V-7 — Live-Tausch: fliegende Kugeln und entfallene Emitter

**Frage:** Was passiert beim Live-Tausch eines Musters mit Kugeln, die schon fliegen, und mit Emittern, die es danach
nicht mehr gibt?

**Kontext:** `replace_unit` tauscht eine Unit an einer Tick-Grenze. Laufende Kugeln tragen Typ- und Programmindizes
des alten Layouts. Nach dem Branch-Text werden sie despawnt (`DespawnCause::Swap`), die Emitter der Unit starten neu.
Emitter mit einem Index, den die neue Unit nicht mehr hat, sind inaktiv und werden wieder aktiv, sobald ein späterer
Tausch den Index zurückbringt (§11.4, von Codex gefunden und vorläufig eingetragen).

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Kugeln despawnen, entfallene Emitter ruhen** (Branch-Text) | Deterministisch und einfach; Live-Editing darf Emitter-Blöcke entfernen und wieder hinzufügen |
| **B: Kugeln despawnen, verkleinernden Tausch ablehnen** (`SigilError::EmitterOutOfRange`) | Ein Tausch, der Emitter-Indizes laufender `Emitter` ungültig macht, ändert nichts und liefert den Fehler; das Entfernen eines genutzten Emitter-Blocks im Editor scheitert |
| **C: Kugeln despawnen, entfallene Emitter-Entities löschen** | Keine inaktiven Emitter; greift in Entities des Spiels ein |
| **D: Kugeln mit alter Unit auslaufen lassen**, entfallene Emitter ruhen | Kein sichtbarer Abbruch; zwei Unit-Versionen je ID im Content-Zustand |

**Empfehlung: A.** Sie ist die einzige Kombination, die weder alte Layouts im Speicher hält noch Bearbeitungen
blockiert noch Spiel-Entities löscht.

### V-8 — Sigil-Typen im Prelude

**Frage:** Welche Sigil-Typen soll ein Spiel ohne vollen Pfad nutzen können?

**Kontext:** Die Kompilierprüfung ergab, dass das Prelude der Fassade Sigil-Typen nennen muss, die das Spiel zum
Aufsetzen von Mustern braucht. Vorläufig eingetragen sind `Emitter`, `AimTarget`, `ClearRequest`, `ClearFilter`,
`UnitId` und `SigilConfig`; alles andere über `grimoire::sigil::…`. Der Integrations-PR prüft die Ergänzungen vor dem
Merge auf Namenskollisionen mit Spiel-Crates.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Kleine Auswahl** (Branch-Text) | Deckt die häufigen Bezüge ab; kleine Fläche für Namenskollisionen |
| **B: Keine Sigil-Typen** | Kein Kollisionsrisiko; Beispiele und Spielcode werden länger |
| **C: Alle öffentlichen Typen aus §11** | Bequem; größere Kollisionsprüfung |

**Empfehlung: A.**

---

## Runde 3 — Replay, Golden Master und Harness

### V-9 — Live-Tausche im Replay

**Frage:** Was sollen Aufzeichnungen in P1 über Live-Tausche festhalten?

**Kontext:** P-8 A verlangt eine Swap-Markierung, damit Tauschsitzungen nie als golden gelten. Der Branch speichert
im Replay-v2-Header eine Liste `SwapRecord { tick, content_manifest }` (16 Byte je Tausch, höchstens 4096) ohne
Unit-Bytes. `is_golden_eligible()` ist genau dann wahr, wenn die Liste leer ist.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Liste aus Tick und Content-Hash** (Branch-Text) | Tauschsitzungen sind diagnostizierbar; ohne dieselben Units nur bis zum ersten Tausch nachspielbar |
| **B: Nur ein Merkmal** „Sitzung hatte einen Tausch“ | Kleinstes Format; Zeitpunkt und Ziel des Tauschs fehlen |
| **C: Liste plus Unit-Bytes** | Tauschsitzungen vollständig nachspielbar; deutlich größere Replays, neue Grenzen nötig |
| **D: Merkmal jetzt, volle Aufzeichnung mit dem Rewind-Spike in P2** | Weniger P1-Arbeit; spätere Formatversion 3 |

**Empfehlung: A.** Sie kostet wenig, erfüllt die Markierung aus P-8 A und macht Tauschsitzungen nachvollziehbar; C
wird zusammen mit dem Rewind-Spike in P2 neu bewertet.

### V-10 — Build-Hash in lokalen Builds

**Frage:** Reicht es für das Erfolgskriterium „Replay-Header tragen Build-Hash und Engine-Pin“, wenn lokale Builds
„unbekannt“ eintragen?

**Kontext:** `ENGINE_BUILD` kommt zur Übersetzungszeit aus `GRIMOIRE_BUILD_HASH`; fehlt die Variable, ist er
`BuildHash::UNKNOWN` (alle Bytes 0). Engine-CI und Release-Workflow setzen die Variable, die Spiel-CI aus dem Commit
in `Cargo.lock`. Den Engine-Pin schreibt das Spiel zusätzlich in die Anwendungs-Metadaten. Nicht geprüft ist, ob
`option_env!` bei geänderter Variable zuverlässig neu baut und ob Cargo-git-Checkouts ein `.git` enthalten.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Ja, die CI setzt ihn** (Branch-Text) | Kriterium in allen CI-Replays erfüllt; Determinismus-Crates bleiben ohne Prozessaufrufe; lokale Arbeit unbehindert |
| **B: Immer Pflicht** | Jeder Build ohne Variable schlägt fehl, auch lokal |
| **C: `build.rs` fragt git** | Kein Setzen nötig; nicht reproduzierbar, Cargo-git-Checkouts haben möglicherweise kein `.git` (nicht geprüft) |

**Empfehlung: A.** Golden Master vergleichen ohnehin Checkpoint-Hashes und nie Replay-Bytes, deshalb schadet ein
lokaler „unbekannter“ Build nichts.

### V-11 — CI-Verhalten bei geändertem Content

**Frage:** Wie reagiert die CI, wenn ein Golden-Master-Vergleich nur wegen geändertem Content abweicht?

**Kontext:** `compare` (§15.2) liefert `ContentChanged`, wenn sich der Content-Manifest-Hash unterscheidet, und
vergleicht dann keine Zustands-Hashes. Der Spiel-Entwurf macht den Lauf vorläufig rot. PRD-0018 FR-05 verlangt, dass
Abweichungen nie still durchgehen; `CONTRIBUTING.md` erlaubt Erneuerungen nur per Werkzeug im eigenen Commit.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Rot, Erneuerung per Ein-Kommando-Werkzeug** (Entwurf) | Wie jede Golden-Abweichung; eigener Commit mit Grund |
| **B: Warnung, wenn derselbe Push Content-Dateien ändert**, sonst rot | Bequemer bei Content-Arbeit; eine Warnung wird leichter übersehen |
| **C: Automatische Erneuerung in der CI** | Kein Handgriff; widerspricht der Golden-Master-Regel |

**Empfehlung: A.**

### V-12 — Harness-Bericht als konkreter Typ

**Frage:** Darf der Harness-Bericht ein fester Datentyp mit JSON-Schema sein, obwohl der Plan von „Trait-Verträgen
`Scene`, `BotProfile`, `HarnessReport`“ spricht?

**Kontext:** Der Bericht hat kein austauschbares Verhalten; CI, Balancing-Dashboard und Golden-Master-Werkzeug hängen
am Schema. Der Spiel-Entwurf §4 macht ihn deshalb zu einem konkreten Typ (dokumentierte Abweichung, analog zu den
ECS-Ressourcen in §2a). `Scene` und `BotProfile` bleiben Traits.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Konkreter Typ** (Entwurf) | Stabiles Schema mit strengem Leser; Abweichung vom Plan-Wortlaut dokumentiert |
| **B: Trait mit Null-Implementierung** (etwa eine Bericht-Senke) | Plan-Wortlaut erfüllt; das Schema braucht es trotzdem zusätzlich |

**Empfehlung: A.**

---

## Runde 4 — Dev-Link und Pack

### V-13 — Abweisung im Debug-Handshake

**Frage:** Soll der Debug-Link Werkzeuge abweisen, deren Engine-Version oder Build nicht zur laufenden Engine passt?

**Kontext:** Plan WP8.2 verlangt einen harten Reject bei abweichender Engine-Version und abweichendem Build-Hash. Der
erste Entwurf prüfte nur Protokollversion und Token, weil C#-Werkzeuge keinen Engine-Build-Hash kennen; das Review
wertete das als stille Einengung des Plans. Jetzt gilt Schritt 7: andere Engine-Version wird abgewiesen, verschiedene
Build-Hashes nur, wenn beide bekannt sind; „unknown“ wird mit Warnung angenommen. Die endgültige Fassung legt das
Engine-ADR „Debug-Link v1“ per Vertrags-PR fest.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Abweisen, wo prüfbar** (Schritt 7, Branch-Text; im Vertrag Option C) | Harter Reject überall, wo er prüfbar ist; lokale Builds und Builds ohne `GRIMOIRE_BUILD_HASH` verbinden sich |
| **B: Immer hart**, auch bei „unknown“ (im Vertrag Option A) | Strengste Lesart von WP8.2; lokale Builds und Werkzeuge ohne Build-Hash können sich nicht verbinden |
| **C: Nur Protokollversion und Token** (im Vertrag Option B, frühere Empfehlung) | Werkzeuge verbinden sich über Engine-Commits hinweg; engt WP8.2 ein, die Unit-Verträglichkeit sichert allein der `SigilUnit`-Decoder |

**Empfehlung: A.** Sie hält den Plan-Reject, wo er Sinn ergibt, und blockiert die tägliche Arbeit mit lokalen Builds
nicht. Hinweis: Mit Alpha-Tags (P-7 A) wechselt die Engine-Version je Tag; Werkzeuge müssen dann je Tag neu gebaut
werden.

### V-14 — Debug-Link im Release-Build

**Frage:** Darf die Debug-Verbindung für die Abschluss-Messsitzung auch in einem optimierten Release-Build laufen?

**Kontext:** Plan und PRD sprechen von „Debug-Link nur im Dev-Build“. Die Abschluss-Messsitzung (WP11.5) braucht aber
einen Release-Build mit Live-Hot-Swap-Demo. Der Branch macht `debug-link` zu einem standardmäßig ausgeschalteten
Feature ohne `compile_error!` im Release; Distributions-Builds eines Spiels schalten es nie ein (§2 Regel 14).

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Lokal erlaubt, nie ausgeliefert** (Branch-Text) | Messsitzung misst den echten Release; ab P3 prüft die Release-Pipeline des Spiels, dass das Feature fehlt |
| **B: `compile_error!` ohne `debug_assertions`** | Kein Link im Release möglich; die Demo liefe in einem Dev-Build mit `opt-level 3` und verfälscht die Messung |
| **C: Eigenes Profil `measure`** | Klare Trennung; ein weiteres Profil zu pflegen |

**Empfehlung: A**, mit der Prüfung in der Release-Pipeline ab P3 (Merkposten für das Red-Team, R8).

### V-15 — Muster-Vorschau über den Debug-Link

**Frage:** Soll die Engine in P1 selbst eine Muster-Vorschau für den Editor rechnen?

**Kontext:** Der Nachrichtenkatalog v1 enthält `SigilPreview`. Nach dem ADR-0010-Vorschlag (P-2, Sammelsitzung B)
rechnet die Editor-Vorschau über `sigilc simulate`. Der Branch definiert die Nachricht vollständig, damit Codegen und
Fixtures komplett sind, und lässt die Engine in P1 mit `Error(NotSupported)` antworten.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Definiert, Antwort `NotSupported`** (Branch-Text) | Vorschau über `sigilc simulate`; Nachricht später ohne Formatwechsel nutzbar |
| **B: Vorschau in einer isolierten Vorschau-Welt der Engine** | Editor braucht keinen Compiler-Aufruf; zusätzliche Arbeit in WP8 und eine zweite Welt in der Engine |
| **C: Nachricht streichen**, nur die ID reservieren | Kleinerer Katalog; eine spätere Einführung braucht einen Vertrags-PR |

**Empfehlung: A**, solange P-2 in Sammelsitzung B bestätigt wird. Wird P-2 abgelehnt, ist B neu zu prüfen.

### V-16 — Größenprüfung von Packs vor dem Laden

**Frage:** Soll ein zu großes Content-Pack abgewiesen werden, bevor es in den Speicher geladen wird?

**Kontext:** `PackReader::open` las die Datei zunächst vollständig und prüfte erst danach `MAX_PACK_LEN` (1 GiB).
Codex fand den Widerspruch zu §2 Regel 9 (Länge vor Allokation). Der Branch ergänzt deshalb den eingefrorenen P0-Trait
`FileSystem` um die bereitgestellte Methode `read_limited`. Die Kompilierprüfung zeigte, dass bestehende
Implementierungen unverändert kompilieren; im lokalen Arbeitsordner gibt es nur `StdFileSystem` und `MemoryFileSystem`.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: `FileSystem::read_limited`** (Branch-Text) | Die Grenze schützt den Speicher; additive Änderung an einem P0-Trait; fremde Implementierungen ohne Überschreibung schützen nicht |
| **B: §5 bleibt eingefroren** | Prüfung erst nach dem vollständigen Laden; §12 dokumentiert eine Ausnahme von Regel 9 |

**Empfehlung: A.**

---

## Runde 5 — Kollision, Zielen und Änderungsprotokoll

### V-17 — Budget-Gate für die Cluster-Szene

**Frage:** Muss auch der Leistungstest mit dicht gedrängten Kugeln das Kollisionsbudget von 1,5 ms hart einhalten?

**Kontext:** P-3 A ergänzt neben `collide_uniform` die Szene `collide_cluster` (10.000 Kugeln in höchstens 4 Zellen).
Ein uniformes Gitter wird in dichten Clustern konstruktionsbedingt langsamer. P-3 A fügt die Szene hinzu, legt aber
nicht fest, ob sie das Gate bricht. Die Frage, ob Budgets überhaupt hart oder nur als Trend geprüft werden, gehört
laut Agentenlauf zusätzlich zum OF-17.3-ADR.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Uniform hart, Cluster nur als Trend** mit Folge-Issue bei Überschreitung | P1 wird nicht früh blockiert; das Cluster-Ergebnis steuert die P2-Entscheidung über hierarchische oder adaptive Gitter |
| **B: Beide Szenen hart ≤ 1,5 ms** | Strengster Nachweis; ein absehbarer Worst Case kann P1 blockieren |
| **C: Cluster mit eigener höherer Schwelle** (etwa ≤ 3 ms) | Harte Grenze für den Worst Case; der Wert ist nicht belegt |

**Empfehlung: A.** Der Worst Case soll sichtbar sein und P2 steuern, nicht P1 an einer bekannten Schwäche des
uniformen Gitters anhalten.

### V-18 — Größte zulässige Koordinate für Kollisionsformen

**Frage:** Reicht eine Welt von höchstens einer Milliarde Einheiten in jede Richtung für Kollisionsformen?

**Kontext:** Riesige, aber endliche Formen ergaben in der Referenzabfrage `inf <= inf` als Treffer, das Gitter aber
nicht (von Codex gefunden). `MAX_COORD = 1.0e9` begrenzt Koordinaten und Radien gültiger Formen, damit jede
Zwischenrechnung endlich bleibt; an den Rändern liegt der `f32`-Abstand dann bei etwa 64 Einheiten. Die Codex-Frage
gibt keine eigene Empfehlung, sondern bittet um Bestätigung oder die größte Weltausdehnung, die das Spiel braucht.
Zum Vergleich: Der Spieler-Proxy ist auf ±64 begrenzt, das Standard-Gitter umfasst 512 × 512 Einheiten.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: 1.0e9 bestätigen** (Branch-Text) | Keine Änderung; Formen weit außerhalb jeder Arena bleiben gültig, aber ungenau |
| **B: 1.0e6** | `f32`-Abstand an den Rändern etwa 0,06 Einheiten; Formen außerhalb gelten als ungültig (Debug-Abbruch, im Release fachlich unbestimmt) |
| **C: Aus der größten geplanten Arena ableiten** (mit dem Stage-Design in P2), bis dahin 1.0e9 | Passender Wert; ein späteres Absenken macht bisher gültige Formen ungültig und ist damit eine inkompatible Vertragsänderung (§2b Stufe I) |

**Empfehlung: A** als eingetragener Wert. Die Optionen B und C sind hier aus dem Kontext abgeleitet und nicht Teil
der ursprünglichen Frage.

### V-19 — Zielrichtung ohne Entfernung

**Frage:** Reicht in P1 die Zielrichtung der Maus, ohne die Entfernung zum Ziel?

**Kontext:** Die Achsen 2/3 eines `InputFrame` kodieren die Richtung als Einheitsvektor × 32767 (Plan WP1.2, schließt
OP-4). PRD-0013 FR-03 spricht von „Skillshot-Zielen per Maus-Weltposition“, was eine Entfernung nahelegt. Das
Eingabeformat hat vier Achsen; eine Entfernung auf eigener Achse bräuchte mehr.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: Nur Richtung in P1** (Branch-Text) | Kein Formatwechsel; WP11.6 gleicht den PRD-Wortlaut an; das P2-Combat-Kit entscheidet über eine Entfernung |
| **B: Versatz mit fester Höchstreichweite** (i16-Festkomma) | Richtung und Entfernung in zwei Achsen; gröbere Auflösung, feste Reichweite |
| **C: Richtung plus Entfernung auf eigenen Achsen** | Mehr als vier Achsen, also Änderung des `InputFrame`-Formats |

**Empfehlung: A.** Entfernungsabhängige Skillshots sind P2-Gameplay; blockiert in P1 nichts.

### V-20 — Umfang der PO-Freigabe bei späteren Vertragsänderungen

**Frage:** Welche späteren Vertragsänderungen sollen dir zur Freigabe vorgelegt werden?

**Kontext:** §2b stuft Änderungen in K (Klarstellung), A (additiv, PATCH) und I (inkompatibel, MINOR) ein. Das Gate
verlangt adversariales Review, PO-Freigabe und überwachte 3-OS-CI; der Umfang der PO-Freigabe je Stufe ist offen.
Plan-Risiko R22 warnt vor Strängen, die auf Entscheidungen warten.

**Optionen:**

| Option | Folgen |
|--------|--------|
| **A: A und I gebündelt in der nächsten Sammelsitzung**, K nach Review | PO bleibt Torwächter für alles, was Stränge im Code oder in Daten sehen; Wortlaut-Korrekturen warten nicht |
| **B: Jeder Vertrags-PR** | Volle Kontrolle; auch Klarstellungen warten auf eine Sitzung |
| **C: Nur I**, K und A nach Review | Schnellste Stränge; neue Nachrichten, Methoden und Typen kommen ohne PO-Blick |

**Empfehlung: A.** Du bleibst Torwächter für alles, was laufende Stränge in Code oder Daten sehen, und reine
Wortlaut-Korrekturen warten nicht auf eine Sitzung (R22).

---

## Vorläufige Entscheidungen

Alle als vorläufig vermerkten oder im Entwurf ohne eigene Frage festgelegten Entscheidungen, je in einer Zeile.
Punkte mit **→ V-n** werden oben einzeln gefragt; die Frage „Alle übrigen vorläufigen Entscheidungen übernehmen?“
betrifft alle anderen. Punkte aus der WP1.0-Freigabe (Dossier) sind mit „(WP1.0)“ gekennzeichnet.

**ADR-Vorschlag 0008 und §1 Crate-Karte**
- Option 2 mit `grimoire_sigilc`, `grimoire_bench`, `grimoire_link` und der Kante `sigil → ecs` → V-1.
- Dev-Kanten `grimoire_exec → grimoire_sigil` und `→ grimoire_collide` für das Thread-Gate → V-1.
- `grimoire_sigilc` hängt zusätzlich an `sim` und `ecs` für `sigilc simulate` (Abweichung vom Plan-Wortlaut WP1.3).
- Normale und Build-Kanten nur nach unten; Dev-Kanten nach oben nur aus Crates außerhalb der Determinismus-Menge.
- Werkzeug-Crates sind nie Abhängigkeit einer Laufzeit-Crate, auch nicht als Dev-Kante; einzige Werkzeug-Kante `link → sigilc`.
- Laufzeit-Tests nutzen eingecheckte Unit-Fixtures; ein Test in `grimoire_sigilc` prüft ihre Aktualität.
- CI-Kanten-Check über `cargo metadata` gegen eine Positivliste mit Positivkontrolle (Umsetzung WP1.3).
- Keine gemeinsame Typ-Crate; Sigil und Render haben eigene Kennungen, die Fassade bildet sie in P1 als Identität mit Bereichsprüfung ab.
- `grimoire_sigilc` ist einzige Quelle von Binär-Units (P-2, Sammelsitzung B).
- `grimoire_link` ist in P1 kein Release-Artefakt (P-14); `tools/` ist kein Cargo-Mitglied, das Standalone-Gate prüft `tools/**` (P-1).
- `grimoire_audio` und `grimoire_ui` bleiben Platzhalter ohne Kante bis zu einem P2-Crate-Map-ADR.

**§2 Regeln 9–15**
- Regel 9: Decoder fremder Bytes liefern Fehler statt Panic, Längen werden vor der Allokation geprüft, Property-Tests sind Pflicht.
- Regel 10: Binärformate Little-Endian mit Magic und Version, Dokument `docs/formats/<format>.md` im Engine-Repo (P-9) und Golden-Fixtures; Nachrichtenströme versionieren im Handshake.
- Regel 11: JSON mit `u64` als 16 Hexziffern, Ganzzahlen ≤ 2⁵³ − 1, kein NaN, `schema_version`, feste Schlüsselreihenfolge.
- Regel 12: Trait-Verträge sind objektsicher, haben eine Null-Implementierung und eine Konformanz-Suite hinter dem Feature `conformance`.
- Regel 13: Neue wachsende Typen sind `#[non_exhaustive]` mit `Default` oder Konstruktor; ausgenommen `repr(C)`-Layouts und reine Ausgabetypen.
- Regel 14: Features `fixtures`, `debug-link`, `tcp`, `conformance` additiv und standardmäßig aus; CI ohne und mit `--all-features`.
- Regel 14: Paketgewählter CI-Schritt prüft die Auslieferungskonfiguration ohne `grimoire_link` (vorläufig).
- Regel 15: Neue Crate-Kanten nur per Crate-Map-ADR.

**§2a Trait-Entscheid**
- Traits `CollisionQuery` (`SpatialGrid`, `BruteForceQuery`, `NullCollision`), `AssetSource` (`PackReader`, `MemorySource`, `EmptyAssetSource`), `DebugTransport` (`InProcessTransport`, `TcpServerTransport`, `NullTransport`), `SystemObserver` (`NoopObserver`).
- `CollisionQuery` und `AssetSource` sind `Send + Sync`, `DebugTransport` ist `Send`, `SystemObserver` keines von beiden.
- Null-Implementierungen sind panicfrei; einzige Ausnahme ist der `debug_assert!` der Palettenraumprüfung im `NullRenderer`.
- Konkrete Typen statt Traits für `BulletPool`, `SpatialGrid`, `SigilContent`, `AimTarget`, `Emitter`, `ClearRequest`, `GrazeProbe`, `GrazeHits`, Proxy-Komponenten, `BehaviorRegistry` und alle Formattypen.
- Zugriff auf zustandsbehaftete Ressourcen über die API der besitzenden Crate → V-2.

**§2b Änderungsprotokoll**
- Stufen K/A/I mit Versionsfolge; ein Vertrags-PR bündelt Text, Code, Suiten und CHANGELOG; Änderungsprotokoll-Tabelle.
- Umfang der PO-Freigabe je Stufe → V-20.
- Sonderfristen: `BulletInstance` nur vor WP5.3 ändern; `QUERY_BLOCK_SIZE` vor dem Einfrieren der Pattern- und Kollisions-Goldens festlegen.

**§3 Determinismus**
- `grimoire_sigilc` trägt die Determinismus-`clippy.toml` und kompiliert auf einem Thread (sieben identische Dateien).
- Abschließende Liste der Threads außerhalb der Simulation: IO-Thread `grimoire-debug-io` und Threads von winit/wgpu; Werkzeug-Crates starten keine eigenen.
- `check-thread-source.sh` bekommt eine `git grep`-Positivliste und eine Feature-Prüfung für `grimoire_debug/tcp` (WP1.3).
- Profiler-, Stats- und Beobachter-Code liest die Welt nur; Präsentationszustand (Kamera, Zeiger, Viewport, `alpha`) bleibt außerhalb der Welt.

**§5 `grimoire_platform`**
- Bereitgestellte Methode `FileSystem::read_limited` → V-16.

**§6 Render**
- `StageFrame`/`StageStats` mit `supports_stage`/`render_stage` → V-3.
- `BulletInstance` mit `repr(C)`, 24 Byte, eingefrorenen Offsets; vorläufig bis zum OF-3.3-ADR.
- Palettenräume `UNASSIGNED 0`, `HOSTILE 1`, `FRIENDLY 2`; der Bullet-Pass zeichnet nur `HOSTILE`; Zahlenwerte vorläufig bis Stilbibel v0 (P-11).
- Feste Ebenenreihenfolge `World → Vfx → PostFxResolve → Telegraphy → Bullets → PlayerMarker → DebugUi`.
- Ungültige Instanzen werden gezählt, ohne Panic; die Fassade interpoliert, der Renderer nie.

**§7 `grimoire_ecs`**
- `QUERY_BLOCK_SIZE = 1024` bis zum P1-Bench (WP1.0).
- Konformanz-Suite `Executor` in `grimoire_ecs::conformance`.
- §7.1: öffentliches `run_blocks` und `slice_block_ranges` → V-5.
- §7.1: Veränderliche Ressourcen in Blöcken nur in exklusiven Systemen per `mem::take` oder `remove_resource`/`insert_resource`; reine Abbildungen dürfen eigene Blockgrößen wählen.
- §7.2: `SystemObserver` wird je Aufruf übergeben, fünf Rückrufe auf dem aufrufenden Thread, keine Zeitmessung einzelner paralleler Systeme in v1.
- §7.3: `WorldSnapshot::resource` als Lesezugriff auf Snapshots.

**§8 `grimoire_sim`**
- Engine-Ströme mit Bit 63, Spiel-Ströme ohne (WP1.0); Aufteilung 1/15/48 Bit mit Eigentümer-Tabelle → V-4.
- §8.1: Replay v2 mit Magic `GRIMREPL`, Version 2, `header_len`, Engine-Version, 20-Byte-Build-Hash, Content-Manifest, Swap-Liste, Metadaten, Frames wie v1; v1 bleibt lesbar.
- §8.1: Grenzen 64 Byte Engine-Version, 4096 Swaps, 32 Metadaten, strenge kanonische Form, kein Panic in beide Richtungen; Header nie gehasht; MINOR-Sprung.
- §8.1: `ContentManifestHash(u64)` → V-6.
- §8.1: Swap-Liste aus Tick und Content-Hash → V-9.
- §8.1: `ENGINE_BUILD` aus `GRIMOIRE_BUILD_HASH`, sonst `UNKNOWN` → V-10.
- §8.1: Replay v2 entsteht in P1 nur aus Headless-Läufen; Golden Master vergleichen nie Replay-Bytes.
- §8.2: `SimSnapshot::resource` und `Simulation::restore_checked`; `restore` bleibt bedingungslos; kein Snapshot-Binärformat in P1.
- §8.4: Unveränderliche Konfiguration außerhalb der Welt nur unter drei Bedingungen, in P1 nur die `BehaviorRegistry`; `step_observed`.
- §8.4/§11.6: `sigil.begin` bricht bei abweichendem Registry-Fingerprint jeden Tick mit Panic ab (Panic in Bibliothekscode, laut Agentenlauf nach §2 Regel 6 abnahmebedürftig).

**§9 Fassade**
- §9.1: Normale Abhängigkeiten `collide`, `sigil`, `assets`, `debug`; `collide` und `sigil` schon an M1 mit den Skeletten (vorläufig).
- §9.1: Features `fixtures` und `debug-link` aus; Adapter `sigil_render`, `sigil_collide`, `assets`, `debug`; Re-Exporte der vier Crates.
- §9.1: Empfohlene Plugin-Reihenfolge Proxy → Sigil-Installation → `SigilCollidePlugin` → Graze-Leser; Systemnamen `<bereich>.<system>`.
- §9.2: Neue Default-Methoden `extract_stage` (Arbeitsname), `focus`, `on_profile`; `AppBuilder::profiler`, `overlay_key` (F3); `PointerState` getrennt von `InputState`; `FrameStats` unverändert.
- §9.2: Sigil-Typen im Prelude → V-8.
- §9.3: Zielachsen einmal je Frame aus aktuellem Zeiger, zuletzt gerenderter Kamera und Fokuspunkt des Vorframes (ab WP2.2).
- §9.4: `quantize_aim` mit Chebyshev-Skalierung, `[0, 0]` bei nicht endlichen oder zu kleinen Offsets; nur Richtung → V-19.
- §9.4: `Camera25D::screen_to_ground` nutzt nur nach ADR-0004 erlaubte Arithmetik, geprüft per Review und 3-OS-Tabellentest (vorläufig).
- §9.5: Spieler-Proxy mit Standardwerten `speed_per_tick 0.25`, Grenzen ±64, Graze-Radien 0,5/2,0; ein Proxy je Simulation; kein `Collider` in v0.
- §9.6: `GrazeProbe`/`GrazeHits` kommen mit WP1.3, Plugin und Systeme mit WP11.2 (vorläufig).
- §9.6: Broadphase exklusiv; Standard-Gitter Ursprung (−256, −256), Zelle 4, 128 × 128; `bullet_layers = layer(0)`; kein Gegner-Abfragesystem in v0.
- §9.7: Profiler-Scope aus dem Systemnamen vor dem ersten Punkt (vorläufig); Bullet-Zähler über `FrameProfile::add_counter`; Overlay in `debug_sprites`.
- §9.7: Debug-Link aus `TcpConfig::from_env`; Transportfehler trennen nur den Link; Swaps unmittelbar vor dem nächsten `step`.

**§10 `grimoire_exec`**
- `grimoire_exec/tests/conformance.rs` prüft `ThreadPoolExecutor` mit 1, 2 und N Threads gegen die Executor-Suite.

**§11 `grimoire_sigil`**
- §11.1: `SigilUnit` v1 mit 40-Byte-Kopf `GRIMSIGL`, sieben Abschnittsarten, unbekannte abgewiesen, kanonische Kodierung erzwungen, `MAX_UNIT_BYTES` 8 MiB, `MAX_CASCADE_DEPTH` 3.
- §11.1: `content_hash` über `StableHasher` ohne das Hash-Feld; Compiler-Version nur im Pack-Manifest.
- §11.1: Kanonischer Content-Pfad als `AssetPath` relativ zur Content-Wurzel, `sigilc` normalisiert nicht (vorläufig).
- §11.2: `SigilLibrary` hält den `Arc<BehaviorRegistry>`, mit dem sie gebaut wurde (vorläufig).
- §11.3: `BulletPool` als SoA mit Slots, FIFO-Freiliste mit Generationen, Überläufe verworfen und gezählt, Ereignisse leert `sigil.begin`, eingefrorenes Hash-Layout.
- §11.3: `spawn` prüft Unit, Typ, Programmindex, Kaskadentiefe und Endlichkeit und ändert bei Fehler nichts.
- §11.4: Emitter sind zustandslos; ungültige Emitter-Referenzen sind inaktiv → V-7.
- §11.4: Spiele fordern Clears nur über `ClearRequest` an; direktes `BulletPool::clear` nur in exklusiven Systemen von Sigil oder Fassade.
- §11.5: Behaviors als Funktionszeiger mit stabilen IDs; Fingerprint über Version, IDs und Namen; IDs ab `0x8000_0000` für die Engine reserviert.
- §11.6: Fünf exklusive Phasen `begin`, `update`, `resolve`, `emit`, `clear`; `POOL_BLOCK_SIZE = QUERY_BLOCK_SIZE`; keine Trigonometrie je Kugel je Tick.
- §11.7: Ströme `EMIT` (Unterschlüssel Entity) und `UPDATE` (Unterschlüssel Blockindex).
- §11.8: `replace_unit` nur zwischen zwei `step`, alles oder nichts; Kugeln der Unit despawnt, Emitter neu gestartet → V-7.
- §11.8: `ContentEpoch { swaps, manifest_hash }` im Zustands-Hash; `restore_checked` weist fremde Epochen ab; ungeprüftes `restore` bleibt erlaubt.
- Nur eine Sigil-Installation (ein Pool, eine Registry) je Simulation in P1.

**§12 `grimoire_assets`**
- Pack v1 mit 64-Byte-Kopf, 64-Byte-Einträgen streng nach `AssetId`, SHA-256 je Eintrag, 16-Byte-Ausrichtung, Manifest am Ende ohne Zeitstempel.
- Arten: 1 `SIGIL`, 2–5 reserviert und abgewiesen, ab `0x8000` anwendungsdefiniert.
- `AssetPath` nur ASCII `[a-z0-9_.-]` und `/`, keine leeren, `.`- oder `..`-Segmente; die Engine lehnt nur ab.
- `AssetId::from_path` über `StableHasher` v1 mit Präfix `grimoire.asset-id.v1` (C#-Werkzeuge müssen `StableHasher` v1 portieren).
- `read` prüft SHA-256 bei jedem Aufruf; `AssetStore::load` nimmt eine Dekodierfunktion; neue Drittabhängigkeit `sha2`.
- `AssetEntry::new` für fremde `AssetSource`-Implementierungen.
- Größenprüfung vor dem Laden → V-16.

**§13 `grimoire_debug`**
- Frame aus `len u32`, `id u16`, `flags u16`, `seq u32`; `MAX_FRAME_LEN` 16 MiB; Längenfehler schließen, Nutzlastfehler ergeben `Error(Malformed)`.
- Nachrichten-IDs `Hello 0x0001`, `Error 0x0002`, `Log 0x0003`, `Stats 0x0010`, `SwapSigilUnit 0x0020`, `SwapAck 0x0021`, `SigilPreview 0x0022`; Bereiche `0x0100`/`0x0200`/`0x0300` reserviert.
- Anwendungsbereich ab `0x8000` ohne Empfänger-API, Antwort `NotSupported`.
- Für alle Protokollversionen eingefroren: ID und erstes Feld von `Hello`, `MAX_HELLO_FRAME_LEN`, ID und Layout von `Error` (vorläufig).
- Handshake-Reihenfolge Schritte 1–8 (vorläufig); Abweisung von Version und Build → V-13.
- Antworten nach dem Handshake für ID 0, freie und reservierte IDs, falsche Richtung, zweites `Hello` (vorläufig).
- TCP nur an genau `127.0.0.1`, Token 32 Byte aus `GRIMOIRE_DEBUG_TOKEN`, Standardport 47474, ein IO-Thread, `sync_channel` mit 256 Frames, ein Client.
- Zeitgrößen `HANDSHAKE_TIMEOUT` 5 s, `IO_POLL_INTERVAL` 10 ms, `IO_WRITE_TIMEOUT` 100 ms, Grenze `MAX_HELLO_FRAME_LEN` 1024 (vorläufig).
- `to_stats` kürzt deterministisch auf 64 Scopes, 64 Zähler und 64-Byte-Namen (vorläufig).
- `debug-link` im lokalen Release erlaubt → V-14; `SigilPreview` mit `NotSupported` → V-15.

**§14 `grimoire_collide`**
- Umfang nach P-3 A: Formen, Layer-Masken, uniformes Gitter, Graze-Ring ohne Gameplay-Wirkung.
- Exakte Überlappung über Abstandsquadrate, Berührung zählt; `ColliderKey` mit Quelle 0 Entity, 1 Pool, 2–127 Engine, 128–255 Spiele.
- Ergebnisse aufsteigend nach Schlüssel ohne Duplikate, unabhängig von Gitter, Executor und Threads.
- Gitter mit höchstens 2²⁰ Zellen, Punkte außerhalb in Randzellen; `SpatialGrid` ist gehashter Zustand.
- Blockgrößen von `rebuild_par` und `overlapping_batch` sind kein Vertragsbestandteil.
- `MAX_COORD = 1.0e9` → V-18.
- Bench-Szenarien `collide_uniform` und `collide_cluster` mit 1 und N Threads, Budget ≤ 1,5 ms; Gate für die Cluster-Szene → V-17.

**§15 `grimoire_bench`**
- Schema-Typen für Bench-Ergebnisse und Golden Master in der Bibliothek von `grimoire_bench` (Spiel-Harness hängt damit an einer Engine-Werkzeug-Crate; Folgefrage im ADR-Vorschlag).
- Größengrenzen der JSON-Leser und Pfadregel nach `AssetPath` (vorläufig).
- `BenchResult` als JSON Lines, streng, mit nachgerechnetem Median, Herkunft `runner`/`reference`/`estimate`.
- `GoldenMaster` `grimoire.golden` v1 mit Algorithmus-Versionen und optionalen Subsystem-Hashes; `compare`-Reihenfolge `NotEligible > ContentChanged > ShapeMismatch > Diverged > Match`; `renewals.jsonl`.
- Bestehende Golden-Konstanten bleiben Konstanten, keine Migration in P1.

**Spiel-Entwurf `spiel-vertraege-entwurf.md`**
- `Scene` und `BotProfile` bleiben Traits; `HarnessReport` konkret → V-12.
- Content-Pfade der Szene gehen unverändert an `sigilc` und ergeben dieselben `UnitId`s wie Pack und `grimoire-link` (vorläufig).
- Standard-Invarianten `no_nan` über einen eigenen Hasher, `no_panic` per `catch_unwind`, `pool_limits`, `clear_within_one_tick` (vorläufig).
- Leser des Berichts streng mit Grenzen 64 MiB, 1024 Metriken, 256 Invarianten, 10.000 Events (vorläufig).
- Spiel-Ströme über `app_stream` mit Eigentümer `0x0001` Bots und `0x0002` `fnp_game`; P0-Konstanten bleiben.
- Golden Master unter `Prototype/tests/golden/`, Abgleich pro Push auf Linux, nightly auf 3 OS; nur `Match` besteht, `ContentChanged` → V-11.

---

## Einfluss der Sammelsitzung A

Am besten wird diese Runde **nach** Runde 1 des Dossiers (P-8, P-7, P-1, P-3) und nach der WP1.0-Freigabe gestellt;
P-9 sollte vor der Frage in Runde 6 beantwortet sein. Weicht eine Antwort von der Empfehlung ab, ändern sich die
Fragen so:

- **P-3 = B** (Kollision wie im Plan, ohne Cluster-Szene): V-17 entfällt; V-18 bleibt.
- **P-3 = C** (Kollision erst in P2): V-17 entfällt. V-18 wird unkritisch, weil WP1.2 laut Dossier trotzdem den Trait
  schneidet, die Formen aber erst in P2 genutzt werden. In V-1 entfällt die Dev-Kante `exec → collide`, und das
  Kollisions-Szenario im Thread-Gate fällt weg. Der Adapter aus §9.6 und die Kollisionsanteile in §9.1 werden auf den
  Trait reduziert.
- **P-8 = B** (Zusatzdatei statt Replay v2): V-9 und V-10 wandern in das Format der Zusatzdatei (Swap-Liste und
  Build-Hash stehen dort statt im Header); §8.1 entfällt als Replay-Version 2. V-6 bleibt, weil Content-Epoche und
  Golden Master den Hash brauchen. V-11 bleibt.
- **P-8 = C** (Replay v2 erst in P3): V-9 und V-10 entfallen für P1; das Erfolgskriterium „Replay-Header tragen
  Build-Hash und Engine-Pin“ wird verschoben. V-6 bleibt für Content-Epoche und Golden Master. V-11 wird schwächer:
  Golden Master erkennen Content-Wechsel nur, solange ihr eigenes Feld `content_manifest` bestehen bleibt.
- **P-7 = B** (Patch-Versionen `0.1.x`): nur zulässig mit P-8 ≠ A und ohne inkompatible Änderung in P1. Dann darf
  §2b-Stufe I in P1 gar nicht vorkommen (V-20); V-3 Option B wäre ausgeschlossen, und die Replay-Version-2-Einstufung
  in §8.1 muss neu gefasst werden.
- **P-7 = C** (Commit-Pins ohne Zwischenversionen): `ENGINE_VERSION` bleibt über viele Commits gleich. Der Build-Hash
  wird damit zur eigentlichen Unterscheidung, V-10 und V-13 gewinnen an Gewicht. Mit A in V-13 verbinden sich
  Werkzeuge mit „unknown“-Builds dann über Commit-Grenzen hinweg.
- **P-7 = A** (Empfehlung): In V-13 müssen Werkzeuge je Alpha-Tag neu gebaut werden, weil die Engine-Version byteweise
  verglichen wird.
- **P-9 = B** (alle Formatdokumente im Engine-Repo): keine Änderung für P1, weil P1 nur Engine-Formate hat.
- **P-9 = C** (alle Formatdokumente im Spiel-Repo): §2 Regel 10 und die Dokumentpfade in §8.1, §11.1, §12, §13 und §15
  müssten ins Spiel-Repo verweisen. Das widerspricht dem Standalone-Gedanken des Engine-Vertrags; der Text wäre vor der
  Freigabe zu überarbeiten, und die Frage in Runde 6 sollte dann „Vertrag anhalten“ nahelegen.
- **Außerhalb von P-3/P-7/P-8/P-9:** P-1 = D (C#-Seite nach P2) macht V-15 weniger dringlich und nimmt V-13 den
  Grund „C#-Werkzeuge ohne Build-Hash“. P-2 abgelehnt (Sammelsitzung B) stellt V-15 neu und ergänzt V-1 um einen
  zweiten Unit-Erzeuger außerhalb der Determinismus-Menge. P-14 ≠ A ändert den Eintrag „`grimoire_link` kein
  Release-Artefakt“.

---

## Fragenentwurf

**Reihenfolge:** Runde 1 entblockt WP1.3 und die zuerst startenden Stränge, Runde 2 die Sigil-Laufzeit, Runde 3 WP7,
Runde 4 WP8, Runde 5 Kollision, Zielen und §2b. Runde 6 gibt den Rest im Ganzen frei. Jede Runde ist ein
`AskUserQuestion`-Aufruf mit `multiSelect: false`; jede Frage beginnt mit der praktischen Wirkung, technische Namen
stehen im Text oben.

**Regeln für die Durchführung:**

- **Überspringen:** Bei P-3 = B oder C entfällt „Cluster-Gate“ (V-17) in Runde 5; bei P-8 = C entfallen „Swap-Replay“
  (V-9) und „Build-Hash“ (V-10) in Runde 3. Eine Runde mit weniger Fragen bleibt ein Aufruf.
- **Anpassen:** Bei P-7 = B entfällt in Runde 1 die Option „Alten Frame erweitern“ (V-3), und in Runde 5 ist die
  Beschreibung von „Änderungen“ (V-20) um „brechende Änderungen kommen in P1 nicht vor“ zu ergänzen. Wird P-2 in
  Sammelsitzung B abgelehnt, ist „Vorschau“ (V-15) vor Runde 4 neu zu fassen. Bei P-9 = C wird Runde 6 erst nach
  Überarbeitung des Vertrags gestellt.
- **V-1 Option 4** (Format-Crate), **V-7 „Kugeln mit neuem Layout weiterlaufen“** und **V-13 „nur Engine-Version
  abweisen“** werden nicht angeboten; der PO kann sie über die freie Antwort wählen.
- **Runde 6:** Wählt der PO „Vertrag anhalten“, werden keine Skelette gebaut; wählt er „Später einzeln durchgehen“,
  beginnt WP1.3 erst mit den dann bestätigten Punkten.

### Runde 1 — Crate-Schnitt und Grundregeln

```json
{
  "questions": [
    {
      "header": "Crate-Karte",
      "question": "Sollen Sigil-Compiler, Benchmarks und das Link-Werkzeug als eigene Crates neben der Engine-Laufzeit entstehen, und dürfen die Thread-Tests Sigil und Kollision direkt einbinden?",
      "multiSelect": false,
      "options": [
        {"label": "Eigene Crates mit Test-Kanten (Empfohlen)", "description": "Der Compiler kann die Laufzeit nie erreichen, und plattformabhängige Rechnungen im Compiler fallen schon im lokalen Clippy-Lauf auf."},
        {"label": "Eigene Crates ohne Test-Kanten", "description": "Wie empfohlen, aber die Thread-Tests erreichen Sigil und Kollision nur über die Fassade, wofür Sigil-Tests selbst eine Kante zur Fassade bräuchten."},
        {"label": "Compiler ohne Determinismus-Lints", "description": "Freiere Compiler-Programmierung, dafür fallen plattformabhängige Units erst im teuren Vergleich auf drei Betriebssystemen auf."},
        {"label": "Alles in bestehenden Crates", "description": "Keine neuen Crates, aber der Parser liegt hinter einem Feature im Laufzeit-Crate und zwei eigentlich verbotene Kanten entstehen."}
      ]
    },
    {
      "header": "Ressourcen",
      "question": "Dürfen Spielsysteme den Kugel-Pool und das Kollisionsgitter direkt lesen, wenn sie den Lesezugriff anmelden?",
      "multiSelect": false,
      "options": [
        {"label": "Lesen mit Anmeldung (Empfohlen)", "description": "Lesen über die API der besitzenden Crate auch parallel, verändern dürfen nur Systeme dieser Crate oder der Fassade oder Anfragen wie ein Clear."},
        {"label": "Nur über Fassaden-Systeme", "description": "Wörtlich wie im Plan: Spiele bekommen nur Kopien oder Ereignisse, was je Tick eine Kopie von bis zu 10.000 Kugeln kostet."},
        {"label": "Je Ressource entscheiden", "description": "Der Planwortlaut bleibt, und jede Crate regelt den Zugriff auf ihre Ressourcen in ihrem eigenen Abschnitt."}
      ]
    },
    {
      "header": "Render-Kanal",
      "question": "Wie soll der Renderer die neuen Kanäle für Kugeln, Spieler-Marker und Debug-Anzeige bekommen, ohne bestehenden Code zu brechen?",
      "multiSelect": false,
      "options": [
        {"label": "Eigener Bühnen-Frame (Empfohlen)", "description": "Ein neuer erweiterbarer Frame-Typ umschließt den alten, sodass alte Typen und fremde Renderer unverändert kompilieren."},
        {"label": "Alten Frame erweitern", "description": "Nur ein Frame-Typ, aber vorhandener Code in Engine und Spiel, der Frames direkt zusammensetzt, kompiliert nicht mehr, entgegen der Zusage im Plan zu WP2.2."},
        {"label": "Separater Kugel-Aufruf", "description": "Der alte Frame bleibt, Kugeln kommen über einen eigenen Aufruf vor dem Rendern, was Aufrufreihenfolge und Zustand koppelt."}
      ]
    },
    {
      "header": "Zufall",
      "question": "Soll die Nummerierung der Zufallsströme so aufgeteilt werden, dass Engine-Teile und Spiel nie denselben Zufall ziehen können?",
      "multiSelect": false,
      "options": [
        {"label": "Bitfelder je Eigentümer (Empfohlen)", "description": "Oberstes Bit für die Engine, 15 Bit Eigentümer und 48 Bit lokale Nummer, kollisionsfrei durch den Aufbau und ohne Änderung bestehender Hashes."},
        {"label": "Nur Engine-Bit festlegen", "description": "Wie auf dem Scheduler-Branch teilt jede Crate formlos auf, und Kollisionen fallen nur im Review auf."},
        {"label": "Zentrale Tabelle mit Test", "description": "Alle Ströme stehen in einer Liste ohne Bitfelder, und ein Test prüft ihre Eindeutigkeit."}
      ]
    }
  ]
}
```

### Runde 2 — Grundlagen der Sigil-Laufzeit

```json
{
  "questions": [
    {
      "header": "Blöcke",
      "question": "Sollen Kugel-Pool und Kollisionsgitter denselben Mechanismus zur Parallelisierung nutzen wie die ECS-Abfragen des Schedulers?",
      "multiSelect": false,
      "options": [
        {"label": "Gemeinsamer Blockläufer (Empfohlen)", "description": "Der interne Blockläufer des ECS wird öffentlich, damit Panic-, Reihenfolge- und Debug-Regeln nur einmal implementiert sind, rein additiv."},
        {"label": "Kopie je Crate", "description": "Sigil und Kollision bekommen je eine eigene Kopie mit denselben Regeln, der Scheduler-Abschnitt bleibt unberührt."},
        {"label": "Neue Welt-Methode", "description": "Ressourcen-Blöcke laufen über eine neue Methode der Welt, was tiefer in den Scheduler-Vertrag eingreift."}
      ]
    },
    {
      "header": "Content-Hash",
      "question": "Wie genau soll die Kennung des geladenen Contents sein, die Aufzeichnungen, Vergleichstests und Debug-Link verwenden?",
      "multiSelect": false,
      "options": [
        {"label": "64-Bit-Hash der Engine (Empfohlen)", "description": "Gleiches Verfahren wie der Zustands-Hash ohne neue Abhängigkeit in Determinismus-Crates, und 64 Bit reichen zur Identifikation von Content."},
        {"label": "32-Byte-SHA-256", "description": "Kryptografisch stark, braucht aber sha2 oder Formattypen in Determinismus-Crates und eine neue Auslegung von ADR-0005."},
        {"label": "Beides zusammen", "description": "64 Bit im Zustand und SHA-256 zusätzlich in den Replay-Metadaten, was sich auch später noch ohne Bruch ergänzen ließe."}
      ]
    },
    {
      "header": "Live-Tausch",
      "question": "Was soll beim Live-Tausch eines Musters mit Kugeln passieren, die schon fliegen, und mit Emittern, die es danach nicht mehr gibt?",
      "multiSelect": false,
      "options": [
        {"label": "Kugeln weg, Emitter ruhen (Empfohlen)", "description": "Kugeln des Musters verschwinden und Emitter starten neu, entfernte Emitter bleiben inaktiv und laufen wieder, sobald sie zurückkommen."},
        {"label": "Verkleinernden Tausch ablehnen", "description": "Kugeln verschwinden wie empfohlen, aber ein Tausch, der von laufenden Emittern genutzte Blöcke entfernt, scheitert und blockiert gewöhnliches Bearbeiten."},
        {"label": "Überzählige Emitter löschen", "description": "Kugeln verschwinden wie empfohlen, und Emitter ohne Gegenstück werden aus der Welt entfernt, was in Spiel-Entities eingreift."},
        {"label": "Kugeln auslaufen lassen", "description": "Fliegende Kugeln laufen mit dem alten Muster zu Ende, das dafür zusätzlich im Speicher bleibt, entfernte Emitter ruhen."}
      ]
    },
    {
      "header": "Prelude",
      "question": "Welche Sigil-Typen soll ein Spiel ohne vollen Pfad direkt über das Prelude der Fassade nutzen können?",
      "multiSelect": false,
      "options": [
        {"label": "Kleine Auswahl (Empfohlen)", "description": "Emitter, Ziel, Clear-Anfrage, Clear-Filter, Unit-ID und Sigil-Konfiguration, mit wenig Raum für Namenskollisionen."},
        {"label": "Keine Sigil-Typen", "description": "Alles läuft über grimoire::sigil, wodurch Beispiele und Spielcode länger werden."},
        {"label": "Alle Sigil-Typen", "description": "Bequem, vergrößert aber die Prüfung auf Namenskollisionen mit den Spiel-Crates."}
      ]
    }
  ]
}
```

### Runde 3 — Replay, Golden Master und Harness

```json
{
  "questions": [
    {
      "header": "Swap-Replay",
      "question": "Was sollen Aufzeichnungen in P1 über Live-Tausche von Mustern festhalten?",
      "multiSelect": false,
      "options": [
        {"label": "Tick und Content-Hash (Empfohlen)", "description": "16 Byte je Tausch, nie golden, und ohne dieselben Units nur bis zum ersten Tausch nachspielbar."},
        {"label": "Nur ein Merkmal", "description": "Nur die Angabe, dass getauscht wurde, nie golden, aber Zeitpunkt und Ziel des Tauschs fehlen."},
        {"label": "Mit Unit-Bytes", "description": "Tauschsitzungen lassen sich vollständig nachspielen, die Aufzeichnungen werden dafür deutlich größer."},
        {"label": "Merkmal jetzt, Rest P2", "description": "In P1 nur das Merkmal, die volle Aufzeichnung folgt mit dem Rewind-Spike in P2 als neue Formatversion."}
      ]
    },
    {
      "header": "Build-Hash",
      "question": "Reicht es, wenn lokal gebaute Aufzeichnungen keinen Build-Hash tragen, solange die CI ihn immer setzt?",
      "multiSelect": false,
      "options": [
        {"label": "Ja, CI setzt ihn (Empfohlen)", "description": "Lokal steht unbekannt, Engine- und Spiel-CI setzen den Commit, und der Engine-Pin steht zusätzlich in den Metadaten."},
        {"label": "Immer Pflicht", "description": "Ohne gesetzte Variable schlägt jeder Build fehl, auch lokal, was die tägliche Arbeit bremst."},
        {"label": "Engine ermittelt ihn selbst", "description": "Das Build-Skript fragt git, was nicht reproduzierbar ist und in Cargo-git-Checkouts ohne .git scheitern kann."}
      ]
    },
    {
      "header": "Golden rot",
      "question": "Wie soll die CI reagieren, wenn ein Vergleichstest nur wegen geändertem Content abweicht?",
      "multiSelect": false,
      "options": [
        {"label": "Rot, Erneuerung per Kommando (Empfohlen)", "description": "Wie bei jeder Golden-Abweichung wird der Master mit dem Ein-Kommando-Werkzeug in einem eigenen Commit erneuert, nichts ändert sich still."},
        {"label": "Warnung bei Content-Commit", "description": "Ändert derselbe Push Content-Dateien, gibt es nur eine Warnung statt Rot, und eine Warnung wird leichter übersehen."},
        {"label": "Automatisch erneuern", "description": "Die CI schreibt den Master selbst neu, entgegen der Regel, dass Goldens nie still erneuert werden."}
      ]
    },
    {
      "header": "Bericht",
      "question": "Darf der Bericht der Sim-Harness ein fester Datentyp mit JSON-Schema sein statt einer austauschbaren Schnittstelle, wie der Plan sie nennt?",
      "multiSelect": false,
      "options": [
        {"label": "Fester Datentyp (Empfohlen)", "description": "Der Bericht ist reine Daten, CI und Dashboard brauchen ein stabiles Schema, und Szene und Bot bleiben austauschbare Schnittstellen."},
        {"label": "Schnittstelle wie im Plan", "description": "Der Bericht wird ein Trait mit Null-Implementierung, und das JSON-Schema kommt trotzdem zusätzlich hinzu."}
      ]
    }
  ]
}
```

### Runde 4 — Dev-Link und Pack

```json
{
  "questions": [
    {
      "header": "Handshake",
      "question": "Soll der Debug-Link Werkzeuge abweisen, deren Engine-Version oder Build nicht zur laufenden Engine passt?",
      "multiSelect": false,
      "options": [
        {"label": "Abweisen, wo prüfbar (Empfohlen)", "description": "Eine andere Engine-Version wird abgewiesen, ein anderer Build nur, wenn beide Seiten ihn kennen, lokale Builds verbinden sich mit Warnung."},
        {"label": "Immer hart abweisen", "description": "Auch ein unbekannter Build wird abgewiesen, sodass sich lokale Builds und Werkzeuge ohne Build-Hash nicht verbinden können."},
        {"label": "Nur Protokollversion prüfen", "description": "Engine-Version und Build werden nur protokolliert, was den Plan einengt und die Unit-Prüfung allein dem Decoder überlässt."}
      ]
    },
    {
      "header": "Link-Build",
      "question": "Darf die Debug-Verbindung für die Abschluss-Messsitzung auch in einem optimierten Release-Build eingeschaltet werden?",
      "multiSelect": false,
      "options": [
        {"label": "Lokal erlaubt, nie ausgeliefert (Empfohlen)", "description": "Das Feature ist standardmäßig aus, Distributions-Builds schalten es nie ein, und ab P3 prüft die Release-Pipeline das."},
        {"label": "Nur in Debug-Builds", "description": "Ohne Debug-Assertions gibt es einen Übersetzungsfehler, die Hot-Swap-Demo liefe in einem Dev-Build und verfälscht die Messung."},
        {"label": "Eigenes Messprofil", "description": "Ein eigenes Profil aus Release plus Debug-Link ist erlaubt, alles andere verboten, mit einem Profil mehr zu pflegen."}
      ]
    },
    {
      "header": "Vorschau",
      "question": "Soll die Engine in P1 selbst eine Muster-Vorschau für den Editor rechnen, oder übernimmt das der Sigil-Compiler?",
      "multiSelect": false,
      "options": [
        {"label": "Vorschau über sigilc (Empfohlen)", "description": "Die Nachricht ist definiert und die Engine antwortet nicht unterstützt, solange die Compiler-Hoheit in Sammelsitzung B bestätigt wird."},
        {"label": "Vorschau in der Engine", "description": "Eine isolierte Vorschau-Welt in der Engine schon in P1, mit mehr Arbeit im Dev-Link-Paket."},
        {"label": "Nachricht streichen", "description": "Nur die Nachrichtennummer bleibt reserviert, eine spätere Einführung braucht dann einen Vertrags-PR."}
      ]
    },
    {
      "header": "Pack-Größe",
      "question": "Soll ein zu großes Content-Pack abgewiesen werden, bevor es vollständig in den Speicher geladen wird?",
      "multiSelect": false,
      "options": [
        {"label": "Vor dem Laden prüfen (Empfohlen)", "description": "Eine bereitgestellte Methode am Dateisystem-Trait aus P0 schützt den Speicher und bricht keine bestehende Implementierung."},
        {"label": "Nach dem Laden prüfen", "description": "Der P0-Trait bleibt eingefroren, das Pack wird erst ganz gelesen und dann abgewiesen, als dokumentierte Ausnahme von Regel 9."}
      ]
    }
  ]
}
```

### Runde 5 — Kollision, Zielen und Änderungsprotokoll

```json
{
  "questions": [
    {
      "header": "Cluster-Gate",
      "question": "Muss auch der Leistungstest mit dicht gedrängten Kugeln das Kollisionsbudget von 1,5 ms hart einhalten?",
      "multiSelect": false,
      "options": [
        {"label": "Cluster nur als Trend (Empfohlen)", "description": "Die normale Szene gilt hart, die Cluster-Szene nur als Trend mit Folge-Issue und steuert in P2 die Wahl eines feineren Gitters."},
        {"label": "Beide Szenen hart", "description": "Beide Szenen brechen bei mehr als 1,5 ms den Lauf, obwohl ein gleichmäßiges Gitter bei Clustern absehbar langsamer wird."},
        {"label": "Eigene höhere Schwelle", "description": "Die Cluster-Szene bekommt einen eigenen Grenzwert von etwa 3 ms, der bisher nicht belegt ist."}
      ]
    },
    {
      "header": "Weltgrenze",
      "question": "Reicht eine Welt von höchstens einer Milliarde Einheiten in jede Richtung für Kollisionsformen?",
      "multiSelect": false,
      "options": [
        {"label": "Eine Milliarde bestätigen (Empfohlen)", "description": "Der eingetragene Wert hält jede Zwischenrechnung endlich, an den Rändern liegt die Genauigkeit bei etwa 64 Einheiten."},
        {"label": "Eine Million", "description": "An den Rändern etwa 0,06 Einheiten genau, und Formen weiter außen gelten als ungültig."},
        {"label": "Aus Arena-Größe ableiten", "description": "Bis zum Stage-Design in P2 gilt eine Milliarde, danach ein Wert aus der größten Arena, wobei das Absenken eine inkompatible Vertragsänderung ist."}
      ]
    },
    {
      "header": "Zielen",
      "question": "Reicht in P1 die Zielrichtung der Maus, ohne die Entfernung zum Ziel?",
      "multiSelect": false,
      "options": [
        {"label": "Nur Richtung in P1 (Empfohlen)", "description": "Wie im Plan und ohne Formatwechsel, ob Skillshots eine Entfernung brauchen, entscheidet das Combat-Kit in P2."},
        {"label": "Versatz mit Höchstreichweite", "description": "Richtung und Entfernung bis zu einer festen Reichweite in denselben zwei Achsen, dafür gröber aufgelöst."},
        {"label": "Entfernung auf eigener Achse", "description": "Braucht mehr als vier Eingabeachsen und damit eine Änderung des Eingabeformats."}
      ]
    },
    {
      "header": "Änderungen",
      "question": "Welche späteren Änderungen an gemergten Verträgen sollen dir zur Freigabe vorgelegt werden?",
      "multiSelect": false,
      "options": [
        {"label": "Additive und brechende (Empfohlen)", "description": "Gebündelt in der nächsten Sammelsitzung, reine Klarstellungen mergen nach dem Review und stehen nur im Änderungsprotokoll."},
        {"label": "Jede Änderung", "description": "Auch Wortlaut-Korrekturen warten auf eine Sitzung, was laufende Stränge länger aufhält."},
        {"label": "Nur brechende Änderungen", "description": "Additive Änderungen und Klarstellungen mergen nach dem Review ohne deine Freigabe."}
      ]
    }
  ]
}
```

### Runde 6 — Freigabe der übrigen vorläufigen Entscheidungen

Setzt Runde 1 bis 5 voraus. Gemeint ist die Liste „Vorläufige Entscheidungen“ ohne die Punkte mit **→ V-n**. Die
Ergänzungen in den Scheduler-Abschnitten (§7.1–§7.3, §8.2, §8.4) brauchen trotz Übernahme noch die Durchsicht des
Scheduler-Eigentümers (offener Punkt des Agentenlaufs).

```json
{
  "questions": [
    {
      "header": "Übernahme",
      "question": "Alle übrigen vorläufigen Entscheidungen übernehmen?",
      "multiSelect": false,
      "options": [
        {"label": "Alle übernehmen (Empfohlen)", "description": "Die Liste gilt als freigegeben, WP1.3 beginnt, und gemergt wird erst nach adversarialem Review und grüner CI auf drei Betriebssystemen."},
        {"label": "Später einzeln durchgehen", "description": "Die Punkte bleiben vorläufig, und WP1.3 beginnt erst mit den Teilen, die du später einzeln bestätigst."},
        {"label": "Vertrag anhalten", "description": "Keine Skelette und kein Start der parallelen Stränge, bis der Entwurf überarbeitet ist."}
      ]
    }
  ]
}
```

## Quellen

- Engine-Branch `p1/wp1.2-contracts-draft` (Kopf `f9765dd`, gelesen im Worktree `<Arbeitsordner>\_wt\p1-contracts`): `docs/architektur/crate-vertraege.md` (§1–§16), `docs/adr/0008-crate-map-erweiterung-p1.md`
- Spiel-Repo: [Spiel-Verträge (Entwurf)](../architektur/spiel-vertraege-entwurf.md), [Plan 0002](0002-phase-p1-sichtbarer-kern.md) (WP1.2, WP1.3, WP1.7, Meilensteine, Offene PO-Entscheidungen, Offene Punkte), [Dossier Sammelsitzung A](0002-sammelsitzung-a-dossier.md), [Agentenlauf 2026-09-15](agentenlauf-2026-09-15.md)
- Agentenlauf-Ergebnisse (Scratchpad): `agentenlauf/wp1.2-result.json` (`integrated.po_questions`, `integrated.decisions`, `integrated.open_issues`, `review`, `final`), `agentenlauf/codex-followups-result.json` (`contract.applied`), `agentenlauf/contract-check-result.json` (`applied`)

## Nicht bestätigte Angaben

- Optionen B und C in V-18 sind aus dem Kontext abgeleitet; die ursprüngliche Frage nennt nur den Wert 1.0e9 und bittet um Bestätigung. Die `f32`-Abstände (etwa 64 bzw. 0,06 Einheiten) sind aus der Größenordnung gerechnet, nicht gemessen.
- Ob `option_env!` bei geänderter `GRIMOIRE_BUILD_HASH` zuverlässig neu baut, ob Cargo-git-Checkouts `.git` enthalten und ob Alpha-Tags die Cargo-Version auf `0.2.0-alpha.N` setzen: laut Agentenlauf nicht geprüft (V-10, V-13).
- Die Zustimmung des Scheduler-Eigentümers zu den Ergänzungen in §7.1–§7.3, §8.2 und §8.4 steht aus (offener Punkt des Agentenlaufs).
- Die Kompilierprüfung deckt nur Signaturen ab; Verhalten, Leistung und die Ausführbarkeit von `mem::take` auf dem Pool oder `run_blocks` mit Nicht-ECS-Aufgaben sind nicht umgesetzt oder gemessen.
- Das adversariale Review im Sinne des WP1.7-Gates bezieht sich auf den künftigen Vertrags-PR mit Skeletten und hat noch nicht stattgefunden; die Reviews des Laufs betrafen den Entwurf.
- Das Restkontingent an Actions-Minuten ist aus dem Dossier übernommen und nicht erneut gelesen. *(Nachtrag 2026-09-15: gegenstandslos, die Repos sind öffentlich.)*

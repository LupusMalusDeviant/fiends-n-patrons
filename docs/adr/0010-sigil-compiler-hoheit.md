# ADR-0010: Sigil-Compiler-Hoheit in Rust (`grimoire_sigilc`), C#-Werkzeuge orchestrieren per CLI/JSON

- **Status:** Akzeptiert (2026-09-15; PO-Entscheidung in Sammelsitzung B)
- **Datum:** 2026-09-15
- **Entscheider:** Lupus Malus Deviant (PO), Entscheidung ausstehend in Sammelsitzung B (Plan 0002, P-2); vorbereitet durch Claude
- **Bezug:** [Plan 0002](../plans/0002-phase-p1-sichtbarer-kern.md) (WP1.5, WP4, WP5.6, WP7.4, WP8.5, WP9, WP10, P-2, P-10, R14, R20, M1), [PRD-0000](../prd/0000-index-fiends-n-patrons.md) (E07, E20, §6), [PRD-0002](../prd/0002-grimoire-engine-architektur.md) (FR-01), [PRD-0003](../prd/0003-rendering-und-art.md) (Lesbarkeitsregeln), [PRD-0004](../prd/0004-sigil-bullet-system.md) (FR-08, FR-10), [PRD-0016](../prd/0016-tooling-suite.md) (FR-01, FR-02, FR-04, FR-10, OF-16.1, OF-16.2), [PRD-0017](../prd/0017-plattform-ci-distribution.md), [PRD-0018](../prd/0018-teststrategie.md) (FR-04, FR-09), [ADR-0001](0001-rust-kern-csharp-tooling.md), [ADR-0005](0005-voll-deterministische-simulation.md), [ADR-0006](0006-sigil-daten-dsl-statt-scripting.md), [ADR-0007](0007-offline-asset-kompilierung.md), [ADR-0008](0008-avalonia-fuer-tooling.md), Projekt-ADR-0011 (Vorschlag, Schema-Codegen OF-16.2), [Dossier Sammelsitzung A](../plans/0002-sammelsitzung-a-dossier.md) (P-1, P-6, P-9, P-13), [Fragenrunde Vertragsfreigabe WP1.2](../plans/0002-vertragsfreigabe-wp1.2.md) (V-1, V-15), Engine-Vertrag [`crate-vertraege.md`](https://github.com/LupusMalusDeviant/grimoire/blob/p1/wp1.2-contracts-draft/docs/architektur/crate-vertraege.md) §1, §3, §11.1, §12, §13 und Engine-ADR-Vorschläge 0007 (Sigil-Quelltextsyntax v1) und 0008 (Crate-Map-Erweiterung P1)

## Kontext

Sigil-Patterns sind Daten (ADR-0006). ADR-0007 legt fest, dass die Engine nur binäre Packs lädt und Parser
sowie Import-Komplexität ins Tooling gehören. Seine Entscheidung nennt dafür ausdrücklich den C#-Asset-Compiler:
„Der C#-Asset-Compiler validiert und kompiliert alle Quellen in versionierte Packs“. Das Entscheidungsregister nennt als Weg „Offline-Kompilierung
(C#-Tooling) → binäre Packs“ (PRD-0000 E07). PRD-0016 FR-01 verlangt einen Asset-Compiler als C#-CLI, der
unter anderem die „Sigil-Statik“ validiert und kompiliert. FR-04 verlangt eine „Tool-interne 2D-Preview“,
der Werkzeugkatalog präzisiert sie als „eigene einfache Canvas-Sim“. PRD-0004 lässt den Ort des Compilers
offen („C#-Tooling oder `grimoire_sigil`“).

Plan 0002 ist inzwischen anders geschnitten. Er setzt eine Rust-Umsetzung voraus, die aber noch niemand
entschieden hat:

- **WP4** baut Parser, Validator und Compiler in der Rust-Crate `grimoire_sigilc` mit der CLI `sigilc`
  (`check`, `build`, `fmt`, `parse --json`, `set`). **WP4.4** vergleicht die Units von Windows, Linux und macOS
  byteweise.
- **WP5.6** ergänzt `sigilc simulate --ticks N --json` über denselben Interpreter, den die Laufzeit nutzt.
- **WP7.4** (Sim-Harness im Spiel) und **WP8.5** (`grimoire-link watch`, der DoD-Nachweis „Hot-Reload via
  Dev-Link“) binden `grimoire_sigilc` als Bibliothek ein.
- **WP9.2** lässt den C#-Asset-Compiler `grimoire-ac` `sigilc build --json` aufrufen und die Diagnosen
  unverändert durchreichen. **WP10.2–10.4** holen Diagnosen, Parameter, Rückschreiben und Vorschau aus
  `sigilc`, ohne Parser in C#.

Der Engine-Vertragsentwurf baut bereits darauf auf, jeweils als vorläufig markiert:

- §1 und Engine-ADR-Vorschlag 0008 führen `grimoire_sigilc` als Werkzeug-Crate an `sigil`, `sim`, `ecs` und
  `core`. Keine Laufzeit-Crate hängt an ihr, und sie ist „die einzige Quelle von Binär-Units“.
- §3 nimmt den Compiler in die Determinismus-Menge auf und gibt ihm die siebte identische `clippy.toml`.
- §11.1 legt `SigilUnit` v1 kanonisch fest: Für jede gültige Eingabe gilt `to_bytes(from_bytes(b)) == b`.
  Weiter heißt es dort: „In P1 ist `sigilc` der einzige Erzeuger (P-2); die C#-Seite erzeugt keine Units.“
- §12 schreibt Compiler-Name und -Version ins Pack-Manifest, nicht in die Unit.
- §13 definiert `SigilPreview`, die Engine antwortet in P1 aber mit `NotSupported`, weil die Vorschau über
  `sigilc simulate` läuft (Vertragsfreigabe WP1.2, V-15).

Auch der Syntax-Spike (Engine-ADR-Vorschlag 0007) empfiehlt eine eigene Grammatik „sigil 1“ mit einem
handgeschriebenen Rust-Parser von rund 2 241 Zeilen im Prototyp. Er nennt als Folge ausdrücklich: Bei
Ablehnung von P-2 braucht auch die C#-Seite einen Parser für diese Grammatik.

Die Plan-Annahme weicht also vom Wortlaut von E07, der Entscheidung von ADR-0007, PRD-0016 FR-01 und dem
Katalogeintrag zu FR-04 ab. Plan 0002 (P-2) nennt das eine Präzisierung von E07 und ADR-0007; wörtlich geht es
darüber hinaus. Weil das Register nach PRD-0000 §6 bindend ist, braucht die Abweichung ein ADR, und das ist dieser
Vorschlag. Plan-Risiko R20 beziffert
eine Ablehnung auf geschätzt +8–10 Tage, wenn sie in P1 erzwungen wird. Die Entscheidung muss vor dem Start
von WP4 fallen, also in Sammelsitzung B am Ende von WP1.

## Anforderungen

- **Eine Wahrheit für Sigil.** Diagnosen, akzeptierte Programme und die erzeugten Units dürfen nicht davon
  abhängen, welches Werkzeug kompiliert (PRD-0004 FR-08, PRD-0016 FR-02).
- **Determinismus.** Dieselbe Quelle ergibt auf Windows, Linux und macOS eine byte-identische Unit. Die Units
  gehen in Content-Hash, Golden Master und Replays ein (ADR-0005, PRD-0018 FR-04). Determinismusfehler sollen
  möglichst lokal auffallen und nicht erst im 3-OS-Vergleich, der einen vollen CI-Durchlauf auf drei
  Plattformen braucht.
- **ADR-0007 bleibt gewahrt.** Parser und Compiler liegen nicht im Laufzeitpfad; die Engine lädt nur Units und
  Packs.
- **Vorschau zeigt, was die Engine tut.** Eine Vorschau, die anders rechnet als die Laufzeit, ist ein
  Diagnosefehler mit Ansage.
- **Editor-Latenz.** Parameter-Regler und Vorschau müssen interaktiv bleiben. PRD-0016 und PRD-0004 nennen < 1 s nur
  für den Roundtrip in die laufende Engine; für die Tool-Vorschau gibt es keinen Zahlenwert. ADR-0008 erwähnt eine
  „60-FPS-Pattern-Preview“ mit Scrubbing als Anspruch an das Canvas; das betrifft das Abspielen, nicht das
  Neuberechnen.
- **Engine ohne C#-Suite.** Engine-Repo, Engine-CI und der DoD-Nachweis über `grimoire-link` funktionieren ohne
  C#-Suite (Plan 0002 WP8.5 „unabhängig von OF-16.1“, R1, E20-Schnitt „C#-Seite nach P2“). Das gilt auch, falls
  P-1 „C#-Seite nach P2“ lautet. PRD-0002 FR-01 verlangt wörtlich nur, dass die Engine ohne Spiel-Abhängigkeit
  baut und testet; es wird erst berührt, wenn die Suite im Spiel-Repo liegt (P-1 = C).
- **Agenten-Tauglichkeit.** Jede Editor-Funktion hat ein CLI-Äquivalent (PRD-0016 NFR).
- **Aufwand und Scope.** Solo-Hobbyprojekt mit dem PO als einzigem Reviewer (R19). Doppelte
  Implementierungen kosten dauerhaft, nicht nur einmal; bei Engpässen wird verschoben, nicht gestrichen (E20).

## Optionen

1. **Rust als einzige Implementierung** — `grimoire_sigilc` (Bibliothek und CLI `sigilc`) enthält Parser,
   Validator, Compiler und `simulate` über den Laufzeit-Interpreter. Die Engine lädt nur Units. `grimoire-ac`
   entdeckt Content, ruft `sigilc build --json` auf, reicht Diagnosen durch und baut Pack und Manifest. Der
   Editor zeichnet die Vorschau selbst in Avalonia, die Positionen rechnet `sigilc simulate`.
   - (+) Genau ein Unit-Erzeuger, und zwar in der Determinismus-Menge. Plattformabhängige Operationen wie
     std-Trigonometrie oder `HashMap`-Reihenfolgen fallen im lokalen Clippy-Lauf auf. WP4.4 bleibt die
     Rückversicherung, nicht der einzige Schutz.
   - (+) Die Vorschau nutzt denselben Interpreter wie die Engine. Abweichungen gibt es bei Eingaben, die die
     Vorschau festlegt (Zielposition für `Aimed`), nicht bei der Logik von Bausteinen, Modifikatoren und
     Transformationen. Zu Behaviors siehe unten.
   - (+) Engine, Harness (WP7.4) und `grimoire-link` (WP8.5) kompilieren ohne .NET. Das passt zu jeder Antwort
     auf P-1, auch zu „C#-Seite nach P2“.
   - (+) Der Rust-Parser aus dem Syntax-Spike wird weiterverwendet. `set`, `fmt` und später `migrate` arbeiten
     auf einem verlustfreien Baum (Engine-ADR-Vorschlag 0007).
   - (−) Die Vorschau überquert eine Prozessgrenze. Jeder Aufruf kostet Prozessstart, Einlesen, Kompilieren,
     Simulieren und JSON-Serialisierung; C# parst das JSON danach. Nichts davon ist gemessen. Der
     JSON-Umfang wächst mit Ticks × Bullets. Eine grobe Rechnung des Autors: 600 Ticks × 1 000 Bullets ×
     etwa 40 Byte je Bullet ergeben rund 24 MB je Aufruf. Ohne Gegenmaßnahmen reicht das nicht für Regler,
     die bei jeder Bewegung neu rechnen (siehe Entscheidung, Baustein 5).
   - (−) Die JSON-Ausgaben von `sigilc` (Diagnosen, `parse`, `simulate`) werden eine dritte versionierte
     Schnittstelle neben Unit- und Pack-Format. Ein Formatwechsel betrifft Rust und C# zugleich.
   - (−) Behaviors (PRD-0004 FR-10) registriert das Spiel als Rust-Funktionen (Vertragsentwurf §11.5; der Bereich
     für Engine-Behaviors ist in P1 leer). Ein aus dem Engine-Tag gebautes `sigilc` kennt sie nicht; ein Pattern
     mit Behavior-Referenz scheitert beim Laden an `UnknownBehavior` (§11.2). Nötig wäre ein spieleigenes
     Simulate-Programm gegen die Bibliothek `grimoire_sigilc` (wie der Harness in WP7.4) oder eine Vorschau ohne
     Behaviors. Der Plan regelt das bisher nicht.
   - (−) Die C#-Werkzeuge brauchen ein `sigilc`-Binary im selben Versionsstand wie die Engine. Liegt die Suite
     nicht in `grimoire/tools/` (P-1 ≠ A), kommt eine Versionskopplung über den Engine-Tag hinzu. Lokal
     gebaute Windows-Binaries werden nach OP-7 signiert, also auch jedes neu gebaute `sigilc`, das der Editor
     aufruft.
   - (−) Weicht vom Wortlaut von E07 („C#-Tooling“), der Entscheidung von ADR-0007 („Der C#-Asset-Compiler
     validiert und kompiliert alle Quellen“), PRD-0016 FR-01 („Sigil-Statik“ im C#-Compiler) und dem
     Katalogeintrag zu FR-04 („eigene einfache Canvas-Sim“) ab. Die Vorschau bleibt zwar tool-intern
     gezeichnet, gerechnet wird aber außerhalb des Tools.
   - (−) Aufwand: im Plan bereits eingepreist (WP4 12 Tage, WP9 8 Tage, WP10 9 Tage). Neu ist nur die
     Pflege des JSON-Vertrags, geschätzt etwa ein Tag, verteilt auf WP4.3 und WP5.6 (Schätzung des Autors).

2. **Zwei Implementierungen, gleich gehalten über einen gemeinsamen Konformitätskorpus** — Rust behält
   Compiler und Unit-Erzeugung (WP4). C# bekommt einen eigenen Parser und Validator für Editor und
   Asset-Compiler sowie eine eigene Canvas-Sim für die Vorschau. Der Korpus aus WP4.1 (gültige und ungültige
   Dateien mit erwarteten Diagnosen) läuft gegen beide.
   - (+) Die Vorschau läuft im Prozess, ohne Prozessstart und ohne JSON-Transport. Das ist die niedrigste
     Latenz aller Optionen.
   - (+) Texteditor, Diagnosen, Parameter-Panel und Vorschau arbeiten ohne `sigilc`-Binary. Pack-Bau und „Push
     to Engine“ brauchen es weiterhin, weil Rust die Units erzeugt. Das liegt näher am Wortlaut von PRD-0016
     FR-01 („Sigil-Statik“ im C#-Compiler) und am Katalogeintrag zu FR-04. E07 und die Entscheidung von ADR-0007
     sind für die Kompilierung wörtlich weiterhin nicht erfüllt.
   - (+) Units bleiben aus einer Hand (Rust); die Determinismus-Aussage für Content-Hash und Golden Master
     ändert sich nicht.
   - (−) Zwei Parser für eine eigene Grammatik ohne fremde Implementierung. Jede DSL-Erweiterung, die ADR-0006
     per Folge-ADR vorsieht, fällt doppelt an, ebenso jede Diagnoseänderung.
   - (−) Ein Korpus prüft Stichproben, keine Gleichheit. Was der C#-Validator zulässt und `sigilc` ablehnt,
     fällt erst im Asset-Gate auf (WP9.3), im Editor also gar nicht.
   - (−) Eine C#-Canvas-Sim ist ein zweiter Interpreter. Damit sie wie die Engine rechnet, müsste C# `dmath`
     und alle Bausteine, Modifikatoren und Transformationen nachbauen. Clippy-Lints greifen dort nicht.
     Ob .NET-`Math`-Funktionen auf allen drei Plattformen gleiche Ergebnisse liefern, ist hier nicht
     nachgeprüft. Rust-Behaviors des Spiels (§11.5) kann eine C#-Sim nicht ausführen. Weicht die Vorschau ab,
     zeigt der Editor ein anderes Pattern als die Engine.
   - (−) Aufwand: laut R20 geschätzt +8–10 Tage, wenn in P1 erzwungen, plus dauerhafte Doppelpflege. Der
     Plan-Rückfall verschiebt diesen Strang nach E20 nach P2.
   - (−) R14 (Scope-Creep im Editor) verschärft sich, weil der „C#-Vorschau-Nachbau“ genau der dort genannte
     Treiber ist.

3. **C# als Compiler, Rust lädt nur Units** — `grimoire-ac` parst, validiert und kompiliert Sigil in C# und
   erzeugt die Units selbst. Die Engine kennt nur Decoder und Interpreter. `grimoire_sigilc` entfällt oder
   schrumpft auf Hilfsfunktionen ohne Compiler.
   - (+) Wörtliche Umsetzung von E07, der Entscheidung von ADR-0007 und PRD-0016 FR-01. Parser und Editor liegen in einer Sprache und einem
     Prozess; die Vorschau kann im Prozess laufen.
   - (+) C#-Produktivität für Parser und Diagnosen, wie ADR-0007 sie für Tooling-Aufwand vorsieht.
   - (−) Der Unit-Erzeuger liegt außerhalb der Determinismus-Menge. Die Clippy-Sperren greifen nicht; eine
     gleichwertige Absicherung in C# (etwa ein Roslyn-Analyzer für gesperrte APIs und ein C#-Nachbau von
     `dmath`) wäre Eigenbau. Plattformabhängige Units fielen erst im 3-OS-Vergleich (WP4.4) auf. Das ist die
     Lage, die Engine-ADR-Vorschlag 0008 in seiner Option 3 als Nachteil beschreibt, nur noch verschärft.
   - (−) Die Engine kommt nicht mehr ohne C#-Suite aus. Engine-Tests und Goldens brauchen Units aus einer
     C#-Toolchain, entweder als eingecheckte Fixtures oder über .NET in der Engine-CI. Eingecheckte Fixtures sieht
     der Vertragsentwurf (§1) für Laufzeit-Tests ohnehin vor; ohne .NET fehlt dann aber der Test, der sie gegen den
     Compiler aktuell hält. `grimoire-link watch` (WP8.5) kann
     ohne C# nicht kompilieren, der DoD-Nachweis „Hot-Reload via Dev-Link“ hängt dann an P-1. Bei P-1 =
     „C#-Seite nach P2“ gäbe es in P1 überhaupt keinen Sigil-Compiler.
   - (−) WP7.4 (Harness kompiliert über `grimoire_sigilc` als Bibliothek) und Engine-ADR-Vorschlag 0008
     (Crate-Karte) müssten umgebaut werden. Die Rust-Parser-Arbeit aus dem Syntax-Spike wäre verloren.
   - (−) Die Vorschau bleibt ungelöst: Entweder rechnet C# mit einem zweiten Interpreter (Nachteile wie
     Option 2), oder die Engine rechnet sie (V-15 Option B, zusätzliche Vorschau-Welt in WP8).
   - (−) Aufwand: nicht belastbar geschätzt. Er liegt nach Einschätzung des Autors über dem von Option 2, weil
     zusätzlich WP4 in C# neu entsteht und WP7.4, WP8.5 sowie der Vertragsentwurf §1, §3 und §11.1 umgebaut
     werden.

4. **WebAssembly-Build des Rust-Compilers, eingebettet in die C#-Werkzeuge** — `grimoire_sigilc` wird
   zusätzlich für ein Wasm-Ziel gebaut (etwa `wasm32-wasip1`, laut rustc-Buch Tier 2) und in C# über eine
   Wasm-Laufzeit geladen, etwa das NuGet-Paket `Wasmtime` (Version 44.0.0 vom 23. Mai 2026, laut NuGet-Seite
   kompatibel mit net8.0, net9.0 und netstandard2.0/2.1). Die Engine und die Rust-Werkzeuge nutzen weiter das
   native `sigilc`.
   - (+) Eine Implementierung wie in Option 1, aber die Aufrufe laufen im Prozess, ohne Prozessstart. Die
     Latenzkosten sinken auf Kompilieren, Simulieren und das Kopieren über den Wasm-Speicher.
   - (+) Die Vorschau nutzt denselben Interpreter-Quelltext wie die Engine.
   - (+) Kompatibel mit Option 1: Bewährt sich die Prozessgrenze nicht, lässt sich Option 4 später
     nachrüsten, ohne die Hoheitsfrage neu zu stellen.
   - (−) Ein zweites Kompilierziel für Code der Determinismus-Menge. Die Wasmtime-Doku „Deterministic Execution“
     nennt als Quellen von Nichtdeterminismus NaN-Bitmuster (`cranelift_nan_canonicalization`), Relaxed SIMD
     (`relaxed_simd_deterministic`), das Wachsen von Speicher und Tabellen, Host-Funktionen wie Uhr und
     Dateisystem sowie epochenbasierte Unterbrechung; jede Quelle braucht eine Einstellung im Host. Gleiche
     Ergebnisse aus nativem und Wasm-Build sind trotzdem ein eigenes Gate (Korpus nativ gegen Wasm), das
     zusätzliche CI-Laufzeit kostet. Baut nur das native `sigilc` Units und dient Wasm allein dem Editor (Diagnosen, `parse`,
     `set`, Vorschau), entfällt der Unit-Vergleich; der Vergleich von Diagnosen und Vorschau bleibt.
   - (−) Eine native Laufzeitbibliothek mit JIT als Abhängigkeit der C#-Suite auf drei Betriebssystemen. Welche
     Plattformen das NuGet-Paket nativ mitbringt und ob es unter .NET 10 (P-13) läuft, ist nicht geprüft.
     Wasmtime erscheint jeden Monat mit einer neuen Hauptversion (Wasmtime-Doku zum Release-Prozess); jede Hebung
     ist ein Pin-Wechsel. Spiel-Behaviors (§11.5) bräuchten wie in Option 1 einen spieleigenen Build.
   - (−) Rust-Code läuft über eine native Bibliothek im Prozess der C#-Werkzeuge. ADR-0001 koppelt beide Seiten
     über Formate und IPC, „bewusst **kein** In-Process-FFI“. Ob eine Wasm-Sandbox darunter fällt, legt der PO
     aus; im Zweifel braucht Option 4 einen Nachtrag zu ADR-0001.
   - (−) Eine eigene Schnittstelle über den Wasm-Speicher (Eingabe, Diagnosen, Simulationsdaten) statt der
     CLI. Das CLI-Äquivalent für Agenten bleibt trotzdem nötig; es gibt dann zwei Aufrufwege für dieselben
     Funktionen. Fehlersuche über die Wasm-Grenze ist mühsamer.
   - (−) Aufwand: geschätzt +3–5 Tage in P1 (etwa 1–2 Tage in WP4 für Wasm-Build und Identitäts-Gate,
     2–3 Tage in WP9 für Host-Anbindung und Paketierung auf drei OS). Die Schätzung des Autors ist nicht durch
     einen Spike belegt.

**Vergleich** (Werte ohne Quelle sind Einschätzungen des Autors, nicht gemessen):

| Kriterium | 1 Rust allein | 2 Zwei Implementierungen | 3 C#-Compiler | 4 Wasm in C# |
|-----------|---------------|--------------------------|---------------|--------------|
| Unit-Erzeuger | `sigilc`, Determinismus-Menge | `sigilc`, Determinismus-Menge | C#, ohne Lints | `sigilc` nativ; als Wasm nur, wenn der Editor damit Units baut |
| 3-OS-Identität der Units | Clippy lokal + WP4.4 | wie 1 | nur WP4.4 + Disziplin | wie 1 + Gate nativ gegen Wasm (Units oder nur Diagnosen und Vorschau) |
| Vorschau rechnet wie die Engine | ja | nein (zweiter Interpreter) | nein, oder Engine-Vorschau-Welt | ja |
| Spiel-Behaviors in der Vorschau | nur mit spieleigenem Simulate-Programm | nein | nein, oder Engine-Vorschau-Welt | nur mit spieleigenem Wasm-Build |
| Verhältnis zu ADR-0001 (Formate und IPC) | passt | passt | passt | Laufzeit im Werkzeugprozess, Auslegung nötig |
| Vorschau-Latenz | Prozessstart + JSON je Aufruf (ungemessen) | im Prozess | im Prozess | im Prozess, Kopie über Wasm-Speicher |
| Engine und `grimoire-link` ohne .NET | ja | ja | nein | ja |
| Mehraufwand P1 gegenüber Plan | ≈ 1 Tag JSON-Vertrag | +8–10 Tage (R20) + Doppelpflege | nicht belastbar geschätzt, > Option 2 | +3–5 Tage |
| Plan-Risiko R20 | entfällt | tritt ein | tritt verschärft ein | entfällt; neues Risiko Wasm-Laufzeit |

**Vorschlag des Autors: Option 1**, mit der Prozessgrenze als ausdrücklich zu messendem Risiko (Baustein 5)
und Option 4 als vorbereitetem Ausweg, falls die Messung scheitert.

Option 1 erfüllt die harten Anforderungen durch Konstruktion. Es gibt genau einen Unit-Erzeuger, Clippy prüft
ihn lokal, die Vorschau nutzt den Interpreter der Engine, und die Engine bleibt ohne .NET vollständig. Der
Preis ist eine Abweichung vom Wortlaut von E07, ADR-0007 und PRD-0016, eine Latenzfrage, die bisher niemand
gemessen hat, und eine noch offene Lösung für Spiel-Behaviors in der Vorschau. Option 2 kauft Latenz mit dauerhafter Doppelpflege und einer Vorschau, die anders rechnen kann als das
Spiel. Option 3 macht Engine und DoD-Nachweis von der C#-Suite abhängig und verlagert den Unit-Erzeuger aus
der Determinismus-Menge. Option 4 ist technisch attraktiv, bringt aber eine zweite Kompilierung von
Determinismus-Code und eine native JIT-Abhängigkeit im Werkzeugprozess mit (Auslegungsfrage zu ADR-0001), für die es in P1 noch keinen gemessenen Bedarf gibt.

## Entscheidung

**Gewählte Option:** 1 — Rust als einzige Implementierung, wie vom Autor vorgeschlagen.

**Nachtrag (2026-09-15, PO-Entscheidung Sammelsitzung B):** Die Bausteine 1–7 des Vorschlags oben gelten wie beschrieben. Zu Baustein 2: Dieses ADR löst ADR-0007 nur teilweise ab, und zwar nur für Sigil (Validierung und Kompilierung); die übrigen Feststellungen von ADR-0007 bleiben unberührt. ADR-0007 erhält dazu einen Verweis in seiner Statuszeile.

Bausteine des Vorschlags (Option 1), damit der PO den Umfang vollständig abnehmen kann:

1. **Hoheit.** `grimoire_sigilc` ist die einzige Implementierung von Lexer, Parser, Validator (einschließlich
   Lesbarkeitsregeln nach PRD-0003) und Compiler für `.sigil` sowie die einzige Quelle von `SigilUnit`-Bytes
   (Vertragsentwurf §1, §11.1). C#-Code enthält keine Sigil-Grammatik, keine Validierungsregeln und keinen
   Interpreter (R14).
2. **Laufzeitpfad.** Die Engine-Laufzeit (`grimoire_sigil`, Fassade) lädt nur Units, per Pack oder
   `SwapSigilUnit`. Keine Laufzeit-Crate hängt an `grimoire_sigilc`, auch nicht als Dev-Kante (Vertragsentwurf
   §1). Der Grundsatz von ADR-0007 bleibt: Parser nicht im Laufzeitpfad, die Engine lädt nur Packs und Units.
   Den Satz „Der C#-Asset-Compiler validiert und kompiliert alle Quellen“ ändert dieses ADR für Sigil:
   Validierung und Kompilierung liegen in `sigilc`, `grimoire-ac` orchestriert. ADR-0007 bekommt bei Annahme
   einen Verweis auf dieses ADR; ob das als teilweise Ablösung gilt, legt der PO fest.
3. **Determinismus.** `grimoire_sigilc` gehört zur Determinismus-Menge mit identischer `clippy.toml`
   (Vertragsentwurf §3). Das 3-OS-Identitäts-Gate der Units (WP4.4) und goldene Unit-Hashes (WP5.7) bleiben
   Pflicht. `grimoire-ac` schreibt Unit-Bytes unverändert ins Pack; die Compiler-Version steht im
   Pack-Manifest (§12).
4. **Orchestrierung.** `grimoire-ac` entdeckt Content, normalisiert Pfade zu `AssetPath` (§12: der
   Asset-Compiler normalisiert, `sigilc` und die Engine lehnen nur ab), ruft `sigilc build --json` auf, reicht
   Diagnosen unverändert durch und schreibt Pack und Manifest. Für den Pack-Schreiber gibt es damit weiterhin
   zwei Implementierungen (C# in `grimoire-ac`, Rust-Referenz `PackWriter` für Tests). Sie werden über
   Golden-Fixtures (WP9.1) und den Schema-Codegen (ADR-0011) gleich gehalten. Die Hoheitsregel dieses ADR
   gilt für Sigil, nicht für das Pack-Format.
5. **Editor-Vorschau über `sigilc simulate`.** Der Editor zeichnet in Avalonia, gerechnet wird durch
   `sigilc simulate` (WP5.6, WP10.4). Weil die Latenz ungemessen ist, gehört zum Vorschlag:
   - eine Messung in WP10.4 an den Referenz-Patterns aus WP4.5, von der Reglerbewegung bis zum neu
     gezeichneten Frame, getrennt nach Prozessstart, Kompilieren, Simulieren und JSON;
   - ein Richtwert als Vorschlag des Autors, nicht aus dem PRD: p95 ≤ 250 ms für eine Neuberechnung;
   - Gegenmaßnahmen in dieser Reihenfolge: Regler-Ereignisse entprellen; nur das sichtbare Tick-Fenster oder
     jeden k-ten Tick ausgeben; kompakte Ausgabe (Zahlen-Arrays statt Objekte je Bullet); ein dauerhafter
     Modus `sigilc serve` mit JSON-Zeilen über stdin/stdout ohne Prozessstart je Aufruf. Das ist dieselbe
     Implementierung, nur ein anderer Aufrufweg, und bräuchte keinen neuen ADR-Entscheid.
   - Reicht auch das nicht, folgt ein Folge-ADR zu Option 4, ohne Option 2 oder 3 zu öffnen.
6. **JSON-Vertrag.** Für die JSON-Ausgaben von `sigilc` gelten die Regeln aus Vertragsentwurf §2 Regel 11
   (`schema_version`, `u64` als Hex-Zeichenkette, feste Schlüsselreihenfolge, kein NaN). Die Formate stehen in
   der Sigil-Formatdoku; deren Ort folgt P-9 (Dossier-Empfehlung A: beim Eigentümer, also im Engine-Repo; noch
   nicht entschieden). C#-Tests laufen gegen eingecheckte Golden-Ausgaben. Ob diese
   Schemata in die Schema-Quelle von ADR-0011 aufgenommen werden, entscheidet ADR-0011.
7. **Abweichung vom Wortlaut.** E07, PRD-0016 FR-01 und FR-04 samt Katalogeintrag sowie die Pipeline-Zeile in
   PRD-0004 werden bei Annahme in WP11.6 nachgezogen, dazu der Verweis in ADR-0007 (Baustein 2). WP11.6 nennt
   bisher nur den Pipeline-Text von PRD-0004 und den Wortlaut von FR-04; E07, FR-01, der Katalogeintrag und
   ADR-0007 kämen hinzu. E07 ändert sich nach PRD-0000 §6 erst mit der Annahme dieses ADR. Vorgeschlagener
   Wortlaut: „Offline-Kompilierung (Rust-Compiler `sigilc`,
   orchestriert vom C#-Tooling) → binäre Packs“; Vorschau „im Tool gezeichnet, gerechnet vom
   Laufzeit-Interpreter über `sigilc simulate`“. Die PRD-Ziele (Validierung vor der Laufzeit, tool-interne
   Vorschau, CLI-Äquivalent, Hot-Swap < 1 s) bleiben unverändert.

## Konsequenzen

Die folgenden Punkte beschreiben die Folgen bei Annahme des Vorschlags (Option 1).

- (+) Eine Sigil-Wahrheit: Editor, Asset-Compiler, Harness, `grimoire-link` und Agenten sehen dieselben
  Diagnosen und erzeugen dieselben Units.
- (+) Determinismusfehler im Compiler fallen im lokalen Clippy-Lauf auf, bevor sie Content-Hashes, Replays
  oder Golden Master erreichen. Das 3-OS-Gate bestätigt nur noch.
- (+) Die Editor-Vorschau zeigt die Pattern-Logik der Engine; ein „im Editor sah es anders aus“ entfällt
  strukturell.
- (+) Engine, Harness und DoD-Nachweis bleiben unabhängig von .NET und von P-1. Die Rückfallschnitte aus E20
  („C#-Seite nach P2“, „Editor nach P2“) bleiben ohne Umbau möglich.
- (+) R20 entfällt. Die +1 Tag Reserve auf WP10 für R20 kann der PO freigeben oder als Reserve für Baustein 5
  umwidmen.
- (+) Die Engine-Vertragsentwürfe (§1, §3, §11.1, §13 mit V-15 A) und Engine-ADR-Vorschlag 0008 brauchen wegen
  dieses ADR keine Änderung. Ihre eigene Freigabe steht weiterhin aus.
- (−) Die Vorschau-Latenz über die Prozessgrenze ist das größte offene Risiko dieses Vorschlags und bis WP10.4
  ungemessen. Im schlechtesten Fall kostet sie `sigilc serve` oder ein Folge-ADR zu Option 4 (geschätzt
  +3–5 Tage, nicht belegt).
- (−) Die JSON-Ausgaben von `sigilc` werden zur versionierten Schnittstelle mit Golden-Tests auf beiden Seiten.
- (−) Die C#-Werkzeuge können ohne passendes `sigilc`-Binary nichts mit Sigil anfangen. Die Spiel-CI baut
  `sigilc` aus dem Engine-Tag (WP9.3, R13 bleibt bestehen). Lokal gebaute Binaries werden nach OP-7 signiert.
- (−) E07, PRD-0016 FR-01/FR-04 und PRD-0004 widersprechen bis zum Nachziehen in WP11.6 dem gelebten Stand.
  Wer nur die PRDs liest, erwartet einen C#-Compiler.
- (−) `sigilc` kompiliert nach §3 sequentiell und ohne `HashMap`. Das bremst große Content-Mengen (Ziel
  Pack-Rebuild < 60 s, PRD-0016 NFR) und bleibt bis zur Messung in WP9.2 offen. Das folgt aus
  Engine-ADR-Vorschlag 0008 und gilt ebenso für Option 2 und 4, weil dort auch `sigilc` die Units baut.
- (−) Spiel-Behaviors (§11.5) kennt das `sigilc` aus dem Engine-Tag nicht. Die Vorschau solcher Patterns braucht
  eine eigene Lösung, spätestens in WP10.4.
- (−) C#-Entwickler müssen für jede Sigil-Änderung Rust anfassen. Das ist gewollt, erhöht aber den
  Kontextwechsel aus ADR-0001.

**Kosten einer Ablehnung** (P-2 = nein; welche Alternative dann gilt, legt der PO fest):

- **Plan.** Bei Option 2 tritt R20 ein: +8–10 Tage für C#-Parser, -Validator und -Vorschau, wenn in P1 erzwungen, sonst
  nach E20 als eigener Strang in P2. Bei Option 4 geschätzt +3–5 Tage (nicht belegt), bei Option 3 nicht
  belastbar geschätzt und höher.
- **WP4.** Bei Option 2 muss der Konformitätskorpus Diagnosen so genau festlegen, dass zwei Implementierungen
  daran gemessen werden können (Codes, Positionen, Knotenpfade). Bei Option 3 entsteht WP4 in C# neu, und der
  Rust-Parser aus dem Spike entfällt.
- **WP9/WP10.** WP9.2 bekommt eigene Sigil-Statik, WP10.3 einen C#-Text-Roundtrip statt `sigilc set`, WP10.4
  eine C#-Sim. Die R14-Mitigation („keine Interpreter- oder Parser-Logik in C#“) und die P-6-Empfehlung
  („kein zweiter Parser in C#“) sind neu zu fassen.
- **Engine-Verträge.** V-15 (Vorschau) ist vor Runde 4 der Vertragsfreigabe neu zu stellen. Bei Option 3
  bekommen V-1 und Engine-ADR-Vorschlag 0008 einen Unit-Erzeuger außerhalb der Determinismus-Menge: den
  einzigen, falls `grimoire_sigilc` entfällt, sonst einen zweiten neben `sigilc` (so formulieren es die
  Fragenrunde und Engine-ADR-Vorschlag 0008). Dann ändert sich auch §11.1 („die C#-Seite erzeugt keine Units“)
  per Vertrags-PR. Bei Option 2 und 4 bleibt §11.1 unberührt.
- **Syntax.** Engine-ADR-Vorschlag 0007 nennt für diesen Fall als Folge, dass Formate mit fremden Parsern
  (KDL, TOML) an Gewicht gewinnen. P-10 wäre dann in derselben Sitzung neu abzuwägen.
- **Determinismus.** Bei Option 3 fällt die lokale Lint-Absicherung des Unit-Erzeugers weg, und das 3-OS-Gate
  wird zum einzigen Schutz. Bei Option 2 kann die Vorschau vom Spiel abweichen, ohne dass ein Gate anschlägt.

## Umsetzung

Nicht umgesetzt; der Vorschlag wartet auf Sammelsitzung B. Bei Annahme ist er schon eingeplant in WP4.1–4.4
(Parser, Compiler, CLI, Identitäts-Gate), WP5.6 (`simulate`), WP7.4, WP8.5, WP9.2/9.3 und WP10.2–10.4. Neu
hinzu kämen Golden-Ausgaben für die C#-Tests (Baustein 6; `schema_version` verlangt schon der Vertragsentwurf
§2 Regel 11), die Latenzmessung mit Gegenmaßnahmen in WP10.4 (Baustein 5), eine Lösung für Spiel-Behaviors in
der Vorschau und das Nachziehen von E07, FR-01, Katalogeintrag und ADR-0007-Verweis in WP11.6 (Baustein 7). Die Nummer 0010 ist
vorläufig und wird beim Merge endgültig vergeben.

**Quellen der Werkzeugangaben** (abgerufen 2026-09-15; nicht in einem Spike geprüft):

- NuGet-Paket `Wasmtime`, Version 44.0.0, Zielframeworks: https://www.nuget.org/packages/Wasmtime
- .NET-Einbettung von Wasmtime: https://github.com/bytecodealliance/wasmtime-dotnet
- Wasmtime „Deterministic Execution“ (NaN-Kanonisierung, Relaxed SIMD): https://docs.wasmtime.dev/examples-deterministic-wasm-execution.html
- WebAssembly-Numerik (nicht deterministische NaN-Bitmuster): https://webassembly.github.io/spec/core/exec/numerics.html
- Wasmtime-Release-Prozess (neue Hauptversion am 20. jedes Monats): https://docs.wasmtime.dev/stability-release.html
- rustc-Buch, Ziel `wasm32-wasip1` (Tier 2): https://doc.rust-lang.org/rustc/platform-support/wasm32-wasip1.html

Nicht geprüft sind die nativen Plattformen des NuGet-Pakets (NuGet-Seite und README nennen sie nicht), dessen
Lauffähigkeit unter .NET 10, die Plattformgleichheit von .NET-`Math`-Funktionen, die Prozessstartkosten von
`sigilc` unter Windows, alle Aufwands- und Latenzzahlen ohne Plan-Quelle und der Umgang von `sigilc simulate`
mit Behavior-Referenzen; die Aussage dazu stützt sich nur auf Vertragsentwurf §11.2 und §11.5.

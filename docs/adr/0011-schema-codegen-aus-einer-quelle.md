# ADR-0011: Schema-Codegen aus einer Quelle für Rust und C# (OF-16.2)

- **Status:** Akzeptiert (2026-09-15; PO-Entscheidung in Sammelsitzung B)
- **Datum:** 2026-09-15
- **Entscheider:** Lupus Malus Deviant (PO) in Sammelsitzung B (P-10), vorbereitet durch Claude (ohne Codex)
- **Bezug:** [Plan 0002](../plans/0002-phase-p1-sichtbarer-kern.md) (WP1.5, WP1.6, WP8.1–WP8.3, WP9.1–WP9.3, WP10.2–WP10.4, P-1, P-9, P-10, P-13, R20), [PRD-0016](../prd/0016-tooling-suite.md) (FR-02, FR-03, FR-04, FR-10, OF-16.1, OF-16.2), [PRD-0000](../prd/0000-index-fiends-n-patrons.md) (E01, E07, E17, E20), [PRD-0004](../prd/0004-sigil-bullet-system.md), [PRD-0017](../prd/0017-plattform-ci-distribution.md), [PRD-0018](../prd/0018-teststrategie.md), [ADR-0001](0001-rust-kern-csharp-tooling.md), [ADR-0006](0006-sigil-daten-dsl-statt-scripting.md), [ADR-0007](0007-offline-asset-kompilierung.md), [ADR-0008](0008-avalonia-fuer-tooling.md), [ADR-0009](0009-engine-pin-ueber-git-tag.md), [ADR-0010](0010-sigil-compiler-hoheit.md) „Sigil-Compiler-Hoheit“ (Vorschlag, Nummer vorläufig; Baustein 6 überlässt die Aufnahme der `sigilc`-JSON-Schemata diesem ADR), [Dossier Sammelsitzung A](../plans/0002-sammelsitzung-a-dossier.md) (P-1, P-9, P-13), [Fragenrunde Vertragsfreigabe WP1.2](../plans/0002-vertragsfreigabe-wp1.2.md) (V-6, V-12, V-15), [Spiel-Verträge (Entwurf)](../architektur/spiel-vertraege-entwurf.md) §4; Engine-Repo `grimoire`, Branch `p1/wp1.2-contracts-draft`: `docs/architektur/crate-vertraege.md` §1, §2 (Regeln 9–11), §3, §11.1, §12, §13, §15 und Engine-ADR-0008 „Crate-Map-Erweiterung P1“ (Vorschlag, Option 4); Branch `p1/wp1.4-sigil-syntax-spike`: Engine-ADR-0007 „Sigil-Quelltextsyntax v1“ (Vorschlag)

## Kontext

ADR-0001 koppelt den Rust-Kern und die C#-Werkzeuge über Datenformate und das Debug-IPC, ausdrücklich ohne FFI.
Als negative Folge nennt es die Synchronisation der Schemata zwischen Rust und C# und empfiehlt dafür Codegen
(OF-16.2). PRD-0016 FR-03 verlangt typisierte Nachrichten („versioniertes Schema, geteilt mit
`grimoire_debug`“). OF-16.2 fragt, ob Codegen aus einer Quelle oder „Hand-Sync mit Versionstest“ gelten soll,
empfiehlt Codegen und terminiert das ADR auf P1. Plan 0002 setzt die Empfehlung in
WP8.1 um: eine Schema-Quelle „(Format laut ADR)“, einen Generator im Engine-Repo mit Rust- und C#-Emitter, eine
ortsneutrale C#-Ausgabe (Zielpfad nach P-1) und den CI-Check „generierter Code aktuell“ (`git diff --exit-code`).
WP9.1 baut darauf `Grimoire.Formats` und `Grimoire.LiveLink` mit Konformanztests gegen die Rust-Golden-Fixtures.

Der Vertragsentwurf (Engine, `p1/wp1.2-contracts-draft`) legt die geteilten Strukturen schon **byte-genau** fest,
bevor ein Werkzeug gewählt ist. §12 und §13 schreiben sogar vor, dass der generierte Code das festgelegte Layout
„exakt reproduzieren“ bzw. „exakt treffen“ muss. Das ADR wählt also ein Werkzeug für vorhandene Formate und
entwirft kein neues Format. Beide Abschnitte sind allerdings noch als *Entwurf WP1.2 — PO-Freigabe ausstehend*
markiert und nach §2b nicht bindend. Eine Formatänderung zugunsten eines Werkzeugs wäre vor dem Merge also noch
ohne Vertrags-PR möglich, müsste aber §2 Regel 10 (feste Breiten, Längenpräfixe mit Obergrenze) und die
Freigabe erneut durchlaufen. Betroffen sind:

| Struktur | Vertrag | Erzeuger → Leser | Besonderheiten, die ein Werkzeug treffen muss |
|----------|---------|------------------|------------------------------------------------|
| Debug-Protokoll v1, Nutzlasten von `Hello`, `Error`, `Log`, `Stats` (mit `StatsScope`, `StatsCounter`), `SwapSigilUnit`, `SwapAck`, `SigilPreview` | §13 | beide Richtungen, Rust ↔ C# | Little-Endian, feste Breiten, `bool` = `u8`, `f32` bitgenau, `Str` = `u32`-Länge + UTF-8 mit Höchstlänge je Feld, `Bytes` = `u32`-Länge, `Vec≤N` = `u32`-Anzahl, `Option` = `u8`-Tag, Enums als `u8`, aber `ErrorCode` als `u16`, feste Arrays `[u8; 32]` und `Option<[f32; 2]>`, keine Rest-Bytes; Höchstlängen prüft `to_frame`, nicht der Typ; eingefroren über alle Versionen (vorläufig): ID und erstes Feld von `Hello`, `MAX_HELLO_FRAME_LEN` sowie ID und Layout von `Error` |
| Frame-Kopf und Handshake | §13 | beide | `len u32`, `id u16`, `flags u16`, `seq u32`; Längenprüfung vor Allokation, `MAX_HELLO_FRAME_LEN`, Reihenfolge der Handshake-Prüfungen (Ablauflogik, kein Datentyp) |
| Pack-Manifest v1 | §12 | Rust-`PackWriter` (Tests) und C#-`grimoire-ac` (WP9.2) → Rust-`PackReader` | `manifest_version u32`, Compiler-Name und -Version als `Str16` (`u16`-Länge, je ≤ 64 Byte), Eintragsanzahl `u32`, Pfade als `Str16` in TOC-Reihenfolge (`AssetPath`, ≤ 255 Byte), Anwendungsblock mit `u32`-Länge (≤ 64 KiB); kein Zeitstempel, **gleiche Eingaben ergeben ein byte-gleiches Pack**; Abgleich Pfad ↔ TOC-ID (`ManifestMismatch`) ist Querprüfung, kein Feldtyp |
| Pack-Header und Inhaltsverzeichnis | §12 | wie oben | 64-Byte-Header, 64-Byte-TOC-Einträge, Ausrichtung auf 16, streng steigende IDs, SHA-256 je Eintrag (Ablauf- und Layoutlogik) |
| JSON von `sigilc` (`check`/`build --json`-Diagnosen, `parse --json`, `simulate --json`) | §2 Regel 11, ADR-0010 Baustein 6, Plan WP9.2, WP10.2–WP10.4 | Rust → C# | `u64` als 16 kleine Hexziffern, Ganzzahlen ≤ 2⁵³ − 1, kein NaN, `schema_version`, feste Schlüsselreihenfolge; `parse --json` ist ein rekursiver Syntaxbaum |
| JSON-Spiegel des Debug-Protokolls und Profiler-Export | §2 Regel 11, §13, §15 | Rust → Werkzeuge, Logs | wie Regel 11; im Vertrag nur als Regel genannt, noch ohne eigenes Schema |
| Harness-Bericht `fnp.harness.report` v1 | Spiel-Verträge §4, V-12 | Rust (Spiel-Repo) → CI, später Balancing-Dashboard | wie Regel 11; strenger Leser mit Größengrenzen; liegt im **Spiel-Repo** |
| Bench-Ergebnis und Golden Master | §15 | Rust → Rust, später Dashboard | im Vertrag als `serde`-Typen der neuen Crate `grimoire_bench` vorgesehen (die Crate existiert noch auf keinem Branch) |

`SigilUnit` (§11.1) ist bewusst nicht dabei: In P1 erzeugt und liest nur Rust Units (ADR-0010-Vorschlag, P-2).
Die C#-Seite reicht sie als undurchsichtige `Bytes` weiter.

Zwei Randbedingungen engen die Wahl zusätzlich ein. **Erstens** verlangt §2 Regel 9 für jeden Decoder fremder Bytes
Fehler statt Panic, Längenprüfung vor Allokation, Property-Tests mit beliebigen und mutierten Eingaben und später
Fuzzing (WP11.4). **Zweitens** hängt der Generator an offenen PO-Fragen: P-1 legt den C#-Zielpfad fest (Empfehlung
`grimoire/tools/`), bei P-1 = D entfällt die C#-Seite in P1 ganz. P-9 legt den Ort der Formatdokumente fest, und
P-13 die .NET-Version (Empfehlung .NET 10 LTS). Engine-ADR-0008 hat eine gemeinsame Format-Crate (dort Option 4)
ausdrücklich bis zu diesem ADR zurückgestellt.

## Anforderungen

- **Exaktes Layout:** Das Werkzeug reproduziert die Byte-Layouts aus §12 und §13 so, wie sie stehen. Das umfasst
  Längenpräfixe unterschiedlicher Breite (`u16`, `u32`), Höchstlängen je Feld, Enum-Breiten je Typ, bitgenaue
  `f32`, feste Arrays und das Verbot von Rest-Bytes. Wer das Format dem Werkzeug anpasst, ändert den Vertrag:
  vor dem Merge den Entwurf samt erneuter Freigabe, danach per Vertrags-PR der Stufe I (§2b).
- **Kanonische Bytes:** Rust- und C#-Schreiber erzeugen für dieselben Werte dieselben Bytes (Pack byte-gleich,
  Golden-Fixtures byteweise, §2 Regel 10).
- **JSON nach §2 Regel 11:** `u64` als 16-stelliger Hex-String, Zahlen-Obergrenze, kein NaN, feste
  Schlüsselreihenfolge, `schema`/`schema_version`.
- **Fuzz-Sicherheit:** Generierte oder handgeschriebene Decoder erfüllen §2 Regel 9 auf beiden Seiten.
- **Eine Quelle:** Eine Layoutänderung an einer Stelle erreicht Rust, C# und idealerweise die Formatdoku
  (PRD-0016 FR-10), oder die CI wird rot.
- **CI-Check:** „Generierter Code aktuell“ als einfacher, auf allen Plattformen gleicher Vergleich (WP8.1). Der
  C#-Build (WP9.1) nutzt dieselben Dateien.
- **Toolchain:** Windows, Linux und macOS lokal und in CI, möglichst ohne neue Laufzeitumgebung neben `cargo` und
  `dotnet` (PRD-0017; jede weitere Laufzeitumgebung verlängert die CI auf drei Plattformen).
- **Determinismus-Menge unberührt:** Keine neue Abhängigkeit in Crates mit `clippy.toml` (§3). `grimoire_debug` und
  `grimoire_assets` liegen außerhalb der Menge (§1).
- **Aufwand passend zu P1:** WP8 ist mit 13 Tagen geschätzt, darin WP8.1 ohne eigene Zahl. Zu synchronisieren sind
  in P1 rund ein Dutzend Nutzlast- und Zeilentypen plus Manifest, nicht Hunderte.

## Optionen

Die Fähigkeiten der Fremdwerkzeuge sind am 2026-09-15 anhand der unter „Quellen“ genannten Seiten geprüft.
Aufwandszahlen sind Schätzungen des Autors, nicht gemessen.

### Option 1: Rust-Typen als Quelle, C# generiert

- **1a — `typeshare` (1Password):** erzeugt aus annotierten Rust-Typen Swift, Go, Python, Kotlin, Scala und
  TypeScript. **C# unterstützt es nicht**, eine Anfrage dazu ist offen (Issue #163). Es erzeugt außerdem nur
  Typdefinitionen für serde-JSON, keinen Binär-Codec. *Ausgeschlossen.*
- **1b — `serde-reflection` + `serde-generate` (0.34.1):** verfolgt Rust-Typen über serde und erzeugt Typen samt
  Laufzeit für **Bincode** (nur Standardkonfiguration) und **BCS**. C# gilt als voll unterstützt (NetCoreApp ≥ 6.0),
  JSON gehört nicht zum Umfang. Beide Kodierungen sind nicht das Layout aus §13. Bincode 1.x schreibt Ganzzahlen
  fest und Little-Endian (Primärquelle), Längenpräfixe als `u64` und Enum-Varianten als `u32` (nur über
  Sekundärquellen bestätigt). BCS kodiert Längen und Enum-Varianten als ULEB128, also mit variabler Breite.
  `Str16`, Höchstlängen je Feld und `u8`-Enums lassen sich nicht ausdrücken. Wer 1b wählt, ersetzt die
  Nutzlastkodierung aus §13 und das Manifest aus §12 durch Bincode oder BCS, also per Vertragsänderung.
  - (+) Ausgereifte Laufzeiten in beiden Sprachen, kein eigener Emitter; Bincode in Standardkonfiguration ist fest,
    Little-Endian und ohne Varints, BCS ist ausdrücklich kanonisch.
  - (−) Höchstlängen je Feld und strenge Rest-Byte-Prüfung müssten zusätzlich von Hand auf beiden Seiten stehen.
  - Toolchain: nur `cargo` (CLI `serdegen`).
- **1c — Eigenbau-Generator über Rust-Typen:** Die Rust-Structs aus §13 („Rust-Form der Nutzlasttypen“) sind die
  Quelle. Wire-Details stehen als Attribute daran (etwa `#[wire(max = 64)]`, `#[wire(len = u16)]`). Ein Werkzeug
  liest die Typen mit `syn` und erzeugt C#. Der Rust-Codec entsteht über ein Derive-Makro oder bleibt
  handgeschrieben.
  - (+) Keine zweite Beschreibungssprache; die Vertragstypen sind die Wahrheit.
  - (+) Variante ohne Quelltext-Parsen: `serde-reflection` als Front-End liefert die Typstruktur, ein eigener
    Emitter schreibt das §13-Layout. Wire-Details, die serde nicht kennt (`Str16`, Höchstlängen), bräuchten dann
    aber eine Nebentabelle, also doch eine zweite Beschreibung.
  - (−) Eigene Attribute wie `#[wire(..)]` akzeptiert rustc nur als Helper-Attribute eines Derive-Makros (geprüft
    mit rustc aus Cargo 1.98.1: „cannot find attribute `wire` in this scope“); ohne
    Proc-Macro-Crate bleiben Umwege wie Doc-Kommentare. Eine Proc-Macro-Crate ist eine neue Engine-Crate mit
    Crate-Map-Änderung (§2 Regel 15) und verlängert Builds.
  - (−) Das Parsen von Rust-Quelltext ist gegen Typ-Aliase, `cfg` und Makros empfindlich.
  - (−) Der Rust-Codec ist entweder Makro-Magie (schwer zu reviewen, Fehlermeldungen im Makro) oder doch
    handgeschrieben und damit keine einzige Quelle.
  - (−) Die Formatdoku lässt sich schlechter ableiten als aus einer flachen Beschreibung.
  - Aufwand ≈ 4–6 Tage.

### Option 2: Neutrale Schema-Sprache als Quelle, beide Seiten generiert

- **2a — FlatBuffers:** Skalare sind Little-Endian, Structs haben feste Ausrichtung, und Rust wie C# haben Verifier
  für nicht vertrauenswürdige Puffer (C#: `Verifier` mit Tiefen- und Tabellengrenzen). Das Format regelt aber
  **Offsets über vtables** und lässt Feld- und Objektreihenfolge offen. Die Doku sagt, zwei Implementierungen dürfen
  für dieselben Werte verschiedene Binärdaten erzeugen, und Felder einer Tabelle dürfen in beliebiger Reihenfolge
  liegen. Damit sind weder das Layout aus §13 noch das byte-gleiche Pack aus `PackWriter` (Rust) und `grimoire-ac`
  (C#) über die generierten Builder zugesichert. Toolchain: Binary `flatc` je OS, NuGet `Google.FlatBuffers`
  (25.2.10). Übernahme nur mit neuem Draht- und Manifestformat per Vertragsänderung.
- **2b — Cap'n Proto:** 8-Byte-Wortausrichtung, Zeiger-Wörter, Segmente, kanonische Form nur optional. Beliebige
  eigene Layouts (Magic, 64-Byte-Header, `Str16`) kann die Schemasprache nicht beschreiben. Rust: `capnp`
  (aktiv gepflegt). C#: zwei Community-Implementierungen, `capnproto-dotnetcore` braucht zur Codegenerierung die
  installierte Cap'n-Proto-Werkzeugkette, `capnproto-dotnet` hat laut README Lücken (Generics, JSON-Codec).
  Toolchain: `capnp` (C++) je OS. Übernahme nur mit neuem Format.
- **2c — Protocol Buffers:** Feld-Tags und Längen sind Varints; feste Breiten gibt es nur für die Feldtypen
  `fixed32`/`fixed64`/`sfixed*`, `float` und `double`. Längenpräfixe mit `u16`/`u32` und Höchstlängen je Feld
  lassen sich nicht ausdrücken. Die Serialisierung ist ausdrücklich
  **nicht kanonisch**; Hashes über serialisierte Nachrichten nennt die Doku instabil. Die JSON-Abbildung schreibt
  64-Bit-Ganzzahlen als **dezimale** Strings, Regel 11 verlangt 16 Hexziffern. Werkzeuge wären `prost` (Rust),
  `Google.Protobuf` (C#) und `protoc` je OS. Übernahme nur mit neuem Format; das byte-gleiche Pack ginge verloren.
- **2d — JSON Schema mit Generatoren:** Nur für die JSON-Schnittstellen, nicht für §12/§13.
  - `schemars` 1.2.2 erzeugt aus serde-Typen JSON Schema 2020-12 und beachtet serde-Attribute.
  - `typify` erzeugt aus JSON Schema serde-Typen in Rust.
  - `NJsonSchema.CodeGeneration.CSharp` (11.6.1) erzeugt C#-DTOs; `quicktype` erzeugt C# und Rust, braucht aber
    Node/npm.
  - Ein `u64`-Hex-Feld wird als `string` mit `pattern` beschrieben und kommt in C# als `string` an, nicht als
    `ulong`. Ein eigener Typname oder Konverter ist nötig (Unterstützung in NJsonSchema nicht nachgeprüft).
  - Feste Schlüsselreihenfolge, die Obergrenze 2⁵³ − 1, Größengrenzen vor dem Parsen und die strengen Leser
    (§15, Spiel-Verträge §4) sind Verhalten, das JSON Schema nicht erzeugt.
  - Aufwand ≈ 1–2 Tage für den JSON-Teil; der Binärteil bleibt offen.
- **2e — Eigene, kleine Schema-Beschreibung mit Rust- und C#-Emitter (Eigenbau):** Eine Datei je Format beschreibt
  Nachrichten, IDs, Richtungen und Felder, und zwar mit genau dem Typvokabular aus §13 („Kodierung der Nutzlast“,
  Katalog) und §12 (Manifest): `u8`…`u64`, `f32`, `bool`, `Str≤N`, `Str16≤N`, `Bytes≤N`, `Vec≤N<Zeile>`,
  `Option<T>`, feste Arrays `[T; N]` (`[u8; 32]`, `[f32; 2]`), Enums mit Breite, dazu die semantischen Typen
  `hash64`/`id64` für Regel 11.
  - Ein Rust-Werkzeug erzeugt daraus Rust-Structs mit Codec, C#-Klassen mit Codec (`BinaryReader`-frei über
    `Span<byte>` und explizites Little-Endian) und die Feldtabellen für `docs/formats/`. Später kommen serde- bzw.
    `System.Text.Json`-Typen für JSON hinzu.
  - Frame-Kopf, Handshake-Ablauf, Pack-Header und Inhaltsverzeichnis bleiben handgeschrieben (Ablauflogik).
  - (+) Trifft das Vertragslayout exakt, weil das Vokabular aus dem Vertrag stammt.
  - (+) Kanonische Bytes sind eine Eigenschaft des Emitters, nicht einer Fremdbibliothek.
  - (+) Toolchain nur `cargo`.
  - (−) Eigenes Werkzeug mit Pflegepflicht; ein Emitterfehler trifft alle Nachrichten gleichzeitig.
  - (−) Neue Werkzeug-Crate (§2 Regel 15) und eventuell eine neue Drittabhängigkeit zum Einlesen der
    Beschreibung, etwa `toml` (§2 Regel 4).
  - (−) Eine weitere Beschreibungssprache, die nur dieses Projekt kennt; neue Mitwirkende und Agenten lernen sie
    zusätzlich zu Rust und C#.
  - Aufwand ≈ 4–5 Tage für Binärnutzlasten und Manifest mit beiden Emittern und Doku-Tabellen, JSON-Emitter
    ≈ +2 Tage. Den rekursiven Syntaxbaum von `sigilc parse --json` deckt das nicht ab, siehe „Vorschlag“.

### Option 3: Beidseitig handgeschrieben, abgesichert durch Golden-Fixtures und Konformanztests

Rust-Codec in `grimoire_debug`/`grimoire_assets` wie im Vertrag, C#-Codec in `Grimoire.Formats` von Hand. Die
Übereinstimmung sichern die ohnehin geplanten byteweisen Golden-Fixtures (`tests/fixtures/debug_v1/`,
`pack_v1_minimal.grimpack`, WP8.2/WP8.3), die C# in WP9.1 rundreist, plus Tests „jede Katalognachricht hat eine
Fixture“ auf beiden Seiten.

- (+) Keine neue Werkzeugkette und kein Generator.
- (+) Jede Seite ist idiomatisch und direkt reviewbar.
- (+) Die Fixtures sind schon eingeplant.
- (+) Die Handshake-Versionsprüfung fängt Fehlpaarungen zwischen Versionen zur Laufzeit.
- (+) Entspricht der Alternative, die OF-16.2 selbst nennt („Hand-Sync mit Versionstest“).
- (+) Keine werkzeugbedingten Gleichtaktfehler: Rust- und C#-Codec entstehen getrennt und prüfen sich über die
  Fixtures gegenseitig.
- (−) Keine einzige Quelle: Jede Feldänderung (etwa `Stats` wächst mit WP6.3) wird zweimal geschrieben, und die
  Doku ein drittes Mal.
- (−) Abweichungen fallen nur dort auf, wo eine Fixture das Feld mit einem unterscheidbaren Wert belegt.
- (−) Weicht von der Empfehlung in ADR-0001 und PRD-0016 OF-16.2 ab, ebenso vom Wortlaut von WP8.1–WP8.3/WP9.1
  („aus WP8.1 generiert“) und von §12/§13 („nach Projekt-ADR-0011 … erzeugt“); PRD, Plan und Vertragswortlaut
  müssten nachgezogen werden (das Layout selbst bleibt).
- Aufwand ≈ 2 Tage für den C#-Codec mit Konformanztests, danach doppelte Pflege je Formatänderung.

### Option 4: Handgeschriebenes Binärformat, beschrieben in `docs/formats/`, nur C# generiert

Rust bleibt die handgeschriebene Referenz. Eine maschinenlesbare Formatbeschreibung neben der Doku erzeugt nur die
C#-Seite.

- **4a — Kaitai Struct (`.ksy`):** Beschreibt beliebige Binärlayouts einschließlich Magic, Endianness und
  Längenpräfixen und erzeugt laut Compiler-README Parser für zwölf Sprachen (seit v0.11 auch Rust), darunter C#
  (Runtime `KaitaiStruct.Runtime.CSharp` 0.11.0).
  - (−) **Serialisierung gibt es in v0.11 nur für Java und Python.** C# kann damit nicht schreiben, obwohl der
    C#-Client `Hello`, `SwapSigilUnit` und `SigilPreview` sendet und `grimoire-ac` Packs mit Manifest schreibt. Der
    Schreibpfad bliebe handgeschrieben.
  - (−) Der Kaitai-Compiler ist in Scala geschrieben. Die Kommandozeile läuft nach Kenntnis des Autors auf der JVM,
    braucht also eine Java-Laufzeit je OS (nicht nachgeprüft). Die npm-Ausgabe `kaitai-struct-compiler` bietet laut
    Paketbeschreibung nur eine Programmier-API, keinen fertigen CLI-Ersatz.
- **4b — eigene Tabellen in `docs/formats/*.md` als Quelle:** Ein Werkzeug liest die Feldtabellen des
  Formatdokuments und erzeugt C#.
  - (+) Doku und C# stimmen per Konstruktion überein.
  - (−) Markdown-Tabellen sind als Quelle fragil, und Rust bleibt eine zweite, handgepflegte Wahrheit, abgesichert
    nur über Fixtures wie in Option 3.
  - (−) Bei P-9 = A liegt die Doku im Engine-Repo; bei anderem Ausgang hängt der Generator an einer Repo-Grenze.
- Aufwand 4a ≈ 2 Tage `.ksy` plus ≈ 1–2 Tage handgeschriebener C#-Schreiber; 4b ≈ 3 Tage.

### Vergleich

| Kriterium | 1a typeshare | 1b serde-generate | 1c Eigenbau über Rust | 2a FlatBuffers | 2b Cap'n Proto | 2c Protobuf | 2d JSON Schema | 2e Eigenbau-Schema | 3 Hand + Fixtures | 4a Kaitai |
|-----------|--------------|-------------------|-----------------------|----------------|----------------|-------------|----------------|--------------------|-------------------|-----------|
| §13-Layout exakt | nein | nein (Bincode/BCS) | ja | nein | nein | nein | — | ja | ja | lesen ja, schreiben nein |
| §12-Manifest exakt, byte-gleich Rust/C# | nein | nein | ja | nein | nein (kanonisch nur optional) | nein | — | ja | ja (über Fixture) | lesen ja |
| Regel 11 (`u64` als Hex, Ordnung, Grenzen) | — (kein C#) | nein (kein JSON) | ja (mit JSON-Emitter) | — | — | nein (dezimal) | teilweise | ja (mit JSON-Emitter) | ja | — |
| C#-Unterstützung | nein | ja | ja | ja | Community | ja | ja | ja | ja | nur lesen |
| Neue Toolchain neben cargo/dotnet | — | nein | nein (+ Proc-Macro-Crate) | `flatc` | `capnp` | `protoc` | Node bei quicktype | nein | nein | JVM (nicht nachgeprüft) |
| Vertragsänderung nötig | — | ja (Format) | nein | ja (Format) | ja (Format) | ja (Format) | nein | nein | nur Wortlaut §12/§13 | nur Wortlaut §12/§13 |
| Eine Quelle für Rust, C#, Doku | — | Rust + C# | Rust + C# | Rust + C#; Doku = Schemadatei | Rust + C#; Doku = Schemadatei | Rust + C#; Doku = Schemadatei | JSON-Teil | ja (Feldtabellen erzeugt) | nein | C#-Leser + Doku |
| Aufwand P1 (Schätzung, ungeprüft) | — | nicht geschätzt (Vertragsänderung zuerst) | ≈ 4–6 Tage | nicht geschätzt | nicht geschätzt | nicht geschätzt | ≈ 1–2 Tage, nur JSON | ≈ 4–5 Tage, JSON + 2 | ≈ 2 Tage, danach Doppelpflege | ≈ 3–4 Tage |

## Vorschlag des Autors

**Option 2e** — eigene, kleine Schema-Beschreibung mit Rust- und C#-Emitter — in folgendem Zuschnitt:

1. **Umfang P1 (WP8.1):**
   - Die Nutzlasttypen des Debug-Protokolls v1 (§13, einschließlich `StatsScope` und `StatsCounter`, Katalog-IDs,
     Richtungen, `PROTOCOL_VERSION`) und das Pack-Manifest v1 (§12) werden generiert.
   - Frame-Kopf, `FrameDecoder`, Handshake-Ablauf, Pack-Header, Inhaltsverzeichnis und SHA-256-Logik bleiben
     handgeschrieben, und zwar auf beiden Seiten. Sie sind Ablauflogik mit wenigen Feldern; sie zu generieren hieße,
     einen Formatcompiler zu bauen.
   - Die Golden-Fixtures aus WP8.2/WP8.3 bleiben Pflicht, als von der Quelle unabhängige Prüfung (Element von
     Option 3).
2. **Emitter:**
   - Rust: Structs mit `encode`/`decode` nach §2 Regel 9, also Längenprüfung vor Allokation, `TrailingBytes`,
     `InvalidUtf8`, `InvalidEnum`, `FieldTooLong`, kein Panic.
   - C#: Klassen mit denselben Prüfungen und denselben Fehlerarten.
   - Doku: Feldtabellen als eingebundene Abschnitte in `docs/formats/debug-protocol.md` und `pack.md`
     (Ort nach P-9).
   - Generierte Dateien werden eingecheckt; es gibt kein `build.rs` und kein Proc-Macro, der Laufzeitpfad hängt also
     nicht am Generator.
3. **JSON (Regel 11):**
   - Die `sigilc`-Diagnosen und die Ausgabe von `simulate --json` kommen in denselben Generator (JSON-Emitter mit
     `hash64` → Hex-String und `ulong` in C#), aber erst, wenn ein C#-Konsument sie typisiert liest. Das ist
     spätestens WP9.2: `grimoire-ac` reicht die Diagnosen laut Plan zwar unverändert durch, muss sie für Exit-Codes
     aber mindestens erkennen; ausgewertet werden sie in WP10.2, `simulate --json` in WP10.4.
   - `sigilc parse --json` (rekursiver Syntaxbaum) bleibt zunächst handgeschrieben mit Fixture, bis der Generator
     Summentypen kann. Timebox: Braucht der JSON-Emitter mehr als 2 Tage, bleibt JSON bei Option 3.
   - Bench-Ergebnis und Golden Master (§15) bleiben handgeschriebene serde-Typen, weil es in P1 keinen
     C#-Konsumenten gibt.
   - Der Harness-Bericht (Spiel-Repo) bleibt ebenfalls handgeschrieben mit Fixture: Er hat in P1 keinen
     C#-Konsumenten, und ein Engine-Generator im Spiel-Repo bräuchte einen eigenen Aufrufweg über den gepinnten Tag
     (ADR-0009).
4. **Ort:**
   - Generator als Werkzeug-Crate im Engine-Workspace, etwa `grimoire_schemagen`, ohne Kanten zu Engine-Crates und
     ohne `clippy.toml`. Die Crate-Map (Engine-ADR-0008, §1-Tabelle) muss sie per Nachtrag aufnehmen.
   - Schema-Dateien unter `grimoire/schema/`; das Beschreibungsformat (etwa TOML) legt WP8.1 fest.
   - C#-Ausgabe nach P-1; bei P-1 = D läuft in P1 nur der Rust- und der Doku-Emitter, der C#-Emitter folgt in P2.
   - Eine gemeinsame Format-Crate (Engine-ADR-0008, Option 4) ist **nicht** nötig: Der Generator schreibt in die
     besitzenden Crates `grimoire_debug` und `grimoire_assets`.
5. **Rückfall:** Überschreitet WP8.1 die Timebox von 5 Tagen für Binärnutzlasten und Manifest, fällt der Strang auf
   Option 3 zurück. Die Fixtures sind dann die einzige Absicherung; PRD-0016 OF-16.2 und WP9.1 werden entsprechend
   nachgezogen.

**Begründung:**
- Alle Fremdwerkzeuge mit Binärkodierung (1b, 2a–2c) bringen **ihr eigenes** Drahtformat mit. Keines trifft das
  vertraglich festgelegte Layout. 2a und 2c garantieren nicht einmal kanonische Bytes, 2b nur optional; das
  byte-gleiche Pack und die Golden-Fixtures setzen sie voraus. BCS (1b) wäre kanonisch, aber mit variabler Breite.
- `typeshare` scheidet mangels C# aus, Kaitai mangels C#-Schreiber.
- Übrig bleiben ein Eigenbau (1c, 2e) oder Handarbeit (3). 2e schlägt 1c, weil es ohne Proc-Macro und ohne das
  Parsen von Rust-Quelltext auskommt und die Formatdoku als dritte Ausgabe liefert (PRD-0016 FR-10, E17).
- 2e schlägt 3 bei der Pflege: Das Protokoll wächst in P1 (WP6.3 erweitert `Stats`) und in P2 (reservierte Bereiche
  für Entity-Inspektion, Replay-Steuerung, Asset-Hot-Swap).
- Der Abstand zu Option 3 ist aber klein, solange nur rund ein Dutzend Typen betroffen sind. Wer den Eigenbau
  scheut, verliert mit Option 3 wenig Sicherheit und spart den Generator.
- Der Vorschlag hängt an P-1: Bei P-1 = D gibt es in P1 keinen C#-Konsumenten. Dann bleiben vom Nutzen nur die
  erzeugten Rust-Codecs und Doku-Tabellen, und Option 3 (nur Rust von Hand, C# in P2) ist in P1 billiger.

## Entscheidung

**Gewählte Option:** 2e — eigene, kleine Schema-Beschreibung mit Rust- und C#-Emitter, wie vom Autor vorgeschlagen.

**Nachtrag (2026-09-15, PO-Entscheidung Sammelsitzung B):** Angenommen im Zuschnitt des Vorschlags oben (Punkte 1–5): In P1 werden die Nutzlasttypen des Debug-Protokolls v1 und das Pack-Manifest v1 generiert; Frame-Kopf, Handshake-Ablauf, Pack-Header, Inhaltsverzeichnis und SHA-256-Logik bleiben auf beiden Seiten handgeschrieben; die Golden-Fixtures aus WP8.2/WP8.3 bleiben Pflicht.

## Konsequenzen

Die folgenden Punkte beschreiben die Folgen bei Annahme des Vorschlags (Option 2e). Die Folgen der anderen Optionen
stehen oben je Option.

**Positiv**

- (+) Eine Quelle für Rust-Codec, C#-Codec und Feldtabellen der Formatdoku. Ändert jemand ein Feld nur an einer
  Stelle, wird der Aktualitäts-Check rot.
- (+) Das Vertragslayout aus §12/§13 bleibt unverändert; kein Vertrags-PR wegen eines Werkzeugs.
- (+) Kanonische Bytes auf beiden Seiten sind eine prüfbare Eigenschaft des Emitters; Rust-`PackWriter` und
  `grimoire-ac` können byte-gleiche Packs gegen dieselbe Fixture beweisen.
- (+) Toolchain nur `cargo` für die Generierung und `dotnet` für den C#-Build, das ohnehin durch WP9.1 kommt. Kein
  `flatc`, `protoc`, `capnp`, keine JVM, kein Node auf drei Runnern. Auf dem Entwicklungsrechner ist keines der drei
  Schema-Werkzeuge installiert (geprüft: `cargo` 1.98.1 und .NET SDK 10.0.400 vorhanden, `protoc`, `flatc`, `capnp`
  nicht gefunden).
- (+) Keine neue Abhängigkeit in der Determinismus-Menge (§3); generierter Code landet nur in `grimoire_debug` und
  `grimoire_assets`.
- (+) Einheitliche Decoder-Prüfungen: Die Regeln aus §2 Regel 9 stehen einmal im Emitter statt je Nachricht von
  Hand.

**Negativ**

- (−) **Ein eigenes Werkzeug mehr** mit Tests, Doku und Pflegepflicht, geschätzt 4–5 Tage in WP8.1 (+2 Tage, falls
  JSON dazukommt). WP8.1 hat im Plan keine eigene Zahl innerhalb der 13 Tage von WP8, und die einzige WP8-Reserve
  (+1 Tag) gehört zu R7 (Hot-Swap und Link-Abriss), nicht zum Generator. Reicht die WP8-Schätzung nicht, geht der
  Mehraufwand zulasten des allgemeinen Puffers.
- (−) **Gleichtaktfehler:** Ein Emitterfehler, etwa eine falsche Prüfreihenfolge oder ein vergessener
  Obergrenzen-Check, steckt in allen Nachrichten beider Sprachen gleichzeitig, und Rust- und C#-Seite bestätigen sich
  dann gegenseitig falsch. Gegenmittel sind die **handgeprüften** Golden-Fixtures, Proptests über den generierten
  Rust-Code (§2 Regel 9) und entsprechende Zufallseingaben-Tests in C#. Die Fixtures dürfen deshalb nie vom Generator
  selbst erzeugt werden.
- (−) **Fuzzing trifft generierten Code:** Befunde aus WP11.4 müssen im Emitter behoben und neu generiert werden,
  nicht in der Ausgabe. Ein Handpatch am generierten Code macht den Aktualitäts-Check rot.
- (−) **Zwei Wahrheiten bleiben** für Frame-Kopf, Handshake-Ablauf, Pack-Header und Inhaltsverzeichnis sowie für
  §15, den Harness-Bericht und `sigilc parse --json`. Dort sichern nur Fixtures und Konformanztests (Option 3 im
  Kleinen).
- (−) **Neue Werkzeug-Crate:** Crate-Map-Nachtrag (Engine-ADR-0008, §1-Tabelle, §2 Regel 15), Kanten-Check und
  eventuell eine neue Drittabhängigkeit für das Beschreibungsformat (§2 Regel 4). Längere Workspace-Builds (OP-5),
  auch wenn der Generator nicht im Laufzeitpfad liegt.
- (−) **Aktualitäts-Check ist plattformempfindlich:** `git diff --exit-code` scheitert auf Windows-Runnern an
  CRLF-Umwandlung, wenn die generierten Dateien nicht per `.gitattributes` auf `eol=lf` stehen. Außerdem darf der
  Emitter nichts Maschinen- oder Zeitabhängiges schreiben (Zeitstempel, absolute Pfade, Werkzeugversionen aus der
  Umgebung) und keine ungeordneten Container iterieren. Den Rust-Code formatiert er selbst oder über ein gepinntes
  `rustfmt`; ein `dotnet format` im Check würde die .NET-Version zur Voraussetzung der Rust-CI machen.
- (−) **Abhängigkeit von P-1:** Bei P-1 = A prüft ein Engine-CI-Job beide Ausgaben in einem Repo. Bei P-1 = B
  (eigenes Repo `grimoire-tools`) oder C (C#-Suite im Spiel-Repo) liegt die C#-Ausgabe hinter einer Repo-Grenze.
  Dann braucht das andere Repo den Generator oder seine Ausgabe aus dem gepinnten Engine-Tag, und jede
  Protokolländerung erreicht C# erst nach einem Tag. Bei P-1 = D entsteht der C#-Emitter erst in P2; ob die
  Beschreibung für C# taugt, zeigt sich dann erst.
- (−) **Versionsdisziplin bleibt Handarbeit:** Der Generator verhindert kein Layout-Update ohne Erhöhung von
  `PROTOCOL_VERSION` bzw. `manifest_version`. Ein zusätzlicher Check ist nötig (siehe Folge-Entscheidungen), sonst
  verbinden sich zwei inkompatible Stände mit gleicher Versionsnummer.
- (−) **Vertragstext muss nachziehen:** §13 verlangt byteweise Golden-Fixtures je Nachricht, aber nicht, dass sie
  von Hand geprüft sind; die Gegenmittel gegen Gleichtaktfehler setzen das voraus. §1 sagt, `tools/` hänge nur über
  Formatdokumente, Golden-Fixtures und `sigilc`-JSON an der Engine; generierter C#-Code aus dem Engine-Repo ist
  eine weitere Kopplung. Beides braucht eine Ergänzung im Vertrag.

**Folge-Entscheidungen**

- **Beschreibungsformat und Crate-Name** in WP8.1, dazu der Nachtrag in Engine-ADR-0008 bzw. der §1-Tabelle
  (Vertrags-PR, §2b).
- **Versions-Fingerabdruck:** Eingecheckte Liste „Protokoll-/Manifestversion → Hash der Schema-Beschreibung“. Die CI
  wird rot, wenn sich der Hash ohne neue Versionsnummer ändert. Umsetzung WP8.1, optional.
- **JSON-Emitter:** Aufnahme von `sigilc check/build --json` und `simulate --json` vor dem ersten C#-Konsumenten
  (spätestens WP9.2, siehe „Vorschlag“ Punkt 3), abhängig von
  ADR-0010 (P-2). Bei Ablehnung von P-2 (R20) entstünde eine C#-Sigil-Seite, und der Umfang der geteilten Typen wäre
  neu zu bewerten.
- **Harness-Bericht und §15** in eine gemeinsame Quelle, sobald ein C#-Konsument (Balancing-Dashboard) terminiert
  ist. Dann ist auch zu klären, wie das Spiel-Repo den Engine-Generator aufruft (V-12, Engine-ADR-0008,
  „Ort der JSON-Schema-Typen“).
- **Format-Crate** (Engine-ADR-0008, Option 4): mit diesem Vorschlag nicht erforderlich; neu bewerten, falls
  Nachrichtentypen später von mehreren Crates geteilt werden.
- **C#-Zufallseingaben-Tests:** Wahl der Bibliothek in WP9.1 (nicht Teil dieses ADR).
- **Nachziehen:** PRD-0016 OF-16.2 als entschieden, mit der Umfangsgrenze (§15, Harness-Bericht und
  `sigilc parse --json` in P1 außerhalb der einen Quelle), WP9.1-Wortlaut, `docs/formats/`-Index (P-9) in WP11.6;
  im Vertrag §13 „handgeprüfte Fixtures“ und §1 (Kopplung von `tools/` über generierten Code), per Entwurf vor dem
  Merge oder per Vertrags-PR.

## Quellen

Geprüft am 2026-09-15; die Versionsangaben sind der Stand der jeweiligen Seite.

- typeshare, Sprachen und fehlendes C#: [README](https://github.com/1Password/typeshare/blob/main/README.md),
  [Issue #163 „Support for C#“](https://github.com/1Password/typeshare/issues/163)
- serde-generate 0.34.1, Sprachen (C# voll unterstützt, NetCoreApp ≥ 6.0), Bincode (nur Standardkonfiguration) und
  BCS, kein JSON: [docs.rs](https://docs.rs/crate/serde-generate/latest),
  [README](https://github.com/zefchain/serde-reflection/blob/main/serde-generate/README.md)
- Bincode 1.x, Standard `serialize` mit Fixint und Little-Endian:
  [docs.rs bincode 1.3.3 config](https://docs.rs/bincode/1.3.3/bincode/config/index.html); `u64`-Längen und
  `u32`-Enum-Varianten nur sekundär, etwa [bincode-next spec](https://docs.rs/bincode-next/latest/bincode_next/spec/)
- BCS, ULEB128 für Längen und Enum-Varianten: [BCS README](https://github.com/diem/bcs/blob/master/README.md)
- FlatBuffers, Little-Endian, Ausrichtung, nicht kanonische Ausgabe verschiedener Implementierungen:
  [FlatBuffers Internals](https://flatbuffers.dev/internals/); C#-Verifier:
  [FlatBuffers C#](https://flatbuffers.dev/languages/c_sharp/); NuGet
  [Google.FlatBuffers](https://www.nuget.org/packages/Google.FlatBuffers)
- Cap'n Proto, Wortausrichtung, optionale kanonische Form:
  [Encoding](https://capnproto.org/encoding.html); Rust [capnproto-rust](https://github.com/capnproto/capnproto-rust);
  C# [capnproto-dotnetcore](https://github.com/c80k/capnproto-dotnetcore),
  [capnproto-dotnet](https://github.com/ThomasBrixLarsen/capnproto-dotnet)
- Protocol Buffers, Serialisierung „is not (and cannot be) canonical“, Hashes serialisierter Nachrichten instabil:
  [Serialization Is Not Canonical](https://protobuf.dev/programming-guides/serialization-not-canonical/);
  ProtoJSON schreibt `int64`/`fixed64`/`uint64` als dezimalen String, Leser akzeptieren auch JSON-Zahlen:
  [ProtoJSON Format](https://protobuf.dev/programming-guides/json/)
- JSON Schema: [schemars 1.2.2](https://docs.rs/schemars/latest/schemars/) (2020-12, serde-Attribute),
  [typify](https://github.com/oxidecomputer/typify),
  [NJsonSchema CSharpGenerator](https://github.com/RicoSuter/NJsonSchema/wiki/CSharpGenerator),
  [NuGet NJsonSchema.CodeGeneration.CSharp 11.6.1](https://www.nuget.org/packages/NJsonSchema.CodeGeneration.CSharp),
  [quicktype](https://github.com/glideapps/quicktype)
- Kaitai Struct v0.11, Serialisierung nur Java/Python, C#-Parser:
  [Release v0.11](https://kaitai.io/news/2025/09/07/kaitai-struct-v0.11-released.html),
  [Serialization Guide](https://doc.kaitai.io/serialization.html),
  [NuGet KaitaiStruct.Runtime.CSharp](https://www.nuget.org/packages/KaitaiStruct.Runtime.CSharp),
  Zielsprachen: [kaitai_struct_compiler](https://github.com/kaitai-io/kaitai_struct_compiler),
  npm-Ausgabe nur als API: [kaitai-struct-compiler](https://www.npmjs.com/package/kaitai-struct-compiler)
  (Seite lieferte beim Abruf HTTP 403, Aussage aus der Suchmaschinen-Zusammenfassung der Paketbeschreibung)

**Nicht nachgeprüft** (Kenntnisstand des Autors):
- Bincode-1.x-Längenpräfixe als `u64` und Enum-Varianten als `u32` in einer Primärquelle (nur sekundär bestätigt)
- ob `serde-reflection` Felder mit `serialize_with` korrekt verfolgt
- ob NJsonSchema eigene Typabbildungen für Hex-`u64` unterstützt
- dass die Kaitai-Kommandozeile eine Java-Laufzeit braucht
- ob der C#-Emitter ohne `dotnet format` stabil formatierten Code liefern kann (Designannahme)
- alle Aufwandsschätzungen und Timeboxen

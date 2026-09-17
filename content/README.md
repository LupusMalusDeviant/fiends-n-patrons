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
| `sigil/` | Bullet-Patterns in Sigil (`sigil 1`): `imp_volley.sigil` (Angriff des Imps, abgeleitet aus den Referenz-Patterns `03-aimed-fan` und `01-opening-ring` der Engine) und `imp_curtain.sigil` (Vorhang-Modus mit rund 10.000 Bullets, abgeleitet aus `02-spiral-curtain`). Nur Silhouetten und Paletten, die der Bullet-Pass zeichnet (Visual-Katalog der Engine). Übergangsweise übersetzt das Build-Skript von `fnp_content` sie beim Bauen mit dem Compiler der Engine (`grimoire_sigilc`) und bettet die Units ein; der kanonische Content-Pfad ist der Pfad relativ zu `content/` |

# content/

Quell-Content des Spiels, der vom Asset-Compiler (C#-Tooling) in binäre Packs übersetzt wird:
Sigil-Patterns (`.sigil`), Raum- und Wellen-Templates, Tuning-Daten, Texte (DE/EN), Audio-Rezepte.
Formate sind in `docs/formats/` dokumentiert, sobald sie entstehen (ab P1).

| Ordner | Inhalt |
|---|---|
| `sigil/` | Bullet-Patterns in Sigil (`sigil 1`): `imp_volley.sigil` (Angriff des Imps, abgeleitet aus den Referenz-Patterns `03-aimed-fan` und `01-opening-ring` der Engine) und `imp_curtain.sigil` (Vorhang-Modus mit rund 10.000 Bullets, abgeleitet aus `02-spiral-curtain`). Nur Silhouetten und Paletten, die der Bullet-Pass zeichnet (Visual-Katalog der Engine). Übergangsweise übersetzt das Build-Skript von `fnp_content` sie beim Bauen mit dem Compiler der Engine (`grimoire_sigilc`) und bettet die Units ein; der kanonische Content-Pfad ist der Pfad relativ zu `content/` |

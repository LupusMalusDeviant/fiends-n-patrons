# content/

Quell-Content des Spiels, der vom Asset-Compiler (C#-Tooling) in binäre Packs übersetzt wird:
Sigil-Patterns (`.sigil`), Raum- und Wellen-Templates, Tuning-Daten, Texte (DE/EN), Audio-Rezepte.
Formate sind in `docs/formats/` dokumentiert, sobald sie entstehen (ab P1).

| Ordner | Inhalt |
|---|---|
| `sigil/` | Bullet-Patterns in Sigil (`sigil 1`). Übergangsweise übersetzt das Build-Skript von `fnp_content` sie beim Bauen mit dem Compiler der Engine (`grimoire_sigilc`) und bettet die Units ein; der kanonische Content-Pfad ist der Pfad relativ zu `content/` |

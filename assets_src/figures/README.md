# Figuren – Imp, Verdammte Seele, Brute

Die Quellen der drei geriggten Figuren, die heute als Pack in der Engine stehen: Modellierung,
Skelett, UV-Abwicklung, Texturen, Backen der Normalen und Masken, Export als `.blend` und `.glb`.
Alles ist Skript, nichts ist von Hand in Blender gebaut. Die Erzeugnisse liegen nicht im Repo.

Maße laut `spec.py`: Imp rund 1,0 m, Verdammte Seele rund 1,8 m, Brute rund 2,4 m. Grundfarben und
Materialwerte stehen in `palette.py` und folgen der [Stilbibel](../../docs/art/stilbibel.md).

## Werkzeuge

- **Python 3 mit numpy** für die Texturstufen (ohne Blender).
- **Blender 5.2** headless für Modell, Backen und Export. Alle Blender-Aufrufe laufen mit
  `-b --factory-startup`, damit keine persönlichen Einstellungen hineinwirken.

## Ablauf

Die Figuren sind in drei Runden entstanden. Jede Runde baut auf der vorigen auf und ändert deren
Dateien nicht; die Kopfkommentare der Skripte sagen jeweils, was sie übernehmen und was neu ist.

1. **Grundtexturen** aus [`../textures`](../textures/README.md):

   ```
   python -B generate.py
   ```

2. **Runde 2 – Figurenmaterialien mit Relief** (Poren, Narben, Maserung), nur numpy:

   ```
   python -B texgen_r2.py --src <textures>/generated --out <runde2>/generated
   ```

3. **Runde 3 – Vorbereitung** der zwei neuen Hornmaterialien, nur numpy:

   ```
   python -B bootstrap_r3_textures.py --src <runde2>/generated --out <runde3>/generated
   ```

4. **Runde 3 – Figur bauen**, je Figur einmal (`imp`, `soul`, `brute`):

   ```
   blender -b --factory-startup --python build_character_r3.py -- \
       --character imp --tex-dir <runde3>/generated \
       --blend-dir <ziel> --blend-dir-low <ziel>/low --work <arbeit> \
       --subsurf-high 2 --subsurf-low 1
   ```

   Das Skript backt Krümmung und Verdeckung aus dem eigenen Netz, erzeugt daraus die
   Abnutzungstexturen neu (`texgen_r3.py`), backt die Normalen von der hohen auf die sparsame Stufe
   und exportiert beide Stufen als `.blend` und `.glb` – die `.glb` **mit Tangenten**, gegen die
   gebacken wurde.

5. **Pack** über den Konverter in [`../figure_pack`](../figure_pack/README.md). Die Engine liest die
   sparsame Stufe.

`export_r3d.py` exportiert eine bereits gebaute `.blend` erneut mit Tangenten. Damit ist die Fassung
`_r3d` aus `_r3c` entstanden, bevor Schritt 4 die Tangenten selbst exportierte.

## Wiederholbarkeit

Jede Zufallsquelle ist fest: Der Seed eines Materials ist `palette.stable_seed(basis, name)`, eine
CRC32-Prüfsumme des Materialnamens. Früher stand dort Pythons `hash()`, das bei jedem Prozessstart
neu gesalzen wird – jeder Lauf erzeugte ein anderes Muster aus Narben, Flecken und Maserung, auch
bei unverändertem Code, und zwei Läufe ließen sich nicht vergleichen. Verzeichnisse werden sortiert
gelesen.

Nachgewiesen für die Stufen 2 und 3 (reines numpy): zwei Läufe mit verschiedener
`PYTHONHASHSEED` ergeben bytegleiche Texturen. Für den Blender-Teil (Schritt 4) steht der Nachweis
noch aus; Blenders eigenes Backen ist ein eigener Kandidat für Abweichungen.

Die Fassung `_r3c` (kräftigere Grundfarbe) wurde **nicht** mit diesen Skripten erzeugt, sondern
durch nachträgliches Umfärben der fertigen Texturen – ein exakter Neulauf war wegen des alten Seeds
nicht möglich. Die neuen Grundfarben stehen inzwischen in `palette.py`. Ein Neulauf trifft den
Farbton also direkt, hat aber ein anderes Detailmuster als `_r3c`.

## Bekannte Mängel

Gemessen in der Engine, in Full HD, mit Mipmaps, Multisampling und echten Tangenten
(siehe [Plan 0002](../../docs/plans/0002-phase-p1-sichtbarer-kern.md), Nachtrag Texturqualität):

- **Flickwerk** an Armen, Beinen und Schwanz sowie an der Mittelnaht. Es kommt aus der Farbtextur
  und verschwindet nur ohne sie.
- **Dunkle, eckige Flecken am Kopf.** Sie kommen aus der gebackenen Normalenkarte. Der Grünkanal
  und die Tangenten sind nachweislich richtig.
- Die Augenhöhlen sind mit Dreiecksfächern eingesetzt statt mit sauberen Kantenschleifen.

## Tests

Ohne Blender: `python -B test_texgen_r3.py`.

Mit Blender: `test_headsculpt.py` und `test_geomasks.py`, jeweils als
`blender -b --factory-startup --python <test>`. Die Tests schreiben nach `work/`, das ignoriert ist.

Die Render-Skripte (`render_*.py`) belasten die Grafikkarte. Sie laufen nur, wenn sie frei ist.

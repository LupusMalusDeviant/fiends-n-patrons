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

Die Figuren sind in vier Runden entstanden. Jede Runde baut auf der vorigen auf; die Kopfkommentare
der Skripte sagen jeweils, was sie übernehmen und was neu ist. **Aktuell ist Runde 4.**

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

4. **Runde 4 – Figur bauen**, je Figur einmal (`imp`, `soul`, `brute`):

   ```
   blender -b --factory-startup --python build_character_r4.py --        --character imp --tex-dir <runde3>/generated        --blend-dir <ziel> --blend-dir-low <ziel>/low --work <arbeit>
   ```

   Das Skript baut Körper, Skelett und Anbauteile wie Runde 3, legt dann aber für jedes texturierte
   Material ein eigenes UV-Layout ohne geteilte Texel an, trägt das Grundmuster im Objektraum auf
   (`texproject.py`), berechnet Krümmung, Verdeckung und die Formnormale der sparsamen Stufe ohne
   Cycles-Bake (`shapenormal.py`) und exportiert beide Stufen als `.blend` und `.glb` mit Tangenten.

5. **Pack** über den Konverter in [`../figure_pack`](../figure_pack/README.md). Die Engine liest die
   sparsame Stufe.

`build_character_r3.py` (Runde 3) bleibt als Quelle der Fassungen `_r3*` im Repo, ebenso
`export_r3d.py`, das eine gebaute `.blend` erneut mit Tangenten exportiert – daraus entstand `_r3d`.

## Was Runde 4 behebt

Gemessen am ausgelieferten Imp `_r3d`, in der Engine und an den Texturen selbst:

- **Flickwerk** an Armen, Beinen und Schwanz. Das Grundmuster entstand als flaches Bild im UV-Raum;
  jede UV-Insel zeigte ein fremdes Stück davon. An Nähten sprang die Helligkeit im Median um 16
  Stufen, im Inneren einer Insel um 0,9 – schon im frisch erzeugten Muster ohne Abnutzung. Runde 4
  tastet das Muster über die Position im Raum ab: Nahtsprung 2,9 gegen 2,2 im Inneren.
- **Dunkle, eckige Flecken am Kopf.** Die UV-Inseln lagen im Weltmaßstab über mehrere Kacheln, und
  nach dem Kacheln teilten sich Körperteile dieselben Texel – am Kopf 81 %. Wo Geometrie in diese
  Texel gebacken wurde, überschrieben sich die Teile gegenseitig (Abweichung der Formnormale am Kopf
  p90 70° gegen 9° in ungeteilten Texeln). Runde 4: 0 geteilte Texel in allen sieben Materialien,
  Kopf p90 15°.
- **Umgekehrte Normalen aus dem Cycles-Bake.** Selbst ohne geteilte Texel schrieb der
  Selected-to-Active-Bake exakt umgekehrte Normalen in 39 % der Horn-Texel; in Runde 3 blieb das Horn
  ganz flach. `shapenormal.py` nimmt stattdessen die Normale der hohen Stufe am nächsten
  Oberflächenpunkt – die Eckpunkte der sparsamen Stufe liegen nachweislich auf der hohen Oberfläche.
  Wo die hohe Normale von der Oberfläche wegzeigt (am Horn 12 % der Texel, dünne Linien entlang der
  Rillen, am ehesten Falten der gerillten Geometrie), bleibt die Normale der sparsamen Stufe.
- **Grünkanal der Detail-Normalen umgekehrt.** `normalmap.height_to_normal` nahm die Zeilenrichtung
  des Bildes als V-Richtung, Bildzeilen laufen aber nach unten. Gegen Blenders eigenes Backen
  gemessen: rot +1,000, grün −1,000; nach der Korrektur beide +1,000. Das betraf alle Detail-Normalen
  aus Runde 2 und 3, nicht die Grundtexturen aus `../textures`.

Die Texeldichte sinkt, weil jedes Material jetzt genau eine Kachel belegt: Imp-Haut 562 px/m,
Seelen-Umhang 440, Brute-Fleisch 181, Horn und Krallen über 2.000. Die Spielkamera zeigt rund
35–65 px/m.

## Wiederholbarkeit

Zwei vollständige Läufe aller drei Figuren in getrennten Blender-Prozessen ergeben bytegleiche
Ergebnisse: alle 49 Texturen und Zwischenbilder, alle sparsamen `.glb` (sie gehen ins Pack) und die
hohen `.glb` von Imp und Seele. Einzige Abweichung: zwei von 21.326 Tangenten der hohen Brute-Stufe
um 0,0001.

Dafür waren drei Dinge nötig:

- **Stabiler Seed:** Der Seed eines Materials ist `palette.stable_seed(basis, name)`, eine
  CRC32-Prüfsumme des Materialnamens. Pythons `hash()` wird bei jedem Prozessstart neu gesalzen.
  Verzeichnisse werden sortiert gelesen.
- **Feste Reihenfolge der Netzelemente:** `surface.py` und `headsculpt.py` bauen den Körper über
  Mengen von Blender-Elementen, deren Reihenfolge an Speicheradressen hängt. Die Punkte waren in jedem
  Prozess gleich, Flächen, Ecken und Kanten nicht – und Aufklappen, Packen und Unterteilen folgen
  dieser Reihenfolge. Runde 4 baut den Körper deshalb aus reinen Daten in fester Reihenfolge neu auf
  und sortiert die Flächen der Anbauteile vor dem Export.
- **Kein Cycles-Bake:** Krümmung, Verdeckung (Strahlen je Punkt mit festem Seed) und Formnormale
  rechnet das Skript selbst.

Die Fassung `_r3c` (kräftigere Grundfarbe) wurde nachträglich umgefärbt, nicht mit diesen Skripten
erzeugt. Die neuen Grundfarben stehen in `palette.py`, Runde 4 trifft den Farbton also direkt.

## Bekannte Mängel

- Die Augenhöhlen sind mit Dreiecksfächern eingesetzt statt mit sauberen Kantenschleifen.
- Die Rillen der Hörner falten die hohe Geometrie; dort bleibt die Oberfläche glatt statt gerillt.
- Der simulierte Umhang der Seele ist ein eigenes Stoffobjekt und trägt weiter die gekachelte Textur
  aus Runde 2; an seinen UV-Nähten bleibt Flickwerk sichtbar. Runde 4 erfasst nur den Körper.
- Die Lederriemen am Umhang der Seele liegen jetzt im Raum und treffen auf die Figur nur in wenigen
  schmalen Streifen (rund 1 % der Umhang-Texel).

## Tests

Ohne Blender: `python -B test_texproject.py` und `python -B test_texgen_r3.py`.

Mit Blender, jeweils als `blender -b --factory-startup --python <test>`:
`test_normal_convention.py` (Grünkanal und Formnormale gegen Blenders eigenen Bake),
`test_headsculpt.py`, `test_geomasks.py`. Die Tests schreiben nach `work/`, das ignoriert ist.

Die Render-Skripte (`render_*.py`) belasten die Grafikkarte. Sie laufen nur, wenn sie frei ist.

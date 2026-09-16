# Prozedurale Texturen – Fiends n Patrons

Erstes Materialpaket für die Look-Testszene: 13 reproduzierbare Materialien,
1024 × 1024 Pixel, glTF-2.0-Metallic-Roughness. Die Python-Skripte und der Katalog
sind die Quellen. PNGs und Berichte sind erzeugte, lokal ignorierte Ergebnisse.

## Aktueller Stand nach der Rückmeldung

Die Quellen sind korrigiert: Bronze verwendet jetzt **#80603D bei Metall = 1**,
Kerzenwachs **#D8CDB4**. Die strengen Helligkeits-/Sättigungsgrenzen gelten nur
für große Umgebungsflächen. Kleine Props besitzen die neue Kategorie `prop`;
ihr Validator verbietet die reservierten Bullet-Farbbereiche, erlaubt aber
natürliche warme und helle Materialfarben. Der vorhandene Umhang bleibt
unverändert **#24505C**. Die Steinrezepte haben zusätzliche mittelgroße Risse,
Kantenschäden und Verschleiß an Fugen; die Mittelwerte bleiben erhalten.

Nach Ende des Spielbetriebs wurden alle **13 korrigierten Materialien in
1024 × 1024 Pixeln** neu erzeugt und erfolgreich geprüft. `generated/` enthält
jetzt die aktuellen Bronze-/Wachsfarben und überarbeiteten Steinmerkmale.
Das Manifest erfasst 67 Dateien mit insgesamt 4.563.532 Bytes (rund 4,35 MiB).
Die früheren **128-Pixel-Vorschauen** liegen weiterhin unter `preview_revision/`.
Die Anwendung und der Licht-/Kameratest in der Blender-Szene stehen noch aus.

Die Erweiterung unter `actors_projectiles/` umfasst **zwölf Figurenmaterialien
und acht gotische Projektilsprites**. Ihren jeweiligen Erzeugungs- und
Prüfstatus sowie die Übergabe beschreibt
[actors_projectiles/README.md](actors_projectiles/README.md).

## Erzeugen und prüfen

Im Ordner dieser README ausführen:

Ressourcenschonender Vorschaupfad (ein numerischer Thread, unter Windows
Idle-Priorität, kurze Pausen zwischen Materialien; kein GPU-Backend):

```sh
python -B generate.py --light-preview
python -B validate.py --root preview_revision --expected-resolution 128 --write-report
```

Vollauflösung (die Ressourcenbeschränkung ist aufgehoben):

```sh
python -m pip install -r requirements.txt
python -B generate.py
python -B validate.py --write-report
```

Benötigt Python 3.11 oder neuer; geprüft mit Python 3.14 und den gepinnten
NumPy-/Pillow-Versionen. Der normale Generatorlauf schreibt nur in `generated/`.
Ein alternativer Ausgabeordner muss innerhalb dieses Texturordners liegen.
Vorhandene gleichnamige Build-Ergebnisse werden beim erneuten Lauf ersetzt.
Der Katalog bestimmt Materialwerte, physische Kachelgrößen und Seeds.

Für einen kleineren technischen Probelauf:

```sh
python -B generate.py --size 128 --output repro_check
python -B validate.py --root repro_check --expected-resolution 128
```

Der 128-Pixel-Lauf prüft den Ablauf. Die Abnahme erfolgt mit 1024 Pixeln; bei
niedrigerer Auflösung können Reliefdetails und quantitative Randstatistiken
wegen der anderen Abtastung abweichen.

## Lieferumfang

Je Material in `generated/<material_id>/`:

| Datei | Bedeutung |
|---|---|
| `*_basecolor.png` | Unbeleuchtete Materialfarbe, sRGB |
| `*_normal.png` | Tangentenraum-Normalen, OpenGL/+Y, linear |
| `*_orm.png` | R = Material-AO, G = Rauheit, B = Metall, linear |
| `*.json` | Faktoren, Zielmittelwerte, Farbräume, physische Kachelgröße und Seed |
| `*_tile_2x2.png` | Exakte 2×2-Wiederholung der unbeleuchteten BaseColor, 2048 × 2048 |

Zusätzlich enthält `generated/` eine beschriftete Materialübersicht, ein
Manifest mit SHA-256 und Dateigrößen sowie nach der Prüfung `validation.json`.
`camera_scale.png` zeigt vier Farbmaterialien mit 35, 50 und 65 Pixeln pro Meter.
Diese Vorschau bei 100 % Bildgröße beurteilen.
Die Übersicht zeigt pro Material oben die Farbtextur und unten eine separat
beleuchtete GGX-Flächenstudie. Sie ist kein Render aus Blender oder Grimoire.
Die Beleuchtung der Übersicht wird niemals in die Quelltexturen übernommen.

Die 13 angeforderten Grundmaterialien benötigen keine Emission. Flammen,
Augen, Runen und die Stabkugel gehören zu eigenen späteren Effektmaterialien.
Es werden weder Mipmaps noch Runtime-Kompression erzeugt.

## Farbentscheidung

Vorrang hat die korrigierte Vorgabe: **große Umgebungsflächen kühl und dunkel;
kleine Props in ihren Materialfarben**.
Farbton ist in HSV auf den sRGB-Zahlen definiert, Helligkeit bedeutet HSV-V.

- Große Steinflächen einschließlich Altar: H 200–240°, S höchstens 25 %, V
  höchstens 35 %. Neutrales Grau besitzt keinen relevanten Farbton.
- Moos an der Ruinenmauer: H 100–110°, ebenfalls S höchstens 25 %, V höchstens
  26 %; die erzeugten grünen Pixel bleiben tatsächlich bei V höchstens 25 %.
  Der zuvor vorgeschlagene Bereich 90–95° überschneidet sich mit Giftlimette
  und wird deshalb nicht verwendet.
- Übergänge zwischen Stein und Moos gehen durch entsättigtes Grau. Sie mischen
  keine zusätzliche cyanfarbene Pigmentzone in die Umgebung.
- Kleine Props wie Bronze und Wachs dürfen wärmer und heller sein. Verboten
  bleiben H 315–335° (Magenta), 75–95° (Limette) und 185–200° (Eis-Cyan).
- Figurenmaterialien (Umhang, Maske, Stab, Haut, Fleisch und Schulterplatten)
  verwenden die zugehörigen Szenenfarben. Diese Farben sind keine Freigabe zur
  Verwendung derselben Materialien auf großen Umgebungsflächen.

| Material-ID | Bereich | BaseColor-Ziel | Rauheit | Metall | Kachelgröße |
|---|---|---|---:|---:|---|
| floor_tiles | Umgebung | #33363D | 0,85 | 0 | 4 × 4 m |
| grout | Umgebung | #1A1C21 | 0,95 | 0 | 1 × 1 m |
| pillar_stone | Umgebung | #3E4047 | 0,75 | 0 | 2 × 2 m |
| ruin_wall_moss | Umgebung | #383A3F | 0,85 | 0 | 4 × 4 m |
| altar_basalt | Umgebung | #26282D | 0,60 | 0 | 2 × 2 m |
| bronze | Kleiner Prop | #80603D | 0,35 | 1 | 1 × 1 m |
| candle_wax | Kleiner Prop | #D8CDB4 | 0,85 | 0 | 0,25 × 0,25 m |
| cloak_fabric | Figur | #24505C | 0,90 | 0 | 1 × 1 m |
| bone_mask | Figur | #CFC3A8 | 0,60 | 0 | 0,5 × 0,5 m |
| staff_wood | Figur | #4A311E | 0,70 | 0 | 1 × 1 m |
| imp_skin | Figur | #7A5231 | 0,55 | 0 | 1 × 1 m |
| brute_flesh | Figur | #5E2B25 | 0,60 | 0 | 2 × 2 m |
| shoulder_plates | Figur | #3B3A3E | 0,40 | 0 | 1 × 1 m |

**Abweichungen von der Szene:** Basalt war #2A2528; sein korrigierter kühler Wert
bleibt bestehen, da der frühere Farbton im reservierten Magenta-Bereich liegt.
Wachs ist wieder beim ursprünglichen #D8CDB4. Die PBR-Szenenbronze besitzt
den Metall-Reflexionswert #F2C28A; nun wird der ausdrücklich gewünschte,
gedämpfte Bereich #6B4A2A bis #8C6A45 mit #80603D getroffen. Bei
glTF-Metallic = 1 ist BaseColor die Reflexionsfarbe. Wie dunkel die Bronze
damit in der tatsächlichen Szene wirkt, muss der spätere Lichttest zeigen.

Schulterplatten behalten Metall = 0 aus der Szenenvorlage. Der Name allein
legt kein freiliegendes Metall fest. Alle Metallkanäle enthalten nur 0 oder 255.

## Anwendung in Blender / glTF

1. Mesh-UVs so skalieren, dass ein kompletter UV-Repeat die in `tile_size_m`
   angegebene Fläche abdeckt. Vier Meter des Bodens enthalten vier Platten je
   Achse. Abbildungen an Säulen und Figuren brauchen passende UV-Abwicklungen.
2. BaseColor-Bild als **sRGB** laden und direkt an Principled Base Color anschließen.
3. Normal-Bild als **Non-Color** laden, über einen Normal-Map-Node im Tangentenraum
   mit Strength 1 an Normal anschließen. **Grün nicht invertieren.**
4. ORM als **Non-Color** laden; G an Roughness und B an Metallic. R ist separat
   als glTF-Occlusion zu exportieren, beispielsweise über den entsprechenden
   glTF-Material-Output. AO nicht dauerhaft in BaseColor multiplizieren.
5. glTF-Faktoren: BaseColor = weiß, RoughnessFactor = 1, MetallicFactor = 1.
   Die tatsächlichen Werte stehen bereits in den Bildern. Eine erneute
   Multiplikation mit den Mittelwerten würde sie doppelt anwenden.
6. Exportierte Texturen mit Repeat adressieren. Mipmaps, Kompression und die
   spätere Pack-Erstellung bleiben Aufgaben der bestehenden Asset-Pipeline.

Die Material-JSON ist eine kleine Übergabedatei für das Blender-/Compiler-Skript;
sie ist selbst kein fertiges glTF und wird von Grimoire noch nicht geladen.

Die Normalen stammen aus demselben Relief, das auch Rauheits- und
Material-AO-Variationen strukturiert. Ableitungen berücksichtigen die Kachelgröße
in Metern. Bei top-down gespeicherten Bildern bedeutet OpenGL/+Y:
`normal = normalize(-dH/dx, +dH/dBildzeile, 1)`. Ein analytischer Sinustest prüft
die beiden Vorzeichen bei jedem Generatorlauf.

AO ist eine zurückhaltende **Material-Vertiefungsmaske**, kein am Zielmodell
gebackenes AO. Kontaktabschattung zwischen Modellteilen entsteht erst am
konkreten Modell. Modellnähte, Silhouetten und die vollständige Lesbarkeit im
Bullet-Gewühl müssen nach der Anwendung in der echten Szene geprüft werden.

## Prüfungen und Grenzen

Die aktuelle korrigierte Ausgabe wurde mit `python -B generate.py` vollständig
in **1024 Pixeln** erzeugt und anschließend mit
`python -B validate.py --write-report` erfolgreich geprüft: **13 Materialien,
67 Manifestdateien, 4.563.532 Bytes (rund 4,35 MiB)**. Manifest und Prüfbericht
kommen zu dieser Dateisumme hinzu. Alle PNGs einschließlich der Übersichten
wurden auf ausschließlich IHDR/IDAT/IEND geprüft.

Für diesen überarbeiteten Stand wurde ein vollständiger Masterlauf geprüft.
Ein zweiter vollständiger Lauf zum Nachweis byteidentischer Wiederholung
steht aus; der entsprechende Nachweis der früheren Ausgabe wird nicht auf
den korrigierten Stand übertragen.

`validate.py` prüft Auflösung, PNG-Format und CRCs, Kanalbelegung,
Metall-Binärwerte, Normalenlänge, Zielmittelwerte, per-Pixel-Palettenregeln,
2×2-Vorschauen, Randgradienten sowie Manifest-Hashes und Dateigrößen.
Der BaseColor-Mittelwert darf je Kanal höchstens 2 RGB8-Stufen vom Ziel abweichen.
Zusätzlich werden lineare Farbmittelwerte zur späteren Kalibrierung ausgegeben.

Die Muster sind periodische Funktionen. Erste und letzte Pixel sind benachbarte
Abtastwerte und müssen deshalb nicht identisch sein. Die Prüfung vergleicht
Randgradienten mit inneren Gradienten und einer Quantisierungstoleranz.
Sie ersetzt nicht die visuelle Kontrolle bei gekachelter Darstellung.

Relief und Rauheit werden periodisch tiefpassgefiltert: Der Filter beginnt bei
9 Zyklen pro Meter und entfernt Frequenzen ab 14 Zyklen pro Meter. Das begrenzt
die direkte Reliefstruktur auf etwa 7 cm und gröber; die nichtlineare
Lichtberechnung kann dennoch neue hohe Frequenzen erzeugen.

Details sind bewusst breit und kontrastarm. Das minimiert Störungen bei der
Spielkamera, beweist aber noch keine Flimmerfreiheit unter Bewegung. Mipmaps,
Spekular-AA und ein Kameratest mit 35–65 Pixeln pro Meter bleiben erforderlich.

Feste Seeds und gepinnte Bibliotheken machen den Build wiederholbar.
Bitidentische Ausgaben lassen sich durch zwei vollständige Läufe und den
Vergleich aller Datei-Hashes bestätigen. Bitgleichheit über andere Plattformen
und Bibliotheksversionen wird nicht zugesichert.

## Herkunft und Repository

Es werden keine externen Bilder, Texturen, Fonts oder CC0-Assets heruntergeladen.
Alle Materialmuster entstehen aus dem eigenen Quellskript. Deshalb ist die Liste
`external_sources` leer; es werden keine fremden Texturen als eigene oder als
CC0 deklariert. Die erzeugten Materialien verweisen auf die Projektlizenz.

Sollten später CC0-Bilder als Eingaben hinzukommen, müssen Asset-Name, konkrete
Quell-URL, Lizenz CC0 und Bezugsdatum vor dem Build ins Manifest aufgenommen werden.

PNG-Dateien enthalten ausschließlich IHDR-, IDAT- und IEND-Blöcke. Farbräume
stehen explizit in der Material-JSON und müssen beim Import gesetzt werden.
Es gibt keine EXIF-, Text-, Zeit-, Profil- oder Rechnerdaten. Metadaten verwenden
nur portable Dateinamen, keine privaten absoluten Pfade. Es werden keine
Blender-Dateien erzeugt oder versioniert. Die Skripte führen keine Git-Befehle aus.

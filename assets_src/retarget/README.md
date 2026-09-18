# retarget/

Überträgt die Bewegungen einer humanoiden Animationsbibliothek auf das Rig einer Spielfigur und
misst, wie viel vom Rig die Bewegung erreicht. Ergebnis ist eine `.glb` mit denselben Clipnamen und
Clip-Längen wie vorher, nur mit Bewegung in allen verformenden Gelenken; von dort geht es wie
gewohnt durch [`../asset_import`](../asset_import/README.md) (Stufe 2) und
[`../figure_pack`](../figure_pack/README.md) (Stufe 3) ins Pack.

## Warum

Ein Clip kann für jedes Gelenk einen Kanal haben und trotzdem fast nichts bewegen. Gemessen an der
Hexe, vor diesem Ordner: ihre 18 Clips bewegten **5 bis 11 ihrer 31 Gelenke**. Füße, Hände,
Schlüsselbeine und Becken standen in **allen** Clips still, im `walk` zusätzlich der Kopf. Deshalb
wirkten Knöchel steif, Ellbogen gerade und die Hüfte tot.

Die Ursache ist nicht die Wiedergabe und war auch kein kaputtes Retarget: Die ausgelieferten Clips
sind **von Hand gesetzt** (`assets_src/witch_rig/build.py` der PO, außerhalb dieses Repos), und
ihre Pose-Tabellen setzen je Clip nur eine Handvoll Knochen. Es gab daneben einen Retarget-Versuch
der PO (`assets_src/witch_mocap/retarget_trial.py`), der 19 der 31 Gelenke abbildete, nur Drehungen
schrieb, Rock und Umhang ausließ und dessen Bewegungsqualität die PO am 17.09. abgelehnt hat. Beide
Wege sind hier nicht verändert worden; dieser Ordner ist der neue, vollständige Weg.

Die Bibliothek selbst ist reich genug: ihre Clips bewegen **17 bis 21 Körperknochen** samt Füßen,
Händen, Schultern, Nacken und beiden Rumpfgelenken (gemessen mit `clip_coverage.py`).

## Ausführen

```sh
python -B retarget_clips.py --figure <figur_animiert.glb> --library <bibliothek.glb>
    --bone-map witch_bone_map.json --clip-table witch_clip_table.json
    --out-dir <ziel> --name witch --blender <blender>
```

(Je Aufruf eine Zeile; Pfade sind Argumente, im Quelltext steht keiner.) Geschrieben werden
`<name>_retargeted.glb`, `<name>_retarget.json` (was der Lauf getan hat), `<name>_coverage.json`
(bewegte Gelenke je Clip, vorher und nachher) und `<name>_blender.log`. Blender läuft mit `-b`,
`--factory-startup` und **einem** Thread; zwei Läufe derselben Eingaben ergeben dieselbe Datei
(nachgewiesen: gleiche SHA-256).

Zwei Datendateien steuern den Lauf, damit eine Änderung eine Zeile ist und kein Patch:

- **`witch_bone_map.json`** — welches Gelenk der Figur welchem Knochen der Bibliothek folgt,
  welche Gelenke zusätzlich eine Position bekommen, und welche Ketten ohne Gegenstück als Stoff
  mitgezogen werden.
- **`witch_clip_table.json`** — welcher Bibliotheksclip welchen Spielclip speist, wie viele Bilder
  der Spielclip hat, ob er schleift und ob seine Füße auf den Boden gezogen werden.

## Wie eine Bewegung übertragen wird

Die beiden Rigs teilen die Gestalt eines Skeletts, nicht seine Ruhepose: Knochenlängen, Rollwinkel
und Ruheausrichtungen unterscheiden sich. Übertragen wird deshalb nicht eine Ausrichtung, sondern
deren **Änderung**, im Raum der Armatur:

    delta(f) = pose_b(f) @ rest_b^-1          die Drehung, die der Quellknochen seit seiner Ruhe gemacht hat
    want_a(f) = delta(f) @ rest_a             dieselbe Drehung auf die Ruhepose der Figur

Die Gelenke werden Eltern zuerst durchlaufen, und die lokale Pose — das, was ein Keyframe
speichert — folgt aus der schon berechneten Pose des Elternteils. Zwischen zwei Gelenken wird
nichts aus dem Depsgraph zurückgelesen: die Pose einer ganzen Figur zu einem Bild entsteht als
Zahlen und wird erst danach als Keyframes geschrieben. Genau das macht einen Lauf wiederholbar.

**Positionen** kommen nur für die Gelenke der Liste `translation` (das Becken) mit; alles andere
bekäme sonst fremde Knochenlängen. Der Versatz wird mit dem Verhältnis der Rumpflängen beider Rigs
skaliert (gemessen: 0,583) — nicht mit einer Höhe über dem Boden, denn der Ursprung eines Rigs kann
überall liegen (der der Hexe liegt bei −0,1 in ihren eigenen Einheiten).

**Füße auf dem Boden.** Drehungen allein halten eine Figur nicht am Boden: die Bibliothek hat im
Verhältnis zum Rumpf längere Beine als die Hexe, also hängt sie in einer geduckten Haltung in der
Luft — gemessen am Jogging das Zehnfache des Abstands, den ein Gang zeigt. Clips mit
`"ground": true` werden deshalb abgesenkt: Pose rechnen, den tieferen Fuß mit seiner Höhe in der
Ruhepose vergleichen, und wenn er schwebt, das Becken um genau diesen Betrag senken und die Pose
noch einmal rechnen. Angehoben wird nie, und außer dem Becken bewegt sich nichts.

**Rock und Umhang** haben in der Bibliothek kein Gegenstück. Statt sie als einzige Teile einer
bewegten Figur starr zu lassen, ziehen sie nach: jedes Glied dreht gegen die Drehung, die sein
Anker in den letzten `lag` Bildern gemacht hat, um `follow` davon, jedes weitere Glied um `falloff`
des vorigen. Keine Simulation, kein Cache, kein Zufall. In einem schleifenden Clip greift die
Verzögerung über das Ende der Schleife hinweg, damit das letzte Bild wieder das erste ist.

**Schleifen** schließen exakt: Das Clipformat speichert eine Schleife mit dem ersten Bild als
letztem. Die Bibliotheksschleifen schließen bis auf 0,004 in einer Quaternionkomponente; für Clips
mit `"loop": true` wird das letzte Bild als Kopie des ersten geschrieben, damit die Abtastung bei
der Cliplänge bitgleich das erste Bild liefert.

**Nicht abgebildet, mit Absicht:** `root` (die Simulation bewegt die Figur) und die beiden
Waffen-Sockel (sie hängen an den Händen). Finger und Zehen hat die Hexe nicht, die Bibliothek hat
keinen Rock und keinen Umhang.

## Messen statt hinsehen

- **`clip_coverage.py <figur.glb>`** — je Clip die Zahl der Gelenke, deren Werte sich tatsächlich
  ändern (Schwelle 1e-5), plus welche stillstehen. Das ist die Zahl, an der dieser Ordner gemessen
  wird. Sie ignoriert Kanäle, die es nur auf dem Papier gibt.
- **`pose_check.py <figur.glb>`** — je Bild die Neigung (Becken zu Kopf gegen die Senkrechte), die
  Verdrehung der Schulterlinie gegen die Ruhepose und die Höhe beider Knöchel über dem Boden, samt
  Ruhewerten. Damit sieht man ohne Renderer, ob eine Figur steht, fällt oder schwebt.

## Ergebnis des Hexen-Laufs

Bewegte Gelenke je Clip (von 31; `root` und zwei Sockel bleiben mit Absicht in Ruhe, es sind also
28 erreichbar):

| Clip | Bilder | vorher | nachher | Clip | Bilder | vorher | nachher |
|---|---:|---:|---:|---|---:|---:|---:|
| idle | 49 | 5 | 26 | parry | 14 | 8 | 27 |
| walk | 17 | 9 | 28 | skill_cast | 19 | 9 | 25 |
| run | 13 | 10 | 26 | ultimate | 30 | 11 | 28 |
| dash | 15 | 9 | 26 | bomb | 19 | 7 | 28 |
| melee_1 | 14 | 7 | 25 | item_use | 15 | 6 | 23 |
| melee_2 | 15 | 7 | 26 | rewind | 16 | 7 | 28 |
| melee_3 | 20 | 10 | 28 | hit_react | 12 | 7 | 24 |
| death | 41 | 10 | 28 | spawn | 18 | 10 | 28 |
| interact | 15 | 5 | 25 | victory | 31 | 8 | 28 |

Haltung, gemessen mit `pose_check.py` an der fertigen Spielfigur: Gang 15,7° Neigung und 7,6°
Verdrehung mit dem Standfuß genau auf Ruhehöhe; Lauf 30,9° Neigung; `melee_3` 110° Verdrehung (ein
Schwertschwung); `death` 84° Neigung am Ende (sie liegt). Der erste Versuch mit `Sprint_Loop`
statt `Jog_Fwd_Loop` als Laufquelle wurde verworfen: 43,7° Neigung und ein Standfuß 17,5 cm über
dem Boden.

## Tests

```sh
python -B -m unittest test_retarget.py
```

Geprüft wird alles, was entscheidet, *was* ein Lauf tut: das Lesen beider Datendateien samt ihrer
Fehlerfälle, die Verteilung der Bilder über den Quellbereich, der Abgleich des Plans gegen zwei
Rigs, und die Messung selbst (Schwelle, längster Kanal statt erstem, Bänder je Clip). Die
Posen-Mathematik lebt in Blender; sie wird durch die Zahlen des Laufs und die Offscreen-Bilder
geprüft.

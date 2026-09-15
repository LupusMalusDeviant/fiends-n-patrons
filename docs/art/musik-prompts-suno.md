# Musik-Prompts (Suno) — Stil-Referenz für die Klangbibel

- **Status:** Referenz, kein Spielinhalt
- **Datum:** 2026-09-15
- **Autor:** Lupus Malus Deviant (PO) / Claude (Ausarbeitung)
- **Bezug:** [PRD-0012 Audio](../prd/0012-audio-system.md) (Metal-Hybrid, vertikale Stems, Beat-Clock, Musik-Zustandsmaschine FR-06), [PRD-0014 UI/UX](../prd/0014-ui-ux.md) (Menü-Hub, Patron-Kammer, Todes- und Sieg-Screen), [PRD-0001](../prd/0001-vision-und-scope.md) (2–3 Stages, 3 Bosse)

## Zweck

Die zehn Prompts beschreiben den Klang des Spiels als Metal-Hybrid: Riffs, düstere Elektronik
und okkulte Elemente wie Chor und Glocken. Die damit erzeugten Stücke dienen als Hörbeispiele für
die Klangbibel (`docs/art/klangbibel.md`, PRD-0012). Die Tabelle ordnet jedes Stück einem
Spielzustand zu, damit erzeugte Varianten später eindeutig zugeordnet werden können.

Laut PRD-0012 (FR-07) entsteht die Spielmusik aus DSP-Rezepten der Audio-Werkstatt. Suno-Stücke
direkt ins Spiel zu übernehmen, wäre eine Änderung an PRD-0012 und bräuchte eine eigene
Entscheidung, auch zu den Nutzungsrechten des jeweiligen Suno-Tarifs.

## Zuordnung

| ID | Titel | Einsatz im Spiel | Musik-Zustand (PRD-0012 FR-06) | BPM | Tonart | Datei-Präfix | Status |
|----|-------|------------------|--------------------------------|-----|--------|--------------|--------|
| MUS-01 | Pact of Ash | Titelbildschirm und Menü-Hub (Ritualtisch) | Menü | 70 | d-Moll | `mus-01-pact-of-ash` | offen |
| MUS-02 | The Patron's Antechamber | Patron-Kammer, Shop und Altar, Pausen zwischen Läufen | Shop/Altar-Stimmung | 80 | a-Moll | `mus-02-patrons-antechamber` | offen |
| MUS-03 | Crypt of Tallow Saints | Stage 1 (Arbeitstitel „Krypta“) | Stage-Track | 128 | e-Moll | `mus-03-crypt-of-tallow-saints` | offen |
| MUS-04 | Bloodmarsh Liturgy | Stage 2 (Arbeitstitel „Blutsumpf“) | Stage-Track | 136 | g-Moll | `mus-04-bloodmarsh-liturgy` | offen |
| MUS-05 | Clockwork Heresy | Stage 3 (Arbeitstitel „Uhrwerk-Tempel“) | Stage-Track | 140 | c-Moll | `mus-05-clockwork-heresy` | offen |
| MUS-06 | Where the Floor Breaks | Stage-Mutation und Korruption (Verwandlungs-Event) | Stage-Track, Eskalationsschicht | 140 | d-Moll | `mus-06-where-the-floor-breaks` | offen |
| MUS-07 | The Brute Remembers | Mini-Boss | Boss-Track | 100 (Half-Time) | h-Moll | `mus-07-the-brute-remembers` | offen |
| MUS-08 | Hymn to a Hungry God | Boss (Patron zeigt sich), Phasen-Eskalation | Boss-Track | 150 | d-Moll | `mus-08-hymn-to-a-hungry-god` | offen |
| MUS-09 | Unbound Soul | Todesscreen-Sequenz | Todesscreen | 60 | d-Moll | `mus-09-unbound-soul` | offen |
| MUS-10 | Dawn Over the Ashen Choir | Sieg-Screen und Abspann | Sieg | 90 | d-Moll → D-Dur | `mus-10-dawn-over-the-ashen-choir` | offen |

Die Stage-Namen sind Arbeitstitel; Biome und Patrone sind in den PRDs noch nicht benannt.
Für den vollständigen Soundtrack (PRD-0012, P5: 3 Stage-, 3 Boss-, 2 Menü-/Hub-Stücke) fehlen
noch zwei Boss-Stücke.

**Dateinamen für erzeugte Varianten:** `<Datei-Präfix>-v<Nummer>.<Endung>`, zum Beispiel
`mus-03-crypt-of-tallow-saints-v2.mp3`. Die gewählte Variante bekommt in der Tabelle den Status
„ausgewählt: v2“. Audiodateien werden nicht ins Repo eingecheckt (Nutzungsrechte, Größe),
sondern lokal außerhalb des Repos abgelegt.

## Gemeinsame Vorgaben für alle Prompts

- **Instrumente:** Riffs in jedem Stück, dazu Kirchenorgel, tiefer Männerchor ohne Worte, Rahmen- und Kriegstrommeln, Cello, dunkle Synth-Flächen, Glocken.
- **Motiv:** absteigendes Vier-Ton-Motiv D–C–B–A (englisch D-C-Bb-A) als Wiedererkennung.
- **Tempo:** Kampfstücke mit festem BPM und ohne Tempowechsel, weil Bullets und Effekte später an der Beat-Clock hängen (PRD-0012 FR-01).
- **Aufbau in Schichten:** Drone, Percussion, Riffs, Lead, Chor, passend zu den vertikalen Stems (PRD-0012 FR-02).
- **Loops:** Kampf- und Menüstücke als nahtlose Schleife; in der Nachbearbeitung auf ganze Takte schneiden.
- **Nacharbeit:** Wird ein Tempo oder das Motiv nicht getroffen, lieber neu erzeugen als die Abweichung übernehmen.

## Prompts

Jeder Block hat zwei Teile: **Style of Music** gehört in Sunos Stil-Feld, **Lyrics** ins
Textfeld. Die Abschnitts-Marken steuern den Aufbau; Gesang gibt es nur als wortlosen Chor.

### MUS-01 · Pact of Ash (Titel und Menü-Hub)

```text
Style of Music:
occult doom metal hybrid, ominous, 70 BPM, D minor, slow crushing down-tuned guitar riffs, dark synth drone, church organ, low male wordless choir, tolling bells, four-note descending motif D-C-Bb-A as the main riff, cinematic, heavy, instrumental, seamless loop

Lyrics:
[Instrumental]
[Intro: synth drone and bells]
[Riff: slow doom guitars play the motif]
[Choir joins over the riff]
[Break: organ alone]
[Riff returns with full drums]
[Outro: back to drone, seamless loop]
```

### MUS-02 · The Patron's Antechamber (Patron-Kammer, Shop, Altar)

```text
Style of Music:
dark post-metal ambient, calm but uneasy, 80 BPM, A minor, clean reverb-drenched baritone guitar, soft distorted guitar swells in the background, dark synth pads, hammered dulcimer, whispering choir, distant bells, four-note motif D-C-Bb-A on clean guitar, occult sanctuary, instrumental, loopable

Lyrics:
[Instrumental]
[Intro: synth pad and bells]
[Section A: clean baritone guitar with the motif]
[Section B: distorted guitar swells, whispering choir]
[Section A variation with dulcimer]
[Outro: seamless loop]
```

### MUS-03 · Crypt of Tallow Saints (Stage 1)

```text
Style of Music:
industrial metal meets dark ritual electronica, driving, steady 128 BPM, E minor, chugging palm-muted seven-string riffs, pounding kick on every downbeat, pulsing darkwave synth bass, pipe organ hooks, male chant stabs, four-note motif D-C-Bb-A as the riff, energetic, tense, instrumental, constant tempo, loopable

Lyrics:
[Instrumental]
[Intro: synth drone]
[Layer: percussion enters]
[Layer: chugging riffs enter]
[Main Loop: riffs, synth bass, organ hook]
[Break: chant stabs over drums]
[Main Loop B: lead guitar melody on top]
[Outro: seamless loop]
```

### MUS-04 · Bloodmarsh Liturgy (Stage 2)

```text
Style of Music:
tribal groove metal hybrid, relentless 136 BPM, G minor, heavy groove riffs with drop tuning, taiko and frame drums, hurdy-gurdy drone, swampy distorted synth bass, eerie wordless female choir wails, four-note motif D-C-Bb-A on hurdy-gurdy and guitar, primal, dark, instrumental, constant tempo, loopable

Lyrics:
[Instrumental]
[Intro: marsh drone and hurdy-gurdy]
[Layer: tribal percussion]
[Layer: groove riffs]
[Main Loop: full band and drums]
[Break: choir wails over taiko]
[Main Loop B: guitar lead with the motif]
[Outro: seamless loop]
```

### MUS-05 · Clockwork Heresy (Stage 3)

```text
Style of Music:
mechanical djent and industrial metal, precise, 140 BPM, C minor, syncopated djent riffs, ticking clockwork percussion, harpsichord arpeggios, glitchy distorted synth bass, metallic hits, cathedral organ chords, choir stabs, four-note motif D-C-Bb-A on harpsichord answered by guitar, menacing, instrumental, constant tempo, loopable

Lyrics:
[Instrumental]
[Intro: ticking clockwork]
[Layer: harpsichord arpeggios]
[Layer: djent riffs]
[Main Loop: full industrial drums]
[Break: organ chords and choir stabs]
[Main Loop B: double-time drums, lead guitar]
[Outro: seamless loop]
```

### MUS-06 · Where the Floor Breaks (Stage-Mutation, Korruption)

```text
Style of Music:
chaotic dark hybrid metal, rising tension, 140 BPM, D minor, dissonant tremolo-picked guitars, glitching reversed organ, granular cracking textures, pulsing sub bass, heavy toms, choir crescendo, four-note motif D-C-Bb-A distorted and detuned, unstable, transformation, instrumental, constant tempo

Lyrics:
[Instrumental]
[Intro: reversed organ and cracking textures]
[Layer: tremolo guitars rising]
[Build-Up: toms and sub bass]
[Glitch Break]
[Climax: full riffs and choir]
[Outro: hard cut back into the pulse]
```

### MUS-07 · The Brute Remembers (Mini-Boss)

```text
Style of Music:
sludge and doom metal with orchestral brass, crushing, 100 BPM half-time feel, B minor, massively down-tuned heavy riffs, war drums, deep brass, low male choir, organ, feedback swells, four-note motif D-C-Bb-A as the main riff, brutal, heavy, instrumental, constant tempo, loopable

Lyrics:
[Instrumental]
[Intro: feedback and single war drum hits]
[Main Riff: crushing guitars and brass]
[Choir Section over the riff]
[Breakdown]
[Main Riff returns, heavier]
[Outro: seamless loop]
```

### MUS-08 · Hymn to a Hungry God (Boss)

```text
Style of Music:
symphonic black metal meets epic dark electronica, intense, 150 BPM, D minor, fast tremolo riffs, blast beats, pounding synth bass, soaring wordless choir, cathedral organ, full orchestra, bells, four-note motif D-C-Bb-A as the choir theme and main riff, apocalyptic, grand, instrumental with wordless choir, constant tempo, loopable

Lyrics:
[Instrumental]
[Intro: bells and organ]
[Layer: synth bass and drums]
[Layer: tremolo riffs]
[Main Theme: choir sings the motif over blast beats]
[Phase Two: heavier, orchestra joins]
[Break: organ solo with guitar lead]
[Final Section: everything together]
[Outro: seamless loop]
```

### MUS-09 · Unbound Soul (Todesscreen)

```text
Style of Music:
melancholic doom ballad, sad, 60 BPM, D minor, slow clean guitar with heavy reverb, one distant distorted guitar swell, solo cello, dark synth pad, broken music box, single bell, four-note motif D-C-Bb-A slow and fragile, short, intimate, instrumental

Lyrics:
[Instrumental]
[Intro: single bell]
[Main: clean guitar and cello play the motif slowly]
[Distorted swell rises and fades]
[Outro: music box, fade into silence]
[End]
```

### MUS-10 · Dawn Over the Ashen Choir (Sieg-Screen, Abspann)

```text
Style of Music:
epic melodic metal ballad, bittersweet and hopeful, 90 BPM, D minor turning to D major, soaring harmonized lead guitars, powerful but slow riffs, warm synth pads, full choir, church organ, bells, timpani, four-note motif D-C-Bb-A transformed into major, emotional cinematic ending, instrumental with wordless choir

Lyrics:
[Instrumental]
[Intro: motif in minor on clean guitar]
[Build-Up: riffs and drums enter]
[Main Theme: motif in major, harmonized leads and choir]
[Quiet Bridge: organ and bells]
[Final Swell: full band and choir]
[Outro: calm resolution]
[End]
```

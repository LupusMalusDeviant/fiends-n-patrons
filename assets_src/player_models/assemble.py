"""Strip render metadata, assemble model review sheets and record build hashes.

Run using the regular Python interpreter and the texture package's Pillow pin.
This script does not invoke Blender, download assets or write outside generated/.
"""

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent
OUTPUT = BASE / 'generated'
IDS = ['iron_penitent', 'ash_reaver', 'veil_warden']
NAMES = ['EISERNER BUESSER', 'ASCHENLAEUFER', 'SCHLEIERHUETER']
ROLES = ['Schwere Klinge / breite Ruestung', 'Schnelle Sichel / schmale Silhouette', 'Klingenstab / Ritualgewand']
BACKGROUND = (13, 19, 26)
INK = (224, 223, 208)
MUTED = (151, 170, 186)


def clean_png(path):
    with Image.open(path) as image:
        clean = Image.frombytes(image.mode, image.size, image.tobytes())
    clean.save(path, compress_level=3)


def heading(draw, title, subtitle):
    draw.text((26, 20), title, fill=INK, font=ImageFont.load_default(size=30))
    draw.text((26, 64), subtitle, fill=MUTED, font=ImageFont.load_default(size=16))


def overview():
    board = Image.new('RGB', (1536, 1024), BACKGROUND)
    draw = ImageDraw.Draw(board)
    heading(draw, 'FIENDS N PATRONS / THREE CONDEMNED SOULS',
            'Drei 3D-Entwuerfe mit PBR, gemeinsamem Rig und Nahkampfwaffen. Echte Blender-Eevee-Render.')
    for i, model_id in enumerate(IDS):
        x = i * 512
        folder = OUTPUT / model_id
        with Image.open(folder / 'front.png') as source:
            board.paste(source.convert('RGB').resize((496, 620), Image.Resampling.LANCZOS), (x + 8, 112))
        draw.text((x + 24, 747), NAMES[i], fill=INK, font=ImageFont.load_default(size=23))
        draw.text((x + 24, 784), ROLES[i], fill=MUTED, font=ImageFont.load_default(size=16))
        metadata = json.loads((folder / (model_id + '.json')).read_text())
        draw.text((x + 24, 813), f"{metadata['triangles_before_export']:,} Tris / 23 Bones / 4 Clips".replace(',', '.'), fill=MUTED, font=ImageFont.load_default(size=15))
        for column, view in enumerate(('back', 'topdown')):
            with Image.open(folder / (view + '.png')) as source:
                board.paste(source.convert('RGB').resize((116, 145), Image.Resampling.LANCZOS), (x + 24 + column * 132, 853))
        draw.text((x + 296, 875), 'Hinten + 65 Grad', fill=MUTED, font=ImageFont.load_default(size=15))
        draw.text((x + 296, 904), 'Arbeitsnamen', fill=MUTED, font=ImageFont.load_default(size=15))
        draw.text((x + 296, 933), 'Kein Gameplay-Test', fill=MUTED, font=ImageFont.load_default(size=15))
    board.save(OUTPUT / 'player_models.png', compress_level=3)


def motion_studies():
    frames = []
    for frame in range(0, 24, 3):
        board = Image.new('RGB', (1008, 504), BACKGROUND)
        draw = ImageDraw.Draw(board)
        draw.text((20, 12), 'FIENDS N PATRONS / WALK CYCLE', fill=INK, font=ImageFont.load_default(size=23))
        draw.text((20, 45), 'In-place Animationsblocking aus Blender; noch kein finales Combat-Timing.', fill=MUTED, font=ImageFont.load_default(size=14))
        for i, model_id in enumerate(IDS):
            with Image.open(OUTPUT / model_id / 'motion' / f'walk_{frame:02d}.png') as source:
                board.paste(source.convert('RGB'), (8 + i * 336, 78))
            draw.text((18 + i * 336, 484), NAMES[i], fill=INK, font=ImageFont.load_default(size=15))
        frames.append(board)
    frames[0].save(OUTPUT / 'walk_cycle.gif', save_all=True, append_images=frames[1:], duration=125, loop=0, disposal=2)
    board = Image.new('RGB', (1280, 1130), BACKGROUND)
    draw = ImageDraw.Draw(board)
    heading(draw, 'MELEE / RIG POSE CHECK', 'Fuenf Zeitpunkte pro Figur. Animationen sind visuelles Blocking; Hitbox und Timing bleiben Engine-Daten.')
    for row, model_id in enumerate(IDS):
        for col, frame in enumerate((0, 5, 9, 13, 18)):
            with Image.open(OUTPUT / model_id / 'motion' / f'melee_{frame:02d}.png') as source:
                board.paste(source.convert('RGB').resize((248, 310), Image.Resampling.LANCZOS), (4 + col * 256, 104 + row * 340))
        draw.text((18, 416 + row * 340), NAMES[row], fill=INK, font=ImageFont.load_default(size=16))
    board.save(OUTPUT / 'melee_poses.png', compress_level=3)


def manifest():
    files = []
    for path in sorted(OUTPUT.rglob('*')):
        if not path.is_file() or path.suffix not in ('.glb', '.json', '.png', '.gif') or path.name == 'manifest.json':
            continue
        payload = path.read_bytes()
        files.append({'path': path.relative_to(OUTPUT).as_posix(), 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()})
    sources = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(BASE.iterdir()) if p.suffix in ('.py', '.json', '.md')}
    data = {'schema_version': 1, 'license': 'project_license', 'external_sources': [],
            'provenance': 'Original procedural geometry; shared original procedural PBR textures; no source models or downloaded imagery.',
            'source_sha256': sources, 'local_blend_files': 'Excluded from distributable manifest; ignored local editing conveniences only.', 'files': files}
    (OUTPUT / 'manifest.json').write_text(json.dumps(data, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')


def main():
    for path in OUTPUT.rglob('*.png'):
        clean_png(path)
    overview()
    if all((OUTPUT / mid / 'motion' / 'walk_00.png').is_file() for mid in IDS):
        motion_studies()
    manifest()
    print('Review sheets, clean PNGs and manifest written.')


if __name__ == '__main__':
    main()

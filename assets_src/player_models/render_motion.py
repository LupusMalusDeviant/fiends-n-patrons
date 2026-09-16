"""Render short, in-place rig studies from the local generated Blender files."""

from pathlib import Path

import bpy
from mathutils import Vector

BASE = Path(__file__).resolve().parent


def main():
    for model_id in ('iron_penitent', 'ash_reaver', 'veil_warden'):
        folder = BASE / 'generated' / model_id
        bpy.ops.wm.open_mainfile(filepath=str(folder / (model_id + '.blend')))
        scene = bpy.context.scene
        armature = next(obj for obj in scene.objects if obj.type == 'ARMATURE')
        scene.render.resolution_x, scene.render.resolution_y = 320, 400
        scene.eevee.taa_render_samples = 32
        scene.camera.location = (3, -7, 3.05)
        scene.camera.rotation_euler = (Vector((-.09, 0, 1.09)) - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
        output = folder / 'motion'
        output.mkdir(exist_ok=True)
        for clip, frames in [('walk', range(0, 24, 3)), ('melee', (0, 5, 9, 13, 18))]:
            armature.animation_data.action = bpy.data.actions[clip]
            for frame in frames:
                scene.frame_set(frame)
                scene.render.filepath = str(output / f'{clip}_{frame:02d}.png')
                bpy.ops.render.render(write_still=True)
        print('Motion study rendered:', model_id, flush=True)


if __name__ == '__main__':
    main()

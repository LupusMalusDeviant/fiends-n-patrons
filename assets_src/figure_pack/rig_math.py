"""Small TRS / quaternion helpers for the skeleton axis correction and its self-check.

No `numpy`: every value here is a plain tuple of `float`, matching the byte layout the converter
writes directly (`f32[3]`, `f32[4]` quaternion `x, y, z, w`).
"""

from __future__ import annotations

import math

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]  # (x, y, z, w)
Mat4 = tuple[float, ...]  # 16 floats, column-major (glTF's own storage order)


def quat_multiply(a: Quat, b: Quat) -> Quat:
    """Hamilton product `a (x) b`: as a rotation matrix, `Rot(a) * Rot(b)` (apply `b`, then `a`)."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def quat_conjugate(q: Quat) -> Quat:
    x, y, z, w = q
    return (-x, -y, -z, w)


def quat_rotate_vec3(q: Quat, v: Vec3) -> Vec3:
    """Rotates `v` by `q` via the sandwich product `q * (v, 0) * conj(q)`."""
    vx, vy, vz = v
    rotated = quat_multiply(quat_multiply(q, (vx, vy, vz, 0.0)), quat_conjugate(q))
    return (rotated[0], rotated[1], rotated[2])


def vec3_add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vec3_scale_components(v: Vec3, s: Vec3) -> Vec3:
    return (v[0] * s[0], v[1] * s[1], v[2] * s[2])


# Rotation of +90 degrees about the shared X axis, mapping glTF's Y-up/-Z-forward space onto the
# engine's X-right/Y-forward/Z-up space (`PointLight` doc comment: "X right, Y away from the
# viewer, Z up") -- see the long derivation and the concrete before/after numbers in
# `build_figure_pack.py`'s module docstring and the PR description; this is the ONE place the
# axis correction is applied (contract: "einmal ... nicht doppelt").
_HALF_ANGLE = math.pi / 4.0  # 90 degrees / 2
AXIS_CORRECTION_QUAT: Quat = (math.sin(_HALF_ANGLE), 0.0, 0.0, math.cos(_HALF_ANGLE))


def apply_axis_correction_vec3(v: Vec3) -> Vec3:
    """Direct closed form of rotating `v` by [`AXIS_CORRECTION_QUAT`]: `(x, y, z) -> (x, -z, y)`."""
    x, y, z = v
    return (x, -z, y)


Tangent = tuple[float, float, float, float]  # (x, y, z, w); w is handedness, +-1


def rotate_tangent(tangent: Tangent) -> Tangent:
    """Rotates a tangent's `xyz` by the axis correction, exactly like a normal; `w` (handedness)
    passes through unchanged -- a proper rotation cannot flip handedness.

    This is the literal statement of texturqualitaet-spec.md's "tangent.xyz wird ... um +90 Grad
    um X gedreht wie die Normale, w unveraendert" -- not how the stored `FNP_MESH` payload value is
    produced (that stays the *raw*, unrotated tangent, see `vector_transform`'s docstring: the
    engine rotates it at runtime with the same bone matrices as the normal, so pre-rotating here
    too would double the effect). This function exists for the forward-kinematics self-check's
    expected value and as the direct, standalone statement of the "w unveraendert" rule.
    """
    x, y, z, w = tangent
    rx, ry, rz = apply_axis_correction_vec3((x, y, z))
    return (rx, ry, rz, w)


def correct_root_joint_transform(translation: Vec3, rotation: Quat) -> tuple[Vec3, Quat]:
    """Prepends the axis correction to one skeleton root joint's rest-pose local transform.

    For a rotation-only correction `R` prepended at the very top of a `T * Rot * S` chain,
    `R * (T(t) * Rot(q) * S(s)) = T(R*t) * Rot(q_R (x) q) * S(s)` (translation rotated, rotation
    composed on the left, scale untouched) -- see the PR description for the derivation. Applying
    this to the root joint(s) only, and leaving every other joint's local transform and every
    mesh's raw vertex data untouched, rotates the whole skinned result exactly once: skinning
    computes `sum_j weight_j * jointGlobalTransform_j * invBindMatrix_j * vertexLocal`, and since
    `R` factors out through the forward-kinematics chain, prepending it at the root is
    mathematically identical to rotating the final skinned vertex directly.
    """
    corrected_translation = apply_axis_correction_vec3(translation)
    corrected_rotation = quat_multiply(AXIS_CORRECTION_QUAT, rotation)
    return corrected_translation, corrected_rotation


def compose_trs(
    parent: tuple[Vec3, Quat, Vec3], child: tuple[Vec3, Quat, Vec3]
) -> tuple[Vec3, Quat, Vec3]:
    """Composes a child's local TRS onto its parent's global TRS (standard scene-graph rule).

    Scale is combined component-wise, which ignores shear that a rotated non-uniform scale would
    introduce -- an approximation shared with most real-time skinning implementations, and exact
    here anyway since every joint in the three shipped rigs has a scale within 1e-6 of 1. Used
    only by `build_figure_pack.py`'s forward-kinematics self-check, never for payload bytes.
    """
    t_p, q_p, s_p = parent
    t_c, q_c, s_c = child
    global_translation = vec3_add(t_p, quat_rotate_vec3(q_p, vec3_scale_components(t_c, s_p)))
    global_rotation = quat_multiply(q_p, q_c)
    global_scale = vec3_scale_components(s_p, s_c)
    return global_translation, global_rotation, global_scale


def point_transform(trs: tuple[Vec3, Quat, Vec3], point: Vec3) -> Vec3:
    """Applies a global TRS transform to a point: `t + rotate(q, s * point)`."""
    t, q, s = trs
    return vec3_add(t, quat_rotate_vec3(q, vec3_scale_components(point, s)))


def vector_transform(trs: tuple[Vec3, Quat, Vec3], vector: Vec3) -> Vec3:
    """Applies a global TRS transform to a direction vector: `rotate(q, s * vector)` (no translation).

    Same role as [`point_transform`], but for a direction (a mesh's `TANGENT.xyz`, exactly like its
    `NORMAL`) rather than a position -- translation must not apply to a direction.

    Used only by `build_figure_pack.py`'s forward-kinematics self-check, to prove that storing a
    primitive's raw (unrotated) tangent, exactly like its raw normal, is equivalent to a direct
    `apply_axis_correction_vec3` once the skeleton root's rest-pose transform carries the +90-degree
    correction: at rest pose every joint's `jointGlobalTransform_j (x) invBindMatrix_j` reduces to the
    single correction rotation `R` (see `build_figure_pack.py`'s module docstring and
    `correct_root_joint_transform`), so the weighted sum of `vector_transform(global_trs_j, v)` over
    a vertex's skin weights collapses to `R * v == apply_axis_correction_vec3(v)` -- the same identity
    the existing position check already relies on. The payload therefore stores the tangent raw,
    never pre-rotated: the engine rotates `tangent.xyz` with the same bone matrices as the normal
    (figuren-in-engine-spec.md, Strang B), so rotating it here too would double the effect exactly
    like it would for position (contract: "einmal ... nicht doppelt").
    """
    _t, q, s = trs
    return quat_rotate_vec3(q, vec3_scale_components(vector, s))


def mat4_apply_point(m: Mat4, p: Vec3) -> Vec3:
    """Applies a column-major affine 4x4 matrix to a point (homogeneous w=1).

    Used only by the forward-kinematics self-check in `build_figure_pack.py`, to apply an
    `inverseBindMatrix` exactly as the accessor stores it ("spaltenweise" / column-major, per the
    spec) without transposing anything.
    """
    x, y, z = p
    ow = m[3] * x + m[7] * y + m[11] * z + m[15]
    if abs(ow - 1.0) > 1e-4:
        raise ValueError(f"matrix is not affine (w={ow!r} instead of 1.0)")
    return (
        m[0] * x + m[4] * y + m[8] * z + m[12],
        m[1] * x + m[5] * y + m[9] * z + m[13],
        m[2] * x + m[6] * y + m[10] * z + m[14],
    )


def mat4_apply_vector(m: Mat4, v: Vec3) -> Vec3:
    """Applies a column-major affine 4x4 matrix to a direction vector (homogeneous w=0).

    Same matrix as [`mat4_apply_point`], but drops the translation column -- the linear (3x3) part
    only, as a direction requires. Used by the forward-kinematics self-check to apply an
    `inverseBindMatrix` to a raw `TANGENT.xyz` exactly like `mat4_apply_point` applies it to
    `POSITION`: the tangent must go through the *same* two-step "undo bind pose, then apply current
    pose" skinning formula as the position does, not just the second step -- skipping the inverse
    bind here would silently drop each joint's own bind-pose orientation from the check.
    """
    x, y, z = v
    return (
        m[0] * x + m[4] * y + m[8] * z,
        m[1] * x + m[5] * y + m[9] * z,
        m[2] * x + m[6] * y + m[10] * z,
    )

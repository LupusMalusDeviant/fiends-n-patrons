"""Pure-math core of the character surfaces: skeleton curves, rotation-minimising
frames and cross-section profiles.

No bpy import on purpose -- everything here is plain numpy, so the surface maths
can be exercised and checked without starting Blender.

Conventions (same as the game): X right, Y forward (the direction a character
faces), Z up. A "chain" is a list of control points in world space; it is
resampled into evenly spaced stations, each of which gets a local frame and a
cross-section profile. Lofting a profile along the stations produces a quad
surface with continuous edge loops -- no separate blobs at the joints.
"""
import math

import numpy as np


# --------------------------------------------------------------- curves ---
def catmull_rom(ctrl, n, alpha=0.5):
    """Resample a control polyline into n points on a centripetal Catmull-Rom
    spline. Centripetal (alpha=0.5) never overshoots into a cusp, which matters
    for the sharply bent digitigrade leg and the curled horns."""
    p = np.asarray(ctrl, dtype=np.float64)
    if len(p) < 2:
        raise ValueError("a chain needs at least two control points")
    if len(p) == 2:
        t = np.linspace(0.0, 1.0, n)[:, None]
        return p[0][None, :] * (1 - t) + p[1][None, :] * t
    # Duplicate the end points so the spline passes through the real first/last.
    q = np.vstack([p[0] + (p[0] - p[1]), p, p[-1] + (p[-1] - p[-2])])
    knots = [0.0]
    for i in range(len(q) - 1):
        d = float(np.linalg.norm(q[i + 1] - q[i]))
        knots.append(knots[-1] + max(d, 1e-9) ** alpha)
    knots = np.array(knots)

    def segment(i, u):
        """Barry-Goldman evaluation of the segment between q[i+1] and q[i+2]."""
        t0, t1, t2, t3 = knots[i:i + 4]
        t = t1 + u * (t2 - t1)
        a1 = (t1 - t) / (t1 - t0) * q[i] + (t - t0) / (t1 - t0) * q[i + 1]
        a2 = (t2 - t) / (t2 - t1) * q[i + 1] + (t - t1) / (t2 - t1) * q[i + 2]
        a3 = (t3 - t) / (t3 - t2) * q[i + 2] + (t - t2) / (t3 - t2) * q[i + 3]
        b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
        b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
        return (t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2

    nseg = len(q) - 3
    # Sample densely, then resample by arc length so stations are evenly spaced.
    dense = np.vstack([segment(i, u) for i in range(nseg)
                       for u in np.linspace(0.0, 1.0, 64, endpoint=(i == nseg - 1))])
    return resample_by_length(dense, n)


def resample_by_length(pts, n):
    """Resample a dense polyline to n points spaced evenly along its arc length."""
    pts = np.asarray(pts, dtype=np.float64)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    if s[-1] <= 1e-12:
        return np.repeat(pts[:1], n, axis=0)
    target = np.linspace(0.0, s[-1], n)
    return np.column_stack([np.interp(target, s, pts[:, k]) for k in range(pts.shape[1])])


def arc_length(pts):
    pts = np.asarray(pts, dtype=np.float64)
    return float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())


# --------------------------------------------------------------- frames ---
def _unit(v, fallback=(0.0, 0.0, 1.0)):
    n = float(np.linalg.norm(v))
    return np.asarray(fallback, dtype=np.float64) if n < 1e-12 else np.asarray(v, dtype=np.float64) / n


def tangents(pts):
    """Central-difference tangents, unit length."""
    pts = np.asarray(pts, dtype=np.float64)
    t = np.empty_like(pts)
    t[1:-1] = pts[2:] - pts[:-2]
    t[0] = pts[1] - pts[0]
    t[-1] = pts[-1] - pts[-2]
    return np.array([_unit(v) for v in t])


def frames(pts, up_hint=(0.0, 0.0, 1.0)):
    """Rotation-minimising (parallel transport) frames along a path.

    Returns (tangent, u, v) arrays of shape (n, 3). Parallel transport is what
    keeps a lofted limb from twisting around its own axis -- a Frenet frame flips
    at every inflection point, which is exactly where the elbow and the knee sit.
    """
    pts = np.asarray(pts, dtype=np.float64)
    tg = tangents(pts)
    up = _unit(up_hint)
    # Seed the first normal from the hint, orthogonalised against the tangent.
    seed = up - tg[0] * float(np.dot(up, tg[0]))
    if float(np.linalg.norm(seed)) < 1e-6:
        alt = np.array([1.0, 0.0, 0.0]) if abs(tg[0][0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        seed = alt - tg[0] * float(np.dot(alt, tg[0]))
    u = np.empty_like(pts)
    u[0] = _unit(seed)
    for i in range(1, len(pts)):
        # Double-reflection parallel transport (Wang et al.), numerically stable.
        d = pts[i] - pts[i - 1] if np.linalg.norm(pts[i] - pts[i - 1]) > 1e-12 else tg[i]
        c1 = float(np.dot(d, d))
        if c1 < 1e-18:
            u[i] = u[i - 1]
            continue
        ul = u[i - 1] - (2.0 / c1) * float(np.dot(d, u[i - 1])) * d
        tl = tg[i - 1] - (2.0 / c1) * float(np.dot(d, tg[i - 1])) * d
        d2 = tg[i] - tl
        c2 = float(np.dot(d2, d2))
        u[i] = _unit(ul if c2 < 1e-18 else ul - (2.0 / c2) * float(np.dot(d2, ul)) * d2)
        u[i] = _unit(u[i] - tg[i] * float(np.dot(u[i], tg[i])))
    v = np.cross(tg, u)
    return tg, u, np.array([_unit(x) for x in v])


def aligned_frames(pts, u_hint):
    """Frames whose u axis stays as close as possible to a fixed world direction.

    Used for the torso, where the cross-section's local u must keep pointing at
    the character's right (world +X) all the way up the spine, so the UV seam and
    the shoulder/hip patches land on predictable segments.
    """
    tg = tangents(pts)
    hint = _unit(u_hint)
    u = np.array([_unit(hint - t * float(np.dot(hint, t)), fallback=(1.0, 0.0, 0.0)) for t in tg])
    v = np.array([_unit(np.cross(t, x)) for t, x in zip(tg, u)])
    return tg, u, v


# ------------------------------------------------------------- profiles ---
PROFILE_FIELDS = ("rx", "ry", "power", "rot", "du", "dv", "shear")
PROFILE_DEFAULTS = dict(rx=0.1, ry=0.1, power=2.0, rot=0.0, du=0.0, dv=0.0, shear=0.0)


def profile_key(t, **kw):
    """One keyed cross-section at parameter t in [0, 1] along a chain.

    rx/ry  half-axes in the frame's u/v directions (metres)
    power  superellipse exponent: 2 = ellipse, 4 = rounded square (armour, jaw),
           1.4 = slightly pinched (a lean flank)
    rot    rotation of the section about the tangent (radians)
    du/dv  offset of the section centre inside the frame -- this is how a belly
           is pushed forward or a brow is pushed out without adding geometry
    shear  v-offset proportional to u, tilts the section (sloped shoulders)
    """
    key = dict(PROFILE_DEFAULTS)
    key.update(kw)
    unknown = set(kw) - set(PROFILE_FIELDS)
    if unknown:
        raise ValueError("unknown profile fields: %s" % sorted(unknown))
    key["t"] = float(t)
    return key


def interp_profiles(keys, n):
    """Interpolate keyed cross-sections onto n stations. Returns a dict of arrays."""
    keys = sorted(keys, key=lambda k: k["t"])
    ts = np.array([k["t"] for k in keys], dtype=np.float64)
    out = {}
    target = np.linspace(0.0, 1.0, n)
    for f in PROFILE_FIELDS:
        vals = np.array([float(k[f]) for k in keys], dtype=np.float64)
        out[f] = np.interp(target, ts, vals)
    return out


def superellipse(angles, rx, ry, power):
    """Superellipse points for one cross-section; angles in radians."""
    c, s = np.cos(angles), np.sin(angles)
    e = 2.0 / max(float(power), 0.2)
    x = rx * np.sign(c) * np.abs(c) ** e
    y = ry * np.sign(s) * np.abs(s) ** e
    return x, y


def ring_points(center, u_axis, v_axis, angles, rx, ry, power, rot=0.0, du=0.0, dv=0.0, shear=0.0):
    """World-space points of one cross-section ring."""
    x, y = superellipse(angles + rot, rx, ry, power)
    x = x + du
    y = y + dv + shear * x
    return (np.asarray(center, dtype=np.float64)[None, :]
            + x[:, None] * np.asarray(u_axis, dtype=np.float64)[None, :]
            + y[:, None] * np.asarray(v_axis, dtype=np.float64)[None, :])


def ring_angles(nseg):
    """Segment angles. The half-segment offset puts a vertex pair symmetrically
    left/right of the u axis instead of a single vertex on it, so a centre seam
    in u runs cleanly between two columns."""
    return np.arange(nseg, dtype=np.float64) * (2.0 * math.pi / nseg)


# ------------------------------------------------------------ deformers ---
def smooth_falloff(dist, radius):
    """Smoothstep falloff, 1 at the centre and 0 at radius."""
    t = np.clip(np.asarray(dist, dtype=np.float64) / max(radius, 1e-9), 0.0, 1.0)
    return 1.0 - t * t * (3.0 - 2.0 * t)


def displace_points(pts, center, radius, offset, falloff=smooth_falloff):
    """Move points near `center` by `offset`, with a smooth falloff.

    This is how the chest plate, deltoid, brow and muzzle get their shape: an
    existing edge loop is pushed, never a new blob added.
    """
    pts = np.asarray(pts, dtype=np.float64)
    d = np.linalg.norm(pts - np.asarray(center, dtype=np.float64)[None, :], axis=1)
    w = falloff(d, radius)
    return pts + w[:, None] * np.asarray(offset, dtype=np.float64)[None, :]


def chain_stations(ctrl, n, u_hint=None):
    """Resample a control chain and return (points, tangent, u, v)."""
    pts = catmull_rom(ctrl, n)
    if u_hint is None:
        return (pts,) + frames(pts)
    return (pts,) + aligned_frames(pts, u_hint)

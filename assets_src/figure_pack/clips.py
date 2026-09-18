"""Samples one animation clip of a glTF figure into an `FNP_CLIP` payload (kind `0x8005`).

The format is the engine's, written down in its `docs/formats/figure-clip.md` (version 1) and part
of the crate contract (§6). This module implements the authoring side of that document and nothing
else: it reads the clip's channels, samples them at the rate they were authored at, stores a track
that never changes once, and writes the payload bytes. Playback belongs to the engine
(`grimoire_render::figure_clip`), which decodes exactly these bytes.

What the document demands of a converter, and where it happens here:

- **One reading.** No key reduction, no quantisation: every varying track holds one value per frame
  (`sample_clip`).
- **The time base starts at zero.** The exported GLBs put their first key at `1/24 s`; frame 0 of
  the payload is that first key, so the offset is subtracted here and never shipped (`clip_frames`).
- **Rotations stay unit.** A key is written as it was authored; interpolation between two keys uses
  slerp, which keeps the length at 1. The decoder rejects anything outside `1e-3`, and the encoder
  checks the same bound instead of silently renormalising (`encode_clip`).
- **Markers are zero-based.** The authoring report counts Blender frames from 1; `markers_from_events`
  subtracts one and rejects a marker outside the clip.
- **The skeleton fingerprint** is `StableHasher` v1 over the joint count and every joint's parent,
  re-implemented here (`StableHasher`, `skeleton_fingerprint`) so the converter needs no engine code.
  The engine's own golden fixture pins both against each other (`test_clips.py`).
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Any

from glb_reader import Glb, read_accessor
from rig_math import Quat, Vec3, correct_root_joint_transform

FNP_CLIP = 0x8005
CLIP_MAGIC = b"FNP_CLIP"
CLIP_FORMAT_VERSION = 1

# Limits of the format document, §7.
MAX_CLIP_FRAMES = 4096
MAX_CLIP_MARKERS = 64
MAX_CLIP_MARKER_NAME_LEN = 63
MAX_CLIP_FRAME_RATE_HZ = 1000.0
CLIP_QUATERNION_TOLERANCE = 1e-3

# Header flags (§2.1): bit 0 says the clip loops, every other bit must be zero.
CLIP_FLAG_LOOPS = 1

# Storage bytes of a track (§2.2).
STORAGE_CONSTANT = 0
STORAGE_SAMPLED = 1

# A frame time may differ from `k / rate` by this much before the clip counts as authored at
# another rate. One tenth of a frame at 24 Hz is 4 ms, far above the f32 noise of the key times
# (the measured clips differ by less than 1e-6 s) and far below a real off-rate key.
FRAME_TIME_TOLERANCE = 0.1

# Two frames count as the same pose (loop detection) when every component differs by less than
# this. The authored clips close their loop exactly; this leaves room for a re-export that does not.
LOOP_CLOSE_TOLERANCE = 1e-6

_MIX_CONSTANT = 0x517C_C1B7_2722_0A95
_MASK64 = 0xFFFF_FFFF_FFFF_FFFF


class ClipError(ValueError):
    """The clip cannot be sampled or does not fit the format."""


class StableHasher:
    """`grimoire_core::hash::StableHasher`, algorithm version 1, as far as this module needs it.

    A 64-bit word mixer `state = (state.rotate_left(5) ^ word) * K` over the fed words, finalised
    with SplitMix64 over `state ^ length`. Only the integer writers are implemented: the skeleton
    fingerprint feeds nothing else.
    """

    def __init__(self) -> None:
        self.state = 0
        self.length = 0

    def _mix(self, word: int) -> None:
        rotated = ((self.state << 5) | (self.state >> 59)) & _MASK64
        self.state = ((rotated ^ word) * _MIX_CONSTANT) & _MASK64

    def write_u32(self, value: int) -> None:
        self._mix(value & 0xFFFF_FFFF)
        self.length = (self.length + 4) & _MASK64

    def write_i32(self, value: int) -> None:
        self.write_u32(value & 0xFFFF_FFFF)

    def finish(self) -> int:
        value = (self.state ^ self.length) & _MASK64
        z = (value + 0x9E37_79B9_7F4A_7C15) & _MASK64
        z = ((z ^ (z >> 30)) * 0xBF58_476D_1CE4_E5B9) & _MASK64
        z = ((z ^ (z >> 27)) * 0x94D0_49BB_1331_11EB) & _MASK64
        return z ^ (z >> 31)


def skeleton_fingerprint(joints) -> int:  # joints: list[skeleton.Joint]
    """Format document §4: the joint count, then every joint's parent (`-1` for a root)."""
    hasher = StableHasher()
    hasher.write_u32(len(joints))
    for joint in joints:
        hasher.write_i32(joint.parent)
    return hasher.finish()


def slerp(a: Quat, b: Quat, t: float) -> Quat:
    """Shortest-arc quaternion interpolation (glTF `LINEAR` for rotations)."""
    dot = sum(x * y for x, y in zip(a, b))
    if dot < 0.0:
        b, dot = tuple(-y for y in b), -dot
    if dot > 0.9995:  # almost parallel: linear, then normalise
        mixed = tuple(x + (y - x) * t for x, y in zip(a, b))
    else:
        theta = math.acos(max(-1.0, min(1.0, dot)))
        sin_theta = math.sin(theta)
        wa, wb = math.sin((1.0 - t) * theta) / sin_theta, math.sin(t * theta) / sin_theta
        mixed = tuple(x * wa + y * wb for x, y in zip(a, b))
    length = math.sqrt(sum(value * value for value in mixed)) or 1.0
    return tuple(value / length for value in mixed)


def sample_channel(
    times: list[float], values: list[Any], time: float, *, rotation: bool, step: bool
):
    """The value of one animation sampler at `time`, clamped at both ends."""
    if not times:
        raise ClipError("sampler without keyframes")
    if time <= times[0]:
        return tuple(values[0])
    if time >= times[-1]:
        return tuple(values[-1])
    index = next(i for i in range(1, len(times)) if times[i] >= time)
    if step:  # glTF STEP: the value of the previous keyframe holds until the next one
        return tuple(values[index - 1])
    span = times[index] - times[index - 1]
    t = 0.0 if span <= 0.0 else (time - times[index - 1]) / span
    first, second = tuple(values[index - 1]), tuple(values[index])
    if rotation:
        return slerp(first, second, t)
    return tuple(x + (y - x) * t for x, y in zip(first, second))


@dataclass(frozen=True)
class Marker:
    """One clip marker, already zero-based."""

    frame: int
    name: str


@dataclass
class SampledClip:
    """Every joint's three tracks, frame by frame, ready to encode."""

    name: str
    frame_rate_hz: float
    frame_count: int
    loops: bool
    # Per joint, in skeleton order: a list of `frame_count` values per track.
    translations: list[list[Vec3]]
    rotations: list[list[Quat]]
    scales: list[list[Vec3]]
    # Channels the clip actually drives, for the report.
    animated_joints: int
    varying_tracks: int


def _channels_of(glb: Glb, clip: str) -> dict[int, dict[str, dict[str, Any]]]:
    """Node index -> path -> `{times, values, step}` of the clip's samplers."""
    animations = glb.json_doc.get("animations", [])
    names = [animation.get("name") for animation in animations]
    if clip not in names:
        known = sorted(name for name in names if name)
        raise ClipError(f"clip {clip!r} not in the figure; it has {known}")
    animation = animations[names.index(clip)]
    channels: dict[int, dict[str, dict[str, Any]]] = {}
    for channel in animation.get("channels", []):
        target = channel.get("target", {})
        node, path = target.get("node"), target.get("path")
        if node is None or path not in ("translation", "rotation", "scale"):
            continue
        sampler = animation["samplers"][channel["sampler"]]
        interpolation = sampler.get("interpolation", "LINEAR")
        if interpolation not in ("LINEAR", "STEP"):
            raise ClipError(
                f"clip {clip!r} uses {interpolation} interpolation on node {node}; "
                "only LINEAR and STEP are sampled (format document: one reading, dense samples)"
            )
        channels.setdefault(int(node), {})[path] = {
            "times": [float(value) for value in read_accessor(glb, sampler["input"])],
            "values": read_accessor(glb, sampler["output"]),
            "step": interpolation == "STEP",
        }
    if not channels:
        raise ClipError(f"clip {clip!r} drives no joint transform")
    return channels


def clip_frames(channels: dict[int, dict[str, dict[str, Any]]], rate: float, *, clip: str):
    """The clip's frame times: its first key is frame 0, one frame every `1 / rate` seconds.

    The exported GLBs start at `1 / 24 s` because Blender counts frames from 1. That offset is the
    authoring base and must not reach the payload (format document §3), so it is subtracted here.
    """
    starts = [track["times"][0] for node in channels.values() for track in node.values()]
    ends = [track["times"][-1] for node in channels.values() for track in node.values()]
    start, end = min(starts), max(ends)
    span_frames = (end - start) * rate
    frame_count = int(round(span_frames)) + 1
    if abs(span_frames - round(span_frames)) > FRAME_TIME_TOLERANCE:
        raise ClipError(
            f"clip {clip!r} is {end - start:.6f} s long, which is {span_frames:.3f} frames at "
            f"{rate:g} Hz and not a whole number; sample it at the rate it was authored at"
        )
    if frame_count > MAX_CLIP_FRAMES:
        raise ClipError(f"clip {clip!r} has {frame_count} frames, over the limit of {MAX_CLIP_FRAMES}")
    return start, frame_count


def _f32(values) -> tuple[float, ...]:
    """The values as the payload will store them, so comparisons see what the engine will read."""
    return struct.unpack(f"<{len(values)}f", struct.pack(f"<{len(values)}f", *values))


def _same(first, second, tolerance: float) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(first, second))


def sample_clip(
    glb: Glb,
    skeleton,  # skeleton.SkeletonResult
    skin_nodes: list[int],
    clip: str,
    *,
    frame_rate: float,
) -> SampledClip:
    """Samples `clip` at `frame_rate` into one value per joint, track and frame."""
    if not (0.0 < frame_rate <= MAX_CLIP_FRAME_RATE_HZ) or not math.isfinite(frame_rate):
        raise ClipError(f"frame rate {frame_rate} is not in (0, {MAX_CLIP_FRAME_RATE_HZ:g}]")
    channels = _channels_of(glb, clip)
    start, frame_count = clip_frames(channels, frame_rate, clip=clip)
    node_of_joint = {new: original for original, new in skeleton.original_index_to_new.items()}

    translations: list[list[Vec3]] = []
    rotations: list[list[Quat]] = []
    scales: list[list[Vec3]] = []
    animated_joints = 0
    for index, joint in enumerate(skeleton.joints):
        node = skin_nodes[node_of_joint[index]]
        driven = channels.get(node, {})
        if driven:
            animated_joints += 1
        joint_translations: list[Vec3] = []
        joint_rotations: list[Quat] = []
        joint_scales: list[Vec3] = []
        for frame in range(frame_count):
            time = start + frame / frame_rate
            translation = joint.translation
            rotation = joint.rotation
            scale = joint.scale
            if "translation" in driven:
                track = driven["translation"]
                translation = sample_channel(
                    track["times"], track["values"], time, rotation=False, step=track["step"]
                )
            if "rotation" in driven:
                track = driven["rotation"]
                rotation = sample_channel(
                    track["times"], track["values"], time, rotation=True, step=track["step"]
                )
            if "scale" in driven:
                track = driven["scale"]
                scale = sample_channel(
                    track["times"], track["values"], time, rotation=False, step=track["step"]
                )
            if joint.parent == -1:
                # The rest pose of a root joint carries the pack's axis correction; a sampled pose
                # has to carry the same one, or the figure lies down in the engine.
                translation, rotation = correct_root_joint_transform(translation, rotation)
            joint_translations.append(_f32(translation))
            joint_rotations.append(_f32(rotation))
            joint_scales.append(_f32(scale))
        translations.append(joint_translations)
        rotations.append(joint_rotations)
        scales.append(joint_scales)

    varying = 0
    for tracks in (translations, rotations, scales):
        for frames in tracks:
            if any(frames[0] != value for value in frames[1:]):
                varying += 1
    loops = _closes_its_loop(translations, rotations, scales)
    return SampledClip(
        name=clip,
        frame_rate_hz=frame_rate,
        frame_count=frame_count,
        loops=loops,
        translations=translations,
        rotations=rotations,
        scales=scales,
        animated_joints=animated_joints,
        varying_tracks=varying,
    )


def _closes_its_loop(translations, rotations, scales) -> bool:
    """A clip loops when its last frame repeats its first (format document §3).

    Measured, not configured: the authored `idle` and `walk` close exactly, `death` does not.
    A quaternion and its negation are the same rotation, so both hemispheres count as closed.
    """
    for tracks in (translations, scales):
        for frames in tracks:
            if not _same(frames[0], frames[-1], LOOP_CLOSE_TOLERANCE):
                return False
    for frames in rotations:
        first, last = frames[0], frames[-1]
        flipped = tuple(-value for value in last)
        if not _same(first, last, LOOP_CLOSE_TOLERANCE) and not _same(
            first, flipped, LOOP_CLOSE_TOLERANCE
        ):
            return False
    return True


def markers_from_events(events: dict[str, int], frame_count: int, *, clip: str) -> list[Marker]:
    """Turns the authoring report's `{name: blender_frame}` into zero-based, sorted markers.

    Blender counts frames from 1 and the payload from 0 (format document §2.3), so every frame
    loses one. A marker outside the clip is an error, not a clamped value.
    """
    markers = []
    for name, blender_frame in events.items():
        if not isinstance(blender_frame, int) or isinstance(blender_frame, bool):
            raise ClipError(f"clip {clip!r}: marker {name!r} has frame {blender_frame!r}, not an integer")
        frame = blender_frame - 1
        if not 0 <= frame < frame_count:
            raise ClipError(
                f"clip {clip!r}: marker {name!r} sits at Blender frame {blender_frame}, "
                f"outside the clip's {frame_count} frames"
            )
        name_bytes = name.encode("utf-8")
        if len(name_bytes) > MAX_CLIP_MARKER_NAME_LEN:
            raise ClipError(
                f"clip {clip!r}: marker name {name!r} is {len(name_bytes)} bytes, over the limit "
                f"of {MAX_CLIP_MARKER_NAME_LEN}"
            )
        markers.append(Marker(frame=frame, name=name))
    markers.sort(key=lambda marker: (marker.frame, marker.name))
    if len(markers) > MAX_CLIP_MARKERS:
        raise ClipError(
            f"clip {clip!r}: {len(markers)} markers, over the limit of {MAX_CLIP_MARKERS}"
        )
    return markers


def _encode_track(frames: list[tuple[float, ...]], width: int, *, label: str) -> bytes:
    for value in frames:
        for component in value:
            if not math.isfinite(component):
                raise ClipError(f"{label}: key {value} is not finite")
    constant = all(frames[0] == value for value in frames[1:])
    out = bytearray()
    out.append(STORAGE_CONSTANT if constant else STORAGE_SAMPLED)
    for value in (frames[:1] if constant else frames):
        out += struct.pack(f"<{width}f", *value)
    return bytes(out)


def encode_clip(clip: SampledClip, fingerprint: int, markers: list[Marker], *, label: str) -> bytes:
    """Encodes one `FNP_CLIP` payload, version 1."""
    joint_count = len(clip.translations)
    if joint_count == 0:
        raise ClipError(f"{label}: a clip needs at least one joint")
    if len(markers) > MAX_CLIP_MARKERS:
        raise ClipError(f"{label}: {len(markers)} markers, over the limit of {MAX_CLIP_MARKERS}")
    out = bytearray()
    out += CLIP_MAGIC
    out += struct.pack("<I", CLIP_FORMAT_VERSION)
    out += struct.pack("<I", CLIP_FLAG_LOOPS if clip.loops else 0)
    out += struct.pack("<I", joint_count)
    out += struct.pack("<I", clip.frame_count)
    out += struct.pack("<f", clip.frame_rate_hz)
    out += struct.pack("<Q", fingerprint)
    out += struct.pack("<I", len(markers))
    for index in range(joint_count):
        rotations = clip.rotations[index]
        for frame, rotation in enumerate(rotations):
            length = math.sqrt(sum(value * value for value in rotation))
            if abs(length - 1.0) > CLIP_QUATERNION_TOLERANCE:
                raise ClipError(
                    f"{label}: joint {index}, frame {frame}: rotation {rotation} has length "
                    f"{length:.6f}; the engine rejects anything outside "
                    f"{CLIP_QUATERNION_TOLERANCE:g} and this converter does not renormalise it"
                )
        out += _encode_track(clip.translations[index], 3, label=f"{label}: joint {index} translation")
        out += _encode_track(rotations, 4, label=f"{label}: joint {index} rotation")
        out += _encode_track(clip.scales[index], 3, label=f"{label}: joint {index} scale")
    previous = -1
    for marker in markers:
        if marker.frame < previous:
            raise ClipError(f"{label}: markers are not sorted by frame")
        if not 0 <= marker.frame < clip.frame_count:
            raise ClipError(
                f"{label}: marker {marker.name!r} at frame {marker.frame} is outside the clip"
            )
        previous = marker.frame
        name_bytes = marker.name.encode("utf-8")
        if len(name_bytes) > MAX_CLIP_MARKER_NAME_LEN:
            raise ClipError(f"{label}: marker name {marker.name!r} is too long")
        out += struct.pack("<I", marker.frame)
        out += struct.pack("<B", len(name_bytes))
        out += name_bytes
    return bytes(out)

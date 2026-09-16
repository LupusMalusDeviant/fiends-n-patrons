"""Extracts one glTF skin as a topologically ordered `FNP_SKELETON` joint list.

The payload format (figuren-in-engine-spec.md) requires `parent < self` for every joint so the
engine can evaluate the whole hierarchy in one forward pass; glTF's own `skin.joints` array
happens to already satisfy that for the three shipped rigs, but this module computes its own
order by breadth-first walk from the root(s) instead of trusting that -- and only this module
knows the resulting remap, which every `JOINTS_0` value must go through before it means anything
in the pack's joint index space (see `remap_joint_indices`).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from glb_reader import Glb, GlbError, read_accessor
from rig_math import Mat4, Quat, Vec3, correct_root_joint_transform

MAX_JOINTS = 256
MAX_NAME_BYTES = 63

_DEFAULT_TRANSLATION: Vec3 = (0.0, 0.0, 0.0)
_DEFAULT_ROTATION: Quat = (0.0, 0.0, 0.0, 1.0)
_DEFAULT_SCALE: Vec3 = (1.0, 1.0, 1.0)


class SkeletonError(ValueError):
    """The skin/node graph is structurally invalid or uses an unsupported feature."""


@dataclass(frozen=True)
class Joint:
    """One `FNP_SKELETON` entry, already in the pack's own (topological) order."""

    name: str
    parent: int  # -1 for a root joint, otherwise an index strictly smaller than this joint's own
    inverse_bind: Mat4  # 16 floats, column-major, exactly as the accessor stores it
    translation: Vec3
    rotation: Quat
    scale: Vec3


@dataclass(frozen=True)
class SkeletonResult:
    joints: list[Joint]
    # Maps an index into the *original* `skin.joints` array (what `JOINTS_0` values refer to) to
    # the joint's index in `joints` above.
    original_index_to_new: dict[int, int]


def _node_local_trs(node: dict[str, Any], *, node_index: int) -> tuple[Vec3, Quat, Vec3]:
    if "matrix" in node:
        raise SkeletonError(
            f"node {node_index}: a raw 'matrix' transform is not supported by this converter "
            "(none of the three shipped rigs use one; decompose it upstream in Blender or add "
            "matrix decomposition here before feeding a rig authored this way)"
        )
    translation = tuple(node.get("translation", _DEFAULT_TRANSLATION))
    rotation = tuple(node.get("rotation", _DEFAULT_ROTATION))
    scale = tuple(node.get("scale", _DEFAULT_SCALE))
    if len(translation) != 3 or len(rotation) != 4 or len(scale) != 3:
        raise SkeletonError(f"node {node_index}: malformed translation/rotation/scale")
    return translation, rotation, scale


def build_skeleton(glb: Glb, skin_index: int, *, label: str) -> SkeletonResult:
    """Builds the pack-ready joint list for `glb`'s skin `skin_index`."""
    skins = glb.json_doc.get("skins", [])
    if not (0 <= skin_index < len(skins)):
        raise SkeletonError(f"{label}: skin index {skin_index} out of range")
    skin = skins[skin_index]
    joint_nodes: list[int] = list(skin["joints"])
    if not joint_nodes:
        raise SkeletonError(f"{label}: skin has no joints")
    if len(joint_nodes) > MAX_JOINTS:
        raise SkeletonError(
            f"{label}: skin has {len(joint_nodes)} joints, more than the {MAX_JOINTS} limit"
        )
    joint_node_set = set(joint_nodes)
    if len(joint_node_set) != len(joint_nodes):
        raise SkeletonError(f"{label}: skin.joints lists the same node twice")

    if "inverseBindMatrices" in skin:
        inverse_binds = read_accessor(glb, skin["inverseBindMatrices"])
        if len(inverse_binds) != len(joint_nodes):
            raise SkeletonError(
                f"{label}: {len(inverse_binds)} inverse bind matrices for {len(joint_nodes)} joints"
            )
    else:
        # glTF core spec: an absent inverseBindMatrices accessor means "identity for every joint".
        identity: Mat4 = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
        inverse_binds = [identity] * len(joint_nodes)

    nodes = glb.json_doc.get("nodes", [])
    parent_of: dict[int, int] = {}
    for index, node in enumerate(nodes):
        for child in node.get("children", []):
            if child in parent_of:
                raise SkeletonError(f"{label}: node {child} has more than one parent")
            parent_of[child] = index

    # Parent *within the skin*: the nearest ancestor that is itself one of this skin's joints.
    # (For the three shipped rigs the immediate glTF parent of each root joint is a plain
    # identity-transform container node outside the skin, so this is never exercised beyond one
    # hop -- but a general skin could nest a joint under non-joint helper nodes.)
    def skin_parent(node_index: int) -> int | None:
        current = parent_of.get(node_index)
        while current is not None and current not in joint_node_set:
            current = parent_of.get(current)
        return current

    children_within_skin: dict[int, list[int]] = {node_index: [] for node_index in joint_nodes}
    roots: list[int] = []
    for node_index in joint_nodes:
        parent_node = skin_parent(node_index)
        if parent_node is None:
            roots.append(node_index)
        else:
            children_within_skin[parent_node].append(node_index)
    if not roots:
        raise SkeletonError(f"{label}: skin has a cycle and no root joint")

    # Breadth-first from the roots (in their `skin.joints` order) guarantees parent < child.
    order: list[int] = []
    seen: set[int] = set()
    queue: deque[int] = deque(roots)
    while queue:
        node_index = queue.popleft()
        if node_index in seen:
            raise SkeletonError(f"{label}: joint hierarchy is not a tree (cycle or DAG merge)")
        seen.add(node_index)
        order.append(node_index)
        queue.extend(children_within_skin[node_index])
    if len(order) != len(joint_nodes):
        raise SkeletonError(
            f"{label}: {len(joint_nodes)} joints declared but only {len(order)} reachable from "
            "the root(s) -- the hierarchy is disconnected"
        )

    new_index_of_node = {node_index: i for i, node_index in enumerate(order)}
    original_index_of_node = {node_index: i for i, node_index in enumerate(joint_nodes)}
    original_index_to_new = {
        original_index_of_node[node_index]: new_index_of_node[node_index] for node_index in order
    }

    joints: list[Joint] = []
    for new_index, node_index in enumerate(order):
        node = nodes[node_index]
        name = node.get("name", f"joint_{node_index}")
        name_bytes = name.encode("utf-8")
        if len(name_bytes) > MAX_NAME_BYTES:
            raise SkeletonError(
                f"{label}: joint name {name!r} is {len(name_bytes)} UTF-8 bytes, over the "
                f"{MAX_NAME_BYTES}-byte limit"
            )
        translation, rotation, scale = _node_local_trs(node, node_index=node_index)
        parent_node = skin_parent(node_index)
        if parent_node is None:
            parent_index = -1
            translation, rotation = correct_root_joint_transform(translation, rotation)
        else:
            parent_index = new_index_of_node[parent_node]
            if not (parent_index < new_index):
                raise SkeletonError(
                    f"{label}: internal error, parent index {parent_index} >= own index {new_index}"
                )
        original_index = original_index_of_node[node_index]
        inverse_bind = tuple(inverse_binds[original_index])
        if len(inverse_bind) != 16:
            raise SkeletonError(f"{label}: joint {name!r} inverse bind matrix is not 4x4")
        joints.append(
            Joint(
                name=name,
                parent=parent_index,
                inverse_bind=inverse_bind,
                translation=translation,
                rotation=rotation,
                scale=scale,
            )
        )

    return SkeletonResult(joints=joints, original_index_to_new=original_index_to_new)


def remap_joint_indices(
    joints_0: list[tuple[int, int, int, int]],
    original_index_to_new: dict[int, int],
    *,
    joint_count: int,
    label: str,
) -> list[tuple[int, int, int, int]]:
    """Rewrites raw `JOINTS_0` values (indices into `skin.joints`) into the pack's own order."""
    remapped: list[tuple[int, int, int, int]] = []
    for vertex_index, quad in enumerate(joints_0):
        new_quad = []
        for slot in quad:
            if slot not in original_index_to_new:
                raise SkeletonError(
                    f"{label}: vertex {vertex_index} references joint slot {slot}, which is not "
                    "one of this skin's joints"
                )
            new_value = original_index_to_new[slot]
            if not (0 <= new_value < joint_count):
                raise SkeletonError(
                    f"{label}: vertex {vertex_index} remapped joint index {new_value} is out of "
                    f"range for {joint_count} joints"
                )
            new_quad.append(new_value)
        remapped.append((new_quad[0], new_quad[1], new_quad[2], new_quad[3]))
    return remapped

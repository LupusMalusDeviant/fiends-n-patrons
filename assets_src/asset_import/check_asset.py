#!/usr/bin/env python3
"""Budget gate for imported 3D assets: measures a .glb against the budget of its role.

    python -B check_asset.py --role player [--budgets FILE] [--json-out FILE] <asset.glb>

Checks three layers, in this order:

1. **Engine limits** (grimoire, hard): what the pack decoder or the GPU context would reject at
   load time, reported here instead of as a late engine abort.
2. **Pipeline rules** (figure-pack converter, hard): what the converter needs to accept the file
   (image types, normals, tangents, one skin, triangle lists).
3. **Role budgets and conventions** (`budgets.json`): triangles, vertices, draw parts, joints,
   textures, estimated GPU memory, height, foot level, facing and the expected clip names.

Exit code: 0 if no check failed (warnings allowed), 1 if at least one failed, 2 if the asset or
the budget file could not be read. Standard library only; no Blender, no numpy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from glb_facts import GlbError, measure_glb

REPORT_FORMAT = 1
DEFAULT_BUDGETS = Path(__file__).resolve().parent / "budgets.json"
MIB = 1024 * 1024

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2


class BudgetFileError(ValueError):
    """The budget file is missing, malformed or lacks the requested role."""


@dataclass(frozen=True)
class Check:
    id: str
    status: str  # "pass", "warn", "fail" or "info"
    measured: Any
    limit: Any
    message: str


_ROLE_KEYS = (
    "height_m", "max_triangles", "max_vertices", "max_primitives", "require_skin", "max_joints",
    "max_textures", "max_texture_dimension", "max_gpu_mib", "expect_normal_map", "clips",
)  # fmt: skip
_ENGINE_KEYS = (
    "max_primitive_vertices", "max_primitive_indices", "max_texture_pixels",
    "max_texture_dimension", "max_skin_joints",
)  # fmt: skip
_PIPELINE_KEYS = (
    "accepted_image_types", "front_axis", "foot_level_tolerance_share", "center_tolerance_share",
    "rest_pose_tolerance",
)  # fmt: skip


def load_budgets(path: Path, role: str) -> dict[str, Any]:
    try:
        budgets = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise BudgetFileError(f"cannot read budget file: {error}") from error
    except json.JSONDecodeError as error:
        raise BudgetFileError(f"budget file is not valid JSON: {error}") from error
    if budgets.get("format") != 1:
        raise BudgetFileError(f"unsupported budget file format {budgets.get('format')!r}")
    for section, keys in (("engine", _ENGINE_KEYS), ("pipeline", _PIPELINE_KEYS)):
        missing = [k for k in keys if k not in budgets.get(section, {})]
        if missing:
            raise BudgetFileError(f"budget file section '{section}' lacks {missing}")
    roles = budgets.get("roles", {})
    if role not in roles:
        raise BudgetFileError(f"unknown role '{role}' (budget file defines {sorted(roles)})")
    missing = [k for k in _ROLE_KEYS if k not in roles[role]]
    if missing:
        raise BudgetFileError(f"role '{role}' lacks {missing}")
    return budgets


def evaluate(facts: dict[str, Any], budgets: dict[str, Any], role: str) -> list[Check]:
    """Applies engine limits, pipeline rules and the role budget to measured facts."""
    engine = budgets["engine"]
    pipeline = budgets["pipeline"]
    budget = budgets["roles"][role]
    geometry = facts["geometry"]
    attributes = geometry["attributes"]
    textures = facts["textures"]
    skins = facts["skins"]
    checks: list[Check] = []

    def add(check_id: str, ok: bool, measured: Any, limit: Any, message: str, *, soft="fail"):
        checks.append(Check(check_id, "pass" if ok else soft, measured, limit, message))

    def at_most(check_id: str, measured: int, limit: int, message: str) -> None:
        add(check_id, measured <= limit, measured, limit, message)

    # ---------------------------------------------------------------- engine limits (grimoire)
    at_most("engine.primitive_vertices", geometry["max_primitive_vertices"],
            engine["max_primitive_vertices"], "largest mesh part, vertices (FNP_MESH)")
    at_most("engine.primitive_indices", geometry["max_primitive_indices"],
            engine["max_primitive_indices"], "largest mesh part, indices (FNP_MESH)")
    largest_pixels = max((t.get("pixels", 0) for t in textures), default=0)
    at_most("engine.texture_pixels", largest_pixels, engine["max_texture_pixels"],
            "largest texture, width x height (FNP_TEXTURE_RAW)")
    largest_side = max((max(t.get("width", 0), t.get("height", 0)) for t in textures), default=0)
    at_most("engine.texture_dimension", largest_side, engine["max_texture_dimension"],
            "longest texture side (max_texture_dimension_2d of the software adapter)")
    joints = max((s["joints"] for s in skins), default=0)
    at_most("engine.skin_joints", joints, engine["max_skin_joints"], "joints in the largest skin")
    extra = attributes["JOINTS_1"] != "none" or attributes["WEIGHTS_1"] != "none"
    add("engine.skin_influences", not extra, "JOINTS_1 present" if extra else "JOINTS_0 only",
        "4 per vertex", "the engine vertex carries four joint influences")
    add("engine.triangle_lists", not geometry["non_triangle_modes"],
        geometry["non_triangle_modes"] or "triangles only", "no points or lines",
        "primitive modes other than triangles")

    # ------------------------------------------------------------ pipeline (figure-pack converter)
    unreadable = {
        "sparse_accessors": geometry["sparse_accessors"],
        "extensions_required": facts["extensions_required"],
    }
    add("pipeline.readable", not (geometry["sparse_accessors"] or facts["extensions_required"]),
        unreadable, "none", "sparse accessors and required extensions (Draco, meshopt, KTX2)")
    bad_images = []
    for t in textures:
        label = t.get("name") or f"image {t['image']}"
        if "error" in t:
            bad_images.append(f"{label}: {t['error']}")
        elif t["sniffed_mime_type"] not in pipeline["accepted_image_types"]:
            bad_images.append(f"{label}: {t['sniffed_mime_type']}")
        elif t.get("declared_mime_type") not in (None, t["sniffed_mime_type"]):
            bad_images.append(
                f"{label}: declared {t['declared_mime_type']}, is {t['sniffed_mime_type']}"
            )
    add("pipeline.image_types", not bad_images, bad_images or "all accepted",
        pipeline["accepted_image_types"], "embedded image formats the converter decodes")
    at_most("pipeline.materials", geometry["primitives_without_material"], 0,
            "mesh parts without a material")
    add("pipeline.normals", attributes["NORMAL"] == "all", attributes["NORMAL"], "all",
        "mesh parts with a NORMAL attribute")
    at_most("pipeline.tangent_values", geometry["invalid_tangents"], 0,
            "tangents neither unit length with w = +-1 nor [0, 0, 0, 0] (the converter aborts)")
    at_most("pipeline.tangents", geometry["primitives_with_uv_but_no_tangent"], 0,
            "mesh parts with TEXCOORD_0 but no TANGENT (the converter aborts on these)")
    at_most("pipeline.single_skin", len(skins), 1, "skins used by the scene")

    # ------------------------------------------------------------------------------ role budget
    at_most("budget.triangles", geometry["triangles"], budget["max_triangles"], "triangles drawn")
    at_most("budget.vertices", geometry["vertices"], budget["max_vertices"],
            "vertices after glTF splits (UV seams, hard edges)")
    at_most("budget.primitives", geometry["primitives"], budget["max_primitives"],
            "mesh parts (one draw per part)")
    if budget["require_skin"]:
        add("budget.skin", bool(skins), len(skins), ">= 1", "a rig is required for this role")
    at_most("budget.joints", joints, budget["max_joints"], "joints")
    at_most("budget.textures", len(textures), budget["max_textures"],
            "distinct images used by the materials")
    at_most("budget.texture_dimension", largest_side, budget["max_texture_dimension"],
            "longest texture side")
    texture_bytes = sum(t.get("gpu_bytes_rgba8_with_mips", 0) for t in textures)
    gpu_bytes = texture_bytes + geometry["gpu_mesh_bytes"]
    add("budget.gpu_memory", gpu_bytes <= budget["max_gpu_mib"] * MIB,
        {
            "total_mib": round(gpu_bytes / MIB, 2),
            "textures_mib": round(texture_bytes / MIB, 2),
            "mesh_mib": round(geometry["gpu_mesh_bytes"] / MIB, 2),
        },
        budget["max_gpu_mib"],
        "estimate: RGBA8 textures with full mip chain, 72-byte vertices, u32 indices")
    if budget["expect_normal_map"]:
        has_normal_map = any("normal" in t["slots"] for t in textures)
        add("budget.normal_map", has_normal_map, has_normal_map, True,
            "a normal map carries the surface detail of the high-resolution source", soft="warn")

    clips = budget["clips"]
    names = [a["name"] for a in facts["animations"]]
    missing = [c for c in clips["required"] if c not in names]
    unexpected = [n for n in names if n not in clips["required"] + clips["optional"]]
    add("budget.clips", not missing,
        {"present": len(names), "missing": missing, "unexpected": unexpected},
        {"required": clips["required"]}, "clip names against the expected list of the role",
        soft=clips["severity"])

    # ------------------------------------------------------------------------------ conventions
    bounds = facts["bounds"]
    if bounds is None:
        add("convention.geometry", False, "no mesh in the scene", "at least one mesh", "")
        return checks
    height = bounds["height_y_m"]
    low, high = budget["height_m"]
    add("convention.height", low <= height <= high, round(height, 4), budget["height_m"],
        "height along +Y in metres")
    foot_tolerance = pipeline["foot_level_tolerance_share"] * max(height, 1e-9)
    add("convention.foot_level", abs(bounds["foot_level_y_m"]) <= foot_tolerance,
        round(bounds["foot_level_y_m"], 4), f"|y| <= {foot_tolerance:.4f}",
        "lowest point at the origin (figures stand on y = 0)")
    center_tolerance = pipeline["center_tolerance_share"] * max(height, 1e-9)
    off_center = max(abs(bounds["center_x_m"]), abs(bounds["center_z_m"]))
    add("convention.centered", off_center <= center_tolerance,
        {"x": bounds["center_x_m"], "z": bounds["center_z_m"]}, f"<= {center_tolerance:.4f}",
        "bounding box centred over the origin", soft="warn")

    facing = facts["facing"]
    expected_axis = pipeline["front_axis"]
    if facing["agreement"] == "conflict":
        add("convention.facing", False, facing["candidates"], expected_axis,
            "methods disagree (mirrored joint side names?); confirm with a front render")
    elif facing["axis"] is None:
        add("convention.facing", False, "undetermined", expected_axis,
            "no method could tell the facing; confirm with a front render", soft="warn")
    else:
        add("convention.facing", facing["axis"] == expected_axis,
            f"{facing['axis']} ({facing['agreement']})", expected_axis,
            "direction the character faces")
    for skin in skins:
        error = skin["rest_pose_vs_bind_pose_max_error"]
        add("convention.rest_pose", error <= pipeline["rest_pose_tolerance"], error,
            pipeline["rest_pose_tolerance"], "joint world x inverse bind = identity", soft="warn")

    # ------------------------------------------------------------------------------ information
    odd = [
        t.get("name") or f"image {t['image']}" for t in textures if t.get("power_of_two") is False
    ]
    add("info.texture_power_of_two", not odd, odd or "all", "power-of-two sides",
        "block compression and mip chains stay exact", soft="warn")
    if facts["unused_images"]:
        add("info.unused_images", False, facts["unused_images"], "none",
            "images no material references", soft="info")
    return checks


def build_report(
    facts: dict[str, Any],
    budgets: dict[str, Any],
    budgets_path: Path,
    role: str,
    checks: list[Check],
) -> dict[str, Any]:
    counts = {s: sum(1 for c in checks if c.status == s) for s in ("fail", "warn", "pass", "info")}
    return {
        "report_format": REPORT_FORMAT,
        "asset": facts["file"],
        "role": role,
        "budgets": {
            "file": budgets_path.name,
            "sha256": hashlib.sha256(budgets_path.read_bytes()).hexdigest(),
            "status": budgets.get("status"),
        },
        "verdict": "fail" if counts["fail"] else "pass",
        "counts": counts,
        "checks": [asdict(c) for c in checks],
        "facts": facts,
    }


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:#.4g}" if abs(value) < 1000 else f"{value:,.0f}"
    if isinstance(value, dict):
        return ", ".join(f"{k} {_fmt(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_fmt(v) for v in value) + "]"
    return str(value)


def format_summary(report: dict[str, Any]) -> str:
    facts = report["facts"]
    counts = report["counts"]
    lines = [
        f"asset check: {report['asset']['name']}  role: {report['role']}  "
        f"budgets: {report['budgets']['file']}",
        f"verdict: {report['verdict'].upper()}  "
        f"({counts['fail']} fail, {counts['warn']} warn, {counts['pass']} pass)",
        "",
    ]
    width = max(len(c["id"]) for c in report["checks"])
    for check in report["checks"]:
        lines.append(
            f"  {check['status'].upper():<4}  {check['id']:<{width}}  {_fmt(check['measured'])}"
            f"  (limit {_fmt(check['limit'])})"
        )
    lines.append("")
    for t in facts["textures"]:
        label = f"texture {t['image']}" + (f" {t['name']}" if t.get("name") else "")
        if "error" in t:
            lines.append(f"  {label}: unreadable ({t['error']})")
            continue
        lines.append(
            f"  {label}: {t['sniffed_mime_type']} {t['width']}x{t['height']} {t['channels']}ch, "
            f"slots {','.join(t['slots'])}, file {t['encoded_bytes'] / MIB:.1f} MiB, "
            f"GPU {t['gpu_bytes_rgba8_with_mips'] / MIB:.1f} MiB"
        )
    bounds = facts["bounds"]
    if bounds:
        lines.append(
            f"  bounds ({bounds['space']}): height {bounds['height_y_m']:.3f} m, "
            f"width {bounds['width_x_m']:.3f} m, depth {bounds['depth_z_m']:.3f} m, "
            f"lowest y {bounds['foot_level_y_m']:.3f} m"
        )
    for method in facts["facing"]["methods"]:
        verdict = method.get("axis") or method.get("reason")
        lines.append(f"  facing by {method['method']}: {verdict}")
    if facts["animations"]:
        lines.append("  clips: " + ", ".join(a["name"] for a in facts["animations"]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("asset", type=Path, help="the .glb to check")
    parser.add_argument("--role", required=True, help="budget role: player, enemy, boss or prop")
    parser.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS, help="budget file")
    parser.add_argument("--json-out", type=Path, help="write the full JSON report here")
    parser.add_argument("--quiet", action="store_true", help="print only the verdict line")
    args = parser.parse_args(argv)

    try:
        budgets = load_budgets(args.budgets, args.role)
    except BudgetFileError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_ERROR
    try:
        facts = measure_glb(args.asset)
    except (OSError, GlbError, KeyError, IndexError, TypeError, ValueError) as error:
        print(f"error: {args.asset.name}: {error}", file=sys.stderr)
        return EXIT_ERROR

    checks = evaluate(facts, budgets, args.role)
    report = build_report(facts, budgets, args.budgets, args.role, checks)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        args.json_out.write_text(text, encoding="utf-8")
    summary = format_summary(report)
    print(summary.splitlines()[1] if args.quiet else summary)
    return EXIT_FAIL if report["verdict"] == "fail" else EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())

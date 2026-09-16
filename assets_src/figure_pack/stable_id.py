"""Pure-Python reimplementation of grimoire_core's `StableHasher` and
`grimoire_assets::AssetId::from_path` (algorithm v1).

The engine derives every `AssetId` as a stable 64-bit hash of the asset's path (contract §12,
`grimoire_assets::ids::AssetId::from_path`, grimoire tag v0.1.1). `FNP_FIGURE` payloads embed
those same ids as plain `u64` cross-references (mesh_id/material_id/texture_id/skeleton_id), so
this converter must be able to compute them *before* the Rust pack-writer stage ever runs.

This module is a byte-for-byte translation of `grimoire_core::hash::StableHasher` (algorithm
version 1, frozen by the engine's own golden test) and of `AssetId::from_path`'s domain-separated
construction. It is cross-checked against the real crate by a Rust unit test
(`crates/fnp_content/src/bin/figure_pack_builder.rs`, `asset_id_matches_the_python_reference`)
that hashes the same paths with the actual `grimoire_assets`/`grimoire_core` and asserts equality
with the constants computed here -- see that test before changing anything in this file.
"""

from __future__ import annotations

_MASK64 = (1 << 64) - 1
_MIX_CONSTANT = 0x517C_C1B7_2722_0A95
_ASSET_ID_DOMAIN = "grimoire.asset-id.v1"


def _rotl64(value: int, amount: int) -> int:
    value &= _MASK64
    return ((value << amount) | (value >> (64 - amount))) & _MASK64


def _splitmix64(value: int) -> int:
    z = (value + 0x9E37_79B9_7F4A_7C15) & _MASK64
    z = ((z ^ (z >> 30)) * 0xBF58_476D_1CE4_E5B9) & _MASK64
    z = ((z ^ (z >> 27)) * 0x94D0_49BB_1331_11EB) & _MASK64
    return z ^ (z >> 31)


class StableHasher:
    """Mirrors `grimoire_core::hash::StableHasher` (algorithm version 1) exactly.

    Only the operations this converter actually needs are implemented: `write_u64` and
    `write_str` (the latter via `write_bytes`, length-prefixed exactly like the Rust original).
    """

    def __init__(self, seed: int = 0) -> None:
        self._state = seed & _MASK64
        self._length = 0

    def _mix(self, word: int) -> None:
        self._state = (_rotl64(self._state, 5) ^ (word & _MASK64)) * _MIX_CONSTANT & _MASK64

    def _add_length(self, count: int) -> None:
        self._length = (self._length + count) & _MASK64

    def write_u64(self, value: int) -> None:
        """Feeds one little-endian 64-bit word (also used for `write_usize`, always u64-wide)."""
        self._mix(value)
        self._add_length(8)

    def write_bytes(self, data: bytes) -> None:
        """Length-prefixed raw bytes, matching `StableHasher::write_bytes` exactly.

        The length prefix is mixed (and counted) through `write_u64` first; the payload words are
        only mixed, and the *actual* byte count is added to the length once at the end -- in that
        order, so concatenations of different lengths never collide (contract: see `hash.rs`).
        """
        self.write_u64(len(data))
        offset = 0
        total = len(data)
        while offset + 8 <= total:
            self._mix(int.from_bytes(data[offset : offset + 8], "little"))
            offset += 8
        tail = data[offset:]
        if tail:
            padded = tail + b"\x00" * (8 - len(tail))
            self._mix(int.from_bytes(padded, "little"))
        self._add_length(total)

    def write_str(self, value: str) -> None:
        self.write_bytes(value.encode("utf-8"))

    def finish(self) -> int:
        return _splitmix64(self._state ^ self._length)


def asset_id_for_path(path: str) -> int:
    """Computes the `u64` `AssetId` of `path`, matching `AssetId::from_path` bit-for-bit.

    `path` must already be a valid `AssetPath` (ASCII `[a-z0-9_.-]` and `/`, no leading/trailing
    or empty segments, contract §12); this function does not validate it -- callers build paths
    from figure names and fixed ASCII segments only, so this always holds here.
    """
    hasher = StableHasher()
    hasher.write_str(_ASSET_ID_DOMAIN)
    hasher.write_str(path)
    return hasher.finish()

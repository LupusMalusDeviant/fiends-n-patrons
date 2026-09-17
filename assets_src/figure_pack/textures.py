"""Texture input for the figure pack: size limits, PNG or JPEG decoding, exact downscaling.

Three rules, in the order a texture meets them:

1. **Limits first, from the header alone.** Before any pixel is decoded, every texture's size is
   read from its PNG or JPEG header (`image_headers.py`) and checked against the engine:
   `FNP_TEXTURE_RAW` accepts at most 64 million pixels, and the software adapter the engine tests
   run on creates textures up to 8192 pixels a side. An oversized texture fails the run at once,
   naming the figure, the image, its size and the `--max-texture-size` that would fit, instead of
   after minutes of decoding or as a late engine abort.
2. **Decoding.** PNG goes through the standard-library decoder (`png_decode.py`) as before, so
   figures with PNG textures that need no reduction still pack without any third-party module.
   JPEG is decoded with Pillow (pinned in `../textures/requirements.txt`), greyscale and YCbCr.
3. **Reduction.** A texture whose longer side exceeds `--max-texture-size` is reduced by the power
   of two that fits, with one exact box filter (numpy). The rule is the engine's own mip rule
   (`grimoire_render` `average_texels`): the colour of an sRGB texture is averaged in linear light
   and rounded in sRGB, alpha and linear textures are averaged directly. The arithmetic is
   integer-only: the sRGB curve is a fixed table in units of 2^-24, and a block's code is the
   number of rounding thresholds its exact mean reaches. Every platform gets the same bytes.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from image_headers import ImageHeaderError, read_image_header
from pack_payloads import MAX_TEXTURE_PIXELS
from png_decode import decode_png

# `wgpu` max_texture_dimension_2d of the software adapter the engine tests run on (grimoire_gpu
# context.rs); hardware adapters allow more, but a pack must open everywhere.
MAX_TEXTURE_SIDE = 8192

# sRGB byte -> linear light, times 2^24, rounded (IEC 61966-2-1 curve). A literal table rather than
# the formula, so no platform's `pow` can change a byte of the output; `test_textures.py` compares
# it with the formula.
SRGB_TO_LINEAR_Q24 = (
    0, 5092, 10185, 15277, 20369, 25462, 30554, 35646, 40739, 45831, 50923, 56146, 61682, 67524,
    73676, 80144, 86931, 94043, 101483, 109255, 117364, 125813, 134607, 143749, 153244, 163095,
    173306, 183880, 194821, 206133, 217819, 229883, 242327, 255157, 268373, 281981, 295983, 310382,
    325182, 340386, 355996, 372016, 388449, 405298, 422565, 440255, 458369, 476910, 495881, 515286,
    535127, 555406, 576126, 597291, 618902, 640963, 663476, 686443, 709868, 733752, 758099, 782910,
    808189, 833938, 860159, 886854, 914027, 941680, 969814, 998433, 1027538, 1057133, 1087218,
    1117798, 1148873, 1180447, 1212520, 1245097, 1278179, 1311767, 1345865, 1380475, 1415598,
    1451237, 1487394, 1524071, 1561270, 1598994, 1637244, 1676023, 1715332, 1755173, 1795550,
    1836463, 1877915, 1919907, 1962442, 2005522, 2049149, 2093324, 2138049, 2183328, 2229161,
    2275550, 2322497, 2370005, 2418074, 2466708, 2515908, 2565675, 2616012, 2666920, 2718402,
    2770458, 2823092, 2876304, 2930097, 2984472, 3039432, 3094977, 3151110, 3207832, 3265145,
    3323052, 3381553, 3440650, 3500346, 3560641, 3621538, 3683038, 3745144, 3807855, 3871176,
    3935106, 3999648, 4064803, 4130573, 4196960, 4263965, 4331589, 4399836, 4468706, 4538200,
    4608321, 4679069, 4750448, 4822457, 4895099, 4968376, 5042288, 5116838, 5192027, 5267856,
    5344328, 5421443, 5499204, 5577611, 5656667, 5736372, 5816729, 5897738, 5979402, 6061722,
    6144699, 6228335, 6312631, 6397589, 6483210, 6569496, 6656448, 6744068, 6832357, 6921317,
    7010948, 7101253, 7192233, 7283889, 7376223, 7469237, 7562930, 7657306, 7752366, 7848110,
    7944540, 8041658, 8139465, 8237963, 8337152, 8437035, 8537612, 8638885, 8740855, 8843524,
    8946893, 9050964, 9155737, 9261215, 9367397, 9474287, 9581885, 9690192, 9799210, 9908940,
    10019383, 10130542, 10242416, 10355008, 10468318, 10582349, 10697100, 10812575, 10928773,
    11045697, 11163346, 11281724, 11400831, 11520668, 11641236, 11762538, 11884573, 12007344,
    12130852, 12255098, 12380082, 12505807, 12632274, 12759484, 12887438, 13016137, 13145583,
    13275776, 13406719, 13538412, 13670857, 13804054, 13938006, 14072712, 14208175, 14344396,
    14481375, 14619114, 14757615, 14896878, 15036905, 15177696, 15319253, 15461578, 15604671,
    15748533, 15893166, 16038571, 16184750, 16331702, 16479430, 16627934, 16777216,
)

# Linear light, times 2^24, at which the rounded sRGB code steps from k to k + 1: the curve at
# (k + 0.5) / 255. A mean at or above entry k encodes to at least k + 1, as `round()` does in
# the engine.
SRGB_ROUNDING_THRESHOLDS_Q24 = (
    2546, 7639, 12731, 17823, 22916, 28008, 33100, 38193, 43285, 48377, 53491, 58876, 64564, 70561,
    76870, 83497, 90446, 97721, 105327, 113267, 121545, 130167, 139134, 148452, 158125, 168155,
    178547, 189304, 200431, 211929, 223804, 236057, 248694, 261716, 275128, 288932, 303133, 317732,
    332733, 348140, 363955, 380181, 396821, 413879, 431357, 449258, 467586, 486342, 505529, 525152,
    545211, 565711, 586653, 608041, 629876, 652163, 674902, 698098, 721752, 745867, 770446, 795491,
    821005, 846989, 873447, 900381, 927793, 955687, 984063, 1012925, 1042274, 1072114, 1102446,
    1133273, 1164597, 1196421, 1228746, 1261575, 1294909, 1328752, 1363106, 1397972, 1433353,
    1469251, 1505667, 1542605, 1580066, 1618053, 1656567, 1695611, 1735186, 1775295, 1815939,
    1857121, 1898843, 1941107, 1983914, 2027267, 2071167, 2115618, 2160619, 2206175, 2252285,
    2298953, 2346181, 2393969, 2442321, 2491237, 2540720, 2590772, 2641395, 2692589, 2744358,
    2796703, 2849626, 2903128, 2957212, 3011879, 3067131, 3122970, 3179397, 3236415, 3294024,
    3352228, 3411027, 3470423, 3530418, 3591014, 3652213, 3714015, 3776424, 3839439, 3903064,
    3967300, 4032148, 4097611, 4163689, 4230385, 4297699, 4365635, 4434193, 4503374, 4573182,
    4643616, 4714680, 4786373, 4858699, 4931658, 5005252, 5079483, 5154353, 5229862, 5306012,
    5382805, 5460243, 5538327, 5617058, 5696438, 5776469, 5857152, 5938488, 6020480, 6103128,
    6186434, 6270400, 6355027, 6440316, 6526270, 6612889, 6700175, 6788129, 6876753, 6966048,
    7056016, 7146659, 7237977, 7329972, 7422645, 7515998, 7610033, 7704750, 7800152, 7896239,
    7993013, 8090476, 8188628, 8287471, 8387007, 8487236, 8588161, 8689783, 8792102, 8895121,
    8998841, 9103263, 9208388, 9314218, 9420754, 9527997, 9635949, 9744612, 9853986, 9964072,
    10074873, 10186389, 10298622, 10411573, 10525243, 10639634, 10754747, 10870583, 10987144,
    11104431, 11222444, 11341186, 11460658, 11580861, 11701795, 11823464, 11945867, 12069006,
    12192883, 12317497, 12442852, 12568948, 12695786, 12823368, 12951694, 13080766, 13210586,
    13341154, 13472472, 13604541, 13737361, 13870936, 14005264, 14140349, 14276191, 14412790,
    14550150, 14688269, 14827151, 14966796, 15107205, 15248379, 15390320, 15533028, 15676506,
    15820753, 15965772, 16111564, 16258129, 16405469, 16553585, 16702478,
)


class TextureError(ValueError):
    """A texture cannot be packed: unreadable, too large, or not reducible exactly."""


@dataclass(frozen=True)
class TexturePlan:
    """What happens to one texture: source format and size, and the reduction factor."""

    mime_type: str
    width: int
    height: int
    factor: int

    @property
    def out_width(self) -> int:
        return self.width // self.factor

    @property
    def out_height(self) -> int:
        return self.height // self.factor


def fits_engine(width: int, height: int) -> bool:
    return width * height <= MAX_TEXTURE_PIXELS and max(width, height) <= MAX_TEXTURE_SIDE


def reduction_factor(width: int, height: int, max_size: int | None) -> int:
    """The smallest power of two that brings the longer side to `max_size` or below."""
    factor = 1
    if max_size is not None:
        while max(width, height) // factor > max_size:
            factor *= 2
    return factor


def plan_texture(data: bytes, *, label: str, max_size: int | None = None) -> TexturePlan:
    """Reads the header and decides the reduction; raises `TextureError` if it cannot be packed."""
    if max_size is not None and max_size < 1:
        raise TextureError(f"--max-texture-size must be at least 1, got {max_size}")
    try:
        header = read_image_header(data)
    except ImageHeaderError as error:
        raise TextureError(f"{label}: {error}") from error
    width, height = header.width, header.height
    factor = reduction_factor(width, height, max_size)
    if width % factor or height % factor:
        raise TextureError(
            f"{label}: {width}x{height} cannot be reduced exactly by {factor} to fit "
            f"{max_size} (both sides must be multiples of the factor); resize it upstream"
        )
    plan = TexturePlan(header.mime_type, width, height, factor)
    if not fits_engine(plan.out_width, plan.out_height):
        suggestion = MAX_TEXTURE_SIDE
        while suggestion > 1:
            f = reduction_factor(width, height, suggestion)
            if fits_engine(width // f, height // f):
                break
            suggestion //= 2
        raise TextureError(
            f"{label}: {header.mime_type} {plan.out_width}x{plan.out_height} exceeds the engine "
            f"limits ({MAX_TEXTURE_PIXELS:,} pixels, {MAX_TEXTURE_SIDE} per side); "
            f"pass --max-texture-size {suggestion} or smaller"
        )
    return plan


def decode_texture(data: bytes, plan: TexturePlan, *, srgb: bool, label: str) -> bytes:
    """Decodes a planned texture to RGBA8, top row first, at its output size."""
    if plan.mime_type == "image/png":
        rgba = decode_png(data, label=label).rgba
    elif plan.mime_type == "image/jpeg":
        rgba = _decode_jpeg(data, label=label)
    else:  # pragma: no cover - read_image_header only knows the two
        raise TextureError(f"{label}: unsupported image type {plan.mime_type}")
    if len(rgba) != plan.width * plan.height * 4:
        raise TextureError(f"{label}: decoded pixels do not match the header size")
    if plan.factor == 1:
        return rgba
    np = _numpy(label)
    pixels = np.frombuffer(rgba, dtype=np.uint8).reshape(plan.height, plan.width, 4)
    return box_reduce(pixels, plan.factor, srgb=srgb).tobytes()


def _decode_jpeg(data: bytes, *, label: str) -> bytes:
    try:
        from PIL import Image
    except ImportError as error:  # pragma: no cover - depends on the environment
        raise TextureError(
            f"{label}: JPEG textures need Pillow (assets_src/textures/requirements.txt)"
        ) from error
    with Image.open(io.BytesIO(data)) as image:
        if image.mode not in ("L", "RGB"):
            raise TextureError(f"{label}: JPEG colour mode {image.mode} is not supported (L, RGB)")
        return image.convert("RGBA").tobytes()


def _numpy(label: str):
    try:
        import numpy
    except ImportError as error:  # pragma: no cover - depends on the environment
        raise TextureError(
            f"{label}: reducing textures needs numpy (assets_src/textures/requirements.txt)"
        ) from error
    return numpy


def box_reduce(pixels, factor: int, *, srgb: bool):
    """Reduces an H x W x C uint8 array (C = 3 or 4) by an integer `factor` with one box filter.

    With `srgb` the first three channels are averaged in linear light and rounded in sRGB (the
    engine's mip rule); a fourth channel, and every channel without `srgb`, is averaged directly
    and rounded half up. Integer arithmetic only.
    """
    np = _numpy("box_reduce")
    height, width, channels = pixels.shape
    if factor < 1 or height % factor or width % factor:
        raise TextureError(f"cannot reduce {width}x{height} exactly by {factor}")
    if factor == 1:
        return pixels.copy()
    decode = np.array(SRGB_TO_LINEAR_Q24, dtype=np.int64)
    thresholds = np.array(SRGB_ROUNDING_THRESHOLDS_Q24, dtype=np.int64)
    out_h, out_w, count = height // factor, width // factor, factor * factor
    out = np.empty((out_h, out_w, channels), dtype=np.uint8)
    colour = min(3, channels) if srgb else 0
    for row in range(out_h):
        block = pixels[row * factor : (row + 1) * factor]
        if colour:
            linear = decode[block[..., :colour]]
            sums = linear.reshape(factor, out_w, factor, colour).sum(axis=(0, 2))
            # T <= sum / count  <=>  T <= floor(sum / count), since every threshold is an integer.
            out[row, :, :colour] = np.searchsorted(thresholds, sums // count, side="right")
        if channels > colour:
            plain = block[..., colour:].astype(np.int64)
            sums = plain.reshape(factor, out_w, factor, channels - colour).sum(axis=(0, 2))
            out[row, :, colour:] = (2 * sums + count) // (2 * count)
    return out

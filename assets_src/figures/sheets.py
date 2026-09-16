"""Compose rendered frames into the deliverable sheets (grids and strips).

Plain numpy on uint8 arrays; the images come in through stage.load_png and go
out through palette.write_png, so no image library is needed.
"""
import numpy as np

import palette as P

BG = (10, 11, 15)          # the void colour, so padding reads as background
RULE = (44, 48, 60)        # thin separator


def _canvas(h, w, color=BG):
    a = np.empty((h, w, 3), dtype=np.uint8)
    a[:, :] = np.array(color, dtype=np.uint8)
    return a


def fit(img, w, h):
    """Nearest-neighbour fit of an image into a w x h cell, preserving aspect."""
    ih, iw = img.shape[:2]
    if (ih, iw) == (h, w):
        return img
    scale = min(w / iw, h / ih)
    nw, nh = max(1, int(round(iw * scale))), max(1, int(round(ih * scale)))
    ys = np.clip((np.arange(nh) / scale).astype(int), 0, ih - 1)
    xs = np.clip((np.arange(nw) / scale).astype(int), 0, iw - 1)
    small = img[ys][:, xs]
    out = _canvas(h, w)
    y0, x0 = (h - nh) // 2, (w - nw) // 2
    out[y0:y0 + nh, x0:x0 + nw] = small
    return out


def crop(img, width, height, cx=None, cy=None):
    """Centre crop to width x height around (cx, cy).

    The hero shots are 16:10 landscape with the character in the middle third;
    fitting those whole into a sheet cell wastes most of the canvas on empty
    floor and black bands, so each panel is cropped to the figure first.
    """
    ih, iw = img.shape[:2]
    width, height = min(width, iw), min(height, ih)
    cx = iw // 2 if cx is None else int(cx)
    cy = ih // 2 if cy is None else int(cy)
    x0 = max(0, min(iw - width, cx - width // 2))
    y0 = max(0, min(ih - height, cy - height // 2))
    return img[y0:y0 + height, x0:x0 + width]


def grid(images, cols, rows, out_w, out_h, pad=6, rule=True):
    """Lay images out in a cols x rows grid inside an out_w x out_h canvas."""
    canvas = _canvas(out_h, out_w)
    cell_w = (out_w - pad * (cols + 1)) // cols
    cell_h = (out_h - pad * (rows + 1)) // rows
    for idx, img in enumerate(images[:cols * rows]):
        r, c = divmod(idx, cols)
        x0 = pad + c * (cell_w + pad)
        y0 = pad + r * (cell_h + pad)
        canvas[y0:y0 + cell_h, x0:x0 + cell_w] = fit(img, cell_w, cell_h)
        if rule:
            canvas[y0:y0 + cell_h, x0:x0 + 1] = RULE
            canvas[y0:y0 + 1, x0:x0 + cell_w] = RULE
    return canvas


def strip(images, out_w, out_h, pad=8):
    """One row, used for the asset sheet."""
    return grid(images, len(images), 1, out_w, out_h, pad=pad)


def save(path, arr):
    P.write_png(path, arr)
    return path

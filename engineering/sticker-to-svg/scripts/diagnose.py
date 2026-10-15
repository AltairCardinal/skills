#!/usr/bin/env python3
"""打印各层连通块的面积 / 厚度 / 包围盒，用于定位残留伪影。

用法: python comp_report.py 原图.png [层名...]
"""
import sys
from pathlib import Path

from PIL import ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
import pipeline as T  # noqa: E402


def main(src, only=None):
    im = T.load_rgb(src)
    layers, bg = T.make_layers(im)
    im = im.filter(ImageFilter.GaussianBlur(1.1))
    masks = T.prepare_masks(im, layers, bg, 0)
    for name, col, _fh, _c, _o, mc, _mh in layers:
        if only and name not in only:
            continue
        m = masks[name]
        comps = T.components(m)
        print(f"--- {name}  #{col[0]:02X}{col[1]:02X}{col[2]:02X}  "
              f"共 {len(comps)} 块  min_px={mc}")
        for px, run, bulk, runs in comps[:12]:
            x0 = min(r[1] for r in runs)
            x1 = max(r[2] for r in runs)
            y0 = min(r[0] for r in runs)
            y1 = max(r[0] + 1 for r in runs)
            print(f"    面积={px:8d} run={run:6.1f} bulk={bulk:7.1f} "
                  f"包围盒={x1 - x0}x{y1 - y0} @({x0},{y0})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:] or None)

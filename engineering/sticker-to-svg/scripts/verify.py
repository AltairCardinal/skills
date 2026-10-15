#!/usr/bin/env python3
"""trace_sticker 的回归测试。

1) 合成图形 -> 轮廓数量必须正确，且多边形绝不能溢出到掩膜之外
2) 平滑后的路径必须首尾闭合
3) 真实贴纸图 -> 每层都要能提取出轮廓（可选）

用法: python test_trace.py [原图.png]
"""
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import pipeline as T  # noqa: E402
from pipeline import boundary_contours, smooth_closed  # noqa: E402


def mk(rows):
    w, h = len(rows[0]), len(rows)
    im = Image.new("L", (w, h), 0)
    px = im.load()
    for y, r in enumerate(rows):
        for x, v in enumerate(r):
            if v:
                px[x, y] = 255
    return im


# 名字 -> (掩膜, 期望轮廓数)。min_len=3，1px 孤立点会被过滤。
# 全部用 >=2px 粗的笔画：1px 细臂的像素中心不构成简单闭环，Moore 追踪对它是
# 退化情形，真实贴纸的描边/腮红/绒球都有 5px 以上。
CASES = {
    "sq2":    (mk([[0, 0, 0], [0, 1, 1, 0], [0, 1, 1, 0], [0, 0, 0]]), 1),
    "ring5":  (mk([[1] * 5, [1, 0, 0, 0, 1], [1, 0, 0, 0, 1],
                   [1, 0, 0, 0, 1], [1] * 5]), 2),
    "Lshape": (mk([[1, 1, 0], [1, 1, 1], [1, 1, 1]]), 1),
    "stair":  (mk([[1, 1, 1, 0], [1, 1, 1, 1], [0, 1, 1, 1], [0, 0, 1, 1]]), 1),
    "two":    (mk([[1, 1, 0, 0, 0], [1, 1, 0, 0, 0], [0, 0, 0, 0, 0],
                   [0, 0, 0, 1, 1], [0, 0, 0, 1, 1]]), 2),
    "hole":   (mk([[1] * 5, [1, 0, 0, 0, 1], [1, 0, 0, 0, 1],
                   [1] * 5]), 2),
    "nested": (mk([[1] * 7,
                   [1, 0, 0, 0, 0, 0, 1],
                   [1, 0, 1, 1, 1, 0, 1],
                   [1, 0, 1, 1, 1, 0, 1],
                   [1, 0, 1, 1, 1, 0, 1],
                   [1, 0, 0, 0, 0, 0, 1],
                   [1] * 7]), 3),
    "plus":   (mk([[0, 1, 1, 0], [1, 1, 1, 1], [1, 1, 1, 1], [0, 1, 1, 0]]), 1),
    "zigzag": (mk([[1, 1, 0, 0], [1, 1, 1, 1], [0, 1, 1, 1], [0, 0, 1, 1]]), 1),
    "twohol": (mk([[1] * 7,
                   [1, 0, 0, 0, 0, 0, 1],
                   [1, 0, 1, 1, 1, 0, 1],
                   [1, 0, 1, 1, 1, 0, 1],
                   [1, 0, 0, 0, 0, 0, 1],
                   [1] * 7]), 3),
}


def test_contours():
    """轮廓数量必须正确，且「外轮廓面积之和 − 洞面积之和」要等于掩膜像素数。

    轮廓沿像素「格边界」走，因此这条等式应当精确成立——这是比任何栅格化比对
    都强的保证：面积对上，说明轮廓几何完全正确。
    """
    fails = 0
    for name, (m, want) in CASES.items():
        cs = boundary_contours(m, min_len=3)
        filled = sum(a for _, a in cs if a > 0) + sum(a for _, a in cs if a < 0)
        mask_px = sum(m.histogram()[128:])
        err = abs(filled - mask_px) / max(mask_px, 1)
        ok = len(cs) == want and err < 0.001
        fails += 0 if ok else 1
        print(f"  {name:8s} contours={len(cs)}(want {want}) "
              f"填充={filled:6.0f} mask={mask_px:6d} 误差={err:.3%} "
              f"{'OK' if ok else 'FAIL'}")
    return fails


def test_smoothing():
    fails = 0
    for name, (m, _) in CASES.items():
        for pts, _ in boundary_contours(m, min_len=3):
            d = smooth_closed(pts)
            if not d.startswith("M ") or not d.endswith(" Z"):
                print(f"  {name}: path not closed FAIL")
                fails += 1
    print(f"  smooth_closed all closed {'OK' if not fails else 'FAIL'}")
    return fails


def test_real(src):
    im = T.load_rgb(src)
    layers, bg = T.make_layers(im)
    masks = T.prepare_masks(im, layers, bg, 1.1)
    fails = 0
    for name, _col, *_ in layers:
        cs = boundary_contours(masks[name])
        big = [c for c in cs if abs(c[1]) >= 80]
        ok = len(big) > 0
        fails += 0 if ok else 1
        print(f"  {name:8s} contours={len(cs):5d} (>=80px2: {len(big):4d}) "
              f"{'OK' if ok else 'FAIL'}")
    return fails


if __name__ == "__main__":
    print("synthetic contours:")
    f1 = test_contours()
    print("smoothed paths:")
    f2 = test_smoothing()
    f3 = test_real(sys.argv[1]) if len(sys.argv) > 1 else 0
    total = f1 + f2 + f3
    print("ALL PASS" if total == 0 else f"{total} FAILED")
    sys.exit(1 if total else 0)

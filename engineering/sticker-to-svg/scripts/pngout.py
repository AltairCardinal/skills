#!/usr/bin/env python3
"""把 SVG 渲染成带透明通道的 PNG。

浏览器无头截图会铺白底，这里再把白底转成 alpha=0，产出可直接叠加使用的贴纸图。

用法: python export_png.py 矢量.svg 输出.png [边长]
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not Path(EDGE).exists():
    EDGE = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"


def render_pair(svg: Path, w: int, h: int, bg: str) -> Image.Image:
    """在指定纯色背景上渲染 SVG，返回 RGB。"""
    html = (
        "<!doctype html><meta charset='utf-8'>"
        f"<style>html,body{{margin:0;padding:0;background:{bg}}}"
        "svg{display:block}</style>" + svg.read_text(encoding="utf-8")
    )
    page = Path(tempfile.gettempdir()) / "_sticker_page.html"
    page.write_text(html, encoding="utf-8")
    out = Path(tempfile.gettempdir()) / f"_sticker_{bg[1:]}.png"
    if out.exists():
        out.unlink()
    for i in range(10):
        subprocess.run([
            EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", "--hide-scrollbars",
            f"--user-data-dir={tempfile.gettempdir()}\\edge-exp-{bg[1:]}-{i}",
            f"--window-size={w},{h}", f"--screenshot={out}",
            f"file:///{page.as_posix()}?v={i}-{w}-{h}-{i * 17}",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if out.exists() and out.stat().st_size > 1000:
            return Image.open(out).convert("RGB")
    raise RuntimeError("render failed")


def matte_alpha(white_rgb, black_rgb):
    """从白底/黑底两次渲染提取带抗锯齿的 alpha。

    直接用「接近白即透明」的硬阈值抠图，边缘必然锯齿、在深色背景上还会露出
    一圈白毛边。标准做法是设前景本色 C、覆盖率 a、背景 B：
        白底: I_W = a·C + (1-a)·255
        黑底: I_B = a·C
    相减得 a = 1 - (I_W - I_B)/255，再由 I_B/a 反解 C。
    """
    w, h = white_rgb.size
    blk, wht = black_rgb.load(), white_rgb.load()
    out = Image.new("RGBA", (w, h))
    dp = out.load()
    for y in range(h):
        for x in range(w):
            wr, wg, wb = wht[x, y]
            br, bg_, bb = blk[x, y]
            a = ((255 - (wr - br)) + (255 - (wg - bg_))
                 + (255 - (wb - bb))) // 3
            if a <= 2:
                dp[x, y] = (255, 255, 255, 0)
            else:
                dp[x, y] = (min(255, br * 255 // a),
                            min(255, bg_ * 255 // a),
                            min(255, bb * 255 // a),
                            min(255, a))
    return out


def fit_square(png_p, size):
    """等比缩放到 size 后居中补成正方形透明画布（不要直接拉伸，会变形）。"""
    im = Image.open(png_p).convert("RGBA")
    s = min(size / im.width, size / im.height)
    nw, nh = max(1, round(im.width * s)), max(1, round(im.height * s))
    im = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    canvas.paste(im, ((size - nw) // 2, (size - nh) // 2), im)
    canvas.save(png_p)


def export(svg_p, png_p, size=None):
    """SVG -> 带抗锯齿透明底的 PNG。"""
    svg_p, png_p = Path(svg_p), Path(png_p)
    head = svg_p.read_text(encoding="utf-8")[:400]
    import re
    vb = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"', head)
    w, h = int(float(vb.group(3))), int(float(vb.group(4)))
    on_white = render_pair(svg_p, w, h, "#ffffff")
    on_black = render_pair(svg_p, w, h, "#000000")
    img = matte_alpha(on_white, on_black)
    img.save(png_p)
    if size:
        fit_square(png_p, size)
    return w, h


def main(svg_p, png_p, size=None):
    w, h = export(svg_p, png_p, size)
    print(f"{png_p}  {w}x{h}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1], sys.argv[2],
         int(sys.argv[3]) if len(sys.argv) > 3 else None)

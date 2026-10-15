#!/usr/bin/env python3
"""
贴纸位图 -> 矢量 SVG + 透明 PNG 一条龙。

    python sticker2svg.py 输入.png                 # 输出 <名>.svg / <名>.png / <名>-compare.png
    python sticker2svg.py 输入.png -o out --both   # 同时输出「含模切边」「无模切边」两套
    python sticker2svg.py 输入.png --no-paper      # 只要无模切边版本
    python sticker2svg.py 输入.png --report        # 附带色板与各层连通块诊断报告
    python sticker2svg.py --selftest               # 轮廓提取回归自检（不需要输入图）

依赖：Pillow；PNG 导出需要一个 Chromium 系浏览器（默认找 Edge）。

设计要点（踩过的坑都在这）：
  * 色板从图中自动提取，不写死——不同贴纸的同名字色可以差很多。
  * 用「最近色」分类，边界落在两色 50% 混合点，也就是描边的几何中线；
    任何固定阈值都会把描边撑粗或削薄。
  * 边界轮廓沿「像素格边界」走，不是像素中心——细线网络（描边）上稳得多。
  * PNG 用黑白双渲染 matte 提取 alpha，边缘抗锯齿，深色背景下不出白毛边。
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pipeline  # noqa: E402
import pngout    # noqa: E402


# --------------------------------------------------------------------------

def build_one(src: Path, outdir: Path, name: str, *, eps, blur, size,
              skip_paper, report):
    im = pipeline.load_rgb(src)
    layers, bg = pipeline.make_layers(im)
    masks = pipeline.prepare_masks(im, layers, bg, blur)

    off = (0, 0)
    bbox = masks["paper"].getbbox()
    if bbox:
        im = im.crop(bbox)
        masks = {k: v.crop(bbox) for k, v in masks.items()}
        off = (bbox[0], bbox[1])

    svg, stats = pipeline.build_svg(
        masks, layers, im.size, off, eps, name, smooth=False,
        skip_paper=skip_paper)
    svg_path = outdir / f"{name}.svg"
    svg_path.write_text(svg, encoding="utf-8")

    png_path = outdir / f"{name}.png"
    pngout.export(svg_path, png_path, size)

    print(f"  {name}.svg   {im.size[0]}x{im.size[1]}  [{stats}]")
    print(f"  {name}.png   {size}x{size} 透明底")
    return svg_path, png_path, layers, bg, masks, off


def compare_strip(src: Path, png_path: Path, out_path: Path, scale=3):
    """原图 | 矢量(铺白底) | 50% 叠加"""
    from PIL import Image
    a = Image.open(src).convert("RGB")
    b = Image.open(png_path).convert("RGBA")
    flat = Image.new("RGBA", b.size, (255, 255, 255, 255))
    b = Image.alpha_composite(flat, b).convert("RGB")
    if b.size != a.size:
        b = b.resize(a.size, Image.LANCZOS)
    h = max(a.size[1], b.size[1])
    canvas = Image.new("RGB", (a.size[0] * 2 + 20, h * 2 + 20), (255, 255, 255))
    canvas.paste(a, (0, 0))
    canvas.paste(b, (a.size[0] + 20, 0))
    canvas.paste(Image.blend(a, b, 0.5), (0, h + 20))
    canvas.resize((canvas.width // scale, canvas.height // scale),
                  Image.LANCZOS).save(out_path)
    print(f"  {out_path.name}   对照图（原图 | 矢量 | 叠加）")


def write_report(outdir: Path, name: str, src, layers, bg, masks, off):
    lines = [f"源图: {src}", f"画布偏移: {off}",
             f"背景色: #{bg[0]:02X}{bg[1]:02X}{bg[2]:02X}", ""]
    for lname, col, *_ in layers:
        px = sum(masks[lname].histogram()[128:])
        lines.append(f"层 {lname:8s} #{col[0]:02X}{col[1]:02X}{col[2]:02X} "
                     f"像素 {px}")
        for cpx, run, bulk, runs in pipeline.components(masks[lname])[:8]:
            x0 = min(r[1] for r in runs)
            x1 = max(r[2] for r in runs)
            y0 = min(r[0] for r in runs)
            y1 = max(r[0] + 1 for r in runs)
            lines.append(f"      面积={cpx:8d} run={run:6.1f} bulk={bulk:7.1f} "
                         f"包围盒={x1 - x0}x{y1 - y0}")
    p = outdir / f"{name}-report.txt"
    p.write_text("\n".join(lines), encoding="utf-8")
    print(f"  {p.name}   诊断报告")


def selftest():
    """跑轮廓提取回归自检（合成图形 -> 轮廓数 / 面积恒等式）。"""
    return subprocess.run([sys.executable, str(HERE / "verify.py")]).returncode


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="贴纸位图 -> 矢量 SVG + 透明 PNG",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", help="输入 PNG/JPG")
    ap.add_argument("-o", "--outdir", help="输出目录（默认与输入同目录）")
    ap.add_argument("-n", "--name", help="输出文件名主干（默认取输入文件名）")
    ap.add_argument("--eps", type=float, default=1.2,
                    help="轮廓简化容差，像素（默认 1.2，约 0.07%% 图宽）")
    ap.add_argument("--blur", type=float, default=1.1,
                    help="分类前的高斯模糊半径（默认 1.1）")
    ap.add_argument("--size", type=int, default=1024, help="导出 PNG 边长")
    ap.add_argument("--no-paper", action="store_true",
                    help="不画米白模切纸边，只保留主体（深色背景更干净）")
    ap.add_argument("--both", action="store_true",
                    help="同时输出含纸边与无纸边两套")
    ap.add_argument("--report", action="store_true", help="附带诊断报告")
    ap.add_argument("--no-compare", action="store_true", help="不生成对照图")
    ap.add_argument("--selftest", action="store_true",
                    help="跑轮廓提取回归自检并退出")
    a = ap.parse_args()

    if a.selftest:
        return 0 if selftest() == 0 else 1
    if not a.input:
        ap.error("需要输入图片（或用 --selftest）")

    src = Path(a.input)
    if not src.exists():
        print(f"找不到文件: {src}", file=sys.stderr)
        return 2
    outdir = Path(a.outdir) if a.outdir else src.parent
    outdir.mkdir(parents=True, exist_ok=True)
    base = a.name or src.stem

    print(f"处理 {src}")
    variants = []
    if a.both or not a.no_paper:
        variants.append((base, False))
    if a.both or a.no_paper:
        variants.append((base + "-nopaper", True))

    first = None
    for name, skip_paper in variants:
        svg_path, png_path, layers, bg, masks, off = build_one(
            src, outdir, name, eps=a.eps, blur=a.blur, size=a.size,
            skip_paper=skip_paper, report=a.report)
        if first is None:
            first = (svg_path, png_path, layers, bg, masks, off)

    if not a.no_compare:
        compare_strip(src, first[1], outdir / f"{base}-compare.png")

    if a.report:
        write_report(outdir, base, src, first[2], first[3], first[4], first[5])

    return 0


if __name__ == "__main__":
    sys.exit(main())

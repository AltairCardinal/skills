#!/usr/bin/env python3
"""
把一张扁平色贴纸位图重建成「颜色区域」矢量 SVG。

思路（从像素重建轮廓，而不是目测描线）：
  1. 按颜色把像素分类：白底 / 黄 / 棕 / 腮红 / 粉
     - 阈值作用在 1px 高斯模糊后的图上 -> 边界亚像素准确
     - 棕色阈值放宽到 mx<=236，把棕线与米白边的抗锯齿过渡带也吃进去
  2. 按行扫描前景游程 -> 沿像素格边缘收集有向边 -> 串成闭合轮廓（含洞）
  3. RDP 简化 + 保角平滑（明显转角保留为直线，其余 Catmull-Rom 转贝塞尔）
  4. 图层顺序：米白(整体外轮廓) -> 黄 -> 粉 -> 腮红 -> 棕(最后)
     棕色最后画，环线与孤立小块（眼睛/鼻孔）一次搞定，不会被粉盖住

用法:
  python trace_sticker.py 输入.png 输出.svg [--eps 1.0] [--crop] [--debug d.png]
"""

import argparse
import math
import sys
from collections import defaultdict

from PIL import Image, ImageChops, ImageFilter


# 色板不写死：两张贴纸的粉分别是 (253,225,222) 与 (253,231,223)，腮红也差
# (243,169,168) vs (245,182,182)。一律由 derive_palette() 从图中自动提取。
# 分类采用「最近色」而非逐层手调阈值——棕线与粉之间的抗锯齿过渡带超过 20px，
# 任何单一阈值都会把描边撑粗；最近色让边界落在两色的 50% 混合点上，
# 也就是描边的几何中线。


def _thr(src, lo=None, hi=None):
    """[lo,hi) 区间取 255，区间外取 0。"""
    if lo is not None and hi is None:
        lut = [0] * lo + [255] * (256 - lo)
    elif lo is None and hi is not None:
        lut = [255] * hi + [0] * (256 - hi)
    else:
        lut = [255] * lo + [0] * (hi - lo) + [255] * (256 - hi)
    return src.point(lut)


def _and(*imgs):
    out = imgs[0]
    for i in imgs[1:]:
        out = ImageChops.multiply(out, i)
    return out


def _not(img):
    return ImageChops.invert(img)


def classify(im):
    """按 RGB 最近色分类，返回 {类名: 'L' 掩膜}。

    用曼哈顿(L1)距离而非欧氏(L2)：L2 要缩 10 位才能塞进 8 位累加，那样
    (3,21,20) 这种米白/粉的微小差异会被直接抹成 0 而误判。L1 每通道先 >>2，
    三通道最大 189，不溢出且差异分辨得开。
    """
    R, G, B = im.split()
    size = im.size

    def dist(r0, g0, b0):
        dr = R.point([abs(v - r0) >> 2 for v in range(256)])
        dg = G.point([abs(v - g0) >> 2 for v in range(256)])
        db = B.point([abs(v - b0) >> 2 for v in range(256)])
        return ImageChops.add(ImageChops.add(dr, dg), db)

    label = None
    best = None
    for idx, (name, (r0, g0, b0)) in enumerate(PALETTE):
        d = dist(r0, g0, b0)
        if best is None:
            best = d
            label = Image.new("L", size, idx)
            continue
        closer = ImageChops.subtract(best, d).point(
            lambda v: 255 if v > 0 else 0)
        label = Image.composite(Image.new("L", size, idx), label, closer)
        best = ImageChops.darker(best, d)

    out = {}
    for idx, (name, _c) in enumerate(PALETTE):
        out[name] = label.point([255 if v == idx else 0 for v in range(256)])
    # 贴纸外形 = 所有非背景像素（含裁切线与内部），后续 fill_holes 会填实
    out["paper"] = _not(out["white"])
    return out


# --------------------------------------------------------------------------
# 轮廓游走
# --------------------------------------------------------------------------

def de_pinch(mask, max_iter=12):
    """补实「对角相接」的夹点，迭代到稳定为止。

    2x2 窗口里只有对角两格为前景时，四条边会在同一个格点相遇，串接时无法判断
    该接哪一条，会拉出横穿整幅图的假线段。补掉一个背景格即可消除歧义，而补完
    又可能形成新的夹点，所以要反复迭代。

    注意 ImageChops.offset(im, dx, dy) 的语义是 result(x,y) = im(x-dx, y-dy)，
    所以「取右邻/下邻/右下邻」要用负偏移。
    """
    w, h = mask.size
    pad = Image.new("L", (w + 4, h + 4), 0)
    pad.paste(mask, (2, 2))
    off = ImageChops.offset

    for _ in range(max_iter):
        m = pad
        p10 = off(m, -1, 0)      # mask(x+1, y)
        p01 = off(m, 0, -1)      # mask(x, y+1)
        p11 = off(m, -1, -1)     # mask(x+1, y+1)
        # 主对角为前景、反对角为空 -> 补 p01
        pinch1 = ImageChops.multiply(
            ImageChops.multiply(m, p11),
            ImageChops.invert(ImageChops.lighter(p10, p01)))
        # 反对角为前景、主对角为空 -> 补 p00
        pinch2 = ImageChops.multiply(
            ImageChops.multiply(p10, p01),
            ImageChops.invert(ImageChops.lighter(m, p11)))
        nxt = ImageChops.lighter(
            m, ImageChops.lighter(pinch2, off(pinch1, 0, -1)))
        if nxt.tobytes() == pad.tobytes():
            break
        pad = nxt
    return pad.crop((2, 2, w + 2, h + 2))


def _row_runs(px, w, h):
    runs = []
    for y in range(h):
        row = px[y * w:(y + 1) * w]
        rs = []
        i = row.find(b"\xff")
        while i >= 0:
            j = row.find(b"\x00", i)
            if j < 0:
                j = w
            rs.append((i, j))
            i = row.find(b"\xff", j)
        runs.append(rs)
    return runs


def _subtract(runs, other):
    """区间集合差: runs \\ other"""
    out = []
    for a, b in runs:
        cur = a
        for c, d in other:
            if d <= cur or c >= b:
                continue
            if c > cur:
                out.append((cur, min(c, b)))
            cur = max(cur, d)
            if cur >= b:
                break
        if cur < b:
            out.append((cur, b))
    return out


# Moore 邻域，从正西开始顺时针（屏幕坐标 y 向下，故「顺时针」对应此顺序）
_NB = ((-1, 0), (-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1))

# 每次 boundary_contours 调用后，这里记录追踪质量
TRACE_STATS = {"open": 0, "open_pts": 0, "runaway": 0, "cap": 40000}


def _moore(px, w, h, sx, sy, fg):
    """从 (sx,sy) 做 Moore 邻域追踪，返回若干条闭合轮廓（像素中心点列）。

    起点必须是该连通块光栅序最靠上/左的像素——这是「绕一圈回到起点即闭合」能
    成立的前提。

    回溯点必须取「顺时针扫过的最后一个背景邻居」，且下一轮扫描要从回溯点本身
    开始（它必定是背景）：用 (i-1)%8 而那个方向仍是前景时，扫描会从前景起步、
    整段边界被跳过；从回溯点之后开始时，遇到「除目标外全是前景」又找不到回溯点。

    轮廓自接触（像素中心上出现 8 连通夹点）时，单条简单环不存在，追踪会在重访
    点处分裂成多个闭环——这里如实切分，而不是截断。

    断头/超时的残弧会被丢弃，并记入 TRACE_STATS 供调用方判断质量。
    """
    start = (sx, sy)
    d = None
    for i, (dx, dy) in enumerate(_NB):
        if not fg(sx + dx, sy + dy):
            d = i
            break
    if d is None:
        return [[start]]                      # 孤立像素

    out = []
    contour = [start]
    pos = {start: 0}          # 当前环：点 -> 下标，切分时 O(1)
    used = {start}             # 整个连通块：像素只能归属一条环
    b = start
    guard = 0
    limit = TRACE_STATS["cap"]
    while guard < limit:
        guard += 1
        nb = None
        for k in range(0, 9):
            i = (d + k) % 8
            nx, ny = b[0] + _NB[i][0], b[1] + _NB[i][1]
            if fg(nx, ny):
                bb = (i - 1) % 8
                for _ in range(8):
                    if not fg(b[0] + _NB[bb][0], b[1] + _NB[bb][1]):
                        break
                    bb = (bb - 1) % 8
                d = bb
                nb = (nx, ny)
                break
        if nb is None:
            break
        if nb not in used:
            b = nb
            contour.append(nb)
            pos[nb] = len(contour) - 1
            used.add(nb)
            continue
        if nb not in pos:
            break                  # 落到此前某条环上，本环结束
        piece = contour[pos[nb]:]
        if len(piece) >= 3:
            out.append(piece)      # 自接触：在此切分收口
        if nb == start:
            contour = []
            break
        contour = [nb]
        pos = {nb: 0}
        b = nb
    if len(contour) >= 3:
        # 只有首尾 8 邻接才算闭合环；断头/超时的残弧必须丢弃，否则会拉出
        # 横跨全图的假边
        fx, fy = contour[0]
        lx, ly = contour[-1]
        if abs(fx - lx) <= 1 and abs(fy - ly) <= 1:
            out.append(contour)
        else:
            # 断头或撞上步数上限的残弧，丢弃并计数
            TRACE_STATS["open"] += 1
            TRACE_STATS["open_pts"] += len(contour)
            if guard >= limit:
                TRACE_STATS["runaway"] += 1
    return out


def _dilate4(mask):
    """4 邻域膨胀。offset 会环绕，必须先补一圈背景再算，否则边缘像素
    会把画布另一侧当成邻居。"""
    w, h = mask.size
    pad = Image.new("L", (w + 2, h + 2), 0)
    pad.paste(mask, (1, 1))
    r = pad
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        r = ImageChops.lighter(r, ImageChops.offset(pad, dx, dy))
    return r.crop((1, 1, w + 1, h + 1))


def _shift_neg(mask, dx, dy):
    """result(x, y) = mask(x + dx, y + dy)，画布外一律为 0。"""
    w, h = mask.size
    pad = Image.new("L", (w + 2, h + 2), 0)
    pad.paste(mask, (1, 1))
    return ImageChops.offset(pad, -dx, -dy).crop((1, 1, w + 1, h + 1))


def boundary_contours(mask, min_len=8):
    """返回 [(pts, 有向面积), ...]，pts 为像素中心整数坐标，含外轮廓与洞。

    每条轮廓都从「该连通块光栅序最靠上/左的像素」起笔——这是 Moore 追踪能靠
    「回到起点即闭合」退出的前提。筛选起点用「上方与左方都不是前景」，而不是
    「四邻有背景」：后者会漏掉实心块的角像素和画布角。

    洞 = 对反相掩膜做同样追踪、且不触碰画布边缘的那些（触碰边缘的是画外背景）。

    内部统一在「四周补一圈背景」的画布上做，保证「画外即背景」与 pred() 一致。
    返回坐标已减回两层 padding。
    """
    w, h = mask.size
    TRACE_STATS["open"] = 0
    TRACE_STATS["open_pts"] = 0
    TRACE_STATS["runaway"] = 0
    base = Image.new("L", (w + 2, h + 2), 0)
    base.paste(mask, (1, 1))          # 第一层：让画外=背景成立

    def area_of(pts):
        a = 0.0
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            a += x0 * y1 - x1 * y0
        return a / 2.0

    def sweep(src):
        """沿像素格边界走一圈。

        返回 [(pts, area), ...]，pts 在第一层 padding 坐标下。
        正面积 = 前景外轮廓，负面积 = 洞。

        相比像素中心的 Moore 追踪，边界走边对「细线网络」（描边、腮红描边圈）
        稳健得多：不会在自接触处反复分裂丢段。前提是 de_pinch 已把对角夹点
        补实——否则同一个格点会有两条出边，串接必然走错。
        """
        W, H = src.size
        pad = Image.new("L", (W + 2, H + 2), 0)
        pad.paste(src, (1, 1))
        CW, CH = W + 2, H + 2
        runs = _row_runs(pad.tobytes(), CW, CH)

        edges = {}
        for y, rs in enumerate(runs):
            up = runs[y - 1] if y > 0 else []
            dn = runs[y + 1] if y < CH - 1 else []
            for a, b in rs:
                for s, e in _subtract([(a, b)], up):      # 上边: 左 -> 右
                    edges[(s, y)] = (e, y)
                for s, e in _subtract([(a, b)], dn):      # 下边: 右 -> 左
                    edges[(e, y + 1)] = (s, y + 1)
                edges[(b, y)] = (b, y + 1)                # 右边: 上 -> 下
                edges[(a, y + 1)] = (a, y)                # 左边: 下 -> 上

        out = []
        while edges:
            start = next(iter(edges))
            pts = [start]
            cur = start
            while True:
                nxt = edges.pop(cur, None)
                if nxt is None:
                    break
                cur = nxt
                if cur == start:
                    break
                pts.append(cur)
            if len(pts) < 4:
                continue
            a = 0.0
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                a += x0 * y1 - x1 * y0
            area = a / 2.0
            if abs(area) < 4:
                continue
            if area < 0 and _touches_border(pts, W, H):
                continue                                    # 画外背景，不是洞
            out.append(([(x - 1, y - 1) for x, y in pts], area))
        return out

    def _touches_border(pts, W, H):
        return any(x == 0 or y == 0 or x == W + 1 or y == H + 1 for x, y in pts)

    contours = []
    for pts, area in sweep(base):
        if len(pts) < min_len:
            continue
        contours.append(([(x - 1, y - 1) for x, y in pts], area))
    return contours


# --------------------------------------------------------------------------
# 简化 + 保角平滑
# --------------------------------------------------------------------------

def rdp(pts, eps):
    if len(pts) < 3:
        return list(pts)
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        x0, y0 = pts[a]
        x1, y1 = pts[b]
        dx, dy = x1 - x0, y1 - y0
        n = math.hypot(dx, dy)
        best, bi = -1.0, -1
        for i in range(a + 1, b):
            qx, qy = pts[i]
            d = (math.hypot(qx - x0, qy - y0) if n < 1e-9
                 else abs(dy * qx - dx * qy + x1 * y0 - y1 * x0) / n)
            if d > best:
                best, bi = d, i
        if best > eps:
            keep[bi] = True
            stack.append((a, bi))
            stack.append((bi, b))
    return [p for p, k in zip(pts, keep) if k]


def _turn(a, b, c):
    v1 = (b[0] - a[0], b[1] - a[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 < 1e-9 or n2 < 1e-9:
        return 0.0
    cosv = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cosv))


def smooth_closed(pts, corner_deg=40.0, tension=0.9):
    """闭合折线 -> SVG 路径数据。转角小于 corner_deg 的区段用
    Catmull-Rom 转三次贝塞尔，明显转角保留为直线段。"""
    n = len(pts)
    if n < 4:
        return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z"

    corner = [_turn(pts[(i - 1) % n], pts[i], pts[(i + 1) % n]) >= corner_deg
              for i in range(n)]

    def fmt(p):
        return f"{p[0]:.1f} {p[1]:.1f}"

    out = ["M " + fmt(pts[0])]
    i = 0
    steps = 0
    while i < n and steps <= n:
        steps += 1
        # 从 i+1 往后找第一个转角 j
        j = (i + 1) % n
        while j != i and not corner[j]:
            j = (j + 1) % n
        if j == i:
            # 整圈都没有明显转角：必须整体走闭合 Catmull-Rom。
            # 若走下面的直线分支，整条轮廓会被压成几条直线（渲染出大三角）。
            for k in range(n):
                a = pts[(k - 1) % n]
                p0 = pts[k % n]
                p1 = pts[(k + 1) % n]
                b = pts[(k + 2) % n]
                c1 = (p0[0] + (p1[0] - a[0]) / 6.0 * tension,
                      p0[1] + (p1[1] - a[1]) / 6.0 * tension)
                c2 = (p1[0] - (b[0] - p0[0]) / 6.0 * tension,
                      p1[1] - (b[1] - p0[1]) / 6.0 * tension)
                out.append(f"C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} "
                           f"{fmt(p1)}")
            break
        k = i
        while k != j:                      # 平滑段：逐段输出贝塞尔
            a = pts[(k - 1) % n]
            p0 = pts[k % n]
            p1 = pts[(k + 1) % n]
            b = pts[(k + 2) % n]
            c1 = (p0[0] + (p1[0] - a[0]) / 6.0 * tension,
                  p0[1] + (p1[1] - a[1]) / 6.0 * tension)
            c2 = (p1[0] - (b[0] - p0[0]) / 6.0 * tension,
                  p1[1] - (b[1] - p0[1]) / 6.0 * tension)
            out.append(f"C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {fmt(p1)}")
            k = (k + 1) % n
        jn = (j + 1) % n                   # 跨过转角，拉一条直线
        out.append("L " + fmt(pts[jn]))
        i = jn
    out.append("Z")
    return " ".join(out)


def poly_path(pts):
    """闭合折线路径。

    比贝塞尔平滑更「笨」但绝不出错：像素中心的折线就是掩膜边界本身，不可能
    自交。平滑后的 Catmull-Rom 在噪声点列上会过冲产生自交，一旦配合
    fill-rule=evenodd 就会整片翻转填充（渲染出横跨全图的大三角）。
    """
    n = len(pts)
    if n < 3:
        return ""
    head = f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
    body = " ".join(f"L {x:.1f} {y:.1f}" for x, y in pts[1:])
    return f"{head} {body} Z"


# --------------------------------------------------------------------------

def components(mask):
    """返回 [(像素数, [(y, a, b), ...]), ...]，按像素数从大到小。

    基于扫描线 + 并查集，避免逐像素 Python 循环。
    """
    w, h = mask.size
    runs = _row_runs(mask.tobytes(), w, h)
    flat = []
    for y, rs in enumerate(runs):
        for a, b in rs:
            flat.append((y, a, b))
    parent = list(range(len(flat)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_row = {}
    for idx, (y, a, b) in enumerate(flat):
        by_row.setdefault(y, []).append(idx)
    for y in range(h - 1):
        up, dn = by_row.get(y), by_row.get(y + 1)
        if not up or not dn:
            continue
        i = j = 0
        while i < len(up) and j < len(dn):
            u, d = up[i], dn[j]
            ua, ub = flat[u][1], flat[u][2]
            da, db = flat[d][1], flat[d][2]
            if ub <= da:
                i += 1
            elif db <= ua:
                j += 1
            else:
                ru, rd = find(u), find(d)
                if ru != rd:
                    parent[rd] = ru
                if ub < db:
                    i += 1
                else:
                    j += 1

    groups = {}
    for idx in range(len(flat)):
        groups.setdefault(find(idx), []).append(idx)
    out = []
    for members in groups.values():
        px = sum(flat[i][2] - flat[i][1] for i in members)
        x0 = min(flat[i][1] for i in members)
        x1 = max(flat[i][2] for i in members)
        y0 = min(flat[i][0] for i in members)
        y1 = max(flat[i][0] + 1 for i in members)
        # 两个厚度指标，各能抓一类伪影：
        #   run   = 平均游程，抓「细带」（沿描边蔓延的过渡带，每行只有几条窄游程）
        #   bulk  = 面积 / 外接框最长边，抓「短粗条」（60x10 的残留长条）
        # 单用任何一个都会漏：细带的包围框横跨整图，bulk 会显得很厚；
        # 而短粗条只有一两条游程，run 会显得很宽。
        out.append((px, px / len(members),
                    px / max(1, x1 - x0, y1 - y0),
                    [flat[i] for i in members]))
    out.sort(key=lambda t: -t[0])
    return out


def filter_small(mask, min_px, thin=False):
    """丢掉太小 / 太薄的连通块。

    thin=True 时启用厚度判据（用于腮红、黄色、粉色）：描边的抗锯齿过渡带在
    这三层里会留下贴着棕线的细带，面积可以很大（沿整条描边蔓延），只有「薄」
    这一特征稳定。

    阈值取「层内最大块的相对比例 + 绝对下限」的较大者，这样对不同尺寸、
    不同色块大小的图都自适应：实测残留细带 bulk=25、鼻头腮红 bulk=147，
    比例差近 6 倍。
    """
    comps = components(mask)
    if thin and comps:
        ref_run = max(r for _p, r, _b, _ in comps)
        ref_bulk = max(b for _p, _r, b, _ in comps)
        lo_run = max(14.0, ref_run * 0.15)
        lo_bulk = max(14.0, ref_bulk * 0.20)
    else:
        lo_run = lo_bulk = 0.0

    def bad(px, run, bulk):
        return px < min_px or run < lo_run or bulk < lo_bulk

    if not any(bad(px, r, b) for px, r, b, _ in comps):
        return mask, 0
    data = bytearray(mask.tobytes())
    w = mask.size[0]
    removed = 0
    for px, run, bulk, runs in comps:
        if not bad(px, run, bulk):
            continue
        removed += 1
        for y, a, b in runs:
            data[y * w + a:y * w + b] = bytes(b - a)
    return Image.frombytes("L", mask.size, bytes(data)), removed


def tidy(mask, close_n=3, open_n=3):
    """形态学清理：先闭运算（填小孔洞）再开运算（去噪点）。

    阈值分割出来的掩膜天然带毛刺——不清理的话，Moore 追踪会在 1px 碎片上
    反复死循环，产出大量残弧。
    """
    from PIL import ImageFilter
    for _ in range(max(0, (close_n - 1) // 2)):
        mask = mask.filter(ImageFilter.MaxFilter(3))
    for _ in range(max(0, (close_n - 1) // 2)):
        mask = mask.filter(ImageFilter.MinFilter(3))
    for _ in range(max(0, (open_n - 1) // 2)):
        mask = mask.filter(ImageFilter.MinFilter(3))
    for _ in range(max(0, (open_n - 1) // 2)):
        mask = mask.filter(ImageFilter.MaxFilter(3))
    return mask


def corner_color(im, patch=6):
    """取四角小块的中位色作为背景色。

    不能靠「最亮的主色」猜背景：贴纸纸底本身就接近白，最亮的往往是背景而不是纸。
    """
    w, h = im.size
    px = im.load()
    samples = []
    for cx, cy in ((0, 0), (w - patch, 0), (0, h - patch), (w - patch, h - patch)):
        for y in range(cy, cy + patch):
            for x in range(cx, cx + patch):
                samples.append(px[x, y])
    samples.sort()
    return samples[len(samples) // 2]


def derive_palette(im, bg, k=6, merge=42, min_share=0.0012):
    """从图中自动提取主色板（排除背景色）。

    硬编码代表色不可行：两张贴纸的粉色分别是 (253,225,222) 和 (253,231,223)，
    腮红也差 (243,169,168) vs (245,182,182)。这里用 PIL 的中位切分拿自适应
    色板，再按曼哈顿距离合并相近颜色。
    """
    small = im.resize((max(1, im.size[0] // 2), max(1, im.size[1] // 2)),
                      Image.BILINEAR)
    q = small.quantize(colors=96, method=Image.MEDIANCUT)
    pal = q.getpalette()
    hist = q.histogram()
    total = sum(hist)

    def d1(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])

    cands = [(tuple(pal[i * 3:i * 3 + 3]), hist[i]) for i in range(len(hist))
             if hist[i] >= max(4, total * min_share) and d1(tuple(pal[i * 3:i * 3 + 3]), bg) > merge]
    cands.sort(key=lambda t: -t[1])
    kept = []
    for col, n in cands:
        if all(d1(col, c) > merge for c, _ in kept):
            kept.append((col, n))
        if len(kept) >= k:
            break
    return [c for c, _ in kept]


def assign_roles(colors):
    """把主色按特征分配成图层角色：纸/棕/黄/腮红/粉。"""
    if len(colors) < 2:
        return []
    lum = lambda c: c[0] + c[1] + c[2]
    order = sorted(colors, key=lum)
    # 纸底 = 最亮且偏白的主色；若色板里没有就用默认米白
    if min(order[-1]) >= 225:
        paper = order[-1]
        order = order[:-1]
    else:
        paper = (250, 246, 242)
    layers = [("paper", paper)]
    if not order:
        return layers
    layers.append(("brown", order[0]))
    rest = order[1:]
    yellow = max(rest, key=lambda c: c[1] - c[2]) if rest else None
    if yellow and yellow[1] - yellow[2] > 40:
        layers.append(("yellow", yellow))
        rest = [c for c in rest if c != yellow]
    blush = max(rest, key=lambda c: c[0] - c[1]) if rest else None
    if blush and blush[0] - blush[1] > 40:
        layers.append(("blush", blush))
        rest = [c for c in rest if c != blush]
    if rest:
        layers.append(("pink", rest[-1]))
    return layers


def layer_params(name):
    """各层的形态学与去碎屑参数（按层名，与颜色无关）。"""
    return {
        "paper": (True, 0, 0, 3000, 0),
        "yellow": (False, 3, 3, 8000, 4000),
        "pink": (False, 3, 3, 3000, 3000),
        "blush": (False, 9, 9, 3000, 2000),
        "brown": (False, 3, 0, 700, 2500),
    }[name]


# 绘制顺序见 DRAW_ORDER；实际图层由 make_layers() 从图中自动提取色板后生成
DRAW_ORDER = ["paper", "yellow", "pink", "blush", "brown"]


def make_layers(im):
    """返回 [(层名, 颜色, 填洞, 闭, 开, 最小块, 最小洞)]，已按绘制顺序排好。

    最小块/最小洞是像素数，必须按图幅缩放：两张图相差 20 倍面积，同一套绝对
    阈值会把小图上真实的腮红当成噪点删掉。
    """
    bg = corner_color(im)
    roles = assign_roles(derive_palette(im, bg))
    k = (im.size[0] * im.size[1]) / (1812.0 * 1558.0)
    out = []
    for name, col in roles:
        fh, cn, on, mc, mh = layer_params(name)
        out.append((name, col, fh, cn, on,
                    max(8, int(mc * k)), max(4, int(mh * k))))
    out.sort(key=lambda t: DRAW_ORDER.index(t[0]))
    return out, bg


def classify(im, palette):
    """按 RGB 最近色分类，返回 {类名: 'L' 掩膜}。

    用曼哈顿(L1)距离而非欧氏(L2)：L2 要缩 10 位才能塞进 8 位累加，那样
    (3,21,20) 这种米白/粉的微小差异会被直接抹成 0 而误判。L1 每通道先 >>2，
    三通道最大 189，不溢出且差异分辨得开。
    """
    R, G, B = im.split()
    size = im.size

    def dist(r0, g0, b0):
        dr = R.point([abs(v - r0) >> 2 for v in range(256)])
        dg = G.point([abs(v - g0) >> 2 for v in range(256)])
        db = B.point([abs(v - b0) >> 2 for v in range(256)])
        return ImageChops.add(ImageChops.add(dr, dg), db)

    label = None
    best = None
    for idx, (name, (r0, g0, b0)) in enumerate(palette):
        d = dist(r0, g0, b0)
        if best is None:
            best = d
            label = Image.new("L", size, idx)
            continue
        closer = ImageChops.subtract(best, d).point(
            lambda v: 255 if v > 0 else 0)
        label = Image.composite(Image.new("L", size, idx), label, closer)
        best = ImageChops.darker(best, d)

    return {name: label.point([255 if v == idx else 0 for v in range(256)])
            for idx, (name, _c) in enumerate(palette)}


def load_rgb(path):
    """读图并合成到白底。

    带 alpha 的 PNG 若直接 convert('RGB')，透明区会变成纯黑，最近色分类会把它
    判成深棕——整张背景都会被填满。
    """
    im = Image.open(path)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        flat = Image.new("RGBA", im.size, (255, 255, 255, 255))
        return Image.alpha_composite(flat, im).convert("RGB")
    return im.convert("RGB")


def prepare_masks(im, layers, bg, blur=1.1):
    """原图 -> 各层掩膜（高斯模糊 -> 最近色分类 -> 去夹点 -> 形态学 -> 去碎屑）。"""
    if blur > 0:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    uniq = [("bg", bg)] + [(str(c), c) for _n, c, *_ in layers
                           if c != bg]
    raw = classify(im, uniq)
    by_col = {c: raw[tag] for tag, c in uniq}

    out = {}
    # 只有腮红/黄色这类「软渐变」层需要放大形态学核来抹掉边缘阶梯。
    # 其余层（尤其纸边和描边）必须保持小核：纸边只有约 20px 宽，核一大就被
    # 腐蚀碎，描边也会被撑粗。
    mscale = max(1.0, min(im.size) / 700.0)
    for name, col, _fh, close_n, open_n, min_comp, _mh in layers:
        m = by_col.get(col)
        if m is None:
            m = Image.new("L", im.size, 0)
        if name in ("blush", "yellow"):
            close_n = int(round(close_n * mscale)) | 1
            open_n = int(round(open_n * mscale)) | 1
        m = de_pinch(tidy(m, close_n, open_n))
        # 描边过渡带会在粉/腮红/黄里留下细带残留，按层内相对厚度筛掉
        thin = name in ("blush", "yellow", "pink")
        out[name] = filter_small(m, min_comp, thin)[0]

    # 贴纸外形 = 所有非背景像素（含裁切线与内部），fill_holes 会填实。
    # 这里要额外做形态学闭合：外缘的「白/非白」交界是抗锯齿噪声，会在外轮廓
    # 上啃出 1~2px 的锯齿缺口，在深色背景下表现为黑边毛刺。
    paper = de_pinch(tidy(_not(by_col[bg]), 5, 5))
    out["paper"] = filter_small(paper, max(8, int(3000 * k_of(im))))[0]
    return out


def k_of(im):
    return (im.size[0] * im.size[1]) / (1812.0 * 1558.0)


def build_svg(masks, layers, size, offsets, eps, title, smooth=False,
              skip_paper=False):
    off_x, off_y = offsets
    w, h = size
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
             # 路径坐标已因裁剪归零，viewBox 必须从 0 开始；原图偏移记在 data 上
             f'viewBox="0 0 {w} {h}" data-origin="{off_x} {off_y}">',
             f"  <title>{title}</title>"]
    stats = []
    for name, col, fill_holes, _c, _o, _mc, min_hole in layers:
        if skip_paper and name == "paper":
            continue
        cs = boundary_contours(masks[name])
        # 外轮廓一律保留（filter_small 已按尺寸剔除过碎块）；洞轮廓小于 min_hole
        # 的一律丢弃 —— 丢掉洞等价于「填实」，正好消掉大色块里被抠出的小白点。
        if fill_holes:
            cs = [c for c in cs if c[1] > 0]
        else:
            cs = [c for c in cs if c[1] > 0 or abs(c[1]) >= min_hole]
        if not cs:
            continue
        d = []
        for pts, area in cs:
            s = rdp(pts, eps)
            if len(s) < 4:
                continue
            if area < 0:
                s = s[::-1]
            path = smooth_closed(s) if smooth else poly_path(s)
            if path:
                d.append(path)
        if not d:
            continue
        hexc = "#%02X%02X%02X" % col
        parts.append(f'  <g id="layer-{name}" fill="{hexc}" fill-rule="evenodd">')
        parts.append('    <path d="' + " ".join(d) + '"/>')
        parts.append('  </g>')
        stats.append(f"{name}{hexc}:{len(d)}")
    parts.append('</svg>')
    return "\n".join(parts), " ".join(stats)


def render_check(masks, layers, size, eps, min_area, out_png):
    """不依赖浏览器，直接用 PIL 把轮廓多边形画出来做自检。"""
    from PIL import ImageDraw
    w, h = size
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for name, col, fill_holes, _c, _o, _mc, min_hole in layers:
        cs = boundary_contours(masks[name])
        if fill_holes:
            cs = [c for c in cs if c[1] > 0]
        else:
            cs = [c for c in cs if c[1] > 0 or abs(c[1]) >= min_hole]
        for pts, area in cs:
            s = rdp(pts, eps)
            if len(s) < 3:
                continue
            d.polygon([(x, y) for x, y in s], fill=col)
    img.save(out_png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--eps", type=float, default=1.0, help="RDP 容差(像素)")
    ap.add_argument("--min-area", type=float, default=80.0, help="丢弃的最小轮廓面积")
    ap.add_argument("--blur", type=float, default=1.1)
    ap.add_argument("--crop", action="store_true")
    ap.add_argument("--debug", default=None)
    ap.add_argument("--check", default=None, help="用 PIL 直接画轮廓做自检")
    ap.add_argument("--smooth", action="store_true",
                    help="输出 Catmull-Rom 贝塞尔而非折线（更小但会自交）")
    ap.add_argument("--no-paper", action="store_true",
                    help="不画米白模切纸边，只保留小猪本体（深色背景下更干净）")
    ap.add_argument("--title", default="")
    a = ap.parse_args()

    im = load_rgb(a.src)
    layers, bg = make_layers(im)
    print(f"背景 {bg[0]:02X}{bg[1]:02X}{bg[2]:02X} | 自动色板: "
          + ", ".join(f"{n}#{c[0]:02X}{c[1]:02X}{c[2]:02X}"
                      for n, c, *_ in layers), flush=True)
    masks = prepare_masks(im, layers, bg, a.blur)
    st = TRACE_STATS
    print(f"掩膜就绪，残弧 {st['open']} 条 / 失控 {st['runaway']} 条", flush=True)

    if a.debug:
        dbg = Image.new("RGB", im.size, (255, 255, 255))
        for name, col, _, _c, _o, _mc, _mh in layers:
            dbg.paste(Image.new("RGB", im.size, col), (0, 0), masks[name])
        dbg.resize((im.size[0] // 3, im.size[1] // 3), Image.LANCZOS).save(a.debug)

    off = (0, 0)
    if a.crop:
        bbox = masks["paper"].getbbox()
        im = im.crop(bbox)
        masks = {k: v.crop(bbox) for k, v in masks.items()}
        off = (bbox[0], bbox[1])

    if a.check:
        render_check(masks, layers, im.size, a.eps, a.min_area, a.check)
        print("check ->", a.check)

    svg, stats = build_svg(masks, layers, im.size, off, a.eps,
                           a.title or a.src, smooth=a.smooth,
                           skip_paper=a.no_paper)
    with open(a.dst, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"{a.dst}  {im.size[0]}x{im.size[1]}  [{stats}]")


if __name__ == "__main__":
    sys.exit(main())

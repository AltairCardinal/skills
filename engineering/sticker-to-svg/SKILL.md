---
name: sticker-to-svg
description: >
  Convert flat-color sticker artwork (PNG/JPG) into a layered vector SVG plus an
  antialiased transparent PNG, by tracing real pixel boundaries instead of hand-drawing
  curves. Use when the user asks to redraw, vectorize, trace, or "make it into an SVG /
  vector / 可编辑矢量" a sticker, mascot, chibi character, logo, icon, or any flat-color
  cartoon image, or asks why a previous vector redraw does not line up with the source.
  Also use to diagnose SVG/PNG artifacts such as color speckles, ragged sticker borders,
  outlines that are too thick or too thin, or jagged edges on dark backgrounds.
---

# Sticker to Vector

把扁平色贴纸位图重建成**分层矢量 SVG + 抗锯齿透明 PNG**。核心原则：**轮廓来自真实像素边界，
不是目测手绘**。手绘贝塞尔只能做到「看着像」，从像素提取才能做到「完全重叠」。

## 用法

脚本位于**本 skill 目录**的 `scripts/` 下。装到 agent 后通常在：

```bash
# 已安装到 skill 根（Codex 与 MiniMax Code 共用此路径）
S=~/.codex/skills/sticker-to-svg/scripts
# Windows: $S="$env:USERPROFILE\.codex\skills\sticker-to-svg\scripts"
# 若 $env:USERPROFILE\.codex 本身是目录联接，真实位置可能是 D:\Codex\home\skills\...

# 直接从 skills 收藏库运行则用仓库内路径
S=<repo>/engineering/sticker-to-svg/scripts
```

```bash
python $S/sticker2svg.py 输入.png                        # <名>.svg / <名>.png / <名>-compare.png
python $S/sticker2svg.py 输入.png -o 输出目录 --both      # 同时给「含模切边」「无纸边」两套
python $S/sticker2svg.py 输入.png --no-paper             # 只要主体，去掉米白模切边
python $S/sticker2svg.py 输入.png --report               # 附诊断报告（色板 / 各层连通块）
python $S/sticker2svg.py --selftest                      # 轮廓提取回归自检
```

常用参数：`--eps` 轮廓简化容差（像素，默认 1.2）、`--blur` 分类前高斯模糊（默认 1.1）、
`--size` 导出 PNG 边长（默认 1024）、`--no-compare` 不生成对照图。

依赖：Python + Pillow。PNG 导出需要一个 Chromium 系浏览器（脚本默认找 Edge，可用
`pngout.py` 里的 `EDGE` 常量改路径）。**不需要 numpy / OpenCV / potrace。**

## 流水线

1. **读图合成到白底** —— 带 alpha 的 PNG 直接 `convert('RGB')` 会把透明区变成纯黑，
   后续按最近色分类会整片判成深棕。
2. **自动提取色板** —— PIL 中位切分拿主色，按曼哈顿距离合并，再按颜色特征分配图层角色
   （最亮→纸底、最暗→棕、G−B 最大→黄、R−G 最大→腮红、其余→粉）。
3. **最近色分类** —— 阈值作用在 1px 高斯模糊上以获得亚像素边界。
4. **逐层清理** —— 去对角夹点 → 形态学闭/开 → 碎屑过滤（最小连通块 + 相对厚度）。
5. **轮廓提取** —— 沿像素格边界走一圈，正面积=外轮廓、负面积=洞。
6. **简化输出** —— RDP 后输出折线（默认）或 Catmull-Rom 贝塞尔。
7. **matte 导出 PNG** —— 白底/黑底各渲染一次提取 alpha。

## 踩过的坑（别再踩一遍）

这些是本流水线调试中最难定位的几个，改动相关代码时务必对照检查：

1. **描边粗细不要用固定阈值**。棕线与相邻色之间的抗锯齿过渡带能宽到 20px 以上，
   任何单一阈值都会把线撑粗（判到过渡带外沿）或削薄。最近色分类让边界自动落在
   50% 混合点，也就是描边的几何中线——这是唯一正确的做法。

2. **距离量化会抹掉小差异**。用欧氏距离要缩 10 位才能塞进 8 位累加，
   `(3,21,20)` 这种米白/粉的微小差异会被直接抹成 0 而误判。改用曼哈顿距离、每通道
   只 `>>2`，三通道最大 189，不溢出且差异分辨得开。

3. **色板不能写死**。两张贴纸的粉色可以是 `(253,225,222)` 和 `(253,231,223)`、
   腮红 `(243,169,168)` 和 `(245,182,182)`。硬编码代表色对另一张直接失效。

4. **轮廓要沿像素格边界走，不是像素中心**。像素中心的 Moore 追踪在「细线网络」
   （描边、腮红描边圈）上会反复自接触分裂、丢段；边界走边稳得多。
   前提是对角夹点已清理干净，否则同一格点会有两条出边，串接必然走错。

5. **起点必须是连通块光栅序的首像素**。「上方与左方都是背景」会**过度命中**
   凸角阶梯上的像素，导致同一块被追踪两次，产生两条几乎重合的轮廓；
   evenodd 相消后整块只剩一圈细线。

6. **贝塞尔平滑会自交**。Catmull-Rom 在噪声点列上过冲产生自交，配 `fill-rule=evenodd`
   会把整片填充翻转，渲染出横跨全图的大三角。默认输出**折线**（像素中心的折线不可能自交）。

7. **「整圈无明显转角」是平滑函数的退化分支**。若不特判，整条轮廓会被压成几条直线段。

8. **纸边/描边不能用大形态学核**。纸边只有约 20px 宽，核一大就被腐蚀碎（外轮廓从
   1 条裂成 6 条）。形态学核放大只能用在腮红/黄色这类软渐变层。

9. **透明 PNG 不要用「接近白即透明」的硬阈值**。边缘必然锯齿，深色背景上露出白毛边和
   黑缺口。用 matte：`alpha = 1 − (I_白 − I_黑)/255`，颜色由 `I_黑 / alpha` 反解。

10. **裁剪后 viewBox 必须从 0 开始**。路径坐标已因裁剪归零，偏移要记在 `data-origin`
    属性里，否则导出图整体错位。

## 伪影速查

| 现象 | 成因 | 处理 |
|---|---|---|
| 色斑碎点 | 阈值分割的孤立连通块 | 最小连通块面积过滤，阈值按图幅面积缩放 |
| 描边外一圈假腮红/假粉色 | 腮红色在 RGB 空间里正好落在「粉—棕」连线上，过渡带粉侧必然被判成腮红 | 按层内相对厚度筛（残留 bulk≈25，真实腮红 bulk≈147） |
| 贴纸白边有黑色缺口 | 外轮廓碎成多条子路径，缺口是轮廓上的凹湾 | 纸层加形态学闭运算，收敛成单条闭环 |
| 描边比原图粗/细 | 分类阈值没落在 50% 混合点 | 改用最近色分类 |
| 深色背景下锯齿、白毛边 | PNG 硬阈值抠图 | 换 matte 提取 |
| 深色背景下一圈白环 | 米白模切边（本就是原图的一部分） | 用 `--no-paper` 变体 |

厚度有两个指标，各抓一类伪影，**单用任何一个都会漏**：
`run` = 平均游程（抓沿描边蔓延的细带），`bulk` = 面积 ÷ 外接框最长边（抓短粗长条）。
细带的包围框横跨整图，`bulk` 会显得很厚；而短粗条只有一两条游程，`run` 会显得很宽。

## 验证

`--selftest` 用 10 个合成图形校验轮廓提取：轮廓数必须正确，且
**「外轮廓面积之和 − 洞面积之和」必须等于掩膜像素数**（误差 0）。这是比任何栅格化
比对都强的保证——面积对上，说明轮廓几何完全正确。改完轮廓代码务必跑一遍。

肉眼验证用 `--both` 生成的对照图：左上原图 / 右上矢量 / 左下 50% 叠加。
**务必分别在白色和深色背景下检查**——很多伪影在白底上完全看不见。

## 局限

- 只适合**扁平色**插画。渐变、照片、写实质感会被压成有限的几块平色。
- 输出是折线（点数多但绝不会错），需要更小的文件可用 `--smooth` 出贝塞尔，
  但要自己承担自交风险。
- 纸边是模切边，本就是原图的一部分；深色背景下若不想要，用 `--no-paper`。

# Skills

个人 skill 收藏库，按类别收纳。每个 skill 一个自包含目录，含自己的 `SKILL.md` 与所需文件，
可单独复制到本机 skill 目录使用。

## 目录结构

```
skills/
├── creative/                    创作类：角色设计、美术
│   └── design-realistic-characters/
└── engineering/                 工程类：工具、自动化脚本
    └── sticker-to-svg/
```

## Skill 索引

### creative — 创作

| Skill | 说明 |
|---|---|
| [design-realistic-characters](creative/design-realistic-characters/) | 设计可信、有辨识度的成人角色身份，避免通用 AI 脸孔。含提示配方与评审量表。 |

### engineering — 工程

| Skill | 说明 |
|---|---|
| [sticker-to-svg](engineering/sticker-to-svg/) | 把扁平色贴纸位图重建成分层矢量 SVG + 抗锯齿透明 PNG。轮廓从真实像素边界提取，而非目测手绘。依赖 Pillow + Chromium。 |

## 安装到本机

Agent 发现 skill 的位置是**扁平的** `<skill 根>\<skill 名>\SKILL.md`；本仓库按类别分了两层，
所以装的时候需要在中间做一次「扁平化」——用仓库自带的安装脚本，它会给每个 skill 在目标根下
建一个**目录联接 / 符号链接**，指向仓库里的实际目录。这样改仓库即生效，两端不会分叉。

```bash
# Windows（PowerShell）—— 默认装到 %USERPROFILE%\.codex\skills
.\install.ps1

# 指定目标根目录
.\install.ps1 -Target D:\Codex\home\skills

# 跨文件系统、目标不支持联接时：改用复制（注意不再自动同步）
.\install.ps1 -Copy
```

```bash
# macOS / Linux —— 默认装到 $HOME/.codex/skills
./install.sh
./install.sh /path/to/skills
COPIES=1 ./install.sh      # 复制而非链接
```

> **注意**：`~/.minimax/skills/` 这样的「各自为政」目录**两个运行时都不扫**。
> 以 Codex 为例，它只看 `~/.codex/skills/<名字>/SKILL.md`（你的 `~/.codex` 本身是个指向
> `D:\Codex\home` 的目录联接，真实位置是 `D:\Codex\home\skills`），MiniMax Code 读同一处，
> 所以两边都能发现。装好后若新 skill 没出现，重启对应 agent 会话即可刷新。

## 新增 skill

1. 在对应类别下新建目录，目录名 = skill 名（小写、连字符）
2. 放一个带 YAML frontmatter 的 `SKILL.md`（至少含 `name` 与 `description`）
   - `description` 决定什么请求会触发它，写清**何时该用**、**何时不该用**
3. 附带文件放 `scripts/` / `references/` / `assets/` 子目录
4. 在本文件索引表里加一行
5. 跑一次 `install.ps1` / `install.sh` 挂到本机
6. 提交 PR

## 约定

- 每个 skill 必须**可独立使用**：不依赖本仓库其它目录
- 脚本尽量零依赖，标准库之外只引入确实需要的库
- 能在白底和深色背景下都验证的视觉产物，交付前两种背景都要看
- 能自检的写自检入口（`--selftest`），改动后先跑

## License

MIT，见 [LICENSE](LICENSE)。

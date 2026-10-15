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

把 skill 目录复制到本机 skill 根目录即可：

```bash
# 复制单个 skill
cp -r engineering/sticker-to-svg ~/.minimax/skills/

# Windows PowerShell
Copy-Item -Recurse engineering\sticker-to-svg "$env:USERPROFILE\.minimax\skills\"
```

或者整个收藏库一起克隆：

```bash
git clone https://github.com/AltairCardinal/skills.git ~/.minimax/skills/
```

## 新增 skill

1. 在对应类别下新建目录，目录名 = skill 名（小写、连字符）
2. 放一个带 YAML frontmatter 的 `SKILL.md`（至少含 `name` 与 `description`）
   - `description` 决定什么请求会触发它，写清**何时该用**、**何时不该用**
3. 附带文件放 `scripts/` / `references/` / `assets/` 子目录
4. 在本文件索引表里加一行
5. 提交 PR

## 约定

- 每个 skill 必须**可独立使用**：不依赖本仓库其它目录
- 脚本尽量零依赖，标准库之外只引入确实需要的库
- 能在白底和深色背景下都验证的视觉产物，交付前两种背景都要看
- 能自检的写自检入口（`--selftest`），改动后先跑

## License

MIT，见 [LICENSE](LICENSE)。

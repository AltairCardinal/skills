#!/usr/bin/env bash
# 把本仓库里的每个 skill 安装到 agent 的 skill 目录。
#
# agent 期望的布局是扁平的 <skill 根>/<skill 名>/SKILL.md，而本仓库按类别分了两层。
# 本脚本为每个含 SKILL.md 的 skill 目录在目标根下放一份真实副本。
#
# 默认复制而非符号链接：链接只是省去同步，但源目录一旦被移动、重命名或清理，
# skill 就会静默失效且不报错。副本自包含、无外部依赖，宁可多跑一次脚本。
# 代价是仓库改了要重跑本脚本才会同步到本机。
#
# 用法:
#   ./install.sh                 # 默认复制到 $HOME/.codex/skills
#   ./install.sh /path/to/skills # 指定目标根
#   LINKS=1 ./install.sh         # 改用符号链接（更快生效，但脆弱）
#   FORCE=1  ./install.sh        # 强制覆盖已存在的 skill 目录
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-$HOME/.codex/skills}"
FORCE="${FORCE:-}"
LINKS="${LINKS:-}"

mkdir -p "$TARGET"

installed=0
skipped=0

while IFS= read -r skill; do
    name="$(basename "$skill")"
    dest="$TARGET/$name"

    if [ -e "$dest" ] || [ -L "$dest" ]; then
        if [ -L "$dest" ] && [ "$(readlink -f "$dest")" = "$(readlink -f "$skill")" ] && [ -n "$LINKS" ]; then
            printf '  ready    %s (symlink)\n' "$name"
            continue
        fi
        if [ -z "$FORCE" ]; then
            printf '  skip     %s -- already exists (use FORCE=1 to overwrite)\n' "$name" >&2
            skipped=$((skipped + 1))
            continue
        fi
        # 之前用链接装过：只摘链接本身，不动源目录
        [ -L "$dest" ] && rm -f "$dest"
    fi

    if [ -n "$LINKS" ]; then
        ln -s "$skill" "$dest"
        printf '  linked   %s -> %s\n' "$name" "$skill"
    else
        mkdir -p "$dest"
        for entry in "$skill"/* "$skill"/.[!.]*; do
            [ -e "$entry" ] || continue
            cp -r "$entry" "$dest/"
        done
        # 编译产物可能嵌在子目录里（如 scripts/__pycache__），复制后统一清掉
        find "$dest" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
        printf '  copied   %s\n' "$name"
    fi
    installed=$((installed + 1))
done < <(find "$REPO" -mindepth 2 -maxdepth 2 -type d -exec test -f '{}/SKILL.md' ';' -print)

echo
if [ "$installed" -eq 0 ]; then
    echo "完成。没有需要更新的 skill -> $TARGET"
else
    echo "完成。已安装/更新 $installed 个 skill -> $TARGET"
fi
[ "$skipped" -gt 0 ] && echo "$skipped 个因目标已存在被跳过（FORCE=1 可覆盖）" >&2
if [ -z "$LINKS" ] && [ "$installed" -gt 0 ]; then
    echo "提示：仓库若有改动，重跑本脚本即可同步到本机。"
fi

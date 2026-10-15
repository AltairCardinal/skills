#!/usr/bin/env bash
# 把本仓库里的每个 skill 安装到 agent 的 skill 目录。
#
# agent 期望的布局是扁平的 <skill 根>/<skill 名>/SKILL.md，而本仓库按类别分了两层。
# 本脚本为每个含 SKILL.md 的 skill 目录在目标根下创建符号链接，改仓库即生效、两端不分叉。
#
# 用法:
#   ./install.sh                      # 默认 $HOME/.codex/skills
#   ./install.sh /path/to/skills      # 指定目标
#   COPIES=1 ./install.sh             # 不用链接，直接复制（跨文件系统时用）
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-$HOME/.codex/skills}"

mkdir -p "$TARGET"

count=0
while IFS= read -r skill; do
    name="$(basename "$skill")"
    link="$TARGET/$name"
    if [ -e "$link" ] || [ -L "$link" ]; then
        if [ "$(readlink -f "$link")" = "$(readlink -f "$skill")" ]; then
            printf '  ready    %s\n' "$name"
        else
            printf '  skip     %s -- already exists and points elsewhere: %s\n' "$name" "$link" >&2
        fi
        continue
    fi
    if [ -n "${COPIES:-}" ]; then
        cp -r "$skill" "$link"
        printf '  copied   %s\n' "$name"
    else
        ln -s "$skill" "$link"
        printf '  linked   %s -> %s\n' "$name" "$skill"
    fi
    count=$((count + 1))
done < <(find "$REPO" -mindepth 2 -maxdepth 2 -type d -exec test -f '{}/SKILL.md' ';' -print)

if [ "$count" -eq 0 ]; then
    echo "没有找到任何含 SKILL.md 的 skill 目录" >&2
    exit 1
fi
echo
echo "完成。已就位于：$TARGET"

<#
.SYNOPSIS
    把本仓库里的每个 skill 安装到 agent 的 skill 目录。

.DESCRIPTION
    agent 期望的布局是扁平的 <skill 根>\<skill 名>\SKILL.md，而本仓库按类别分了两层。
    本脚本为每个含 SKILL.md 的 skill 目录在目标根下放一份**真实副本**。

    默认复制而非目录联接：联接只是省去同步，但源目录一旦被移动、重命名或清理，
    skill 就会静默失效，且不会报错。副本自包含、无外部依赖，宁可多跑一次脚本。

    代价是仓库改了要重跑本脚本才会同步到本机。

    默认目标：
      Windows  %USERPROFILE%\.codex\skills
      其他     $HOME/.codex/skills
    都可用 -Target 覆盖。

.PARAMETER Target
    skill 根目录。

.PARAMETER Link
    改用目录联接（junction）。省去同步，但源目录移动后会静默失效。

.PARAMETER Force
    强制覆盖已存在的 skill 目录。默认遇到同名目录会跳过并告警，避免误删别的 skill。

.EXAMPLE
    .\install.ps1                          # 复制到默认 skill 根
    .\install.ps1 -Target D:\Codex\home\skills
    .\install.ps1 -Force                    # 仓库有改动时重新覆盖
    .\install.ps1 -Link                     # 改用联接（会更快生效，但脆弱）
#>
[CmdletBinding()]
param(
    [string]$Target = (Join-Path $env:USERPROFILE '.codex\skills'),
    [switch]$Link,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path $Target)) {
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    Write-Host "已创建 skill 根目录: $Target"
}

# 所有含 SKILL.md 的 <类别>\<skill> 目录
$skills = Get-ChildItem $repo -Directory -Recurse -Depth 2 |
    Where-Object { $_.Name -ne '.git' -and (Test-Path (Join-Path $_.FullName 'SKILL.md')) }

if (-not $skills) {
    Write-Warning '没有找到任何含 SKILL.md 的 skill 目录'
    exit 1
}

$installed = 0
$skipped = 0

foreach ($s in $skills) {
    $dest = Join-Path $Target $s.Name

    if (Test-Path $dest) {
        $existing = Get-Item $dest -Force

        # 之前用联接装过：先摘掉重解析点，再按当前模式落内容
        if ($existing.LinkType) {
            if ($existing.Target -notcontains $s.FullName) {
                Write-Warning "  跳过    $($s.Name) —— 目标已存在且指向别处：$dest"
                $skipped++
                continue
            }
            if ($Link) {
                Write-Host "  已就绪  $($s.Name)（联接）" -ForegroundColor DarkGray
                continue
            }
            fsutil reparsepoint delete $dest | Out-Null
        }
        elseif (-not $Force) {
            Write-Warning "  跳过    $($s.Name) —— 目标已存在，加 -Force 可覆盖：$dest"
            $skipped++
            continue
        }
    }

    if ($Link) {
        New-Item -ItemType Junction -Path $dest -Target $s.FullName | Out-Null
        Write-Host "  已联接  $($s.Name)  ->  $($s.FullName)" -ForegroundColor Green
    } else {
        New-Item -ItemType Directory -Force -Path $dest | Out-Null
        Get-ChildItem $s.FullName -Force | ForEach-Object {
            Copy-Item $_.FullName -Destination $dest -Recurse -Force
        }
        # 编译产物可能嵌在子目录里（如 scripts/__pycache__），复制后统一清掉
        Get-ChildItem $dest -Recurse -Directory -Filter '__pycache__' -Force |
            Remove-Item -Recurse -Force
        Write-Host "  已复制  $($s.Name)" -ForegroundColor Green
    }
    $installed++
}

Write-Host ''
if ($installed) {
    Write-Host "完成。已安装/更新 $($installed) 个 skill -> $Target"
} else {
    Write-Host "完成。没有需要更新的 skill -> $Target"
}
if ($skipped) {
    Write-Warning "$($skipped) 个因目标已存在被跳过（加 -Force 可覆盖）"
}
if (-not $Link -and $installed) {
    Write-Host '提示：仓库若有改动，重跑本脚本即可同步到本机。'
}

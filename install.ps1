<#
.SYNOPSIS
    把本仓库里的每个 skill 安装到 agent 的 skill 目录。

.DESCRIPTION
    agent 期望的布局是扁平的 <skill 根>\<skill 名>\SKILL.md，而本仓库按类别分了两层。
    本脚本为每个含 SKILL.md 的 skill 目录在目标根下创建一个目录联接（junction），
    这样改仓库即生效、两端不会分叉。

    默认目标：
      Windows  %USERPROFILE%\.codex\skills
      其他     $HOME/.codex/skills
    都可用 -Target 覆盖。

.PARAMETER Target
    skill 根目录。

.PARAMETER Copy
    不用联接，直接复制（跨卷/跨盘、或目标文件系统不支持联接时用）。
    注意：复制后仓库改动不会自动同步，需要重跑本脚本。

.EXAMPLE
    .\install.ps1
    .\install.ps1 -Target D:\Codex\home\skills
    .\install.ps1 -Copy
#>
[CmdletBinding()]
param(
    [string]$Target = (Join-Path $env:USERPROFILE '.codex\skills'),
    [switch]$Copy
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

foreach ($s in $skills) {
    $link = Join-Path $Target $s.Name
    if (Test-Path $link) {
        $existing = Get-Item $link -Force
        if ($existing.Target -contains $s.FullName) {
            Write-Host "  已就绪  $($s.Name)" -ForegroundColor DarkGray
        } else {
            Write-Warning "  跳过    $($s.Name) —— 目标已存在且不是指向本仓库的联接：$link"
        }
        continue
    }
    if ($Copy) {
        Copy-Item $s.FullName -Destination $link -Recurse
        Write-Host "  已复制  $($s.Name)" -ForegroundColor Green
    } else {
        New-Item -ItemType Junction -Path $link -Target $s.FullName | Out-Null
        Write-Host "  已联接  $($s.Name)  ->  $($s.FullName)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "完成。$($skills.Count) 个 skill 已就位：$Target"

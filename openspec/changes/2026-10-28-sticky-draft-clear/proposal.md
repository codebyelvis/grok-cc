# 显式清理 Orca sticky draft

作者：elvis。

## Why

Orca screen JSON 的独立 `draft` 字段可能非空，即使 composer 只显示 `❯`。
现有 `_idle` 用模糊 ValueError 阻断 send/finish，无法区分真实草稿与 sticky draft，
也没有用户确认后的安全恢复入口。视觉空白不能授权删除真实草稿。

## What Changes

- draft 非空输出不可自动重试的 `nonempty_draft`，只含存在性、逻辑行数、UTF-8 字节数和 SHA256。
- 新增 `clear-draft`：默认只读；显式 `--confirm` 后按 Orca 上游算法单独写清理控制串，不带 Enter。
- 首次清理后只在读回 draft 仍非空且安全核验仍满足时再发一次最大 burst；最多两次，失败为 `sticky_draft`。
- send/finish 不清理草稿；文档说明授权、重验和失败后人工处置。
- 新增隔离回归，版本 dev12 → dev13，只更新四个已改载荷的 manifest hash。

## Scope And Authorization

本轮用户已明确指定设计、TDD、独立 worktree、OpenSpec 和源码交付。
只改 binding helper/测试、SKILL、session-binding reference、CHANGELOG、VERSION、manifest 和本轮 OpenSpec/计划/审核记录。
不 add/commit/push/发布/安装；不运行真实 Orca、SSH/云端 CC 或 Tailscale，
不访问共享 registry，不改全局配置，也不导入安装副本的 archive/retire/collect 补丁。
现有分支均已并入 master；新 worktree 从 `3ae6336` 建立。

2026-10-29 用户另行授权 Git 操作并要求只在主分支交付；按现有 master 收敛并推送 origin/master，
删除本轮功能分支。仅此 Git 授权覆盖上段初次交付时的 Git 限制；发布、安装、真实终端及配置权限不变。

## Evidence Boundary

源码候选采用 standard 独立本地审核；真实临时项目/Registry/CLI，外部 Orca 仅 mock。
运行 `make check`、OpenSpec strict 和独立反例；这些不证明真实终端清理已验收。

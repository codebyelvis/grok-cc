# 保留最终答复回收的父链链接

作者：elvis。

## Why

多个本地窗口对已受理审查做 `recover-final-reply` 时，得到 `integrity_failure`：`Final assistant ancestry does not reach the accepted user turn`。SSH 和 JSONL 读取已经完成。云端转录里，最终 assistant 和已受理 user 之间经常隔着 `attachment` 等非 `user`/`assistant` 记录。现行投影只保留这两类，父链走到缺失 uuid 就中断。这不是 SSH 不可达，也不是登录失败。

## What Changes

远端投影对其他类型只保留 `type`、`uuid`、`parentUuid`，不传 message、attachment 正文、文件快照或其他字段。本机父链行走使用这些链接。导出条件不变：最终 assistant 必须 `end_turn`、有非空 text，且父链回到带本次 marker 的 user。链回到另一条 user、中间 uuid 缺失或成环时仍拒绝。屏幕片段仍不能批准。

不改 SSH、known_hosts、绑定、发送、创建或 finish，也不改云机或 Grok Bot。

## Scope And Authorization

提案待用户批准 `change-id: preserve-final-reply-parent-links` 后才能改代码。本文件不授权安装、提交或推送。

## Evidence

本机 `~/.claude/projects` 的 JSONL 与云端 Claude Code 同一记录族。只统计类型和链接，不读取正文。200 条 `end_turn` 中，31 条父节点直接是 user；122 条在到达 user 之前经过非 assistant 节点，这些节点的类型只有 `attachment`。当前 `RECOVER_REMOTE` 丢弃 `attachment` 后，`_final_text` 无法从最终 assistant 走回已受理 user。

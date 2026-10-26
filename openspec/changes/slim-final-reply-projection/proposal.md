# 最终答复回收投影瘦身

作者：elvis。

## Why

`0.1.0.dev10` 的短重试已经生效：真实 `recover-final-reply` 对 `faae9e6a-f1ce-4355-bbc2-c4e1a62aa524` / `main` 返回 `status=BLOCKED`、`diagnostic.kind=timeout`、`attempts=3`，耗时 277 秒，等于 `90+2+90+5+90`。小 SSH 秒通。Tailscale 只有 DERP，没有直连。完整投影约 764KB，经 DERP 约 155 秒，大于单次 90 秒，所以三次都是 `TimeoutExpired`。体积主要来自 user 大 prompt（单条可达约 240KB），不是 end_turn 正文（约 8KB）。

## What Changes

- `RECOVER_REMOTE` 继续由本机 skill 经 stdin 执行，不改去调用云机上的旁路脚本。窗口算法对标 `/workspace/keepalive/recover-task-slim.py`。
- 非 user/assistant 仍只留 `type`、`uuid`、`parentUuid`。
- user 文本只留 `grok-cc-msg:<task>` 或 task_id 附近窗口，不传整段 user。另附原文 `prompt_sha256`，供无标记旧 prompt 继续按全文摘要比对。
- assistant 只在 `stop_reason=end_turn` 时保留全文；其他 assistant 文本不传。`tool_result` 仍只留类型。
- 单次子进程超时从 90 秒改为 240 秒。`ConnectTimeout` 仍为 20 秒。尝试次数仍最多 3 次，间隔仍为 2 秒和 5 秒。
- `host_key_mismatch`、`jsonl_read_failed`、父链和身份失败仍不重试。不改 known_hosts、bindings、主机钥或云机出口。

## Scope And Authorization

用户本条要求直接改本地 skill，并在改完后对上述 task 再跑一次真实 `recover-final-reply`。`change-id: slim-final-reply-projection`。本文件不授权提交或推送。

## Evidence

云机只读脚本对 faae 的试跑 stdout 为 27940 字节。本变更的目标是同类投影 stdout 小于 50KB，从而单次传输落在 240 秒以内。

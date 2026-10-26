# 最终答复回收的 SSH 超时短重试

作者：elvis。

## Why

`recover-final-reply` 在云机 `sshd` 正常时仍反复返回 `unreachable` / `diagnostic.kind=timeout`。安装版 skill 已含 `d2c1bfe` 的 `_parent_link_record`，这不是 attachment 父链的 `integrity_failure`。当前 `ConnectTimeout=10`，整次 `subprocess.run` 只有 60 秒，且 timeout 不重试。慢传输会被当成 SSH 失败。

## What Changes

只改 `read_final_candidates` 的 recover SSH 读路径、对应回归，以及 Skill/reference 里这一句说明。

- `ConnectTimeout` 从 10 改为 20。整次 SSH 子进程超时从 60 秒改为 90 秒。
- 仅对 `timeout`，以及进程都没启动的 `OSError` / `handshake_failed`，最多尝试 3 次。失败间隔 2 秒、5 秒。最后一次失败不再 sleep。
- 仍失败时类别保持 `unreachable`，`diagnostic.kind` 保持 `timeout` 或真实的 `handshake_failed`。结果可带整数 `attempts`。不回传 stderr。
- `host_key_mismatch`、`jsonl_read_failed`、父链和身份校验失败不重试。
- 保持 `StrictHostKeyChecking=yes`、`UpdateHostKeys=no`、`BatchMode=yes`、`HostKeyAlgorithms=ssh-ed25519`、`ControlMaster=no`。不改 known_hosts，不换 host/user。

不改发送、绑定、创建、云机出口或 Grok Bot keepalive。

## Scope And Authorization

提案待用户批准 `change-id: retry-final-reply-ssh-timeout` 后才能改代码。本文件不授权安装、提交或推送。

## Evidence

2026-10-26 对本机活动 skill 的只读测量，任务 `faae9e6a-f1ce-4355-bbc2-c4e1a62aa524`，未导出正文，未改 bindings：

- 活动 `session_binding.py` 含 `_parent_link_record`。短脚本 SSH 约 2.5–3.7 秒返回。
- 同一 JSONL 为 2,073,560 字节、116 行，远端解析约 0.01 秒，text 约 739,957 字节。
- 安装版完整 `RECOVER_REMOTE` 加 `ssh -v`：20 秒收到 196,608 字节，进程仍未结束。按这个速率，60 秒上限会在传输中途触发 `TimeoutExpired`。
- 1MB 的 stdin 传输探测在 30 秒时仍未结束。

90 秒和 3 次尝试能盖住这次量级附近的抖动。若路径持续停在约 10KB/s，单次 90 秒仍可能不够。本提案不把超时再放宽到 90 秒以上。

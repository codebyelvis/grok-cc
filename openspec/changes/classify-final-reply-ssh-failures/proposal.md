# 区分最终答复回收的 SSH 失败

作者：elvis。

## Why

Orca stream 没有正文时，屏幕结束标记不能当作完整答复。`recover-final-reply` 是唯一的 JSONL 回收路径，但握手失败、主机密钥不匹配、超时和 JSONL 读取失败现在都落成笼统的 `unreachable` 或同一句 “SSH unavailable”。操作者无法判断该停在 Mac，还是只需只读检查云机 `sshd`。

## What Changes

只改 `read_final_candidates` 的失败分类、对应回归，以及 Skill/reference 中这一段说明。失败结果增加固定的 `diagnostic.kind`：`handshake_failed`、`host_key_mismatch`、`timeout`、`jsonl_read_failed`。不回传 SSH stderr。主机密钥验证失败从笼统 `unreachable` 改为已有的 `identity_changed`。其余失败仍拒绝导出。

不改 known_hosts、不自动修钥、不放宽屏幕片段批准、不改发送/绑定/创建，也不改云机或 Grok Bot。

## Scope And Authorization

提案待用户批准 `change-id: classify-final-reply-ssh-failures` 后才能改代码。本文件不授权安装、提交或推送。

## Evidence

当前源码把 `TimeoutExpired`、`OSError` 和 SSH 退出码 255 都报成 `unreachable`；退出码 2 也是 `unreachable`。指纹不匹配已经是 `identity_changed`。见 `scripts/session_binding.py` 的 `read_final_candidates` 与 `scripts/tests/test_session_binding.py` 的 `test_ssh_unreachable_and_permission`。

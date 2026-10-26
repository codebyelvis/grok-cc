# classify-final-reply-ssh-failures 自检

文档类型：自检 verification review

日志及版本：2026-10-26，源码 VERSION `0.1.0.dev8`

结论：有风险

验证范围：

- `openspec/changes/classify-final-reply-ssh-failures/specs/final-reply-recovery/spec.md`
- `scripts/session_binding.py` 的 `read_final_candidates`
- `scripts/tests/test_session_binding.py` 的 `RecoverFinalReplyTests`
- `SKILL.md`、`references/session-binding.md`
- `bundle-manifest.json` 仅更新上述四个载荷的 SHA256；其余四文件与改前清单一致
- `make check`：Payload verified 8 files, `0.1.0.dev8`；184 tests OK

## 问题与风险

未发现阻塞缺陷。`make check` 通过。以下事项未关闭：

- 这是实施者自检，不是独立 Review。
- 未执行真实 SSH，未碰 `~/.local/state/grok-cc`、原 CC 或安装副本 `~/.agents/skills/grok-cc`。
- 用户随后要求改版本号。源码现为 `0.1.0.dev8`。active Skill 仍是旧安装，不会自动变成这版行为。
- 工作区里既有的 `AGENTS.md`、`docs/engineering/engineering-invariants.md` 以及未跟踪的 handoff、学习卡、`docs/review:requirement/`、`.playwright-mcp/` 不属于本轮。

## 事实偏差 / 遗漏

无。语义拒绝（无 `end_turn`、候选歧义、绑定漂移）仍用原类别，不套 SSH 的四类 `diagnostic.kind`。`jsonl_read_failed` 只用于 SSH 已结束之后的搜索、权限或投影解析失败。

## 摘要

`read_final_candidates` 把超时标为 `unreachable` / `timeout`，握手未完成标为 `unreachable` / `handshake_failed`，主机密钥验证失败（含退出码 255 的 host key verification）标为 `identity_changed` / `host_key_mismatch`。退出码 2、其他非 255 失败和 JSON 解析失败标为 `integrity_failure` / `jsonl_read_failed`，结果不包含远端 stderr。`StrictHostKeyChecking=yes`、`UpdateHostKeys=no`、`BatchMode=yes` 仍在。屏幕片段仍不能批准。

## 后续建议或待办

版本号已改为 `0.1.0.dev8`。安装仍须独立 Review 和明确的发布授权。本文件不授权提交、推送或安装。

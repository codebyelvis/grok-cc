# 执行计划与证据

作者：elvis。

- [x] 先补失败回归：大 user prompt 的投影不含远离窗口的正文，stdout 小于 50KB，end_turn 全文仍可回收；无标记旧 prompt 靠 `prompt_sha256` 命中；子进程超时断言为 240 秒。改前该测试 stdout 为 320998 字节，超时断言 90。
- [x] 瘦身 `RECOVER_REMOTE`，并把单次 SSH 超时改为 240 秒。尝试次数仍不超过 3。
- [x] 更新 SKILL、`references/session-binding.md`、`CHANGELOG.md`、`VERSION`、`bundle-manifest.json`。
- [x] `make check`：Payload verified 8 files, 0.1.0.dev11；188 tests OK。活动 skill 手术安装后 255 tests OK。保留 `archive_creation` 与 `retire_dead_binding`。
- [x] 对 `faae9e6a-f1ce-4355-bbc2-c4e1a62aa524` / `main` 跑一次真实 `recover-final-reply`。`action=recovered`，耗时 4.212 秒，`body_bytes=2480`。bindings 与 known_hosts 未变。未做 host_key 或 integrity 探测。

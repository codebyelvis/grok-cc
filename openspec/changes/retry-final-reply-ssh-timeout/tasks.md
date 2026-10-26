# 执行计划与证据

作者：elvis。

- [x] 核对活动安装已含 `_parent_link_record`。不把 attachment `integrity_failure` 混进这次 timeout 修改。
- [x] 先补失败回归：前两次 `TimeoutExpired`、第三次成功则回收；连续三次 timeout 为 `unreachable` / `timeout` 且 `attempts=3`；`host_key_mismatch` 只尝试一次；`OSError` 可重试；`jsonl_read_failed` 不重试。
- [x] 最小修改 `read_final_candidates`：`ConnectTimeout=20`，子进程超时 90 秒，最多 3 次，间隔 2 秒和 5 秒。不改 known_hosts 和 SSH 严格选项。
- [x] 更新 SKILL 与 `references/session-binding.md`：timeout 可内置短重试，勿与 attachment integrity 混修。
- [x] 更新 `CHANGELOG.md`、`VERSION` 与 `bundle-manifest.json`。
- [x] 跑对应 unittest 与 `make check`。不跑真实 SSH，不碰 registry、原 CC 或安装副本。`make check`：Payload verified 8 files, 0.1.0.dev10；187 tests OK。

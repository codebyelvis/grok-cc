# 执行计划与证据

作者：elvis。

- [x] 先补失败回归：四类 `diagnostic.kind`、stderr 不外泄、主机密钥失败为 `identity_changed`，超时与握手分开。
- [x] 最小修改 `read_final_candidates`。保持 `StrictHostKeyChecking=yes`、`UpdateHostKeys=no`、`BatchMode=yes`，不写 known_hosts。
- [x] 更新 SKILL 与 `references/session-binding.md` 的回收失败说明。屏幕片段仍不能批准。
- [x] 跑对应 unittest 与 `make check`。不跑真实 SSH，不碰 registry、原 CC 或安装副本。

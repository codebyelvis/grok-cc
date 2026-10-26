# 执行计划与证据

作者：elvis。

- [x] 先补失败回归：`attachment` 位于已受理 user 与最终 assistant 之间时可以回收；投影不得包含 attachment 或文件快照正文；父链回到另一条 user，或中间 uuid 缺失时仍拒绝且不写出文件。
- [x] 最小修改 `RECOVER_REMOTE` 与 `_final_text` 的记录校验。只增加链接字段，不放宽 end_turn、marker、并列分支或屏幕批准。
- [x] 更新 `references/session-binding.md` 的投影与父链说明。SKILL 回收段没有重复投影合同，未改。
- [x] 更新 `CHANGELOG.md`、`VERSION` 与 `bundle-manifest.json`。
- [x] 跑对应 unittest 与 `make check`。不跑真实 SSH，不碰 registry、原 CC 或安装副本。`make check`：Payload verified 8 files, 0.1.0.dev9；186 tests OK。

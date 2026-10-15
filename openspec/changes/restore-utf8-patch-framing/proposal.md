# Change: 恢复 UTF-8 补丁的原始行边界

作者：elvis。

## Why

当前 `scripts/task_packet.py` 用 `str.splitlines()` 解析 unified diff，把换页符、裸 CR、U+2028 等文件内容误当补丁换行，导致 Git 本可应用的合法补丁被拒。实际 `check` CLI 还用通用换行读取回复，可能在解析前改变裸 CR/CRLF 字节。这违背既有 UTF-8 文本修改/新增合同。

本轮经用户批准，已通过原 CC 对公开源码单次只读审查，收到这一条 P2 发现；随后用真实临时文件及 Git 核实，9 类内嵌字符均被 Git 接受但被当前 helper 拒绝。云端未修改文件、未运行测试；本地复现不能代替修复后验收。

## What Changes

- 在原 helper 内恢复与 Git 一致的 LF 补丁分帧，保留 hunk 内的 UTF-8 内容及既有 CRLF 补丁兼容；不清洗或重写补丁载荷。
- `check` CLI 按 UTF-8 原字节读取回复，避免通用换行转换；以真实 CLI prepare/check、Git 检查和应用验证。
- 必要时仅修复同一行边界问题造成的任务标记误判；须先有独立失败回归，不泛化标记规则。
- 补充回归，更新版本及受影响的载荷哈希，记录修复原因。
- 保持任务标记唯一/完整、文件白名单、基线、symlink、hunk 计数及真实 Git 检查。

## Impact

产品文件仅限 `scripts/task_packet.py`、`scripts/tests/test_task_packet.py`、`VERSION`、`bundle-manifest.json`、`CHANGELOG.md`，以及 `README.md`/`README.en.md` 的版本徽标元数据；提案位于本 change 目录。无新依赖、命令、packet/registry schema、身份或生命周期能力。

不改 `session_binding.py`、Skill 自然语言流程、ai_app、云端工程、网络、Clash、Tailscale、认证、模型、hooks、原生配置或现有绑定。不重放已完成任务，不再调用云端生成补丁。

## Approval and Delivery

用户已明确批准 `restore-utf8-patch-framing`。本轮交付顺序为 RED → 最小修复 → GREEN/整包检查 → 独立 Codex Review → 精选提交/推送 → hosted CI → 最后按已发布 revision 更新本地 Skill并独立复核。GitHub 推送与本地更新沿用用户本轮已有授权。

Tailscale 历史间歇断连为既有外部限制，本修复不宣称解决网络稳定性。

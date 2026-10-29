# Sticky draft clear — Preflight

记录：elvis。审核证据来源：独立 Codex `/root/sticky_draft_preflight`，未参与实现。

## Assignment and result

目的：源码候选实现前的合同、计划和权限预审；产品 codex，角色 independent-reviewer，
profile control-plane-high，实例须区别于主控/实现 `/root`，结果权限仅 governed-review-evidence。
Router local governed variant 适用：审实际未提交文件，不派发云端、不修改工作文件、不执行未授权 Git。

```yaml
review_mode: FULL_PREFLIGHT
attempt: 1
lineage_root_revision:
  path: docs/superpowers/plans/2026-10-28-sticky-draft-clear.md
  sha256: f94855029a41e9cc250a7c2bf0eb72b1486664dea2b5df2bfce835bea746303d
reviewed_revision:
  path: docs/superpowers/plans/2026-10-28-sticky-draft-clear.md
  sha256: f94855029a41e9cc250a7c2bf0eb72b1486664dea2b5df2bfce835bea746303d
parent_review: null
reviewer_identity:
  product: codex
  role: independent-reviewer
  capability_profile: control-plane-high
  instance: /root/sticky_draft_preflight
same_reviewer_instance: true
protected_boundaries:
  - source-only; mock Orca with temporary project/state
  - no real Orca/SSH/cloud/shared registry/global config
  - no add/commit/push/reset/clean/install/publication
declared_correction_set: []
mechanical_self_check:
  actual_artifacts_inspected: true
  openspec_strict: PASS
  old_critical_regressions: 3 PASS
  isolated_baseline_probe: PASS
  git_diff_check: PASS
finding_completeness: true
blocking_findings: []
non_blocking_recommendations: []
accepted_residual_risks:
  - real terminal effectiveness remains unverified; owner is subsequent authorized runtime validation
  - explicit confirmation may delete real draft; concurrent manual input is not fully locked
result: PASS
```

主控核对计划 SHA 与上表一致并签收，仅允许按既定合同进入 RED/实现。
非提交 clear 回执不借用 `_accepted` 的模型阶段要求；它可能只有 send.accepted 和 runtime，
必须独立验 accepted/身份并读回，缺/拒绝/未知结果不盲重试。

## Reference-consumption RED

独立 reviewer 读取旧版 SKILL/reference 后对三个恢复场景的演练结果：

| 场景 | 旧版可选择动作 | 缺口 |
| --- | --- | --- |
| JSON draft 非空、❯ 空、尚未授权 | 保留草稿，原绑定只读核对，停止 send/finish | 没有清理命令 |
| 随后明确授权清理 | 报告 helper 无此能力，不拼控制字符绕过 | 无确认参数、算法或重验流程 |
| 两次清理后仍粘 | 停止，不自动关闭或换绑 | 无两次协议/sticky_draft 决策 |

独立隔离探针确认旧 finish 抛 `ValueError("Input screen/draft cannot be verified")`，
registry 原字节不变、零额外 send；clear_draft 不存在，clear-draft CLI 返回 invalid_input。
这是文档/接口缺口证据，不把未知草稿识别成 ghost，也不执行真实恢复。

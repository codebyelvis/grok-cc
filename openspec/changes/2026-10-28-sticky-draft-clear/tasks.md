# Tasks

作者：elvis。主控：Codex /root；授权来源：本轮用户明确要求源码修改、隔离测试及待批准交付。

- [x] 读取规则、代码、现有 OpenSpec、版本/清单；核对分支/worktree，保留原工作区残留。
- [x] 新建 `feat/sticky-draft-clear` worktree；基线 make check 193 项通过，无载荷漂移。
- [x] 对照 Orca 上游指定提交；记录设计、规格和可执行计划。
- [x] 独立 Preflight PASS，记录旧 Skill 消费缺口。证据：docs/design/reviews/2026-10-28-sticky-draft-clear-preflight.md；计划 SHA f94855029a41e9cc250a7c2bf0eb72b1486664dea2b5df2bfce835bea746303d。
- [x] 新增失败回归并确认 RED；最小实现结构化阻断和显式 clear-draft。20 项 focused：旧实现 1 failure/27 subtest errors（缺入口/旧 ValueError/CLI 分类），最小实现后 20/20 通过。
- [x] focused GREEN、Skill/reference 决策表与消费复验、CHANGELOG/dev13/四文件 hash。独立三场景消费通过；初次 20/20，补审核反例后 22/22。
- [x] make check、OpenSpec strict、diff/边界检查及独立完整 diff/行为反例 Review。主控215/215；独立修正重审215/215及15个边界探针通过，无剩余finding；学习候选提升至reference/确定性回归，证据见Implementation Review。
- [x] 签收审核、新鲜最终核验；核对两工作区状态，交付未提交源码候选并等待用户授权。独立Final PASS、22项focused及18个额外探针通过；主控最终make check 215/215（16.681s），完整14文件审核指纹核对通过。收尾证据：docs/design/reviews/2026-10-28-sticky-draft-clear-final.md。

初次源码交付时未授权：add/commit/push、发布、安装、真实终端/共享 state 操作；不自动归档本 change。

## 2026-10-29 Git 授权增量

用户已明确“授权git操作”，并指定“不需要维护多个分支 main就行”，随后要求“继续”。
本仓库现有主分支为 master，本次按该现有主分支收敛：仅暂存本变更15文件，
中文 Conventional Commits 提交后 fast-forward 合入 master，正常推送 origin/master。
成功后删除本轮 feat/sticky-draft-clear；开发 worktree 可保留 detached 以便核查，不维护功能分支。
原主工作区既有修改及历史 worktree 不纳入提交、不丢弃或清理。
此增量不授予 force-push/reset/clean、源码发布、安装、真实终端/共享 state 或全局配置权限。
Git 结果以本变更提交及 origin/master 的实际 SHA 核验为准；初次交付记录保留历史时点。

## Verification evidence

- 基线：make check 193 tests OK，八文件 manifest 通过；所有现有开发分支均已并入 master。
  旧 resilience worktree 另留未跟踪 proposal 草稿；现行已跟踪提案明确它是保留的未批准旧稿，不含产品实现，不续接或覆盖旧草稿。
- 初始 RED：20 项 focused，1 failure/27 subtest errors；原因是旧 ValueError/缺 clear_draft/CLI 旧分类。
- 初始 GREEN：20 focused OK，make check 213 tests OK；独立实现初审额外两个反例为 FAIL，不能升级为验收通过。
- 审核修正 RED：22 focused，20 个失败子例（16 个完整性标志反例、3 个读回故障和1个 busy 断言）。
- 审核修正 GREEN：22 focused OK；make check 215 tests /16.901s OK；OpenSpec strict、diffcheck 通过。
- 最终交付：reference旧confirm说明冲突已修正；主控fresh make check 215 tests /16.681s OK，独立Final PASS（22 focused、18额外探针）；全部发现闭环。原主工作区残留保留，本worktree 7改动+8新文档未暂存/提交，下一步等用户授权。
- manifest：八文件清单原字节未变；只改 SKILL.md、references/session-binding.md、scripts/session_binding.py、scripts/tests/test_session_binding.py 四个 SHA256，另外四个与基线一致。VERSION/manifest 为 0.1.0.dev13。
- 真实 Orca、云端/SSH、共享 state、安装、全局配置及 Git 暂存/提交/推送未执行；本轮证据只覆盖源码候选和隔离外部替身。

## 新增测试名

全部位于 `scripts/tests/test_session_binding.py`，22 项，外部仅 mock Orca。

```text
test_sticky_draft_send_reports_nonempty_metadata_without_sending
test_sticky_draft_finish_reports_metadata_and_keeps_task_open
test_sticky_draft_preview_is_read_only_without_lock_or_send
test_sticky_draft_preview_without_binding_creates_no_state
test_sticky_draft_confirm_burst_counts_logical_lines_without_enter
test_sticky_draft_large_input_caps_first_burst_at_forty_lines
test_sticky_draft_clear_and_later_body_are_separate_writes
test_sticky_draft_second_maximum_burst_can_succeed
test_sticky_draft_two_failed_bursts_stop_without_finish
test_sticky_draft_busy_rejects_clear_without_send
test_sticky_draft_already_empty_confirm_does_not_send
test_sticky_draft_clear_then_finish_preserves_history_and_attempts
test_sticky_draft_non_auto_or_unreadable_screen_never_clears
test_sticky_draft_identity_drift_prevents_clear
test_sticky_draft_unknown_or_rejected_clear_does_not_retry
test_sticky_draft_empty_json_with_residual_composer_cannot_succeed
test_sticky_draft_clear_accepts_only_exact_empty_placeholders
test_sticky_draft_unresolved_message_blocks_confirmed_clear
test_sticky_draft_busy_after_first_clear_prevents_second_burst
test_sticky_draft_incomplete_screen_never_proves_clear
test_sticky_draft_readback_failure_is_not_retryable_after_clear
test_sticky_draft_cli_block_inspect_confirm_and_finish
```

# 2026-10-19 项目学习签收

作者：elvis。仅蒸馏 grok-cc 本项目；不推广为全局 Skill 或共享治理规则。原始记录和批准见[会话归档](../handoffs/2026-10-19-local-closeout.md)及两个 change 的 tasks；本页不迁入聊天、原始审核报告或私有任务材料。

2026-10-19，本轮已绑定 Codex 主控核对实际十份文件与独立学习 Review 后签收以下三个项目内提升。Review 由不同实例执行，结果 PASS、无可操作发现；报告 SHA256 `42878bda13fa8d7f8606a09878e49e3c613a43f2256137ab37e91e561cc42b47`，受审完整差异 SHA256 `826d8b65c8f9f7852fc2c486df95c3a6e8e4c4a89db81dbff3e774c34f209ec1`。此处是主控签收，Reviewer 未自授提升或最终完成；后续最终验证和单独 Final Review 以 resilience tasks 第6节为准。

## LC-1：完整意图、任务快照和候选占用一起构成创建证据

```yaml
status: promoted
event_kind: integrity
severity: high
scope: project-local
promotion_trigger: explicit-archive-distill
symptom: Invalid creation evidence could become bound; reduced prior-task snapshots allowed replay, and another owner pending candidate was ignored.
prior_assumption: A valid create receipt or merely retaining some history was sufficient for ownership and cumulative task limits.
correction_or_evidence: Independent IR-1 and IR-3 probes reproduced task replay and candidate conflict; separate author regressions first failed and then rejected them. Full selector and malformed inventory faults were also reproduced.
generalized_invariant: A binding transition preserves the exact intent, complete prior tasks, cumulative limits and exclusive candidate ownership; unknown creation never submits again.
independent_reproductions: Author RED/GREEN and independent implementation probes; separate Final probes interrupted after reservation and introduced ownership during verification.
independence_rationale: Review instances were distinct from the executor and executed real isolated Registry/CLI paths with only the Orca boundary doubled.
duplicate_or_conflict_result: Consolidates the two existing design candidates and approved creation contract; no changed behavior or reset exception.
target_artifacts: docs/engineering/engineering-invariants.md; docs/adr/0001-local-at-most-once-create.md; references/session-binding.md; scripts/tests/test_session_binding.py
mechanical_enforcement: required
mechanical_enforcement_reason: Existing explicit recovery, candidate ownership, archive replay, no-op rebind and process concurrency regressions reject the prior wrong behavior.
verification: 2026-10-19 archive make check passed 77 binding plus 35 packet; 23 named regression methods resolved, both active changes passed strict validation. Independent learning Review PASS; report fingerprint above.
review_result: pass
decision_owner: codex
decision_provenance: User explicitly requested repository-local archive and distillation; historical design cards remain unchanged and their old status does not grant this promotion.
```

## LC-2：字节完整性与来源/业务验收不能互相替代

```yaml
status: promoted
event_kind: correction
severity: medium
scope: project-local
promotion_trigger: explicit-archive-distill
symptom: Line splitting, newline conversion, echoed framing or legacy fallback could hide malformed patch evidence; a valid hash could be overstated as business acceptance.
prior_assumption: Text-equivalent patches and one apparently complete candidate were adequate, or a cloud result could replace the Mac baseline.
correction_or_evidence: Existing real CLI and Git regressions preserve raw CR/CRLF and non-LF payload; corrupted hashed, duplicate and truncated candidates reject before apply.
generalized_invariant: Validate exact diff bytes, unique intact framing, original packet scope and all baselines before native Git checks; keep model output and Mac business acceptance separate.
independent_reproductions: Original byte-framing repair and later independent source/Final review exercised distinct parser and artifact faults.
independence_rationale: Native Git and filesystem behavior were actual local operations; remote model claims were not used as acceptance.
duplicate_or_conflict_result: Restates existing utf8-patch-validation and quota contracts; no broader media or secret detection promise.
target_artifacts: docs/engineering/engineering-invariants.md; references/final-patch-prompt.md; scripts/tests/test_task_packet.py
mechanical_enforcement: required
mechanical_enforcement_reason: Existing byte-preservation, damaged hash, legacy downgrade, budget and media regressions reject the prior assumptions.
verification: 2026-10-19 archive make check passed all 112 including 35 packet tests; all 51 relative links resolved and no payload changed. Independent learning Review PASS; report fingerprint above.
review_result: pass
decision_owner: codex
decision_provenance: Explicit archive-distill request, existing accepted byte-framing history and current source tests; no new product behavior.
```

## LC-3：源码、发布、安装、窗口消费与真实远端分层取证

```yaml
status: promoted
event_kind: false-pass
severity: medium
scope: project-local
promotion_trigger: explicit-archive-distill
symptom: A local feature commit existed while master and shared installed files were still old; a connected screenshot did not show CC creation or sending.
prior_assumption: Local commit meant local Skill updated, or matching installed files meant existing windows had consumed the new rules.
correction_or_evidence: Actual path/hash inspection separated branch, master and installed state; explicit user local-update authorization then produced fixed-commit installation with preserved links and backup.
generalized_invariant: Report each layer only from its own evidence; runtime updates use fixed payload and accepted preimage, while old-window consumption and remote acceptance remain separate facts.
independent_reproductions: Executor and independent installation reviewer checked actual 8-file parity, 112 active tests and both entry probes.
independence_rationale: The reviewer did not perform the copy and independently ran installed tests; no native model or cloud probe was represented by fixture results.
duplicate_or_conflict_result: Default publication-before-install rule remains; the specific user-authorized local update is recorded as a one-time scope decision.
target_artifacts: docs/engineering/engineering-invariants.md; docs/handoffs/2026-10-19-local-closeout.md; docs/installation.md
mechanical_enforcement: required
mechanical_enforcement_reason: Existing make verify-payload plus the documented read-only multi-root hash check enforce file parity; existing ensure/CLI tests enforce zero implicit creation. Run a real mismatched-root negative control when validating the documented check.
nonmechanical_boundary: Native window rule consumption and remote publication cannot be inferred from local files. Offline enforcement is infeasible; adversarial Review must reject a parity-PASS report that also claims hot reload, publication or E2E without their actual evidence.
verification: Historical install acceptance SHA256 2878c1e3b7c92c167d4fe5e17c3a5a3d8610131dc57ec939f56e1f9b4faad78a. On 2026-10-19 the exact documented code passed source/shared/Codex/Claude parity and rejected the real older master root with Payload mismatch; independent learning Review PASS. Native-window consumption, publication and real E2E remain unverified.
review_result: pass
decision_owner: codex
decision_provenance: Actual user correction and explicit archive request; source publication and other windows rule loading remain unverified rather than silently upgraded.
```

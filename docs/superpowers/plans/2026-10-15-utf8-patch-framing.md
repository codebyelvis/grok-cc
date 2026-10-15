# UTF-8 Patch Framing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans with its Router-governed variant. Steps use checkbox syntax; canonical contract progress remains in OpenSpec tasks.md.

作者：elvis。

**Goal:** 恢复合法 UTF-8 补丁从 CLI 读取到 Git 检查和输出的原字节语义。

**Architecture:** 在既有 task_packet helper 内修复 LF 分帧与通用换行读取。真实文件、真实 CLI 和 Git 证明旧版本失败及修复后可应用；保持全部原 guard。

**Tech Stack:** Python stdlib，Git，Make；Python 3.11/3.13，macOS/Linux。

**Spec:** `openspec/changes/restore-utf8-patch-framing/proposal.md`、`design.md`、`specs/utf8-patch-validation/spec.md`。用户已明确批准本提案。

## Global Constraints

- Product files: `scripts/task_packet.py`, `scripts/tests/test_task_packet.py`, `VERSION`, `bundle-manifest.json`, `CHANGELOG.md`; both README files only version metadata.
- No new dependencies, command/schema, binding/lifecycle/auth/network changes; preserve all existing guards.
- Worktree: `/Users/elvis/.codex/worktrees/grok-cc-utf8-20261015`, branch `fix/utf8-patch-framing`, base `daf80281169aaef821619e76d292ae3d0c888ffa`. Native task tool cannot choose the independent repository, so use a Git worktree here.
- User authorizes selected commit/push then active synchronization. No reset/clean/force push; no writes to ai_app or another task.
- Risk/evidence: strict. Root implements; `/root/repo_bootstrap_review` is independent Codex reviewer, control-plane-high, governed-review-evidence, distinct from root. Final Review uses a separate eligible Codex instance.

## Review Focus

- VT/FF/FS/GS/RS/NEL/U+2028/U+2029/inline CR in context and +/- lines: native Git accepted bytes must remain unchanged.
- Real CLI reply ingress: no universal newline conversion, including lone CR and CRLF.
- Already accepted CRLF structural headers: parser compatibility retained, no payload normalization.
- Marker-looking text after non-LF payload separators: not a separate task marker; true missing/duplicate markers remain rejected.
- Out-of-scope paths, malformed counts, baseline/symlink drift: still fail before checked output/project mutation.

## Task 1: Restore the existing patch validation chain

**Interfaces:** Existing `prepare(root, names, task)`, `check(manifest, reply) -> str`, `diff_paths(diff) -> list[str]`, and CLI prepare/check; no signature changes.

- [x] Add `test_non_lf_hunk_payload_checks_and_applies`: literal three-line source/context and changed payload, table of nine demonstrated characters. First native Git check must return 0; helper must return identical diff, checking must retain original/unrelated bytes, native apply must produce expected bytes.
- [x] Add `test_cli_preserves_patch_newlines`: invoke actual prepare/check using `sys.executable`, external packet/reply/output files, raw CR and CRLF fixtures (LF or CRLF structural headers). Assert exact output bytes, no source mutation by check, and exact native apply result.
- [x] Add `test_markers_use_patch_line_boundaries`: valid hunk contains marker-looking text after U+2028, proving whether current marker parsing falsely counts it; retain missing/duplicate real marker negatives.
- [x] Run RED: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -p test_task_packet.py -v`. Verify failures come from production line splitting/newline conversion, not fixture errors.
- [x] Minimum fix: LF-only structural parsing; strip optional terminal CR only from parser syntax views, never returned diff; CLI reply uses explicit UTF-8 decoding without newline conversion. Change marker framing only when its regression is RED.
- [x] Run the same packet tests GREEN. Existing negative tests remain unchanged.
- [x] Set VERSION/manifest/version badges to `0.1.0.dev1`, update only two changed payload hashes, record mechanism and real-Git/CLI regression in CHANGELOG.
- [x] Run `make check` and official Skill `quick_validate.py` (using existing PyYAML cache, no install); strict OpenSpec validation. Search changed files for unintended normalization/guard changes, inspect full diff.
- [x] Independent Implementation Review inspects complete diff and actual files, reruns critical tests, probes an adversarial marker/hunk or scope case. All actionable findings return to same-scope fix/verify/review.

## Task 2: Publish, synchronize, and close

- [ ] Preserve approved proposal preimage outside checkout; reconcile source checkout's own untracked proposal before a fast-forward merge. Verify no source drift. Stage only approved product files and this change's governance artifacts, using Chinese Conventional Commit with grouped body and elvis author.
- [ ] Push exact reviewed revision to existing origin/master, no force; verify remote and all four existing CI jobs.
- [ ] Use official skill-installer to download that exact revision into a new private staging directory; `make check` there. Preserve active payload preimage, permissions and entry links; compare accepted baseline immediately before update.
- [ ] Sync only reviewed bundle files after successful source push/CI, preserving registry and native configuration. Run active suite and Skill validator; check both Codex/Claudex entry targets and all eight hashes.
- [ ] Independent Final Review checks source/remote/CI/staging/active evidence and actual complete diff, reruns critical evidence and an independent boundary probe.
- [ ] Reconcile OpenSpec tasks, archive only once required delivery gates pass, validate archived artifacts; publish any necessary documentation-only closeout, verify corresponding source/active parity.

## Rollback and Stop

Keep published base and private active preimage. Stop overwrites on concurrent source or active drift; never discard unknown edits. Recovery uses retained preimage only within authorization and only if current files still match this upgrade. Any requirement beyond this approved contract returns to scope review. A failed/missing test, Review or CI is not completion.

Private logs/packets/receipts stay outside Git. No repeated cloud invocation is needed: its original static Review is complete and the original task was closed through the helper.

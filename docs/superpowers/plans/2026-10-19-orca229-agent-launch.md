# Orca 1.4.229 Agent Launch Implementation Plan

> **For agentic workers:** Execute inline under the Router's current contract. The 2026-10-20 amendment below supersedes historical source/Git/installation exclusions. Real Orca mutations remain forbidden.

**Goal:** Prepare a source-only launch/replay compatibility candidate while preserving all existing uncertainty and ownership protections.

**Architecture:** Reuse the existing private registry and create reservation. Replace only the native startup boundary and receipt interpretation, add one explicit native-ID replay, and retain all post-launch terminal checks. Do not introduce a second registry or runner.

**Tech Stack:** Python stdlib, unittest, local executable Orca fixture, existing OpenSpec CLI.

**Spec:** `openspec/changes/adapt-orca-229-agent-launch/design.md` and `specs/orca-agent-launch/spec.md`.

## Current execution amendment — 2026-10-20

Goal: publish/install approved plan (a), retaining the installed placeholder
prerequisite and related uncommitted safety regressions. Reuse existing master,
base `d094ffe`, and this OpenSpec change. Fixed cloud diff SHA256:
`05791a8e5f26cd11461c84e2ebba2e3f9895a7123076febdf0489db5305318b9`.
Its failed reference hunk is baseline wording drift; integrate reviewed source,
never force-patch the installation. Baseline make check: 131 tests PASS.

Allowed: helper/tests, SKILL/reference, troubleshooting/invariants/recovery
learning card, VERSION/CHANGELOG/manifest, this plan and existing change's
proposal/design/spec/tasks/status. Fixed eight-file payload; packet code/tests,
AGENTS and requirement drafts are outside edits. No global config, live state
or real cloud operations. Private source preimage and draft hashes are saved.

Controller/executor: Codex `mode-auto-controller`, control-plane/control-plane-high.
Preflight/implementation: Codex `mode-auto-implementation`,
independent-reviewer/control-plane-high; distinct from controller/executor;
purpose readiness then implementation safety; authority governed-review-evidence.
Final: Codex `mode-auto-final`, independent-reviewer/control-plane-high, distinct
from controller/executor and implementation reviewer; purpose final source,
publication and installation acceptance; authority governed-review-evidence.
Neither reviewer owns transitions/completion or authorizes a real-instance test.

### Amendment task 1: Source integration and regression

Interfaces: preserve `BindingManager.create(confirm=False, retry_launch=None)`.
New records use `terminal.create.claude-auto.v1`; old agent records retain their
protocol. Reply is `result.terminal.handle` and `_meta.runtimeId`; saved outcome
has no operationId/retrySafe. No second registry/runner or new dependency.

- [x] Independent FULL_PREFLIGHT: plan/contract SHA, exact scope, existing branch,
  source/preimage/draft preservation, Git authority, isolation and rollback.
- [x] Add prerequisite and auto-path regressions before runtime edits. RED must
  show old code cannot bind prerequisite placeholders or submit the exact
  per-instance command. Legacy tests keep their original protocol; subprocess
  fixtures exercise the actual production default.
- [x] Minimum prerequisite and launch dispatch. Cover loss/timeout/bad reply,
  bypass/draft/identity refusal, legacy replay/no-ID, receipt-before-inventory,
  occupancy and concurrency. Preserve retained tests even above expected136.
- [x] Synchronize docs/version0.1.0.dev5 and reviewed payload hashes. Run
  `make check`, `openspec validate adapt-orca-229-agent-launch --strict`, and
  `git diff --check`. Inspect complete diff and stale launcher claims.
- [x] Independent implementation Review reruns critical checks and one
  adversarial temporary-state probe. Findings require RED/GREEN and re-review.

### Amendment task 2: Publish and activate

- [x] Resolve project learning in existing recovery card/invariant/test mapping.
- [x] Fresh final source verification and distinct final Review of actual full
  diff, learning/sensitive scope and an independent safety probe.
- [x] Stage only reviewed paths, Chinese Conventional Commit without coauthor,
  verify staged contents, normal push to existing `origin master`. Refuse remote
  divergence; no force, reset or clean.
- [x] Existing skill installer fetches the fixed published revision into private
  staging; run `make check`. Preserve installed bytes/modes/inventory/aliases
  outside discovery and reject source/preimage drift.
- [x] Existing rsync copies only eight manifest files, without delete. Verify
  actual aliases, hashes, nonpayload and installed unittest; final reviewer
  independently checks installation and claim boundaries.
- [x] Reconcile status/tasks and prepare source-frozen closeout metadata for
  scoped publication. Final Git/CI receipt must be checked after execution.
  Real new-instance verification awaits user.

Rollback: source preimage and accepted install preimage are retained privately.
Restore only after no-later-drift checks within explicit rollback authority;
never discard unknown work. Stop on changed protected scope, incompatible native
contract, required new permissions, remote divergence, source/install drift,
sensitive content or failed Review. Existing pending recovery stays deferred.

Acceptance: source2152650 normally published, remote SHA verified and CI4/4
success. Controller/source/stage/installed suites each139 PASS, distinct source
and installation Reviews PASS. Only eight reviewed payload files activated;
nonpayload, modes and both aliases preserved. The final administrative commit
has parent2152650 and exactly status/plan/tasks/recovery-card paths; inspect Git
history before repeating it. Its actual remote SHA/CI receipt is checked after
commit/push, outside these self-referential bytes. The payload stays fixed and
requires no reinstall for this metadata-only commit. Three original requirement
drafts remain excluded, unchanged and owned by their original task.

The sections below are historical records, not current exclusions.

## Global Constraints
- Baseline: `4ea6ddb8307bbb99ee6ad2efc4833094d59b4c6a`; isolated detached worktree only.
- No active installation, real registry, native config, secrets, real Orca, Bot or CC calls.
- Legacy pending without operationId stays unchanged. No fallback terminal create.
- Native error messages/payloads are not safe diagnostics. Replay is explicit and capped at one.
- Structured chats and non-auto terminals are not supported send surfaces; retain pending.

## Review Focus
- A stdout JSON error can carry sensitive launchRequest/recoveryCommand fields beside a valid operationId.
- A lost receipt can occur before any operationId survives; never mint one locally to bypass it.
- New runtime, executable, cwd or selector must not retarget a replay.
- Native terminal outcomes lack an incarnation; derive it only for the exact receipt-bound handle from complete inventory.
- Another owner or concurrent late receipt must not overwrite or claim a pending outcome.

### Task 1: Launcher and receipt boundary
Files: `scripts/session_binding.py`, existing `scripts/tests/test_session_binding.py`.
Interfaces: `BindingManager.create(confirm=False, retry_launch=None)`; minimized `creation_launch` in the existing row; `NativeFailure` safe diagnostic and launch-evidence projection.
- [x] Add failing tests for agent launch without prompt/settings, native receipt-before-read, structured/non-auto refusal and stdout error minimization.
- [x] Run focused tests and confirm failures are missing behavior, not fixture errors (76 of 85 RED under new protocol).
- [x] Implement the public launcher, matching-runtime capability gate, finite process budget and exact-handle verification.
- [x] Run existing binding tests, preserving their safety assertions under the new native envelope.

### Task 2: Bounded replay and regression
Files: same helper and test file.
- [x] Add failing tests for same-ID replay, persistence-before-replay, changed destination/runtime/cwd/executable refusal, legacy pending refusal and one-replay exhaustion.
- [x] Implement explicit replay only; keep known-success verification read-only.
- [x] Exercise the real helper CLI through a local executable fixture and replay ledger, plus existing concurrency tests (91 binding tests GREEN).

### Task 3: Reference and source-candidate validation
Files: `SKILL.md`, `references/session-binding.md`, troubleshooting/invariants, version/changelog/manifest, this change's artifacts.
- [x] Record reference application baseline: old guide cannot express native launch replay; legacy pending must still block.
- [x] Update the reference recipe and run the same application probe with the new documents (`/root/orca229_reference_probe`: PASS, bounded evidence only).
- [x] Set candidate version `0.1.0.dev4`; recompute only reviewed payload hashes in the existing eight-file manifest.
- [x] Run `make check` (126 PASS); `openspec validate adapt-orca-229-agent-launch --strict` (valid); `git diff --check` (clean). Final verification follows review corrections, if any.
- [x] Distinct reviewer reruns critical tests and one adversarial probe. Resolve findings and repeat relevant verification/review (P1/P2 RED/GREEN, re-review129 PASS; source-only findings closed).
- [x] After learning promotion, fresh final verification and separate final source Review; keep the historical isolation exception explicit (numeric finding corrected; 129 PASS and final re-review PASS).
- [x] Report source preparation only, with installed/real-cloud acceptance explicitly pending in the source status; final handback retains the exception and uncommitted scope.

## Rollback And Stop
All candidate edits remain in this isolated worktree; baseline and other worktrees remain intact. Keep uncommitted candidate files for review. Stop on native contract ambiguity, required settings changes, a need to migrate legacy state, or a request to activate the candidate. Any rollback is a reviewed patch operation, never reset/clean.

## Authorized follow-up: local activation and read-only check

The user has now explicitly approved activation of this local candidate and read-only cloud/pending checks. This follow-up supersedes the earlier stop-on-activation boundary only for the frozen candidate; all source and real-task exclusions remain.

- [x] Prepare private installed preimage, inventory/permissions/links, immutable eight-file local stage and registry hash-only read evidence; refuse drift. Use existing rsync, no new installer.
- [x] Independent installation-readiness review of pinned source, preimage and bounded copy/verification/rollback steps (FULL_PREFLIGHT PASS).
- [x] Recheck preimage immediately; synchronize only manifest files, no broad deletion or link/config changes. Preserve before bytes for guarded rollback.
- [x] Validate installed hashes and all existing aliases, run installed unittest suite129 PASS and help smoke, then reload this window's installed Skill.
- [x] Read-only native status attempts and legacy pending verification completed; registry unchanged. Both cloud checks returned remote_runtime_unavailable, so terminal census is unavailable rather than verified. Send no input and create/replay nothing.
- [x] Independent installation/evidence acceptance and final scope check (Codex `/root/orca229_final_review` PASS, independent installed suite129 PASS); cloud unavailable and legacy pending limitations retained. No genuine task acceptance claimed.

## Source integration preparation follow-up

The retained16 files can form one local candidate commit on their current base. Fresh make check129 PASS (6.529s), strict validation and diff check pass. Master is two existing prerequisite commits behind that base; retain their ancestry rather than copying the16-file delta directly onto master.

- [x] Verify current tree, base/master ancestry, frozen installed payload parity and exact retained scope; prepare an external file snapshot/manifest and Chinese commit message for review.
- [x] User approved local staging/commit and selected no new branch, existing master only; replace the proposed new-branch step with a detached candidate commit followed by a master fast-forward. Preserve the two prerequisite commits and the original root's three untracked files.
- [x] Independently preflight candidate/master hashes, exact16 paths, ancestor relation and untracked-path noncollision (FULL_PREFLIGHT PASS, finding_completeness=true). Refuse staged/concurrent drift or non-fast-forward; use no reset/clean, branch deletion or remote write.
- [x] Stage only16 candidate files in the detached source worktree, inspect the complete staged diff and create one Chinese Conventional Commit using the existing author elvis (4f25828). Anchor it by `git merge --ff-only <new-commit>` in the original root on existing master; create no branch (executed).
- [x] Verify both worktrees, original untracked file hashes, exact commit paths/parent and eight-file installed parity; run main-root make check129 PASS (6.198s) and all three applicable active-change strict validations (valid). In original root/master, update only `docs/agent-collab/adapt-orca-229-agent-launch/status.md`, this plan and `openspec/changes/adapt-orca-229-agent-launch/tasks.md` with actual results, then obtain independent integration/closeout acceptance of the actual files and complete diff (Codex `/root/orca229_final_review` PASS, no actionable finding).

Final bounded Git action after independent acceptance: stage only those three canonical documents and create one Chinese docs closeout commit on existing master. Verify its exact three paths and unchanged parent runtime tree, all active strict validations/diff checks, existing branch-ref set and original three untracked file hashes. Original master must have no tracked residue; detached source stays clean at4f25828. Preserve other existing branches/worktrees and the shared installed payload. Actual final HEAD and execution receipt are checked after committing and retained privately in `~/.local/share/grok-cc-integration-prep/20261019-master-y_1kk270/`; do not invent a self-referential commit hash or repeat this action without inspecting Git history.

Remote screenshot investigation runs independently using systematic-debugging, orca-cli and read-only local Tailscale/DNS/TCP probes. At13:58 local Tailscale is healthy, the Grok peer reports offline (LastSeen12:40), ping/TCP6768 time out and Orca reports remote_runtime_unavailable. This is network-path evidence, not a proven VM-freeze cause. Request one bounded cloud-side Bot report; do not change pairing, services, firewall, native settings, registry or CC sessions. No automatic Bot-model calls, extra polling or unrelated infrastructure investigation.

The user supplied the requested Bot report at14:04:02: cloud Tailscale Running but Self.Online=false, Orca1.4.229 still listening6768, watchdog PID alive but state last updated13:25:28; the last confirmed time-jump is13:29:04 for3m20s. Cloud process/listener state and the report's timing are user-relayed evidence, not fresh Mac validation or proof of a39-minute freeze. Obtain one targeted read-only process wait-point report to distinguish an actually blocked child from prior suspension before proposing a watchdog/network fix.

That report was received:14:09 samples show normal sleep300, state14:06:44 and logged automatic TERM/bootstrap/online recovery. Mac retest14:10 independently confirmed peer online, TCP6768 and Orca runtime/graph ready, exact hello metadata access and complete0-terminal inventory. No real create/send/replay/rebind, service/network/config change or automatic Bot-model request was made. Sustained stability and freeze trigger remain unverified. Desktop visual check failed at tool bootstrap (NODE_REPL_TRUSTED_SERVICES unavailable); no GUI action or workaround. Resume genuine usage only under existing identity/creation gates.

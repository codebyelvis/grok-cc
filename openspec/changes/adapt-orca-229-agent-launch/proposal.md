# Orca 1.4.229 agent launch compatibility

作者：elvis。

## Why

The version-matched Orca 1.4.229 guide starts agents through `agent launch`, not a shell command in `terminal create`. Its public replay contract carries an operationId. The existing helper both misses that contract and discards safe native failure classification when a creation fails. A legacy unknown creation cannot be recovered by guessing ownership.

## What Changes

- Keep explicit `create --confirm`, but invoke `agent launch --agent claude` without a prompt, model, effort or settings change.
- Persist minimized native launch identity and safe diagnostics in the existing private registry; bind only a verified Claude auto terminal.
- Add an explicit, single `create --confirm --retry-launch <saved-operationId>` replay for a new-protocol unknown launch on its original runtime, destination, executable and local working directory.
- Preserve legacy pending records without an operationId, including after a runtime upgrade. Structured-chat outcomes remain pending and cannot use terminal send.
- Update the existing skill reference, regression tests and payload manifest. Prepare source only.

## Scope And Approval

The user approved this source-and-isolated-test preparation on 2026-10-19 with “批准下一步”, following the concrete proposal to adapt startup, receipts and recovery while retaining pending, leaving the installed skill unchanged and creating no real sessions. This is the approved design boundary; no second design choice is introduced.

The base is committed source `4ea6ddb8307bbb99ee6ad2efc4833094d59b4c6a`, whose binding helper matches the installed helper. Work is isolated in a detached worktree. No merge, staging, commit, push, installation, real Orca invocation, registry edit, network change or model request is authorized in this implementation stage.

## Impact

Affected: `scripts/session_binding.py`, its existing tests, `SKILL.md`, `references/session-binding.md`, `docs/troubleshooting.md`, `docs/engineering/engineering-invariants.md`, `docs/learning-candidates/2026-10-19-orca229-execution-context.md`, `VERSION`, `CHANGELOG.md`, `bundle-manifest.json`, and this change's planning/evidence documents. Packet handling and other worktrees remain outside the change. The learning card records in-scope Review corrections and their enforced invariant; it does not change runtime or approval authority.

The source candidate does not resolve an already-lost receipt, prove a live cloud round trip, or establish continuous cloud availability.

## Authorized local activation follow-up

On 2026-10-19 the user explicitly approved: “批准从这份本地候选更新 grok-cc，并只读核对云端和旧 pending”. This authorizes a local unpublished-candidate installation exception to the usual publication-first order. The frozen eight-file manifest is the activation source; no source implementation change, Git mutation or remote publication is included.

Back up the installed payload/permissions/inventory/links outside discovery roots, reject source or preimage drift, synchronize only the eight files with the existing file-copy tool, verify actual runtime aliases and installed tests, and review acceptance independently. Cloud/registry checks are read-only. No create, replay, send, rebind, reset/delete, native configuration, service/network restart or Bot model request is authorized. Preserve the legacy pending and the earlier unknown-effects exception.

## Authorized source integration and diagnosis follow-up

The user subsequently approved staging/committing the retained16 candidate files and required no new branch, using one existing branch. The controller resolves this as a commit on the existing detached candidate followed by an ancestry-preserving fast-forward of original master. Both existing prerequisite commits remain unchanged. This scope supersedes the earlier Git exclusion only for those local operations; it does not authorize publication, branch/worktree deletion, reset/clean or unrelated files.

The same message requests investigation of remote Orca failing to load the cloud hello workspace. Diagnose read-only Mac-to-cloud connectivity and request minimal cloud-side facts when unavailable. No new behavior design, service/network/config mutation, pairing change, registry reset, create/replay/send/rebind or automatic Bot-model call is included. Preserve local-vs-cloud evidence boundaries and the earlier unknown-effects exception.

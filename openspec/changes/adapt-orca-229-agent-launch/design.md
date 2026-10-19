# Design

作者：elvis。

## Public boundary

Use the official 1.4.229 CLI contract verified before this source-only stage: `agent launch --agent claude --worktree id:<full-id>`, same `--environment`, with no launch prompt. The CLI chooses chat or terminal according to existing settings. Do not change settings to force a surface or permission mode. Preflight requires a matching ready runtime, version >= 1.4.229 and the agent launch/replay-required/background-presentation capabilities.

`result.operationId` and `result.outcome.{kind,handle}` are distinct from a terminal incarnation. A successful terminal receipt is saved before further remote reads; a complete inventory must then supply the exact handle's incarnation and Claude identity. Existing liveness, ownership, idle, empty-composer and auto checks remain mandatory. A structured outcome is retained as an unsupported surface, not converted or sent to.

## Reservation and replay

The existing creation_id remains a local reservation identity; never pass it as a native operationId. Resolve and pin the executable before the first native query, using the canonical project child cwd for both relative executable paths and relative PATH entries; preflight and submission must use the same absolute file. Save that executable and cwd with the reservation. Native subprocesses execute from that cwd. Native launch calls have a finite 180-second outer budget, accommodating the CLI's status and launch phases; there is no automatic mutation retry.

For a native unknown-result error, accept replay evidence only from the documented JSON error envelope with code `agent_session_operation_unknown`, data.launchOutcome=`unknown`, retrySafe=true, and a valid 13-digit-timestamp/32-lowercase-hex operationId. Do not parse an ID from prose, stderr tokens, recovery commands or arbitrary nested fields.

Only an explicit matching retry-launch on create+confirm may replay. Require the saved protocol, exact operationId, unchanged owner/project/worktree/environment/runtime/executable/cwd, no candidate or known successful outcome, no active/uncertain task, a complete inventory and supported runtime. Persist the replay intent before the one allowed replay. It reuses the native operationId and exact launch arguments; it never becomes a fresh launch. Unknown/expired/mismatched replay remains pending. Legacy no-ID pending never gains replay authority, even after restart or an empty inventory.

## Diagnostics

Extract error JSON from stdout (the public CLI JSON error channel), with stderr JSON only as compatibility input. Keep raw messages, source, launchRequest, prompt, recoveryCommand, nextSteps, native configuration and stderr out of output/state. Retain only locally enumerated failure kind, started flag, bounded integer returncode, finite timeout, known error code and validated launch identity. Preserve the safe reason across subsequent read-only recovery attempts.

## Isolation and evidence

The repository regression suite exercises actual private files, fsync, locks, concurrency and the real Python CLI. Only the external Orca process boundary is doubled; a local executable fixture implements documented envelopes and a replay ledger. Production state, real cloud processes, the installed skill and the real pending record are excluded from authorized test operations.

Fixtures use an absolute Python shebang and isolated child PATH plus an unavailable ORCA_CLI_COMMAND default. A missing or malformed selected fixture must fail locally rather than discover an installed Orca. Explicit null or malformed saved outcomes/diagnostics are integrity failures before any native query. The implementation Review's isolation exception is recorded in the change status and cannot be relabeled as a successful isolated probe or cloud acceptance.

Frozen baseline behavior unrelated to the new launcher is preserved. Existing tests that expect terminal-create envelopes must be translated to launch envelopes, preserving their safety assertions. Existing packet regressions remain unchanged. Source-only verification is not live Orca acceptance.

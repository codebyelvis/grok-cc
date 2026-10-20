# Design

作者：elvis。

## Public boundary

The 2026-10-20 approved amendment selects the public `terminal create --worktree id:<full-id> --command "claude --permission-mode auto"`, with the saved environment, for new reservations. Never pass bare `claude`: Orca can substitute global agent defaults. The full command scopes auto mode to the new instance without changing global/native settings. Preflight retains matching ready runtime, version >=1.4.229 and the existing capability checks; no fallback or runtime migration is introduced. Preview describes this terminal command.

Persist protocol `terminal.create.claude-auto.v1`; project only the safe `result.terminal.handle` under the matching `_meta.runtimeId` into a terminal outcome before further remote reads. This route has no native operationId or replay ledger. Complete inventory supplies the exact handle's incarnation and Claude identity. Existing liveness, ownership, idle, empty-composer and auto/no-bypass checks remain mandatory. Bad/lost results retain pending, even if the native process did not start; repeat confirm never starts another instance.

Saved `agent.launch.v2` reservations retain `agent launch --agent claude --worktree id:<full-id>`, the saved native operationId and original outcome interpretation. Structured outcomes remain unsupported and pending. Upgrade does not rewrite saved records or change surfaces/settings. Protocol validation prevents terminal-create records from gaining native-ID/retrySafe authority.

## Reservation and replay

The existing creation_id remains a local reservation identity; never pass it as a native operationId. Resolve and pin the executable before the first native query, using the canonical project child cwd for both relative executable paths and relative PATH entries; preflight and submission must use the same absolute file. Save that executable and cwd with the reservation. Native subprocesses execute from that cwd. Native launch calls have a finite 180-second outer budget, accommodating the CLI's status and launch phases; there is no automatic mutation retry.

For a saved agent-protocol native unknown-result error, accept replay evidence only from the documented JSON error envelope with code `agent_session_operation_unknown`, data.launchOutcome=`unknown`, retrySafe=true, and a valid 13-digit-timestamp/32-lowercase-hex operationId. Terminal-create failures never acquire this authority. Do not parse an ID from prose, stderr tokens, recovery commands or arbitrary nested fields.

Only an explicit matching retry-launch on create+confirm may replay. Require the saved protocol, exact operationId, unchanged owner/project/worktree/environment/runtime/executable/cwd, no candidate or known successful outcome, no active/uncertain task, a complete inventory and supported runtime. Persist the replay intent before the one allowed replay. It reuses the native operationId and exact launch arguments; it never becomes a fresh launch. Unknown/expired/mismatched replay remains pending. Legacy no-ID pending never gains replay authority, even after restart or an empty inventory.

## Diagnostics

Extract error JSON from stdout (the public CLI JSON error channel), with stderr JSON only as compatibility input. Keep raw messages, source, launchRequest, prompt, recoveryCommand, nextSteps, native configuration and stderr out of output/state. Retain only locally enumerated failure kind, started flag, bounded integer returncode, finite timeout, known error code and validated launch identity. Preserve the safe reason across subsequent read-only recovery attempts.

## Isolation and evidence

The repository regression suite exercises actual private files, fsync, locks, concurrency and the real Python CLI. Only the external Orca process boundary is doubled; local executable fixtures implement both terminal replies and saved-agent replay envelopes. Shared state, real cloud processes and existing pending records are excluded. Published-revision local installation is separately authorized by the amendment, with preimage/drift protection and actual installed-suite verification.

Fixtures use an absolute Python shebang and isolated child PATH plus an unavailable ORCA_CLI_COMMAND default. A missing or malformed selected fixture must fail locally rather than discover an installed Orca. Explicit null or malformed saved outcomes/diagnostics are integrity failures before any native query. The implementation Review's isolation exception is recorded in the change status and cannot be relabeled as a successful isolated probe or cloud acceptance.

Frozen baseline behavior unrelated to the new launcher is preserved. Saved-agent tests explicitly select their historical protocol; subprocess fixtures exercise the actual production default. Keep the accepted eight-placeholder prerequisite and reported-draft rejection, including the screen heuristic's ambiguity limitation. Retain source-only receipt/visible-marker regressions. Packet regressions remain unchanged. Source/installation verification is not live Orca acceptance; no real create/send is authorized.

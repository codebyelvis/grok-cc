## ADDED Requirements

### Requirement: Structured remote failure without unsafe resend

The helper MUST distinguish subprocess timeout, launch failure, nonzero exit and invalid result, and MUST emit a structured BLOCKED JSON with category and retryable. It MUST retain send intent on uncertain outcomes and MUST NOT infer non-delivery solely from remote error strings. Printed and persisted diagnostics MUST exclude prompt text, raw stderr and secrets.

#### Scenario: Process failed before submission could start

- **GIVEN** a durable send intent and positive local evidence that the subprocess never started
- **WHEN** that send fails
- **THEN** the message becomes not_sent with a bounded sanitized explanation
- **AND** a later explicit same-task, same-message, same-text send must pass identity, idle and concurrency checks before another submission

#### Scenario: Remote timeout or nonzero result is not delivery proof

- **GIVEN** a send subprocess started and then timed out, exited nonzero, returned malformed data or showed acceptance traces
- **WHEN** the caller repeats the send invocation
- **THEN** it returns the pending state without submitting again, and finish/new task/rebind cannot bypass the intent

### Requirement: Receipt minimization and legacy protection

The helper MUST persist only requestId, stages, processIncarnation, handle, runtimeId and accepted from remote receipts. Existing schema-1 records MUST remain readable without resetting ownership; legacy uncertain intents MUST remain uncertain.

#### Scenario: Receipt contains source or arbitrary nested fields

- **GIVEN** a response containing valid receipt identity plus extra source, stderr or nested content
- **WHEN** the message is persisted or returned
- **THEN** only validated allowlisted receipt fields are retained, with no raw response or source copied into the registry

### Requirement: Conservative read-only reconciliation

Reconcile MUST query only the saved bound destination and cursor and MUST NOT send, create or execute a shell. A stable message marker MUST NOT on its own prove acceptance; idle and absence of input MUST NOT prove non-delivery. The command MAY update local evidence when a saved valid receipt proves acceptance, but MUST retain the prior outcome when evidence is insufficient.

#### Scenario: Echo or empty stream after uncertain send

- **GIVEN** a pending send and either its marker in a composer echo or no new stream output while idle
- **WHEN** reconcile runs
- **THEN** the message remains pending with a reason, no model input is submitted and no new terminal is created

#### Scenario: Saved receipt proves accepted input

- **GIVEN** a pending message with a validated allowlisted receipt matching runtime, handle and process incarnation, a requestId, accepted=true and input_accepted
- **WHEN** reconcile revalidates the binding and current local intent
- **THEN** it may persist accepted without resending the message

#### Scenario: Official request retry contract is unavailable

- **GIVEN** no verified official offline request retry contract under this task's no-real-Orca restriction
- **WHEN** explicit request retry is requested
- **THEN** the helper reports unsupported_contract with retryable=false before any Orca call, including list/read/wait, and delivery does not claim this original requirement complete

### Requirement: Explicit safe rebind preserves history

Rebind MUST require explicit confirmed handle and incarnation and documented user approval. It MUST require an existing bound record, no active task or uncertain intent, the same worktree, a live writable non-orphaned claude terminal, auto mode, empty input and no conflicting current ownership. It MUST archive the old binding and task history, MUST NOT auto-select/create a target and MUST NOT delete or reset ownership.

#### Scenario: Confirmed unoccupied target is eligible

- **GIVEN** a user-confirmed exact target satisfying all checks and an inactive certain binding
- **WHEN** rebind verifies that registry and destination have not drifted
- **THEN** it archives the old binding and histories and updates the current binding without creating or sending

#### Scenario: Active or uncertain task blocks rebind

- **GIVEN** an active task, unknown create/send, occupied target, non-auto mode, draft, wrong worktree or changed incarnation
- **WHEN** rebind is requested
- **THEN** it fails without changing ownership, history or remote terminals

### Requirement: Budgeted lock-free read retries

Only list/read/wait MAY automatically retry classified transient errors using 2, 5, 15 and then capped 30 second waits within a configurable default 300 second monotonic budget shared by the whole command's read chain. Positive-budget call timeouts MUST fit the remaining deadline. Zero budget disables retries, but each necessary query still has a finite timeout. Read calls and sleeps MUST NOT hold the registry lock. After reacquisition the helper MUST reload and validate relevant state before writes. Send/create MUST NOT automatically retry; send subprocess timeout MUST equal wait-submit plus 45 seconds.

#### Scenario: Concurrent operation changes an intent during a retry

- **GIVEN** a read retry releases the registry lock and another process changes the relevant binding/task
- **WHEN** the first process reacquires the lock
- **THEN** it detects drift instead of writing stale state or sending based on an old check

#### Scenario: Budget expires

- **GIVEN** classified transient read failures and exhausted time budget
- **WHEN** another read or sleep would exceed the remaining budget
- **THEN** it stops with a structured result and read-attempt evidence, retaining binding and pending intent

### Requirement: Safe bounded packet rendering and secret scanning

Render MUST create a new private external UTF-8 prompt containing only task identity, selected relative paths, task, snapshot contents and required response constraints, excluding project_root and baseline hashes. It MUST validate the packet and use a default 120 KiB maximum final prompt budget with explicit override and a labeled rough token estimate. Prepare and render MUST scan task, paths and contents for the requested credential families and MUST report locations without exposing matches.

#### Scenario: Tampered packet contains a token

- **GIVEN** a manually edited packet with a token in task text, path or file content
- **WHEN** render is invoked
- **THEN** it blocks before creating output and reports only a safe location, not the token

#### Scenario: Render respects exact snapshot and output boundary

- **GIVEN** a valid packet and a changed Mac source after preparation
- **WHEN** render produces an approved-size prompt
- **THEN** it uses the saved snapshot without leaking local root or hashes, and cannot overwrite project files, existing files or symlink targets

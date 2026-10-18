## ADDED Requirements

### Requirement: Explicit confirmation instead of implicit terminal creation

The helper MUST expose create with an explicit full Orca project/worktree selector and an optional confirm flag. Without confirm it MUST perform only a read-only dry-run, returning the exact proposed claude/auto/worktree placement and a bounded sanitized terminal inventory. It MUST NOT submit a create or save a creation intent. Ensure MUST NOT implicitly create a terminal, including first binding. Skill instructions and AGENTS MUST prohibit automatic creation; implementing the helper MUST NOT authorize a real create-confirm invocation.

#### Scenario: Empty inventory dry-run

- **GIVEN** a complete reachable inventory is empty, with no active or uncertain local operation
- **WHEN** create is called without confirm
- **THEN** it reports the plan and empty inventory without creating a terminal, state directory, lock or durable intent

#### Scenario: Ensure has no binding

- **GIVEN** no local binding exists
- **WHEN** ensure is called
- **THEN** it does not create, reports that explicit user confirmation is needed, and directs the controller to list targets and ask the user to choose rebind or create

### Requirement: Verified absence is different from temporary unreachability

Confirmed creation MUST require no active task, uncertain message or unverified creation intent. A live binding MUST block replacement with category has_live_binding; pending work MUST block with uncertain_send. Replacement MUST require a complete inventory affirmatively showing the original instance absent, not just an exception from verify. Transient transport failure, incomplete listing, busy input, non-auto mode or a temporarily disconnected known instance MUST NOT authorize creating a replacement. The explicit project MUST match the binding's cloud worktree and Mac owner/project boundary.

#### Scenario: Live binding or unfinished work blocks create

- **GIVEN** a live bound CC, active task, uncertain send or unresolved create
- **WHEN** a new creation is requested
- **THEN** no new terminal is submitted, and the helper reports has_live_binding or uncertain_send with a safe explanation

#### Scenario: Runtime cannot be queried

- **GIVEN** the runtime returns remote_runtime_unavailable or no complete inventory
- **WHEN** create performs its checks
- **THEN** it reports unreachable or an integrity error, suggests waiting one to two minutes before checking the same operation, and does not infer that the terminal disappeared

### Requirement: Official version-bound native creation contract

A confirmed native call MUST use a verified local official help/guide contract for command, selectors, claude auto mode, placement and receipt fields. The helper MUST use the already verified public terminal create route and MUST NOT invent a native caller-key flag or claim native cross-request deduplication. Capability names or guessed flags MUST NOT substitute for that contract. Unsupported or unverified required capability MUST fail closed before native mutation. User and app versions MUST be distinguished rather than inferred from a skills manifest revision.

#### Scenario: Required contract or capability is not verified

- **GIVEN** the exact public native creation contract or required runtime capability is unavailable
- **WHEN** confirmed creation is requested
- **THEN** the helper stops with an unsupported explanation and makes no speculative native create call

### Requirement: Durable local at-most-once creation submission

Before its single native mutation the helper MUST atomically reserve a stable local create intent ID for the real local owner and exact destination, completing file fsync, atomic replacement and directory fsync before the native call. A reservation failure MUST prevent the native call. Once reserved, the intent MUST permit at most one native create invocation, including outcomes where the native process did not start. The helper MUST release the registry lock during remote calls, reload and validate the same intent before committing results, and preserve concurrent unrelated ownership records. Create MUST NOT retry automatically or through repeated confirmation. Repeated invocations MUST NOT submit a second creation or rotate the local intent ID to escape an unknown outcome. A day-based ID alone MUST NOT collide across distinct later user-confirmed replacement operations. Legacy creating records MUST remain unresolved, never be reset by an upgrade.

This guarantee is limited to this helper using the same retained managed registry and real owner/destination. It MUST NOT be described as native cross-client, cross-registry or exactly-once creation. Switching or deleting registry state or changing identity to bypass an unresolved intent remains prohibited.

#### Scenario: Repeated confirmation does not create twice

- **GIVEN** the same owner/destination creation intent was already submitted or verified
- **WHEN** create is invoked again
- **THEN** it resumes the saved evidence or reports the live/pending binding, without another native create or a different local intent ID

#### Scenario: Reservation cannot be persisted

- **GIVEN** saving or syncing the reservation fails
- **WHEN** confirmed creation is requested
- **THEN** the helper makes no native create call and preserves any saved uncertainty for investigation

#### Scenario: No receipt survives the creation attempt

- **GIVEN** a reserved creation was interrupted, failed to start, timed out or lost its receipt
- **WHEN** create is invoked again, even if an inventory contains a plausible new terminal
- **THEN** it retains create_unverified and does not submit again or infer ownership from a title, timestamp or arbitrary terminal

### Requirement: Verify a newly created CC before binding

A successful create receipt alone MUST NOT establish a binding. The helper MUST first save only the exact valid runtime/handle/incarnation/worktree identity as a pending candidate, then locate it in a complete inventory and verify agentIdentity=claude, liveness, writable non-orphaned state, idle, auto mode and an empty or verified startup-hint composer. Only then MAY it commit the new binding and archive the old binding and task history without deleting anything. Archived task identities and cumulative limits MUST remain effective. Failed or uncertain post-create verification MUST report create_unverified, retain the intent/evidence and MUST NOT create another terminal. A later confirmed invocation MAY only resume read-only verification of the exact saved candidate before committing the binding; it MUST NOT submit another create. Pending creation MUST block ensure, send and rebind.

#### Scenario: Confirmed create verifies and binds once

- **GIVEN** verified absence, explicit user confirmation, a supported native contract and a durable intent
- **WHEN** one create returns a target that passes the complete identity and idle checks
- **THEN** the helper binds it, preserves the old history and task deduplication, and returns only minimized evidence

#### Scenario: Created target cannot be verified

- **GIVEN** a submitted create and an unavailable, wrong-identity, busy or unverified target
- **WHEN** post-create checks fail
- **THEN** the helper reports create_unverified and retains the intent; repeated calls may investigate that intent but do not create a second target

#### Scenario: Saved candidate becomes verifiable

- **GIVEN** the exact created candidate identity was saved but its post-create verification failed
- **WHEN** a later confirmed invocation verifies that same candidate and the unchanged reservation
- **THEN** it may bind that candidate without another native create and without losing other owners or archived task protection

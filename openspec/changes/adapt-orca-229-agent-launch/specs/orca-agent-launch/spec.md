## ADDED Requirements

### Requirement: Explicit native agent launch

Confirmed creation MUST use the verified Orca >=1.4.229 `agent launch --agent claude` route in the explicitly selected worktree and environment. It MUST send no prompt and change no settings, model, account, proxy or permission mode. Ensure and dry-run MUST remain non-creating. Required runtime support MUST be checked before reservation/submission.

#### Scenario: Supported terminal result
- **GIVEN** an explicitly approved target and supported matching runtime
- **WHEN** one confirmed launch returns a terminal handle and native operationId
- **THEN** the helper saves minimized receipt identity before querying that exact handle, and binds only after all existing Claude/auto/composer/ownership checks pass

#### Scenario: Chat or unsafe terminal result
- **GIVEN** a structured-chat outcome, non-auto terminal, unknown draft or mismatched identity
- **WHEN** post-launch verification runs
- **THEN** the helper retains pending evidence, sends no input, changes no settings and creates no replacement

### Requirement: Explicit bounded replay under native identity

Only a documented, validated native operationId saved for the same pending launch MAY authorize an explicitly requested `create --confirm --retry-launch` replay. The original runtime, owner, destination, executable and canonical cwd MUST match. The replay intent MUST be durable before the single replay; automatic retries, a fresh launch, prompt carry and operationId substitution are forbidden.

#### Scenario: Lost launch reply with native replay evidence
- **GIVEN** a new-protocol pending launch with safe native unknown-result evidence and a saved operationId
- **WHEN** the user explicitly requests the matching replay on the original runtime
- **THEN** the helper invokes the same launch with that operationId at most once, and verifies the returned exact outcome without a second fresh agent

#### Scenario: Unknown, expired or exhausted replay
- **GIVEN** replay returns unknown or expired, or one replay was already submitted
- **WHEN** another invocation arrives
- **THEN** the helper preserves pending and the operationId and submits no further mutation

#### Scenario: Legacy pending after an upgrade
- **GIVEN** a legacy creating row without a native operationId
- **WHEN** the runtime changes, an inventory is empty, or retry-launch is supplied
- **THEN** no new launch is submitted and the legacy row remains pending without reset, guessed ownership or migration

### Requirement: Safe creation diagnostics and isolation

Creation failures MUST retain distinguishable sanitized native failure kind and allowed metadata. Native CLI JSON errors in stdout MUST be recognized. Raw stderr, messages, request payloads, source, prompts and credentials MUST NOT enter output or registry. Real-source preparation MUST NOT touch active skill files, real registries, native settings or real cloud agents.

#### Scenario: Unknown-result envelope contains private fields
- **GIVEN** the public unknown-launch error with operationId and extra private payload fields
- **WHEN** the helper records and reports the failure
- **THEN** only validated replay identity and safe diagnostics survive, and unrelated task/owner/history state is preserved

#### Scenario: Unsafe or malformed error evidence
- **GIVEN** an unrecognized code, prose-only ID, malformed JSON or mismatched operationId
- **WHEN** the helper handles the failure
- **THEN** it remains pending, exposes no raw data and gains no replay authority

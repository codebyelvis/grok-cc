## ADDED Requirements

### Requirement: Explicit per-instance auto terminal creation

New confirmed reservations MUST use Orca >=1.4.229 public `terminal create --worktree id:<selected-worktree> --command "claude --permission-mode auto"` in the selected environment. The exact command MUST affect only that new instance; bare `claude`, global settings changes, mode-toggle input, prompts and model overrides are forbidden. Existing runtime/version/capability preflight MUST remain. Ensure and dry-run MUST remain non-creating; preview MUST describe the terminal and its exact command. Existing `agent.launch.v2` rows MUST retain their saved protocol without migration or rewriting.

#### Scenario: Supported terminal result
- **GIVEN** an explicitly approved target and supported matching runtime
- **WHEN** one confirmed terminal creation returns a safe handle
- **THEN** the helper saves only the terminal outcome under `terminal.create.claude-auto.v1`, with no operationId/retrySafe, before querying that exact handle, and binds only after existing runtime/incarnation/worktree/Claude/auto/composer/ownership checks pass

#### Scenario: Chat or unsafe terminal result
- **GIVEN** a structured-chat outcome, non-auto terminal, unknown draft or mismatched identity
- **WHEN** post-launch verification runs
- **THEN** the helper retains pending evidence, sends no input, changes no settings and creates no replacement

#### Scenario: Lost, malformed or failed terminal-create result
- **GIVEN** a new-protocol reservation whose create result fails, times out or cannot prove identity
- **WHEN** create is confirmed again or retry-launch is supplied
- **THEN** uncertainty stays durable, no operationId is invented, and neither another create nor agent launch/replay is submitted

### Requirement: Exact startup placeholders preserve real drafts

Only the eight exact Claude Code startup placeholders in the accepted prerequisite MAY count as an empty composer before task history. Any reported native draft, lookalike text, unknown screen, non-auto mode or changed identity MUST block binding/sending without clearing input or launching again. A screen match is a heuristic, not proof that typed text is absent.

#### Scenario: Placeholder before and after task history
- **GIVEN** an exact known placeholder with no reported draft and all identity/auto checks passing
- **WHEN** initial binding and first sending are verified
- **THEN** the placeholder is allowed, but the same text after task history and any explicitly reported native draft remain blocked

### Requirement: Explicit bounded replay under native identity

Only a documented, validated native operationId saved for the same pending `agent.launch.v2` reservation MAY authorize an explicitly requested `create --confirm --retry-launch` replay. The original runtime, owner, destination, executable and canonical cwd MUST match. The replay intent MUST be durable before the single replay; automatic retries, a fresh launch, prompt carry and operationId substitution are forbidden. `terminal.create.claude-auto.v1` grants no replay authority.

#### Scenario: Lost launch reply with native replay evidence
- **GIVEN** a saved agent-protocol pending launch with safe native unknown-result evidence and a saved operationId
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

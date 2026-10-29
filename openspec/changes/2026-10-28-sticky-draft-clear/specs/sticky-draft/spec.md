## ADDED Requirements

### Requirement: Nonempty draft is a structured preservation block

The helper MUST preserve any nonempty screen JSON draft even when the visual composer is empty. Idle checks used by send and finish MUST raise `Blocked('nonempty_draft')` with `retryable=false`, a constant instruction requiring explicit user authorization for clear-draft, and diagnostic fields `draft_present`, `draft_lines`, `draft_bytes`, `draft_sha256`. It MUST NOT expose draft or screen text. Send and finish MUST NOT clear input.

#### Scenario: Visual prompt hides typed draft

- **GIVEN** a verified idle bound Claude terminal with visual `❯` and nonempty JSON draft
- **WHEN** send or finish checks idle input
- **THEN** nonempty_draft reports true, CRLF/CR/LF logical lines, UTF-8 byte length and SHA256, without the draft text or any send/state mutation

### Requirement: Draft inspection is read only

The helper MUST provide `clear-draft` using the same owner and bound destination arguments. Without `--confirm` it MUST report only draft metadata and binding identity, without terminal send, state creation, lock creation or registry writes. It MUST NOT create or rebind a terminal.

#### Scenario: No confirmation

- **GIVEN** an existing bound terminal with a draft
- **WHEN** clear-draft is invoked without confirm
- **THEN** draft-inspected returns metadata and leaves input and local state unchanged

### Requirement: Confirmed clearing is bounded and never submits

Confirmed clear-draft MUST verify binding identity, reject unresolved messages, busy, non-auto or unverifiable input, and preserve tasks/history. Screen limited/truncated MUST each be explicitly boolean false; missing or falsey values MUST NOT prove completeness. A clear draft with legal composer MUST return draft-already-clear with zero sends. Otherwise it MUST count logical lines by CRLF/CR/LF, including trailing empty lines, choose `N=min(40,max(1,lines+8))`, and send `2N-1` Ctrl+U followed by `2N-1` Ctrl+K in one dedicated terminal.send without Enter or body text. It MUST reverify idle, identity, draft emptiness and empty/exact CLAUDE_EMPTY_PLACEHOLDERS composer. Only a verified nonempty residual draft permits one further maximum burst with N=40 in the same command; no third clear is allowed. Two residual drafts or a residual composer MUST produce non-retryable sticky_draft. Uncertain send/read outcomes MUST stop without blind retry, finish, close, rebind or retire. Failures after attempting a clear MUST set retryable=false even when their underlying read operation is transient.

#### Scenario: First burst clears multiline draft

- **GIVEN** an explicitly confirmed two-line draft and valid idle auto terminal
- **WHEN** clear-draft executes
- **THEN** one write contains exactly 19 Ctrl+U then 19 Ctrl+K, no Enter or body, and verified empty input returns draft-cleared

#### Scenario: First burst leaves residue

- **GIVEN** the first clear is accepted and reverified draft remains nonempty
- **WHEN** the second maximum burst executes
- **THEN** it contains exactly 79 Ctrl+U then 79 Ctrl+K, and a still nonempty draft yields sticky_draft without any third write or task closure

#### Scenario: Safe gates fail

- **GIVEN** busy, identity drift, unresolved send, non-auto or an unknown/unreadable composer
- **WHEN** a confirmed clear would mutate input
- **THEN** the helper blocks without changing permission mode, terminal identity or task state

#### Scenario: Clear and later model submission are separate writes

- **GIVEN** explicit clear succeeded and the caller later invokes send or finish
- **WHEN** the ordinary input gates pass again
- **THEN** send contains only the reviewed body and existing marker trailer, finish closes only its task with project_pass=false, and neither path clears automatically

#### Scenario: Clear read-back lacks completeness evidence

- **GIVEN** an accepted clear followed by a screen with empty draft but a missing, null, numeric or array limited/truncated flag
- **WHEN** the helper checks the screen
- **THEN** it blocks with integrity_failure, never reports draft-cleared and never sends another clear

#### Scenario: Read-back transiently fails after a clear

- **GIVEN** one attempted clear and a subsequent list/wait/read failure
- **WHEN** the read budget cannot produce verified evidence
- **THEN** the result has retryable=false, no further clear occurs and task/binding state remains unchanged

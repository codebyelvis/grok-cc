## ADDED Requirements

### Requirement: Concise production prompts

The production render function and CLI MUST instruct CC to give at most ten lines of conclusions outside the patch block, without repeating the task or pasting full logs. Existing log references MUST be labeled as non-Mac evidence; the prompt MUST NOT instruct CC to run cloud project tests as Mac acceptance.

#### Scenario: Real prompt generation carries reply constraints

- **GIVEN** a valid minimal text packet
- **WHEN** render creates the actual external prompt
- **THEN** the output contains the concise-reply and no-full-log constraints and retains the Mac-source and no-cloud-project-test boundaries

### Requirement: Shared preflight packet budget

Prepare and render MUST use the same configurable maximum final-prompt UTF-8 byte budget, defaulting to 120 KiB, and MUST report a clearly labeled rough token estimate. Preparing an oversized prompt MUST fail before writing a packet and recommend reducing the allowlist rather than packaging the repository. Existing file/total safety limits MUST remain enforced.

#### Scenario: UTF-8 prompt exceeds the limit

- **GIVEN** task and source text whose final rendered UTF-8 size exceeds max-bytes
- **WHEN** prepare or render runs
- **THEN** both apply the same boundary, report only safe size metadata and reduction advice, and leave no successful partial output

#### Scenario: Exact threshold is accepted

- **GIVEN** a safe final prompt exactly max-bytes in UTF-8 and within all existing limits
- **WHEN** prepare and render run
- **THEN** both accept it and report consistent prompt byte counts and labeled rough token estimates

### Requirement: Optional evidence-based handoff summary

Handoff-summary MUST generate at most fifteen LF lines in a new private external file. It MUST not read shared registry, contact a remote, execute tests or infer successful Mac tests from task identity. Optional packet identity MUST match task-id; supplied test evidence MUST use constrained labels/status/counts. Missing evidence MUST remain explicitly unverified. Summary fields MUST exclude source, diff and secrets.

#### Scenario: Only task-id and output are supplied

- **GIVEN** a valid task-id, a safely determined project boundary and no test evidence
- **WHEN** handoff-summary generates an output
- **THEN** it reports missing file/test evidence as unverified, never claims PASS and performs no remote write

#### Scenario: Unsafe or mismatched evidence is rejected

- **GIVEN** a mismatched packet task-id, secret-bearing field, arbitrary log/code input or invalid test counts
- **WHEN** handoff-summary is requested
- **THEN** it fails without leaking the content or creating successful output

### Requirement: Explicit handoff authority and Mac source truth

The Skill MUST state that dispatcher handoffs supply only goals, allowlisted paths and acceptance criteria while Mac files remain source truth. Appending a summary to cloud handoff files MUST require separate user authorization for the destination and content, and MUST NOT be performed by the helper.

#### Scenario: Dispatcher supplies a cloud handoff path

- **GIVEN** a task originating in a dispatcher handoff
- **WHEN** the local controller prepares a packet or summary
- **THEN** it uses Mac source snapshots and does not treat the cloud path or local summary request as authorization for remote reads or writes

### Requirement: Two model submissions with independent read budget

Each task MUST durably record cumulative model submission attempts and per-message deduplication, with at most two submissions across main and exports. Retrying a message MUST be explicit, same identity and text, positively not_sent and reverified idle. After an accepted main, one explicit format-only export MAY consume the remaining attempt; changing export IDs MUST NOT bypass the task total. Uncertain outcomes MUST remain blocked. Accepted-message resume MUST NOT increment attempts. BLOCKED JSON MUST include cumulative task attempts and MUST set retryable=false at the limit. Pure read calls MUST be counted separately as read_attempts within the resilience time budget.

#### Scenario: Second positively not-sent attempt fails

- **GIVEN** the same message has two recorded submission attempts and neither was accepted
- **WHEN** another send is requested
- **THEN** it blocks with attempts=2 and retryable=false without a third submission

#### Scenario: Unknown receipt stops after the first attempt

- **GIVEN** the first attempt has an uncertain outcome
- **WHEN** the caller repeats the invocation or requests another message/task to bypass it
- **THEN** the helper does not send and does not treat the two-attempt ceiling as permission to retry

#### Scenario: Read-only transient recovery does not spend submission attempts

- **GIVEN** list/read/wait encounter classified transient errors
- **WHEN** read-only budgeted recovery makes more than two queries without input submission
- **THEN** read_attempts reflects those calls while model submission attempts remain unchanged

### Requirement: Media exclusion preserves text-only transport

Prepare MUST block common image/video/scanned-document extensions by default and recommend a text summary. Allow-binary MAY waive only extension filtering; actual binary, invalid UTF-8, NUL, recognized media magic, explicit media data URLs and bounded decoded blocks matching media magic MUST remain blocked. The helper MUST NOT encode media automatically or claim perfect detection of arbitrary encodings. Ordinary source/regex/long text MUST NOT be classified as media without such evidence. Existing path, size and secret protections MUST remain active.

#### Scenario: Actual image with explicit extension override

- **GIVEN** a real image or video and allow-binary
- **WHEN** prepare inspects it
- **THEN** it still blocks without writing a packet or embedding binary/Base64 content

#### Scenario: Text fixture has a media extension

- **GIVEN** a small safe UTF-8 text fixture with a blocked media extension
- **WHEN** prepare is called without the override
- **THEN** it blocks
- **AND** only explicit allow-binary may waive that extension gate while all content and safety checks still apply

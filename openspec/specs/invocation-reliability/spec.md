# invocation-reliability Specification

## Purpose

Preserve reviewed prompt bytes, durable send receipts and bounded local cleanup across supported controllers, while keeping existing identity, path and uncertain-delivery safeguards and a minimal documented invocation path.

## Requirements

### Requirement: Receipt persistence tolerates observational evidence

The helper MUST preserve a valid native send receipt when concurrent reconciliation only updates observational evidence on existing saved messages. It MUST retain the latest evidence, reject any other changed binding, task or send-intent field, and never resubmit the operation.

#### Scenario: Reconcile completes before the send receipt returns

- **GIVEN** a durable sending intent and a concurrent reconcile writing evidence on its message
- **WHEN** the original native send returns an accepted receipt
- **THEN** the receipt and accepted state are saved together with that evidence and only one native send occurred

#### Scenario: Whole-task reconciliation overlaps an export receipt

- **GIVEN** an accepted main and a pending export on the same task
- **WHEN** reconcile updates evidence on both existing messages before the export receipt returns
- **THEN** both observations survive and the export receipt is saved without another send

#### Scenario: Intent changes while a send is pending

- **GIVEN** a changed attempt, message content, task, identity or submission counter
- **WHEN** a late receipt returns
- **THEN** the current state is preserved and the stale operation cannot overwrite it

### Requirement: Reviewed prompt bytes and transport limits remain consistent

The send CLI MUST preserve the reviewed UTF-8 text including CR and CRLF. Prepare, render and send MUST reject empty, NUL-containing, reserved-marker or over-450-KiB prompts before dispatch; the default rendering budget remains 120 KiB and no rejected preparation writes output.

#### Scenario: Snapshot contains non-LF newlines

- **GIVEN** a prepared and rendered snapshot containing CRLF and bare CR
- **WHEN** the send CLI reads the approved prompt
- **THEN** the native text equals the approved bytes decoded as UTF-8, followed only by the existing message trailer

#### Scenario: An overridden budget exceeds the transport boundary

- **GIVEN** a large explicit render budget or ordinary source containing the reserved message marker
- **WHEN** the final prompt is not transportable
- **THEN** preparation and rendering reject it without writing output or exposing source contents

### Requirement: Local process cleanup is bounded

After a timeout or read failure, the helper MUST terminate only its own local process group and perform bounded pipe/child cleanup. It MUST retain uncertain delivery and MUST NOT retry remote mutations.

#### Scenario: Descendant retains output pipes

- **GIVEN** a local CLI descendant holding inherited stdout or stderr
- **WHEN** the local call times out
- **THEN** bounded cleanup returns structured failure even if pipe EOF would otherwise never arrive

### Requirement: Controller and path compatibility survives source publication

The source MUST support existing Codex, Claudex and explicit Grok identities without changing legacy keys. Grok MUST NOT be selected under another controller's native session environment. Output paths MAY use canonical parent aliases while all project, no-overwrite and symlink-swap protections remain enforced.

#### Scenario: A foreign host supplies a different Grok UUID

- **GIVEN** a Codex or Claudex native environment and an unrelated valid UUID
- **WHEN** the caller selects the Grok controller
- **THEN** the call rejects the identity before any registry or native action

#### Scenario: A macOS temporary path resolves outside the project

- **GIVEN** a parent alias resolving to a private external directory
- **WHEN** a new packet or prompt is written
- **THEN** it is created through pinned directory descriptors and existing or project-contained targets remain protected

### Requirement: The documented fast path matches the helper contract

For a known existing binding, the Skill MUST permit direct send with its existing full checks. It MUST describe ensure as optional diagnosis and instruct the model to return the minimal supported text diff format with integrity metadata.

#### Scenario: A valid existing binding receives a normal task

- **GIVEN** the same owner and exact destination with no unresolved operation
- **WHEN** the normal workflow submits reviewed text
- **THEN** send performs the required checks without a preceding mandatory ensure or any additional model dispatch

#### Scenario: The requested patch creates a plain text file

- **GIVEN** a whitelisted absent file and the rendered production instructions
- **WHEN** the model follows the minimal diff recipe using /dev/null
- **THEN** the resulting hashed text patch is accepted without Git mode metadata or a format export

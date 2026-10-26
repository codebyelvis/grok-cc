## ADDED Requirements

### Requirement: Transcript parent links survive projection

The recovery projection SHALL keep `type`, `uuid`, and `parentUuid` for transcript records whose type is not `user` or `assistant`. It SHALL NOT include their message bodies, attachment payloads, file snapshots, or any other fields. The ancestry walk SHALL follow those links. Export SHALL still require the final assistant to have `end_turn`, non-empty text, and a parent chain that reaches the accepted user turn for this message. A chain that reaches a different user, a missing uuid, or a cycle SHALL be refused without recovery files. Screen text remains insufficient for recovery.

#### Scenario: Attachment sits between the accepted user and the final assistant

- **GIVEN** an accepted message whose marker is on one user record
- **AND** the final `end_turn` assistant reaches that user through an attachment record
- **WHEN** recover-final-reply projects and validates the transcript
- **THEN** the helper exports only the assistant text
- **AND** the projection does not contain the attachment body or any file-snapshot payload

#### Scenario: The parent chain does not prove this accepted turn

- **GIVEN** a final assistant whose parent links reach a different user or a uuid absent from the projection
- **WHEN** recovery is requested
- **THEN** the helper returns `integrity_failure`, exports nothing, and does not change the binding

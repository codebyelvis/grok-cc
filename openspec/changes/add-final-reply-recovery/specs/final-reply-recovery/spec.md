## ADDED Requirements

### Requirement: Recover an accepted final assistant reply without mutation

The helper SHALL resolve the native owner and require an existing bound task and accepted message with matching receipt and prompt digest. It SHALL read Claude JSONL over strict noninteractive SSH without modifying Orca, registry or known_hosts. Optional expected fingerprint SHALL match both advertised ED25519 key and actual handshake. Only final end_turn assistant text blocks on the target user ancestry SHALL be exported, preserving text order and bytes.

#### Scenario: Missing screen pages with a completed reply

- **GIVEN** an accepted bound task and one unambiguous matching native session
- **WHEN** recover-final-reply is requested
- **THEN** the helper exclusively writes project-external text and provenance metadata and returns recovered without sending or finishing any task

#### Scenario: Missing acceptance or ambiguous evidence

- **GIVEN** no accepted receipt, multiple unresolved candidates, missing end_turn, or unrelated assistant ancestry
- **WHEN** recovery is requested
- **THEN** the helper refuses without recovery files or binding mutation

#### Scenario: Host identity or output boundary fails

- **GIVEN** an unexpected host fingerprint, unavailable strict SSH trust, symlink output parent, or project-internal output
- **WHEN** recovery is requested
- **THEN** the helper refuses and does not repair trust or overwrite files

#### Scenario: Empty or damaged patch metadata

- **GIVEN** a complete final text reply containing patch framing
- **WHEN** patch metadata is checked
- **THEN** an empty SHA256 patch with zero LF count is valid and a damaged hash is recorded false without altering or discarding the recovered original text

## ADDED Requirements

### Requirement: Classify strict SSH recovery failures

When `recover-final-reply` cannot accept a JSONL projection, the helper SHALL refuse export and SHALL NOT modify known_hosts, Orca, or the binding registry. The Blocked result SHALL include `diagnostic.kind` with exactly one of `handshake_failed`, `host_key_mismatch`, `timeout`, or `jsonl_read_failed`. The result SHALL NOT contain remote stderr, host key material, or command output. `StrictHostKeyChecking=yes`, `UpdateHostKeys=no`, and `BatchMode=yes` remain in force.

`host_key_mismatch` SHALL use category `identity_changed`, including an SSH exit 255 whose stderr indicates host key verification failure. `handshake_failed` and `timeout` SHALL use category `unreachable`. A completed SSH session that cannot search, read, or parse the JSONL projection SHALL use `jsonl_read_failed` and SHALL NOT be labeled as a handshake failure. Screen text remains insufficient for recovery.

#### Scenario: Handshake, timeout, and host key are distinct

- **GIVEN** a bound accepted message and a strict SSH attempt
- **WHEN** the attempt times out, fails before a session, or fails host key verification
- **THEN** the helper returns the matching `diagnostic.kind`, exports nothing, and does not repair known_hosts

#### Scenario: JSONL read fails after SSH connects

- **GIVEN** SSH has already produced a non-255 status
- **WHEN** remote search, permission, or JSONL parsing fails
- **THEN** the helper returns `jsonl_read_failed` and does not describe the failure as SSH unreachable

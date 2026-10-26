## ADDED Requirements

### Requirement: Retry only transient recover SSH timeouts

`recover-final-reply` SHALL keep `StrictHostKeyChecking=yes`, `UpdateHostKeys=no`, `BatchMode=yes`, `HostKeyAlgorithms=ssh-ed25519`, and `ControlMaster=no`. It SHALL NOT modify known_hosts or change the SSH host or user. The recover SSH connect timeout SHALL be 20 seconds, and each SSH subprocess deadline SHALL be 90 seconds.

The helper SHALL attempt that SSH read at most 3 times. It SHALL retry only `diagnostic.kind=timeout` and a `handshake_failed` `OSError` that occurs before a child process starts. It SHALL sleep 2 seconds after the first such failure and 5 seconds after the second, and SHALL NOT sleep after the final failure. `host_key_mismatch`, `jsonl_read_failed`, ancestry failure, and identity failure SHALL NOT be retried.

When all attempts fail, the category SHALL remain `unreachable` and `diagnostic.kind` SHALL be `timeout` or the actual `handshake_failed`. The result MAY include an integer `attempts` and SHALL NOT include remote stderr, host key material, or command output. Screen text remains insufficient for recovery.

#### Scenario: A later attempt returns the projection

- **GIVEN** an accepted message and a strict SSH read
- **WHEN** the first two attempts time out and the third returns a valid projection
- **THEN** the helper continues recovery from that projection and does not treat the earlier timeouts as a final refusal

#### Scenario: Timeouts are exhausted

- **GIVEN** every SSH attempt times out
- **WHEN** the third attempt times out
- **THEN** the helper returns `unreachable` with `diagnostic.kind=timeout` and `attempts=3`, exports nothing, and does not repair known_hosts

#### Scenario: Host key failure is not retried

- **GIVEN** the first SSH attempt fails host key verification
- **WHEN** recovery handles that result
- **THEN** the helper returns `identity_changed` with `host_key_mismatch` after one attempt and does not open another SSH session

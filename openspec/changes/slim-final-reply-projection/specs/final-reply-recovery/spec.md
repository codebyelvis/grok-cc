## ADDED Requirements

### Requirement: Slim the final-reply JSONL projection

The recover SSH script SHALL keep parent-link edges for records that are neither user nor assistant. It SHALL keep the full text of assistant records whose `stop_reason` is `end_turn`. It SHALL omit text from other assistant records. User text SHALL be reduced to a window around `grok-cc-msg:<task>` when that marker is present, otherwise around the task id when that id is present, and SHALL NOT include the rest of a large user prompt. A user record MAY include `prompt_sha256` of its original full text so an unmarked accepted prompt can still match without sending that text. Thinking, tool-use payloads, attachment bodies, and file snapshots SHALL NOT be projected. The projection for a large user prompt plus a small end_turn SHALL stay under 50KB.

#### Scenario: A large marked user prompt stays off the wire

- **GIVEN** a JSONL user turn whose prompt is hundreds of kilobytes and ends with the accepted `grok-cc-msg` marker
- **WHEN** the remote projection runs
- **THEN** stdout is smaller than 50KB, omits the distant prompt body, still contains the marker and the full end_turn text, and local recovery exports that end_turn text

#### Scenario: An unmarked prompt matches by original digest

- **GIVEN** an accepted message whose saved digest is the original full user text and the JSONL has no `grok-cc-msg` marker
- **WHEN** the projected user text is only a window around the task id
- **THEN** recovery accepts the turn from `prompt_sha256` and still exports the end_turn text

### Requirement: Recover SSH deadline covers a slim DERP transfer

Each recover SSH subprocess deadline SHALL be 240 seconds. The connect timeout SHALL remain 20 seconds. The helper SHALL still attempt the read at most 3 times and SHALL still retry only `timeout` and a pre-start `handshake_failed`. It SHALL NOT retry `host_key_mismatch` or `jsonl_read_failed`. It SHALL NOT modify known_hosts.

#### Scenario: The deadline is 240 seconds

- **GIVEN** a recover SSH read
- **WHEN** the helper starts the SSH subprocess
- **THEN** that subprocess timeout is 240 seconds and `ConnectTimeout` remains 20 seconds

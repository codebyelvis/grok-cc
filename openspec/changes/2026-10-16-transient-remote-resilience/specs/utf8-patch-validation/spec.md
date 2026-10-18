## MODIFIED Requirements

### Requirement: Validation boundaries remain enforced

The check operation MUST require one complete valid task-bound artifact candidate, selected-file allowlisting, unchanged local baselines, safe non-symlink paths, supported UTF-8 text-only modification/addition types, valid hunk counts and successful native Git validation. By default it MUST require matching PATCH_SHA256 and PATCH_LINES immediately before END_PATCH. Hashes MUST cover the exact original UTF-8 diff bytes, and line counts MUST equal the number of LF bytes in that diff, excluding metadata and wrapper markers. Non-LF payload characters MUST NOT bypass these protections. The parser MUST preserve existing raw CR/CRLF behavior.

#### Scenario: Malformed or out-of-scope patch remains rejected

- **GIVEN** a patch with an out-of-allowlist path, malformed hunk counts, missing or multiple valid task-bound candidates, changed baseline, unsafe path, mismatched hash/line count or truncated metadata
- **WHEN** the helper or CLI checks it, including variants containing non-LF separators
- **THEN** checking fails without writing project files or a successful checked patch

#### Scenario: Echoed instructions precede the authentic patch

- **GIVEN** prompt echo contains a marker template without valid integrity metadata and the reply later contains exactly one complete authentic candidate with correct SHA256 and LF count
- **WHEN** check validates the reply
- **THEN** it selects the authentic candidate without treating the echo template as a second artifact, and preserves the original diff bytes

#### Scenario: Damaged hashed artifact cannot be ignored or downgraded

- **GIVEN** a complete or truncated hash-bearing candidate with invalid metadata, possibly alongside a different valid block
- **WHEN** check runs with or without allow-unhashed
- **THEN** it blocks rather than hiding corruption by selecting another block or accepting it as legacy output

#### Scenario: Explicit legacy compatibility

- **GIVEN** exactly one complete task-bound legacy artifact with no integrity metadata
- **WHEN** check runs without allow-unhashed
- **THEN** it blocks
- **AND** only explicit allow-unhashed may accept that legacy artifact after all existing path, baseline, hunk and native Git checks

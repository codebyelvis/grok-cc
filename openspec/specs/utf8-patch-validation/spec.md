# utf8-patch-validation Specification

## Purpose
Preserve valid UTF-8 patch bytes across reply intake, structural parsing, native Git validation and checked output while retaining task, path and baseline protections.

## Requirements

### Requirement: Lossless UTF-8 reply intake

The check CLI MUST preserve the bytes of a valid UTF-8, non-NUL text patch from the reply file through the checked patch output and native Git validation. It MUST NOT apply universal-newline conversion to embedded CR or CRLF bytes.

#### Scenario: Embedded carriage return reaches native Git unchanged

- **GIVEN** an explicitly selected UTF-8 file and a complete task-bound reply whose hunk contains an inline CR byte and whose patch native Git accepts
- **WHEN** the actual prepare and check CLIs process that reply
- **THEN** the checked diff bytes equal the original diff bytes, and checking leaves selected and unrelated files unchanged
- **AND** applying that checked diff in the isolated test project produces the independently specified target bytes

#### Scenario: Existing CRLF patch compatibility is retained

- **GIVEN** a selected CRLF text file and a valid patch with CRLF hunk content, including the already accepted CRLF structural-header form
- **WHEN** the check CLI validates it
- **THEN** it preserves the diff bytes and native Git can apply the checked output without converting the file line endings

### Requirement: Git-compatible line framing

The patch parser MUST use LF as its structural line boundary while retaining UTF-8 payload characters within hunk lines. It MUST preserve the existing handling of a final LF and optional CRLF framing without dropping hunk content.

#### Scenario: Unicode and control separators are hunk content

- **GIVEN** a native-Git-accepted patch containing VT, FF, FS, GS, RS, NEL, U+2028, U+2029, or inline CR in context, deletion, or addition lines
- **WHEN** the helper checks the complete task-bound patch
- **THEN** those characters do not create extra structural lines or alter the checked diff bytes

### Requirement: Validation boundaries remain enforced

The check operation MUST continue to require unique complete task markers, selected-file allowlisting, unchanged local baselines, safe non-symlink paths, supported text-only modification/addition types, valid hunk counts, and successful native Git validation. Non-LF payload characters MUST NOT bypass these protections.

#### Scenario: Malformed or out-of-scope patch remains rejected

- **GIVEN** a patch with an out-of-allowlist path, malformed hunk counts, missing or duplicate task markers, changed baseline, or symlink path
- **WHEN** the helper or CLI checks it, including variants containing non-LF separators
- **THEN** checking fails and does not write project files or a successful checked patch

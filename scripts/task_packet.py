#!/usr/bin/env python3
"""Author: elvis. Local context snapshots and read-only unified diff validation."""
import argparse
import base64
import binascii
import hashlib
import json
import os
import stat
from pathlib import Path
import re
import subprocess
import sys
import uuid

MAX_FILE = 128 * 1024
MAX_TOTAL = 400 * 1024
MAX_PROMPT = 120 * 1024
MAX_SEND_BYTES = 450 * 1024
SECRET = re.compile(r'AKIA[A-Z0-9]{16}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}'
                    r'|sk-[A-Za-z0-9_-]{20,}|xox[abp]-[A-Za-z0-9-]{10,}|tskey-[A-Za-z0-9_-]{10,}'
                    r'|-----BEGIN [A-Z ]*PRIVATE KEY-----')
RESPONSE_RULES = '''Only analyze the supplied Mac snapshot; do not read or modify the cloud project, install, or run cloud project tests.
Use only minimal unified diff: --- a/path (or --- /dev/null for a new file), +++ b/path, and @@ hunks.
Do not include diff --git, index, or mode metadata; change only allowlisted UTF-8 text files.
Outside the patch block, give at most 10 lines of conclusions; do not repeat the task or paste full logs.
Existing logs: report only paths and pass/fail counts, explicitly not Mac acceptance; do not run tests to create logs.
Create the suggested diff only as a temporary artifact and use tools to calculate its SHA256 and LF byte count.
The opening line joins BEGIN_PATCH, one ASCII space, and task_id; do not use Markdown fences.
After the LF-terminated original diff, output PATCH_SHA256 plus space plus 64 lowercase hex digits,
then PATCH_LINES plus space plus the decimal LF count, each on its own line.
The closing line joins END_PATCH, one ASCII space, and task_id.
Hash and count only the original diff bytes, excluding metadata and markers. Preserve CR/CRLF and all UTF-8 payload bytes.
'''
PRIVATE_PARTS = {'.git', '.ssh', '.aws', '.config', '.claude', '.codex', '.agents', '.tailscale', 'sessions', 'history', 'logs', '__pycache__', 'node_modules'}


def safe_path(root, name):
    if not isinstance(name, str) or not name or re.search(r'[\s\x00-\x1f\\]', name):
        raise ValueError('Unsupported file path')
    parts = name.split('/')
    if name.startswith('/') or any(part in ('', '.', '..') for part in parts):
        raise ValueError('Path must be a normalized relative path')
    lower = [part.lower() for part in parts]
    base = lower[-1]
    if (any(part in PRIVATE_PARTS for part in lower) or base.startswith('.env')
            or base.endswith(('.pem', '.key', '.p12', '.pfx', '.log'))
            or re.search(r'(^|[-_.])(credentials?|secrets?|auth|api[-_]?token)([-_.]|$)', base)
            or base in ('id_rsa', 'id_ed25519')):
        raise ValueError('Sensitive/native runtime path is excluded')
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Symlink path is excluded')
    if not current.is_relative_to(root):
        raise ValueError('Path escapes project')
    return current


def open_directory(path):
    """Pin every directory component; never follow symlinks during traversal."""
    path = Path(path)
    if not path.is_absolute() or any(part in ('.', '..') for part in path.parts):
        raise ValueError('Directory must be canonical and absolute')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_selected(root, name):
    safe_path(root, name)
    fd = open_directory(root)
    try:
        parts = name.split('/')
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(leaf, 'rb') as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('Only regular files are supported')
            if info.st_size > MAX_FILE:
                raise ValueError('File too large; select smaller context')
            raw = source.read(MAX_FILE + 1)
            after = os.fstat(source.fileno())
            if len(raw) > MAX_FILE or (info.st_size, info.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError('File changed during snapshot or exceeded limit')
            return raw
    except FileNotFoundError:
        return None
    finally:
        os.close(fd)


MEDIA_EXTENSIONS = frozenset(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.heic', '.heif', '.bmp',
                              '.tif', '.tiff', '.svg', '.pdf', '.mp4', '.mov', '.webm', '.mkv', '.avi'))
CATEGORIES = ('none', 'unreachable', 'busy', 'identity_changed', 'uncertain_send', 'invalid_input',
              'integrity_failure', 'unsupported_contract', 'model_blocked')


def media_magic(raw):
    head = raw.removeprefix(b'\xef\xbb\xbf').lstrip()
    return (head.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a',
                             b'%PDF-', b'\x1a\x45\xdf\xa3', b'OggS'))
            or (head.startswith(b'RIFF') and head[8:12] == b'WEBP')
            or (len(head) >= 16 and head[4:8] == b'ftyp'
                and 16 <= int.from_bytes(head[:4], 'big') <= len(head))
            or re.match(br'(?:<\?xml[^>]*>\s*)?<svg(?:\s|>)', head[:1024]) is not None)


def reject_media(text):
    if media_magic(text.encode('utf-8')) or re.search(r'data:(?:image/|video/|audio/|application/pdf[;,])', text, re.I):
        raise ValueError('Media content is excluded; supply a necessary text summary')
    for match in re.finditer(r'[A-Za-z0-9+/]{16,}={0,2}', text):
        encoded = match[0]
        if len(encoded) > MAX_TOTAL:
            continue
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            continue
        if media_magic(decoded):
            raise ValueError('Recognized encoded media is excluded; supply a text summary')


def scan_secret(text, label):
    match = SECRET.search(text)
    if match:
        line = text[:match.start()].count('\n') + 1
        raise ValueError(f'Potential secret in {label}, line {line}; remove it before export')


def validate_packet(manifest):
    if not isinstance(manifest, dict) or manifest.get('schema') != 1:
        raise ValueError('Unsupported packet schema')
    tid, task, files = manifest.get('task_id'), manifest.get('task'), manifest.get('files')
    if (not isinstance(tid, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', tid)
            or not isinstance(task, str) or not task.strip() or not isinstance(files, dict) or not files):
        raise ValueError('Invalid packet task or explicit file list')
    scan_secret(tid, 'task_id'); scan_secret(task, 'task'); reject_media(task)
    root = Path(manifest['project_root'])
    if not root.is_absolute() or root.is_symlink() or root.resolve(strict=True) != root or not root.is_dir():
        raise ValueError('Project root changed')
    total = 0
    for index, (name, before) in enumerate(files.items(), 1):
        if not isinstance(name, str) or not isinstance(before, dict):
            raise ValueError('Invalid snapshot entry')
        scan_secret(name, f'file path #{index}')
        safe_path(root, name)
        content, digest = before.get('content'), before.get('sha256')
        if content is None and digest is None:
            continue
        if not isinstance(content, str) or not isinstance(digest, str):
            raise ValueError('Invalid snapshot content or hash')
        raw = content.encode('utf-8'); total += len(raw)
        if len(raw) > MAX_FILE or total > MAX_TOTAL or b'\0' in raw:
            raise ValueError('Context too large or binary')
        scan_secret(content, name); reject_media(content)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Snapshot content/hash mismatch')
    return root


def prompt_metrics(text):
    size = len(text.encode('utf-8'))
    return {'prompt_bytes': size, 'token_estimate': (size + 3) // 4,
            'token_estimate_basis': 'rough UTF-8 bytes/4, not an exact tokenizer'}


def validate_prompt_transport(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Prompt must be nonempty UTF-8 text')
    if '\0' in text:
        raise ValueError('Prompt contains NUL; remove it before export')
    if 'grok-cc-msg:' in text:
        raise ValueError('Prompt contains a reserved message marker; remove it before export')
    size = len(text.encode('utf-8'))
    if size > MAX_SEND_BYTES:
        raise ValueError(f'Prompt transport limit exceeded: {size} > {MAX_SEND_BYTES} bytes; reduce the file allowlist or task')


def render(manifest, max_bytes=MAX_PROMPT):
    validate_packet(manifest)
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError('max-bytes must be a positive integer')
    parts = ['task_id: ' + manifest['task_id'], 'Task:\n' + manifest['task'], RESPONSE_RULES]
    parts.append('Allowed relative paths:\n' + '\n'.join(manifest['files']))
    for name, before in manifest['files'].items():
        parts.append('File: ' + name + '\n' + (before['content'] if before['content'] is not None else '(new file, absent)'))
    text = '\n\n'.join(parts) + '\n'
    validate_prompt_transport(text)
    size = len(text.encode('utf-8'))
    if size > max_bytes:
        raise ValueError(f'Prompt budget exceeded: {size} > {max_bytes} bytes; reduce the file allowlist, not the whole repository')
    return text


def prepare(root, names, task, max_bytes=MAX_PROMPT, allow_binary=False):
    root = Path(root).resolve(strict=True)
    if not root.is_dir() or not task.strip() or not names or len(names) != len(set(names)):
        raise ValueError('Need a directory, task and unique explicit file list')
    scan_secret(task, 'task')
    files = {}
    total = 0
    for index, name in enumerate(names, 1):
        if not isinstance(name, str):
            raise ValueError('Invalid file path')
        scan_secret(name, f'file path #{index}')
        if not allow_binary and Path(name).suffix.lower() in MEDIA_EXTENSIONS:
            raise ValueError('Media extension is excluded; supply a text summary; allow-binary only waives the extension gate')
        raw = read_selected(root, name)
        if raw is None:
            files[name] = {'sha256': None, 'content': None}
            continue
        total += len(raw)
        if total > MAX_TOTAL or b'\0' in raw:
            raise ValueError('Context too large or binary')
        try:
            content = raw.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ValueError('Context must be UTF-8') from exc
        scan_secret(content, name)
        files[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'content': content}
    manifest = {'schema': 1, 'task_id': str(uuid.uuid4()), 'project_root': str(root), 'task': task, 'files': files}
    render(manifest, max_bytes)  # The same final UTF-8 budget is checked before any packet is written.
    return manifest


def handoff_summary(task_id, manifest=None, mac_tests=(), unverified=(), category='none'):
    if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', task_id):
        raise ValueError('Invalid summary task identity')
    scan_secret(task_id, 'task_id')
    names = []
    if manifest is not None:
        validate_packet(manifest)
        if manifest['task_id'] != task_id:
            raise ValueError('Summary task differs from packet')
        names = list(manifest['files'])
    if (category not in CATEGORIES or not isinstance(mac_tests, (list, tuple))
            or not isinstance(unverified, (list, tuple)) or len(mac_tests) > 8 or len(unverified) > 8):
        raise ValueError('Invalid or oversized summary fields')
    for field in (*mac_tests, *unverified):
        if not isinstance(field, str):
            raise ValueError('Invalid summary field')
        scan_secret(field, 'summary field')
    for value in mac_tests:
        match = re.fullmatch(r'([A-Za-z][A-Za-z0-9_.-]{0,63}):(pass|fail|not_run):([0-9]{1,9}):([0-9]{1,9})', value)
        if not match:
            raise ValueError('Mac evidence requires label:pass|fail|not_run:passed:failed, not logs or code')
        state, passed, failed = match[2], int(match[3]), int(match[4])
        if ((state == 'pass' and (not passed or failed)) or (state == 'fail' and not failed)
                or (state == 'not_run' and (passed or failed))):
            raise ValueError('Mac test status/counts disagree')
    if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}', value) for value in unverified):
        raise ValueError('Unverified fields must be short labels, not source or logs')
    listing = ', '.join(names[:10])
    if len(names) > 10 or len(listing) > 400:
        listing = listing[:400] + f' [list truncated; {len(names)} total]'
    lines = ['# Local handoff summary', 'task_id: ' + task_id,
             'Files (packet allowlist, not a verified changed-file claim): ' + (listing or 'not supplied'),
             'Mac tests (supplied by controller, not executed here): ' + ('; '.join(mac_tests) or 'unverified'),
             'Unverified: ' + (', '.join(unverified) or 'acceptance not independently verified'),
             'Blocker category: ' + category,
             'Overall verdict: unverified; this summary is not acceptance or remote-write authorization.']
    return '\n'.join(lines) + '\n'


def summary_root(manifest, project_root):
    if manifest is not None:
        root = validate_packet(manifest)
        if project_root and Path(project_root).resolve(strict=True) != root:
            raise ValueError('Summary project differs from packet')
        return root
    if project_root:
        root = Path(project_root).resolve(strict=True)
    else:
        result = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise ValueError('Need explicit project-root without a packet or verified Git root')
        root = Path(result.stdout.strip()).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Summary project must be a directory')
    return root


def diff_paths(diff):
    """Parse narrow text diffs. Native git validates actual hunk/context semantics."""
    # Git frames patch lines with LF; other Unicode separators are payload.
    lines = diff.split('\n')
    if lines[-1] == '':
        lines.pop()
    # Accept existing CRLF syntax without changing the original diff bytes.
    lines = [line.removesuffix('\r') for line in lines]
    touched = []
    i = 0
    while i < len(lines):
        git_name = None
        if lines[i].startswith('diff --git '):
            match = re.fullmatch(r'diff --git a/(\S+) b/(\S+)', lines[i])
            if not match or match[1] != match[2]:
                raise ValueError('Rename or malformed diff header')
            git_name = match[1]
            i += 1
            if i < len(lines) and lines[i].startswith('index '):
                if not re.fullmatch(r'index [0-9a-f]+\.\.[0-9a-f]+(?: 100644)?', lines[i]):
                    raise ValueError('Unsupported index metadata')
                i += 1
        if i + 1 >= len(lines) or not lines[i].startswith('--- ') or not lines[i+1].startswith('+++ '):
            raise ValueError('Expected unified diff file headers; no binary/mode/rename metadata')
        old, new = lines[i][4:], lines[i+1][4:]
        if not new.startswith('b/') or (old != '/dev/null' and old != 'a/'+new[2:]):
            raise ValueError('Delete, rename or malformed path')
        name = new[2:]
        if (git_name and git_name != name) or name in touched:
            raise ValueError('Duplicate or mismatched file header')
        touched.append(name)
        i += 2
        hunks = 0
        while i < len(lines) and lines[i].startswith('@@ '):
            match = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:.*)', lines[i])
            if not match:
                raise ValueError('Malformed hunk header')
            remaining_old = int(match[2]) if match[2] is not None else 1
            remaining_new = int(match[4]) if match[4] is not None else 1
            i += 1
            while remaining_old or remaining_new:
                if i >= len(lines) or not lines[i] or lines[i][0] not in ' +-':
                    raise ValueError('Truncated or malformed hunk')
                kind = lines[i][0]
                remaining_old -= kind in ' -'
                remaining_new -= kind in ' +'
                if remaining_old < 0 or remaining_new < 0:
                    raise ValueError('Hunk length mismatch')
                i += 1
                if i < len(lines) and lines[i] == '\\ No newline at end of file':
                    i += 1
            hunks += 1
        if not hunks:
            raise ValueError('Empty diff')
    if not touched:
        raise ValueError('Empty patch')
    return touched


def verify_baseline(root, files):
    if root.is_symlink() or root.resolve(strict=True) != root:
        raise ValueError('Project root changed')
    for name, before in files.items():
        raw = read_selected(root, name)
        if before['sha256'] is None:
            if raw is not None:
                raise ValueError('New file collided with local work')
        elif raw is None or hashlib.sha256(raw).hexdigest() != before['sha256']:
            raise ValueError('Local baseline changed; reconcile instead of applying')


def extract_patch(tid, reply, allow_unhashed=False):
    begin, end = f'BEGIN_PATCH {tid}', f'END_PATCH {tid}'
    lines = reply.split('\n')
    hashed, legacy = [], []
    start = None
    starts = ends = 0
    def has_metadata(block):
        return any(line.removesuffix('\r').startswith(('PATCH_SHA256', 'PATCH_LINES')) for line in block)
    for index, raw in enumerate(lines):
        line = raw.removesuffix('\r')
        if line == begin:
            starts += 1
            if start is not None and has_metadata(lines[start+1:index]):
                raise ValueError('Truncated hashed patch')
            start = index
        elif line == end:
            ends += 1
            if start is None:
                raise ValueError('Unmatched task end marker')
            block = lines[start+1:index]
            start = None
            if not has_metadata(block):
                legacy.append('\n'.join(block) + '\n')
                continue
            if (len(block) < 3 or not re.fullmatch(r'PATCH_SHA256 [0-9a-f]{64}', block[-2].removesuffix('\r'))
                    or not re.fullmatch(r'PATCH_LINES [0-9]{1,9}', block[-1].removesuffix('\r'))):
                raise ValueError('Malformed patch integrity metadata')
            diff = '\n'.join(block[:-2]) + '\n'
            digest = block[-2].removesuffix('\r').split(' ')[1]
            count = int(block[-1].removesuffix('\r').split(' ')[1])
            if hashlib.sha256(diff.encode('utf-8')).hexdigest() != digest or diff.count('\n') != count:
                raise ValueError('Patch SHA256 or LF line count mismatch')
            hashed.append(diff)
        elif start is None and line.startswith(('PATCH_SHA256', 'PATCH_LINES')):
            raise ValueError('Integrity metadata outside task markers')
    if start is not None and has_metadata(lines[start+1:]):
        raise ValueError('Truncated hashed patch')
    if len(hashed) == 1:
        return hashed[0]
    if not hashed and allow_unhashed and len(legacy) == starts == ends == 1:
        return legacy[0]
    raise ValueError('Need one complete hashed patch bound to this task; legacy requires allow-unhashed')


def check(manifest, reply, allow_unhashed=False):
    root = validate_packet(manifest)
    diff = extract_patch(manifest['task_id'], reply, allow_unhashed)
    if len(diff.encode('utf-8')) > MAX_TOTAL or '\0' in diff:
        raise ValueError('Oversized or binary patch')
    touched = diff_paths(diff)
    files = manifest['files']
    if any(name not in files for name in touched):
        raise ValueError('Patch outside selected file allowlist')
    verify_baseline(root, files)
    result = subprocess.run(['git', 'apply', '--check', '--'], input=diff, text=True,
                            cwd=root, capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError('git apply --check rejected patch; preserve the original reply for local inspection')
    verify_baseline(root, files)
    return diff


def write_external_output(path, text, root):
    path = Path(path).absolute()
    if path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('Output must be outside the project')
    if path.is_symlink() or path.exists():
        raise ValueError('Refuse to overwrite existing output')
    # Resolve parent aliases (e.g. macOS /tmp) once, then pin the resolved directories
    # with O_NOFOLLOW. A later symlink swap cannot redirect the exclusive leaf write.
    parent = Path(os.path.realpath(path.parent, strict=True))
    path = parent / path.name
    if path.is_symlink() or path.exists():
        raise ValueError('Refuse to overwrite existing output')
    if parent.is_relative_to(Path(root).resolve()):
        raise ValueError('Output parent resolves inside project')
    directory_fd = open_directory(parent)
    try:
        leaf_fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o600, dir_fd=directory_fd)
        with os.fdopen(leaf_fd, 'w', encoding='utf-8') as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(text)
    finally:
        os.close(directory_fd)



class SafeParser(argparse.ArgumentParser):
    def error(self, _message):
        raise ValueError('Invalid arguments; consult --help')


def main():
    command = None
    try:
        parser = SafeParser(description=__doc__)
        sub = parser.add_subparsers(dest='command', required=True)
        create = sub.add_parser('prepare')
        create.add_argument('--root', required=True)
        create.add_argument('--file', action='append', required=True)
        create.add_argument('--task', required=True)
        create.add_argument('--out', required=True)
        create.add_argument('--max-bytes', type=int, default=MAX_PROMPT)
        create.add_argument('--allow-binary', action='store_true', help='Waive only media extension filtering; content must still be UTF-8 text')
        validate = sub.add_parser('check')
        validate.add_argument('--packet', required=True)
        validate.add_argument('--reply', required=True)
        validate.add_argument('--out', required=True)
        validate.add_argument('--allow-unhashed', action='store_true')
        export = sub.add_parser('render')
        export.add_argument('--packet', required=True)
        export.add_argument('--out', required=True)
        export.add_argument('--max-bytes', type=int, default=MAX_PROMPT)
        summary = sub.add_parser('handoff-summary')
        summary.add_argument('--task-id', required=True)
        summary.add_argument('--packet')
        summary.add_argument('--project-root')
        summary.add_argument('--out', required=True)
        summary.add_argument('--mac-test', action='append', default=[])
        summary.add_argument('--unverified', action='append', default=[])
        summary.add_argument('--category', choices=CATEGORIES, default='none')
        args = parser.parse_args()
        command = args.command
        if command == 'prepare':
            manifest = prepare(args.root, args.file, args.task, args.max_bytes, args.allow_binary)
            serialized = json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'
            metrics = prompt_metrics(render(manifest, args.max_bytes))
            write_external_output(args.out, serialized, manifest['project_root'])
            result = {'task_id': manifest['task_id'], 'packet': args.out,
                      'packet_bytes': len(serialized.encode('utf-8')), **metrics}
        elif command == 'handoff-summary':
            manifest = json.loads(Path(args.packet).read_text(encoding='utf-8')) if args.packet else None
            text = handoff_summary(args.task_id, manifest, args.mac_test, args.unverified, args.category)
            write_external_output(args.out, text, summary_root(manifest, args.project_root))
            result = {'task_id': args.task_id, 'summary': args.out, 'result': 'summary-only-unverified'}
        else:
            manifest = json.loads(Path(args.packet).read_text(encoding='utf-8'))
            if command == 'render':
                text = render(manifest, args.max_bytes)
                write_external_output(args.out, text, manifest['project_root'])
                result = {'task_id': manifest['task_id'], 'prompt': args.out, **prompt_metrics(text)}
            else:
                diff = check(manifest, Path(args.reply).read_bytes().decode('utf-8'), args.allow_unhashed)
                write_external_output(args.out, diff, manifest['project_root'])
                result = {'task_id': manifest['task_id'], 'result': 'checked-only', 'patch': args.out}
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        detail = str(exc) if type(exc) is ValueError else 'Local input unavailable or invalid; preserve existing files'
        print(json.dumps({'status': 'BLOCKED', 'category': 'integrity_failure' if command == 'check' else 'invalid_input',
                          'retryable': False, 'attempts': 0, 'read_attempts': 0, 'detail': detail}), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())

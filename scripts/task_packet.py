#!/usr/bin/env python3
"""Author: elvis. Local context snapshots and read-only unified diff validation."""
import argparse
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


def prepare(root, names, task):
    root = Path(root).resolve(strict=True)
    if not root.is_dir() or not task.strip() or not names or len(names) != len(set(names)):
        raise ValueError('Need a directory, task and unique explicit file list')
    files = {}
    total = 0
    for name in names:
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
        files[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'content': content}
    return {'schema': 1, 'task_id': str(uuid.uuid4()), 'project_root': str(root), 'task': task, 'files': files}


def diff_paths(diff):
    """Parse narrow text diffs. Native git validates actual hunk/context semantics."""
    lines = diff.splitlines()
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


def check(manifest, reply):
    if manifest.get('schema') != 1:
        raise ValueError('Unsupported packet schema')
    root = Path(manifest['project_root'])
    if root.is_symlink() or root.resolve(strict=True) != root:
        raise ValueError('Project root changed')
    tid = manifest['task_id']
    begin, end = f'BEGIN_PATCH {tid}', f'END_PATCH {tid}'
    lines = reply.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip('\r\n') == begin]
    ends = [i for i, line in enumerate(lines) if line.rstrip('\r\n') == end]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ValueError('Need unique complete markers bound to this task')
    diff = ''.join(lines[starts[0]+1:ends[0]])
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
        raise ValueError('git apply --check rejected patch: '+result.stderr.strip())
    verify_baseline(root, files)
    return diff


def write_external_output(path, text, root):
    path = Path(path).absolute()
    if path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('Output must be outside the project')
    if path.is_symlink() or path.exists():
        raise ValueError('Refuse to overwrite existing output')
    for parent in path.parents:
        if parent.is_symlink():
            raise ValueError('Output parent is a symlink')
    parent = path.parent.resolve(strict=True)
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



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('prepare')
    create.add_argument('--root', required=True)
    create.add_argument('--file', action='append', required=True)
    create.add_argument('--task', required=True)
    create.add_argument('--out', required=True)
    validate = sub.add_parser('check')
    validate.add_argument('--packet', required=True)
    validate.add_argument('--reply', required=True)
    validate.add_argument('--out', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            manifest = prepare(args.root, args.file, args.task)
            write_external_output(args.out, json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', manifest['project_root'])
            print(json.dumps({'task_id': manifest['task_id'], 'packet': args.out}))
        else:
            manifest = json.loads(Path(args.packet).read_text())
            diff = check(manifest, Path(args.reply).read_text())
            write_external_output(args.out, diff, manifest['project_root'])
            print(json.dumps({'task_id': manifest['task_id'], 'result': 'checked-only', 'patch': args.out}))
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as exc:
        print('BLOCKED: '+str(exc), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())

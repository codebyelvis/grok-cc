#!/usr/bin/env python3
"""Author: elvis. Durable one-conversation/one-Orca-CC ownership and send guards."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import uuid


def resolve_owner(controller, session_id=None):
    if controller not in ('codex', 'claudex'):
        raise ValueError('Unsupported local controller')
    native = os.environ.get('CODEX_THREAD_ID') if controller == 'codex' else None
    if controller == 'codex' and not native:
        raise ValueError('Native CODEX_THREAD_ID is required; a supplied UUID cannot replace it')
    if native and session_id and native != session_id:
        raise ValueError('Session ID differs from the current native Codex thread')
    session_id = session_id or native
    try:
        if not session_id or str(uuid.UUID(session_id)) != session_id.lower():
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError('Need the actual native conversation ID; unresolved placeholders are refused') from None
    return {'controller': controller, 'session_id': session_id.lower()}


def owner_key(owner):
    return hashlib.sha256((owner['controller'] + '\0' + owner['session_id']).encode()).hexdigest()


def _directory(path):
    """Create/open each component using pinned FDs, never traversing symlinks."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('State directory must be an absolute normalized path')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            try:
                os.mkdir(part, 0o700, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('State directory must be owned by this user with mode 0700')
        return fd
    except BaseException:
        os.close(fd)
        raise


class Registry:
    def __init__(self, path):
        self.path = Path(path)
        self.fd = self.lock = None

    def __enter__(self):
        try:
            self.fd = _directory(self.path)
            self.lock = os.open('bindings.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                                0o600, dir_fd=self.fd)
            self._private(self.lock)
            try:
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('Binding operation busy; wait and retry this same conversation') from None
            try:
                leaf = os.open('bindings.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
            except FileNotFoundError:
                self.data = {'schema': 1, 'bindings': {}}
            else:
                with os.fdopen(leaf, 'r', encoding='utf-8') as source:
                    self._private(source.fileno())
                    raw = source.read(4 * 1024 * 1024 + 1)
                    if len(raw) > 4 * 1024 * 1024:
                        raise ValueError('Registry oversized; preserve it for investigation')
                    self.data = json.loads(raw)
            if (not isinstance(self.data, dict) or self.data.get('schema') != 1
                    or not isinstance(self.data.get('bindings'), dict)):
                raise ValueError('Invalid registry; do not reset ownership')
            for key, row in self.data['bindings'].items():
                if not isinstance(row, dict) or owner_key(row['owner']) != key:
                    raise ValueError('Invalid ownership record; preserve registry')
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    @staticmethod
    def _private(fd):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_nlink != 1 or info.st_mode & 0o077):
            raise ValueError('Registry files must be private regular single-link files')

    def save(self):
        name = 'pending-' + uuid.uuid4().hex
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self.fd)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as output:
                output.write(json.dumps(self.data, ensure_ascii=False, indent=2) + '\n')
                output.flush(); os.fsync(output.fileno())
            os.replace(name, 'bindings.json', src_dir_fd=self.fd, dst_dir_fd=self.fd)
            os.fsync(self.fd)
        finally:
            try:
                os.unlink(name, dir_fd=self.fd)
            except FileNotFoundError:
                pass

    def __exit__(self, *_):
        if self.lock is not None:
            os.close(self.lock); self.lock = None
        if self.fd is not None:
            os.close(self.fd); self.fd = None


class NativeOrca:
    def __init__(self, executable):
        self.executable = executable

    def __call__(self, args):
        result = subprocess.run([self.executable, *args], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise ValueError('Native Orca failed: ' + (result.stderr or result.stdout).strip()[:1500])
        return json.loads(result.stdout)


class BindingManager:
    def __init__(self, state, owner, project, environment, worktree, orca):
        self.state = Path(state).expanduser().absolute()
        self.project = str(Path(project).resolve(strict=True))
        if not Path(self.project).is_dir() or self.state.resolve().is_relative_to(Path(self.project)):
            raise ValueError('Binding state must live outside the Mac project')
        self.owner = owner
        self.key = owner_key(owner)
        self.environment = environment
        self.worktree = worktree.removeprefix('id:')
        if not environment or '::' not in self.worktree or self.worktree in ('active', 'current'):
            raise ValueError('Need explicit environment and discovered full worktree identity')
        self.orca = orca

    def _call(self, command):
        result = self.orca([*command, '--environment', self.environment, '--json'])
        if not isinstance(result, dict) or result.get('ok') is not True:
            raise ValueError('Native Orca did not return verified success')
        runtime = result.get('_meta', {}).get('runtimeId')
        if not isinstance(runtime, str) or not runtime:
            raise ValueError('Native runtime identity unavailable')
        return result

    def _list(self):
        result = self._call(['terminal', 'list'])
        if result['result'].get('truncated') is not False:
            raise ValueError('Incomplete terminal inventory')
        terminals = result['result']['terminals']
        if not isinstance(terminals, list):
            raise ValueError('Invalid terminal inventory')
        return result['_meta']['runtimeId'], terminals

    def _row(self, db):
        row = db.data['bindings'].get(self.key)
        if row is None:
            raise ValueError('No binding; run ensure once with this native conversation identity')
        expected = {'owner': self.owner, 'project': self.project, 'environment': self.environment,
                    'worktree': self.worktree}
        if any(row.get(k) != v for k, v in expected.items()):
            raise ValueError('Binding destination/project differs; do not create a replacement')
        if row.get('state') != 'bound':
            raise ValueError('Creation outcome uncertain; preserve intent and investigate read-only')
        for key, other in db.data['bindings'].items():
            if (key != self.key and other.get('runtime') == row['runtime']
                    and other.get('handle') == row['handle']):
                raise ValueError('Terminal has conflicting conversation ownership')
        return row

    def _verify(self, row):
        runtime, terminals = self._list()
        matches = [t for t in terminals if t.get('handle') == row['handle']]
        if runtime != row['runtime'] or len(matches) != 1:
            raise ValueError('Bound runtime/terminal unavailable; retain binding')
        terminal = matches[0]
        if (terminal.get('incarnationId') != row['incarnation']
                or terminal.get('worktreeId') != row['worktree']
                or terminal.get('agentIdentity') != 'claude'
                or terminal.get('connected') is not True
                or terminal.get('writable') is not True or terminal.get('orphaned') is not False):
            raise ValueError('Bound CC identity/liveness changed; retain binding and do not send')

    @staticmethod
    def _view(row):
        return {k: row[k] for k in ('handle', 'incarnation', 'runtime', 'worktree', 'environment')}

    def ensure(self):
        with Registry(self.state) as db:
            if self.key in db.data['bindings']:
                row = self._row(db)
                self._verify(row)
                return self._view(row)
            runtime, _ = self._list()
            row = {'owner': self.owner, 'project': self.project, 'environment': self.environment,
                   'worktree': self.worktree, 'runtime': runtime, 'state': 'creating',
                   'creation_id': str(uuid.uuid4()), 'tasks': {}, 'active_task': None}
            db.data['bindings'][self.key] = row
            db.save()  # Durable reservation BEFORE a non-idempotent remote create.
            result = self._call(['terminal', 'create', '--worktree', 'id:' + self.worktree,
                                 '--command', 'claude --permission-mode auto',
                                 '--title', 'grok-cc ' + self.owner['controller'] + ' ' + self.owner['session_id'][:8]])
            terminal = result['result']['terminal']
            if (result['_meta']['runtimeId'] != runtime or terminal.get('worktreeId') != self.worktree
                    or not terminal.get('handle') or not terminal.get('incarnationId')):
                raise ValueError('Creation identity unverifiable; preserve intent, never recreate')
            if any(other.get('runtime') == runtime and other.get('handle') == terminal['handle']
                   for key, other in db.data['bindings'].items() if key != self.key):
                raise ValueError('Create returned a terminal already owned by another conversation')
            row.update(state='bound', handle=terminal['handle'], incarnation=terminal['incarnationId'])
            db.save()
            return self._view(row)

    def _idle(self, row):
        wait = self._call(['terminal', 'wait', '--terminal', row['handle'], '--for', 'tui-idle',
                          '--timeout-ms', '1000'])
        if wait['_meta']['runtimeId'] != row['runtime'] or wait['result']['wait'].get('satisfied') is not True:
            raise ValueError('Bound CC busy; wait on this terminal, do not create another')
        stream = self._call(['terminal', 'read', '--terminal', row['handle'], '--limit', '1'])
        screen = self._call(['terminal', 'read', '--terminal', row['handle'], '--screen'])
        if any(r['_meta']['runtimeId'] != row['runtime'] for r in (stream, screen)):
            raise ValueError('Runtime changed while checking input')
        terminal = screen['result']['terminal']
        tail = terminal['tail']
        if (terminal.get('handle') != row['handle'] or terminal.get('source') != 'screen'
                or terminal.get('draft') or terminal.get('truncated') or terminal.get('limited')):
            raise ValueError('Input screen/draft cannot be verified')
        separators = [i for i, line in enumerate(tail) if re.fullmatch('[─━]{3,}', line.strip())]
        if len(separators) < 2:
            raise ValueError('Cannot identify the bound CC composer')
        start, end = separators[-2:]
        composer = '\n'.join(tail[start+1:end]).strip()
        footer = '\n'.join(tail[end+1:]).lower()
        if 'auto mode on' not in footer or 'bypass' in footer:
            raise ValueError('Auto mode is not proven')
        # Claude renders NBSP between the prompt glyph and its empty startup hint.
        # Normalize only that delimiter, never arbitrary draft content.
        if not composer.startswith('❯'):
            raise ValueError('Cannot identify the bound CC input prompt')
        content = composer[1:].lstrip()
        allowed = {''}
        if not row['tasks']:
            allowed.update(('Try "edit <filepath> to..."', 'Try "fix typecheck errors"',
                            'Try "refactor <filepath>"', 'Try "write a test for <filepath>"'))
        if content not in allowed:
            raise ValueError('Bound CC has a nonempty or ambiguous draft; preserve it')
        cursor = stream['result']['terminal'].get('latestCursor')
        if cursor is None:
            raise ValueError('Native pre-send cursor unavailable')
        self._verify(row)
        return cursor

    def send(self, task_id, message_id, text):
        if (not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', task_id)
                or not re.fullmatch(r'main|export-[1-9][0-9]*', message_id)
                or not text.strip() or len(text.encode()) > 450 * 1024):
            raise ValueError('Need task ID, main/export-N message identity and bounded nonempty text')
        digest = hashlib.sha256(text.encode()).hexdigest()
        with Registry(self.state) as db:
            row = self._row(db)
            task = row['tasks'].get(task_id)
            if task and message_id in task['messages']:
                message = task['messages'][message_id]
                if message['sha256'] != digest:
                    raise ValueError('Message identity reused for different content')
                return {'action': 'resume', 'binding': self._view(row), 'message': message}
            if row['active_task'] not in (None, task_id):
                raise ValueError('Another task is pending on this conversation; do not dispatch elsewhere')
            if task and (task.get('closed') or any(m['state'] != 'accepted' for m in task['messages'].values())):
                raise ValueError('Task closed or has an uncertain send; use existing receipts/read-only recovery')
            if not task and message_id != 'main':
                raise ValueError('Export requires an existing task')
            self._verify(row)
            cursor = self._idle(row)
            if task is None:
                task = {'closed': False, 'messages': {}}
                row['tasks'][task_id] = task
            message = {'state': 'sending', 'sha256': digest, 'cursor': cursor}
            task['messages'][message_id] = message
            row['active_task'] = task_id
            db.save()  # Unknown send outcome remains recorded even if this process dies.
            result = self._call(['terminal', 'send', '--terminal', row['handle'], '--text', text,
                                 '--enter', '--wait-submit', '15'])
            send = result['result']['send']
            prompt = send.get('prompt', {})
            message['receipt'] = result
            if (result['_meta']['runtimeId'] != row['runtime'] or send.get('handle') != row['handle']
                    or send.get('accepted') is not True or not prompt.get('requestId')
                    or prompt.get('processIncarnation') != row['incarnation']
                    or 'input_accepted' not in prompt.get('stages', [])):
                db.save()
                raise ValueError('Send identity/result uncertain; retain receipt and never blindly repeat')
            message['state'] = 'accepted'
            db.save()
            return {'action': 'sent', 'binding': self._view(row), 'message': message}

    def finish(self, task_id):
        with Registry(self.state) as db:
            row = self._row(db)
            task = row['tasks'].get(task_id)
            if not task or row['active_task'] not in (None, task_id):
                raise ValueError('Task not active in this conversation')
            if any(m['state'] != 'accepted' for m in task['messages'].values()):
                raise ValueError('Unknown send outcome must remain pending')
            self._verify(row); self._idle(row)
            task['closed'] = True
            row['active_task'] = None
            db.save()
            return {'action': 'dispatch-task-closed', 'binding': self._view(row),
                    'project_pass': False, 'task_id': task_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['ensure', 'send', 'finish', 'identity'])
    parser.add_argument('--controller', choices=['codex', 'claudex'], required=True)
    parser.add_argument('--session-id')
    parser.add_argument('--project-root')
    parser.add_argument('--environment', default='Grok Bot')
    parser.add_argument('--worktree')
    parser.add_argument('--state-dir', default=str(Path.home() / '.local/state/grok-cc'))
    parser.add_argument('--orca', default=os.environ.get('ORCA_CLI_COMMAND', 'orca'))
    parser.add_argument('--task-id')
    parser.add_argument('--message-id', default='main')
    parser.add_argument('--text-file')
    args = parser.parse_args()
    try:
        owner = resolve_owner(args.controller, args.session_id)
        if args.command == 'identity':
            result = {'owner': owner, 'key': owner_key(owner)}
        else:
            if not args.project_root or not args.worktree:
                raise ValueError('Need project-root and explicit cloud worktree')
            manager = BindingManager(args.state_dir, owner, args.project_root, args.environment,
                                     args.worktree, NativeOrca(args.orca))
            if args.command == 'ensure':
                result = manager.ensure()
            elif args.command == 'send':
                if not args.text_file or not args.task_id:
                    raise ValueError('Need task-id and reviewed prompt text-file')
                result = manager.send(args.task_id, args.message_id, Path(args.text_file).read_text(encoding='utf-8'))
            else:
                if not args.task_id:
                    raise ValueError('Need task-id')
                result = manager.finish(args.task_id)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print('BLOCKED: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

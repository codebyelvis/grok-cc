#!/usr/bin/env python3
"""Author: elvis. Durable one-conversation/one-Orca-CC ownership and send guards."""
import argparse
import copy
import fcntl
import functools
import math
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid

from task_packet import validate_prompt_transport


class Blocked(ValueError):
    """Only constant, local diagnostics may cross the CLI boundary."""
    def __init__(self, category, detail, retryable=False, diagnostic=None, launch=None):
        super().__init__(detail)
        self.category = category
        self.detail = detail
        self.retryable = retryable
        self.attempts = self.read_attempts = 0
        self.diagnostic = diagnostic or {}
        self.launch = launch or {}

    def result(self):
        return ({'status': 'BLOCKED', 'category': self.category, 'retryable': self.retryable,
                'attempts': self.attempts, 'read_attempts': self.read_attempts, 'detail': self.detail}
                | ({'diagnostic': self.diagnostic} if self.diagnostic else {})
                | ({'launch': self.launch} if self.launch else {}))


TRANSIENT_READ_CODES = frozenset(('remote_runtime_unavailable', 'transport_unavailable',
                                  'connection_reset', 'connection_refused'))
NATIVE_CODES = TRANSIENT_READ_CODES | frozenset(('agent_session_operation_unknown',
    'agent_session_operation_expired', 'incompatible_runtime', 'invalid_argument',
    'runtime_error', 'runtime_access_denied', 'agent_launch_tab_closed'))
NATIVE_KINDS = frozenset(('launch', 'timeout', 'nonzero', 'invalid_json', 'invalid_envelope', 'invalid_result'))
# Claude Code 2.1.303 bundle, empty-input placeholder list with no example files:
# ["fix lint errors","fix typecheck errors","how does <f> work?","refactor <f>",
#  "how do I log an error?","edit <f> to...","write a test for <f>","create a util logging.py that..."]
CLAUDE_EMPTY_PLACEHOLDERS = frozenset('Try "' + hint + '"' for hint in (
    'fix lint errors', 'fix typecheck errors', 'how does <filepath> work?', 'refactor <filepath>',
    'how do I log an error?', 'edit <filepath> to...', 'write a test for <filepath>',
    'create a util logging.py that...'))
# Orca `agent launch` applies global agentDefaultArgs.claude
# (--dangerously-skip-permissions). This per-instance path uses the public
# `terminal create --command`; never bare `claude`, which Orca rewrites to its agent default.
AUTO_LAUNCH_PROTOCOL = 'terminal.create.claude-auto.v1'
AUTO_LAUNCH_COMMAND = 'claude --permission-mode auto'
NEW_CREATE_PROTOCOL = AUTO_LAUNCH_PROTOCOL  # new reservations only; saved agent.launch.v2 rows keep their protocol
LAUNCH_CAPABILITIES = frozenset(('agent.launch.v2', 'agent.launch.replay-required.v1',
                                'agent.launch.local-presentation.v1'))


def _operation_id(value):
    return isinstance(value, str) and re.fullmatch(r'\d{13}-[0-9a-f]{32}', value, re.ASCII) is not None


def _unknown_launch(code, data):
    if (code == 'agent_session_operation_unknown' and isinstance(data, dict)
            and data.get('launchOutcome') == 'unknown' and data.get('retrySafe') is True
            and _operation_id(data.get('operationId'))):
        return {k: data[k] for k in ('launchOutcome', 'retrySafe', 'operationId')}
    return {}


def _diagnostic(exc):
    diagnostic = {'kind': exc.kind if isinstance(exc, NativeFailure) and isinstance(exc.kind, str)
                  and exc.kind in NATIVE_KINDS
                  else 'invalid_result', 'started': True}
    if isinstance(exc, NativeFailure):
        if type(exc.started) is bool:
            diagnostic['started'] = exc.started
        if type(exc.returncode) is int and -255 <= exc.returncode <= 255:
            diagnostic['returncode'] = exc.returncode
        if type(exc.timeout) in (int, float) and 0 < exc.timeout <= 180 and math.isfinite(exc.timeout):
            diagnostic['timeout'] = exc.timeout
        if exc.code in NATIVE_CODES:
            diagnostic['code'] = exc.code
    return diagnostic


class NativeFailure(ValueError):
    """Raw subprocess evidence stays in memory, never in str(), output or state."""
    def __init__(self, kind, *, started=True, returncode=None, stderr=None, timeout=None, code=None, receipt=None,
                 launch=None):
        super().__init__('Native Orca operation failed')
        self.kind = kind
        self.started = started
        self.returncode = returncode
        self.stderr = stderr
        self.timeout = timeout
        self.code = code if isinstance(code, str) and code in NATIVE_CODES else None
        self.receipt = _receipt(receipt)
        self.launch = _unknown_launch(self.code, launch)


def _launch_record(row):
    """Validate the new private ledger without giving legacy rows replay authority."""
    launch = row.get('creation_launch')
    if launch is None:
        return
    required = {'protocol', 'context', 'replay_attempts'}
    allowed = required | {'operationId', 'retrySafe', 'outcome', 'diagnostic'}
    context = launch.get('context') if isinstance(launch, dict) else None
    valid = (isinstance(launch, dict) and required <= set(launch) <= allowed
        and launch['protocol'] in ('agent.launch.v2', AUTO_LAUNCH_PROTOCOL)
        and (launch['protocol'] == 'agent.launch.v2' or not ({'operationId', 'retrySafe'} & set(launch)))
        and type(launch['replay_attempts']) is int and launch['replay_attempts'] in (0, 1)
        and isinstance(context, dict) and set(context) == {'executable', 'cwd'}
        and context.get('cwd') == row.get('project')
        and all(isinstance(context.get(k), str) and context[k].startswith('/')
                and '\0' not in context[k] and '..' not in Path(context[k]).parts for k in context))
    try:
        valid = valid and str(uuid.UUID(row['creation_id'])) == row['creation_id']
    except (ValueError, KeyError, TypeError, AttributeError):
        valid = False
    if not valid or row.get('state') not in ('creating', 'bound'):
        raise Blocked('integrity_failure', 'Invalid saved launch context; preserve registry')
    outcome = launch.get('outcome')
    if 'operationId' in launch and not _operation_id(launch['operationId']):
        raise Blocked('integrity_failure', 'Invalid saved native launch identity; preserve registry')
    if 'retrySafe' in launch and (launch['retrySafe'] is not True or 'operationId' not in launch or outcome is not None):
        raise Blocked('integrity_failure', 'Invalid saved replay evidence; preserve registry')
    if 'outcome' in launch and (not isinstance(outcome, dict) or set(outcome) != {'kind', 'handle'}
            or outcome.get('kind') not in ('terminal', 'structured') or not _safe_identity(outcome.get('handle'))
            or ('operationId' not in launch) != (launch['protocol'] == AUTO_LAUNCH_PROTOCOL)
            or (launch['protocol'] == AUTO_LAUNCH_PROTOCOL and outcome.get('kind') != 'terminal')):
        raise Blocked('integrity_failure', 'Invalid saved launch outcome; preserve registry')
    diagnostic = launch.get('diagnostic')
    if 'diagnostic' in launch:
        if (not isinstance(diagnostic, dict) or not {'kind', 'started'} <= set(diagnostic)
                or set(diagnostic) - {'kind', 'started', 'returncode', 'timeout', 'code'}
                or not isinstance(diagnostic.get('kind'), str) or diagnostic['kind'] not in NATIVE_KINDS
                or type(diagnostic.get('started')) is not bool
                or ('code' in diagnostic and (not isinstance(diagnostic['code'], str) or diagnostic['code'] not in NATIVE_CODES))
                or ('returncode' in diagnostic and (type(diagnostic['returncode']) is not int
                                                    or not -255 <= diagnostic['returncode'] <= 255))
                or ('timeout' in diagnostic and (type(diagnostic['timeout']) not in (int, float)
                    or not 0 < diagnostic['timeout'] <= 180 or not math.isfinite(diagnostic['timeout'])))):
            raise Blocked('integrity_failure', 'Invalid saved launch diagnostic; preserve registry')


def _receipt(value):
    """Project both native envelopes and old schema-1 receipts conservatively."""
    if not isinstance(value, dict):
        return {}
    if 'result' in value:
        result = value.get('result')
        send = result.get('send') if isinstance(result, dict) else None
        if not isinstance(send, dict):
            return {}
        prompt = send.get('prompt')
        prompt = prompt if isinstance(prompt, dict) else {}
        meta = value.get('_meta')
        value = {**prompt, 'handle': send.get('handle'), 'accepted': send.get('accepted'),
                 'runtimeId': meta.get('runtimeId') if isinstance(meta, dict) else None}
    receipt = {}
    for key in ('requestId', 'processIncarnation', 'handle', 'runtimeId'):
        field = value.get(key)
        if isinstance(field, str) and re.fullmatch(r'[A-Za-z0-9._:/-]{1,256}', field):
            receipt[key] = field
    if type(value.get('accepted')) is bool:
        receipt['accepted'] = value['accepted']
    stages = value.get('stages')
    if isinstance(stages, list) and len(stages) <= 32 and all(isinstance(s, str) for s in stages):
        receipt['stages'] = [s for s in stages if s in ('input_accepted', 'turn_started', 'turn_completed')]
    return receipt


def _project_row(row, depth=0):
    if not isinstance(row, dict) or depth > 32:
        raise Blocked('integrity_failure', 'Invalid binding history; preserve registry')
    _launch_record(row)
    tasks, history = row.get('tasks', {}), row.get('history', [])
    if not isinstance(tasks, dict) or not isinstance(history, list):
        raise Blocked('integrity_failure', 'Invalid task/history structure; preserve registry')
    for task in tasks.values():
        if not isinstance(task, dict) or not isinstance(task.get('messages'), dict):
            raise Blocked('integrity_failure', 'Invalid message structure; preserve registry')
        for message in task['messages'].values():
            if not isinstance(message, dict):
                raise Blocked('integrity_failure', 'Invalid saved message; preserve registry')
            if 'receipt' in message:
                message['receipt'] = _receipt(message['receipt'])
    for old in history:
        _project_row(old, depth + 1)
    candidate = row.get('creation_candidate')
    if candidate is not None:
        creation_id = row.get('creation_id')
        try:
            valid_id = isinstance(creation_id, str) and str(uuid.UUID(creation_id)) == creation_id
        except ValueError:
            valid_id = False
        if (not valid_id or row.get('state') != 'creating' or not isinstance(candidate, dict)
                or set(candidate) != {'runtime', 'handle', 'incarnation', 'worktree'}
                or any(not _safe_identity(candidate.get(k)) for k in ('runtime', 'handle', 'incarnation'))
                or candidate.get('runtime') != row.get('runtime')
                or candidate.get('worktree') != row.get('worktree')):
            raise Blocked('integrity_failure', 'Invalid creation candidate; preserve registry')
        launch = row.get('creation_launch')
        if launch is not None and launch.get('outcome') != {'kind': 'terminal', 'handle': candidate['handle']}:
            raise Blocked('integrity_failure', 'Candidate differs from native launch receipt; preserve registry')
    if row.get('state') == 'creating' and tasks and 'creation_previous' not in row:
        raise Blocked('integrity_failure', 'Missing prior creation tasks; preserve registry')
    if 'creation_previous' in row:
        previous = row['creation_previous']
        if (row.get('state') != 'creating' or not isinstance(previous, dict)
                or previous.get('state') != 'bound'
                or any(previous.get(k) != row.get(k) for k in ('owner', 'project', 'environment', 'worktree'))
                or any(k in previous for k in ('history', 'creation_previous', 'creation_candidate'))):
            raise Blocked('integrity_failure', 'Invalid prior creation binding; preserve registry')
        _project_row(previous, depth + 1)
        if previous.get('tasks', {}) != tasks or previous.get('active_task') != row.get('active_task'):
            raise Blocked('integrity_failure', 'Prior creation tasks differ; preserve registry')


def _safe_identity(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9._:/-]{1,256}', value) is not None


def _command(method):
    """One monotonic read deadline per public invocation, not per nested read."""
    @functools.wraps(method)
    def call(self, *args, **kwargs):
        self.read_attempts = self.attempts = self._backoff = 0
        self._deadline = time.monotonic() + self.retry_budget_s if self.retry_budget_s > 0 else None
        try:
            return method(self, *args, **kwargs)
        except Blocked as exc:
            exc.attempts = self.attempts
            exc.read_attempts = self.read_attempts
            exc.retryable = exc.retryable and self.attempts < 2
            raise
    return call


# Each controller owns its identity; ids are never cross-mapped between controllers.
# grok = Grok CLI (grokcli). No Grok CLI session env var is documented or installed on
# this box, so its id must always be passed explicitly with --session-id.
CONTROLLER_ENV = {'codex': 'CODEX_THREAD_ID', 'claudex': 'CLAUDE_SESSION_ID', 'grok': None}
CONTROLLERS = tuple(CONTROLLER_ENV)


def _uuid_or_none(value):
    try:
        return value.lower() if value and str(uuid.UUID(value)) == value.lower() else None
    except (ValueError, AttributeError, TypeError):
        return None


def detect_controller():
    found = [name for name, var in CONTROLLER_ENV.items() if var and os.environ.get(var)]
    if len(found) != 1:
        raise ValueError('Cannot infer controller (%s); pass --controller codex|claudex|grok explicitly'
                         % ('ambiguous: ' + ', '.join(found) if found else 'no native session env'))
    return found[0]


def resolve_owner(controller, session_id=None):
    if controller is None:
        controller = detect_controller()
    if controller not in CONTROLLERS:
        raise ValueError('Unsupported local controller')
    own_var = CONTROLLER_ENV[controller]
    native = os.environ.get(own_var) if own_var else None
    if controller == 'codex' and not native:
        raise ValueError('Native CODEX_THREAD_ID is required; a supplied UUID cannot replace it')
    if controller == 'claudex' and not native and os.environ.get('CODEX_THREAD_ID'):
        raise ValueError('Environment indicates a Codex session, not Claudex; use --controller codex')
    if controller == 'grok' and any(os.environ.get(var) for var in CONTROLLER_ENV.values() if var):
        raise ValueError('Native session environment belongs to another controller; do not select Grok')
    if controller == 'grok' and not session_id:
        raise ValueError('Grok CLI session ID must be passed explicitly with --session-id')
    if native and session_id and native.lower() != session_id.lower():
        raise ValueError('Session ID differs from the current native %s session' % controller)
    session_id = _uuid_or_none(session_id or native)
    if not session_id:
        raise ValueError('Need the actual native conversation ID; unresolved placeholders are refused')
    for other, var in CONTROLLER_ENV.items():
        value = os.environ.get(var) if var and other != controller else None
        if value and value.lower() == session_id:
            raise ValueError('Session ID belongs to the %s controller; never cross-map it' % other)
    return {'controller': controller, 'session_id': session_id}


def owner_key(owner):
    return hashlib.sha256((owner['controller'] + '\0' + owner['session_id']).encode()).hexdigest()


def _directory(path, create=True):
    """Open pinned directory FDs; read-only callers never create components."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('State directory must be an absolute normalized path')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            if create:
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
                raise Blocked('busy', 'Binding operation busy; retain this conversation', True) from None
            self.data = self._read(self.fd)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    @classmethod
    def inspect(cls, path):
        """Read an atomic file snapshot without creating a directory or lock."""
        try:
            fd = _directory(path, create=False)
        except FileNotFoundError:
            return {'schema': 1, 'bindings': {}}
        try:
            return cls._read(fd)
        finally:
            os.close(fd)

    @classmethod
    def _read(cls, directory_fd):
        try:
            leaf = os.open('bindings.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        except FileNotFoundError:
            return {'schema': 1, 'bindings': {}}
        with os.fdopen(leaf, 'r', encoding='utf-8') as source:
            cls._private(source.fileno())
            raw = source.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise ValueError('Registry oversized; preserve it for investigation')
            data = json.loads(raw)
        if not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('bindings'), dict):
            raise ValueError('Invalid registry; do not reset ownership')
        for key, row in data['bindings'].items():
            if not isinstance(row, dict) or owner_key(row['owner']) != key:
                raise ValueError('Invalid ownership record; preserve registry')
            _project_row(row)
        return data

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
    def __init__(self, executable, cwd=None):
        self.executable = executable
        self.cwd = cwd

    def execution_context(self, cwd):
        directory = Path(cwd).resolve(strict=True)
        def from_child(path):
            candidate = Path(path)
            return str(candidate if candidate.is_absolute() else directory / candidate)
        if os.path.dirname(self.executable):
            executable = shutil.which(from_child(self.executable))
        else:
            # exec resolves relative PATH entries after chdir too; do not consult the parent's cwd.
            executable = shutil.which(self.executable, path=os.pathsep.join(map(from_child, os.get_exec_path())))
        if executable is None:
            raise Blocked('unsupported_contract', 'Cannot pin the native executable; do not launch')
        self.executable = str(Path(executable).resolve(strict=True))
        self.cwd = str(directory)
        return {'executable': self.executable, 'cwd': self.cwd}

    @staticmethod
    def _stop(process):
        # Popen creates this session/group; never signal the caller's process group.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            try:
                process.kill()
            except OSError:
                pass
        try:
            process.communicate(timeout=1)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            # A descendant can escape the group while retaining either pipe. Do not await EOF.
            for pipe in (process.stdout, process.stderr):
                if pipe is not None:
                    try:
                        pipe.close()
                    except OSError:
                        pass
            try:
                process.wait(timeout=1)
            except (subprocess.TimeoutExpired, OSError):
                pass

    def __call__(self, args, timeout=None):
        timeout = timeout if timeout is not None else (180 if args[:2] == ['agent', 'launch'] else
                                                      60 if args[:2] == ['terminal', 'send'] else 30)
        try:
            process = subprocess.Popen([self.executable, *args], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, encoding='utf-8', cwd=self.cwd,
                                       start_new_session=True)
        except OSError as exc:
            # Popen did not return a child: positive local no-acceptance evidence.
            raise NativeFailure('launch', started=False, stderr=str(exc)) from None
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            self._stop(process)
            raise NativeFailure('timeout', timeout=timeout, stderr=exc.stderr) from None
        except (OSError, UnicodeError):
            self._stop(process)
            raise NativeFailure('invalid_result') from None
        try:
            result = json.loads(stdout)
        except (ValueError, TypeError):
            result = None
        error = result.get('error') if isinstance(result, dict) and result.get('ok') is False else None
        if process.returncode or isinstance(error, dict):
            # The public CLI prints JSON errors on stdout. Never mine prose for an ID.
            code = error.get('code') if isinstance(error, dict) else None
            launch = error.get('data') if isinstance(error, dict) else None
            try:
                compatibility = json.loads(stderr)
                if error is None and isinstance(compatibility, dict):
                    code = compatibility.get('code')
                    if isinstance(compatibility.get('error'), dict):
                        code = compatibility['error'].get('code', code)
            except (ValueError, TypeError):
                if error is None and stderr.strip() in TRANSIENT_READ_CODES:
                    code = stderr.strip()
            raise NativeFailure('nonzero' if process.returncode else 'invalid_envelope',
                                returncode=process.returncode, stderr=stderr, code=code, receipt=result, launch=launch)
        if result is None:
            raise NativeFailure('invalid_json', stderr=stderr) from None
        if (not isinstance(result, dict) or result.get('ok') is not True
                or not isinstance(result.get('_meta'), dict)
                or not isinstance(result['_meta'].get('runtimeId'), str)
                or not result['_meta']['runtimeId'] or not isinstance(result.get('result'), dict)):
            raise NativeFailure('invalid_envelope', stderr=stderr, receipt=result)
        return result


class BindingManager:
    def __init__(self, state, owner, project, environment, worktree, orca, retry_budget_s=300):
        self.state = Path(state).expanduser().absolute()
        self.project = str(Path(project).resolve(strict=True))
        if not Path(self.project).is_dir() or self.state.resolve().is_relative_to(Path(self.project)):
            raise ValueError('Binding state must live outside the Mac project')
        self.owner = owner
        self.key = owner_key(owner)
        self.environment = environment
        self.worktree = worktree.removeprefix('id:')
        project_id, separator, remote_path = self.worktree.partition('::')
        if not environment or not project_id or not separator or not remote_path.startswith('/'):
            raise ValueError('Need explicit environment and discovered full worktree identity')
        self.orca = orca
        if not math.isfinite(retry_budget_s) or retry_budget_s < 0:
            raise Blocked('invalid_input', 'Read retry budget must be finite and nonnegative')
        self.retry_budget_s = retry_budget_s
        self.read_attempts = self.attempts = 0

    def _call(self, command):
        read = command == ['status'] or command[:2] in (['terminal', 'list'], ['terminal', 'read'], ['terminal', 'wait'])
        while True:
            timeout = (180 if command[:2] == ['agent', 'launch'] else
                       60 if command[:2] == ['terminal', 'send'] else 30)
            if read:
                if self._deadline is not None:
                    remaining = self._deadline - time.monotonic()
                    if remaining <= 0:
                        raise Blocked('unreachable', 'Read budget exhausted; retain binding and intent', True)
                    timeout = min(timeout, remaining)
                self.read_attempts += 1
            try:
                result = self.orca([*command, '--environment', self.environment, '--json'], timeout=timeout)
                if (not isinstance(result, dict) or result.get('ok') is not True
                        or not isinstance(result.get('_meta'), dict)
                        or not isinstance(result['_meta'].get('runtimeId'), str)
                        or not result['_meta']['runtimeId'] or not isinstance(result.get('result'), dict)):
                    raise NativeFailure('invalid_envelope')
                return result
            except NativeFailure as exc:
                transient = exc.code in TRANSIENT_READ_CODES
                if read and transient and self._deadline is not None:
                    delay = (2, 5, 15, 30)[min(self._backoff, 3)]
                    self._backoff += 1
                    if self._deadline - time.monotonic() > delay:
                        time.sleep(delay)
                        continue
                if not read:
                    raise
                raise Blocked('unreachable' if transient or exc.kind == 'timeout' else 'integrity_failure',
                              'Native read unavailable; retain binding and intent', transient) from None

    def _list(self):
        result = self._call(['terminal', 'list'])
        terminals = result['result'].get('terminals')
        if (result['result'].get('truncated') is not False or not isinstance(terminals, list)
                or not all(isinstance(t, dict) for t in terminals)):
            raise Blocked('integrity_failure', 'Incomplete or invalid terminal inventory')
        return result['_meta']['runtimeId'], terminals

    def _row(self, db):
        row = db.data['bindings'].get(self.key)
        if row is None:
            raise Blocked('invalid_input', 'No binding; list targets and choose rebind or explicit create')
        self._destination(row)
        if row.get('state') != 'bound':
            raise Blocked('uncertain_send', 'Creation outcome uncertain; preserve intent')
        self._unoccupied(db, row['runtime'], row['handle'])
        return row

    def _destination(self, row):
        expected = {'owner': self.owner, 'project': self.project, 'environment': self.environment,
                    'worktree': self.worktree}
        if any(row.get(k) != v for k, v in expected.items()):
            raise Blocked('identity_changed', 'Binding destination/project differs; retain binding')

    def _unoccupied(self, db, runtime, handle, reservation=False):
        for key, other in db.data['bindings'].items():
            if key == self.key or other.get('runtime') != runtime:
                continue
            candidate = other.get('creation_candidate') or {}
            launch = (((other.get('creation_launch') or {}).get('outcome') or {})
                      if other.get('state') == 'creating' else {})
            if (other.get('handle') == handle or candidate.get('handle') == handle or launch.get('handle') == handle
                    or (reservation and other.get('state') == 'creating'
                    and not other.get('handle') and other.get('worktree') == self.worktree)):
                raise Blocked('busy', 'Terminal is owned or reserved by another conversation')

    def _snapshot(self):
        with Registry(self.state) as db:
            return copy.deepcopy(self._row(db))

    def _unchanged(self, db, snapshot):
        row = self._row(db)
        if row != snapshot:
            identity = ('owner', 'project', 'environment', 'worktree', 'runtime', 'handle', 'incarnation')
            category = 'identity_changed' if any(row.get(k) != snapshot.get(k) for k in identity) else 'busy'
            raise Blocked(category, 'Binding or intent changed during operation; retain current state')
        return row

    def _send_unchanged(self, db, intent):
        # Reconcile may observe every existing message while this send awaits its receipt.
        # Only those observations may differ; all identities, tasks and attempts stay exact.
        current = self._row(db)
        expected = copy.deepcopy(intent)
        for task_id, task in expected['tasks'].items():
            latest = current['tasks'].get(task_id, {}).get('messages', {})
            for message_id, message in task['messages'].items():
                message.pop('evidence', None)
                if 'evidence' in latest.get(message_id, {}):
                    message['evidence'] = copy.deepcopy(latest[message_id]['evidence'])
        return self._unchanged(db, expected)

    def _verify(self, row):
        runtime, terminals = self._list()
        matches = [t for t in terminals if t.get('handle') == row['handle']]
        if runtime != row['runtime']:
            raise Blocked('identity_changed', 'Bound runtime identity changed; retain binding')
        if len(matches) != 1:
            raise Blocked('unreachable', 'Bound terminal unavailable; retain binding', True)
        terminal = matches[0]
        if (terminal.get('incarnationId') != row['incarnation']
                or terminal.get('worktreeId') != row['worktree']
                or terminal.get('agentIdentity') != 'claude'):
            raise Blocked('identity_changed', 'Bound CC identity changed; do not send')
        if terminal.get('connected') is not True:
            raise Blocked('unreachable', 'Bound CC disconnected; retain identity', True)
        if terminal.get('writable') is not True or terminal.get('orphaned') is not False:
            raise Blocked('busy', 'Bound CC is not safely writable; retain binding')

    @staticmethod
    def _view(row):
        return {k: row[k] for k in ('handle', 'incarnation', 'runtime', 'worktree', 'environment')}

    @_command
    def ensure(self):
        if self.key not in Registry.inspect(self.state)['bindings']:
            raise Blocked('invalid_input', 'No binding; list targets and choose rebind or explicit create')
        with Registry(self.state) as db:
            row = copy.deepcopy(self._row(db))
        self._verify(row)
        with Registry(self.state) as db:
            return self._view(self._unchanged(db, row))

    @staticmethod
    def _creation_ready(row):
        rows = [row] if row is not None else []
        while rows:
            saved = rows.pop()
            if saved.get('active_task') is not None or any(m.get('state') != 'accepted'
                    for task in saved.get('tasks', {}).values() for m in task['messages'].values()):
                raise Blocked('uncertain_send', 'Create requires no active task or unresolved message')
            rows.extend(saved.get('history', []))

    def _creation_unchanged(self, db, snapshot):
        current = db.data['bindings'].get(self.key)
        if current != snapshot:
            raise Blocked('busy', 'Creation reservation changed; retain current state')
        if current is not None:
            self._destination(current)
        return current

    def _creation_inventory(self):
        runtime, terminals = self._list()
        handles = [terminal.get('handle') for terminal in terminals]
        if (not _safe_identity(runtime) or any(not _safe_identity(h) for h in handles)
                or len(set(handles)) != len(handles)):
            raise Blocked('integrity_failure', 'Invalid inventory identity; absence is not proven')
        return runtime, terminals

    def _launch_preflight(self, runtime):
        status = self._call(['status'])
        host = status['result'].get('runtime')
        if (not isinstance(host, dict) or status['_meta']['runtimeId'] != runtime
                or host.get('runtimeId') != runtime):
            raise Blocked('identity_changed', 'Launch runtime changed; preserve the original intent')
        if host.get('state') != 'ready' or host.get('reachable') is not True:
            raise Blocked('unreachable', 'Launch runtime not ready; retain intent', True)
        version = host.get('appVersion')
        capabilities = host.get('capabilities')
        if (not isinstance(version, str) or re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version) is None
                or tuple(map(int, version.split('.'))) < (1, 4, 229)
                or not isinstance(capabilities, list) or not all(isinstance(c, str) for c in capabilities)
                or not LAUNCH_CAPABILITIES <= set(capabilities)):
            raise Blocked('unsupported_contract', 'Need Orca 1.4.229 launch and replay capabilities on the execution host')

    @staticmethod
    def _creation_blocked(intent, detail, category='create_unverified'):
        launch = intent.get('creation_launch') or {}
        view = {k: copy.deepcopy(launch[k]) for k in ('operationId', 'outcome') if k in launch}
        if view:
            view['replay_available'] = (launch.get('retrySafe') is True and not launch.get('outcome')
                                        and launch['replay_attempts'] == 0)
        return Blocked(category, detail, diagnostic=copy.deepcopy(launch.get('diagnostic')), launch=view)

    def _launch_call(self, intent, retry_launch=None):
        if intent['creation_launch']['protocol'] == AUTO_LAUNCH_PROTOCOL:
            return self._auto_launch_call(intent)
        command = ['agent', 'launch', '--agent', 'claude', '--worktree', 'id:' + self.worktree]
        if retry_launch is not None:
            command.extend(['--retry-launch', retry_launch])
        try:
            result = self._call(command)
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            with Registry(self.state) as db:
                row = self._creation_unchanged(db, intent)
                launch = row['creation_launch']
                launch['diagnostic'] = _diagnostic(exc)
                proof = exc.launch if isinstance(exc, NativeFailure) else {}
                if proof and (retry_launch is None or proof['operationId'] == retry_launch):
                    launch.update(operationId=proof['operationId'], retrySafe=True)
                db.save()
                pending = copy.deepcopy(row)
            raise self._creation_blocked(pending, 'Launch outcome unavailable; retain intent, never start a fresh launch') from None
        result_data = result['result']
        outcome, receipt = result_data.get('outcome'), result_data.get('receipt')
        operation = result_data.get('operationId')
        if (result['_meta']['runtimeId'] != intent['runtime'] or result_data.get('worktreeId') != self.worktree
                or not _operation_id(operation) or (retry_launch is not None and operation != retry_launch)
                or not isinstance(outcome, dict) or outcome.get('kind') not in ('terminal', 'structured')
                or not _safe_identity(outcome.get('handle')) or not isinstance(receipt, dict)
                or receipt.get('mode') != outcome['kind']):
            raise self._creation_blocked(intent, 'Launch identity unverifiable; retain intent and do not recreate')
        with Registry(self.state) as db:
            row = self._creation_unchanged(db, intent)
            launch = row['creation_launch']
            launch.update(operationId=operation, outcome={k: outcome[k] for k in ('kind', 'handle')})
            launch.pop('retrySafe', None)
            # The known handle survives any subsequent inventory/read failure, even before incarnation is known.
            db.save()
            return copy.deepcopy(row)

    def _auto_launch_call(self, intent):
        command = ['terminal', 'create', '--worktree', 'id:' + self.worktree, '--command', AUTO_LAUNCH_COMMAND]
        try:
            result = self._call(command)
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            with Registry(self.state) as db:
                row = self._creation_unchanged(db, intent)
                row['creation_launch']['diagnostic'] = _diagnostic(exc)
                db.save()
                pending = copy.deepcopy(row)
            # terminal create has no native replay ledger: unknown stays pending forever.
            raise self._creation_blocked(pending, 'Launch outcome unavailable; retain intent, never start a fresh launch') from None
        terminal = result['result'].get('terminal')
        handle = terminal.get('handle') if isinstance(terminal, dict) else None
        if result['_meta']['runtimeId'] != intent['runtime'] or not _safe_identity(handle):
            raise self._creation_blocked(intent, 'Launch identity unverifiable; retain intent and do not recreate')
        with Registry(self.state) as db:
            row = self._creation_unchanged(db, intent)
            row['creation_launch']['outcome'] = {'kind': 'terminal', 'handle': handle}
            db.save()
            return copy.deepcopy(row)

    def _replay_launch(self, intent, operation):
        launch = intent.get('creation_launch') or {}
        if (not _operation_id(operation) or launch.get('operationId') != operation
                or launch.get('retrySafe') is not True or launch.get('outcome')
                or intent.get('creation_candidate') or launch.get('replay_attempts') != 0):
            raise self._creation_blocked(intent, 'No matching unused native replay proof; preserve intent')
        if self.orca.execution_context(self.project) != launch.get('context'):
            raise Blocked('identity_changed', 'Native launch executable or cwd changed; do not replay')
        runtime, _ = self._creation_inventory()
        if runtime != intent['runtime']:
            raise Blocked('identity_changed', 'Original launch host changed; do not replay')
        self._launch_preflight(runtime)
        with Registry(self.state) as db:
            row = self._creation_unchanged(db, intent)
            row['creation_launch']['replay_attempts'] = 1
            db.save()  # Consume the one explicit replay before calling the native ledger.
            replay = copy.deepcopy(row)
        return self._complete_creation(self._launch_call(replay, operation))

    def _complete_creation(self, intent):
        candidate = intent.get('creation_candidate')
        if not candidate:
            launch = intent.get('creation_launch') or {}
            outcome = launch.get('outcome')
            if not outcome:
                raise self._creation_blocked(intent, 'Creation outcome unknown; retain intent and never submit again')
            if outcome['kind'] == 'structured':
                raise self._creation_blocked(intent, 'Native launch opened a chat; terminal binding is unsupported',
                                             'unsupported_contract')
            with Registry(self.state) as db:
                self._creation_unchanged(db, intent)
                self._unoccupied(db, intent['runtime'], outcome['handle'])
            try:
                runtime, terminals = self._creation_inventory()
            except (ValueError, OSError, subprocess.TimeoutExpired):
                raise self._creation_blocked(intent, 'Launch receipt saved; exact terminal inventory unavailable') from None
            matches = [t for t in terminals if t.get('handle') == outcome['handle']]
            if (runtime != intent['runtime'] or len(matches) != 1
                    or not _safe_identity(matches[0].get('incarnationId'))
                    or matches[0].get('worktreeId') != self.worktree or matches[0].get('agentIdentity') != 'claude'):
                raise self._creation_blocked(intent, 'Launch receipt saved; exact CC identity not verified')
            candidate = {'runtime': runtime, 'handle': outcome['handle'],
                         'incarnation': matches[0]['incarnationId'], 'worktree': self.worktree}
            with Registry(self.state) as db:
                row = self._creation_unchanged(db, intent)
                self._unoccupied(db, runtime, candidate['handle'])
                row['creation_candidate'] = candidate
                db.save()
                intent = copy.deepcopy(row)
        with Registry(self.state) as db:
            self._creation_unchanged(db, intent)
            self._unoccupied(db, candidate['runtime'], candidate['handle'])
        target = {**intent, **candidate, 'tasks': {}, 'active_task': None}
        try:
            self._verify(target)
            self._idle(target)
        except (ValueError, OSError, subprocess.TimeoutExpired):
            raise self._creation_blocked(intent, 'Created target not verified; retain candidate and do not recreate') from None
        with Registry(self.state) as db:
            row = self._creation_unchanged(db, intent)
            self._unoccupied(db, candidate['runtime'], candidate['handle'])
            previous = row.pop('creation_previous', None)
            if previous is not None:
                row.setdefault('history', []).append(previous)
            row.pop('creation_candidate', None)
            row.update(**candidate, state='bound', tasks={}, active_task=None)
            db.save()
            result = {**self._view(row), 'action': 'bound', 'creation_id': row['creation_id']}
            if 'operationId' in row.get('creation_launch', {}):
                result['operationId'] = row['creation_launch']['operationId']
            return result

    @_command
    def create(self, confirm=False, retry_launch=None):
        snapshot = copy.deepcopy(Registry.inspect(self.state)['bindings'].get(self.key))
        if retry_launch is not None and (not confirm or snapshot is None or snapshot.get('state') != 'creating'):
            raise Blocked('invalid_input', 'Replay requires explicit create confirm and the original pending launch')
        if snapshot is not None:
            self._destination(snapshot)
            self._creation_ready(snapshot)
            if snapshot.get('state') == 'creating':
                if not confirm:
                    raise self._creation_blocked(snapshot, 'Pending creation; only verify its saved exact candidate')
                if retry_launch is not None:
                    return self._replay_launch(snapshot, retry_launch)
                return self._complete_creation(snapshot)
            if snapshot.get('state') != 'bound':
                raise Blocked('integrity_failure', 'Invalid binding state; preserve registry')
        context = self.orca.execution_context(self.project)
        try:
            runtime, terminals = self._creation_inventory()
        except Blocked as exc:
            if exc.category == 'unreachable':
                raise Blocked('unreachable', 'Runtime unavailable; wait one to two minutes and inspect the same operation',
                              exc.retryable) from None
            raise
        if snapshot is not None:
            if runtime != snapshot['runtime']:
                raise Blocked('identity_changed', 'Runtime changed; original absence is not proven')
            matches = [t for t in terminals if t.get('handle') == snapshot['handle']]
            if matches:
                if (len(matches) != 1 or matches[0].get('incarnationId') != snapshot['incarnation']
                        or matches[0].get('worktreeId') != self.worktree or matches[0].get('agentIdentity') != 'claude'):
                    raise Blocked('identity_changed', 'Original target identity changed; do not create')
                if matches[0].get('connected') is not True:
                    raise Blocked('unreachable', 'Original target disconnected; wait one to two minutes and inspect', True)
                raise Blocked('has_live_binding', 'A live binding exists; retain it instead of creating')
        self._launch_preflight(runtime)
        if not confirm:
            matching = [t for t in terminals if t.get('worktreeId') == self.worktree]
            inventory = []
            for terminal in matching[:20]:
                item = {}
                for key in ('handle', 'incarnationId', 'agentIdentity'):
                    if _safe_identity(terminal.get(key)):
                        item[key] = terminal[key]
                for key in ('connected', 'writable', 'orphaned'):
                    if type(terminal.get(key)) is bool:
                        item[key] = terminal[key]
                inventory.append(item)
            return {'action': 'dry_run', 'plan': {'project': self.worktree, 'agent': 'claude',
                    'required_mode': 'auto', 'placement': 'terminal in the explicit worktree',
                    'command': AUTO_LAUNCH_COMMAND},
                    'inventory': inventory, 'inventory_count': len(matching),
                    'inventory_limited': len(matching) > 20}
        row = {'owner': self.owner, 'project': self.project, 'environment': self.environment,
               'worktree': self.worktree, 'runtime': runtime, 'state': 'creating',
               'creation_id': str(uuid.uuid4()), 'tasks': {}, 'active_task': None}
        row['creation_launch'] = {'protocol': NEW_CREATE_PROTOCOL, 'context': context,
                                  'replay_attempts': 0}
        _launch_record(row)
        if snapshot is not None:
            previous = copy.deepcopy(snapshot)
            previous.pop('history', None)
            row.update(tasks=copy.deepcopy(snapshot['tasks']), history=copy.deepcopy(snapshot.get('history', [])),
                       creation_previous=previous)
        with Registry(self.state) as db:
            self._creation_unchanged(db, snapshot)
            db.data['bindings'][self.key] = copy.deepcopy(row)
            db.save()  # Reservation is durable before the single, non-retried create.
        return self._complete_creation(self._launch_call(row))

    def _idle(self, row, allow_hint=True):
        wait = self._call(['terminal', 'wait', '--terminal', row['handle'], '--for', 'tui-idle',
                          '--timeout-ms', '1000'])
        status = wait['result'].get('wait')
        if not isinstance(status, dict) or type(status.get('satisfied')) is not bool:
            raise Blocked('integrity_failure', 'Invalid native wait response; do not send')
        if wait['_meta']['runtimeId'] != row['runtime']:
            raise Blocked('identity_changed', 'Runtime changed while waiting; retain binding')
        if status['satisfied'] is not True:
            raise Blocked('busy', 'Bound CC busy; wait on this terminal, do not create another', True)
        stream = self._call(['terminal', 'read', '--terminal', row['handle'], '--limit', '1'])
        screen = self._call(['terminal', 'read', '--terminal', row['handle'], '--screen'])
        if any(r['_meta']['runtimeId'] != row['runtime'] for r in (stream, screen)):
            raise Blocked('identity_changed', 'Runtime changed while checking input')
        stream_terminal = stream['result'].get('terminal')
        terminal = screen['result'].get('terminal')
        if not isinstance(stream_terminal, dict) or not isinstance(terminal, dict):
            raise Blocked('integrity_failure', 'Invalid native read response; do not send')
        if stream_terminal.get('handle') != row['handle']:
            raise Blocked('identity_changed', 'Stream destination changed; do not send')
        tail = terminal.get('tail')
        if not isinstance(tail, list) or not all(isinstance(line, str) for line in tail):
            raise Blocked('integrity_failure', 'Invalid native screen lines; preserve input')
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
        if allow_hint and not row['tasks']:
            # Reject any reported `draft` above; screen matching is only a heuristic.
            # Hidden-cursor input identical to a hint may be ambiguous, not proven empty.
            # Accept only this exact startup set, never arbitrary "Try" text.
            allowed.update(CLAUDE_EMPTY_PLACEHOLDERS)
        if content not in allowed:
            raise ValueError('Bound CC has a nonempty or ambiguous draft; preserve it')
        cursor = stream_terminal.get('latestCursor')
        if not isinstance(cursor, (str, int)) or isinstance(cursor, bool) or cursor == '':
            raise Blocked('integrity_failure', 'Native pre-send cursor unavailable')
        self._verify(row)
        return cursor

    @staticmethod
    def _attempts(task):
        if not task:
            return 0
        counts = [m.get('attempts', 1) for m in task['messages'].values()]
        counts.append(task.get('attempts', 0))
        if any(type(n) is not int or n < 0 for n in counts):
            raise Blocked('integrity_failure', 'Invalid attempt history; preserve registry')
        return max(sum(counts[:-1]), counts[-1])

    @staticmethod
    def _accepted(row, receipt):
        return (receipt.get('runtimeId') == row['runtime'] and receipt.get('handle') == row['handle']
                and receipt.get('processIncarnation') == row['incarnation']
                and bool(receipt.get('requestId')) and receipt.get('accepted') is True
                and 'input_accepted' in receipt.get('stages', []))

    @_command
    def send(self, task_id, message_id, text, retry_request=None):
        if retry_request is not None:
            raise Blocked('unsupported_contract', 'Native request retry contract is unavailable')
        if (not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', task_id)
                or not isinstance(message_id, str) or not re.fullmatch(r'main|export-[1-9][0-9]*', message_id)):
            raise Blocked('invalid_input', 'Need valid message identity and bounded text without reserved markers')
        try:
            validate_prompt_transport(text)
        except ValueError:
            raise Blocked('invalid_input', 'Need bounded UTF-8 text without NUL or reserved markers') from None
        digest = hashlib.sha256(text.encode()).hexdigest()
        snapshot = self._snapshot()
        task = snapshot['tasks'].get(task_id)
        for old in snapshot.get('history', []):
            archived = old.get('tasks', {}).get(task_id)
            if archived is not None:
                self.attempts = self._attempts(archived)
                raise Blocked('invalid_input', 'Task identity is archived; rebind does not authorize replay')
        self.attempts = self._attempts(task)
        previous = task['messages'].get(message_id) if task else None
        if previous:
            if previous['sha256'] != digest:
                raise Blocked('invalid_input', 'Message identity reused for different content')
            if previous['state'] != 'not_sent':
                return {'action': 'resume', 'binding': self._view(snapshot), 'message': previous}
        if snapshot['active_task'] not in (None, task_id):
            raise Blocked('busy', 'Another task is pending on this conversation')
        if any(m['state'] != 'accepted' for name, t in snapshot['tasks'].items() for mid, m in t['messages'].items()
               if (name, mid) != (task_id, message_id)):
            raise Blocked('uncertain_send', 'An unresolved message remains; use read-only recovery')
        if task and task.get('closed'):
            raise Blocked('invalid_input', 'Task is closed; new submissions are refused')
        if message_id != 'main' and (not task or task['messages'].get('main', {}).get('state') != 'accepted'):
            raise Blocked('invalid_input', 'Export requires an accepted main on this task')
        if self.attempts >= 2:
            raise Blocked('busy', 'Task submission limit reached; do not change message IDs')
        self._verify(snapshot)
        cursor = self._idle(snapshot)
        with Registry(self.state) as db:
            row = self._unchanged(db, snapshot)
            task = row['tasks'].setdefault(task_id, {'closed': False, 'messages': {}})
            self.attempts += 1
            task['attempts'] = self.attempts
            message = {'state': 'sending', 'sha256': digest, 'cursor': cursor,
                       'attempts': previous.get('attempts', 1) + 1 if previous else 1,
                       'attempt_id': uuid.uuid4().hex}
            task['messages'][message_id] = message
            row['active_task'] = task_id
            db.save()  # Unknown outcome remains durable if the process dies.
            intent = copy.deepcopy(row)
        wire = text + '\n\ngrok-cc-msg:' + task_id + '/' + message_id + '/' + digest[:8]
        try:
            result = self._call(['terminal', 'send', '--terminal', snapshot['handle'], '--text', wire,
                                 '--enter', '--wait-submit', '15'])
        except (NativeFailure, OSError, subprocess.TimeoutExpired) as exc:
            native = isinstance(exc, NativeFailure)
            not_sent = native and exc.kind == 'launch' and exc.started is False and not exc.receipt
            with Registry(self.state) as db:
                row = self._send_unchanged(db, intent)
                message = row['tasks'][task_id]['messages'][message_id]
                message['error'] = {'kind': exc.kind if native and exc.kind in
                    ('launch', 'timeout', 'nonzero', 'invalid_json', 'invalid_envelope', 'invalid_result') else 'unknown',
                    'returncode': exc.returncode if native and type(exc.returncode) is int else None}
                if native and exc.receipt:
                    message['receipt'] = exc.receipt
                if not_sent:
                    message['state'] = 'not_sent'
                db.save()
            if not native:
                raise
            if not_sent:
                raise Blocked('unreachable', 'Local send process did not start; explicit same-message retry only', True) from None
            raise Blocked('uncertain_send', 'Send outcome uncertain; retain intent and never repeat') from None
        receipt = _receipt(result)
        accepted = self._accepted(snapshot, receipt)
        with Registry(self.state) as db:
            row = self._send_unchanged(db, intent)
            message = row['tasks'][task_id]['messages'][message_id]
            message['receipt'] = receipt
            if accepted:
                message['state'] = 'accepted'
            db.save()
            if not accepted:
                raise Blocked('uncertain_send', 'Send identity/result uncertain; retain receipt')
            return {'action': 'sent', 'binding': self._view(row), 'message': copy.deepcopy(message)}

    @_command
    def finish(self, task_id):
        snapshot = self._snapshot()
        task = snapshot['tasks'].get(task_id)
        self.attempts = self._attempts(task)
        if not task or snapshot['active_task'] not in (None, task_id):
            raise Blocked('invalid_input', 'Task not active in this conversation')
        if any(m['state'] != 'accepted' for m in task['messages'].values()):
            raise Blocked('uncertain_send', 'Unknown send outcome must remain pending')
        self._verify(snapshot); self._idle(snapshot)
        with Registry(self.state) as db:
            row = self._unchanged(db, snapshot)
            row['tasks'][task_id]['closed'] = True
            row['active_task'] = None
            db.save()
            return {'action': 'dispatch-task-closed', 'binding': self._view(row),
                    'project_pass': False, 'task_id': task_id}

    @_command
    def reconcile(self, task_id, message_id=None):
        snapshot = self._snapshot()
        task = snapshot['tasks'].get(task_id)
        self.attempts = self._attempts(task)
        if not task or (message_id is not None and message_id not in task['messages']):
            raise Blocked('invalid_input', 'Reconcile requires a saved task/message')
        selected = {mid: m for mid, m in task['messages'].items() if message_id is None or mid == message_id}
        self._verify(snapshot)
        evidence = {}
        for mid, message in selected.items():
            cursor = message.get('cursor')
            if not isinstance(cursor, (str, int)) or isinstance(cursor, bool):
                evidence[mid] = {'complete': False, 'reason': 'saved_cursor_unavailable'}
                continue
            result = self._call(['terminal', 'read', '--terminal', snapshot['handle'],
                                 '--cursor', str(cursor), '--limit', '1000'])
            terminal = result['result'].get('terminal')
            if (not isinstance(terminal, dict) or result['_meta']['runtimeId'] != snapshot['runtime']
                    or terminal.get('handle') != snapshot['handle']):
                raise Blocked('identity_changed', 'Reconcile destination changed; retain intent')
            # Cursor continuity cannot be inferred by comparing opaque cursor strings.
            readable = (terminal.get('source') == 'stream' and terminal.get('limited') is False
                        and terminal.get('truncated') is False)
            complete = readable and terminal.get('cursor') == str(cursor)
            evidence[mid] = {'complete': complete, 'receipt_readable': readable,
                             'reason': 'stream_not_acceptance_proof' if complete else 'incomplete_stream'}
        self._verify(snapshot)
        with Registry(self.state) as db:
            row = self._unchanged(db, snapshot)
            messages = row['tasks'][task_id]['messages']
            for mid in selected:
                message = messages[mid]
                if (message['state'] == 'sending' and evidence[mid].get('receipt_readable')
                        and self._accepted(row, _receipt(message.get('receipt')))):
                    message['state'] = 'accepted'
                    evidence[mid]['reason'] = 'saved_receipt_proves_acceptance'
                message['evidence'] = evidence[mid]
            db.save()
            return {'action': 'reconciled', 'binding': self._view(row),
                    'messages': {mid: copy.deepcopy(messages[mid]) for mid in selected},
                    'read_attempts': self.read_attempts}

    @_command
    def rebind(self, confirm_handle, confirm_incarnation):
        if not confirm_handle or not confirm_incarnation:
            raise Blocked('invalid_input', 'Rebind requires confirmed handle and incarnation')
        snapshot = self._snapshot()
        if snapshot['active_task'] is not None or any(m['state'] != 'accepted'
                for task in snapshot['tasks'].values() for m in task['messages'].values()):
            raise Blocked('uncertain_send', 'Rebind requires no active task or unresolved message')
        runtime, terminals = self._list()
        matches = [t for t in terminals if t.get('handle') == confirm_handle]
        if len(matches) != 1 or matches[0].get('incarnationId') != confirm_incarnation:
            raise Blocked('identity_changed', 'Confirmed rebind target is unavailable or changed')
        candidate = {**snapshot, 'runtime': runtime, 'handle': confirm_handle, 'incarnation': confirm_incarnation}
        with Registry(self.state) as db:
            self._unchanged(db, snapshot)
            self._unoccupied(db, runtime, confirm_handle, reservation=True)
        self._verify(candidate)
        self._idle(candidate, allow_hint=False)
        with Registry(self.state) as db:
            row = self._unchanged(db, snapshot)
            self._unoccupied(db, runtime, confirm_handle, reservation=True)
            if (runtime, confirm_handle, confirm_incarnation) == (row['runtime'], row['handle'], row['incarnation']):
                return self._view(row)  # A confirmed no-op cannot erase task identities or counters.
            old = copy.deepcopy(row)
            old.pop('history', None)  # Prior snapshots remain in the flat history, never duplicated recursively.
            row.setdefault('history', []).append(old)
            row.pop('creation_launch', None)
            row.update(runtime=runtime, handle=confirm_handle, incarnation=confirm_incarnation,
                       tasks={}, active_task=None)
            db.save()
            return self._view(row)


class SafeParser(argparse.ArgumentParser):
    def error(self, _message):
        # argparse's default error includes the rejected value, which can be a secret.
        raise Blocked('invalid_input', 'Invalid command arguments; consult --help')


def main():
    manager = None
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument('command', choices=['ensure', 'create', 'send', 'finish', 'identity', 'reconcile', 'rebind'])
        parser.add_argument('--controller', choices=list(CONTROLLERS))
        parser.add_argument('--session-id')
        parser.add_argument('--project-root')
        parser.add_argument('--environment', default='Grok Bot')
        parser.add_argument('--worktree')
        parser.add_argument('--project', dest='create_project')
        parser.add_argument('--confirm', action='store_true')
        parser.add_argument('--state-dir', default=str(Path.home() / '.local/state/grok-cc'))
        parser.add_argument('--orca', default=os.environ.get('ORCA_CLI_COMMAND', 'orca'))
        parser.add_argument('--task-id')
        parser.add_argument('--message-id')
        parser.add_argument('--text-file')
        parser.add_argument('--retry-budget-s', type=float, default=300)
        parser.add_argument('--retry-request', nargs='?', const='')
        parser.add_argument('--retry-launch')
        parser.add_argument('--confirm-handle')
        parser.add_argument('--confirm-incarnation')
        args = parser.parse_args()
        if args.retry_request is not None:
            raise Blocked('unsupported_contract', 'Native request retry contract is unavailable')
        if args.command != 'create' and (args.create_project is not None or args.confirm or args.retry_launch is not None):
            raise Blocked('invalid_input', 'Project/confirm parameters require explicit create')
        if args.retry_launch is not None and not args.confirm:
            raise Blocked('invalid_input', 'Native launch replay requires explicit confirm')
        if args.command == 'create':
            if not args.create_project or (args.worktree and
                    args.worktree.removeprefix('id:') != args.create_project.removeprefix('id:')):
                raise Blocked('invalid_input', 'Create requires an explicit matching project/worktree')
            args.worktree = args.create_project
        owner = resolve_owner(args.controller, args.session_id)
        if args.command == 'identity':
            result = {'owner': owner, 'key': owner_key(owner)}
        else:
            if not args.project_root or not args.worktree:
                raise Blocked('invalid_input', 'Need project-root and explicit cloud worktree')
            manager = BindingManager(args.state_dir, owner, args.project_root, args.environment,
                                     args.worktree, NativeOrca(args.orca, cwd=args.project_root), args.retry_budget_s)
            if args.command == 'ensure':
                result = manager.ensure()
            elif args.command == 'create':
                result = manager.create(confirm=args.confirm, retry_launch=args.retry_launch)
            elif args.command == 'rebind':
                result = manager.rebind(args.confirm_handle, args.confirm_incarnation)
            else:
                if not args.task_id:
                    raise Blocked('invalid_input', 'Need task-id')
                if args.command == 'send':
                    if not args.text_file:
                        raise Blocked('invalid_input', 'Need reviewed prompt text-file')
                    result = manager.send(args.task_id, args.message_id or 'main',
                                          Path(args.text_file).read_bytes().decode('utf-8'))
                elif args.command == 'reconcile':
                    result = manager.reconcile(args.task_id, args.message_id)
                else:
                    result = manager.finish(args.task_id)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        if isinstance(exc, Blocked):
            blocked = exc
        elif isinstance(exc, (OSError, KeyError, TypeError, json.JSONDecodeError)):
            blocked = Blocked('integrity_failure', 'Local state or input unavailable; preserve existing records')
        else:
            blocked = Blocked('invalid_input', 'Invalid identity or input; preserve existing records')
        if manager is not None:
            blocked.attempts = manager.attempts
            blocked.read_attempts = manager.read_attempts
        print(json.dumps(blocked.result(), ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

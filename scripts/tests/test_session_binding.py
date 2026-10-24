"""Author: elvis. Real private-state/locking tests; only remote Orca is doubled."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import io
import time
import errno
import fcntl
import stat

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
TARGET = SCRIPTS / 'session_binding.py'
OWNER_A = {'controller': 'codex', 'session_id': '11111111-1111-4111-8111-111111111111'}
OWNER_B = {'controller': 'claudex', 'session_id': '22222222-2222-4222-8222-222222222222'}
OWNER_G = {'controller': 'grok', 'session_id': '33333333-3333-4333-8333-33333333333a'}
WORKTREE = 'repo::/home/box/orca/projects/hello'
LAUNCH_CAPABILITIES = ['agent.launch.v2', 'agent.launch.replay-required.v1',
                       'agent.launch.local-presentation.v1']
OPERATION_ID = '1792370000000-00000000000000000000000000000001'


def launch_result(terminal, operation_id=OPERATION_ID, kind='terminal'):
    return {'operationId': operation_id, 'outcome': {'kind': kind, 'handle': terminal['handle']},
            'worktreeId': terminal['worktreeId'], 'receipt': {'mode': kind, 'detail': 'PRIVATE-DETAIL'}}


class RemoteOrca:
    """External CLI boundary only, matching observed native JSON fields."""
    def __init__(self):
        self.terminals = []
        self.creates = self.sends = 0
        self.offline = self.busy = self.lose_create = self.lose_send = False
        self.mode = 'auto mode on'
        self.draft = ''
        self.native_draft = None  # Orca 1.4.229 typed-text (non-dim, before cursor) classification
        self.source = 'screen'
        self.runtime = 'runtime-one'
        self.prompt_space = ' '
        self.calls = []
        self.hook = None
        self.executable = '/fixture/orca'
        self.version = '1.4.229'
        self.capabilities = list(LAUNCH_CAPABILITIES)
        self.ready = True
        self.launches = {}
        self.replays = 0

    def execution_context(self, cwd):
        return {'executable': self.executable, 'cwd': cwd}

    def __call__(self, args, timeout=None):
        self.calls.append((list(args), timeout))
        if self.hook:
            result = self.hook(args)
            if result is not None:
                return result
        if self.offline:
            raise OSError('remote_runtime_unavailable')
        envelope = {'ok': True, '_meta': {'runtimeId': self.runtime}}
        action = args[1] if args[0] != 'status' else 'status'
        if action == 'status':
            envelope['result'] = {'runtime': {'state': 'ready' if self.ready else 'starting',
                'reachable': self.ready, 'runtimeId': self.runtime, 'appVersion': self.version,
                'capabilities': list(self.capabilities)}}
        elif action == 'list':
            envelope['result'] = {'terminals': copy.deepcopy(self.terminals), 'truncated': False}
        elif action == 'create':
            assert args[args.index('--command') + 1] == 'claude --permission-mode auto', args
            self.creates += 1
            terminal = {'handle': 'term_' + str(self.creates), 'incarnationId': 'inc_' + str(self.creates),
                        'worktreeId': WORKTREE, 'agentIdentity': 'claude', 'connected': True,
                        'writable': True, 'orphaned': False}
            self.terminals.append(terminal)
            if self.lose_create:
                raise TimeoutError('response lost after create')
            envelope['result'] = {'terminal': {'handle': terminal['handle'], 'worktreeId': WORKTREE}}
        elif action == 'launch':
            if '--retry-launch' in args:
                self.replays += 1
                operation_id = args[args.index('--retry-launch') + 1]
                terminal = self.launches[operation_id]
            else:
                self.creates += 1
                operation_id = '1792370000000-' + format(self.creates, '032x')
                terminal = {'handle': 'term_' + str(self.creates), 'incarnationId': 'inc_' + str(self.creates),
                        'worktreeId': WORKTREE, 'agentIdentity': 'claude', 'connected': True,
                        'writable': True, 'orphaned': False}
                self.terminals.append(terminal)
                self.launches[operation_id] = copy.deepcopy(terminal)
            if self.lose_create:
                raise TimeoutError('response lost after create')
            envelope['result'] = launch_result(terminal, operation_id)
        elif action == 'wait':
            envelope['result'] = {'wait': {'satisfied': not self.busy}}
        elif action == 'read':
            screen = '--screen' in args
            # Orca replaces a typed composer row with the bare glyph and reports it as `draft`.
            row = '❯' if screen and self.native_draft else '❯' + self.prompt_space + self.draft
            envelope['result'] = {'terminal': {'handle': args[args.index('--terminal') + 1],
                'tail': ['────────', row, '────────', '⏵⏵ ' + self.mode],
                'source': self.source if screen else 'stream', 'truncated': False, 'limited': False,
                'latestCursor': '41', 'nextCursor': '41', 'oldestCursor': '0'}}
            if screen and self.native_draft:
                envelope['result']['terminal']['draft'] = self.native_draft
        elif action == 'send':
            self.sends += 1
            if self.lose_send:
                raise TimeoutError('response lost after send')
            terminal = next(t for t in self.terminals if t['handle'] == args[args.index('--terminal') + 1])
            envelope['result'] = {'send': {'handle': terminal['handle'], 'accepted': True,
                'prompt': {'requestId': 'request-' + str(self.sends),
                    'processIncarnation': terminal['incarnationId'],
                    'stages': ['input_accepted', 'turn_started']}}}
        else:
            raise AssertionError('Unexpected native mutation/action: ' + str(args))
        return envelope


class BindingTests(unittest.TestCase):
    def setUp(self):
        # Isolate from the real controller session env (e.g. tests run inside Codex/Claude).
        _env = patch.dict(os.environ)
        _env.start()
        self.addCleanup(_env.stop)
        for _name in ('CODEX_THREAD_ID', 'CLAUDE_SESSION_ID', 'GROK_SESSION_ID'):
            os.environ.pop(_name, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.project = self.root / 'project'
        self.project.mkdir()
        self.state = self.root / 'state'
        self.remote = RemoteOrca()
        self.assertTrue(TARGET.is_file(), 'Missing durable conversation-binding implementation')
        spec = importlib.util.spec_from_file_location('session_binding', TARGET)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        # Existing suite keeps covering saved agent.launch.v2 behavior; AutoLaunchTests cover the new path.
        self.mod.NEW_CREATE_PROTOCOL = self.launch_protocol or 'agent.launch.v2'

    launch_protocol = None

    def manager(self, owner=OWNER_A, project=None, env='Grok Bot', worktree=WORKTREE):
        return self.mod.BindingManager(self.state, owner, project or self.project, env, worktree, self.remote)

    def explicit_create(self, manager=None, confirm=True):
        manager = manager or self.manager()
        self.assertTrue(callable(getattr(manager, 'create', None)), 'Missing explicit create entry point')
        return manager.create(confirm=confirm)

    def fixture_env(self):
        # A forgotten --orca must fail locally, never find an installed CLI.
        return {**os.environ, 'CODEX_THREAD_ID': OWNER_A['session_id'],
                'PATH': str(self.root / 'fixture-only-path'),
                'ORCA_CLI_COMMAND': str(self.root / 'disabled-default-orca')}

    def unknown_launch(self):
        """The external host admitted a launch; only its replay envelope was returned."""
        def lose(args):
            if args[:2] == ['agent', 'launch']:
                self.remote.hook = None
                result = self.remote(args)
                self.remote.hook = lose
                raise self.failure('nonzero', returncode=1, code='agent_session_operation_unknown',
                    stderr='PRIVATE-STDERR', launch={'launchOutcome': 'unknown', 'retrySafe': True,
                        'operationId': result['result']['operationId'], 'launchRequest': 'PRIVATE-PROMPT'})
        self.remote.hook = lose
        with self.assertRaises(self.mod.Blocked) as caught:
            self.explicit_create()
        self.remote.hook = None
        return caught.exception

    def cli_fixture(self):
        path = self.root / 'orca-create-fixture'
        path.write_text('#!' + sys.executable + '\n' + '''
import json,pathlib,sys,os,time
p=pathlib.Path(__file__).parent
args=sys.argv[1:]; action=args[1] if args[0]!='status' else 'status'
with (p/'native-calls.jsonl').open('a') as f: f.write(json.dumps(args)+'\\n')
with (p/'native-cwds.jsonl').open('a') as f: f.write(json.dumps(os.getcwd())+'\\n')
t={'handle':'term-cli','incarnationId':'inc-cli','worktreeId':'repo::/home/box/orca/projects/hello','agentIdentity':'claude','connected':True,'writable':True,'orphaned':False}
if action=='status': r={'runtime':{'state':'ready','reachable':True,'runtimeId':'runtime-cli','appVersion':'1.4.229','capabilities':['agent.launch.v2','agent.launch.replay-required.v1','agent.launch.local-presentation.v1']}}
elif action=='list': r={'terminals':[t] if (p/'created-cli').exists() else [],'truncated':False}
elif action=='create':
 assert args[args.index('--command')+1]=='claude --permission-mode auto'
 with (p/'created-cli').open('a') as f: f.write('create\\n')
 r={'terminal':{'handle':t['handle'],'worktreeId':t['worktreeId']}}
elif action=='launch':
 if '--retry-launch' not in args:
  with (p/'created-cli').open('a') as f: f.write('create\\n')
 r={'operationId':'1792370000000-00000000000000000000000000000001','outcome':{'kind':'terminal','handle':t['handle']},'worktreeId':t['worktreeId'],'receipt':{'mode':'terminal'}}
 if (p/'unknown-reply').exists() and '--retry-launch' not in args:
  print(json.dumps({'ok':False,'error':{'code':'agent_session_operation_unknown','message':'PRIVATE-MESSAGE','data':{'launchOutcome':'unknown','retrySafe':True,'operationId':r['operationId'],'launchRequest':'PRIVATE-SOURCE','cause':'PRIVATE-CAUSE','recoveryCommand':['PRIVATE-AUTH']}},'_meta':{'runtimeId':None}})); sys.exit(1)
 if '--retry-launch' in args:
  assert args[args.index('--retry-launch')+1]==r['operationId']
  assert (p/'created-cli').read_text()=='create\\n'
  with (p/'replayed-cli').open('a') as f: f.write('replay\\n')
  time.sleep(.1)
elif action=='wait': r={'wait':{'satisfied':True}}
elif action=='read': r={'terminal':{'handle':'term-cli','tail':['────────','❯','────────','auto mode on'],'source':'screen' if '--screen' in args else 'stream','truncated':False,'limited':False,'latestCursor':'1'}}
elif action=='send': r={'send':{'handle':'term-cli','accepted':True,'prompt':{'requestId':'request-cli','processIncarnation':'inc-cli','stages':['input_accepted','turn_started']}}}
else: raise SystemExit('unsupported fixture operation')
print(json.dumps({'ok':True,'result':r,'_meta':{'runtimeId':'runtime-cli'}}))
''')
        path.chmod(0o700)
        return path

    def test_prepare_render_send_cli_preserves_crlf_and_bare_cr_bytes(self):
        executable = self.cli_fixture()
        env = self.fixture_env()
        common = ['--controller', 'codex', '--project-root', str(self.project),
                  '--worktree', WORKTREE, '--state-dir', str(self.state), '--orca', str(executable)]
        created = subprocess.run([sys.executable, '-B', str(TARGET), 'create', *common,
            '--project', WORKTREE, '--confirm'], env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(created.returncode, 0, created.stderr)
        source = b'first\r\nsecond\rthird\n'
        (self.project / 'notes.txt').write_bytes(source)
        packet, prompt = self.root / 'packet.json', self.root / 'reviewed.txt'
        for command in ([str(SCRIPTS / 'task_packet.py'), 'prepare', '--root', str(self.project),
                         '--file', 'notes.txt', '--task', 'Preserve the supplied line endings', '--out', str(packet)],
                        [str(SCRIPTS / 'task_packet.py'), 'render', '--packet', str(packet), '--out', str(prompt)]):
            result = subprocess.run([sys.executable, '-B', *command], env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
        reviewed = prompt.read_bytes()
        self.assertIn(source, reviewed)
        task_id = json.loads(packet.read_bytes())['task_id']
        sent = subprocess.run([sys.executable, '-B', str(TARGET), 'send', *common,
            '--task-id', task_id, '--text-file', str(prompt)], env=env,
            capture_output=True, text=True, timeout=15)
        self.assertEqual(sent.returncode, 0, sent.stderr)
        calls = [json.loads(line) for line in (self.root / 'native-calls.jsonl').read_text().splitlines()]
        sends = [args for args in calls if args[:2] == ['terminal', 'send']]
        self.assertEqual(len(sends), 1)
        digest = self.mod.hashlib.sha256(reviewed).hexdigest()
        expected = reviewed + ('\n\ngrok-cc-msg:' + task_id + '/main/' + digest[:8]).encode()
        self.assertEqual(sends[0][sends[0].index('--text') + 1].encode(), expected)
        self.assertEqual(json.loads(sent.stdout)['message']['sha256'], digest)

    def test_send_transport_rejection_preserves_state_before_native_calls(self):
        m = self.manager(); m.create(confirm=True)
        before = (self.state / 'bindings.json').read_bytes()
        calls = len(self.remote.calls)
        for text in (None, 42, b'bytes', '', ' \r\n\t', 'grok-cc-msg:reserved',
                     'x' * (450 * 1024 + 1), '汉' * (150 * 1024 + 1), 'has\0nul'):
            with self.subTest(kind=type(text).__name__, size=len(text) if isinstance(text, (str, bytes)) else None):
                with self.assertRaises(self.mod.Blocked) as caught:
                    m.send('task-one', 'main', text)
                self.assertEqual(caught.exception.category, 'invalid_input')
                self.assertEqual((self.state / 'bindings.json').read_bytes(), before)
                self.assertEqual(len(self.remote.calls), calls)

    def test_relative_executable_is_pinned_from_child_cwd_before_every_native_call(self):
        source = self.cli_fixture()
        caller = self.root / 'caller'; caller.mkdir()
        for directory in (caller, self.project):
            target = directory / 'orca'
            target.write_bytes(source.read_bytes()); target.chmod(0o700)
        for case, executable in enumerate(('./orca', 'orca')):
            with self.subTest(executable=executable):
                self.state = self.root / ('path-state-' + str(case))
                command = [sys.executable, '-B', str(TARGET), 'create', '--controller', 'codex',
                           '--project-root', str(self.project), '--project', WORKTREE, '--confirm',
                           '--state-dir', str(self.state), '--orca', executable]
                result = subprocess.run(command, cwd=caller, env={**self.fixture_env(), 'PATH': '.'},
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse((caller / 'native-calls.jsonl').exists(), 'Must not change executable after preflight')
                calls = [json.loads(line) for line in (self.project / 'native-calls.jsonl').read_text().splitlines()]
                self.assertEqual(sum(a[:2] in (['agent', 'launch'], ['terminal', 'create']) for a in calls), 1)
                self.assertEqual(self.saved()['creation_launch']['context'], {
                    'cwd': str(self.project), 'executable': str(self.project / 'orca')})
                self.assertTrue(all(json.loads(cwd) == str(self.project)
                                for cwd in (self.project / 'native-cwds.jsonl').read_text().splitlines()))
                for name in ('native-calls.jsonl', 'native-cwds.jsonl', 'created-cli'):
                    (self.project / name).unlink()

    def test_null_saved_outcome_is_blocked_as_json_before_other_owner_queries(self):
        self.explicit_create()
        self.unknown_launch_for_other_owner()
        original = json.loads((self.state / 'bindings.json').read_text())
        executable = self.cli_fixture()
        command = [sys.executable, '-B', str(TARGET), 'ensure', '--controller', 'codex',
                   '--project-root', str(self.project), '--worktree', WORKTREE,
                   '--state-dir', str(self.state), '--orca', str(executable)]
        for field, value in (('outcome', None), ('outcome', []), ('outcome', {'kind': 'terminal'}),
                             ('diagnostic', None), ('diagnostic', {'kind': [], 'started': True}),
                             ('diagnostic', {'kind': 'nonzero', 'started': True, 'code': []}),
                             ('diagnostic', {'kind': 'timeout', 'started': True, 'timeout': 10 ** 400})):
            with self.subTest(field=field, value=value):
                data = copy.deepcopy(original)
                data['bindings'][self.mod.owner_key(OWNER_B)]['creation_launch'][field] = value
                (self.state / 'bindings.json').write_text(json.dumps(data))
                before = (self.state / 'bindings.json').read_bytes()
                result = subprocess.run(command, env=self.fixture_env(), capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(json.loads(result.stderr)['category'], 'integrity_failure')
                self.assertEqual((self.state / 'bindings.json').read_bytes(), before)
                self.assertFalse((self.root / 'native-calls.jsonl').exists())

    def unknown_launch_for_other_owner(self):
        self.remote.lose_create = True
        with self.assertRaises(self.mod.Blocked): self.explicit_create(self.manager(OWNER_B))
        self.remote.lose_create = False

    def test_fixture_environment_disables_unselected_native_cli(self):
        result = subprocess.run([sys.executable, '-B', str(TARGET), 'create', '--controller', 'codex',
            '--project-root', str(self.project), '--project', WORKTREE, '--confirm',
            '--state-dir', str(self.state), '--retry-budget-s', '0'], env=self.fixture_env(),
            capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stderr)['category'], 'unsupported_contract')
        self.assertFalse(self.state.exists())

    def test_launch_receipt_is_durable_before_inventory_and_incarnation_lookup(self):
        observed = []
        def observe(args):
            if args[:2] == ['terminal', 'list'] and self.remote.creates:
                row = self.saved()
                observed.append(copy.deepcopy(row.get('creation_launch')))
        self.remote.hook = observe
        result = self.explicit_create()
        self.assertTrue(observed)
        self.assertEqual(observed[0]['operationId'], OPERATION_ID)
        self.assertEqual(observed[0]['outcome'], {'kind': 'terminal', 'handle': 'term_1'})
        self.assertEqual(result['incarnation'], 'inc_1')
        self.assertNotIn('PRIVATE', (self.state / 'bindings.json').read_text())
        args, timeout = next((a, t) for a, t in self.remote.calls if a[:2] == ['agent', 'launch'])
        self.assertEqual(timeout, 180)
        self.assertEqual(args[:2], ['agent', 'launch'])

    def test_launch_preflight_rejects_old_missing_capability_and_unready_before_reservation(self):
        for version, caps, ready in (('1.4.228', LAUNCH_CAPABILITIES, True),
                ('unknown', LAUNCH_CAPABILITIES, True), ('1.4.229-beta', LAUNCH_CAPABILITIES, True),
                ('1.4.229', LAUNCH_CAPABILITIES[:-1], True), ('1.4.229', LAUNCH_CAPABILITIES, False)):
            with self.subTest(version=version, caps=caps, ready=ready):
                self.remote.version, self.remote.capabilities, self.remote.ready = version, caps, ready
                with self.assertRaises(self.mod.Blocked): self.explicit_create()
                self.assertFalse(self.state.exists())
                self.assertEqual(self.remote.creates, 0)

    def test_structured_outcome_stays_pending_without_terminal_verification_or_replay(self):
        def structured(args):
            if args[:2] == ['agent', 'launch']:
                return {'ok': True, '_meta': {'runtimeId': self.remote.runtime}, 'result':
                        launch_result({'handle': 'agent_1', 'worktreeId': WORKTREE}, kind='structured')}
        self.remote.hook = structured
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
        self.assertEqual(caught.exception.category, 'unsupported_contract')
        self.assertEqual(self.saved()['creation_launch']['outcome']['kind'], 'structured')
        self.assertNotIn('creation_candidate', self.saved())
        before = (self.state / 'bindings.json').read_bytes(); calls = len(self.remote.calls)
        for action in (lambda: self.explicit_create(),
                       lambda: self.manager().create(confirm=True, retry_launch=OPERATION_ID),
                       lambda: self.manager().send('one', 'main', 'text')):
            with self.assertRaises(self.mod.Blocked): action()
        self.assertEqual((self.state / 'bindings.json').read_bytes(), before)
        self.assertEqual(len(self.remote.calls), calls)
        self.assertEqual(self.remote.sends, 0)

    def test_unknown_launch_reports_only_safe_fields_and_replays_same_id_once(self):
        failure = self.unknown_launch()
        row = self.saved(); creation_id = row['creation_id']
        self.assertEqual(row['creation_launch']['operationId'], OPERATION_ID)
        self.assertEqual(row['creation_launch']['replay_attempts'], 0)
        self.assertEqual(failure.result()['diagnostic']['code'], 'agent_session_operation_unknown')
        self.assertNotIn('PRIVATE', json.dumps(failure.result()) + (self.state / 'bindings.json').read_text())
        before = (self.state / 'bindings.json').read_bytes(); calls = len(self.remote.calls)
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.assertEqual(len(self.remote.calls), calls)
        self.assertEqual((self.state / 'bindings.json').read_bytes(), before)
        bound = self.manager().create(confirm=True, retry_launch=OPERATION_ID)
        self.assertEqual(bound['handle'], 'term_1')
        self.assertEqual(self.saved()['creation_id'], creation_id)
        self.assertEqual(self.saved()['creation_launch']['replay_attempts'], 1)
        self.assertEqual((self.remote.creates, self.remote.replays, self.remote.sends), (1, 1, 0))
        command = next(a for a, _ in self.remote.calls if '--retry-launch' in a)
        self.assertEqual(command[command.index('--retry-launch') + 1], OPERATION_ID)
        with self.assertRaises(self.mod.Blocked): self.manager().create(confirm=True, retry_launch=OPERATION_ID)
        self.assertEqual(self.remote.replays, 1)

    def test_replay_requires_saved_id_confirm_original_context_and_budget(self):
        self.unknown_launch()
        original = (self.state / 'bindings.json').read_bytes()
        calls = len(self.remote.calls)
        for confirm, identity in ((False, OPERATION_ID), (True, '1792370000000-' + 'a' * 32),
                                  (True, 'PRIVATE-ID')):
            with self.subTest(confirm=confirm, identity=identity):
                with self.assertRaises(self.mod.Blocked): self.manager().create(confirm=confirm, retry_launch=identity)
                self.assertEqual(len(self.remote.calls), calls)
                self.assertEqual((self.state / 'bindings.json').read_bytes(), original)
        self.remote.executable = '/fixture/different-orca'
        with self.assertRaises(self.mod.Blocked): self.manager().create(confirm=True, retry_launch=OPERATION_ID)
        self.assertEqual(len(self.remote.calls), calls)
        self.remote.executable = '/fixture/orca'
        self.remote.runtime = 'upgraded-runtime'
        with self.assertRaises(self.mod.Blocked): self.manager().create(confirm=True, retry_launch=OPERATION_ID)
        self.assertEqual(self.remote.replays, 0)
        self.assertEqual((self.state / 'bindings.json').read_bytes(), original)
        self.remote.runtime = 'runtime-one'
        def lose_again(args):
            if '--retry-launch' in args:
                self.remote.replays += 1
                self.assertEqual(self.saved()['creation_launch']['replay_attempts'], 1)
                raise self.failure('nonzero', code='agent_session_operation_unknown', launch={
                    'launchOutcome': 'unknown', 'retrySafe': True, 'operationId': OPERATION_ID})
        self.remote.hook = lose_again
        with self.assertRaises(self.mod.Blocked): self.manager().create(confirm=True, retry_launch=OPERATION_ID)
        self.remote.hook = None
        with self.assertRaises(self.mod.Blocked): self.manager().create(confirm=True, retry_launch=OPERATION_ID)
        self.assertEqual(self.remote.replays, 1)
        self.assertEqual(self.remote.creates, 1)

    def test_legacy_no_id_pending_is_unchanged_after_upgrade_even_with_retry_flag(self):
        self.remote.lose_create = True
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.change_row(lambda row: row.pop('creation_launch', None))
        before = (self.state / 'bindings.json').read_bytes(); calls = len(self.remote.calls)
        self.remote.lose_create = False; self.remote.runtime = 'upgraded-runtime'; self.remote.terminals.clear()
        for action in (lambda: self.explicit_create(),
                       lambda: self.manager().create(confirm=True, retry_launch=OPERATION_ID)):
            with self.assertRaises(self.mod.Blocked): action()
        self.assertEqual((self.state / 'bindings.json').read_bytes(), before)
        self.assertEqual(len(self.remote.calls), calls)
        self.assertEqual(self.remote.creates, 1)

    def test_known_receipt_survives_failed_inventory_and_can_only_resume_exact_handle(self):
        def fail_inventory(args):
            if args[:2] == ['terminal', 'list'] and self.remote.creates:
                raise self.failure('invalid_json', stderr='PRIVATE-INVENTORY')
        self.remote.hook = fail_inventory
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.assertEqual(self.saved()['creation_launch']['outcome']['handle'], 'term_1')
        self.assertNotIn('creation_candidate', self.saved())
        self.remote.hook = None
        self.remote.terminals[0]['incarnationId'] = 'inc-exact-from-inventory'
        bound = self.explicit_create()
        self.assertEqual(bound['incarnation'], 'inc-exact-from-inventory')
        self.assertEqual((self.remote.creates, self.remote.replays), (1, 0))

    def test_stdout_native_error_contract_is_minimized_not_parsed_from_prose(self):
        native = self.mod.NativeOrca('/fixture/orca')
        data = {'launchOutcome': 'unknown', 'retrySafe': True, 'operationId': OPERATION_ID,
                'launchRequest': 'PRIVATE-PROMPT', 'cause': 'PRIVATE-CAUSE', 'recoveryCommand': 'PRIVATE'}
        for returncode in (0, 1):
            process = Mock(returncode=returncode)
            process.communicate.return_value = (json.dumps({'ok': False, 'error': {
                'code': 'agent_session_operation_unknown', 'message': 'PRIVATE', 'data': data}}), 'PRIVATE-STDERR')
            with patch.object(self.mod.subprocess, 'Popen', return_value=process):
                with self.assertRaises(self.mod.NativeFailure) as caught: native(['agent', 'launch'])
            self.assertEqual(caught.exception.code, 'agent_session_operation_unknown')
            self.assertEqual(caught.exception.launch, {k: data[k] for k in ('launchOutcome', 'retrySafe', 'operationId')})
            self.assertNotIn('PRIVATE', str(caught.exception) + json.dumps(caught.exception.launch))
        for poison in ({**data, 'operationId': 'PRIVATE'}, {**data, 'retrySafe': 'true'},
                       {'message': OPERATION_ID, 'launchOutcome': 'unknown', 'retrySafe': True},
                       {**data, 'launchOutcome': 'success'}):
            process = Mock(returncode=1)
            process.communicate.return_value = (json.dumps({'ok': False, 'error': {
                'code': 'agent_session_operation_unknown', 'data': poison}}), OPERATION_ID)
            with patch.object(self.mod.subprocess, 'Popen', return_value=process):
                with self.assertRaises(self.mod.NativeFailure) as caught: native(['agent', 'launch'])
            self.assertEqual(caught.exception.launch, {})

    def test_real_cli_replays_stdout_unknown_once_under_concurrent_callers(self):
        executable = self.cli_fixture()
        (self.root / 'unknown-reply').touch()
        env = self.fixture_env()
        command = [sys.executable, '-B', str(TARGET), 'create', '--controller', 'codex',
                   '--project-root', str(self.project), '--project', WORKTREE, '--confirm',
                   '--state-dir', str(self.state), '--orca', str(executable)]
        # A pre-upgrade agent.launch.v2 reservation; new reservations use the auto terminal path.
        legacy = [sys.executable, '-B', '-c', 'import pathlib,runpy,sys;sys.argv=sys.argv[1:];'
                  'sys.path.insert(0,str(pathlib.Path(sys.argv[0]).parent));'
                  'm=runpy.run_path(sys.argv[0]);m["NEW_CREATE_PROTOCOL"]="agent.launch.v2";'
                  'g=m["main"].__globals__;g["NEW_CREATE_PROTOCOL"]="agent.launch.v2";sys.exit(m["main"]())',
                  str(TARGET), *command[3:]]
        first = subprocess.run(legacy, capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(first.returncode, 1, first.stdout)
        blocked = json.loads(first.stderr)
        self.assertEqual(blocked['launch']['operationId'], OPERATION_ID)
        self.assertTrue(blocked['launch']['replay_available'])
        self.assertEqual(blocked['diagnostic']['returncode'], 1)
        self.assertNotIn('PRIVATE', first.stdout + first.stderr + (self.state / 'bindings.json').read_text())
        pending_id = self.saved()['creation_id']
        before = (self.state / 'bindings.json').read_bytes()
        again = subprocess.run(command, capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(again.returncode, 1)
        self.assertEqual((self.state / 'bindings.json').read_bytes(), before)
        replay = [*command, '--retry-launch', OPERATION_ID]
        processes = [subprocess.Popen(replay, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
                     for _ in range(4)]
        outputs = [(p, p.communicate(timeout=15)) for p in processes]
        self.assertTrue(any(p.returncode == 0 for p, _ in outputs), outputs)
        self.assertTrue(all(p.returncode in (0, 1) for p, _ in outputs))
        self.assertEqual((self.root / 'created-cli').read_text(), 'create\n')
        self.assertEqual((self.root / 'replayed-cli').read_text(), 'replay\n')
        self.assertEqual(self.saved()['creation_id'], pending_id)
        self.assertEqual(self.saved()['state'], 'bound')
        self.assertEqual(self.saved()['creation_launch']['replay_attempts'], 1)
        calls = [json.loads(line) for line in (self.root / 'native-calls.jsonl').read_text().splitlines()]
        self.assertEqual(sum(a[:2] == ['agent', 'launch'] for a in calls), 2)
        self.assertEqual(sum('--retry-launch' in a for a in calls), 1)
        cwds = [json.loads(line) for line in (self.root / 'native-cwds.jsonl').read_text().splitlines()]
        self.assertTrue(cwds and all(cwd == str(self.project) for cwd in cwds))

    def test_replay_reservation_fsync_failure_prevents_native_replay(self):
        self.unknown_launch()
        original = (self.state / 'bindings.json').read_bytes()
        fsync = self.mod.os.fsync
        for directory in (False, True):
            with self.subTest(directory=directory):
                (self.state / 'bindings.json').write_bytes(original)
                def fail(fd):
                    if stat.S_ISDIR(os.fstat(fd).st_mode) == directory:
                        raise OSError('PRIVATE-SYNC')
                    return fsync(fd)
                with patch.object(self.mod.os, 'fsync', side_effect=fail):
                    with self.assertRaises(OSError):
                        self.manager().create(confirm=True, retry_launch=OPERATION_ID)
                self.assertEqual(self.remote.replays, 0)
                if directory:
                    with self.assertRaises(self.mod.Blocked):
                        self.manager().create(confirm=True, retry_launch=OPERATION_ID)
                    self.assertEqual(self.remote.replays, 0)

    def test_receipt_handle_without_candidate_already_reserves_other_owner_target(self):
        m = self.manager(); self.explicit_create(m)
        def missing_inventory(args):
            if args[:2] == ['terminal', 'list'] and self.remote.creates == 2:
                raise self.failure('invalid_json')
        self.remote.hook = missing_inventory
        with self.assertRaises(self.mod.Blocked): self.explicit_create(self.manager(OWNER_B))
        self.remote.hook = None
        data = json.loads((self.state / 'bindings.json').read_text())
        other = data['bindings'][self.mod.owner_key(OWNER_B)]
        self.assertNotIn('creation_candidate', other)
        self.assertEqual(other['creation_launch']['outcome']['handle'], 'term_2')
        before = (self.state / 'bindings.json').read_bytes()
        with self.assertRaises(self.mod.Blocked) as caught: m.rebind('term_2', 'inc_2')
        self.assertEqual(caught.exception.category, 'busy')
        self.assertEqual((self.state / 'bindings.json').read_bytes(), before)
        self.assertEqual((self.remote.creates, self.remote.replays), (2, 0))

    def test_status_inventory_runtime_mismatch_never_reserves_creation(self):
        def changed(args):
            if args[0] == 'status':
                return {'ok': True, '_meta': {'runtimeId': 'replacement-runtime'},
                        'result': {'runtime': {'runtimeId': 'replacement-runtime', 'state': 'ready',
                            'reachable': True, 'appVersion': '1.4.229', 'capabilities': LAUNCH_CAPABILITIES}}}
        self.remote.hook = changed
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
        self.assertEqual(caught.exception.category, 'identity_changed')
        self.assertFalse(self.state.exists())
        self.assertEqual(self.remote.creates, 0)

    def test_mismatched_replay_receipt_cannot_replace_original_operation_id(self):
        self.unknown_launch()
        def mismatch(args):
            if '--retry-launch' in args:
                return {'ok': True, '_meta': {'runtimeId': self.remote.runtime},
                        'result': launch_result(self.remote.terminals[0], operation_id='1792370000000-' + 'a' * 32)}
        self.remote.hook = mismatch
        with self.assertRaises(self.mod.Blocked): self.manager().create(confirm=True, retry_launch=OPERATION_ID)
        self.assertEqual(self.saved()['creation_launch']['operationId'], OPERATION_ID)
        self.assertEqual(self.saved()['creation_launch']['replay_attempts'], 1)
        self.assertNotIn('creation_candidate', self.saved())
        self.assertNotIn('outcome', self.saved()['creation_launch'])

    def test_retry_launch_is_rejected_before_native_calls_for_other_commands_or_without_confirm(self):
        for action, flags in (('identity', []), ('ensure', []), ('send', []), ('rebind', []),
                              ('create', ['--project', WORKTREE])):
            with self.subTest(action=action):
                error = io.StringIO()
                args = ['session_binding', action, '--controller', 'codex', '--retry-launch', OPERATION_ID, *flags]
                with patch.object(sys, 'argv', args), patch.object(self.mod, 'NativeOrca') as native, \
                        patch('sys.stderr', error):
                    self.assertEqual(self.mod.main(), 1)
                native.assert_not_called()
                self.assertEqual(json.loads(error.getvalue())['category'], 'invalid_input')

    def test_explicit_ensure_without_binding_has_no_native_or_state_side_effect(self):
        with self.assertRaises(self.mod.Blocked) as caught:
            self.manager().ensure()
        self.assertEqual(caught.exception.category, 'invalid_input')
        self.assertFalse(self.state.exists())
        self.assertEqual(self.remote.calls, [])

    def test_explicit_empty_dry_run_has_no_directory_lock_or_intent(self):
        result = self.explicit_create(confirm=False)
        self.assertEqual(result['action'], 'dry_run')
        self.assertEqual(result['plan']['project'], WORKTREE)
        self.assertEqual(result['inventory'], [])
        self.assertEqual(result['inventory_count'], 0)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.remote.creates, 0)

    def test_explicit_dry_run_filters_bounds_and_projects_inventory(self):
        for i in range(25):
            self.remote.terminals.append({'handle': 't-' + str(i), 'incarnationId': 'i-' + str(i),
                'worktreeId': WORKTREE, 'agentIdentity': 'claude', 'connected': True,
                'writable': True, 'orphaned': False, 'screen': 'PRIVATE-DRAFT', 'unknown': 'PRIVATE-NATIVE'})
        self.remote.terminals.append({'handle': 'foreign', 'worktreeId': 'other::/private', 'screen': 'PRIVATE-OTHER'})
        result = self.explicit_create(confirm=False)
        self.assertEqual(result['inventory_count'], 25)
        self.assertEqual(len(result['inventory']), 20)
        self.assertTrue(result['inventory_limited'])
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertNotIn('foreign', json.dumps(result))
        self.assertFalse(self.state.exists())

    def test_explicit_confirmation_persists_candidate_then_verifies_before_binding(self):
        states = []
        def observe(args):
            if args[1] in ('launch', 'wait', 'read'):
                row = self.saved()
                states.append((args[1], row['state'], 'creation_candidate' in row))
        self.remote.hook = observe
        first = self.explicit_create()
        self.assertEqual(first['handle'], 'term_1')
        self.assertEqual(self.saved()['state'], 'bound')
        self.assertEqual(states[0], ('launch', 'creating', False))
        self.assertTrue(all(state == 'creating' and candidate for action, state, candidate in states[1:]))
        command = next(args for args, _ in self.remote.calls if args[1] == 'launch')
        self.assertEqual(command[command.index('--worktree') + 1], 'id:' + WORKTREE)
        self.assertEqual(command[:2], ['agent', 'launch'])
        self.assertEqual(command[command.index('--agent') + 1], 'claude')
        for flag in ('--command', '--prompt', '--model', '--effort', '--title', '--permission-mode'):
            self.assertNotIn(flag, command)
        self.assertNotIn('--retry-request', command)
        self.assertEqual(self.remote.creates, 1)

    def test_explicit_create_cli_dispatch_and_confirmation_boundary(self):
        fixture = self.cli_fixture()
        common = ['--controller', 'codex', '--session-id', OWNER_A['session_id'],
                  '--project-root', str(self.project), '--project', WORKTREE,
                  '--state-dir', str(self.state), '--orca', str(fixture)]
        env = self.fixture_env()
        def invoke(extra=()):
            return subprocess.run([sys.executable, '-B', str(TARGET), 'create', *common, *extra],
                                  capture_output=True, text=True, env=env, timeout=15)
        dry = invoke()
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertEqual(json.loads(dry.stdout)['action'], 'dry_run')
        self.assertFalse(self.state.exists())
        mismatch = invoke(['--worktree', 'other::/elsewhere', '--confirm'])
        self.assertEqual(mismatch.returncode, 1)
        self.assertFalse(self.state.exists())
        created = invoke(['--confirm'])
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertEqual(json.loads(created.stdout)['handle'], 'term-cli')
        duplicate = invoke(['--confirm'])
        self.assertEqual(duplicate.returncode, 1)
        self.assertEqual(json.loads(duplicate.stderr)['category'], 'has_live_binding')
        self.assertEqual((self.root / 'created-cli').read_text(), 'create\n')
        calls = [json.loads(line) for line in (self.root / 'native-calls.jsonl').read_text().splitlines()]
        self.assertEqual(sum(args[1] in ('launch', 'create') for args in calls), 1)
        self.assertFalse(any(args[:2] == ['agent', 'launch'] for args in calls))

    def test_explicit_reservation_sync_failure_prevents_native_create(self):
        original = self.mod.os.fsync
        for directory in (False, True):
            with self.subTest(directory=directory):
                m = self.manager()
                m.state = self.root / ('dir-failure' if directory else 'file-failure')
                def fail(fd):
                    if stat.S_ISDIR(os.fstat(fd).st_mode) == directory:
                        raise OSError('injected sync failure')
                    return original(fd)
                with patch.object(self.mod.os, 'fsync', side_effect=fail):
                    with self.assertRaises((ValueError, OSError)):
                        self.explicit_create(m)
                self.assertEqual(self.remote.creates, 0)
                if directory:
                    with self.assertRaises(self.mod.Blocked): self.explicit_create(m)
                    self.assertEqual(self.remote.creates, 0)

    def test_explicit_failed_native_launch_is_not_resubmitted(self):
        def no_launch(args):
            if args[1] == 'launch': raise self.failure('launch', started=False)
        self.remote.hook = no_launch
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
        self.assertEqual(caught.exception.category, 'create_unverified')
        identity = self.saved()['creation_id']
        self.remote.hook = None
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.assertEqual(self.saved()['creation_id'], identity)
        self.assertEqual(sum(args[1] == 'launch' for args, _ in self.remote.calls), 1)

    def test_explicit_lost_receipt_does_not_infer_owner_or_recreate(self):
        self.remote.lose_create = True
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
        self.assertEqual(caught.exception.category, 'create_unverified')
        before = (self.state / 'bindings.json').read_bytes()
        self.remote.lose_create = False
        self.assertEqual(len(self.remote.terminals), 1)
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.assertEqual((self.state / 'bindings.json').read_bytes(), before)
        self.assertEqual(self.remote.creates, 1)

    def test_explicit_bad_receipt_stays_pending_without_native_repeat(self):
        def malformed(args):
            if args[1] == 'launch':
                return {'ok': True, '_meta': {'runtimeId': 'runtime-one'},
                        'result': {'terminal': {'handle': {'bad': True}, 'worktreeId': WORKTREE}}}
        self.remote.hook = malformed
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.remote.hook = None
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.assertEqual(sum(args[1] == 'launch' for args, _ in self.remote.calls), 1)
        self.assertEqual(self.saved()['state'], 'creating')

    def test_explicit_saved_candidate_resumes_only_read_verification(self):
        self.remote.draft = 'real unsent user draft'
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
        self.assertEqual(caught.exception.category, 'create_unverified')
        row = self.saved()
        self.assertEqual(row['state'], 'creating')
        self.assertEqual(row['creation_candidate']['handle'], 'term_1')
        self.assertEqual(self.remote.draft, 'real unsent user draft')
        self.remote.draft = ''
        bound = self.explicit_create()
        self.assertEqual(bound['handle'], 'term_1')
        self.assertEqual(self.saved()['creation_id'], row['creation_id'])
        self.assertEqual(self.remote.creates, 1)

    def test_explicit_live_active_and_uncertain_bindings_are_not_replaced(self):
        m = self.manager(); self.explicit_create(m)
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create(m)
        self.assertEqual(caught.exception.category, 'has_live_binding')
        m.send('task-one', 'main', 'text')
        self.remote.terminals.clear()
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create(m)
        self.assertEqual(caught.exception.category, 'uncertain_send')
        self.change_row(lambda row: row.update(active_task=None))
        self.change_row(lambda row: row['tasks']['task-one']['messages']['main'].update(state='sending'))
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create(m)
        self.assertEqual(caught.exception.category, 'uncertain_send')
        self.assertEqual(self.remote.creates, 1)

    def test_explicit_disconnected_or_changed_runtime_does_not_prove_absence(self):
        m = self.manager(); self.explicit_create(m)
        self.remote.terminals[0]['connected'] = False
        with self.assertRaises(self.mod.Blocked): self.explicit_create(m)
        self.remote.terminals.clear(); self.remote.runtime = 'changed-runtime'
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create(m)
        self.assertEqual(caught.exception.category, 'identity_changed')
        self.assertEqual(self.remote.creates, 1)

    def test_explicit_replacement_preserves_archived_task_identity_and_attempts(self):
        m = self.manager(); first = self.explicit_create(m)
        m.send('task-one', 'main', 'text'); m.send('task-one', 'export-1', 'export'); m.finish('task-one')
        self.remote.terminals.clear()
        second = self.explicit_create(m)
        self.assertNotEqual(first['handle'], second['handle'])
        old = self.saved()['history'][0]
        self.assertEqual(old['tasks']['task-one']['attempts'], 2)
        self.assertNotIn('history', old)
        with self.assertRaises(self.mod.Blocked) as caught: m.send('task-one', 'main', 'text')
        self.assertEqual(caught.exception.attempts, 2)
        self.assertEqual(self.remote.sends, 2)

    def test_explicit_legacy_creating_blocks_every_mutating_entry_point(self):
        m = self.manager(); self.explicit_create(m)
        def legacy(row):
            row.update(state='creating')
            row.pop('handle', None); row.pop('incarnation', None); row.pop('creation_launch', None)
        self.change_row(legacy)
        before = (self.state / 'bindings.json').read_bytes()
        for action in (lambda: self.explicit_create(m), m.ensure,
                       lambda: m.send('new-task', 'main', 'text'), lambda: m.rebind('some', 'inc')):
            with self.assertRaises(self.mod.Blocked): action()
        self.assertEqual((self.state / 'bindings.json').read_bytes(), before)
        self.assertEqual(self.remote.creates, 1)
        self.assertEqual(self.remote.sends, 0)

    def test_explicit_late_create_receipt_cannot_overwrite_changed_intent(self):
        def drift(args):
            if args[1] == 'launch':
                self.change_row(lambda row: row.update(creation_id='99999999-9999-4999-8999-999999999999'))
        self.remote.hook = drift
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.assertEqual(self.saved()['creation_id'], '99999999-9999-4999-8999-999999999999')
        self.assertEqual(self.saved()['state'], 'creating')
        self.assertNotIn('creation_candidate', self.saved())
        self.remote.hook = None
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.assertEqual(self.remote.creates, 1)

    def test_explicit_dry_run_refuses_symlink_state_without_touching_target(self):
        target = self.root / 'private-target'; target.mkdir(mode=0o700)
        self.state.symlink_to(target, target_is_directory=True)
        with self.assertRaises((ValueError, OSError)): self.explicit_create(confirm=False)
        self.assertEqual(list(target.iterdir()), [])
        self.assertEqual(self.remote.calls, [])

    def test_explicit_candidate_requires_valid_saved_intent_identity(self):
        self.remote.draft = 'unsent draft'
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.change_row(lambda row: row.update(creation_id='not-a-valid-intent-id'))
        before = (self.state / 'bindings.json').read_bytes()
        calls = len(self.remote.calls)
        self.remote.draft = ''
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
        self.assertEqual(caught.exception.category, 'integrity_failure')
        self.assertEqual(len(self.remote.calls), calls)
        self.assertEqual((self.state / 'bindings.json').read_bytes(), before)

    def test_explicit_malformed_inventory_never_proves_prior_absence(self):
        m = self.manager(); self.explicit_create(m)
        before = (self.state / 'bindings.json').read_bytes()
        for terminals in ([{'worktreeId': WORKTREE}],
                          [{'handle': 'duplicate'}, {'handle': 'duplicate'}]):
            with self.subTest(terminals=terminals):
                self.remote.terminals = terminals
                with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create(m)
                self.assertEqual(caught.exception.category, 'integrity_failure')
                self.assertEqual(self.remote.creates, 1)
                self.assertEqual((self.state / 'bindings.json').read_bytes(), before)

    def test_explicit_invalid_runtime_is_rejected_before_reservation(self):
        self.remote.runtime = 'unsafe runtime value'
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
        self.assertEqual(caught.exception.category, 'integrity_failure')
        self.assertEqual(self.remote.creates, 0)
        self.assertFalse(self.state.exists())

    def test_explicit_unreachable_suggests_wait_without_reserving(self):
        def unavailable(args):
            raise self.failure('nonzero', code='remote_runtime_unavailable')
        self.remote.hook = unavailable
        m = self.manager(); m.retry_budget_s = 0
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create(m)
        self.assertEqual(caught.exception.category, 'unreachable')
        self.assertIn('one to two minutes', caught.exception.detail)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.remote.creates, 0)

    def test_explicit_recovery_rejects_missing_or_inconsistent_previous_tasks(self):
        m = self.manager(); self.explicit_create(m)
        m.send('completed', 'main', 'text'); m.send('completed', 'export-1', 'format'); m.finish('completed')
        self.remote.terminals.clear(); self.remote.draft = 'preserved draft'
        with self.assertRaises(self.mod.Blocked): self.explicit_create(m)
        pending = json.loads((self.state / 'bindings.json').read_text())
        mutations = (
            lambda row: row.pop('creation_previous'),
            lambda row: row['creation_previous'].update(tasks={}),
            lambda row: row['creation_previous'].update(active_task='completed'),
            lambda row: row['creation_previous']['tasks']['completed']['messages']['main'].update(state='sending'),
        )
        self.remote.draft = ''
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                data = copy.deepcopy(pending)
                mutation(data['bindings'][self.mod.owner_key(OWNER_A)])
                (self.state / 'bindings.json').write_text(json.dumps(data))
                before = (self.state / 'bindings.json').read_bytes(); calls = len(self.remote.calls)
                with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create(m)
                self.assertEqual(caught.exception.category, 'integrity_failure')
                self.assertEqual((self.state / 'bindings.json').read_bytes(), before)
                self.assertEqual(len(self.remote.calls), calls)
                self.assertEqual(self.remote.sends, 2)
        (self.state / 'bindings.json').write_text(json.dumps(pending))
        self.explicit_create(m)
        with self.assertRaises(self.mod.Blocked): m.send('completed', 'main', 'text')
        self.assertEqual(self.remote.sends, 2)

    def test_explicit_incomplete_project_cli_is_rejected_before_any_side_effect(self):
        fixture = self.cli_fixture()
        common = ['--controller', 'codex', '--session-id', OWNER_A['session_id'],
                  '--project-root', str(self.project)]
        env = self.fixture_env()
        for i, selector in enumerate(('repo::', '::/path', 'repo::relative')):
            with self.subTest(selector=selector):
                case = self.root / ('selector-' + str(i)); case.mkdir()
                executable = case / 'fixture'; executable.write_bytes(fixture.read_bytes()); executable.chmod(0o700)
                result = subprocess.run([sys.executable, '-B', str(TARGET), 'create', *common,
                                         '--state-dir', str(case / 'state'), '--orca', str(executable),
                                         '--project', selector, '--confirm'],
                                        capture_output=True, text=True, env=env, timeout=15)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(json.loads(result.stderr)['category'], 'invalid_input')
                self.assertFalse((case / 'state').exists())
                self.assertFalse((case / 'native-calls.jsonl').exists())
        valid = subprocess.run([sys.executable, '-B', str(TARGET), 'create', *common,
                                '--state-dir', str(self.state), '--orca', str(fixture),
                                '--project', 'id:' + WORKTREE, '--confirm'],
                               capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertEqual(json.loads(valid.stdout)['worktree'], WORKTREE)
        self.assertEqual((self.root / 'created-cli').read_text(), 'create\n')

    def test_explicit_other_owner_pending_candidate_reserves_exact_target(self):
        other = self.manager(OWNER_B); self.remote.draft = 'other owner draft'
        with self.assertRaises(self.mod.Blocked): self.explicit_create(other)
        saved = json.loads((self.state / 'bindings.json').read_text())
        other_row = copy.deepcopy(saved['bindings'][self.mod.owner_key(OWNER_B)])
        target = copy.deepcopy(self.remote.terminals[0]); self.remote.draft = ''
        def stale_receipt(args):
            if args[1] == 'launch':
                return {'ok': True, '_meta': {'runtimeId': self.remote.runtime}, 'result': launch_result(target, operation_id='1792370000000-00000000000000000000000000000002')}
        self.remote.hook = stale_receipt
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
        self.assertEqual(caught.exception.category, 'busy')
        data = json.loads((self.state / 'bindings.json').read_text())
        self.assertEqual(data['bindings'][self.mod.owner_key(OWNER_B)], other_row)
        self.assertEqual(self.saved()['state'], 'creating')
        self.assertNotIn('handle', self.saved())
        self.assertNotIn('creation_candidate', self.saved())
        # A persisted colliding candidate is also blocked before any remote reads on recovery.
        self.change_row(lambda row: row.update(creation_candidate=copy.deepcopy(other_row['creation_candidate'])))
        before = (self.state / 'bindings.json').read_bytes(); calls = len(self.remote.calls)
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
        self.assertEqual(caught.exception.category, 'busy')
        self.assertEqual((self.state / 'bindings.json').read_bytes(), before)
        self.assertEqual(len(self.remote.calls), calls)
        self.assertEqual(sum(args[1] == 'launch' for args, _ in self.remote.calls), 2)

    def test_repeated_ensure_creates_only_once(self):
        first = self.manager().create(confirm=True)
        second = self.manager().ensure()
        self.assertEqual(first['handle'], second['handle'])
        self.assertEqual(first['incarnation'], second['incarnation'])
        self.assertEqual(self.remote.creates, 1)

    def test_distinct_owner_ignores_idle_foreign_terminal(self):
        a = self.manager().create(confirm=True)
        b = self.manager(OWNER_B).create(confirm=True)
        self.assertNotEqual(a['handle'], b['handle'])
        self.assertEqual(self.manager().ensure()['handle'], a['handle'])
        self.assertEqual(self.remote.creates, 2)

    def test_successive_tasks_reuse_binding_and_preserve_history(self):
        m = self.manager()
        first = m.create(confirm=True)
        m.send('task-one', 'main', 'code task one')
        m.finish('task-one')
        m.send('task-two', 'main', 'code task two')
        m.finish('task-two')
        self.assertEqual(m.ensure()['handle'], first['handle'])
        old = m.send('task-one', 'main', 'code task one')
        self.assertEqual(old['action'], 'resume')
        self.assertEqual(self.remote.creates, 1)
        self.assertEqual(self.remote.sends, 2)

    def test_duplicate_message_is_resume_and_changed_text_is_refused(self):
        m = self.manager(); m.create(confirm=True)
        first = m.send('task-one', 'main', 'original text')
        repeat = m.send('task-one', 'main', 'original text')
        self.assertEqual(first['message']['receipt'], repeat['message']['receipt'])
        with self.assertRaises(ValueError):
            m.send('task-one', 'main', 'different text')
        self.assertEqual(self.remote.sends, 1)

    def test_pending_other_task_blocks_and_export_stays_on_same_terminal(self):
        m = self.manager(); first = m.create(confirm=True)
        m.send('task-one', 'main', 'original text')
        with self.assertRaises(ValueError):
            m.send('task-two', 'main', 'other task')
        result = m.send('task-one', 'export-1', 'export final patch only')
        self.assertEqual(result['binding']['handle'], first['handle'])
        self.assertEqual(self.remote.creates, 1)

    def test_busy_or_offline_does_not_create_replacement(self):
        m = self.manager(); first = m.create(confirm=True)
        self.remote.busy = True
        with self.assertRaises(ValueError):
            m.send('task-one', 'main', 'text')
        self.assertEqual(m.ensure()['handle'], first['handle'])
        self.remote.offline = True
        with self.assertRaises(OSError):
            m.ensure()
        self.remote.offline = False; self.remote.busy = False
        self.assertEqual(m.ensure()['handle'], first['handle'])
        self.assertEqual(self.remote.creates, 1)
        self.assertEqual(self.remote.sends, 0)

    def test_stale_incarnation_or_runtime_blocks_without_replacement(self):
        m = self.manager(); m.create(confirm=True)
        self.remote.terminals[0]['incarnationId'] = 'restarted'
        with self.assertRaises(ValueError): m.ensure()
        self.remote.terminals[0]['incarnationId'] = 'inc_1'
        self.remote.runtime = 'other-runtime'
        with self.assertRaises(ValueError): m.ensure()
        self.assertEqual(self.remote.creates, 1)

    def test_project_or_destination_mismatch_is_not_a_new_binding(self):
        self.manager().create(confirm=True)
        another = self.root / 'another'; another.mkdir()
        for m in [self.manager(project=another), self.manager(env='Elsewhere'), self.manager(worktree='other::/path')]:
            with self.assertRaises(ValueError): m.ensure()
        self.assertEqual(self.remote.creates, 1)

    def test_lost_create_response_leaves_intent_and_never_recreates(self):
        self.remote.lose_create = True
        with self.assertRaises(self.mod.Blocked): self.manager().create(confirm=True)
        self.remote.lose_create = False
        with self.assertRaises(ValueError): self.manager().ensure()
        self.assertEqual(self.remote.creates, 1)
        self.assertTrue((self.state / 'bindings.json').exists())

    def test_lost_send_response_never_resends_or_finishes(self):
        m = self.manager(); m.create(confirm=True); self.remote.lose_send = True
        with self.assertRaises(TimeoutError): m.send('task-one', 'main', 'text')
        self.remote.lose_send = False
        replay = m.send('task-one', 'main', 'text')
        self.assertEqual(replay['action'], 'resume')
        self.assertEqual(replay['message']['state'], 'sending')
        with self.assertRaises(ValueError): m.finish('task-one')
        with self.assertRaises(ValueError): m.send('task-one', 'export-1', 'export')
        self.assertEqual(self.remote.sends, 1)

    def test_nonempty_draft_bypass_or_unavailable_screen_blocks_send(self):
        m = self.manager(); m.create(confirm=True)
        for attr, value in [('draft', 'my unsent draft'), ('mode', 'bypass permissions on'), ('source', 'screen-unavailable')]:
            original = getattr(self.remote, attr); setattr(self.remote, attr, value)
            with self.assertRaises(ValueError): m.send('task-one', 'main', 'text')
            setattr(self.remote, attr, original)
        self.assertEqual(self.remote.sends, 0)

    def test_native_empty_startup_hint_with_nbsp_is_not_a_user_draft(self):
        m = self.manager(); m.create(confirm=True)
        self.remote.prompt_space = '\u00a0'
        self.remote.draft = 'Try "edit <filepath> to..."'
        try:
            result = m.send('task-one', 'main', 'actual code task')
        except ValueError as exc:
            result = {'action': 'blocked', 'reason': str(exc)}
        self.assertEqual(result['action'], 'sent')
        self.assertEqual(self.remote.sends, 1)
        with self.assertRaises(ValueError):
            m.send('task-one', 'export-1', 'another message while nonempty')

    def test_fix_typecheck_startup_hint_is_allowed_only_without_task_history(self):
        m = self.manager(); m.create(confirm=True)
        self.remote.prompt_space = ' '
        self.remote.draft = 'Try "fix typecheck errors"'
        try:
            result = m.send('task-one', 'main', 'actual code task')
        except ValueError as exc:
            result = {'action': 'blocked', 'reason': str(exc)}
        self.assertEqual(result['action'], 'sent')
        self.assertEqual(self.remote.sends, 1)
        with self.assertRaises(ValueError):
            m.send('task-one', 'export-1', 'export final patch')
        self.remote.draft = ''; m.finish('task-one')
        self.remote.draft = 'Try "fix typecheck errors"'
        with self.assertRaises(ValueError):
            m.send('task-two', 'main', 'new task with nonempty input')
        self.assertEqual(self.remote.sends, 1)

    def test_refactor_startup_hint_sends_once_and_stays_first_task_only(self):
        m = self.manager(); binding = m.create(confirm=True)
        self.remote.prompt_space = '\u00a0'
        self.remote.draft = 'Try "refactor <filepath>"'
        try:
            result = m.send('task-one', 'main', 'actual refactor task')
        except ValueError as exc:
            result = {'action': 'blocked', 'reason': str(exc)}
        self.assertEqual(result['action'], 'sent')
        self.assertEqual(result['binding']['handle'], binding['handle'])
        self.assertEqual(m.send('task-one', 'main', 'actual refactor task')['action'], 'resume')
        with self.assertRaises(ValueError):
            m.send('task-one', 'export-1', 'export existing final patch')
        self.remote.draft = ''; m.finish('task-one')
        self.remote.draft = 'Try "refactor <filepath>"'
        with self.assertRaises(ValueError):
            m.send('task-two', 'main', 'another task')
        row = json.loads((self.state / 'bindings.json').read_text())['bindings'][self.mod.owner_key(OWNER_A)]
        self.assertEqual(set(row['tasks']), {'task-one'})
        self.assertEqual(set(row['tasks']['task-one']['messages']), {'main'})
        self.assertIsNone(row['active_task'])
        self.assertEqual(self.remote.creates, 1)
        self.assertEqual(self.remote.sends, 1)

    def test_write_test_startup_hint_sends_once_and_stays_first_task_only(self):
        m = self.manager(); binding = m.create(confirm=True)
        self.remote.prompt_space = '\u00a0'
        self.remote.draft = 'Try "write a test for <filepath>"'
        try:
            result = m.send('task-one', 'main', 'actual review task')
        except ValueError as exc:
            result = {'action': 'blocked', 'reason': str(exc)}
        self.assertEqual(result['action'], 'sent')
        self.assertEqual(result['binding']['handle'], binding['handle'])
        self.assertEqual(m.send('task-one', 'main', 'actual review task')['action'], 'resume')
        with self.assertRaises(ValueError):
            m.send('task-one', 'export-1', 'export existing final patch')
        self.remote.draft = ''; m.finish('task-one')
        self.remote.draft = 'Try "write a test for <filepath>"'
        with self.assertRaises(ValueError):
            m.send('task-two', 'main', 'another task')
        row = json.loads((self.state / 'bindings.json').read_text())['bindings'][self.mod.owner_key(OWNER_A)]
        self.assertEqual(set(row['tasks']), {'task-one'})
        self.assertEqual(set(row['tasks']['task-one']['messages']), {'main'})
        self.assertIsNone(row['active_task'])
        self.assertEqual(self.remote.creates, 1)
        self.assertEqual(self.remote.sends, 1)

    NATIVE_STATIC_HINTS = ('Try "create a util logging.py that..."', 'Try "fix lint errors"',
                           'Try "how do I log an error?"')

    def test_claude_2_1_303_static_placeholders_bind_new_create_once(self):
        for hint in self.NATIVE_STATIC_HINTS:
            with self.subTest(hint=hint):
                self.state = self.root / ('state-' + str(abs(hash(hint))))
                self.remote = RemoteOrca(); self.remote.prompt_space = '\u00a0'; self.remote.draft = hint
                bound = self.explicit_create()
                self.assertEqual(bound['action'], 'bound')
                self.assertEqual(self.remote.creates, 1)
                self.assertEqual(self.manager().send('task-one', 'main', 'code task')['action'], 'sent')
                self.remote.draft = ''; self.manager().finish('task-one'); self.remote.draft = hint
                with self.assertRaises(ValueError): self.manager().send('task-two', 'main', 'more')
                self.assertEqual(self.remote.sends, 1)

    def test_typed_try_text_reported_as_native_draft_is_never_a_placeholder(self):
        self.remote.native_draft = 'Try "create a util logging.py that..."'
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
        self.assertEqual(caught.exception.category, 'create_unverified')
        self.assertEqual(self.saved()['state'], 'creating')
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.assertEqual(self.remote.creates, 1)
        self.remote.native_draft = None
        self.explicit_create()
        self.remote.native_draft = 'Try "fix lint errors"'
        with self.assertRaises(ValueError): self.manager().send('task-one', 'main', 'code task')
        self.assertEqual(self.remote.sends, 0)

    def test_placeholder_lookalikes_and_drifted_or_non_auto_candidates_stay_pending(self):
        for draft in ('Try "create a util logging.py that... now"', 'Try "fix lint errors" && rm -rf .',
                      'Try "how do I log an error?" please', 'Try anything', 'Try "create a util logging.py"'):
            with self.subTest(draft=draft):
                self.state = self.root / ('look-' + str(abs(hash(draft))))
                self.remote = RemoteOrca(); self.remote.draft = draft
                with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
                self.assertEqual(caught.exception.category, 'create_unverified')
                self.assertEqual(self.saved()['state'], 'creating')
        for attr, value in (('mode', 'bypass permissions on'), ('mode', 'accept edits on'), ('mode', '')):
            with self.subTest(mode=value):
                self.state = self.root / ('mode-' + str(abs(hash(value))))
                self.remote = RemoteOrca(); self.remote.draft = self.NATIVE_STATIC_HINTS[0]
                setattr(self.remote, attr, value)
                with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
                self.assertEqual(caught.exception.category, 'create_unverified')
                with self.assertRaises(self.mod.Blocked): self.explicit_create()
                self.assertEqual(self.saved()['state'], 'creating')
                self.assertEqual(self.remote.creates, 1)  # never relaunch to obtain auto mode
                self.assertEqual(self.remote.sends, 0)    # never type a mode toggle
        self.state = self.root / 'drift'; self.remote = RemoteOrca()
        self.remote.draft = self.NATIVE_STATIC_HINTS[0]
        self.remote.busy = True
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.assertEqual(self.saved()['creation_candidate']['incarnation'], 'inc_1')
        self.remote.busy = False
        self.remote.terminals[0]['incarnationId'] = 'inc_other'  # identity drift after candidate
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.assertEqual(self.saved()['state'], 'creating')
        self.assertEqual(self.remote.creates, 1)
        self.assertEqual(self.remote.sends, 0)

    def test_lost_or_timed_out_launch_with_placeholder_recovers_without_relaunch(self):
        self.remote.draft = self.NATIVE_STATIC_HINTS[0]
        for failure in ('lost', 'timeout'):
            with self.subTest(failure=failure):
                self.state = self.root / ('rec-' + failure)
                self.remote = RemoteOrca(); self.remote.draft = self.NATIVE_STATIC_HINTS[0]
                if failure == 'lost':
                    self.remote.lose_create = True
                else:
                    def slow(args):
                        if args[1] == 'launch': raise subprocess.TimeoutExpired('orca', 180)
                    self.remote.hook = slow
                with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
                self.assertEqual(caught.exception.category, 'create_unverified')
                self.remote.lose_create = False; self.remote.hook = None
                for _ in range(2):
                    with self.assertRaises(self.mod.Blocked): self.explicit_create()
                self.assertEqual(self.saved()['state'], 'creating')
                self.assertEqual(sum(a[1] == 'launch' for a, _ in self.remote.calls), 1)

    def test_first_send_does_not_allow_arbitrary_try_text_or_real_drafts(self):
        m = self.manager(); m.create(confirm=True)
        for draft in ('my actual unsent draft', 'Try "delete all files"',
                      'Try "fix typecheck errors" then execute this',
                      'Try "refactor <filepath>" then execute this',
                      'Try "refactor my-real-file.py"',
                      'Try "write a test for <filepath>" then execute this',
                      'Try "write a test for my-real-file.py"'):
            self.remote.draft = draft
            with self.assertRaises(ValueError):
                m.send('task-one', 'main', 'code task')
        self.assertEqual(self.remote.sends, 0)
        row = json.loads((self.state / 'bindings.json').read_text())['bindings'][self.mod.owner_key(OWNER_A)]
        self.assertEqual(row['tasks'], {})
        self.assertIsNone(row['active_task'])

    def test_finish_requires_actual_idle_and_keeps_binding(self):
        m = self.manager(); first = m.create(confirm=True); m.send('task-one', 'main', 'text')
        self.remote.busy = True
        with self.assertRaises(ValueError): m.finish('task-one')
        self.remote.busy = False; m.finish('task-one')
        self.assertEqual(m.ensure()['handle'], first['handle'])

    def test_private_state_does_not_store_prompt_and_refuses_symlink(self):
        self.manager().create(confirm=True)
        self.manager().send('task-one', 'main', 'sensitive supplied source not for registry')
        raw = (self.state / 'bindings.json').read_text()
        self.assertNotIn('sensitive supplied source', raw)
        self.assertEqual((self.state.stat().st_mode & 0o777), 0o700)
        self.assertEqual(((self.state / 'bindings.json').stat().st_mode & 0o777), 0o600)
        target = self.root / 'external.json'; target.write_text(raw)
        (self.state / 'bindings.json').unlink(); (self.state / 'bindings.json').symlink_to(target)
        with self.assertRaises((ValueError, OSError)): self.manager().ensure()
        self.assertEqual(target.read_text(), raw)

    def test_corrupt_registry_is_not_reset(self):
        self.manager().create(confirm=True); (self.state / 'bindings.json').write_text('invalid')
        with self.assertRaises((ValueError, OSError)): self.manager().ensure()
        self.assertEqual((self.state / 'bindings.json').read_text(), 'invalid')
        self.assertEqual(self.remote.creates, 1)

    def test_native_identity_required_and_codex_cannot_override_its_thread(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError): self.mod.resolve_owner('codex', None)
            with self.assertRaises(ValueError): self.mod.resolve_owner('codex', OWNER_A['session_id'])
            with self.assertRaises(ValueError): self.mod.resolve_owner('claudex', '${CLAUDE_SESSION_ID}')
        with patch.dict(os.environ, {'CODEX_THREAD_ID': OWNER_A['session_id']}, clear=True):
            self.assertEqual(self.mod.resolve_owner('codex', None), OWNER_A)
            with self.assertRaises(ValueError): self.mod.resolve_owner('codex', OWNER_B['session_id'])

    def test_codex_controller_uses_native_thread(self):
        with patch.dict(os.environ, {'CODEX_THREAD_ID': OWNER_A['session_id']}, clear=True):
            self.assertEqual(self.mod.resolve_owner('codex', None), OWNER_A)
            self.assertEqual(self.mod.resolve_owner(None, None), OWNER_A)
            with self.assertRaises(ValueError): self.mod.resolve_owner('codex', OWNER_G['session_id'])

    def test_claudex_controller_matches_env_and_rejects_other_controllers(self):
        b, g = OWNER_B['session_id'], OWNER_G['session_id']
        with patch.dict(os.environ, {'CLAUDE_SESSION_ID': b}, clear=True):
            self.assertEqual(self.mod.resolve_owner('claudex', None), OWNER_B)
            self.assertEqual(self.mod.resolve_owner('claudex', b.upper()), OWNER_B)
            self.assertEqual(self.mod.resolve_owner(None, None), OWNER_B)
            with self.assertRaises(ValueError): self.mod.resolve_owner('claudex', g)
        with patch.dict(os.environ, {'CODEX_THREAD_ID': OWNER_A['session_id']}, clear=True):
            with self.assertRaises(ValueError): self.mod.resolve_owner('claudex', b)
            with self.assertRaises(ValueError): self.mod.resolve_owner('claudex', g)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.mod.resolve_owner('claudex', b), OWNER_B)

    def test_grok_controller_requires_explicit_uuid(self):
        g = OWNER_G['session_id']
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.mod.resolve_owner('grok', g), OWNER_G)
            self.assertEqual(self.mod.resolve_owner('grok', g.upper()), OWNER_G)
            for bad in (None, '', '${GROK_SESSION_ID}', 'not-a-uuid'):
                with self.assertRaises(ValueError): self.mod.resolve_owner('grok', bad)
            with self.assertRaises(ValueError): self.mod.resolve_owner('grokbot', g)
        with patch.dict(os.environ, {'GROK_SESSION_ID': g}, clear=True):
            with self.assertRaises(ValueError): self.mod.resolve_owner('grok', None)

    def test_grok_rejects_foreign_native_env_even_with_unrelated_uuid(self):
        for name, owner in (('CODEX_THREAD_ID', OWNER_A), ('CLAUDE_SESSION_ID', OWNER_B)):
            with self.subTest(native=name), patch.dict(os.environ, {name: owner['session_id']}, clear=True):
                with self.assertRaises(ValueError):
                    self.mod.resolve_owner('grok', OWNER_G['session_id'])
                env = self.fixture_env()
                for key in ('CODEX_THREAD_ID', 'CLAUDE_SESSION_ID'):
                    env.pop(key, None)
                env[name] = owner['session_id']
                prompt = self.root / 'reviewed-prompt'
                prompt.write_text('reviewed task')
                result = subprocess.run([sys.executable, '-B', str(TARGET), 'send',
                    '--controller', 'grok', '--session-id', OWNER_G['session_id'],
                    '--project-root', str(self.project), '--worktree', WORKTREE,
                    '--state-dir', str(self.state), '--task-id', 'task-one',
                    '--text-file', str(prompt)],
                    capture_output=True, text=True, env=env)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.state.exists())
                self.assertEqual(json.loads(result.stderr)['read_attempts'], 0)

    def test_cross_mapping_between_controllers_is_rejected(self):
        a, b = OWNER_A['session_id'], OWNER_B['session_id']
        with patch.dict(os.environ, {'CODEX_THREAD_ID': a, 'CLAUDE_SESSION_ID': b}, clear=True):
            for ctl, sid in [('claudex', a), ('grok', a), ('grok', b), ('codex', b)]:
                with self.subTest(ctl=ctl, sid=sid), self.assertRaises(ValueError):
                    self.mod.resolve_owner(ctl, sid)
        keys = {self.mod.owner_key({'controller': c, 'session_id': OWNER_G['session_id']})
                for c in self.mod.CONTROLLERS}
        self.assertEqual(len(keys), 3)

    def test_controller_autodetect_errors_on_none_or_ambiguous(self):
        for env in ({}, {'CODEX_THREAD_ID': OWNER_A['session_id'], 'CLAUDE_SESSION_ID': OWNER_B['session_id']}):
            with patch.dict(os.environ, env, clear=True), self.assertRaises(ValueError) as caught:
                self.mod.resolve_owner(None, OWNER_G['session_id'])
            self.assertIn('--controller', str(caught.exception))

    def test_grok_binding_is_separate_and_legacy_keys_unchanged(self):
        import hashlib
        legacy = hashlib.sha256(('claudex\0' + OWNER_B['session_id']).encode()).hexdigest()
        self.assertEqual(self.mod.owner_key(OWNER_B), legacy)
        self.manager(OWNER_B).create(confirm=True)
        bound = self.manager(OWNER_G).create(confirm=True)
        self.assertEqual(self.manager(OWNER_G).ensure()['handle'], bound['handle'])
        self.manager(OWNER_G).send('task-one', 'main', 'text')
        data = json.loads((self.state / 'bindings.json').read_text())
        self.assertIn(legacy, data['bindings'])
        self.assertIn(self.mod.owner_key(OWNER_G), data['bindings'])
        twin = {'controller': 'claudex', 'session_id': OWNER_G['session_id']}
        self.assertNotIn(self.mod.owner_key(twin), data['bindings'])

    def test_grok_controller_cli_identity(self):
        env = dict(self.fixture_env()); env.pop('CODEX_THREAD_ID', None); env.pop('CLAUDE_SESSION_ID', None)
        ok = subprocess.run([sys.executable, '-B', str(TARGET), 'identity', '--controller', 'grok',
                             '--session-id', OWNER_G['session_id']], capture_output=True, text=True, env=env)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout)['owner'], OWNER_G)
        bad = subprocess.run([sys.executable, '-B', str(TARGET), 'identity', '--controller', 'claudex',
                              '--session-id', OWNER_G['session_id']], capture_output=True, text=True,
                             env={**env, 'CLAUDE_SESSION_ID': OWNER_B['session_id']})
        self.assertNotEqual(bad.returncode, 0)

    def test_legacy_receipt_adoption_is_not_an_available_mutation(self):
        result = subprocess.run([sys.executable, '-B', str(TARGET), 'ensure', '--adopt-terminal', 'foreign'], capture_output=True, env=self.fixture_env())
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.state.exists())

    def test_parallel_processes_create_and_submit_at_most_once(self):
        # Real helper processes and flock; only the external CLI is emulated.
        fake = self.root / 'orca-fixture'
        fake.write_text('#!' + sys.executable + '\n' + '''
import json,sys,pathlib,time
p=pathlib.Path(__file__).parent
args=sys.argv[1:]; action=args[1] if args[0]!='status' else 'status'
t={'handle':'term-process','incarnationId':'inc-process','worktreeId':'repo::/home/box/orca/projects/hello','agentIdentity':'claude','connected':True,'writable':True,'orphaned':False}
if action=='status': r={'runtime':{'state':'ready','reachable':True,'runtimeId':'runtime-process','appVersion':'1.4.229','capabilities':['agent.launch.v2','agent.launch.replay-required.v1','agent.launch.local-presentation.v1']}}
elif action=='list': r={'terminals':[t] if (p/'created').exists() else [],'truncated':False}
elif action=='create':
 assert args[args.index('--command')+1]=='claude --permission-mode auto'
 with (p/'created').open('a') as f: f.write('create\\n')
 time.sleep(.25); r={'terminal':{'handle':t['handle'],'worktreeId':t['worktreeId']}}
elif action=='launch':
 with (p/'created').open('a') as f: f.write('create\\n')
 time.sleep(.25); r={'operationId':'1792370000000-00000000000000000000000000000001','outcome':{'kind':'terminal','handle':t['handle']},'worktreeId':t['worktreeId'],'receipt':{'mode':'terminal'}}
elif action=='wait': r={'wait':{'satisfied':True}}
elif action=='read': r={'terminal':{'handle':'term-process','tail':['────────','❯','────────','auto mode on'],'source':'screen' if '--screen' in args else 'stream','truncated':False,'limited':False,'latestCursor':'1'}}
elif action=='send':
 with (p/'sent').open('a') as f: f.write('send\\n')
 time.sleep(.25); r={'send':{'handle':'term-process','accepted':True,'prompt':{'requestId':'request-process','processIncarnation':'inc-process','stages':['input_accepted','turn_started']}}}
else: raise SystemExit('unsupported fixture operation')
print(json.dumps({'ok':True,'result':r,'_meta':{'runtimeId':'runtime-process'}}))
''')
        fake.chmod(0o700)
        common = ['--controller', 'codex', '--session-id', OWNER_A['session_id'],
                  '--project-root', str(self.project), '--worktree', WORKTREE,
                  '--state-dir', str(self.state), '--orca', str(fake)]
        env = self.fixture_env()
        def concurrent(command, extra=()):
            procs = [subprocess.Popen([sys.executable, '-B', str(TARGET), command, *common, *extra],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) for _ in range(4)]
            results = [(p, p.communicate(timeout=15)) for p in procs]
            self.assertTrue(any(p.returncode == 0 for p, _ in results))
            self.assertTrue(all(p.returncode in (0, 1) for p, _ in results))
        concurrent('create', ['--project', WORKTREE, '--confirm'])
        self.assertEqual((self.root / 'created').read_text(), 'create\n')
        prompt = self.root / 'prompt.txt'; prompt.write_text('one real logical task')
        concurrent('send', ['--task-id', 'task-one', '--text-file', str(prompt)])
        self.assertEqual((self.root / 'sent').read_text(), 'send\n')
        self.assertEqual((self.root / 'created').read_text(), 'create\n')

    def saved(self):
        return json.loads((self.state / 'bindings.json').read_text())['bindings'][self.mod.owner_key(OWNER_A)]

    def change_row(self, change):
        with self.mod.Registry(self.state) as db:
            change(db.data['bindings'][self.mod.owner_key(OWNER_A)])
            db.save()

    def failure(self, kind='nonzero', **kwargs):
        return self.mod.NativeFailure(kind, **kwargs)

    def native_pipe_holder(self, escaped):
        fixture = self.root / 'pipe-holder'
        fixture.write_text('#!' + sys.executable + '\n' + '''
import json,os,pathlib,time
p=pathlib.Path(__file__).parent
with (p/'native-starts').open('a') as f: f.write('start\\n')
child=os.fork()
if child==0:
 if ESCAPED: os.setsid()
 (p/'child-ready').write_text(json.dumps({'pid':os.getpid(),'pgid':os.getpgrp()}))
 deadline=time.monotonic()+8
 while time.monotonic()<deadline and not (p/'release-child').exists():
  (p/'child-heartbeat').write_text(str(time.monotonic_ns()))
  time.sleep(.01)
 (p/'child-stopped').touch()
 os._exit(0)
while not (p/'child-ready').exists(): time.sleep(.01)
(p/'parent-ready').write_text(json.dumps({'pid':os.getpid(),'pgid':os.getpgrp()}))
deadline=time.monotonic()+8
while time.monotonic()<deadline and not (p/'release-child').exists(): time.sleep(.01)
'''.replace('ESCAPED', repr(escaped)))
        fixture.chmod(0o700)
        # Escaped descendants are self-limiting and also receive an early-exit signal on failure.
        def release():
            (self.root / 'release-child').touch()
            ready = self.root / 'child-ready'
            if not ready.exists(): return
            pid = json.loads(ready.read_text())['pid']
            deadline = time.monotonic() + 2
            while not (self.root / 'child-stopped').exists():
                try:
                    os.kill(pid, 0)  # existence check only, never signal an unrelated process
                except ProcessLookupError:
                    return
                if time.monotonic() >= deadline:
                    self.fail('Fixture descendant did not acknowledge its exit signal')
                time.sleep(.01)
        self.addCleanup(release)
        return self.mod.NativeOrca(str(fixture), cwd=str(self.project))

    def assert_bounded_native_cleanup(self, escaped, read_error=False):
        native = self.native_pipe_holder(escaped)
        real_popen = subprocess.Popen
        def start(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            communicate = process.communicate
            first = True
            def fail_read_once(timeout=None):
                nonlocal first
                if first:
                    first = False
                    deadline = time.monotonic() + 2
                    while not (self.root / 'parent-ready').exists() and time.monotonic() < deadline:
                        time.sleep(.01)
                    raise OSError('fixture pipe read failure')
                return communicate(timeout=timeout)
            if read_error:
                process.communicate = fail_read_once
            return process
        started = time.monotonic()
        with patch.dict(os.environ, self.fixture_env()), patch.object(self.mod.subprocess, 'Popen', side_effect=start):
            with self.assertRaises(self.mod.NativeFailure) as caught:
                native(['terminal', 'send'], timeout=.5)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 4.5, 'Cleanup waited for inherited pipes instead of its finite deadline')
        self.assertTrue(caught.exception.started)
        self.assertEqual(caught.exception.kind, 'invalid_result' if read_error else 'timeout')
        parent = json.loads((self.root / 'parent-ready').read_text())
        child = json.loads((self.root / 'child-ready').read_text())
        self.assertEqual(parent['pid'], parent['pgid'])
        self.assertNotEqual(parent['pgid'], os.getpgrp())
        self.assertEqual(child['pgid'], child['pid'] if escaped else parent['pgid'])
        if not escaped:
            heartbeat = (self.root / 'child-heartbeat').read_bytes()
            time.sleep(.1)
            self.assertEqual((self.root / 'child-heartbeat').read_bytes(), heartbeat,
                             'Same-group descendant remained alive after cleanup')

    def test_native_timeout_kills_only_owned_process_group(self):
        self.assert_bounded_native_cleanup(False)

    def test_native_timeout_is_bounded_when_descendant_escapes_with_pipes(self):
        self.assert_bounded_native_cleanup(True)

    def test_native_read_failure_is_bounded_when_descendant_escapes_with_pipes(self):
        self.assert_bounded_native_cleanup(True, read_error=True)

    def test_native_invalid_utf8_returns_structured_failure_after_cleanup(self):
        fixture = self.root / 'invalid-utf8'
        fixture.write_text('#!' + sys.executable + '\nimport os\nos.write(1, b"\\xff")\n')
        fixture.chmod(0o700)
        with patch.dict(os.environ, self.fixture_env()):
            with self.assertRaises(self.mod.NativeFailure) as caught:
                self.mod.NativeOrca(str(fixture))(['terminal', 'send'], timeout=.2)
        self.assertEqual(caught.exception.kind, 'invalid_result')
        self.assertTrue(caught.exception.started)

    def test_native_cleanup_timeout_retains_sending_intent_without_resubmit(self):
        m = self.manager(); m.create(confirm=True)
        native = self.native_pipe_holder(True)
        def dispatch(args, timeout=None):
            if args[:2] == ['terminal', 'send']:
                return native(args, timeout=.5)
            return self.remote(args, timeout=timeout)
        m.orca = dispatch
        with patch.dict(os.environ, self.fixture_env()):
            with self.assertRaises(self.mod.Blocked) as caught:
                m.send('task-one', 'main', 'reviewed task')
        self.assertEqual(caught.exception.category, 'uncertain_send')
        message = self.saved()['tasks']['task-one']['messages']['main']
        self.assertEqual(message['state'], 'sending')
        self.assertEqual(message['error']['kind'], 'timeout')
        self.assertEqual(m.send('task-one', 'main', 'reviewed task')['action'], 'resume')
        self.assertEqual((self.root / 'native-starts').read_text(), 'start\n')
        self.assertEqual(self.remote.creates, 1)

    def test_native_launch_is_distinct_from_started_failure_and_safe(self):
        native = self.mod.NativeOrca('/fixture/not-real')
        with patch.object(self.mod.subprocess, 'Popen', side_effect=FileNotFoundError('SECRET path')):
            with self.assertRaises(self.mod.NativeFailure) as caught:
                native(['terminal', 'send'])
        self.assertFalse(caught.exception.started)
        self.assertNotIn('SECRET', str(caught.exception))
        process = Mock(returncode=9)
        process.communicate.return_value = ('', 'remote_runtime_unavailable SECRET source')
        with patch.object(self.mod.subprocess, 'Popen', return_value=process):
            with self.assertRaises(self.mod.NativeFailure) as caught:
                native(['terminal', 'send'])
        self.assertTrue(caught.exception.started)
        self.assertEqual(caught.exception.returncode, 9)
        self.assertIn('SECRET', caught.exception.stderr)
        self.assertNotIn('SECRET', str(caught.exception))
        self.assertEqual(process.communicate.call_args.kwargs['timeout'], 60)

    def test_native_timeout_invalid_json_and_envelope_are_uncertain(self):
        native = self.mod.NativeOrca('/fixture/not-real')
        for output in ('SECRET invalid json', json.dumps({'ok': False, 'secret': 'SECRET'})):
            process = Mock(returncode=0)
            process.communicate.return_value = (output, '')
            with patch.object(self.mod.subprocess, 'Popen', return_value=process):
                with self.assertRaises(self.mod.NativeFailure) as caught:
                    native(['terminal', 'send'])
            self.assertTrue(caught.exception.started)
            self.assertNotIn('SECRET', str(caught.exception))
        process = Mock(pid=123456789)
        process.communicate.side_effect = [subprocess.TimeoutExpired('SECRET', 60, stderr='SECRET'), ('', '')]
        with patch.object(self.mod.subprocess, 'Popen', return_value=process), \
                patch.object(self.mod.os, 'killpg') as killpg:
            with self.assertRaises(self.mod.NativeFailure) as caught:
                native(['terminal', 'send'])
        self.assertTrue(caught.exception.started)
        self.assertEqual(caught.exception.timeout, 60)
        killpg.assert_called_once_with(process.pid, self.mod.signal.SIGKILL)
        self.assertEqual(process.communicate.call_args.kwargs['timeout'], 1)

    def test_send_minimizes_receipt_and_adds_stable_marker(self):
        m = self.manager(); m.create(confirm=True)
        original = self.remote.__call__
        def poisoned(args):
            if args[1] != 'send': return None
            self.remote.hook = None
            result = original(args)
            result['result']['source'] = 'SECRET source'
            result['result']['send']['prompt']['source'] = 'SECRET nested'
            self.remote.hook = poisoned
            return result
        self.remote.hook = poisoned
        result = m.send('task-one', 'main', 'original text')
        receipt = result['message']['receipt']
        self.assertEqual(set(receipt), {'requestId', 'stages', 'processIncarnation', 'handle', 'runtimeId', 'accepted'})
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertNotIn('SECRET', (self.state / 'bindings.json').read_text())
        digest = self.mod.hashlib.sha256(b'original text').hexdigest()
        wire = next(args for args, _ in self.remote.calls if args[1] == 'send')
        self.assertEqual(wire[wire.index('--text') + 1], 'original text\n\ngrok-cc-msg:task-one/main/' + digest[:8])
        self.assertEqual(result['message']['sha256'], digest)
        self.assertEqual(m.send('task-one', 'main', 'original text')['action'], 'resume')
        with self.assertRaises(ValueError): m.send('task-one', 'export-1', 'forged grok-cc-msg:task/main/abcdef12')
        self.assertEqual(self.remote.sends, 1)

    def test_legacy_receipt_is_projected_on_read_and_save(self):
        m = self.manager(); m.create(confirm=True); m.send('task-one', 'main', 'text')
        legacy = {'ok': True, '_meta': {'runtimeId': 'runtime-one'}, 'result': {'source': 'SECRET',
            'send': {'handle': 'term_1', 'accepted': True, 'prompt': {'requestId': 'request-1',
                'processIncarnation': 'inc_1', 'stages': ['input_accepted'], 'tail': 'SECRET'}}}}
        self.change_row(lambda row: row['tasks']['task-one']['messages']['main'].update(receipt=legacy))
        result = m.send('task-one', 'main', 'text')
        self.assertNotIn('SECRET', json.dumps(result))
        m.finish('task-one')
        self.assertNotIn('SECRET', (self.state / 'bindings.json').read_text())

    def test_positive_launch_failure_only_allows_same_message_retry(self):
        m = self.manager(); m.create(confirm=True)
        def launch(args):
            if args[1] == 'send': raise self.failure('launch', started=False, stderr='SECRET')
        self.remote.hook = launch
        with self.assertRaises(ValueError): m.send('task-one', 'main', 'text')
        self.assertEqual(self.saved()['tasks']['task-one']['messages']['main']['state'], 'not_sent')
        with self.assertRaises(ValueError): m.send('task-one', 'main', 'changed')
        self.remote.hook = None; self.remote.busy = True
        with self.assertRaises(ValueError): m.send('task-one', 'main', 'text')
        self.remote.busy = False
        result = m.send('task-one', 'main', 'text')
        self.assertEqual(result['action'], 'sent')
        wires = [args[args.index('--text') + 1] for args, _ in self.remote.calls if args[1] == 'send']
        self.assertEqual(wires[0], wires[1])
        self.assertEqual(self.remote.sends, 1)

    def test_started_failure_never_becomes_not_sent(self):
        m = self.manager(); m.create(confirm=True)
        def fail(args):
            if args[1] == 'send':
                raise self.failure('nonzero', started=True, returncode=1, stderr='remote_runtime_unavailable SECRET')
        self.remote.hook = fail
        with self.assertRaises(ValueError): m.send('task-one', 'main', 'text')
        self.assertEqual(m.send('task-one', 'main', 'text')['message']['state'], 'sending')
        with self.assertRaises(ValueError): m.send('task-one', 'export-1', 'export')
        with self.assertRaises(ValueError): m.rebind('term_new', 'inc_new')
        self.assertNotIn('SECRET', (self.state / 'bindings.json').read_text())
        self.assertEqual(len([a for a, _ in self.remote.calls if a[1] == 'send']), 1)

    def test_reads_and_sleep_never_hold_registry_lock(self):
        m = self.manager(); m.create(confirm=True)
        calls = []
        def check(args):
            if args[1] in ('list', 'wait', 'read', 'send', 'launch'):
                with self.mod.Registry(self.state): calls.append(args[1])
        self.remote.hook = check
        m.send('task-one', 'main', 'text'); m.finish('task-one'); m.ensure()
        self.assertIn('send', calls)

    def clock(self):
        now = [0.0]; sleeps = []
        def sleep(seconds):
            with self.mod.Registry(self.state): pass
            sleeps.append(seconds); now[0] += seconds
        self.addCleanup(patch.stopall)
        patch.object(self.mod.time, 'monotonic', side_effect=lambda: now[0]).start()
        patch.object(self.mod.time, 'sleep', side_effect=sleep).start()
        return now, sleeps

    def test_transient_reads_retry_with_shared_budget_and_actual_counts(self):
        m = self.manager(); m.create(confirm=True); now, sleeps = self.clock()
        m.retry_budget_s = 25
        remaining = {'list': 2, 'wait': 2}
        def transient(args):
            action = args[1]
            if remaining.get(action, 0):
                remaining[action] -= 1
                raise self.failure('nonzero', started=True, returncode=1, code='remote_runtime_unavailable')
        self.remote.hook = transient
        start = len(self.remote.calls)
        with self.assertRaises(self.mod.Blocked) as caught: m.send('task-one', 'main', 'text')
        self.assertEqual(sleeps, [2, 5, 15])
        self.assertEqual(caught.exception.read_attempts, 5)
        self.assertEqual(caught.exception.category, 'unreachable')
        self.assertEqual(self.remote.sends, 0)
        self.assertEqual(now[0], 22)
        self.assertTrue(all(0 < t <= 25 for _, t in self.remote.calls[start:]))

    def test_read_backoff_caps_at_thirty_and_zero_disables_retry(self):
        m = self.manager(); m.create(confirm=True); _, sleeps = self.clock()
        m.retry_budget_s = 85
        def fail(args): raise self.failure('nonzero', started=True, code='remote_runtime_unavailable')
        self.remote.hook = fail
        with self.assertRaises(self.mod.Blocked) as caught: m.ensure()
        self.assertEqual(sleeps, [2, 5, 15, 30, 30])
        self.assertEqual(caught.exception.read_attempts, 6)
        sleeps.clear(); m.retry_budget_s = 0
        with self.assertRaises(self.mod.Blocked) as caught: m.ensure()
        self.assertEqual(sleeps, [])
        self.assertEqual(caught.exception.read_attempts, 1)
        self.assertGreater(self.remote.calls[-1][1], 0)

    def test_unclassified_failure_does_not_retry(self):
        m = self.manager(); m.create(confirm=True); _, sleeps = self.clock()
        def fail(args): raise self.failure('nonzero', started=True, code='unknown', stderr='SECRET')
        self.remote.hook = fail
        with self.assertRaises(self.mod.Blocked) as caught: m.ensure()
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(caught.exception.read_attempts, 1)
        self.assertEqual(sleeps, [])

    def test_positive_deadline_applies_to_whole_read_chain(self):
        m = self.manager(); m.create(confirm=True); now, sleeps = self.clock()
        m.retry_budget_s = 3
        def elapsed(args):
            if args[1] in ('list', 'wait', 'read'): now[0] += 1
        self.remote.hook = elapsed
        start = len(self.remote.calls)
        with self.assertRaises(self.mod.Blocked) as caught: m.send('task-one', 'main', 'text')
        self.assertEqual([t for _, t in self.remote.calls[start:]], [3, 2, 1])
        self.assertEqual(caught.exception.read_attempts, 3)
        self.assertEqual(sleeps, [])
        self.assertEqual(self.remote.sends, 0)

    def test_relevant_row_drift_stops_send_before_intent(self):
        m = self.manager(); m.create(confirm=True); changed = []
        def drift(args):
            if not changed:
                changed.append(True)
                self.change_row(lambda row: row.update(active_task='other-task'))
        self.remote.hook = drift
        with self.assertRaises(self.mod.Blocked): m.send('task-one', 'main', 'text')
        self.assertEqual(self.remote.sends, 0)
        self.assertEqual(self.saved()['active_task'], 'other-task')

    def test_other_owner_updates_survive_create_and_send_merge(self):
        m = self.manager()
        def insert_other(args):
            if args[1] in ('launch', 'send'):
                with self.mod.Registry(self.state) as db:
                    db.data['bindings'][self.mod.owner_key(OWNER_B)] = {'owner': OWNER_B, 'note': args[1]}
                    db.save()
        self.remote.hook = insert_other
        m.create(confirm=True); m.send('task-one', 'main', 'text')
        with self.mod.Registry(self.state) as db:
            self.assertEqual(db.data['bindings'][self.mod.owner_key(OWNER_B)]['note'], 'send')
        self.assertEqual(self.saved()['tasks']['task-one']['messages']['main']['state'], 'accepted')

    def reconcile_during_send(self, message_id, failure=None):
        m = self.manager(); m.create(confirm=True)
        if message_id != 'main':
            m.send('task-one', 'main', 'main text')
        observations = {}
        def observe(args):
            if args[:2] != ['terminal', 'send']: return None
            result = self.manager().reconcile('task-one')  # default observes main and pending export
            observations.update({mid: msg['evidence'] for mid, msg in result['messages'].items()})
            with self.mod.Registry(self.state) as db:
                db.data['bindings'][self.mod.owner_key(OWNER_B)] = {'owner': OWNER_B, 'note': 'observed'}
                db.save()
            if failure is not None:
                raise failure
        self.remote.hook = observe
        if failure is None:
            result = m.send('task-one', message_id, 'reviewed text')
            self.assertEqual(result['action'], 'sent')
        else:
            with self.assertRaises(self.mod.Blocked) as caught:
                m.send('task-one', message_id, 'reviewed text')
            self.assertEqual(caught.exception.category, 'uncertain_send')
        messages = self.saved()['tasks']['task-one']['messages']
        self.assertEqual(set(observations), {'main'} if message_id == 'main' else {'main', 'export-1'})
        for mid, evidence in observations.items():
            self.assertEqual(messages[mid]['evidence'], evidence)
        with self.mod.Registry(self.state) as db:
            self.assertEqual(db.data['bindings'][self.mod.owner_key(OWNER_B)]['note'], 'observed')
        target = messages[message_id]
        self.assertEqual(target['state'], 'accepted' if failure is None else 'sending')
        if failure is None:
            self.assertTrue(target['receipt']['accepted'])
        else:
            self.assertEqual(target['error']['kind'], failure.kind)
            if failure.receipt:
                self.assertEqual(target['receipt'], failure.receipt)
        self.assertEqual(m.send('task-one', message_id, 'reviewed text')['action'], 'resume')
        sends = [args for args, _ in self.remote.calls if args[:2] == ['terminal', 'send']]
        self.assertEqual(len(sends), 1 if message_id == 'main' else 2)

    def test_reconcile_during_send_preserves_accepted_main_receipt(self):
        self.reconcile_during_send('main')

    def test_reconcile_during_send_preserves_main_and_export_evidence(self):
        self.reconcile_during_send('export-1')

    def test_reconcile_during_send_preserves_uncertain_error_and_receipt(self):
        for mid in ('main', 'export-1'):
            for receipt in ({}, {'requestId': 'request-uncertain', 'accepted': False}):
                with self.subTest(message=mid, receipt=bool(receipt)):
                    self.state = self.root / (mid + ('-receipt' if receipt else '-empty'))
                    self.remote = RemoteOrca()
                    self.reconcile_during_send(mid, self.failure('nonzero', receipt=receipt, returncode=1))

    def test_late_receipt_rejects_every_non_evidence_intent_change(self):
        mutations = {
            'attempt_id': lambda r: r['tasks']['task-one']['messages']['main'].update(attempt_id='new-intent'),
            'sha256': lambda r: r['tasks']['task-one']['messages']['main'].update(sha256='different'),
            'cursor': lambda r: r['tasks']['task-one']['messages']['main'].update(cursor='42'),
            'message_attempts': lambda r: r['tasks']['task-one']['messages']['main'].update(attempts=2),
            'task_attempts': lambda r: r['tasks']['task-one'].update(attempts=2),
            'receipt': lambda r: r['tasks']['task-one']['messages']['main'].update(receipt={'requestId': 'other'}),
            'state': lambda r: r['tasks']['task-one']['messages']['main'].update(state='not_sent'),
            'closed': lambda r: r['tasks']['task-one'].update(closed=True),
            'active_task': lambda r: r.update(active_task=None),
            'incarnation': lambda r: r.update(incarnation='inc-other'),
            'new_message': lambda r: r['tasks']['task-one']['messages'].update(other={'evidence': {}}),
            'new_task': lambda r: r['tasks'].update(other={'messages': {}}),
        }
        for name, mutate in mutations.items():
            for uncertain in (False, True):
                with self.subTest(field=name, uncertain=uncertain):
                    self.state = self.root / (name + str(uncertain)); self.remote = RemoteOrca()
                    m = self.manager(); m.create(confirm=True)
                    changed = {}
                    def drift(args):
                        if args[:2] != ['terminal', 'send']: return None
                        self.manager().reconcile('task-one')
                        self.change_row(mutate)
                        changed.update(self.saved())
                        if uncertain: raise self.failure('timeout', timeout=1)
                    self.remote.hook = drift
                    with self.assertRaises(self.mod.Blocked) as caught:
                        m.send('task-one', 'main', 'text')
                    self.assertIn(caught.exception.category, ('busy', 'identity_changed'))
                    self.assertEqual(self.saved(), changed)
                    self.assertEqual(len([a for a, _ in self.remote.calls if a[:2] == ['terminal', 'send']]), 1)

    def test_late_receipt_does_not_overwrite_changed_intent(self):
        m = self.manager(); m.create(confirm=True)
        def drift(args):
            if args[1] == 'send':
                self.change_row(lambda row: row['tasks']['task-one']['messages']['main'].update(attempt_id='new-intent'))
        self.remote.hook = drift
        with self.assertRaises(self.mod.Blocked): m.send('task-one', 'main', 'text')
        message = self.saved()['tasks']['task-one']['messages']['main']
        self.assertEqual(message['attempt_id'], 'new-intent')
        self.assertEqual(message['state'], 'sending')
        self.assertNotIn('receipt', message)

    def test_reconcile_echo_empty_incomplete_never_proves_acceptance(self):
        m = self.manager(); m.create(confirm=True); self.remote.lose_send = True
        with self.assertRaises(TimeoutError): m.send('task-one', 'main', 'text')
        self.remote.lose_send = False
        for mode in ('empty', 'echo', 'limited', 'truncated', 'screen'):
            def evidence(args):
                if args[1] != 'read': return None
                self.assertEqual(args[args.index('--cursor') + 1], '41')
                self.assertEqual(args[args.index('--terminal') + 1], 'term_1')
                terminal = {'handle': 'term_1', 'source': 'screen' if mode == 'screen' else 'stream',
                    'tail': [] if mode == 'empty' else ['grok-cc-msg:task-one/main/echo SECRET'],
                    'limited': mode == 'limited', 'truncated': mode == 'truncated',
                    'oldestCursor': '0', 'latestCursor': '42', 'nextCursor': '42'}
                return {'ok': True, '_meta': {'runtimeId': 'runtime-one'}, 'result': {'terminal': terminal}}
            self.remote.hook = evidence
            result = m.reconcile('task-one', 'main')
            self.assertEqual(result['messages']['main']['state'], 'sending')
            self.assertNotIn('SECRET', json.dumps(result))
        self.assertEqual(self.remote.sends, 1)
        self.assertEqual(self.remote.creates, 1)
        self.assertNotIn('SECRET', (self.state / 'bindings.json').read_text())

    def test_reconcile_saved_receipt_only_with_current_identity(self):
        m = self.manager(); m.create(confirm=True); m.send('task-one', 'main', 'text')
        self.change_row(lambda row: row['tasks']['task-one']['messages']['main'].update(state='sending'))
        result = m.reconcile('task-one')
        self.assertEqual(result['messages']['main']['state'], 'accepted')
        self.change_row(lambda row: row['tasks']['task-one']['messages']['main'].update(state='sending'))
        self.remote.terminals[0]['incarnationId'] = 'changed'
        with self.assertRaises(self.mod.Blocked): m.reconcile('task-one')
        self.assertEqual(self.saved()['tasks']['task-one']['messages']['main']['state'], 'sending')
        self.assertEqual(self.remote.sends, 1)

    def test_retry_request_cli_rejects_before_any_orca_call(self):
        stderr = io.StringIO()
        with patch.object(sys, 'argv', ['session_binding', 'send', '--controller', 'claudex',
                '--retry-request', 'SECRET']), patch.object(self.mod, 'NativeOrca') as native, \
                patch('sys.stderr', stderr):
            self.assertEqual(self.mod.main(), 1)
        native.assert_not_called()
        result = json.loads(stderr.getvalue())
        self.assertEqual(result['category'], 'unsupported_contract')
        self.assertFalse(result['retryable'])
        self.assertNotIn('SECRET', stderr.getvalue())

    def test_cli_invalid_arguments_and_oserror_are_sanitized_json(self):
        for args in (['SECRET'], ['identity', '--controller', 'claudex', '--session-id', 'SECRET']):
            stderr = io.StringIO()
            with patch.object(sys, 'argv', ['session_binding', *args]), patch('sys.stderr', stderr):
                self.assertEqual(self.mod.main(), 1)
            result = json.loads(stderr.getvalue())
            self.assertEqual(result['category'], 'invalid_input')
            self.assertEqual(result['attempts'], 0)
            self.assertEqual(result['read_attempts'], 0)
            self.assertNotIn('SECRET', stderr.getvalue())
        stderr = io.StringIO()
        with patch.object(sys, 'argv', ['session_binding', 'ensure', '--controller', 'claudex',
                '--session-id', OWNER_B['session_id'], '--project-root', str(self.project),
                '--worktree', WORKTREE, '--state-dir', str(self.state)]), \
                patch.object(self.mod.BindingManager, 'ensure', side_effect=OSError('SECRET path')), \
                patch('sys.stderr', stderr):
            self.assertEqual(self.mod.main(), 1)
        self.assertNotIn('SECRET', stderr.getvalue())
        self.assertEqual(json.loads(stderr.getvalue())['category'], 'integrity_failure')

    def target_terminal(self):
        target = copy.deepcopy(self.remote.terminals[0])
        target.update(handle='term-target', incarnationId='inc-target')
        self.remote.terminals.append(target)
        return target

    def test_explicit_rebind_archives_complete_old_binding_without_remote_write(self):
        m = self.manager(); m.create(confirm=True); m.send('task-one', 'main', 'text'); m.finish('task-one')
        old = self.saved(); self.target_terminal()
        result = m.rebind('term-target', 'inc-target')
        self.assertEqual(result['handle'], 'term-target')
        saved = self.saved()
        self.assertEqual(saved['history'][-1], old)
        self.assertEqual(saved['tasks'], {})
        self.assertIsNone(saved['active_task'])
        self.assertEqual((self.remote.creates, self.remote.sends), (1, 1))

    def test_rebind_rejects_active_wrong_target_occupied_draft_or_drift(self):
        m = self.manager(); m.create(confirm=True); target = self.target_terminal()
        for key, value in [('incarnationId', 'changed'), ('worktreeId', 'wrong::/path'),
                           ('agentIdentity', 'shell'), ('connected', False), ('writable', False), ('orphaned', True)]:
            original = target[key]; target[key] = value
            with self.assertRaises(ValueError): m.rebind('term-target', 'inc-target')
            target[key] = original
        self.remote.draft = 'Try "fix typecheck errors"'
        with self.assertRaises(ValueError): m.rebind('term-target', 'inc-target')
        self.remote.draft = ''; self.remote.mode = 'bypass permissions on'
        with self.assertRaises(ValueError): m.rebind('term-target', 'inc-target')
        self.remote.mode = 'auto mode on'
        with self.mod.Registry(self.state) as db:
            db.data['bindings'][self.mod.owner_key(OWNER_B)] = {'owner': OWNER_B, 'runtime': 'runtime-one',
                'handle': 'term-target', 'state': 'creating'}
            db.save()
        with self.assertRaises(ValueError): m.rebind('term-target', 'inc-target')
        self.assertEqual(self.saved()['handle'], 'term_1')
        self.assertNotIn('history', self.saved())

    def test_task_total_caps_exports_and_legacy_attempts(self):
        m = self.manager(); m.create(confirm=True); m.send('task-one', 'main', 'text')
        m.send('task-one', 'export-1', 'format only')
        with self.assertRaises(self.mod.Blocked) as caught:
            m.send('task-one', 'export-2', 'format again')
        self.assertEqual(caught.exception.attempts, 2)
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(self.remote.sends, 2)
        self.assertEqual(m.send('task-one', 'main', 'text')['action'], 'resume')
        self.change_row(lambda row: [msg.pop('attempts', None)
            for msg in row['tasks']['task-one']['messages'].values()])
        with self.assertRaises(self.mod.Blocked): m.send('task-one', 'export-3', 'format')
        self.assertEqual(self.remote.sends, 2)

    def test_failed_launch_budget_persists_and_reports_safe_error(self):
        m = self.manager(); m.create(confirm=True)
        def fail(args):
            if args[1] == 'send': raise self.failure('launch', started=False, stderr='SECRET')
        self.remote.hook = fail
        for attempt in (1, 2):
            with self.assertRaises(self.mod.Blocked) as caught: m.send('task-one', 'main', 'text')
            self.assertEqual(caught.exception.attempts, attempt)
            self.assertEqual(caught.exception.retryable, attempt < 2)
        self.remote.hook = None
        with self.assertRaises(self.mod.Blocked) as caught: self.manager().send('task-one', 'main', 'text')
        self.assertEqual(caught.exception.attempts, 2)
        message = self.saved()['tasks']['task-one']['messages']['main']
        self.assertEqual(message['attempts'], 2)
        self.assertEqual(message['error']['kind'], 'launch')
        self.assertNotIn('SECRET', json.dumps(message))

    def test_busy_and_unreachable_have_distinct_categories(self):
        m = self.manager(); m.create(confirm=True); self.remote.busy = True
        with self.assertRaises(self.mod.Blocked) as caught: m.send('task-one', 'main', 'text')
        self.assertEqual(caught.exception.category, 'busy')
        self.remote.busy = False; self.remote.terminals[0]['connected'] = False
        with self.assertRaises(self.mod.Blocked) as caught: m.ensure()
        self.assertEqual(caught.exception.category, 'unreachable')
        self.remote.terminals[0]['incarnationId'] = 'changed'
        with self.assertRaises(self.mod.Blocked) as caught: m.ensure()
        self.assertEqual(caught.exception.category, 'identity_changed')

    def test_clipped_read_cannot_reconcile_even_saved_receipt(self):
        m = self.manager(); m.create(confirm=True); m.send('task-one', 'main', 'text')
        self.change_row(lambda row: row['tasks']['task-one']['messages']['main'].update(state='sending'))
        original = self.remote.__call__
        def clipped(args):
            if args[1] != 'read': return None
            self.remote.hook = None
            result = original(args)
            self.remote.hook = clipped
            result['result']['terminal']['limited'] = True
            return result
        self.remote.hook = clipped
        self.assertEqual(m.reconcile('task-one')['messages']['main']['state'], 'sending')

    def test_rebind_keeps_flat_history(self):
        m = self.manager(); m.create(confirm=True); self.target_terminal()
        m.rebind('term-target', 'inc-target'); m.rebind('term_1', 'inc_1')
        history = self.saved()['history']
        self.assertEqual(len(history), 2)
        self.assertFalse(any(old.get('history') for old in history))

    def test_nonzero_receipt_survives_without_raw_response(self):
        receipt = {'ok': False, '_meta': {'runtimeId': 'runtime-one'}, 'result': {'secret': 'SECRET',
            'send': {'handle': 'term_1', 'accepted': True, 'prompt': {'requestId': 'req-x',
                'processIncarnation': 'inc_1', 'stages': ['input_accepted']}}}}
        process = Mock(returncode=1)
        process.communicate.return_value = (json.dumps(receipt), 'SECRET')
        with patch.object(self.mod.subprocess, 'Popen', return_value=process):
            with self.assertRaises(self.mod.NativeFailure) as caught:
                self.mod.NativeOrca('/not-real')(['terminal', 'send'])
        self.assertEqual(caught.exception.receipt['requestId'], 'req-x')
        m = self.manager(); m.create(confirm=True)
        def fail(args):
            if args[1] == 'send': raise caught.exception
        self.remote.hook = fail
        with self.assertRaises(self.mod.Blocked): m.send('task-one', 'main', 'text')
        message = self.saved()['tasks']['task-one']['messages']['main']
        self.assertEqual(message['state'], 'sending')
        self.assertEqual(message['receipt']['requestId'], 'req-x')
        self.assertNotIn('SECRET', json.dumps(message))

    def test_archived_task_cannot_replay_after_rebind(self):
        m = self.manager(); m.create(confirm=True); m.send('task-one', 'main', 'text')
        m.send('task-one', 'export-1', 'format'); m.finish('task-one'); self.target_terminal()
        m.rebind('term-target', 'inc-target')
        for mid, text in (('main', 'text'), ('export-2', 'format again')):
            with self.assertRaises(self.mod.Blocked) as caught: m.send('task-one', mid, text)
            self.assertEqual(caught.exception.attempts, 2)
            self.assertFalse(caught.exception.retryable)
        self.assertEqual(self.remote.sends, 2)
        self.assertEqual(self.saved()['history'][0]['tasks']['task-one']['attempts'], 2)
        self.assertEqual(self.saved()['tasks'], {})

    def test_same_target_rebind_cannot_reset_task_history(self):
        m = self.manager(); bound = m.create(confirm=True); m.send('task-one', 'main', 'text'); m.finish('task-one')
        before = self.saved()
        m.rebind(bound['handle'], bound['incarnation'])
        self.assertEqual(self.saved(), before)
        self.assertEqual(m.send('task-one', 'main', 'text')['action'], 'resume')
        self.assertEqual(self.remote.sends, 1)

    def test_malformed_nested_native_responses_stay_structured(self):
        m = self.manager(OWNER_B); m.create(confirm=True); m.send('task-one', 'main', 'text')
        common = ['--controller', 'claudex', '--session-id', OWNER_B['session_id'],
                  '--project-root', str(self.project), '--worktree', WORKTREE,
                  '--state-dir', str(self.state), '--task-id', 'task-one']
        for target, body in [('wait', {'wait': None}), ('stream', {'terminal': None}),
                ('screen', {'terminal': {'handle': 'term_1', 'source': 'screen', 'tail': None}})]:
            def malformed(args):
                action = args[1]
                match = action == target or (action == 'read' and (target == 'screen') == ('--screen' in args) and target != 'wait')
                if match: return {'ok': True, '_meta': {'runtimeId': 'runtime-one'}, 'result': body}
            self.remote.hook = malformed
            stderr = io.StringIO()
            with patch.object(sys, 'argv', ['helper', 'finish', *common]), \
                    patch.object(self.mod, 'NativeOrca', return_value=self.remote), patch('sys.stderr', stderr):
                self.assertEqual(self.mod.main(), 1)
            result = json.loads(stderr.getvalue())
            self.assertEqual(result['category'], 'integrity_failure')
            self.assertEqual(result['attempts'], 1)
            self.assertNotIn('Traceback', stderr.getvalue())

    def test_task_aware_errors_restore_total_attempts(self):
        m = self.manager(); m.create(confirm=True); m.send('task-one', 'main', 'text'); m.send('task-one', 'export-1', 'format')
        self.remote.busy = True
        with self.assertRaises(self.mod.Blocked) as caught: m.finish('task-one')
        self.assertEqual(caught.exception.attempts, 2); self.assertFalse(caught.exception.retryable)
        self.remote.busy = False; self.remote.terminals[0]['connected'] = False
        with self.assertRaises(self.mod.Blocked) as caught: m.reconcile('task-one')
        self.assertEqual(caught.exception.attempts, 2); self.assertFalse(caught.exception.retryable)
        self.assertEqual(self.remote.sends, 2)

    def test_malformed_registry_shape_is_safe_blocked_without_rewrite(self):
        m = self.manager(OWNER_B); m.create(confirm=True)
        with self.mod.Registry(self.state) as db:
            db.data['bindings'][self.mod.owner_key(OWNER_B)]['tasks'] = None
            db.save()
        before = (self.state / 'bindings.json').read_bytes()
        stderr = io.StringIO()
        args = ['helper', 'ensure', '--controller', 'claudex', '--session-id', OWNER_B['session_id'],
                '--project-root', str(self.project), '--worktree', WORKTREE, '--state-dir', str(self.state)]
        with patch.object(sys, 'argv', args), patch.object(self.mod, 'NativeOrca', return_value=self.remote), \
                patch('sys.stderr', stderr):
            self.assertEqual(self.mod.main(), 1)
        self.assertEqual(json.loads(stderr.getvalue())['category'], 'integrity_failure')
        self.assertEqual((self.state / 'bindings.json').read_bytes(), before)

    def test_malformed_create_identity_retains_uncertain_reservation(self):
        def malformed(args):
            if args[1] == 'launch':
                return {'ok': True, '_meta': {'runtimeId': 'runtime-one'}, 'result': {'terminal':
                    {'handle': {'invalid': True}, 'incarnationId': 'inc', 'worktreeId': WORKTREE}}}
        self.remote.hook = malformed
        with self.assertRaises(self.mod.Blocked): self.manager().create(confirm=True)
        self.assertEqual(self.saved()['state'], 'creating')
        self.assertNotIn('handle', self.saved())



    def test_how_does_filepath_startup_hint_is_allowed_only_without_task_history(self):
        m = self.manager(); m.create(confirm=True)
        self.remote.prompt_space = '\u00a0'
        self.remote.draft = 'Try "how does <filepath> work?"'
        try:
            result = m.send('task-one', 'main', 'actual code task')
        except ValueError as exc:
            result = {'action': 'blocked', 'reason': str(exc)}
        self.assertEqual(result['action'], 'sent')
        self.assertEqual(self.remote.sends, 1)
        with self.assertRaises(ValueError):
            m.send('task-one', 'export-1', 'export final patch')

    def test_visible_screen_marker_without_receipt_stays_unaccepted(self):
        m = self.manager(); m.create(confirm=True)
        def fail(args):
            if args[1] == 'send':
                raise self.failure('nonzero', started=True, returncode=1)
        self.remote.hook = fail
        with self.assertRaises(self.mod.Blocked):
            m.send('task-one', 'main', 'text')
        def read(args):
            if args[1] != 'read':
                return None
            screen = '--screen' in args
            terminal = {'handle': args[args.index('--terminal') + 1],
                        'truncated': False, 'limited': False,
                        'source': 'screen' if screen else 'stream'}
            if screen:
                terminal['tail'] = ['● visible answer', 'VISIBLE_ONLY_MARKER',
                                    '────────', '❯' + self.remote.prompt_space, '────────',
                                    '⏵⏵ auto mode on']
            else:
                terminal.update(tail=[], latestCursor='1', nextCursor='1', oldestCursor='0')
            return {'ok': True, '_meta': {'runtimeId': self.remote.runtime},
                    'result': {'terminal': terminal}}
        self.remote.hook = read
        result = m.reconcile('task-one', 'main')
        message = result['messages']['main']
        self.assertEqual(message['state'], 'sending')
        self.assertNotIn('receipt', message)
        self.assertFalse(message['evidence']['complete'])
        self.assertEqual(message['evidence']['reason'], 'incomplete_stream')
        with self.assertRaises(self.mod.Blocked) as caught:
            m.finish('task-one')
        self.assertEqual(caught.exception.category, 'uncertain_send')
        self.assertEqual(m.send('task-one', 'main', 'text')['action'], 'resume')
        self.assertEqual(sum(args[1] == 'send' for args, _ in self.remote.calls), 1)
        self.assertTrue(all('--environment' in args and args[args.index('--environment') + 1] == 'Grok Bot'
                            for args, _ in self.remote.calls))
        saved = (self.state / 'bindings.json').read_text()
        self.assertNotIn('VISIBLE_ONLY_MARKER', saved)
        self.assertNotIn('VISIBLE_ONLY_MARKER', json.dumps(result))


class AutoLaunchTests(unittest.TestCase):
    """Per-instance auto creation; saved agent reservations keep their protocol."""
    launch_protocol = 'terminal.create.claude-auto.v1'
    setUp = BindingTests.setUp
    manager = BindingTests.manager
    explicit_create = BindingTests.explicit_create
    saved = BindingTests.saved
    failure = BindingTests.failure

    def test_auto_preview_reports_exact_command_without_creating_state(self):
        result = self.explicit_create(confirm=False)
        self.assertEqual(result['action'], 'dry_run')
        self.assertEqual(result['plan'].get('command'), 'claude --permission-mode auto')
        self.assertEqual(result['plan']['placement'], 'terminal in the explicit worktree')
        self.assertFalse(self.state.exists())
        self.assertEqual(self.remote.creates, 0)
        self.assertEqual(self.remote.sends, 0)
        self.assertFalse(any(a[:2] in (['terminal', 'create'], ['agent', 'launch'])
                             for a, _ in self.remote.calls))

    def test_auto_create_uses_exact_per_instance_command_and_binds_only_in_auto(self):
        bound = self.explicit_create()
        self.assertEqual(bound['action'], 'bound')
        self.assertNotIn('operationId', bound)
        command = next(a for a, _ in self.remote.calls if a[:2] == ['terminal', 'create'])
        self.assertEqual(command[:6], ['terminal', 'create', '--worktree', 'id:' + WORKTREE,
                                       '--command', 'claude --permission-mode auto'])
        self.assertNotIn('--dangerously-skip-permissions', ' '.join(command))
        self.assertFalse(any(a[:2] == ['agent', 'launch'] for a, _ in self.remote.calls))
        self.assertEqual(self.remote.creates, 1)

    def test_auto_create_in_bypass_or_unknown_mode_never_binds_or_relaunches(self):
        for mode in ('bypass permissions on', 'auto mode on · bypass', '', 'accept edits on'):
            with self.subTest(mode=mode):
                self.state = self.root / ('auto-' + str(abs(hash(mode))))
                self.remote = RemoteOrca(); self.remote.mode = mode
                with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
                self.assertEqual(caught.exception.category, 'create_unverified')
                with self.assertRaises(self.mod.Blocked): self.explicit_create()
                self.assertEqual(self.saved()['state'], 'creating')
                self.assertEqual(self.remote.creates, 1)
                self.assertEqual(self.remote.sends, 0)

    def test_auto_create_failure_timeout_or_bad_reply_is_never_replayed(self):
        cases = {'lost': None, 'timeout': subprocess.TimeoutExpired('orca', 180),
                 'not_started': 'launch', 'bad': 'bad'}
        for name, failure in cases.items():
            with self.subTest(case=name):
                self.state = self.root / ('autofail-' + name); self.remote = RemoteOrca()
                if name == 'lost':
                    self.remote.lose_create = True
                else:
                    def hook(args, failure=failure):
                        if args[:2] != ['terminal', 'create']: return None
                        if failure == 'bad':
                            return {'ok': True, '_meta': {'runtimeId': 'runtime-one'}, 'result': {'terminal': {'handle': {'x': 1}}}}
                        if failure == 'launch': raise self.failure('launch', started=False)
                        raise failure
                    self.remote.hook = hook
                with self.assertRaises(self.mod.Blocked): self.explicit_create()
                self.remote.hook = None; self.remote.lose_create = False
                for _ in range(2):
                    with self.assertRaises(self.mod.Blocked): self.explicit_create()
                row = self.saved()
                self.assertEqual(row['state'], 'creating')
                self.assertNotIn('operationId', row['creation_launch'])
                with self.assertRaises(self.mod.Blocked):
                    self.manager().create(confirm=True, retry_launch=OPERATION_ID)
                self.assertEqual(sum(a[:2] == ['terminal', 'create'] for a, _ in self.remote.calls), 1)
                self.assertFalse(any(a[:2] == ['agent', 'launch'] for a, _ in self.remote.calls))


class RecoverFinalReplyTests(unittest.TestCase):
    setUp = BindingTests.setUp
    manager = BindingTests.manager
    explicit_create = BindingTests.explicit_create
    launch_protocol = None
    TASK = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
    SESSION = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'

    def prepare(self):
        self.explicit_create()
        self.manager().send(self.TASK, 'main', 'review')
        self.out = self.root / 'reply'
        self.before = (self.state / 'bindings.json').read_bytes()
        self.records = [
            {'type': 'user', 'uuid': 'u1', 'promptId': 'p1', 'message': {'content':
                'review\n\ngrok-cc-msg:' + self.TASK + '/main/' + self.mod.hashlib.sha256(b'review').hexdigest()[:8]}},
            {'type': 'assistant', 'uuid': 'a1', 'parentUuid': 'u1', 'message': {
                'stop_reason': 'end_turn', 'content': [{'type': 'thinking', 'thinking': 'SECRET'},
                {'type': 'text', 'text': '结论\nBEGIN_PATCH ' + self.TASK + '\nPATCH_SHA256 ' +
                 self.mod.hashlib.sha256(b'').hexdigest() + '\nPATCH_LINES 0\nEND_PATCH ' + self.TASK + '\n'}]}}]
        self.candidates = [{'sessionId': self.SESSION, 'path': '/home/box/.claude/projects/hello/' +
                            self.SESSION + '.jsonl', 'mtime': 1000, 'records': self.records}]

    def recover(self, **kw):
        return self.mod.recover_final_reply(self.state, OWNER_A, self.TASK, out=self.out,
                                           remote_read=lambda *a: self.candidates, **kw)

    def refused(self, category, **kw):
        with self.assertRaises(self.mod.Blocked) as caught:
            self.recover(**kw)
        self.assertEqual(caught.exception.category, category)
        self.assertFalse(Path(str(self.out) + '.txt').exists())
        self.assertEqual((self.state / 'bindings.json').read_bytes(), self.before)

    def test_empty_patch_and_no_orca_mutation(self):
        self.prepare()
        with patch.object(self.mod.NativeOrca, '__call__', side_effect=AssertionError('no Orca')):
            result = self.recover()
        self.assertEqual(result['action'], 'recovered')
        body = Path(str(self.out) + '.txt').read_bytes()
        meta = json.loads(Path(str(self.out) + '.meta.json').read_bytes())
        self.assertNotIn(b'SECRET', body)
        self.assertEqual(meta['body_sha256'], self.mod.hashlib.sha256(body).hexdigest())
        self.assertTrue(meta['patch_sha_ok'])
        self.assertEqual(meta['text_block_count'], 1)
        self.assertEqual((self.state / 'bindings.json').read_bytes(), self.before)

    def test_multiple_text_blocks_preserve_bytes(self):
        self.prepare()
        self.records[-1]['message']['content'] = [{'type': 'text', 'text': 'a\r\n'},
            {'type': 'tool_use', 'input': {'secret': 'x'}}, {'type': 'text', 'text': '中'}]
        self.recover()
        self.assertEqual(Path(str(self.out) + '.txt').read_bytes(), 'a\r\n中'.encode())

    def test_nonaccepted_and_missing_receipt(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                if not hasattr(self, 'out'): self.prepare()
                with self.mod.Registry(self.state) as db:
                    msg = db.data['bindings'][self.mod.owner_key(OWNER_A)]['tasks'][self.TASK]['messages']['main']
                    msg['state'] = 'accepted' if missing else 'sending'
                    if missing: msg['receipt'] = {}
                    db.save()
                self.before = (self.state / 'bindings.json').read_bytes()
                self.refused('uncertain_send')

    def test_no_binding_or_wrong_task(self):
        self.prepare()
        with self.mod.Registry(self.state) as db:
            db.data['bindings'][self.mod.owner_key(OWNER_A)]['tasks'] = {}
            db.save()
        self.before = (self.state / 'bindings.json').read_bytes()
        self.refused('invalid_input')
        with self.mod.Registry(self.state) as db:
            db.data['bindings'] = {}; db.save()
        self.before = (self.state / 'bindings.json').read_bytes()
        self.refused('invalid_input')

    def test_ambiguous_jsonl(self):
        self.prepare()
        other = copy.deepcopy(self.candidates[0]); other['sessionId'] = OWNER_B['session_id']
        other['path'] = str(Path(other['path']).with_name(other['sessionId'] + '.jsonl'))
        self.candidates.append(other)
        with self.assertRaises(self.mod.Blocked) as caught:
            self.recover()
        self.assertEqual(caught.exception.diagnostic['candidate_session_ids'], [self.SESSION, OWNER_B['session_id']])
        self.assertFalse(Path(str(self.out) + '.txt').exists())

    def test_no_end_turn_or_no_text(self):
        self.prepare()
        self.records[-1]['message']['stop_reason'] = 'tool_use'
        self.refused('integrity_failure')
        self.records[-1]['message'].update(stop_reason='end_turn', content=[])
        self.refused('integrity_failure')

    def test_next_user_turn_is_not_our_answer(self):
        self.prepare()
        self.records[-1]['message']['stop_reason'] = 'tool_use'
        self.records.extend([{'type': 'user', 'message': {'content': 'unrelated'}},
            {'type': 'assistant', 'uuid': 'other', 'message': {'stop_reason': 'end_turn',
            'content': [{'type': 'text', 'text': 'wrong answer'}]}}])
        self.refused('integrity_failure')

    def test_tool_result_continuation(self):
        self.prepare()
        self.records.insert(1, {'type': 'user', 'promptId': 'p1', 'message': {
            'content': [{'type': 'tool_result', 'content': 'not exported'}]}})
        self.recover()

    def test_invalid_patch_still_exports(self):
        self.prepare()
        self.records[-1]['message']['content'][1]['text'] = 'BEGIN_PATCH ' + self.TASK + '\nbroken'
        self.recover()
        self.assertFalse(json.loads(Path(str(self.out) + '.meta.json').read_bytes())['patch_sha_ok'])

    def test_output_symlink_or_project_refused(self):
        self.prepare()
        self.out = self.project / 'reply'
        self.refused('invalid_input')
        alias = self.root / 'alias'; alias.symlink_to(self.root, target_is_directory=True)
        self.out = alias / 'reply'
        self.refused('invalid_input')

    def test_fingerprint_mismatch(self):
        self.prepare()
        key = 'ssh-ed25519 ' + self.mod.base64.b64encode(b'test-key').decode()
        with patch.object(self.mod.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0,
                ('host ' + key + '\n').encode(), b'')) as run:
            with self.assertRaises(self.mod.Blocked) as caught:
                self.mod.read_final_candidates('100.84.23.115', 'box', self.TASK, 'SHA256:' + 'A' * 43)
        self.assertEqual(caught.exception.category, 'identity_changed')
        self.assertEqual(run.call_count, 1)

    def test_ssh_options_and_handshake_key_change(self):
        self.prepare()
        key = self.mod.base64.b64encode(b'test-key')
        fp = 'SHA256:' + self.mod.base64.b64encode(self.mod.hashlib.sha256(b'test-key').digest()).decode().rstrip('=')
        scan = subprocess.CompletedProcess([], 0, b'host ssh-ed25519 ' + key + b'\n', b'')
        response = subprocess.CompletedProcess([], 0, b'[]', b'debug1: Server host key: ssh-ed25519 ' + fp.encode() + b'\n')
        with patch.object(self.mod.subprocess, 'run', side_effect=[scan, response]) as run:
            self.assertEqual(self.mod.read_final_candidates('100.84.23.115', 'box', self.TASK, fp), [])
        args = run.call_args_list[1].args[0]
        for option in ('BatchMode=yes', 'StrictHostKeyChecking=yes', 'UpdateHostKeys=no'):
            self.assertIn(option, args)
        self.assertIn('box@100.84.23.115', args)
        response.stderr = b'debug1: Server host key: ssh-ed25519 SHA256:' + b'A' * 43 + b'\n'
        with patch.object(self.mod.subprocess, 'run', side_effect=[scan, response]):
            with self.assertRaises(self.mod.Blocked) as caught:
                self.mod.read_final_candidates('100.84.23.115', 'box', self.TASK, fp)
        self.assertEqual(caught.exception.category, 'identity_changed')

    def test_ssh_unreachable_and_permission(self):
        self.prepare()
        for status in (255, 2):
            with self.subTest(status=status), patch.object(self.mod.subprocess, 'run',
                    return_value=subprocess.CompletedProcess([], status, b'', b'PRIVATE')):
                with self.assertRaises(self.mod.Blocked) as caught:
                    self.mod.read_final_candidates('100.84.23.115', 'box', self.TASK)
                self.assertEqual(caught.exception.category, 'unreachable')
                self.assertNotIn('PRIVATE', str(caught.exception.result()))

    def test_remote_projection_executes_on_isolated_jsonl(self):
        self.prepare()
        home = self.root / 'remote-home'; project = home / '.claude/projects/-home-box-orca-projects-hello'
        project.mkdir(parents=True)
        path = project / (self.SESSION + '.jsonl')
        path.write_text(''.join(json.dumps(record) + '\n' for record in self.records))
        sub = project / (self.SESSION + '/subagents'); sub.mkdir(parents=True)
        (sub / 'agent-example.jsonl').write_text(path.read_text())
        proc = subprocess.run([sys.executable, '-c', self.mod.RECOVER_REMOTE, self.TASK],
            capture_output=True, env={**os.environ, 'HOME': str(home)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(len(result), 1)
        self.assertNotIn('SECRET', proc.stdout.decode())
        self.assertEqual(self.mod._final_text(result[0], self.TASK, 'main',
            self.mod.Registry.inspect(self.state)['bindings'][self.mod.owner_key(OWNER_A)]['tasks'][self.TASK]['messages']['main'])[2], 1)
        path.write_text('{bad JSON')
        proc = subprocess.run([sys.executable, '-c', self.mod.RECOVER_REMOTE, self.TASK],
            capture_output=True, env={**os.environ, 'HOME': str(home)})
        # No task occurrence is a legitimate empty search, never a guessed answer.
        self.assertEqual(json.loads(proc.stdout), [])

    def test_message_marker_separates_export(self):
        self.prepare()
        self.records[0]['message']['content'] = self.records[0]['message']['content'].replace('/main/', '/export-1/')
        self.refused('integrity_failure')

    def test_existing_output_not_overwritten(self):
        self.prepare()
        meta = Path(str(self.out) + '.meta.json'); meta.write_text('keep')
        self.refused('invalid_input')
        self.assertEqual(meta.read_text(), 'keep')

    def test_cli_native_owner_and_no_registry_creation(self):
        self.prepare()
        absent = self.root / 'absent-state'
        args = [sys.executable, '-B', str(TARGET), 'recover-final-reply', '--controller', 'codex',
                '--session-id', OWNER_A['session_id'], '--task-id', self.TASK, '--state-dir', str(absent)]
        env = {k: v for k, v in os.environ.items() if k not in ('CODEX_THREAD_ID', 'CLAUDE_SESSION_ID', 'GROK_SESSION_ID')}
        for native in (False, True):
            if native: env['CODEX_THREAD_ID'] = OWNER_A['session_id']
            proc = subprocess.run(args, capture_output=True, text=True, env=env)
            self.assertEqual(json.loads(proc.stderr)['category'], 'invalid_input')
            self.assertFalse(absent.exists())

    def test_unrelated_assistant_branch_refused(self):
        self.prepare()
        self.records[-1]['parentUuid'] = 'different-user'
        self.refused('integrity_failure')

    def test_real_tool_result_parent_chain(self):
        self.prepare()
        self.records.insert(1, {'type': 'assistant', 'uuid': 'tool-call', 'parentUuid': 'u1',
            'message': {'stop_reason': 'tool_use', 'content': []}})
        self.records.insert(2, {'type': 'user', 'uuid': 'tool-response', 'parentUuid': 'tool-call',
            'promptId': 'p1', 'message': {'content': [{'type': 'tool_result'}]}})
        self.records[-1]['parentUuid'] = 'tool-response'
        self.recover()

    def test_timestamp_disambiguation_only_with_binding_evidence(self):
        self.prepare()
        other = copy.deepcopy(self.candidates[0]); other.update(sessionId=OWNER_B['session_id'],
            path='/home/box/.claude/projects/hello/' + OWNER_B['session_id'] + '.jsonl', mtime=5000)
        self.candidates.append(other)
        with self.mod.Registry(self.state) as db:
            db.data['bindings'][self.mod.owner_key(OWNER_A)]['handle_created_at'] = 1000
            db.save()
        result = self.recover()
        self.assertEqual(result['sessionId'], self.SESSION)

    def test_cli_recovery_with_fake_ssh_only(self):
        self.prepare()
        fixture_bin = self.root / 'bin'; fixture_bin.mkdir()
        ssh = fixture_bin / 'ssh'
        ssh.write_text('#!' + sys.executable + '\nimport sys\nassert "StrictHostKeyChecking=yes" in sys.argv\n'
                       + 'sys.stdin.read()\nprint(' + repr(json.dumps(self.candidates)) + ')\n')
        ssh.chmod(0o700)
        env = self.fixture_env() if hasattr(self, 'fixture_env') else dict(os.environ)
        env.update(PATH=str(fixture_bin), CODEX_THREAD_ID=OWNER_A['session_id'])
        args = [sys.executable, '-B', str(TARGET), 'recover-final-reply', '--controller', 'codex',
                '--session-id', OWNER_A['session_id'], '--task-id', self.TASK, '--state-dir', str(self.state),
                '--out', str(self.out)]
        proc = subprocess.run(args, capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['action'], 'recovered')
        self.assertEqual((self.state / 'bindings.json').read_bytes(), self.before)

    def test_registry_drift_during_read_refused(self):
        self.prepare()
        def read(*args):
            with self.mod.Registry(self.state) as db:
                db.data['bindings'][self.mod.owner_key(OWNER_A)]['active_task'] = None
                db.save()
            return self.candidates
        with self.assertRaises(self.mod.Blocked) as caught:
            self.mod.recover_final_reply(self.state, OWNER_A, self.TASK, out=self.out, remote_read=read)
        self.assertEqual(caught.exception.category, 'identity_changed')
        self.assertFalse(Path(str(self.out) + '.txt').exists())


if __name__ == '__main__':
    unittest.main()

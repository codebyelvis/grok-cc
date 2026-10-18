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
WORKTREE = 'repo::/home/box/orca/projects/hello'


class RemoteOrca:
    """External CLI boundary only, matching observed native JSON fields."""
    def __init__(self):
        self.terminals = []
        self.creates = self.sends = 0
        self.offline = self.busy = self.lose_create = self.lose_send = False
        self.mode = 'auto mode on'
        self.draft = ''
        self.source = 'screen'
        self.runtime = 'runtime-one'
        self.prompt_space = ' '
        self.calls = []
        self.hook = None

    def __call__(self, args, timeout=None):
        self.calls.append((list(args), timeout))
        if self.hook:
            result = self.hook(args)
            if result is not None:
                return result
        if self.offline:
            raise OSError('remote_runtime_unavailable')
        envelope = {'ok': True, '_meta': {'runtimeId': self.runtime}}
        action = args[1]
        if action == 'list':
            envelope['result'] = {'terminals': copy.deepcopy(self.terminals), 'truncated': False}
        elif action == 'create':
            self.creates += 1
            terminal = {'handle': 'term_' + str(self.creates), 'incarnationId': 'inc_' + str(self.creates),
                        'worktreeId': WORKTREE, 'agentIdentity': 'claude', 'connected': True,
                        'writable': True, 'orphaned': False}
            self.terminals.append(terminal)
            if self.lose_create:
                raise TimeoutError('response lost after create')
            envelope['result'] = {'terminal': copy.deepcopy(terminal)}
        elif action == 'wait':
            envelope['result'] = {'wait': {'satisfied': not self.busy}}
        elif action == 'read':
            screen = '--screen' in args
            envelope['result'] = {'terminal': {'handle': args[args.index('--terminal') + 1],
                'tail': ['────────', '❯' + self.prompt_space + self.draft, '────────', '⏵⏵ ' + self.mode],
                'source': self.source if screen else 'stream', 'truncated': False, 'limited': False,
                'latestCursor': '41', 'nextCursor': '41', 'oldestCursor': '0'}}
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

    def manager(self, owner=OWNER_A, project=None, env='Grok Bot', worktree=WORKTREE):
        return self.mod.BindingManager(self.state, owner, project or self.project, env, worktree, self.remote)

    def explicit_create(self, manager=None, confirm=True):
        manager = manager or self.manager()
        self.assertTrue(callable(getattr(manager, 'create', None)), 'Missing explicit create entry point')
        return manager.create(confirm=confirm)

    def cli_fixture(self):
        path = self.root / 'orca-create-fixture'
        path.write_text('''#!/usr/bin/env python3
import json,pathlib,sys
p=pathlib.Path(__file__).parent
args=sys.argv[1:]; action=args[1]
with (p/'native-calls.jsonl').open('a') as f: f.write(json.dumps(args)+'\\n')
t={'handle':'term-cli','incarnationId':'inc-cli','worktreeId':'repo::/home/box/orca/projects/hello','agentIdentity':'claude','connected':True,'writable':True,'orphaned':False}
if action=='list': r={'terminals':[t] if (p/'created-cli').exists() else [],'truncated':False}
elif action=='create':
 with (p/'created-cli').open('a') as f: f.write('create\\n')
 r={'terminal':t}
elif action=='wait': r={'wait':{'satisfied':True}}
elif action=='read': r={'terminal':{'handle':'term-cli','tail':['────────','❯','────────','auto mode on'],'source':'screen' if '--screen' in args else 'stream','truncated':False,'limited':False,'latestCursor':'1'}}
else: raise SystemExit('unsupported fixture operation')
print(json.dumps({'ok':True,'result':r,'_meta':{'runtimeId':'runtime-cli'}}))
''')
        path.chmod(0o700)
        return path

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
            if args[1] in ('create', 'wait', 'read'):
                row = self.saved()
                states.append((args[1], row['state'], 'creation_candidate' in row))
        self.remote.hook = observe
        first = self.explicit_create()
        self.assertEqual(first['handle'], 'term_1')
        self.assertEqual(self.saved()['state'], 'bound')
        self.assertEqual(states[0], ('create', 'creating', False))
        self.assertTrue(all(state == 'creating' and candidate for action, state, candidate in states[1:]))
        command = next(args for args, _ in self.remote.calls if args[1] == 'create')
        self.assertEqual(command[command.index('--worktree') + 1], 'id:' + WORKTREE)
        self.assertEqual(command[command.index('--command') + 1], 'claude --permission-mode auto')
        self.assertNotIn('--retry-request', command)
        self.assertEqual(self.remote.creates, 1)

    def test_explicit_create_cli_dispatch_and_confirmation_boundary(self):
        fixture = self.cli_fixture()
        common = ['--controller', 'codex', '--session-id', OWNER_A['session_id'],
                  '--project-root', str(self.project), '--project', WORKTREE,
                  '--state-dir', str(self.state), '--orca', str(fixture)]
        env = {**os.environ, 'CODEX_THREAD_ID': OWNER_A['session_id']}
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
        self.assertEqual(sum(args[1] == 'create' for args in calls), 1)

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
            if args[1] == 'create': raise self.failure('launch', started=False)
        self.remote.hook = no_launch
        with self.assertRaises(self.mod.Blocked) as caught: self.explicit_create()
        self.assertEqual(caught.exception.category, 'create_unverified')
        identity = self.saved()['creation_id']
        self.remote.hook = None
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.assertEqual(self.saved()['creation_id'], identity)
        self.assertEqual(sum(args[1] == 'create' for args, _ in self.remote.calls), 1)

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
            if args[1] == 'create':
                return {'ok': True, '_meta': {'runtimeId': 'runtime-one'},
                        'result': {'terminal': {'handle': {'bad': True}, 'worktreeId': WORKTREE}}}
        self.remote.hook = malformed
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.remote.hook = None
        with self.assertRaises(self.mod.Blocked): self.explicit_create()
        self.assertEqual(sum(args[1] == 'create' for args, _ in self.remote.calls), 1)
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
            row.pop('handle', None); row.pop('incarnation', None)
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
            if args[1] == 'create':
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
        env = {**os.environ, 'CODEX_THREAD_ID': OWNER_A['session_id']}
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
            if args[1] == 'create':
                return {'ok': True, '_meta': {'runtimeId': self.remote.runtime}, 'result': {'terminal': target}}
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
        self.assertEqual(sum(args[1] == 'create' for args, _ in self.remote.calls), 2)

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

    def test_legacy_receipt_adoption_is_not_an_available_mutation(self):
        result = subprocess.run([sys.executable, '-B', str(TARGET), 'ensure', '--adopt-terminal', 'foreign'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.state.exists())

    def test_parallel_processes_create_and_submit_at_most_once(self):
        # Real helper processes and flock; only the external CLI is emulated.
        fake = self.root / 'orca-fixture'
        fake.write_text('''#!/usr/bin/env python3
import json,sys,pathlib,time
p=pathlib.Path(__file__).parent
args=sys.argv[1:]; action=args[1]
t={'handle':'term-process','incarnationId':'inc-process','worktreeId':'repo::/home/box/orca/projects/hello','agentIdentity':'claude','connected':True,'writable':True,'orphaned':False}
if action=='list': r={'terminals':[t] if (p/'created').exists() else [],'truncated':False}
elif action=='create':
 with (p/'created').open('a') as f: f.write('create\\n')
 time.sleep(.25); r={'terminal':t}
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
        env = {**os.environ, 'CODEX_THREAD_ID': OWNER_A['session_id']}
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
        process = Mock()
        process.communicate.side_effect = [subprocess.TimeoutExpired('SECRET', 60, stderr='SECRET'), ('', '')]
        with patch.object(self.mod.subprocess, 'Popen', return_value=process):
            with self.assertRaises(self.mod.NativeFailure) as caught:
                native(['terminal', 'send'])
        self.assertTrue(caught.exception.started)
        self.assertEqual(caught.exception.timeout, 60)
        process.kill.assert_called_once()

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
            if args[1] in ('list', 'wait', 'read', 'send', 'create'):
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
            if args[1] in ('create', 'send'):
                with self.mod.Registry(self.state) as db:
                    db.data['bindings'][self.mod.owner_key(OWNER_B)] = {'owner': OWNER_B, 'note': args[1]}
                    db.save()
        self.remote.hook = insert_other
        m.create(confirm=True); m.send('task-one', 'main', 'text')
        with self.mod.Registry(self.state) as db:
            self.assertEqual(db.data['bindings'][self.mod.owner_key(OWNER_B)]['note'], 'send')
        self.assertEqual(self.saved()['tasks']['task-one']['messages']['main']['state'], 'accepted')

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
            if args[1] == 'create':
                return {'ok': True, '_meta': {'runtimeId': 'runtime-one'}, 'result': {'terminal':
                    {'handle': {'invalid': True}, 'incarnationId': 'inc', 'worktreeId': WORKTREE}}}
        self.remote.hook = malformed
        with self.assertRaises(self.mod.Blocked): self.manager().create(confirm=True)
        self.assertEqual(self.saved()['state'], 'creating')
        self.assertNotIn('handle', self.saved())


if __name__ == '__main__':
    unittest.main()

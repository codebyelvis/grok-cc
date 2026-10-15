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
from unittest.mock import patch

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

    def __call__(self, args):
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

    def test_repeated_ensure_creates_only_once(self):
        first = self.manager().ensure()
        second = self.manager().ensure()
        self.assertEqual(first['handle'], second['handle'])
        self.assertEqual(first['incarnation'], second['incarnation'])
        self.assertEqual(self.remote.creates, 1)

    def test_distinct_owner_ignores_idle_foreign_terminal(self):
        a = self.manager().ensure()
        b = self.manager(OWNER_B).ensure()
        self.assertNotEqual(a['handle'], b['handle'])
        self.assertEqual(self.manager().ensure()['handle'], a['handle'])
        self.assertEqual(self.remote.creates, 2)

    def test_successive_tasks_reuse_binding_and_preserve_history(self):
        m = self.manager()
        first = m.ensure()
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
        m = self.manager(); m.ensure()
        first = m.send('task-one', 'main', 'original text')
        repeat = m.send('task-one', 'main', 'original text')
        self.assertEqual(first['message']['receipt'], repeat['message']['receipt'])
        with self.assertRaises(ValueError):
            m.send('task-one', 'main', 'different text')
        self.assertEqual(self.remote.sends, 1)

    def test_pending_other_task_blocks_and_export_stays_on_same_terminal(self):
        m = self.manager(); first = m.ensure()
        m.send('task-one', 'main', 'original text')
        with self.assertRaises(ValueError):
            m.send('task-two', 'main', 'other task')
        result = m.send('task-one', 'export-1', 'export final patch only')
        self.assertEqual(result['binding']['handle'], first['handle'])
        self.assertEqual(self.remote.creates, 1)

    def test_busy_or_offline_does_not_create_replacement(self):
        m = self.manager(); first = m.ensure()
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
        m = self.manager(); m.ensure()
        self.remote.terminals[0]['incarnationId'] = 'restarted'
        with self.assertRaises(ValueError): m.ensure()
        self.remote.terminals[0]['incarnationId'] = 'inc_1'
        self.remote.runtime = 'other-runtime'
        with self.assertRaises(ValueError): m.ensure()
        self.assertEqual(self.remote.creates, 1)

    def test_project_or_destination_mismatch_is_not_a_new_binding(self):
        self.manager().ensure()
        another = self.root / 'another'; another.mkdir()
        for m in [self.manager(project=another), self.manager(env='Elsewhere'), self.manager(worktree='other::/path')]:
            with self.assertRaises(ValueError): m.ensure()
        self.assertEqual(self.remote.creates, 1)

    def test_lost_create_response_leaves_intent_and_never_recreates(self):
        self.remote.lose_create = True
        with self.assertRaises(TimeoutError): self.manager().ensure()
        self.remote.lose_create = False
        with self.assertRaises(ValueError): self.manager().ensure()
        self.assertEqual(self.remote.creates, 1)
        self.assertTrue((self.state / 'bindings.json').exists())

    def test_lost_send_response_never_resends_or_finishes(self):
        m = self.manager(); m.ensure(); self.remote.lose_send = True
        with self.assertRaises(TimeoutError): m.send('task-one', 'main', 'text')
        self.remote.lose_send = False
        replay = m.send('task-one', 'main', 'text')
        self.assertEqual(replay['action'], 'resume')
        self.assertEqual(replay['message']['state'], 'sending')
        with self.assertRaises(ValueError): m.finish('task-one')
        with self.assertRaises(ValueError): m.send('task-one', 'export-1', 'export')
        self.assertEqual(self.remote.sends, 1)

    def test_nonempty_draft_bypass_or_unavailable_screen_blocks_send(self):
        m = self.manager(); m.ensure()
        for attr, value in [('draft', 'my unsent draft'), ('mode', 'bypass permissions on'), ('source', 'screen-unavailable')]:
            original = getattr(self.remote, attr); setattr(self.remote, attr, value)
            with self.assertRaises(ValueError): m.send('task-one', 'main', 'text')
            setattr(self.remote, attr, original)
        self.assertEqual(self.remote.sends, 0)

    def test_native_empty_startup_hint_with_nbsp_is_not_a_user_draft(self):
        m = self.manager(); m.ensure()
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
        m = self.manager(); m.ensure()
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
        m = self.manager(); binding = m.ensure()
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

    def test_first_send_does_not_allow_arbitrary_try_text_or_real_drafts(self):
        m = self.manager(); m.ensure()
        for draft in ('my actual unsent draft', 'Try "delete all files"',
                      'Try "fix typecheck errors" then execute this',
                      'Try "refactor <filepath>" then execute this',
                      'Try "refactor my-real-file.py"'):
            self.remote.draft = draft
            with self.assertRaises(ValueError):
                m.send('task-one', 'main', 'code task')
        self.assertEqual(self.remote.sends, 0)
        row = json.loads((self.state / 'bindings.json').read_text())['bindings'][self.mod.owner_key(OWNER_A)]
        self.assertEqual(row['tasks'], {})
        self.assertIsNone(row['active_task'])

    def test_finish_requires_actual_idle_and_keeps_binding(self):
        m = self.manager(); first = m.ensure(); m.send('task-one', 'main', 'text')
        self.remote.busy = True
        with self.assertRaises(ValueError): m.finish('task-one')
        self.remote.busy = False; m.finish('task-one')
        self.assertEqual(m.ensure()['handle'], first['handle'])

    def test_private_state_does_not_store_prompt_and_refuses_symlink(self):
        self.manager().ensure()
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
        self.manager().ensure(); (self.state / 'bindings.json').write_text('invalid')
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
        concurrent('ensure')
        self.assertEqual((self.root / 'created').read_text(), 'create\n')
        prompt = self.root / 'prompt.txt'; prompt.write_text('one real logical task')
        concurrent('send', ['--task-id', 'task-one', '--text-file', str(prompt)])
        self.assertEqual((self.root / 'sent').read_text(), 'send\n')
        self.assertEqual((self.root / 'created').read_text(), 'create\n')


if __name__ == '__main__':
    unittest.main()

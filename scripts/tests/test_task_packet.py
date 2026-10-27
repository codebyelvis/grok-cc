"""Author: elvis. Exercise real filesystem and git apply, no mocks."""
import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'task_packet.py'
spec=importlib.util.spec_from_file_location('task_packet', SOURCE)
packet=importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet)

class PacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        (self.root/'a.py').write_text('value = 1\n')
        (self.root/'unrelated.txt').write_text('user draft\n')
        self.manifest=packet.prepare(self.root, ['a.py'], 'Set value to 2')
        self.diff='--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n'
    def tearDown(self):
        self.tmp.cleanup()
    def wrap(self, diff=None, task_id=None):
        tid=task_id or self.manifest['task_id']
        diff = self.diff if diff is None else diff
        digest = hashlib.sha256(diff.encode('utf-8')).hexdigest()
        count = diff.count('\n')
        return f'BEGIN_PATCH {tid}\n{diff}PATCH_SHA256 {digest}\nPATCH_LINES {count}\nEND_PATCH {tid}\n'
    def test_snapshot_carries_actual_bytes_and_project_root(self):
        self.assertEqual(self.manifest['project_root'], str(self.root.resolve()))
        self.assertEqual(self.manifest['files']['a.py']['content'], 'value = 1\n')
        self.assertEqual(self.manifest['files']['a.py']['sha256'], hashlib.sha256(b'value = 1\n').hexdigest())
    def test_valid_patch_checks_without_modifying_any_source(self):
        self.assertEqual(packet.check(self.manifest, self.wrap()), self.diff)
        self.assertEqual((self.root/'a.py').read_text(), 'value = 1\n')
        self.assertEqual((self.root/'unrelated.txt').read_text(), 'user draft\n')
    def test_empty_patch_checks_and_validates_baseline(self):
        empty_reply = self.wrap('')
        self.assertEqual(packet.check(self.manifest, empty_reply), '')
        self.assertEqual((self.root/'a.py').read_text(), 'value = 1\n')
        (self.root/'a.py').write_text('value = 99\n')
        with self.assertRaises(ValueError): packet.check(self.manifest, empty_reply)
        (self.root/'a.py').write_text('value = 1\n')
    def test_empty_patch_cli_check_writes_zero_byte_file(self):
        with tempfile.TemporaryDirectory() as external:
            packet_path = Path(external).resolve() / 'packet.json'
            reply_path = Path(external).resolve() / 'reply.txt'
            out_patch = Path(external).resolve() / 'checked.patch'
            packet_path.write_text(json.dumps(self.manifest))
            reply_path.write_text(self.wrap(''))
            args = [sys.executable, str(SOURCE), 'check', '--packet', str(packet_path),
                    '--reply', str(reply_path), '--out', str(out_patch)]
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out_patch.is_file())
            self.assertEqual(out_patch.read_bytes(), b'')
    def test_check_denies_changed_baseline(self):
        (self.root/'a.py').write_text('value = 77\n')
        with self.assertRaises(ValueError): packet.check(self.manifest, self.wrap())
        self.assertEqual((self.root/'a.py').read_text(), 'value = 77\n')
    def test_check_denies_stale_and_incomplete_result(self):
        for reply in [self.wrap(task_id='other'), self.wrap().replace('END_PATCH','MISSING'), self.wrap()+self.wrap()]:
            with self.subTest(reply=reply):
                with self.assertRaises(ValueError): packet.check(self.manifest, reply)
    def test_check_denies_scope_escape_and_delete(self):
        for diff in [self.diff.replace('a.py','unrelated.txt'), self.diff.replace('b/a.py','/dev/null'), self.diff.replace('a.py','../escape.py')]:
            with self.subTest(diff=diff):
                with self.assertRaises(ValueError): packet.check(self.manifest, self.wrap(diff))
    def test_check_denies_binary_rename_and_mode_metadata(self):
        for prefix in ['GIT binary patch\n', 'rename from a.py\n', 'new file mode 100755\n']:
            with self.subTest(prefix=prefix):
                with self.assertRaises(ValueError): packet.check(self.manifest, self.wrap(prefix+self.diff))
    def test_prepare_denies_sensitive_paths_and_traversal(self):
        for name in ['.env', '.env.production', '.claude/settings.json', 'private.pem', 'api-token.txt', '../outside', '/tmp/outside']:
            with self.subTest(name=name):
                with self.assertRaises(ValueError): packet.prepare(self.root,[name],'task')
    def test_prepare_denies_symlinks_and_non_utf8(self):
        (self.root/'link.py').symlink_to(self.root/'a.py')
        (self.root/'raw.bin').write_bytes(b'\xff')
        for name in ['link.py','raw.bin']:
            with self.assertRaises(ValueError): packet.prepare(self.root,[name],'task')
    def test_check_denies_parent_symlink_swap(self):
        folder=self.root/'folder';folder.mkdir();(folder/'a.py').write_text('value = 1\n')
        manifest=packet.prepare(self.root,['folder/a.py'],'task')
        (folder/'a.py').unlink();folder.rmdir()
        folder.symlink_to(self.root)
        reply=self.wrap(self.diff.replace('a.py','folder/a.py'), manifest['task_id'])
        with self.assertRaises(ValueError):packet.check(manifest,reply)
    def test_new_file_is_explicit_and_collision_is_denied(self):
        manifest=packet.prepare(self.root,['new.py'],'create')
        diff='--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+value = 2\n'
        reply=self.wrap(diff, manifest['task_id'])
        self.assertEqual(packet.check(manifest,reply),diff)
        self.assertFalse((self.root/'new.py').exists())
        subprocess.run(['git','apply','--'],input=diff.encode('utf-8'),cwd=self.root,check=True)
        self.assertEqual((self.root/'new.py').read_bytes(),b'value = 2\n')
        (self.root/'new.py').write_text('user work\n')
        with self.assertRaises(ValueError):packet.check(manifest,reply)
    def test_real_git_rejects_context_mismatch(self):
        diff=self.diff.replace('-value = 1','-value = 9')
        with self.assertRaises(ValueError):packet.check(self.manifest,self.wrap(diff))
    def test_cli_cannot_overwrite_project_source_or_existing_output(self):
        result=subprocess.run(['python3',str(SOURCE),'prepare','--root',str(self.root),'--file','a.py','--task','task','--out',str(self.root/'a.py')],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((self.root/'a.py').read_text(),'value = 1\n')
    def test_check_rejects_hunk_smuggling_and_multiple_diffs(self):
        diffs=[self.diff+'--- a/unrelated.txt\n+++ b/unrelated.txt\n@@ -1 +1 @@\n-user draft\n+oops\n', self.diff+'garbage\n']
        for diff in diffs:
            with self.assertRaises(ValueError):packet.check(self.manifest,self.wrap(diff))
    def test_check_denies_edit_occurring_during_native_git_check(self):
        (self.root/'a.py').write_text('value = 1\n'+''.join(f'line{i} = {i}\n' for i in range(30)))
        manifest=packet.prepare(self.root,['a.py'],'task')
        tid=manifest['task_id']
        diff='--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,3 @@\n-value = 1\n+value = 2\n line0 = 0\n line1 = 1\n'
        reply=self.wrap(diff, tid)
        real_git=shutil.which('git')
        wrappers=self.root/'wrappers';wrappers.mkdir()
        wrapper=wrappers/'git'
        wrapper.write_text('#!/bin/sh\n'+"printf 'user_edit = 99\\n' >> a.py\n"+f'exec {real_git} "$@"\n')
        wrapper.chmod(0o755)
        old_path=os.environ['PATH']
        try:
            os.environ['PATH']=str(wrappers)+os.pathsep+old_path
            with self.assertRaises(ValueError):packet.check(manifest,reply)
        finally:os.environ['PATH']=old_path
        self.assertTrue((self.root/'a.py').read_text().endswith('user_edit = 99\n'))
    def test_prepare_never_exports_outside_bytes_during_symlink_swap(self):
        outside=self.root.parent/(self.root.name+'-outside.txt')
        outside.write_text('PRIVATE_OUTSIDE_BYTES\n')
        link=self.root/'swap';link.symlink_to(outside)
        selected=self.root/'a.py'
        saved=self.root/'saved'
        stop=threading.Event()
        def swap():
            while not stop.is_set():
                try:
                    selected.rename(saved);link.rename(selected)
                    selected.rename(link);saved.rename(selected)
                except FileNotFoundError:pass
        worker=threading.Thread(target=swap);worker.start()
        try:
            for _ in range(1500):
                try:
                    result=packet.prepare(self.root,['a.py'],'task')
                except (ValueError,OSError):continue
                self.assertNotIn('PRIVATE_OUTSIDE_BYTES',result['files']['a.py']['content'] or '')
        finally:
            stop.set();worker.join();outside.unlink()
    def test_output_never_writes_project_during_parent_symlink_swap(self):
        with tempfile.TemporaryDirectory() as external:
            external=Path(external).resolve()
            parent=external/'output';parent.mkdir()
            link=external/'link';link.symlink_to(self.root)
            saved=external/'saved'
            stop=threading.Event()
            def swap():
                while not stop.is_set():
                    try:
                        parent.rename(saved);link.rename(parent)
                        parent.rename(link);saved.rename(parent)
                    except FileNotFoundError:pass
            worker=threading.Thread(target=swap);worker.start()
            try:
                for i in range(1500):
                    try:packet.write_external_output(parent/f'result{i}.txt','data',self.root)
                    except (ValueError,OSError):pass
                self.assertEqual(list(self.root.glob('result*.txt')),[])
            finally:stop.set();worker.join()
    def test_output_parent_symlink_like_macos_tmp_is_resolved(self):
        with tempfile.TemporaryDirectory() as other:
            real=Path(other).resolve()/'private'/'tmp';real.mkdir(parents=True)
            link=Path(other)/'tmp';link.symlink_to(real)
            packet.write_external_output(link/'out.txt','data',self.root)
            self.assertEqual((real/'out.txt').read_text(),'data')
            self.assertFalse((real/'out.txt').is_symlink())
            with self.assertRaises(ValueError):packet.write_external_output(link/'out.txt','x',self.root)
            inside=Path(other)/'into_project';inside.symlink_to(self.root)
            with self.assertRaises(ValueError):packet.write_external_output(inside/'leak.txt','x',self.root)
            self.assertFalse((self.root/'leak.txt').exists())
    def test_normal_git_can_apply_checked_output(self):
        patch=packet.check(self.manifest,self.wrap())
        subprocess.run(['git','apply','--'],input=patch,text=True,cwd=self.root,check=True)
        self.assertEqual((self.root/'a.py').read_text(),'value = 2\n')
    def test_non_lf_hunk_payload_checks_and_applies(self):
        for separator in ['\v', '\f', '\x1c', '\x1d', '\x1e', '\x85', '\u2028', '\u2029', '\r']:
            with self.subTest(separator=ascii(separator)):
                context=f'# left{separator}right\n'
                before=context+f'value = "old{separator}tail"\n'
                after=context+f'value = "new{separator}tail"\n'
                (self.root/'a.py').write_bytes(before.encode('utf-8'))
                self.manifest=packet.prepare(self.root,['a.py'],'update text')
                diff=('--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,2 @@\n '+context
                      +f'-value = "old{separator}tail"\n+value = "new{separator}tail"\n')
                native=subprocess.run(['git','apply','--check','--'],input=diff.encode('utf-8'),
                                      cwd=self.root,capture_output=True)
                self.assertEqual(native.returncode,0,native.stderr)
                try:
                    checked=packet.check(self.manifest,self.wrap(diff))
                except ValueError as exc:
                    self.fail(f'Native Git accepted the UTF-8 patch but helper rejected it: {exc}')
                self.assertEqual(checked.encode('utf-8'),diff.encode('utf-8'))
                self.assertEqual((self.root/'a.py').read_bytes(),before.encode('utf-8'))
                self.assertEqual((self.root/'unrelated.txt').read_bytes(),b'user draft\n')
                subprocess.run(['git','apply','--'],input=checked.encode('utf-8'),cwd=self.root,check=True)
                self.assertEqual((self.root/'a.py').read_bytes(),after.encode('utf-8'))
    def test_cli_preserves_patch_newlines(self):
        cases=[
            ('inline-cr',b'value = "old\rtail"\n',b'value = "new\rtail"\n',b'\n'),
            ('crlf-content',b'value = 1\r\n',b'value = 2\r\n',b'\n'),
            ('crlf-headers',b'value = 1\r\n',b'value = 2\r\n',b'\r\n'),
        ]
        with tempfile.TemporaryDirectory() as external:
            external=Path(external).resolve()
            for name,before,after,framing in cases:
                with self.subTest(case=name):
                    (self.root/'a.py').write_bytes(before)
                    manifest_path=external/(name+'.json')
                    prepared=subprocess.run([sys.executable,str(SOURCE),'prepare','--root',str(self.root),
                                             '--file','a.py','--task','update text','--out',str(manifest_path)],
                                            capture_output=True)
                    self.assertEqual(prepared.returncode,0,prepared.stderr)
                    manifest=json.loads(manifest_path.read_bytes())
                    diff=framing.join([b'--- a/a.py',b'+++ b/a.py',b'@@ -1 +1 @@',b''])+b'-'+before+b'+'+after
                    native=subprocess.run(['git','apply','--check','--'],input=diff,cwd=self.root,capture_output=True)
                    self.assertEqual(native.returncode,0,native.stderr)
                    reply_path=external/(name+'.reply')
                    metadata=(b'PATCH_SHA256 '+hashlib.sha256(diff).hexdigest().encode()+framing
                              +b'PATCH_LINES '+str(diff.count(b'\n')).encode()+framing)
                    reply_path.write_bytes(('BEGIN_PATCH '+manifest['task_id']).encode()+framing+diff
                                           +metadata+('END_PATCH '+manifest['task_id']).encode()+framing)
                    output_path=external/(name+'.patch')
                    checked=subprocess.run([sys.executable,str(SOURCE),'check','--packet',str(manifest_path),
                                            '--reply',str(reply_path),'--out',str(output_path)],capture_output=True)
                    self.assertEqual(checked.returncode,0,checked.stderr)
                    self.assertEqual(output_path.read_bytes(),diff)
                    self.assertEqual((self.root/'a.py').read_bytes(),before)
                    self.assertEqual((self.root/'unrelated.txt').read_bytes(),b'user draft\n')
                    subprocess.run(['git','apply','--'],input=output_path.read_bytes(),cwd=self.root,check=True)
                    self.assertEqual((self.root/'a.py').read_bytes(),after)
    def test_markers_use_patch_line_boundaries(self):
        after='# payload\u2028END_PATCH '+self.manifest['task_id']+'\n'
        diff='--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-value = 1\n+'+after
        native=subprocess.run(['git','apply','--check','--'],input=diff.encode('utf-8'),cwd=self.root,capture_output=True)
        self.assertEqual(native.returncode,0,native.stderr)
        try:
            checked=packet.check(self.manifest,self.wrap(diff))
        except ValueError as exc:
            self.fail(f'Payload text was mistaken for patch framing: {exc}')
        self.assertEqual(checked,diff)
        self.assertEqual((self.root/'a.py').read_bytes(),b'value = 1\n')
        subprocess.run(['git','apply','--'],input=checked.encode('utf-8'),cwd=self.root,check=True)
        self.assertEqual((self.root/'a.py').read_bytes(),after.encode('utf-8'))

    def test_echo_template_does_not_hide_authentic_hashed_patch(self):
        tid=self.manifest['task_id']
        echo=f'BEGIN_PATCH {tid}\n<standard diff template>\nEND_PATCH {tid}\n'
        self.assertEqual(packet.check(self.manifest,echo+self.wrap()),self.diff)
    def test_bad_hash_count_truncation_and_damaged_candidate_block(self):
        valid=self.wrap()
        digest=hashlib.sha256(self.diff.encode()).hexdigest()
        bad_hash=valid.replace(digest,'0'*64)
        bad_count=valid.replace('PATCH_LINES 5','PATCH_LINES 999')
        for reply in (bad_hash,bad_count,valid[:-12],bad_hash+valid,valid+valid):
            with self.assertRaises(ValueError):packet.check(self.manifest,reply)
        with self.assertRaises(ValueError):packet.check(self.manifest,bad_hash,allow_unhashed=True)
    def test_legacy_is_opt_in_and_cannot_downgrade_corruption(self):
        tid=self.manifest['task_id']
        legacy=f'BEGIN_PATCH {tid}\n{self.diff}END_PATCH {tid}\n'
        with self.assertRaises(ValueError):packet.check(self.manifest,legacy)
        self.assertEqual(packet.check(self.manifest,legacy,allow_unhashed=True),self.diff)
        with self.assertRaises(ValueError):packet.check(self.manifest,legacy+legacy,allow_unhashed=True)
    def test_render_omits_root_and_baseline_preserves_snapshot_and_bounds(self):
        (self.root/'a.py').write_text('local edit\n')
        text=packet.render(self.manifest)
        self.assertIn('value = 1\n',text)
        self.assertNotIn(str(self.root.resolve()),text)
        self.assertNotIn(self.manifest['files']['a.py']['sha256'],text)
        self.assertNotIn('BEGIN_PATCH '+self.manifest['task_id'],text)
        self.assertNotIn('END_PATCH '+self.manifest['task_id'],text)
        size=len(text.encode('utf-8'))
        self.assertEqual(packet.render(self.manifest,max_bytes=size),text)
        with self.assertRaises(ValueError):packet.render(self.manifest,max_bytes=size-1)
        self.assertEqual((self.root/'a.py').read_text(),'local edit\n')
    def test_secret_scan_prepare_and_tampered_render_without_value_leak(self):
        tokens=['AKIA'+'A'*16,'ghp_'+'A'*36,'github_pat_'+'A'*30,'sk-'+'A'*30,
                'xoxb-'+'1'*20,'tskey-'+'A'*25,'-----BEGIN '+'PRIVATE KEY-----']
        for token in tokens:
            (self.root/'a.py').write_text('first\n'+token+'\n')
            with self.assertRaises(ValueError) as caught:packet.prepare(self.root,['a.py'],'task')
            self.assertNotIn(token,str(caught.exception))
            self.assertIn('a.py',str(caught.exception));self.assertIn('2',str(caught.exception))
            changed=json.loads(json.dumps(self.manifest));changed['task']=token
            with self.assertRaises(ValueError) as caught:packet.render(changed)
            self.assertNotIn(token,str(caught.exception))
        (self.root/'a.py').write_text('prefixes ghp_ sk- tskey- and regex [A-Z]{16}\n')
        packet.prepare(self.root,['a.py'],'safe task')
    def test_secret_in_path_and_task_do_not_escape_diagnostics(self):
        token='ghp_'+'A'*36
        for names,task in ((['a.py'],token),([token+'.py'],'task')):
            with self.assertRaises(ValueError) as caught:packet.prepare(self.root,names,task)
            self.assertNotIn(token,str(caught.exception))
    def test_render_cli_uses_private_external_output_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as external:
            folder=Path(external).resolve();manifest=folder/'packet.json';out=folder/'prompt.txt'
            manifest.write_text(json.dumps(self.manifest),encoding='utf-8')
            args=[sys.executable,str(SOURCE),'render','--packet',str(manifest),'--out',str(out)]
            result=subprocess.run(args,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            metadata=json.loads(result.stdout)
            self.assertEqual(metadata['prompt_bytes'],len(out.read_bytes()))
            self.assertEqual(out.stat().st_mode&0o777,0o600)
            self.assertNotEqual(subprocess.run(args,capture_output=True).returncode,0)
            self.assertEqual((self.root/'a.py').read_text(),'value = 1\n')
    def test_render_refuses_inconsistent_snapshot(self):
        changed=json.loads(json.dumps(self.manifest));changed['files']['a.py']['content']='changed'
        with self.assertRaises(ValueError):packet.render(changed)

    def test_prepare_frontloads_same_utf8_budget_as_render(self):
        text=packet.render(self.manifest);size=len(text.encode('utf-8'))
        prepared=packet.prepare(self.root,['a.py'],'Set value to 2',max_bytes=size)
        self.assertEqual(len(packet.render(prepared,max_bytes=size).encode('utf-8')),size)
        with self.assertRaises(ValueError):packet.prepare(self.root,['a.py'],'Set value to 2',max_bytes=size-1)
        (self.root/'a.py').write_text('汉'*42000,encoding='utf-8')
        with self.assertRaises(ValueError):packet.prepare(self.root,['a.py'],'task')
        prepared=packet.prepare(self.root,['a.py'],'task',max_bytes=200000)
        self.assertGreater(len(packet.render(prepared,max_bytes=200000).encode()),120*1024)
    def test_prepare_cli_reports_metrics_and_overbudget_writes_nothing(self):
        with tempfile.TemporaryDirectory() as external:
            out=Path(external).resolve()/'packet.json'
            args=[sys.executable,str(SOURCE),'prepare','--root',str(self.root),'--file','a.py',
                  '--task','task','--out',str(out)]
            failed=subprocess.run([*args,'--max-bytes','1'],capture_output=True)
            self.assertNotEqual(failed.returncode,0);self.assertFalse(out.exists())
            self.assertIn('reduce',json.loads(failed.stderr)['detail'])
            result=subprocess.run(args,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            metrics=json.loads(result.stdout)
            prompt=packet.render(json.loads(out.read_text(encoding='utf-8')))
            self.assertEqual(metrics['prompt_bytes'],len(prompt.encode()))
            self.assertEqual(metrics['token_estimate'],(metrics['prompt_bytes']+3)//4)
            self.assertEqual(metrics['packet_bytes'],len(out.read_bytes()))
            self.assertIn('at most 10 lines',prompt);self.assertIn('do not repeat the task',prompt)
    def test_prepare_and_render_reject_unsupported_transport_without_output(self):
        with tempfile.TemporaryDirectory() as external:
            external=Path(external).resolve()
            for label,task,content in (
                    ('marker','task','marker = "grok-cc-msg:"\n'),
                    ('nul-task','task\0private-content','value = 1\n'),
                    ('oversized','x'*65000,'y'*100000)):
                with self.subTest(case=label):
                    names=['a.py'] if label!='oversized' else ['a.py','b.py','c.py','d.py']
                    for name in names:(self.root/name).write_text(content,encoding='utf-8')
                    manifest=json.loads(json.dumps(self.manifest));manifest['task']=task
                    manifest['files']={name:{'content':content,'sha256':hashlib.sha256(content.encode()).hexdigest()}
                                       for name in names}
                    with self.assertRaises(ValueError) as caught:
                        packet.prepare(self.root,names,task,max_bytes=500000)
                    self.assertNotIn(content,str(caught.exception))
                    self.assertNotIn(task,str(caught.exception))
                    packet_path=external/(label+'.json');packet_path.write_text(json.dumps(manifest))
                    output=external/(label+'.txt')
                    result=subprocess.run([sys.executable,str(SOURCE),'render','--packet',str(packet_path),
                                           '--out',str(output),'--max-bytes','500000'],capture_output=True)
                    self.assertNotEqual(result.returncode,0)
                    self.assertFalse(output.exists())
                    self.assertNotIn(content,result.stderr.decode());self.assertNotIn(task,result.stderr.decode())
                    if label!='nul-task':
                        output=external/(label+'-prepared.json')
                        args=[sys.executable,str(SOURCE),'prepare','--root',str(self.root),'--task',task,
                              '--out',str(output),'--max-bytes','500000']
                        for name in names:args.extend(['--file',name])
                        result=subprocess.run(args,capture_output=True)
                        self.assertNotEqual(result.returncode,0)
                        self.assertFalse(output.exists())
    def test_transport_boundary_counts_utf8_bytes_before_render_output(self):
        manifest=json.loads(json.dumps(self.manifest))
        manifest['task']='汉'
        overhead=len(packet.render(manifest).encode('utf-8'))-3
        remaining=450*1024-overhead
        manifest['task']='汉'*(remaining//3)+'x'*(remaining%3)
        self.assertEqual(len(packet.render(manifest,max_bytes=500000).encode('utf-8')),460800)
        manifest['task']+='x'
        with self.assertRaises(ValueError):packet.render(manifest,max_bytes=500000)
    def test_media_override_is_only_an_extension_override(self):
        (self.root/'diagram.png').write_text('safe UTF-8 text\n')
        with self.assertRaises(ValueError):packet.prepare(self.root,['diagram.png'],'task')
        packet.prepare(self.root,['diagram.png'],'task',allow_binary=True)
        (self.root/'diagram.png').write_bytes(b'\x89PNG\r\n\x1a\n')
        with self.assertRaises(ValueError):packet.prepare(self.root,['diagram.png'],'task',allow_binary=True)
        for raw in (b'%PDF-1.7\ntext',b'<svg viewBox="0 0 10 10"></svg>'):
            (self.root/'a.py').write_bytes(raw)
            with self.assertRaises(ValueError):packet.prepare(self.root,['a.py'],'task',allow_binary=True)
    def test_known_encoded_media_rejected_without_flagging_ordinary_text(self):
        import base64
        encoded=base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'fake-payload'*20).decode()
        for content in (encoded,'data:'+'image/png;base64,'+encoded):
            (self.root/'a.py').write_text(content)
            with self.assertRaises(ValueError):packet.prepare(self.root,['a.py'],'task')
            changed=json.loads(json.dumps(self.manifest));changed['task']=content
            with self.assertRaises(ValueError):packet.render(changed)
        (self.root/'a.py').write_text('A'*2000+'\nregex = "[A-Za-z0-9+/]+"\n')
        packet.prepare(self.root,['a.py'],'safe plain text')
    def test_summary_explicit_evidence_is_short_and_not_a_verdict(self):
        summary=packet.handoff_summary(self.manifest['task_id'],self.manifest,
            mac_tests=['unit:pass:4:0'],unverified=['cloud'],category='none')
        self.assertLessEqual(len(summary.split('\n'))-1,15)
        self.assertIn('a.py',summary);self.assertIn('unit:pass:4:0',summary)
        self.assertIn('supplied',summary);self.assertNotIn('value =',summary)
        self.assertNotIn(str(self.root.resolve()),summary)
        self.assertIn('unverified',packet.handoff_summary(self.manifest['task_id']))
        for fields in ({'mac_tests':['unit:pass:0:2']},{'unverified':['source\n+diff']},
                       {'mac_tests':['ghp_'+'A'*36+':pass:1:0']}):
            with self.assertRaises(ValueError):packet.handoff_summary(self.manifest['task_id'],**fields)
        with self.assertRaises(ValueError):packet.handoff_summary('other',self.manifest)
    def test_summary_cli_external_private_no_overwrite_and_no_project_write(self):
        with tempfile.TemporaryDirectory() as external:
            out=Path(external).resolve()/'summary.md'
            args=[sys.executable,str(SOURCE),'handoff-summary','--task-id',self.manifest['task_id'],
                  '--project-root',str(self.root),'--out',str(out)]
            result=subprocess.run(args,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('unverified',out.read_text());self.assertEqual(out.stat().st_mode&0o777,0o600)
            self.assertNotEqual(subprocess.run(args,capture_output=True).returncode,0)
            inside=[*args];inside[-1]=str(self.root/'summary.md')
            self.assertNotEqual(subprocess.run(inside,capture_output=True).returncode,0)
            self.assertFalse((self.root/'summary.md').exists())

    def test_ftype_source_is_not_a_media_container(self):
        import base64
        source='def ftype(path):\n    return path.suffix\n'
        compile(source,'ftype.py','exec')
        (self.root/'a.py').write_text(source)
        self.assertFalse(packet.media_magic(source.encode()))
        prepared=packet.prepare(self.root,['a.py'],'adjust docstring')
        self.assertIn(source,packet.render(prepared))
        container=b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2'
        self.assertTrue(packet.media_magic(container))
        (self.root/'a.py').write_text(base64.b64encode(container).decode())
        with self.assertRaises(ValueError):packet.prepare(self.root,['a.py'],'task',allow_binary=True)

if __name__=='__main__':unittest.main()

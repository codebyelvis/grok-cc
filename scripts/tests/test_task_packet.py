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
        return f'BEGIN_PATCH {tid}\n{diff or self.diff}END_PATCH {tid}\n'
    def test_snapshot_carries_actual_bytes_and_project_root(self):
        self.assertEqual(self.manifest['project_root'], str(self.root.resolve()))
        self.assertEqual(self.manifest['files']['a.py']['content'], 'value = 1\n')
        self.assertEqual(self.manifest['files']['a.py']['sha256'], hashlib.sha256(b'value = 1\n').hexdigest())
    def test_valid_patch_checks_without_modifying_any_source(self):
        self.assertEqual(packet.check(self.manifest, self.wrap()), self.diff)
        self.assertEqual((self.root/'a.py').read_text(), 'value = 1\n')
        self.assertEqual((self.root/'unrelated.txt').read_text(), 'user draft\n')
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
        reply=f"BEGIN_PATCH {manifest['task_id']}\n{self.diff.replace('a.py','folder/a.py')}END_PATCH {manifest['task_id']}\n"
        with self.assertRaises(ValueError):packet.check(manifest,reply)
    def test_new_file_is_explicit_and_collision_is_denied(self):
        manifest=packet.prepare(self.root,['new.py'],'create')
        diff='--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+value = 2\n'
        reply=f"BEGIN_PATCH {manifest['task_id']}\n{diff}END_PATCH {manifest['task_id']}\n"
        self.assertEqual(packet.check(manifest,reply),diff)
        self.assertFalse((self.root/'new.py').exists())
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
        reply=f'BEGIN_PATCH {tid}\n{diff}END_PATCH {tid}\n'
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
                    reply_path.write_bytes(('BEGIN_PATCH '+manifest['task_id']).encode()+framing+diff
                                           +('END_PATCH '+manifest['task_id']).encode()+framing)
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

if __name__=='__main__':unittest.main()

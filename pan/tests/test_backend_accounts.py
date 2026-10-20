import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from config_persistence import atomic_write_config
from bootstrap import initialize

AVAILABLE = importlib.util.find_spec('werkzeug') is not None
if AVAILABLE:
    from auth_accounts import account, verify, public_accounts, add_account, change_password, remove_account


@unittest.skipUnless(AVAILABLE, 'Password hash dependencies are verified inside the Docker image')
class AccountRulesTests(unittest.TestCase):
    def setUp(self): self.auth = {'users': '原始账号', 'password': ' 旧密码-123 ', 'session_timeout': 3600}

    def test_old_credentials_untouched_new_password_is_hashed(self):
        before = copy.deepcopy(self.auth)
        updated = add_account(self.auth, '新账号', 'new-pass-123')
        self.assertEqual(self.auth, before)
        self.assertEqual(updated['users'], before['users'])
        self.assertEqual(updated['password'], before['password'])
        self.assertTrue(verify(updated, '原始账号', ' 旧密码-123 '))
        self.assertFalse(verify(updated, '原始账号', '旧密码-123'))
        self.assertTrue(verify(updated, '新账号', 'new-pass-123'))
        self.assertNotIn('new-pass-123', json.dumps(updated))
        self.assertNotIn('password_hash', json.dumps(public_accounts(updated, '新账号')))

    def test_duplicate_invalid_and_weak_credentials_do_not_mutate(self):
        for name, password in [('原始账号', 'abcdef'), ('a/b', 'abcdef'), ('valid', 'short'), ('', 'abcdef')]:
            before = copy.deepcopy(self.auth)
            with self.assertRaises(ValueError): add_account(self.auth, name, password)
            self.assertEqual(before, self.auth)
        updated = add_account(self.auth, 'Member', 'abcdef')
        with self.assertRaises(ValueError): add_account(updated, 'member', 'abcdef')

    def test_change_only_target_and_revoke_its_old_version(self):
        updated = add_account(self.auth, 'member', 'abcdef')
        original_version = account(updated, 'member')['session_version']
        changed = change_password(updated, 'member', 'changed-pass')
        self.assertEqual(changed['password'], self.auth['password'])
        self.assertFalse(verify(changed, 'member', 'abcdef'))
        self.assertTrue(verify(changed, 'member', 'changed-pass'))
        self.assertNotEqual(account(changed, 'member')['session_version'], original_version)
        self.assertEqual(account(changed, '原始账号')['session_version'], 'legacy')

    def test_primary_and_current_account_protected(self):
        updated = add_account(self.auth, 'member', 'abcdef')
        with self.assertRaises(ValueError): remove_account(updated, '原始账号', 'member')
        with self.assertRaises(ValueError): remove_account(updated, 'member', 'member')
        removed = remove_account(updated, 'member', '原始账号')
        self.assertIsNone(account(removed, 'member'))
        self.assertTrue(verify(removed, '原始账号', self.auth['password']))


class ConfigPreservationTests(unittest.TestCase):
    def test_failed_atomic_replace_keeps_complete_previous_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            original = {'auth': {'users': 'old', 'password': 'old-pass'}, 'baidu': {'tasks': [{'task_uid': 'keep'}]}}
            atomic_write_config(original, path)
            previous = path.read_bytes()
            with patch('config_persistence.os.replace', side_effect=OSError('simulated disk error')):
                with self.assertRaises(OSError): atomic_write_config({'changed': True}, path)
            self.assertEqual(path.read_bytes(), previous)
            self.assertEqual(list(Path(tmp).glob('*.tmp')), [])

    def test_bootstrap_never_reinitializes_existing_credentials_or_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'config').mkdir()
            config = {'auth': {'users': 'old-owner', 'password': 'keep-password', 'login_accounts': []},
                      'baidu': {'users': {'my-pan': {'cookies': 'fixture-only'}}, 'tasks': [{'task_uid': 'keep', 'name': '保留任务'}]}}
            path = root/'config/config.json'; path.write_text(json.dumps(config), encoding='utf8')
            before = path.read_bytes()
            with patch.dict(os.environ, {'ADMIN_USERNAME': 'must-not-replace', 'ADMIN_PASSWORD': 'must-not-replace'}): initialize(root)
            self.assertEqual(path.read_bytes(), before)

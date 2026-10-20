"""CI-only legacy data: no cloud account credentials or real media files."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import enum
import pickle
import types
import hashlib

from film_index.bootstrap import prepare
from film_index.subscriptions.auth_accounts import add_account
from film_index.subscriptions.task_history import TaskHistory

os.environ['ADMIN_USERNAME'] = 'existing-owner'
os.environ['ADMIN_PASSWORD'] = 'ci-existing-password'
root = prepare(sys.argv[1])
value = json.loads((root / 'config/config.json').read_text(encoding='utf8'))
value['auth'] = add_account(value['auth'], 'existing-member', 'ci-member-password')
value['tmdb'] = {'default_root': '/001', 'fixture_marker': 'preserve-tmdb'}
value['baidu']['tasks'] = [{'order': 1, 'name': 'existing-task', 'task_uid': 'existing-task-uid',
                          'url': 'https://pan.baidu.com/s/fixture-only', 'save_dir': '/001/fixture',
                          'cron': '0 0 1 1 *'}]
(root / 'config/config.json').write_text(json.dumps(value), encoding='utf8')
history = TaskHistory('existing-task-uid', value['baidu']['tasks'][0]['url'])
history.remember({'fs_id': 'original-file-id', 'size': 1234, 'md5': 'fixture-md5'}, '/001/already-moved-away.mp4')
import film_index
template = Path(film_index.__file__).parent / 'media/config/config.yaml'
shutil.copyfile(template, root / 'media/config.yaml')
from ruamel.yaml import YAML
yaml = YAML()
media_config = yaml.load((root / 'media/config.yaml').read_text(encoding='utf8'))
media_config['app']['rmt_tmdbkey'] = 'ci-media-key-preserved'
with (root / 'media/config.yaml').open('w', encoding='utf8') as handle:
    yaml.dump(media_config, handle)
# Old pickle records refer to the original module name, not the new application package.
legacy_modules = {name: types.ModuleType(name) for name in ('app', 'app.utils', 'app.utils.types')}
sys.modules.update(legacy_modules)
legacy_type = enum.Enum('MediaType', {'TV':'电视剧'}, module='app.utils.types')
legacy_modules['app.utils.types'].MediaType = legacy_type
with (root / 'media/tmdb.dat').open('wb') as handle:
    pickle.dump({'legacy-cache-key':{'id':123,'type':legacy_type.TV,'title':'existing-cache-title','year':'2024'}}, handle)
for name in legacy_modules:
    del sys.modules[name]
(root / 'config/.ci-cache-hash').write_text(hashlib.sha256((root / 'media/tmdb.dat').read_bytes()).hexdigest())
# Emulate an existing database with old history column names. New schema must be additive.
with sqlite3.connect(root / 'media/user.db') as db:
    db.execute('CREATE TABLE TRANSFER_HISTORY (ID INTEGER PRIMARY KEY, TITLE TEXT, TYPE TEXT, YEAR TEXT, MODE TEXT, FILE_PATH TEXT, FILE_NAME TEXT, SE TEXT)')
    db.execute("INSERT INTO TRANSFER_HISTORY VALUES (1,'existing-media-history','电视剧','2024','copy','/media/source','existing.mp4','S02E03')")
    db.execute('CREATE TABLE LEGACY_KEEP (VALUE TEXT)')
    db.execute("INSERT INTO LEGACY_KEEP VALUES ('original-user-data')")
print('Existing accounts, task memory and old media database prepared')


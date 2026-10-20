import json
from pathlib import Path
import sqlite3
import sys
from film_index.subscriptions.task_history import TaskHistory
from film_index.bootstrap import prepare

root = prepare(sys.argv[1])
value = json.loads((root / 'config/config.json').read_text(encoding='utf8'))
assert value['auth']['users'] == 'existing-owner'
assert value['auth']['password'] == 'ci-existing-password'
assert value['baidu']['tasks'][0]['task_uid'] == 'existing-task-uid'
assert value['tmdb']['fixture_marker'] == 'preserve-tmdb'
memory = TaskHistory('existing-task-uid', value['baidu']['tasks'][0]['url'])
assert memory.contains({'fs_id': 'moved-renamed-source-id', 'size': 1234, 'md5': 'fixture-md5'})
with sqlite3.connect(root / 'media/user.db') as db:
    assert db.execute('SELECT VALUE FROM LEGACY_KEEP').fetchone()[0] == 'original-user-data'
    row = db.execute('SELECT TITLE,FILE_PATH,SOURCE_PATH,FILE_NAME,SOURCE_FILENAME,SE,SEASON_EPISODE FROM TRANSFER_HISTORY WHERE ID=1').fetchone()
    assert row == ('existing-media-history','/media/source','/media/source','existing.mp4','existing.mp4','S02E03','S02E03'), row
    assert db.execute("SELECT COUNT(*) FROM CONFIG_SYNC_PATHS WHERE SOURCE='/media/source'").fetchone()[0] == 1
assert list((root / 'backups').glob('*/config/config.json'))
print('PASS: original credentials, task UID, transfer memory, media history and sync configuration preserved')


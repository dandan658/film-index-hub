from contextlib import closing
"""Portable configuration backups; restoration runs before any worker starts."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile
import zipfile

MAX_ARCHIVE = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024

def export_backup(root):
    root = Path(root)
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copytree(root / 'config', stage / 'config', symlinks=False)
        (stage / 'media').mkdir()
        for source in (root / 'media').iterdir():
            if source.is_symlink() or not source.is_file():
                continue
            target = stage / 'media' / source.name
            if source.suffix == '.db':
                with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as db:
                    with closing(sqlite3.connect(target)) as dest:
                        db.backup(dest)
            elif source.name == 'config.yaml' or source.suffix in ('.json', '.pkl', '.pickle', '.dat'):
                shutil.copy2(source, target)
        files = sorted(p for p in stage.rglob('*') if p.is_file())
        manifest = {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            for source in files:
                archive.write(source, source.relative_to(stage).as_posix())
            archive.writestr('film-index-backup.json', json.dumps({'format': 1, 'files': manifest}))
        output.seek(0)
        return output

def validate_backup(payload):
    if len(payload) > MAX_ARCHIVE:
        raise ValueError('备份文件不能超过 64 MB')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries = archive.infolist()
        if len(entries) > 10000 or sum(x.file_size for x in entries) > MAX_EXPANDED:
            raise ValueError('备份展开大小或文件数量超限')
        names = [x.filename for x in entries]
        if len(set(names)) != len(names):
            raise ValueError('备份含重复文件')
        meta = json.loads(archive.read('film-index-backup.json'))
        if meta.get('format') != 1 or not isinstance(meta.get('files'), dict):
            raise ValueError('不是 Film Index 完整备份')
        if set(names) != set(meta['files']) | {'film-index-backup.json'}:
            raise ValueError('备份清单不匹配')
        for name, digest in meta['files'].items():
            path = PurePosixPath(name)
            if '\\' in name or path.is_absolute() or '..' in path.parts or len(path.parts) < 2 or path.parts[0] not in ('config', 'media') or ':' in name:
                raise ValueError('备份包含非法路径')
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError('备份校验失败')
        config = json.loads(archive.read('config/config.json'))
        if not isinstance(config, dict) or not isinstance(config.get('auth'), dict):
            raise ValueError('备份缺少账号配置')
        if 'media/config.yaml' in names:
            from ruamel.yaml import YAML
            media = YAML(typ='safe').load(archive.read('media/config.yaml'))
            if not isinstance(media, dict) or not isinstance(media.get('app'), dict):
                raise ValueError('媒体配置无效')
        with tempfile.TemporaryDirectory() as temp:
            for name in meta['files']:
                if name.endswith('.db'):
                    dbfile = Path(temp) / 'validate.db'
                    dbfile.write_bytes(archive.read(name))
                    with closing(sqlite3.connect(dbfile)) as db:
                        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                            raise ValueError('备份数据库损坏')
        return meta

def restore_pending(root):
    root = Path(root)
    pending = root / '.restore-pending.zip'
    if not pending.exists():
        return
    payload = pending.read_bytes()
    meta = validate_backup(payload)
    # Keep the previous state before replacing anything; never restore a live DB.
    from datetime import datetime
    backup = root / 'backups' / ('before-restore-' + datetime.now().strftime('%Y%m%d-%H%M%S%f') + '.zip')
    backup.parent.mkdir(exist_ok=True)
    backup.write_bytes(export_backup(root).getvalue())
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in meta['files']:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink() or any(parent.is_symlink() for parent in target.parents if parent != root and root in parent.parents):
                raise ValueError('恢复目标含符号链接')
            # Clear stale SQLite sidecars before starting database connections.
            if target.suffix == '.db':
                for suffix in ('-wal', '-shm'):
                    target.with_name(target.name + suffix).unlink(missing_ok=True)
            temporary = target.with_name(target.name + '.restore-tmp')
            temporary.write_bytes(archive.read(name))
            temporary.chmod(0o600)
            os.replace(temporary, target)
    pending.unlink()

def install(app, subscriptions, root):
    from flask import request, send_file
    @app.route('/api/system/backup', methods=['GET'])
    @subscriptions.login_required
    def download():
        response = send_file(export_backup(root), as_attachment=True, download_name='Film-Index-backup.zip', mimetype='application/zip')
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.route('/api/system/restore', methods=['POST'])
    @subscriptions.login_required
    def restore():
        if request.headers.get('X-Film-Index') != 'backup':
            return {'success': False, 'message': '请求来源无效'}, 400
        file = request.files.get('file')
        if not file:
            return {'success': False, 'message': '请选择备份文件'}, 400
        payload = file.read(MAX_ARCHIVE + 1)
        try:
            validate_backup(payload)
        except (ValueError, KeyError, zipfile.BadZipFile, UnicodeError, sqlite3.DatabaseError):
            return {'success': False, 'message': '备份无效或校验失败，未修改当前数据'}, 400
        pending = Path(root) / '.restore-pending.zip'
        temp = pending.with_suffix('.tmp')
        temp.write_bytes(payload)
        temp.chmod(0o600)
        os.replace(temp, pending)
        return {'success': True, 'message': '备份校验通过，请重启容器完成恢复；恢复前会自动保存当前数据。'}

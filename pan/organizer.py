"""Lossless per-file transfers: plan first, stage individually, never overwrite."""
import hashlib
import json
import os
from pathlib import Path
import posixpath
import time
import uuid

from media_rules import destination_name
from task_history import TaskHistory


def field(item, name, default=None):
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def same_file(entry, source):
    if int(field(entry, 'size', -1)) != int(source.get('size', -2)):
        return False
    left, right = field(entry, 'md5'), source.get('md5')
    return not (left and right) or left.lower() == right.lower()


def scan(storage, client, root):
    result = {}
    def visit(directory):
        # Fail closed on listing errors: treating errors as an empty directory
        # would duplicate or overwrite files on the next transfer.
        for entry in storage._list_dir_entries_with_fallback(directory, client=client):
            path = storage._get_list_entry_path(entry)
            if not path:
                continue
            if storage._is_list_entry_dir(entry):
                if not posixpath.basename(path).startswith('.baidu-autosave-'):
                    visit(path)
            else:
                result[path] = entry
    visit(root)
    return result


def transfer_organized(storage, client, files, roots, share_url, save_dir, task, progress=None, selected=None):
    report = progress or (lambda *_: None)
    root = posixpath.normpath('/' + (save_dir or '').lstrip('/'))
    if root == '/' and (task.get('flatten') or task.get('auto_rename')):
        raise ValueError('整理模式需要专用保存目录，不能使用网盘根目录')
    identity = str(task.get('task_uid') or task.get('order') or share_url)
    owner = storage.config['baidu'].get('current_user', '')
    task_key = hashlib.sha256(f'{owner}:{identity}:{share_url}:{root}'.encode()).hexdigest()[:24]
    state_dir = Path('config/organized')
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / f'{task_key}.json'
    records = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    history = TaskHistory(identity, share_url)
    history.register_organized(state_path)
    def persist():
        if history.deleted: return
        temporary = state_path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        try:
            with temporary.open('w', encoding='utf-8') as handle:
                json.dump(records, handle, ensure_ascii=False, indent=2)
            os.replace(temporary, state_path)
        finally:
            if temporary.exists():
                temporary.unlink()
    single_folder = len(roots) == 1 and bool(field(roots[0], 'is_dir', False))
    planned = []
    seen_ids = set()
    warnings = []
    for source in sorted(files, key=lambda f: (str(f['path']), str(f['fs_id']))):
        source_id = str(source['fs_id'])
        if source_id in seen_ids:
            continue
        seen_ids.add(source_id)
        relative = source['path'].lstrip('/')
        if single_folder and '/' in relative:
            relative = relative.split('/', 1)[1]
        if selected is not None and relative not in selected and source['path'] not in selected:
            continue
        if any(part in ('.', '..', '') for part in relative.split('/')):
            raise ValueError(f'分享文件路径不安全：{relative}')
        previous = records.get(source_id)
        if previous and same_file(previous, source) and not history.contains(source):
            history.remember(source, previous['path'])
        if history.contains(source):
            continue
        included, destination, warning = destination_name(relative, task, source_path=source['path'])
        if warning:
            warnings.append(warning)
            report('warning', warning)
        if not included:
            continue
        suffix = hashlib.sha256(source_id.encode()).hexdigest()[:10]
        planned.append({'source': source, 'id': source_id, 'relative': relative,
                        'desired': posixpath.join(root, destination), 'suffix': suffix})
    if not planned:
        if warnings:
            return {'success': False, 'error': '\n'.join(warnings), 'transferred_files': []}
        report('info', '已按任务转存记忆跳过历史文件，没有新文件需要转存')
        return {'success': True, 'skipped': True, 'transferred_files': [], 'message': '没有新文件需要转存（已记忆的文件即使被移动也不重复转存）'}
    if not storage._ensure_dir_tree_exists(root, client=client):
        raise ValueError(f'无法创建目标目录：{root}')
    existing = scan(storage, client, root)
    # Resolve collisions deterministically before any transfer takes place.
    reserved = {}
    for item in planned:
        original = posixpath.join(root, item['relative'])
        record = records.get(item['id'], {})
        old_path = record.get('path')
        if old_path and (old_path not in existing or not same_file(existing[old_path], item['source'])):
            old_path = None
        if not old_path and original in existing and same_file(existing[original], item['source']):
            old_path = original
        desired = item['desired']
        prior_target = record.get('path')
        stem, ext = posixpath.splitext(desired)
        # Retain an already assigned collision suffix across subscription runs.
        if prior_target == f'{stem} [{item["suffix"]}]{ext}' and prior_target == old_path:
            desired = prior_target
        counter = 0
        while desired in reserved or (desired in existing and desired != old_path):
            counter += 1
            extra = '' if counter == 1 else f'-{counter}'
            desired = f'{stem} [{item["suffix"]}{extra}]{ext}'
        reserved[desired] = item['id']
        item.update(destination=desired, old_path=old_path)
    completed, failures = [], []
    staging_root = posixpath.join(root, f'.baidu-autosave-{task_key}')
    for item in planned:
        if history.deleted:
            return {'success': False, 'error': '任务已删除，已停止后续转存并清除记忆', 'transferred_files': completed}
        source, destination, old_path = item['source'], item['destination'], item['old_path']
        if old_path == destination:
            history.remember(source, destination)
            continue
        try:
            parent = posixpath.dirname(destination)
            if not storage._ensure_dir_tree_exists(parent, client=client):
                raise ValueError(f'无法创建目录：{parent}')
            current_targets = {storage._get_list_entry_path(e) for e in storage._list_dir_entries_with_fallback(parent, client=client)}
            if destination in current_targets:
                raise ValueError(f'目标位置出现了新文件，已停止以避免覆盖：{destination}')
            if old_path:
                report('info', f'整理已有文件：{old_path} → {destination}')
                client.rename(old_path, destination)
                existing.pop(old_path, None)
            else:
                staging = posixpath.join(staging_root, item['suffix'])
                if not storage._ensure_dir_tree_exists(staging, client=client):
                    raise ValueError(f'无法创建临时目录：{staging}')
                staged_path = posixpath.join(staging, posixpath.basename(source['path']))
                staged = {storage._get_list_entry_path(e): e for e in storage._list_dir_entries_with_fallback(staging, client=client)}
                if staged_path in staged:
                    if not same_file(staged[staged_path], source):
                        raise ValueError(f'暂存文件冲突，已保留待检查：{staged_path}')
                else:
                    report('info', f'转存并整理：{source["path"]} → {destination}')
                    info = roots[0]
                    storage._transfer_shared_paths_with_retry(
                        remotedir=staging, fs_ids=[source['fs_id']], uk=int(field(info, 'uk')),
                        share_id=int(field(info, 'share_id')), bdstoken=str(field(info, 'bdstoken')),
                        shared_url=share_url, client=client)
                client.rename(staged_path, destination)
                # Delete only our own staging directory, after confirming empty.
                if not storage._list_dir_entries_with_fallback(staging, client=client):
                    try:
                        client.remove(staging)
                    except Exception as error:
                        report('warning', f'空临时目录清理失败：{error}')
            existing[destination] = source
            records[item['id']] = {'path': destination, 'size': source.get('size'), 'md5': source.get('md5')}
            persist()
            history.remember(source, destination)
            completed.append(posixpath.relpath(destination, root))
            report('success', f'整理成功：{destination}')
            time.sleep(storage.config.get('file_operations', {}).get('rename_delay_seconds', 0.5))
        except Exception as error:
            message = f'{source["path"]}：{error}（暂存或原文件已保留，下次可重试）'
            failures.append(message)
            report('error', message)
    if failures:
        return {'success': False, 'error': '\n'.join(failures), 'transferred_files': completed, 'warnings': warnings}
    if warnings:
        return {'success': False, 'error': '\n'.join(warnings), 'transferred_files': completed, 'warnings': warnings}
    return {'success': True, 'skipped': not completed, 'transferred_files': completed,
            'message': f'已整理 {len(completed)} 个文件' if completed else '没有新文件需要转存'}

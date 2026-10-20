"""Cheap, bounded directory listing cache for network-backed path pickers."""
import html
import os
import time
from collections import OrderedDict
from threading import Lock
from urllib.parse import unquote

_cache = OrderedDict()
_lock = Lock()
TTL = 8
MAX_CACHE = 128


def directory_html(path, folders_only=False, show_parent=False, refresh=False):
    path = os.path.normpath(unquote(path or os.path.abspath(os.sep)))
    key = (path, folders_only, show_parent)
    now = time.monotonic()
    with _lock:
        cached = _cache.get(key)
        if cached and not refresh and now - cached[0] < TTL:
            _cache.move_to_end(key)
            return cached[1]
    def scan(folder):
        with os.scandir(folder) as entries:
            return [(e.name, e.path, e.is_dir()) for e in entries]
    try:
        try:
            entries = scan(path)
        except NotADirectoryError:
            path = os.path.dirname(path)
            entries = scan(path)
        rows = ['<ul class="jqueryFileTree" style="display: none;">']
        parent = os.path.dirname(path)
        if show_parent and parent != path:
            rows.append('<li class="directory collapsed"><a rel="%s/">..</a></li>' % html.escape(parent.replace('\\', '/').rstrip('/'), quote=True))
        for name, full, is_dir in sorted(entries, key=lambda x: (not x[2], x[0].casefold())):
            if folders_only and not is_dir:
                continue
            rel = html.escape(full.replace('\\', '/') + ('/' if is_dir else ''), quote=True)
            label = html.escape(name, quote=True)
            kind = 'directory collapsed' if is_dir else 'file'
            rows.append('<li class="%s"><a rel="%s">%s</a></li>' % (kind, rel, label))
        rows.append('</ul>')
        result = ''.join(rows)
    except OSError:
        return '<ul class="jqueryFileTree"><li class="fti-path-error">目录不可读取，请检查路径和挂载权限，或手动输入路径。</li></ul>'
    with _lock:
        _cache[key] = (time.monotonic(), result)
        _cache.move_to_end(key)
        while len(_cache) > MAX_CACHE:
            _cache.popitem(last=False)
    return result

"""Pure naming rules shared by task validation and the transfer planner."""
import posixpath
import re
import unicodedata

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.m4v', '.ts', '.m2ts', '.wmv', '.flv', '.webm'}
SUBTITLE_EXTENSIONS = {'.srt', '.ass', '.ssa', '.vtt', '.sub'}


def safe_name(value):
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', value).strip(' .')
    if not value or value in ('.', '..'):
        raise ValueError('文件名称不能为空或包含路径跳转')
    return value


def replacement(value):
    # Accept both the UI's $1 notation and Python's \1 / \g<1> notation.
    return re.sub(r'\$(\d+)', lambda m: '\\g<' + m[1] + '>', value)


def task_options(data, previous=None):
    previous = previous or {}
    result = {key: data.get(key, previous.get(key, default)) for key, default in (
        ('media_type', 'other'), ('flatten', False), ('auto_rename', False), ('season', 1), ('season_folders', []), ('force_first_season', False), ('tmdb', None))}
    if result['media_type'] not in ('other', 'movie', 'tv'):
        raise ValueError('资源类型必须为普通文件、电影或电视剧')
    for key in ('flatten', 'auto_rename', 'force_first_season'):
        if not isinstance(result[key], bool):
            raise ValueError(f'{key} 必须为布尔值')
    if isinstance(result['season'], bool) or not isinstance(result['season'], int) or not 1 <= result['season'] <= 999:
        raise ValueError('季数必须是 1 至 999 的整数')
    if result['auto_rename']:
        if result['media_type'] == 'other' or not data.get('name', previous.get('name', '')).strip():
            raise ValueError('自动命名需要选择电影或电视剧并填写自定义任务名称')
    if not isinstance(result['season_folders'], list) or len(result['season_folders']) > 100:
        raise ValueError('分季目录规则必须为列表，最多 100 条')
    rules, seen = [], set()
    for rule in result['season_folders']:
        if not isinstance(rule, dict):
            raise ValueError('分季目录规则格式不正确')
        source = str(rule.get('source', '')).strip().strip('/')
        season = rule.get('season', 1)
        if not source or '\\' in source or any(p in ('', '.', '..') for p in source.split('/')) or source in seen:
            raise ValueError('源子目录必须填写不重复的相对路径，不能包含路径跳转')
        if isinstance(season, bool) or not isinstance(season, int) or not 1 <= season <= 999:
            raise ValueError('每个子目录的季数必须为 1 至 999 的整数')
        name = str(rule.get('name', '')).strip() or f'Season {season:02d}'
        if safe_name(name) != name:
            raise ValueError('新季目录名不能包含斜杠、特殊字符或路径跳转')
        rules.append({'source': source, 'season': season, 'name': name})
        seen.add(source)
    result['season_folders'] = rules
    metadata = result['tmdb']
    if metadata is not None:
        if (not isinstance(metadata, dict) or isinstance(metadata.get('id'), bool)
                or not isinstance(metadata.get('id'), int) or metadata['id'] <= 0
                or metadata.get('media_type') != result['media_type']
                or result['media_type'] not in ('tv', 'movie')
                or not isinstance(metadata.get('title'), str) or not metadata['title'].strip()):
            raise ValueError('TMDB 影片资料格式不正确或与资源类型不符')
        result['tmdb'] = {'id': metadata['id'], 'media_type': metadata['media_type'],
                          'title': safe_name(metadata['title'][:200]), 'year': str(metadata.get('year', ''))[:4]}
    if rules and result['media_type'] != 'tv':
        raise ValueError('分季目录规则只适用于电视剧')
    pattern = data.get('regex_pattern', previous.get('regex_pattern', '')) or ''
    replace = data.get('regex_replace', previous.get('regex_replace', '')) or ''
    if pattern:
        compiled = re.compile(pattern)
        if replace:
            compiled.sub(replacement(replace), '')
    return result


def regex_filename(path, task):
    parent, filename = posixpath.split(path)
    pattern, replace = task.get('regex_pattern', ''), task.get('regex_replace', '')
    if pattern and not re.search(pattern, filename):
        return False, path
    if replace:
        renamed = re.sub(pattern, replacement(replace), filename) if pattern else replace
        # Literal names without an extension retain the original extension.
        if not posixpath.splitext(renamed)[1]:
            renamed += posixpath.splitext(filename)[1]
        if '/' in renamed or '\\' in renamed or renamed in ('', '.', '..'):
            raise ValueError('重命名结果必须是文件名，不能包含目录')
        return True, posixpath.join(parent, safe_name(renamed))
    return True, path


def season_number(value):
    """Parse a season number without confusing years or episode-range folders."""
    value = unicodedata.normalize('NFKC', value).strip()
    if value.isdecimal():
        number = int(value)
    else:
        digits = dict(zip('零〇一二两三四五六七八九', (0, 0, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9)))
        if not value or any(char not in digits and char not in '十百' for char in value):
            return None
        if not any(char in '十百' for char in value):
            number = int(''.join(str(digits[char]) for char in value))
        else:
            number, current, previous_unit = 0, 0, 1000
            for char in value:
                if char in digits:
                    current = digits[char]
                else:
                    unit = 10 if char == '十' else 100
                    if unit >= previous_unit:
                        return None
                    number += (current or 1) * unit
                    current, previous_unit = 0, unit
            number += current
    return number if 1 <= number <= 999 else None


def season_in_folder(folder):
    folder = unicodedata.normalize('NFKC', folder)
    # A range describes a collection, not a single season.
    if re.search(r'(?i)(?:season[ ._-]*|(?<![a-z0-9])s)\d{1,3}\s*[-~至到]\s*(?:season[ ._-]*|s)?\d', folder):
        return None
    values = re.findall(r'第\s*([0-9零〇一二两三四五六七八九十百]{1,7})\s*季', folder)
    plain = re.fullmatch(r'\s*([0-9零〇一二两三四五六七八九十百]{1,7})\s*季\s*', folder)
    if plain:
        values.append(plain[1])
    values += re.findall(r'(?i)(?:(?<![a-z])season[ ._-]*|(?<![a-z0-9])s)(\d{1,3})(?!\d|[eE]\d)', folder)
    numbers = {season_number(value) for value in values}
    numbers.discard(None)
    return numbers.pop() if len(numbers) == 1 else None


def directory_season(path):
    """The nearest season directory wins over a season label on an outer collection."""
    parts = posixpath.dirname(path).split('/')
    for index in range(len(parts) - 1, -1, -1):
        number = season_in_folder(parts[index])
        if number is not None:
            return index, number
    return None


def episode(path, default_season=1):
    stem = posixpath.splitext(posixpath.basename(path))[0]
    parent = directory_season(path)
    season = parent[1] if parent else (season_in_folder(stem) or default_season)
    match = re.search(r'(?i)(?<![a-z0-9])S(\d{1,3})[ ._-]*E(\d{1,4})(?!\d)', stem)
    if match:
        return season if parent else int(match[1]), int(match[2])
    for pattern in (r'第\s*(\d{1,4})\s*[集话話]', r'(?i)(?<![a-z0-9])(?:EP?|episode)[ ._-]*(\d{1,4})(?!\d)', r'^\s*(\d{1,4})(?=$|[ ._\-])'):
        match = re.search(pattern, stem)
        if match:
            number = int(match[1])
            if number in (360, 480, 576, 720, 1080, 2160, 4320) or 1900 <= number <= 2099:
                continue
            return season, number
    return None


def destination_name(path, task, source_path=None):
    """Return (included, relative destination, warning). No network side effects."""
    included, renamed = regex_filename(path, task)
    if not included:
        return False, path, ''
    season = task.get('season', 1)
    mapped_parent = posixpath.dirname(path)
    matched_rule = None
    for rule in sorted(task.get('season_folders', []), key=lambda r: len(r['source']), reverse=True):
        prefix = rule['source'].strip('/')
        if path.startswith(prefix + '/'):
            season = rule['season']
            mapped_parent = posixpath.dirname(posixpath.join(rule.get('name') or f'Season {season:02d}', path[len(prefix) + 1:]))
            matched_rule = rule
            break
    detected_directory = directory_season(source_path or path) if task.get('media_type') == 'tv' else None
    if detected_directory and not matched_rule:
        season = detected_directory[1]
        relative_directory = directory_season(path)
        if relative_directory:
            parts = mapped_parent.split('/')
            parts[relative_directory[0]] = f'Season {season:02d}'
            mapped_parent = '/'.join(parts)
        else:
            # The share root may have been stripped for destination layout;
            # retain its season even when only quality subfolders remain.
            mapped_parent = posixpath.join(f'Season {season:02d}', mapped_parent)
    force_first = task.get('media_type') == 'tv' and task.get('force_first_season', False)
    if force_first:
        season = 1
        # Override season labels while retaining non-season subdirectory structure.
        parts = mapped_parent.split('/')
        parts = [part for part in parts if season_in_folder(part) is None]
        mapped_parent = posixpath.join('Season 01', *[part for part in parts if part])
        if matched_rule:
            original = posixpath.dirname(path[len(matched_rule['source'].strip('/')) + 1:])
            mapped_parent = posixpath.join('Season 01', *[part for part in original.split('/') if part and season_in_folder(part) is None])
    renamed = posixpath.join(mapped_parent, posixpath.basename(renamed))
    if task.get('auto_rename'):
        ext = posixpath.splitext(path)[1].lower()
        if ext not in VIDEO_EXTENSIONS | SUBTITLE_EXTENSIONS:
            return False, path, ''
        title = safe_name(task['name'])
        if task['media_type'] == 'tv':
            parsed = episode(path, season)
            if parsed is None:
                return False, path, f'无法识别集数，跳过并保留源文件：{path}'
            detected_season, number = parsed
            # An explicit per-directory rule takes precedence over filename tags.
            season = season if force_first or matched_rule or detected_directory else detected_season
            filename = f'{title} - S{season:02d}E{number:02d}'
        else:
            filename = title
        # Preserve subtitle language / forced markers so sidecars stay distinct.
        if ext in SUBTITLE_EXTENSIONS:
            suffix = re.search(r'(?i)[. _-](zh-cn|zh-tw|chs|cht|zh|en|eng|forced|简体|繁体|双语)$', posixpath.splitext(path)[0])
            if suffix:
                filename += '.' + suffix[1].lower()
        if not mapped_parent and task['media_type'] == 'tv' and not task.get('flatten'):
            mapped_parent = f'Season {season:02d}'
        renamed = posixpath.join(mapped_parent, filename + ext)
    return True, posixpath.basename(renamed) if task.get('flatten') else renamed, ''

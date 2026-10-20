"""Additional backend logins coexist with the untouched legacy primary login."""
import copy
import hmac
import re
import uuid
from werkzeug.security import check_password_hash, generate_password_hash


def account(auth, username):
    if not isinstance(username, str):
        return None
    if username == auth.get('users'):
        return {'username': username, 'is_primary': True,
                'session_version': auth.get('session_version', 'legacy')}
    for entry in auth.get('login_accounts', []):
        if entry.get('username') == username:
            return dict(entry, is_primary=False)
    return None


def verify(auth, username, password):
    if not isinstance(password, str) or len(password) > 1024:
        return False
    entry = account(auth, username)
    if not entry:
        return False
    if entry['is_primary']:
        legacy_password = auth.get('password')
        return isinstance(legacy_password, str) and hmac.compare_digest(password.encode(), legacy_password.encode())
    try:
        return check_password_hash(entry.get('password_hash', ''), password)
    except (ValueError, TypeError):
        return False


def public_accounts(auth, current_username):
    names = [auth.get('users')] + [entry.get('username') for entry in auth.get('login_accounts', [])]
    return [{'username': name, 'is_primary': name == auth.get('users'), 'is_current': name == current_username}
            for name in names if name]


def validate_password(password):
    if not isinstance(password, str) or not 6 <= len(password) <= 1024:
        raise ValueError('密码需要 6 至 1024 个字符')


def add_account(auth, username, password):
    if not isinstance(username, str):
        raise ValueError('请填写登录账号')
    username = username.strip()
    if not re.fullmatch(r'[\w.@-]{1,64}', username):
        raise ValueError('账号限 1 至 64 位字母、数字、中文、下划线、点、@ 或短横线')
    if any(entry['username'].casefold() == username.casefold() for entry in public_accounts(auth, '')):
        raise ValueError('登录账号已存在')
    validate_password(password)
    updated = copy.deepcopy(auth)
    updated.setdefault('login_accounts', []).append({
        'username': username, 'password_hash': generate_password_hash(password),
        'session_version': uuid.uuid4().hex,
    })
    return updated


def change_password(auth, username, password):
    validate_password(password)
    entry = account(auth, username)
    if not entry:
        raise ValueError('登录账号不存在')
    updated = copy.deepcopy(auth)
    version = uuid.uuid4().hex
    if entry['is_primary']:
        updated['password'] = password
        updated['session_version'] = version
    else:
        for target in updated.get('login_accounts', []):
            if target['username'] == username:
                target['password_hash'] = generate_password_hash(password)
                target['session_version'] = version
                break
    return updated


def remove_account(auth, username, current_username):
    entry = account(auth, username)
    if not entry:
        raise ValueError('登录账号不存在')
    if entry['is_primary']:
        raise ValueError('原始登录账号受保护，不能删除')
    if username == current_username:
        raise ValueError('不能删除当前正在登录的账号')
    updated = copy.deepcopy(auth)
    updated['login_accounts'] = [entry for entry in updated.get('login_accounts', []) if entry['username'] != username]
    return updated

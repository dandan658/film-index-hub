"""Real HTTP checks against one running service, with existing data mounted."""
import http.cookiejar
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'http://127.0.0.1:18520'
jar = http.cookiejar.LWPCookieJar('/tmp/film-index-cookies')
if Path(jar.filename).exists():
    jar.load(ignore_discard=True, ignore_expires=True)
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(path, data=None, anonymous=False, form=False, headers=None):
    headers = dict(headers or {})
    if data is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
        data = (urllib.parse.urlencode(data) if form else json.dumps(data)).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=headers)
    try:
        with (urllib.request.build_opener() if anonymous else client).open(req, timeout=20) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def check_pages():
    for page in ('mediafile','unidentification','history','tmdbcache','service','basic','library','directorysync','notification','customwords','mediaserver','subtitle'):
        status, body = call('/media-engine/' + page)
        assert status == 200, (page, status, body[:400])
        if page == 'history':
            assert b'existing-media-history' in body
    main = json.loads(call('/api/system/architecture')[1])
    media = json.loads(call('/media-engine/profile-info')[1])
    assert main['process_id'] == media['process_id'] == 1
    assert main['application_id'] == media['application_id']
    assert main['gateway'] is False
    assert call('/media-engine/users')[0] == 403
    for page in ('downloader','indexer','filterrule','douban','upload'):
        assert call('/media-engine/' + page)[0] == 404
    status, body = call('/media-engine/?next=mediafile')
    assert status == 200 and b'fti-hub-embedded' in body
    assert call('/project-source.zip')[0] == 200


if '--after-restart' not in sys.argv:
    assert call('/media-engine/mediafile', anonymous=True)[0] == 401
    assert call('/media-engine/mediafile', anonymous=True, headers={'X-Hub-Token':'fake','X-Hub-User':'YWRtaW4='})[0] == 401
    status, body = call('/api/auth/login', {'username':'existing-owner','password':'ci-existing-password'})
    assert status == 200 and json.loads(body)['success'], body
    check_pages()
    tasks = json.loads(call('/api/tasks')[1])['tasks']
    assert tasks[0]['task_uid'] == 'existing-task-uid'
    status, body = call('/media-engine/do', {'cmd':'add_or_edit_sync_path', 'data':json.dumps({'from':'/media/source','to':'/media/destination','syncmod':'copy','rename':False,'enabled':False})}, form=True)
    assert status == 200 and json.loads(body)['code'] == 0, body
    jar.save(ignore_discard=True, ignore_expires=True)
    print('PASS: existing primary login opens subscriptions and media in the same Flask object and PID 1')
else:
    assert json.loads(call('/api/auth/check')[1])['success']
    check_pages()
    status, body = call('/api/auth/login', {'username':'existing-member','password':'ci-member-password'})
    assert status == 200 and json.loads(body)['success'], body
    check_pages()
    call('/api/auth/logout', {})
    assert call('/media-engine/mediafile')[0] == 401
    print('PASS: session and additional original account survive restart; logout revokes media access')


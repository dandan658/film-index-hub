"""Real HTTP tests against the complete three-service stack; CI-only accounts."""
import http.cookiejar
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
BASE='http://127.0.0.1:18520'
COOKIE=Path('/tmp/film-hub-cookies.json')
jar=http.cookiejar.LWPCookieJar(str(COOKIE))
if COOKIE.exists():jar.load(ignore_discard=True,ignore_expires=True)
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def request(path,data=None,method=None,authenticated=True,headers=None):
    values=headers or {}
    if data is not None:values['Content-Type']='application/json';data=json.dumps(data).encode()
    req=urllib.request.Request(BASE+path,data=data,headers=values,method=method)
    try:
        with (client if authenticated else urllib.request.build_opener()).open(req,timeout=40) as reply:return reply.status,reply.read().decode('utf8',errors='replace'),dict(reply.headers)
    except urllib.error.HTTPError as error:return error.code,error.read().decode('utf8',errors='replace'),dict(error.headers)
def check_media():
    for page in ['mediafile','unidentification','history','tmdbcache','service','basic','library','directorysync','notification','customwords','mediaserver','subtitle']:
        status,body,_=request('/media-engine/'+page);assert status==200,(page,status,body[:300]);assert 'name="username"' not in body
    assert request('/media-engine/users')[0]==403
    for page in ['downloader','indexer','filterrule','douban','upload']:assert request('/media-engine/'+page)[0]==404
    status,body,_=request('/media-engine/?next=mediafile');assert status==200 and 'fti-hub-embedded' in body
    assert request('/internal/hub-auth')[0]==404
    assert request('/project-source.zip')[0]==200
if '--after-restart' in sys.argv:
    status,body,_=request('/api/auth/check');assert status==200 and json.loads(body)['success'],body
    check_media()
    status,body,_=request('/api/auth/login',{'username':'ci-second-login','password':'ci-second-test-only'});assert json.loads(body)['success'],body
    check_media()
    request('/api/auth/logout',{})
    assert request('/media-engine/?next=mediafile')[0]==401
    print('PASS: original session survives restarts; additional original account works; logout revokes media access')
else:
    assert request('/media-engine/?next=mediafile',authenticated=False)[0]==401
    assert request('/media-engine/?next=mediafile',authenticated=False,headers={'X-Hub-Token':'fake','X-Hub-User':'YWRtaW4='})[0]==401
    status,body,_=request('/api/auth/login',{'username':'admin','password':'ci-smoke-test-only'});assert json.loads(body)['success'],body
    assert any(cookie.name=='film_hub_session' for cookie in jar)
    check_media()
    status,body,_=request('/api/auth/accounts',{'username':'ci-second-login','password':'ci-second-test-only','current_password':'ci-smoke-test-only'});assert json.loads(body)['success'],body
    jar.save(ignore_discard=True,ignore_expires=True)
    print('PASS: one Baidu login accesses every media page; forged headers blocked; source download works')

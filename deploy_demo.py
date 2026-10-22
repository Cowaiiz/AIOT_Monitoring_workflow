"""Deploy only the changed demo via the local Node-RED Admin API, with revision guard and backups."""
import json
import hashlib
import sys
from datetime import datetime
from pathlib import Path
from urllib import request,error

ROOT=Path(__file__).resolve().parent
TAB='giang_http_v1_20261022'
BASE='http://127.0.0.1:1880'

def http(path,body=None,headers=None):
    req=request.Request(BASE+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json','Node-RED-API-Version':'v2',**(headers or {})},method='GET' if body is None else 'POST')
    with request.urlopen(req,timeout=10) as r:
        raw=r.read()
        return json.loads(raw) if raw else None

def selected(node):return node.get('id')==TAB or node.get('z')==TAB

def main():
    from build_flow import build
    build()
    desired=json.loads((ROOT/'flow.json').read_text(encoding='utf-8'))
    current=http('/flows')
    if not isinstance(current,dict) or not current.get('rev'):raise RuntimeError('Expected Admin API v2 revision; no deployment attempted')
    before=current['flows'];others=[n for n in before if not selected(n)]
    ids={n['id'] for n in desired}
    if any(n['id'] in ids for n in others):raise RuntimeError('Node ID collision outside demo')
    routes={(n.get('method'),n.get('url')) for n in desired if n.get('type')=='http in'}
    if any(n.get('type')=='http in' and (n.get('method'),n.get('url')) in routes for n in others):raise RuntimeError('HTTP route collision outside demo')
    if len(routes)!=8:raise RuntimeError('Expected exactly 8 unique demo routes')
    backup=ROOT/'backups'/('deploy-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True)
    (backup/'all-flows-before.json').write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf-8')
    # Preserve runtime observations where available before RAM resets. Not a restore mechanism.
    for route in ['alerts','events','metrics']:
        try:state=http('/giang-aiot/v1/'+route)
        except error.HTTPError as e:
            if e.code!=404:raise
            state={'unavailable':404}
        (backup/(route+'-before.json')).write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    http('/flows',{'rev':current['rev'],'flows':others+desired},{'Node-RED-Deployment-Type':'flows'})
    after=http('/flows')['flows'];actual={n['id']:n for n in after if selected(n)}
    unchanged={n['id']:n for n in after if not selected(n)}=={n['id']:n for n in others}
    synced=len(actual)==len(desired) and all(all(actual.get(n['id'],{}).get(k)==v for k,v in n.items()) for n in desired)
    metrics=http('/giang-aiot/v1/metrics');alerts=http('/giang-aiot/v1/alerts')
    result={'mode':'real Node-RED Admin API deployment','unrelated_unchanged':unchanged,'source_matches_deployed':synced,'demo_objects':len(actual),'route_count':len(routes),'backup':str(backup),'config_version':metrics.get('config_version'),'alerts_after_deploy':alerts['total'],'flow_sha256':hashlib.sha256((ROOT/'flow.json').read_bytes()).hexdigest()}
    (ROOT/'results/deployment-v2.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2))
    if not unchanged or not synced:raise RuntimeError('Post-deploy verification failed; see backup and report. No automatic rollback of other flows.')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('Deployment not verified: '+repr(e),file=sys.stderr)
        raise SystemExit(1)

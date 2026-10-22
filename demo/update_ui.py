"""Update only the demo's HTML-serving function, without restarting Python."""
import copy
import json
from datetime import datetime
from urllib import request
from build_flow import build, ROOT, TAB

BASE='http://127.0.0.1:1880'
def http(path,body=None,extra=None):
    req=request.Request(BASE+path,data=None if body is None else json.dumps(body).encode(),
        headers={'Content-Type':'application/json','Node-RED-API-Version':'v2',**(extra or {})})
    with request.urlopen(req,timeout=20) as r:
        raw=r.read()
        return json.loads(raw) if raw else None

def main():
    desired=build()
    current=http('/flows')
    if not isinstance(current,dict) or not current.get('rev'):
        raise RuntimeError('Expected Node-RED Admin API v2 revision; nothing changed')
    by_id={n['id']:n for n in current['flows']}
    if 'pcb_store_request' not in by_id or by_id.get('pcb_dispatch',{}).get('z')!=TAB:
        raise RuntimeError('Expected persistent PCB4 v2 flow; nothing changed')
    # Require source and deployed functional definitions to match except the HTML dispatcher.
    for n in desired:
        if n['id']=='pcb_dispatch':continue
        live=by_id.get(n['id'],{})
        for key in ('type','z','func','initialize','url','method','wires'):
            if key in n and live.get(key)!=n[key]:
                raise RuntimeError(f'Flow drift at {n["id"]}.{key}; stopped without overwriting')
    backup=ROOT/'backups'/('ui-deploy-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True,exist_ok=False)
    (backup/'all-flows-before.json').write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf-8')
    before_alerts=http('/giang-pcb4/v1/alerts')
    (backup/'alerts-before.json').write_text(json.dumps(before_alerts,ensure_ascii=False,indent=2),encoding='utf-8')
    replacement=next(n['func'] for n in desired if n['id']=='pcb_dispatch')
    updated=copy.deepcopy(current['flows'])
    for n in updated:
        if n['id']=='pcb_dispatch':n['func']=replacement
    http('/flows',{'rev':current['rev'],'flows':updated},{'Node-RED-Deployment-Type':'nodes'})
    after=http('/flows')
    expected={n['id']:n for n in updated}
    actual={n['id']:n for n in after['flows']}
    if expected!=actual:
        raise RuntimeError('Post-deploy flow differs; see backup. No automatic rollback of unrelated edits.')
    after_alerts=http('/giang-pcb4/v1/alerts')
    health=http('/giang-pcb4/v1/health')
    before_ids={a['alert_id']:a for a in before_alerts['alerts']}
    after_ids={a['alert_id']:a for a in after_alerts['alerts']}
    preserved=all(after_ids.get(k)==v for k,v in before_ids.items())
    with request.urlopen(BASE+'/giang-pcb4/v1/demo',timeout=10) as response:
        html=response.read().decode('utf-8')
    report={'updated_node':'pcb_dispatch','other_nodes_unchanged':True,'alerts_preserved':preserved,
            'model_ready':health.get('ready') is True,'html_matches_source':html==(ROOT/'index.html').read_text(encoding='utf-8'),
            'backup':str(backup),'browser_interactions_tested':False}
    (ROOT/'ui-deployment.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    if not all(report[k] for k in ('alerts_preserved','model_ready','html_matches_source')):
        raise RuntimeError('UI deployed but verification incomplete; inspect ui-deployment.json')
    print('UI UPDATED. Reload http://localhost:1880/giang-pcb4/v1/demo\nModel service remains running.')

if __name__=='__main__':main()

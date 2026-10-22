"""One local command: load model, start service, deploy only own tab, verify HTTP."""
import base64
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import request, error
from build_flow import build, ROOT, TAB
from model_service import Predictor, create_server, RUN
from storage import Store, DB

def http(path, body=None, extra=None):
    req=request.Request('http://127.0.0.1:1880'+path,data=None if body is None else json.dumps(body).encode(),
        headers={'Content-Type':'application/json','Node-RED-API-Version':'v2',**(extra or {})})
    try:
        with request.urlopen(req,timeout=45) as response:
            raw=response.read()
            return response.status,json.loads(raw) if raw else None
    except error.HTTPError as exc:
        return exc.code,json.loads(exc.read())

def main():
    code,current=http('/flows')
    if code!=200 or not isinstance(current,dict) or not current.get('rev'):
        raise RuntimeError('Node-RED Admin API v2 unavailable; nothing deployed')
    desired=build()
    selected=lambda n:n.get('id')==TAB or n.get('z')==TAB
    others=[n for n in current['flows'] if not selected(n)]
    routes={(n.get('method'),n.get('url')) for n in desired if n['type']=='http in'}
    ids={n['id'] for n in desired}
    if len(routes)!=5 or any(n['id'] in ids or (n.get('type')=='http in' and (n.get('method'),n.get('url')) in routes) for n in others):
        raise RuntimeError('Node/route collision; nothing deployed')
    backup=ROOT/'backups'/datetime.now().strftime('%Y%m%d-%H%M%S')
    backup.mkdir(parents=True,exist_ok=False)
    (backup/'all-flows-before.json').write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf-8')
    persistent_before=any(n['id']=='pcb_store_request' for n in current['flows'])
    if persistent_before and not DB.is_file():
        raise RuntimeError('Persistent flow exists but SQLite file is missing. Restore backup; refusing an empty replacement.')
    store=Store()
    store.backup(backup/'workflow-before.sqlite3')
    if any(selected(n) for n in current['flows']):
        if persistent_before:
            status,state=200,store.snapshot()
        else:
            status,state=http('/giang-pcb4/v1/alerts')
        if status!=200:raise RuntimeError('Cannot back up alerts; stopped before deployment')
        (backup/'alerts-before.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
        store.migrate(state)
    print('Loading local model (no download)...',flush=True)
    predictor=Predictor()
    server=create_server(predictor,store) # Fail before deploy if port occupied.
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    status,_=http('/flows',{'rev':current['rev'],'flows':others+desired},{'Node-RED-Deployment-Type':'flows'})
    if status!=200:
        server.shutdown()
        raise RuntimeError(f'Deploy rejected HTTP {status}; backup: {backup}')
    _,after=http('/flows')
    assert {n['id']:n for n in after['flows'] if not selected(n)}=={n['id']:n for n in others},'Unrelated flow changed'
    actual={n['id']:n for n in after['flows'] if selected(n)}
    assert all(all(actual.get(n['id'],{}).get(k)==v for k,v in n.items()) for n in desired),'Source/deploy mismatch'
    checks=[]
    try:
        code,health=http('/giang-pcb4/v1/health')
        assert code==200 and health['ready']
        checks.append('model health')
        predictions=json.loads((RUN/'test-predictions.json').read_text())
        # Two fixed examples selected from saved baseline; no threshold tuning.
        examples=[next(r for r in predictions if r['label']=='normal'),next(r for r in predictions if r['predicted_anomaly'])]
        for row in examples:
            _,before_alerts=http('/giang-pcb4/v1/alerts')
            image=Path('D:/Project/aiot-model/datasets/visa')/row['image']
            payload={'image_base64':base64.b64encode(image.read_bytes()).decode(),
                     'record_id':'verify_'+uuid.uuid4().hex,'timestamp':datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')}
            code,data=http('/giang-pcb4/v1/infer',payload)
            assert code==200,(code,data)
            item=data['workflow']['results'][0]
            expected='alert' if row['predicted_anomaly'] else 'normal'
            assert item['status']==expected and abs(data['model']['raw_score']-row['score'])<.001
            code,repeat=http('/giang-pcb4/v1/infer',payload)
            assert code==200 and repeat['workflow']['results'][0]['status']=='duplicate'
            _,after_alerts=http('/giang-pcb4/v1/alerts')
            assert after_alerts['total']==before_alerts['total']+int(expected=='alert')
            if expected=='alert':
                _,first=http('/giang-pcb4/v1/ack',{'alert_id':item['alert_id']})
                _,second=http('/giang-pcb4/v1/ack',{'alert_id':item['alert_id']})
                assert first['changed'] and not second['changed']
                assert first['alert']['acknowledged_at']==second['alert']['acknowledged_at']
            checks.append(expected+' score / duplicate / ACK where applicable')
        code,_=http('/giang-pcb4/v1/ack',{'alert_id':'not_found'})
        assert code==404
        checks.append('unknown ACK rejected')
        invalid={'record_id':'invalid_'+uuid.uuid4().hex,'timestamp':datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z'),'image_base64':base64.b64encode(b'not an image').decode()}
        code,bad=http('/giang-pcb4/v1/infer',invalid)
        assert code==502 and bad['code']=='MODEL_UNAVAILABLE_OR_IMAGE_ERROR'
        checks.append('intentional invalid image: error, never normal')
        _,via_http=http('/giang-pcb4/v1/alerts')
        reopened=Store().snapshot()
        assert via_http['alerts']==reopened['alerts']
        checks.append('database reopened: alerts and ACK match HTTP')
        report={'http_passed':True,'checks':checks,'unrelated_flows_unchanged':True,'source_matches_deployed':True,'backup':str(backup)}
    except Exception as exc:
        report={'http_passed':False,'checks':checks,'error':repr(exc),'backup':str(backup)}
    (ROOT/'http-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    print('OPEN: http://localhost:1880/giang-pcb4/v1/demo\nKeep this terminal open. Ctrl+C stops model service.',flush=True)
    try:
        worker.join()
    except KeyboardInterrupt:
        server.shutdown()

if __name__=='__main__':main()

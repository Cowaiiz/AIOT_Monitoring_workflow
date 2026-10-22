"""Real Python HTTP tests; fixtures are independent of the engine. Bounded: 4 workers, 3s/request."""
import concurrent.futures as cf
import json
import time
import uuid
from pathlib import Path
import client

def run(base=client.BASE):
    cases=[];run_id='pyw'+uuid.uuid4().hex[:10];seq=0
    def req(route,p=None,**kw):return client.send(route,p,base=base,**kw)
    def first(r):return (r.get('body') or {}).get('results',[{}])[0]
    def check(name,expected,ok,actual):cases.append(dict(name=name,expected=expected,pass_=bool(ok),actual=actual))
    def rec(score=.2,source='src01'):
        nonlocal seq
        seq+=1
        return dict(record_id=f'{run_id}_{seq}',source_id=source,timestamp=client.timestamp(),anomaly_score=score)
    probe=req('alerts')
    if probe['http']!=200:
        return dict(mode='Python real HTTP workflow',blocked=True,probe=probe,passed=0,failed=0,cases=[],note='No cases ran; this is not a pass.')
    before=probe['body']['total'];fixture=json.loads(Path(__file__).with_name('mixed_cases.json').read_text());rows=[]
    for c in fixture['cases']:
        p=rec(c['score']);kind=c['kind']
        if kind=='missing':del p['anomaly_score']
        if kind=='unknown':p['source_id']='unknown'
        if kind=='stale':p['timestamp']=client.timestamp(-3600000)
        if kind=='bad_time':p['timestamp']='invalid'
        rows.append(p)
    mixed=req('batch',dict(records=rows));results=(mixed['body'] or {}).get('results',[])
    check('Mixed batch','207 and 80 results',mixed['http']==207 and len(results)==80,mixed)
    for c,got in zip(fixture['cases'],results):
        check(c['id']+' '+c['kind'],c['expected_code'] or c['expected_status'],got.get('status')==c['expected_status'] and got.get('code')==c['expected_code'],got)
    created=sum(c['expected_status']=='alert' for c in fixture['cases'])
    malformed=req('records','{bad');check('Malformed JSON','400 INVALID_JSON',malformed['http']==400 and (malformed['body'] or {}).get('code')=='INVALID_JSON',malformed)
    d=rec(.9);new=req('records',d);created+=1
    duplicate=req('records',d);conflict=req('records',{**d,'anomaly_score':.1})
    check('Duplicate','duplicate',first(duplicate).get('status')=='duplicate',duplicate)
    check('Conflict','ID_CONFLICT',first(conflict).get('code')=='ID_CONFLICT',conflict)
    old=rec();old['timestamp']=client.timestamp(-10000);r=req('records',old)
    check('Out of order','OUT_OF_ORDER',first(r).get('code')=='OUT_OF_ORDER',r)
    multi=[rec(.95,s) for s in ['src02','src03','src04','src05']]
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        parallel=list(pool.map(lambda p:req('records',p),multi))
    created+=4;check('Concurrent sources','4 alert',all(first(r).get('status')=='alert' for r in parallel),parallel)
    same=rec(.9,'src06')
    with cf.ThreadPoolExecutor(max_workers=4) as pool:retries=list(pool.map(lambda _:req('records',same),range(4)))
    created+=1;check('Concurrent duplicate','1 alert and 3 duplicate',[first(r).get('status') for r in retries].count('alert')==1 and [first(r).get('status') for r in retries].count('duplicate')==3,retries)
    delayed=rec(.9,'src07');timeout=req('records',delayed,timeout=.02,headers={'x-demo-delay-ms':'200'});time.sleep(.3);retry=req('records',delayed);created+=1
    check('Sender timeout retry','timeout and duplicate',bool(timeout['transport_error']) and 'tim' in timeout['transport_error'].lower() and first(retry).get('status')=='duplicate',dict(first=timeout,retry=retry))
    alert_id=first(new).get('alert_id');ack=req('ack',dict(alert_id=alert_id));again=req('ack',dict(alert_id=alert_id))
    check('ACK once and again','true then false; same time',ack['body'].get('changed') is True and again['body'].get('changed') is False and ack['body']['alert']['acknowledged_at']==again['body']['alert']['acknowledged_at'],dict(first=ack,again=again))
    alert_id2=first(parallel[0]).get('alert_id')
    with cf.ThreadPoolExecutor(max_workers=4) as pool:acks=list(pool.map(lambda _:req('ack',dict(alert_id=alert_id2)),range(4)))
    check('Concurrent ACK','one change; one timestamp',sum(r['body'].get('changed') is True for r in acks)==1 and len({r['body'].get('alert',{}).get('acknowledged_at') for r in acks})==1,acks)
    unknown=req('ack',dict(alert_id='does-not-exist'));check('Unknown ACK','404 ALERT_NOT_FOUND',unknown['http']==404 and unknown['body'].get('code')=='ALERT_NOT_FOUND',unknown)
    after=req('alerts')['body'];mine=[a for a in after['alerts'] if a['record_id'].startswith(run_id)]
    check('Actual alert state',f'{created} created; 2 acknowledged',len(mine)==created and after['total']-before==created and sum(a['status']=='acknowledged' for a in mine)==2,mine)
    req('records',rec(.2,'src10'));time.sleep(31.05);silent=next(s for s in req('sources')['body']['sources'] if s['source_id']=='src10');req('records',rec(.2,'src10'));active=next(s for s in req('sources')['body']['sources'] if s['source_id']=='src10')
    check('Silence and recovery','silent then active',silent['state']=='silent' and active['state']=='active',dict(silent=silent,active=active))
    for c in cases:c['pass']=c.pop('pass_')
    return dict(mode='Python real HTTP workflow',run=run_id,seed=42,blocked=False,passed=sum(c['pass'] for c in cases),failed=sum(not c['pass'] for c in cases),cases=cases)

if __name__=='__main__':
    try:result=run()
    except Exception as e:result=dict(mode='Python real HTTP workflow',blocked=False,failed=1,error=repr(e))
    Path('results').mkdir(exist_ok=True)
    Path('results/python-workflow-http.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=True))
    raise SystemExit(1 if result.get('blocked') or result.get('failed') else 0)

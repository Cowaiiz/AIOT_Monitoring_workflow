"""Python 3.11+, standard library only. All data are simulated."""
import argparse
import concurrent.futures as cf
import json
import math
import random
import socket
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import request, error

BASE = 'http://127.0.0.1:1880/giang-aiot/v1'

def timestamp(offset_ms=0):
    return datetime.fromtimestamp(time.time()+offset_ms/1000,timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')

def generate(count=10000, sources=10, seed=42):
    rng=random.Random(seed)
    return [{'record_id':f'r{i:06}', 'source_id':f'src{i%sources+1:02}',
             'age_ms':0,'anomaly_score':round(rng.random(),6)} for i in range(count)]

def materialize(rows, run_id):
    # Fresh per dispatch. Same exact serialized record must be retained for retries.
    return [dict(record_id=f'{run_id}_{r["record_id"]}',source_id=r['source_id'],
                 timestamp=timestamp(-r.get('age_ms',0)),anomaly_score=r['anomaly_score']) for r in rows]

def send(route, payload=None, base=BASE, timeout=3, headers=None):
    raw=payload.encode() if isinstance(payload,str) else json.dumps(payload,allow_nan=False).encode() if payload is not None else None
    req=request.Request(base+'/'+route,data=raw,headers={'Content-Type':'application/json',**(headers or {})},method='GET' if payload is None else 'POST')
    start=time.perf_counter()
    try:
        try:
            with request.urlopen(req,timeout=timeout) as response:
                status=response.status;data=response.read()
        except error.HTTPError as exc:
            status=exc.code;data=exc.read()
        try: body=json.loads(data)
        except (ValueError,UnicodeDecodeError): body={'code':'NON_JSON_RESPONSE','preview':data[:200].decode(errors='replace')}
        return {'http':status,'body':body,'latency_ms':(time.perf_counter()-start)*1000,'transport_error':None}
    except (error.URLError,TimeoutError,socket.timeout,OSError) as exc:
        return {'http':None,'body':None,'latency_ms':(time.perf_counter()-start)*1000,'transport_error':type(exc).__name__+': '+str(exc)}

def summarize(responses, seconds, sent_records):
    lat=sorted(r['latency_ms'] for r in responses)
    results=[v for r in responses for v in (r['body'] or {}).get('results',[])]
    unexpected=sum(bool(r['transport_error']) or r['http']!=200 for r in responses)
    accepted=sum(v['status'] in ('normal','alert') for v in results)
    return {'requests':len(responses),'records_sent':sent_records,'records_with_results':len(results),
            'accepted_records':accepted,'record_errors':sum(v['status']=='error' for v in results),
            'transport_errors':sum(bool(r['transport_error']) for r in responses),
            'unexpected_request_errors':unexpected,'unexpected_request_error_rate':unexpected/max(1,len(responses)),
            'elapsed_seconds':seconds,'accepted_records_per_second':accepted/max(seconds,1e-9),
            'requests_per_second':len(responses)/max(seconds,1e-9),
            'latency_median_ms':statistics.median(lat) if lat else None,
            'latency_p95_ms':lat[max(0,math.ceil(.95*len(lat))-1)] if lat else None,
            'latency_scope':'client request including failed attempts; not per-record latency'}

def load(args):
    rows=json.loads(Path(args.input).read_text(encoding='utf-8')) if args.input else generate(args.count,args.sources,args.seed)
    rows=rows[:args.count]
    run_id=uuid.uuid4().hex[:12]
    start=time.perf_counter();responses=[];sent=0
    # Sequential per source avoids generating accidental out-of-order traffic.
    for offset in range(0,len(rows),args.batch):
        if time.perf_counter()-start>args.deadline: break
        target=start+offset/args.rate
        if target>time.perf_counter(): time.sleep(target-time.perf_counter())
        if time.perf_counter()-start>args.deadline: break
        batch=materialize(rows[offset:offset+args.batch],run_id)
        response=send('records' if args.batch==1 else 'batch',batch[0] if args.batch==1 else {'records':batch},args.base,args.timeout)
        responses.append(response);sent+=len(batch)
        if response['transport_error'] or response['http']!=200: break
    return {'mode':'Python real HTTP','seed':args.seed,'run_id':run_id,'target_rate':args.rate,
            'completed':sent==len(rows),'metrics':summarize(responses,time.perf_counter()-start,sent),
            'first_error':next((r for r in responses if r['transport_error'] or r['http']!=200),None)}

def tests(base=BASE):
    cases=[];prefix=uuid.uuid4().hex[:10];n=0
    def rec(score=.2,source='src01',**kw):
        nonlocal n
        n+=1;return dict(record_id=f'{prefix}_{n}',source_id=source,timestamp=timestamp(),anomaly_score=score,**kw)
    def status(r): return (r['body'] or {}).get('results',[{}])[0].get('status')
    def code(r): return (r['body'] or {}).get('results',[{}])[0].get('code',(r['body'] or {}).get('code'))
    def check(name,ok,response,expected_error=False):
        cases.append({'name':name,'pass':bool(ok),'expected_error':expected_error,'response':response})
    probe=send('metrics',base=base)
    if probe['transport_error'] or probe['http']!=200:
        return {'mode':'Python real HTTP','blocked':True,'probe':probe,'cases':[],'passed':0,'failed':0,'note':'No cases executed: endpoint unavailable. This is not a passing suite.'}
    for score,want in [(.2,'normal'),(.5,'alert'),(.9,'alert')]:
        r=send('records',rec(score),base);check('score '+str(score),r['http']==200 and status(r)==want,r)
    r=send('records',rec(.5,'src02'),base);check('per source',status(r)=='normal',r)
    missing=rec();del missing['anomaly_score']
    stale=rec();stale['timestamp']=timestamp(-3600000)
    future=rec();future['timestamp']=timestamp(3600000)
    invalid=rec();invalid['timestamp']='2026-02-30T00:00:00.000Z'
    for name,p,want in [('missing',missing,'MISSING_FIELD_anomaly_score'),('string',rec('0.9'),'INVALID_SCORE'),('bool',rec(True),'INVALID_SCORE'),('null',rec(None),'INVALID_SCORE'),('range',rec(-.1),'INVALID_SCORE'),('source',rec(.2,'unknown'),'UNKNOWN_SOURCE'),('stale',stale,'STALE_RECORD'),('future',future,'FUTURE_RECORD'),('date',invalid,'INVALID_TIMESTAMP')]:
        r=send('records',p,base);check(name,r['http']==422 and code(r)==want,r,True)
    r=send('records','{bad',base);check('JSON syntax',r['http']==400 and code(r)=='INVALID_JSON',r,True)
    r=send('batch',{'records':[rec(),rec('bad'),rec(.9)]},base);check('mixed batch',r['http']==207 and (r['body'] or {}).get('summary',{}).get('errors')==1,r,True)
    r=send('batch',{'records':[rec() for _ in range(201)]},base);check('batch cap',r['http']==413,r,True)
    duplicate=rec(.9,'src03');send('records',duplicate,base)
    r=send('records',duplicate,base);check('duplicate',status(r)=='duplicate',r)
    r=send('records',{**duplicate,'anomaly_score':.1},base);check('conflict',code(r)=='ID_CONFLICT',r,True)
    older=rec(.2,'src03');older['timestamp']=timestamp(-10000)
    r=send('records',older,base);check('out of order',code(r)=='OUT_OF_ORDER',r,True)
    same=rec(.9,'src04')
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        rs=list(pool.map(lambda _:send('records',same,base),range(8)))
    check('concurrent duplicate',sum(status(r)=='alert' for r in rs)==1 and sum(status(r)=='duplicate' for r in rs)==7,rs)
    delayed=rec(.9,'src05')
    first=send('records',delayed,base,timeout=.02,headers={'x-demo-delay-ms':'200'})
    time.sleep(.3)
    retry=send('records',delayed,base)
    check('sender timeout retry',bool(first['transport_error']) and status(retry)=='duplicate',{'first':first,'retry':retry},True)
    return {'mode':'Python real HTTP','blocked':False,'passed':sum(c['pass'] for c in cases),'failed':sum(not c['pass'] for c in cases),
            'expected_error_cases':sum(c['expected_error'] for c in cases),'cases':cases,'server_metrics':send('metrics',base=base)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['generate','send','test','ramp'])
    p.add_argument('--base',default=BASE);p.add_argument('--count',type=int,default=10000)
    p.add_argument('--sources',type=int,default=10);p.add_argument('--seed',type=int,default=42)
    p.add_argument('--batch',type=int,default=100);p.add_argument('--rate',type=float,default=500)
    p.add_argument('--timeout',type=float,default=3);p.add_argument('--deadline',type=float,default=120)
    p.add_argument('--input');p.add_argument('--output',default='results/client.json')
    args=p.parse_args()
    if not (1<=args.count<=100000 and 1<=args.sources<=10 and 1<=args.batch<=200 and 0<args.rate<=2000 and 0<args.timeout<=10 and 0<args.deadline<=300):p.error('Limits: count 1..100000, sources 1..10, batch 1..200, rate <=2000, timeout <=10, deadline <=300')
    if args.command=='generate':result=generate(args.count,args.sources,args.seed)
    elif args.command=='test':result=tests(args.base)
    elif args.command=='send':result=load(args)
    else:
        result={'stages':[]}
        for count,rate in [(1000,100),(3000,500),(6000,1000)]:
            args.count=count;args.rate=rate;args.batch=100;args.deadline=60
            stage=load(args);result['stages'].append(stage)
            if not stage['completed'] or stage['metrics']['unexpected_request_errors']:break
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Saved {path}');print(json.dumps(result if args.command!='generate' else {'records':len(result),'seed':args.seed},ensure_ascii=True)[:3000])
    if args.command=='test' and (result.get('blocked') or result.get('failed')):raise SystemExit(1)
    if args.command=='send' and (not result['completed'] or result['metrics']['unexpected_request_errors']):raise SystemExit(1)
    if args.command=='ramp' and (len(result['stages'])!=3 or any(not s['completed'] or s['metrics']['unexpected_request_errors'] for s in result['stages'])):raise SystemExit(1)

if __name__=='__main__':main()

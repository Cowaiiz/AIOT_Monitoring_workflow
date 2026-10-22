"""Transactional local workflow storage. No automatic eviction of records/alerts."""
import json
import math
import re
import sqlite3
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pathlib import Path

DB = Path(__file__).resolve().parent/'data/workflow.sqlite3'
def utc():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
def canonical(p):
    return json.dumps(p, sort_keys=True, separators=(',',':'), allow_nan=False)

class Store:
    def __init__(self, path=DB, capacity=20000, record_capacity=100000):
        self.path=Path(path)
        self.capacity=capacity
        self.record_capacity=record_capacity
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS records
                (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, result TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);''')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            db.execute('PRAGMA synchronous=FULL')
            with db:
                yield db
        finally:
            db.close()
    def snapshot(self):
        with self.connect() as db:
            items=[json.loads(r[0]) for r in db.execute('SELECT body FROM alerts ORDER BY rowid')]
        return {'alerts':items,'total':len(items),'pending':sum(a['status']=='pending' for a in items),
                'acknowledged':sum(a['status']=='acknowledged' for a in items),
                'capacity':self.capacity,'storage':'SQLite; persistent across service/Node-RED restart and redeploy'}
    def backup(self, destination):
        with self.connect() as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
    def migrate(self, snapshot):
        """Keep legacy alerts/ACK times; explicitly retain limited legacy fingerprint."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for a in snapshot['alerts']:
                existing=db.execute('SELECT body FROM alerts WHERE id=?',(a['alert_id'],)).fetchone()
                if existing:
                    previous=json.loads(existing[0])
                    for key in ('record_id','source_id','timestamp','anomaly_score'):
                        if previous[key]!=a[key]:raise ValueError('Legacy migration conflict')
                    if previous['status']=='pending' and a['status']=='acknowledged':
                        previous.update(status='acknowledged',acknowledged_at=a['acknowledged_at'])
                        db.execute('UPDATE alerts SET body=? WHERE id=?',(canonical(previous),a['alert_id']))
                    continue
                if a['status'] not in ('pending','acknowledged') or a['source_id']!='visa_pcb4':
                    raise ValueError('Invalid legacy alert; migration rolled back')
                result={k:v for k,v in a.items() if k not in ('created_at','acknowledged_at')}
                result['status']='alert'
                db.execute('INSERT INTO alerts VALUES (?,?)',(a['alert_id'],canonical(a)))
                db.execute('INSERT INTO records VALUES (?,?,?)',(a['record_id'],'legacy',canonical(result)))
    def handle(self,route,p):
        if route=='alerts':return 200,self.snapshot()
        def fail(code,http=422):return http,{'status':'error','code':code}
        if not isinstance(p,dict):return fail('INVALID_REQUEST')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if route=='ack':
                if not isinstance(p.get('alert_id'),str):return fail('INVALID_ALERT_ID',400)
                row=db.execute('SELECT body FROM alerts WHERE id=?',(p['alert_id'],)).fetchone()
                if not row:return fail('ALERT_NOT_FOUND',404)
                a=json.loads(row[0]);changed=a['status']=='pending'
                if changed:
                    a.update(status='acknowledged',acknowledged_at=utc())
                    db.execute('UPDATE alerts SET body=? WHERE id=?',(canonical(a),a['alert_id']))
                return 200,{'changed':changed,'alert':a}
            if route!='records':return fail('NOT_FOUND',404)
            for key in ('record_id','source_id'):
                if not isinstance(p.get(key),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',p[key]):return fail('INVALID_'+key.upper())
            if p['source_id']!='visa_pcb4':return fail('UNKNOWN_SOURCE')
            for key in ('anomaly_score','raw_score','raw_threshold'):
                if type(p.get(key)) not in (float,int) or not math.isfinite(p[key]):return fail('INVALID_SCORE')
            if not 0<=p['anomaly_score']<=1 or p['raw_score']<0 or p['raw_threshold']<=0:return fail('INVALID_SCORE')
            if abs(p['anomaly_score']-p['raw_score']/(p['raw_score']+p['raw_threshold']))>1e-12:return fail('SCORE_MISMATCH')
            expected='alert' if p['raw_score']>=p['raw_threshold'] else 'normal'
            if p.get('decision')!=expected:return fail('DECISION_MISMATCH')
            for key,pattern in [('image_sha256',r'[0-9a-f]{64}'),('model_version',r'[0-9a-f]{16}')]:
                if not isinstance(p.get(key),str) or not re.fullmatch(pattern,p[key]):return fail('INVALID_'+key.upper())
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z',p['timestamp']):raise ValueError()
                stamp=datetime.fromisoformat(p['timestamp'].replace('Z','+00:00'))
            except (ValueError,TypeError,KeyError):return fail('INVALID_TIMESTAMP')
            fingerprint=canonical(p)
            old=db.execute('SELECT fingerprint,result FROM records WHERE id=?',(p['record_id'],)).fetchone()
            def wrap(result):
                return 200,{'results':[result],'summary':{'records':1,'errors':0,'accepted':int(result['status']!='duplicate'),'duplicates':int(result['status']=='duplicate')}}
            if old:
                prior=json.loads(old[1])
                if old[0]=='legacy':
                    # Full image fingerprint was not exposed by v1; never assume equality.
                    return fail('LEGACY_ID_RESERVED_USE_NEW_RECORD',409)
                if old[0]!=fingerprint:return fail('ID_CONFLICT',409)
                return wrap({'status':'duplicate','record_id':p['record_id'],'original':prior})
            age=(datetime.now(timezone.utc)-stamp).total_seconds()
            if age>300:return fail('STALE_RECORD')
            if age< -30:return fail('FUTURE_RECORD')
            watermark=db.execute("SELECT value FROM metadata WHERE key='watermark'").fetchone()
            if watermark and p['timestamp']<watermark[0]:return fail('OUT_OF_ORDER')
            if db.execute('SELECT count(*) FROM records').fetchone()[0]>=self.record_capacity:return fail('RECORD_CAPACITY_FULL',503)
            if expected=='alert' and db.execute('SELECT count(*) FROM alerts').fetchone()[0]>=self.capacity:return fail('ALERT_CAPACITY_FULL',503)
            result={**p,'status':expected,'threshold':.5,'simulated':False}
            result.pop('decision')
            if expected=='alert':
                result.update(alert_id='ai:visa_pcb4:'+p['record_id'],event_id='ai:visa_pcb4:'+p['record_id'])
                alert={**result,'status':'pending','created_at':utc(),'acknowledged_at':None}
                db.execute('INSERT INTO alerts VALUES (?,?)',(alert['alert_id'],canonical(alert)))
            db.execute('INSERT INTO records VALUES (?,?,?)',(p['record_id'],fingerprint,canonical(result)))
            db.execute("INSERT OR REPLACE INTO metadata VALUES ('watermark',?)",(p['timestamp'],))
            return wrap(result)

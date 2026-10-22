import concurrent.futures
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from storage import Store,utc

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'test.sqlite3'
        self.store=Store(self.path)
    def tearDown(self):self.tmp.cleanup()
    def record(self,id='one',score=16):
        return dict(record_id=id,source_id='visa_pcb4',timestamp=utc(),raw_score=score,raw_threshold=14,
                    anomaly_score=score/(score+14),decision='alert' if score>=14 else 'normal',
                    image_sha256='a'*64,model_version='b'*16)
    def test_threshold_normal_and_restart(self):
        p=self.record(score=14)
        code,body=self.store.handle('records',p)
        self.assertEqual((code,body['results'][0]['status']),(200,'alert'))
        self.store.handle('records',self.record('normal',2))
        reopened=Store(self.path)
        self.assertEqual(reopened.snapshot()['total'],1)
        self.assertEqual(reopened.handle('records',p)[1]['results'][0]['status'],'duplicate')
    def test_concurrent_retry_and_ack(self):
        p=self.record()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            responses=list(pool.map(lambda _:self.store.handle('records',p),range(4)))
        self.assertEqual(sum(r[1]['results'][0]['status']=='alert' for r in responses),1)
        aid=self.store.snapshot()['alerts'][0]['alert_id']
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            ack=list(pool.map(lambda _:self.store.handle('ack',{'alert_id':aid})[1],range(4)))
        self.assertEqual(sum(a['changed'] for a in ack),1)
        self.assertEqual(len({a['alert']['acknowledged_at'] for a in ack}),1)
        self.assertEqual(Store(self.path).snapshot()['acknowledged'],1)
    def test_conflict_missing_ack_and_bad_data(self):
        p=self.record();self.store.handle('records',p)
        self.assertEqual(self.store.handle('records',{**p,'image_sha256':'c'*64})[0],409)
        self.assertEqual(self.store.handle('ack',{'alert_id':'absent'})[0],404)
        self.assertEqual(self.store.handle('records',{**self.record('bad'),'decision':'normal'})[1]['code'],'DECISION_MISMATCH')
        self.assertEqual(self.store.handle('records',{**self.record('bad'),'raw_score':float('nan')})[0],422)
        self.assertEqual(self.store.snapshot()['total'],1)
    def test_capacity_keeps_pending(self):
        small=Store(self.path,capacity=1,record_capacity=2)
        small.handle('records',self.record())
        self.assertEqual(small.handle('records',self.record('two'))[1]['code'],'ALERT_CAPACITY_FULL')
        self.assertEqual(small.snapshot()['pending'],1)
        small.handle('records',self.record('normal',1))
        self.assertEqual(small.handle('records',self.record('normal2',1))[1]['code'],'RECORD_CAPACITY_FULL')
    def test_rollback_on_write_failure(self):
        with self.store.connect() as db:
            db.execute("CREATE TRIGGER fail_record BEFORE INSERT ON records BEGIN SELECT RAISE(ABORT,'test disk failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.store.handle('records',self.record())
        self.assertEqual(Store(self.path).snapshot()['total'],0)
    def test_migration_and_backup(self):
        legacy={'alert_id':'ai:visa_pcb4:old','record_id':'old','source_id':'visa_pcb4','timestamp':utc(),
                'anomaly_score':.5,'threshold':.5,'simulated':False,'status':'acknowledged',
                'created_at':'2026-01-01T00:00:00.000Z','acknowledged_at':'2026-01-01T01:00:00.000Z'}
        self.store.migrate({'alerts':[legacy]});self.store.migrate({'alerts':[legacy]})
        self.assertEqual(self.store.snapshot()['alerts'],[legacy])
        self.assertEqual(self.store.handle('records',self.record('old'))[1]['code'],'LEGACY_ID_RESERVED_USE_NEW_RECORD')
        dest=Path(self.tmp.name)/'backup.sqlite3';self.store.backup(dest)
        self.assertEqual(Store(dest).snapshot()['alerts'],[legacy])
    def test_timestamp_and_durable_retry(self):
        self.assertEqual(self.store.handle('records',{**self.record(),'timestamp':'not-time'})[1]['code'],'INVALID_TIMESTAMP')
        self.assertEqual(self.store.handle('records',{**self.record(),'timestamp':'2020-01-01T00:00:00.000Z'})[1]['code'],'STALE_RECORD')
        p=self.record();self.store.handle('records',p)
        # Retry uses persisted fingerprint before freshness, even after restart.
        self.assertEqual(Store(self.path).handle('records',p)[1]['results'][0]['status'],'duplicate')

if __name__=='__main__':unittest.main(verbosity=2)

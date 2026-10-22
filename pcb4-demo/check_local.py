"""Read-only real checkpoint verification; does not open network sockets."""
import json
from pathlib import Path
from model_service import Predictor,RUN
p=Predictor()
rows=json.loads((RUN/'test-predictions.json').read_text())
samples=[next(r for r in rows if r['label']=='normal'),next(r for r in rows if r['predicted_anomaly']),next(r for r in rows if r['label']=='anomaly' and not r['predicted_anomaly'])]
checks=[]
for row in samples:
    raw=(Path('D:/Project/aiot-model/datasets/visa')/row['image']).read_bytes()
    a=p.predict(raw)
    b=p.predict(raw)
    assert abs(a['raw_score']-row['score'])<.001,(a['raw_score'],row['score'])
    assert a['raw_score']==b['raw_score'],'Repeated inference differs'
    assert (a['anomaly_score']>=.5)==row['predicted_anomaly']
    checks.append({'image':row['image'],'score':a['raw_score'],'baseline_score':row['score'],'matched':True})
try:
    p.predict(b'not an image')
    raise AssertionError('Invalid image accepted')
except OSError:
    pass
report={'real_checkpoint_passed':True,'device':p.device,'cases':checks,'invalid_image_rejected':True,'http_tested':False}
Path(__file__).with_name('local-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))

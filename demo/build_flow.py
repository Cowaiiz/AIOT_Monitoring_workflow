import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TAB='giang_pcb4_real_v1'
def build():
    nodes=[dict(id=TAB,type='tab',label='VisA PCB4 — AI thật',disabled=False,info='v2: SQLite persistent workflow, loopback only. Source: demo/build_flow.py')]
    def add(id,type,wires=None,**kw):
        nodes.append(dict(id='pcb_'+id,z=TAB,type=type,x=kw.pop('x',500),y=kw.pop('y',200),wires=[['pcb_'+v for v in w] for w in (wires or [])],**kw))
    for i,route in enumerate(['demo','infer','alerts','ack','health']):
        add(route,'http in',[['guard']],name=route,url='/giang-pcb4/v1/'+route,method='post' if route in ['infer','ack'] else 'get',upload=False,skipBodyParsing=False,x=100,y=80+i*80)
    add('guard','function',[['dispatch'],['response']],name='Loopback only',outputs=2,func="const ip=msg.req.socket?.remoteAddress||msg.req._req?.socket?.remoteAddress;if(!['127.0.0.1','::1','::ffff:127.0.0.1'].includes(ip)){msg.statusCode=403;msg.payload={code:'LOCAL_ONLY'};return [null,msg];}return [msg,null];")
    html=json.dumps((ROOT/'index.html').read_text(encoding='utf-8'))
    add('dispatch','function',[['request'],['engine'],['response']],name='Image / workflow routes',outputs=3,func="""const r=msg.req.url.split('?')[0].split('/').pop();msg.route=r;
if(r==='demo'){msg.headers={'content-type':'text/html; charset=utf-8'};msg.payload=HTML;return [null,null,msg];}
if(r==='infer'||r==='health'){
 if(r==='infer'){const p=msg.payload;if(!p||typeof p.image_base64!=='string'||p.image_base64.length>7000000||typeof p.record_id!=='string'||!/^[a-zA-Z0-9_-]{1,64}$/.test(p.record_id)||typeof p.timestamp!=='string'){msg.statusCode=400;msg.payload={code:'INVALID_INPUT'};return [null,null,msg];}msg.record={record_id:p.record_id,timestamp:p.timestamp};}
 msg.url='http://127.0.0.1:1891/'+r;msg.method=r==='health'?'GET':'POST';msg.headers={'content-type':'application/json'};return [msg,null,null];}
return [null,msg,null];""".replace('HTML',html))
    add('request','http request',[['model_result']],name='Python PatchCore (loopback)',method='use',ret='obj',paytoqs='ignore',url='',persist=False,insecureHTTPParser=False,senderr=False,headers=[],requestTimeout='30000')
    add('model_result','function',[['engine'],['response']],name='Validate model output',outputs=2,func="""if(msg.statusCode!==200){msg.statusCode=502;msg.payload={code:'MODEL_UNAVAILABLE_OR_IMAGE_ERROR',detail:msg.payload?.code};return [null,msg];}
msg.headers={'content-type':'application/json','cache-control':'no-store'};
if(msg.route==='health')return [null,msg];const p=msg.payload;
if(!p||!Number.isFinite(p.raw_score)||p.raw_score<0||!Number.isFinite(p.raw_threshold)||p.raw_threshold<=0){msg.statusCode=502;msg.payload={code:'INVALID_MODEL_OUTPUT'};return [null,msg];}
msg.model=p;msg.payload={...msg.record,source_id:'visa_pcb4',anomaly_score:p.raw_score/(p.raw_score+p.raw_threshold),raw_score:p.raw_score,raw_threshold:p.raw_threshold,decision:p.raw_score>=p.raw_threshold?'alert':'normal',image_sha256:p.image_sha256,model_version:p.model_version};return [msg,null];""")
    add('engine','function',[['store_request']],name='Save decision / read alerts / ACK',outputs=1,func="msg.url='http://127.0.0.1:1891/'+(msg.route==='infer'?'records':msg.route);msg.method=msg.route==='alerts'?'GET':'POST';msg.headers={'content-type':'application/json'};delete msg.statusCode;return msg;")
    add('store_request','http request',[['store_result']],name='SQLite transactional workflow',method='use',ret='obj',paytoqs='ignore',url='',persist=False,insecureHTTPParser=False,senderr=False,headers=[],requestTimeout='10000')
    add('store_result','function',[['response']],name='Only respond after database commit',outputs=1,func="msg.headers={'content-type':'application/json','cache-control':'no-store'};if(typeof msg.statusCode!=='number'){msg.statusCode=502;msg.payload={code:'STORAGE_UNAVAILABLE'};}if(msg.statusCode===200 && msg.model)msg.payload={model:msg.model,workflow:msg.payload};return msg;")
    add('response','http response',name='HTTP response',statusCode='',headers={},x=1000)
    add('catch','catch',[['error']],name='Processing / network error',scope=None,uncaught=False)
    add('error','function',[['response']],name='Never normal on error',outputs=1,func="msg.statusCode=502;msg.headers={'content-type':'application/json'};msg.payload={code:'MODEL_OR_WORKFLOW_ERROR'};return msg;")
    (ROOT/'flow.json').write_text(json.dumps(nodes,ensure_ascii=False,indent=2),encoding='utf-8')
    return nodes
if __name__=='__main__':build()

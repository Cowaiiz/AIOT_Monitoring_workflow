"""Generate an importable, independent tab; never modifies the running Node-RED."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TAB = 'giang_http_v1_20261022'

def build():
    config = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    engine = (ROOT/'engine.js').read_text(encoding='utf-8').split("if(typeof module")[0]
    nodes = [{'id':TAB,'type':'tab','label':'AIoT - HTTP medium demo','disabled':False,'info':'Simulated AI only. Loopback clients only. See README.md. State resets on redeploy/restart.'}]
    def add(id, type, name, x, y, wires=None, **kw):
        nodes.append(dict(id=id,z=TAB,type=type,name=name,x=x,y=y,wires=wires or [],**kw))
    for i,route in enumerate(['records','batch','metrics','events','sources','demo','alerts','ack']):
        post=route in ['records','batch','ack']
        add('gh_'+route,'http in',route,150,80+i*70,[['gh_guard']],url='/giang-aiot/v1/'+route,method='post' if post else 'get',upload=False,skipBodyParsing=post,swaggerDoc='')
    add('gh_guard','function','Local clients only',390,200,[['gh_engine'],['gh_response']],outputs=2,func="const ip=msg.req.socket?.remoteAddress || msg.req._req?.socket?.remoteAddress; if(!['127.0.0.1','::1','::ffff:127.0.0.1'].includes(ip)){msg.statusCode=403;msg.payload={status:'error',code:'LOCAL_ONLY'};return [null,msg];} return [msg,null];")
    init=engine+'\ncontext.set("engine",createEngine('+json.dumps(config)+'));'
    html=(ROOT/'demo.html').read_text(encoding='utf-8').replace('// BROWSER_TESTS','async function runDemoLoad'+(ROOT/'browser_tests.js').read_text(encoding='utf-8').split('async function runDemoLoad',1)[1]).replace('// WORKFLOW_TESTS',(ROOT/'workflow_tests.js').read_text(encoding='utf-8')).replace('/* FIXTURE */ null',json.dumps(json.loads((ROOT/'mixed_cases.json').read_text(encoding='utf-8')),separators=(',',':')))
    func='''const route=msg.req.url.split('?')[0].split('/').pop();
if(route==='demo') {msg.headers={'content-type':'text/html; charset=utf-8'};msg.payload=DEMO_HTML;return [msg,null];}
msg.headers={'content-type':'application/json','cache-control':'no-store'};
const engine=context.get('engine');
if(!engine) throw Error('Engine not initialized');
let body=msg.payload;
if(Buffer.isBuffer(body)) {
  if(body.length>MAX_BYTES) {msg.statusCode=413;msg.payload={status:'error',code:'BODY_TOO_LARGE'};return [msg,null];}
  body=body.toString('utf8');
}
if(['records','batch','ack'].includes(route) && !/^application\\/json(?:;|$)/i.test(msg.req.headers['content-type']||'')) {msg.statusCode=415;msg.payload={status:'error',code:'CONTENT_TYPE'};return [msg,null];}
const result=engine.handle(route,body);
msg.statusCode=result.http;msg.payload=result.body;
const alerts=(result.body.results||[]).filter(r=>r.status==='alert').map(r=>({payload:{...r,event_type:'anomaly_detected'}}));
const delay=Number(msg.req.headers['x-demo-delay-ms']||0);
if(delay>0 && delay<=250) {setTimeout(()=>{node.send([msg,null]);node.done();},delay);return [null,alerts.length?alerts:null];}
return [msg,alerts.length?alerts:null];'''.replace('DEMO_HTML',json.dumps(html)).replace('MAX_BYTES',str(config['max_body_bytes']))
    add('gh_engine','function','Validate / dedup / rules / events',680,200,[['gh_response'],['gh_event_out']],outputs=2,initialize=init,func=func,finalize='',libs=[])
    add('gh_response','http response','HTTP result',990,160,statusCode='',headers={})
    add('gh_event_out','link out','Simulated anomaly events',1010,260,mode='link',links=[])
    add('gh_catch','catch','Unexpected processing errors',420,430,[['gh_error']],scope=['gh_guard','gh_engine'],uncaught=False)
    add('gh_error','function','Never turn exception into normal',730,430,[['gh_response']],outputs=1,func="msg.statusCode=500;msg.headers={'content-type':'application/json'};msg.payload={status:'error',kind:'internal',code:'INTERNAL_ERROR'};return msg;")
    (ROOT/'flow.json').write_text(json.dumps(nodes,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Built', ROOT/'flow.json')

if __name__=='__main__': build()

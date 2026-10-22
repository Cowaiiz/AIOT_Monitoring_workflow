const assert=require('node:assert/strict'),fs=require('node:fs');
const {createEngine}=require('./engine'),cfg=require('./config.json');
const {runWorkflowTests}=require('./workflow_tests');
async function main(){
 let now=Date.now();const e=createEngine(cfg);
 const req=async(path,p,options={})=>{const result=e.handle(path,p,now);if(options.timeout===20){const error=new Error('Simulated transport timeout AFTER processing');error.name='AbortError';throw error;}return {http:result.http,body:result.body};};
 const report=await runWorkflowTests(req,require('./mixed_cases.json'),()=>{},async ms=>{now+=ms;},()=>now);
 report.mode='offline engine + workflow; timeout simulated, NOT HTTP';
 function check(name,fn){try{fn();report.cases.push({name,pass:true});}catch(error){report.cases.push({name,pass:false,error:error.stack});}}
 const record=(id,score=.9)=>({record_id:id,source_id:'src01',timestamp:new Date(now).toISOString(),anomaly_score:score});
 check('Alert capacity rejects without dropping pending or marking accepted',()=>{
  const e=createEngine({...cfg,alert_capacity:2});e.handle('records',record('a'),now);e.handle('records',record('b'),now);
  assert.equal(e.handle('records',record('c'),now).http,503);assert.equal(e.handle('alerts',null,now).body.pending,2);assert.equal(e.handle('metrics',null,now).body.accepted,2);
  const id=e.handle('alerts',null,now).body.alerts[0].alert_id;e.handle('ack',{alert_id:id},now);
  assert.equal(e.handle('records',record('c'),now).body.results[0].code,'ALERT_CAPACITY_FULL');
  assert.equal(e.handle('alerts',null,now).body.acknowledged,1);
  const batch=e.handle('batch',{records:[record('d',.2),record('e')]},now);assert.equal(batch.http,207);assert.deepEqual(batch.body.results.map(r=>r.status),['normal','error']);
 });
 check('Alert identity survives dedup eviction and TTL, including conflict',()=>{
  const e=createEngine({...cfg,dedup_max_entries:1,dedup_ttl_ms:10});const a=record('a');e.handle('records',a,now);e.handle('records',record('b',.2),now);
  assert.equal(e.handle('records',a,now+11).body.results[0].status,'duplicate');assert.equal(e.handle('records',{...a,extra:'changed'},now+11).body.results[0].code,'ID_CONFLICT');assert.equal(e.handle('alerts',null,now).body.total,1);
 });
 check('Reinitialization loses alerts and acknowledgment (explicit RAM limitation)',()=>{
  const e=createEngine(cfg),a=record('restart');const id=e.handle('records',a,now).body.results[0].alert_id;e.handle('ack',{alert_id:id},now);
  const fresh=createEngine(cfg);assert.equal(fresh.handle('alerts',null,now).body.total,0);assert.equal(fresh.handle('ack',{alert_id:id},now).http,404);assert.equal(fresh.handle('records',a,now).body.results[0].status,'alert');
 });
 check('ACK copies cannot mutate internal state',()=>{const e=createEngine(cfg),id=e.handle('records',record('a'),now).body.results[0].alert_id;const ack=e.handle('ack',{alert_id:id},now);ack.body.alert.status='pending';assert.equal(e.handle('alerts',null,now).body.acknowledged,1);});
 report.passed=report.cases.filter(c=>c.pass).length;report.failed=report.cases.length-report.passed;
 fs.writeFileSync('results/workflow-unit.json',JSON.stringify(report,null,2));console.log(JSON.stringify({mode:report.mode,passed:report.passed,failed:report.failed,failures:report.cases.filter(c=>!c.pass)},null,2));process.exitCode=report.failed?1:0;
}
main().catch(e=>{console.error(e);process.exitCode=1;});

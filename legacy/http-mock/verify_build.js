// Validate actual generated Node-RED code, not only the separately imported engine.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const nodes=JSON.parse(fs.readFileSync('flow.json','utf8'));
const node=nodes.find(n=>n.id==='gh_engine'),context=new Map();
vm.runInNewContext(node.initialize,{context});
const engine=context.get('engine');assert.ok(engine);
const run=new Function('msg','context','node',node.func);
const message=url=>({req:{url,headers:{'content-type':'application/json'}},payload:undefined});
const page=run(message('/giang-aiot/v1/demo'),context,{});
const script=page[0].payload.match(/<script>([\s\S]*)<\/script>/)[1];new vm.Script(script);
const response=run({...message('/giang-aiot/v1/records'),payload:JSON.stringify({record_id:'build-check',source_id:'src01',timestamp:new Date().toISOString(),anomaly_score:.9})},context,{});
assert.equal(response[0].statusCode,200);assert.equal(response[0].payload.results[0].status,'alert');assert.equal(response[1].length,1);
const id=response[0].payload.results[0].alert_id;
const ack=run({...message('/giang-aiot/v1/ack'),payload:JSON.stringify({alert_id:id})},context,{});assert.equal(ack[0].payload.changed,true);
const routes=nodes.filter(n=>n.type==='http in').map(n=>n.method+' '+n.url);assert.equal(new Set(routes).size,8);
const result={mode:'offline generated flow validation; NOT Node-RED HTTP',script_syntax:true,embedded_engine:true,alert_output:true,ack_route:true,unique_routes:8};fs.writeFileSync('results/build-validation.json',JSON.stringify(result,null,2));console.log(result);

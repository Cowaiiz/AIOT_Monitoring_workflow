// Shared scenario runner; req is a real HTTP adapter or an explicitly labelled offline adapter.
// Expected results come from reviewed fixtures, never from createEngine.
async function runWorkflowTests(req, fixture, log=()=>{}, sleep=ms=>new Promise(r=>setTimeout(r,ms)), clock=()=>Date.now()) {
 const run='w'+clock()+'_'+Math.random().toString(36).slice(2,8),cases=[];let seq=0;
 const rec=(score=.2,source='src01',extra={})=>({record_id:run+'_'+(++seq),source_id:source,timestamp:new Date(clock()).toISOString(),anomaly_score:score,...extra});
 const check=(name,expected,ok,actual)=>{const c={name,expected,pass:!!ok,actual};cases.push(c);log((ok?'ĐẠT: ':'KHÔNG ĐẠT: ')+name);};
 const first=r=>r.body.results?.[0]||{};
 const before=await req('alerts');if(before.http!==200)throw Error('Không đọc được API cảnh báo');
 let expectedCreated=0;
 const rows=fixture.cases.map(c=>{let p=rec(c.score);if(c.kind==='missing')delete p.anomaly_score;if(c.kind==='unknown')p.source_id='unknown';if(c.kind==='stale')p.timestamp=new Date(clock()-3600000).toISOString();if(c.kind==='bad_time')p.timestamp='invalid';return p;});
 const mixed=await req('batch',{records:rows});
 check('Lô hỗn hợp seed 42','HTTP 207; đúng kết quả của cả 80 bản ghi',mixed.http===207&&mixed.body.results?.length===rows.length,mixed.http);
 fixture.cases.forEach((c,i)=>{const got=mixed.body.results?.[i];check('Mẫu '+c.id+' • '+c.kind,c.expected_code||c.expected_status,got?.status===c.expected_status&&(got?.code||null)===c.expected_code,got);if(c.expected_status==='alert')expectedCreated++;});
 const malformed=await req('records','{broken');check('JSON hỏng','400 INVALID_JSON',malformed.http===400&&malformed.body.code==='INVALID_JSON',malformed);
 const d=rec(.9),created=await req('records',d);expectedCreated++;
 const dup=await req('records',d),conflict=await req('records',{...d,anomaly_score:.1});
 check('Gửi lại bản ghi','duplicate; không tạo cảnh báo',first(dup).status==='duplicate',dup);
 check('Cùng ID khác nội dung','ID_CONFLICT',first(conflict).code==='ID_CONFLICT',conflict);
 const old=await req('records',rec(.2,'src01',{timestamp:new Date(Date.parse(d.timestamp)-1).toISOString()}));check('Đến sai thứ tự','OUT_OF_ORDER',first(old).code==='OUT_OF_ORDER',old);
 const parallel=await Promise.all(['src02','src03','src04','src05'].map(s=>req('records',rec(.95,s))));expectedCreated+=4;
 check('Bốn nguồn đồng thời','4 alert',parallel.every(r=>first(r).status==='alert'),parallel);
 const same=rec(.9,'src06'),retries=await Promise.all(Array.from({length:4},()=>req('records',same)));expectedCreated++;
 check('Bốn retry đồng thời','1 alert + 3 duplicate',retries.filter(r=>first(r).status==='alert').length===1&&retries.filter(r=>first(r).status==='duplicate').length===3,retries);
 const delayed=rec(.9,'src07');let timeout=false;
 try{await req('records',delayed,{timeout:20,headers:{'x-demo-delay-ms':'200'}});}catch(e){timeout=e.name==='AbortError'||e.name==='TimeoutError';}
 await sleep(300);const retry=await req('records',delayed);expectedCreated++;
 check('Timeout có chủ đích rồi retry','timeout + duplicate',timeout&&first(retry).status==='duplicate',retry);
 const id=first(created).alert_id,ack=await req('ack',{alert_id:id}),again=await req('ack',{alert_id:id});
 check('Xác nhận lần đầu','changed=true; acknowledged',ack.body.changed===true&&ack.body.alert?.status==='acknowledged',ack);
 check('Xác nhận lặp','changed=false; giữ thời gian ban đầu',again.body.changed===false&&again.body.alert?.acknowledged_at===ack.body.alert?.acknowledged_at,again);
 const id2=first(parallel[0]).alert_id,acks=await Promise.all(Array.from({length:4},()=>req('ack',{alert_id:id2})));
 check('Xác nhận đồng thời','đúng 1 thay đổi; cùng timestamp',acks.filter(a=>a.body.changed===true).length===1&&new Set(acks.map(a=>a.body.alert?.acknowledged_at)).size===1,acks);
 const unknown=await req('ack',{alert_id:'does-not-exist'});check('Mã cảnh báo không tồn tại','404 ALERT_NOT_FOUND',unknown.http===404&&unknown.body.code==='ALERT_NOT_FOUND',unknown);
 const after=await req('alerts'),mine=after.body.alerts.filter(a=>a.record_id.startsWith(run));
 check('Đếm cảnh báo thực tế','tạo '+expectedCreated+'; 2 acknowledged; còn lại pending',mine.length===expectedCreated&&mine.filter(a=>a.status==='acknowledged').length===2&&after.body.total-before.body.total===expectedCreated,{created:mine.length,acknowledged:mine.filter(a=>a.status==='acknowledged').length});
 await req('records',rec(.2,'src10'));log('Đợi 31 giây để kiểm tra nguồn ngừng gửi…');await sleep(31050);
 const silent=(await req('sources')).body.sources.find(s=>s.source_id==='src10');
 await req('records',rec(.2,'src10'));const active=(await req('sources')).body.sources.find(s=>s.source_id==='src10');
 check('Nguồn ngừng rồi gửi lại','silent → active',silent.state==='silent'&&active.state==='active',{before:silent.state,after:active.state});
 return {run,seed:fixture.seed,mode:'workflow integration',passed:cases.filter(c=>c.pass).length,failed:cases.filter(c=>!c.pass).length,cases};
}
if(typeof module!=='undefined')module.exports={runWorkflowTests};

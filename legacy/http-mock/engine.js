function createEngine(cfg) {
 const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
 if(!cfg||!cfg.thresholds||!Object.keys(cfg.thresholds).length)throw Error('Invalid configuration');
 for(const [k,v] of Object.entries(cfg.thresholds))if(!/^[A-Za-z0-9_-]{1,64}$/.test(k)||typeof v!=='number'||!Number.isFinite(v)||v<0||v>1)throw Error('Invalid threshold');
 for(const k of ['max_age_ms','future_tolerance_ms','dedup_ttl_ms','dedup_max_entries','max_batch','max_body_bytes','event_capacity','offline_after_ms'])if(!Number.isSafeInteger(cfg[k])||cfg[k]<=0)throw Error('Invalid limit '+k);
 if(!Number.isSafeInteger(cfg.alert_capacity)||cfg.alert_capacity<=0)throw Error('Invalid alert_capacity');
 const seen=new Map(),sources=new Map(),events=[],alerts=new Map(),alertRecords=new Map();
 // Canonical JSON includes extra fields: reordered keys are equal, changed content conflicts.
 const canonical=v=>JSON.stringify(v===null||typeof v!=='object'?v:Array.isArray(v)?v.map(x=>JSON.parse(canonical(x))):Object.fromEntries(Object.keys(v).sort().map(k=>[k,JSON.parse(canonical(v[k]))])));
 const m={requests:0,records:0,accepted:0,normal:0,alert:0,duplicate:0,data_errors:0,request_errors:0,internal_errors:0,capacity_errors:0,events:0,evictions:0};let sequence=0;
 function prune(now){for(const [key,item] of seen){if(now-item.at<cfg.dedup_ttl_ms)break;seen.delete(key);}}
 function ingest(p,now){
 const err=code=>{m.data_errors++;return {status:'error',kind:'data',code,record_id:p&&typeof p.record_id==='string'?p.record_id:null};};
 if(!p||typeof p!=='object'||Array.isArray(p))return err('INVALID_RECORD');
 for(const k of ['record_id','source_id','timestamp','anomaly_score'])if(!own(p,k))return err('MISSING_FIELD_'+k);
 for(const k of ['record_id','source_id'])if(typeof p[k]!=='string'||!/^[A-Za-z0-9_-]{1,64}$/.test(p[k]))return err('INVALID_'+k.toUpperCase());
 if(!own(cfg.thresholds,p.source_id))return err('UNKNOWN_SOURCE');
 if(typeof p.anomaly_score!=='number'||!Number.isFinite(p.anomaly_score)||p.anomaly_score<0||p.anomaly_score>1)return err('INVALID_SCORE');
 if(typeof p.timestamp!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(p.timestamp))return err('INVALID_TIMESTAMP');
 const ts=Date.parse(p.timestamp);if(!Number.isFinite(ts)||new Date(ts).toISOString()!==p.timestamp)return err('INVALID_TIMESTAMP');
 const key=JSON.stringify([p.source_id,p.record_id]),fingerprint=canonical(p);
 if(seen.has(key)||alertRecords.has(key)){const previous=seen.get(key)||alertRecords.get(key);if(previous.fingerprint!==fingerprint)return err('ID_CONFLICT');m.duplicate++;return {status:'duplicate',record_id:p.record_id,source_id:p.source_id,original:previous.result};}
 if(now-ts>cfg.max_age_ms)return err('STALE_RECORD');if(ts-now>cfg.future_tolerance_ms)return err('FUTURE_RECORD');
 const prev=sources.get(p.source_id);if(prev&&ts<prev.watermark)return err('OUT_OF_ORDER');
 const threshold=cfg.thresholds[p.source_id],status=p.anomaly_score>=threshold?'alert':'normal';
 const result={status,record_id:p.record_id,source_id:p.source_id,timestamp:p.timestamp,anomaly_score:p.anomaly_score,threshold,simulated:true};
 if(status==='alert'){
   if(alerts.size>=cfg.alert_capacity){m.capacity_errors++;return {status:'error',kind:'capacity',code:'ALERT_CAPACITY_FULL',record_id:p.record_id,source_id:p.source_id,retryable:true};}
   result.event_id='sim:'+p.source_id+':'+p.record_id;result.alert_id=result.event_id;
   const alert={...result,status:'pending',created_at:new Date(now).toISOString(),acknowledged_at:null};
   alerts.set(result.alert_id,alert);alertRecords.set(key,{fingerprint,result});
   events.push({...result,event_type:'anomaly_detected',received_at:alert.created_at,sequence:++sequence});if(events.length>cfg.event_capacity)events.shift();m.events++;
 }
 sources.set(p.source_id,{watermark:ts,last_valid_at:now});seen.set(key,{at:now,fingerprint,result});while(seen.size>cfg.dedup_max_entries){seen.delete(seen.keys().next().value);m.evictions++;}m.accepted++;m[status]++;return result;
 }
 return {handle(path,payload,now=Date.now()){
 prune(now);
 if(path==='alerts'){const list=[...alerts.values()].map(a=>({...a}));return {http:200,body:{alerts:list,total:list.length,pending:list.filter(a=>a.status==='pending').length,acknowledged:list.filter(a=>a.status==='acknowledged').length,capacity:cfg.alert_capacity,storage:'RAM; restart/redeploy resets state; no automatic eviction'}};}
 if(path==='metrics')return {http:200,body:{...m,dedup_entries:seen.size,event_entries:events.length,config_version:cfg.version}};
 if(path==='events')return {http:200,body:{events:[...events],total_events:m.events,capacity:cfg.event_capacity}};
 if(path==='sources')return {http:200,body:{sources:Object.keys(cfg.thresholds).map(id=>({source_id:id,threshold:cfg.thresholds[id],...sources.get(id),state:!sources.has(id)?'unseen':now-sources.get(id).last_valid_at>cfg.offline_after_ms?'silent':'active'}))}};
 m.requests++;const fail=(http,code,kind='request')=>{m.request_errors++;return {http,body:{status:'error',kind,code}};};
 try{if(typeof payload==='string'){if(payload.length>cfg.max_body_bytes)return fail(413,'BODY_TOO_LARGE');try{payload=JSON.parse(payload);}catch{return fail(400,'INVALID_JSON');}}
 if(path==='ack'){
   if(!payload||typeof payload.alert_id!=='string')return fail(400,'INVALID_ALERT_ID');
   const alert=alerts.get(payload.alert_id);if(!alert)return fail(404,'ALERT_NOT_FOUND');
   const changed=alert.status==='pending';if(changed){alert.status='acknowledged';alert.acknowledged_at=new Date(now).toISOString();}
   return {http:200,body:{changed,alert:{...alert}}};
 }
 let batch;if(path==='records')batch=[payload];else if(path==='batch'){if(!payload||!Array.isArray(payload.records)||!payload.records.length)return fail(400,'INVALID_BATCH');if(payload.records.length>cfg.max_batch)return fail(413,'BATCH_TOO_LARGE');batch=payload.records;}else return fail(404,'NOT_FOUND');
 const results=batch.map(p=>{m.records++;return ingest(p,now);}),errors=results.filter(r=>r.status==='error').length;
 return {http:path==='records'?(errors?(results[0].kind==='capacity'?503:422):200):(errors?207:200),body:{results,summary:{records:results.length,errors,accepted:results.filter(r=>['normal','alert'].includes(r.status)).length,duplicates:results.filter(r=>r.status==='duplicate').length}}};
 }catch(e){m.internal_errors++;return {http:500,body:{status:'error',kind:'internal',code:'INTERNAL_ERROR'}};}
 }};
}

if(typeof module!=="undefined") module.exports={createEngine};

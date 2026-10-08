"""Validated, asset-local ML anomaly detection and evidence investigation."""
import csv, io, json, math, hashlib
from datetime import datetime, timezone
import numpy as np
from sklearn.ensemble import IsolationForest

DEFAULT_HYPOTHESES=[
 {'id':'capacity','name':'Capacity or resource bottleneck','supports':['RESOURCE_PRESSURE','QUEUE_BUILDUP'],'contradicts':['RESOURCE_HEALTHY'],'metrics':['latency_ms','queue_depth','cpu_pct'],'next_check':'Inspect resource utilization and queue ownership during the affected interval.'},
 {'id':'dependency','name':'Upstream dependency degradation','supports':['DEPENDENCY_TIMEOUT','UPSTREAM_ERROR'],'contradicts':['DEPENDENCY_HEALTHY'],'metrics':['latency_ms','error_rate'],'next_check':'Correlate upstream request IDs, provider status and downstream failures.'},
 {'id':'change','name':'Configuration or operating-mode change','supports':['CONFIG_CHANGED','DEPLOYMENT'],'contradicts':['CONFIG_UNCHANGED'],'metrics':[],'next_check':'Compare configuration and operating mode before and after the change.'},
 {'id':'hardware','name':'Physical subsystem issue','supports':['DEVICE_FAULT','POWER_ALARM','THERMAL_ALARM'],'contradicts':['DEVICE_SELFTEST_OK'],'metrics':['temperature_c','voltage_v'],'next_check':'Obtain device diagnostic codes or a qualified inspection; telemetry alone may not locate a damaged component.'},
 {'id':'data','name':'Measurement or data-quality issue','supports':['SENSOR_STALE','CLOCK_DRIFT','MEASUREMENT_FAULT'],'contradicts':['MEASUREMENT_VERIFIED'],'metrics':[],'next_check':'Verify timestamps, units, collection health and the original measurement source.'}
]

def stamp(s):
 if not isinstance(s,str): raise ValueError('timestamp must be a string')
 d=datetime.fromisoformat(s.replace('Z','+00:00'))
 if d.tzinfo is None: raise ValueError('Timestamps need timezone offsets, such as +00:00.')
 return d.astimezone(timezone.utc)

def bounded_text(v,label,limit=200):
 if not isinstance(v,str) or not v.strip() or len(v)>limit: raise ValueError(f'{label} must be nonempty text, maximum {limit} characters.')
 return v.strip()

def validate(data):
 if not isinstance(data,dict): raise ValueError('Input must be a JSON object.')
 clean={'name':bounded_text(data.get('name'),'name'),'asset_id':bounded_text(data.get('asset_id'),'asset_id'),'source':bounded_text(data.get('source','Uploaded data'),'source'),'synthetic':data.get('synthetic') is True}
 specs=data.get('metrics'); readings=data.get('readings'); events=data.get('events',[])
 if not isinstance(specs,list) or not 1<=len(specs)<=12: raise ValueError('Provide 1–12 metric definitions.')
 clean['metrics']=[{'name':bounded_text(m.get('name'),'metric name',60),'unit':bounded_text(m.get('unit'),'unit',30)} for m in specs if isinstance(m,dict)]
 if len(clean['metrics'])!=len(specs): raise ValueError('Metric definitions must be objects.')
 names=[m['name'] for m in clean['metrics']]
 if len(set(names))!=len(names): raise ValueError('Metric names must be unique.')
 if not isinstance(readings,list) or not 65<=len(readings)<=10000: raise ValueError('Provide 65–10,000 readings: at least 60 baseline and 5 current.')
 clean['readings']=[]; ids=set(); times=set()
 for r in readings:
  if not isinstance(r,dict): raise ValueError('Reading must be an object.')
  rid=bounded_text(r.get('id'),'reading id',80); dt=stamp(r.get('timestamp')); period=r.get('period'); values=r.get('values')
  if rid in ids or dt in times: raise ValueError('Reading IDs and timestamps must be unique within an asset dataset.')
  ids.add(rid);times.add(dt)
  if period not in ('baseline','current'): raise ValueError('period must be baseline or current.')
  if not isinstance(values,dict) or set(values)!=set(names): raise ValueError('Every reading must contain exactly the declared metrics.')
  for n,v in values.items():
   if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or abs(v)>1e12: raise ValueError(f'{n} must be a finite number within ±1e12.')
  clean['readings'].append({'id':rid,'timestamp':dt.isoformat(),'period':period,'values':values})
 clean['readings'].sort(key=lambda r:r['timestamp'])
 base=[r for r in clean['readings'] if r['period']=='baseline']; current=[r for r in clean['readings'] if r['period']=='current']
 if len(base)<60 or len(current)<5: raise ValueError('At least 60 baseline and 5 current readings are required.')
 if base[-1]['timestamp']>=current[0]['timestamp']: raise ValueError('Baseline must precede all current observations. Training on current observations would leak test data.')
 if not isinstance(events,list) or len(events)>5000: raise ValueError('Events must be an array with at most 5,000 entries.')
 clean['events']=[];ids=set(); reading_ids={r['id'] for r in clean['readings']}
 for e in events:
  if not isinstance(e,dict):raise ValueError('Event must be an object.')
  eid=bounded_text(e.get('id'),'event id',80)
  if eid in ids:raise ValueError('Event IDs must be unique.')
  ids.add(eid); rid=e.get('reading_id')
  if rid is not None and rid not in reading_ids: raise ValueError('Event reading_id must refer to a reading in this dataset.')
  asset=bounded_text(e.get('asset_id',clean['asset_id']),'event asset_id')
  clean['events'].append({'id':eid,'timestamp':stamp(e.get('timestamp')).isoformat(),'category':bounded_text(e.get('category'),'category',80),'message':bounded_text(e.get('message'),'message',1500),'source':bounded_text(e.get('source','Event log'),'source'),'asset_id':asset,'reading_id':rid})
 hypotheses=data.get('hypotheses',DEFAULT_HYPOTHESES)
 if not isinstance(hypotheses,list) or not 2<=len(hypotheses)<=10:raise ValueError('Provide 2–10 competing hypotheses.')
 clean['hypotheses']=[];hids=set()
 for h in hypotheses:
  if not isinstance(h,dict):raise ValueError('Hypothesis must be an object.')
  out={k:bounded_text(h.get(k),k,500 if k=='next_check' else 100) for k in ['id','name','next_check']}
  if out['id'] in hids:raise ValueError('Hypothesis IDs must be unique.')
  hids.add(out['id'])
  for k in ['supports','contradicts','metrics']:
   v=h.get(k,[])
   if not isinstance(v,list) or len(v)>30 or any(not isinstance(x,str) or not x or len(x)>80 for x in v):raise ValueError('Hypothesis signal lists are invalid.')
   out[k]=list(dict.fromkeys(v))
  if set(out['supports']) & set(out['contradicts']):raise ValueError('The same signal cannot support and contradict one hypothesis.')
  clean['hypotheses'].append(out)
 return clean

def from_csv(name,asset_id,csv_text,events_text,units):
 rows=list(csv.DictReader(io.StringIO(csv_text)))
 if not rows:raise ValueError('CSV is empty.')
 metadata={'id','timestamp','period'}
 if not metadata.issubset(rows[0]):raise ValueError('CSV needs id,timestamp,period plus numeric metric columns.')
 names=[k for k in rows[0] if k not in metadata]
 if set(names)!=set(units):raise ValueError('Units JSON must map every metric column to a unit.')
 readings=[]
 for r in rows:
  readings.append({**{k:r[k] for k in metadata},'values':{k:float(r[k]) for k in names}})
 events=[json.loads(line) for line in events_text.splitlines() if line.strip()]
 return {'name':name,'asset_id':asset_id,'source':'CSV + JSONL upload','metrics':[{'name':k,'unit':units[k]} for k in names],'readings':readings,'events':events}

def investigate(d):
 names=[m['name'] for m in d['metrics']];base=[r for r in d['readings'] if r['period']=='baseline'];current=[r for r in d['readings'] if r['period']=='current'];split=int(len(base)*.8)
 matrix=lambda rows:np.asarray([[r['values'][n] for n in names] for r in rows],dtype=float)
 train=matrix(base[:split]);cal=matrix(base[split:]);x=matrix(current)
 model=IsolationForest(n_estimators=160,contamination='auto',random_state=42,n_jobs=1).fit(train)
 threshold=float(np.quantile(model.score_samples(cal),.02));scores=model.score_samples(x);ml_flags=scores<threshold
 med=np.median(train,axis=0);scale=np.maximum(1.4826*np.median(np.abs(train-med),axis=0),np.maximum(np.abs(med)*.01,.001))
 # Isolation Forest can miss a large shift in just one dimension. A robust
 # statistical safeguard, explicitly reported separately, catches that case.
 deviation_flags=np.any(np.abs((x-med)/scale)>6,axis=1)
 flags=ml_flags|deviation_flags
 fraction=float(np.mean(flags));anomaly=fraction>=.2 and int(flags.sum())>=3
 changes=[]
 for i,m in enumerate(d['metrics']):
  current_med=float(np.median(x[:,i]));deviation=float((current_med-med[i])/scale[i]);changes.append({**m,'baseline':round(float(med[i]),3),'current':round(current_med,3),'deviation':round(deviation,2),'shifted':abs(deviation)>=3})
 outliers={r['id'] for r,f in zip(current,flags) if f};start=current[0]['timestamp'];end=current[-1]['timestamp'];evidence=[];rankings=[]
 trace=[{'tool':'baseline.fit','detail':f'Fitted Isolation Forest to {split} earlier readings of {d["asset_id"]}; calibrated threshold on {len(cal)} separate baseline readings.'},{'tool':'current.score','detail':f'{int(flags.sum())}/{len(current)} current readings flagged by ML or the 6-MAD statistical safeguard. Investigation requires ≥20% and ≥3 flagged observations.'}]
 if anomaly:
  trace.append({'tool':'events.correlate','detail':'Anomaly triggered event inspection. Matched asset, time window and optional reading IDs; retained ignored evidence for review.'})
  for e in d['events']:
   relevant=True;relation='Same asset and current interval';factor=.6
   if e['asset_id']!=d['asset_id']:relevant=False;relation='Different asset'
   elif not start<=e['timestamp']<=end:relevant=False;relation='Outside current interval'
   elif e['reading_id']:
    if e['reading_id'] in outliers:factor=1;relation='Linked anomalous reading'
    else:factor=.25;relation='Linked non-anomalous reading (weak support)'
   evidence.append({**e,'relevant':relevant,'relation':relation,'factor':factor if relevant else 0})
  for h in d['hypotheses']:
   supports=[];contradicts=[];buckets={}
   for e in evidence:
    if not e['relevant']:continue
    sign=1 if e['category'] in h['supports'] else (-1 if e['category'] in h['contradicts'] else 0)
    if not sign:continue
    v=round(sign*35*e['factor'],1)
    (supports if sign==1 else contradicts).append({'id':e['id'],'contribution':v})
    key=e['category'];buckets[key]=max(buckets.get(key,0),v) if sign==1 else min(buckets.get(key,0),v)
   matching=[m['name'] for m in changes if m['shifted'] and m['name'] in h['metrics']]
   metric_score=min(20,len(matching)*10);score=round(min(100,max(0,sum(buckets.values())+metric_score)),1)
   rankings.append({**h,'score':score,'support':supports,'counterevidence':contradicts,'shifted_metrics':matching,'score_breakdown':{'deduplicated_signals':buckets,'metric_alignment':metric_score}})
  rankings.sort(key=lambda h:(-h['score'],h['id']));lead=rankings[0];margin=lead['score']-rankings[1]['score'];strong=lead['score']>=50 and margin>=15 and len({next(e['category'] for e in evidence if e['id']==s['id']) for s in lead['support']})>=2
  status='Leading hypothesis' if strong else 'Needs more evidence'
  summary=f'{lead["name"]} is the leading explanation. Validate it with the recommended check.' if strong else 'An unusual pattern was detected, but the evidence does not distinguish a reliable cause.'
  gaps=[]
  if not any(e['relevant'] for e in evidence):gaps.append('No correlated events: add logs, error codes or timestamped operator observations.')
  if not strong:gaps.append('Competing explanations remain: collect independent evidence before assigning a cause.')
  if any(h['id']=='hardware' and h['score']>0 for h in rankings):gaps.append('Physical damage cannot be localized without component-specific diagnostics or inspection.')
  trace.append({'tool':'hypotheses.compare','detail':f'Compared {len(rankings)} configured hypotheses; deduplicated signal types and subtracted contradictions.'})
  trace.append({'tool':'investigation.decide','detail':lead['next_check'] if strong else 'Abstain from a definite diagnosis and request missing evidence.'})
 else:status='Within learned baseline';summary='The current interval did not meet the investigation threshold. This does not certify that the equipment is healthy.';gaps=[]
 series=[{'id':r['id'],'timestamp':r['timestamp'],'values':r['values'],'period':r['period'],'anomaly':bool(f),'ml_flagged':bool(m),'statistical_flagged':bool(s)} for r,f,m,s in zip(current,flags,ml_flags,deviation_flags)]
 context=base[-40:]
 return {'status':status,'summary':summary,'anomaly':anomaly,'asset_id':d['asset_id'],'name':d['name'],'synthetic':d['synthetic'],'model':{'name':'Isolation Forest','training_rows':split,'calibration_rows':len(cal),'threshold':round(threshold,6),'random_seed':42,'fingerprint':hashlib.sha256(json.dumps(base,sort_keys=True).encode()).hexdigest()[:16]},'current_count':len(current),'flagged_count':int(flags.sum()),'ml_flagged_count':int(ml_flags.sum()),'statistical_flagged_count':int(deviation_flags.sum()),'flagged_fraction':round(fraction,3),'metrics':changes,'series':[dict(r,anomaly=False) for r in context]+series,'rankings':rankings,'evidence':evidence,'trace':trace,'gaps':gaps,'caution':'Model scores are not fault probabilities. Ranked causes are hypotheses, not confirmed damage.'}

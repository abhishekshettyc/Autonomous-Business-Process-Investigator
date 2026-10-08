"""Live, instrumented local test workload. No external hardware connection."""
import json,random,threading,time,uuid
from datetime import datetime,timezone
import database as db
from core import investigate

def now():return datetime.now(timezone.utc).isoformat()
HYPOTHESES=[
 {'id':'delay','name':'Delay in the local worker stage','supports':['DELAY_ENTERED','DELAY_COMPLETED'],'contradicts':['WORKER_NORMAL'],'metrics':['duration_ms'],'next_check':'Inspect the worker timing events. Set Normal to remove the controlled delay and watch the rolling window recover.'},
 {'id':'timeout','name':'Test upstream timeout','supports':['UPSTREAM_TIMEOUT','REQUEST_FAILED'],'contradicts':['REQUEST_SUCCEEDED'],'metrics':['error_count'],'next_check':'Inspect the failed request event. Set Normal to stop the test timeout and verify successful requests.'},
 {'id':'database','name':'Database query failure','supports':['DB_ERROR'],'contradicts':['DB_QUERY_OK'],'metrics':[],'next_check':'Inspect SQL query errors and database availability. Do not infer a database fault from total duration alone.'}
]

class LiveRunner:
 def __init__(self):
  self.lock=threading.RLock();self.stop_event=threading.Event();self.thread=None;self.session=None;self.mode='normal'
 def initialize(self):
  # A crashed or stopped server cannot still be producing readings.
  with db.connect() as c:c.execute("UPDATE live_sessions SET state='stopped',mode='normal' WHERE state IN ('warming','running')")
 def start(self):
  with self.lock:
   if self.thread and self.thread.is_alive():return self.status()
   did=db.insert({'name':'Live local workload '+datetime.now().strftime('%H:%M:%S'),'asset_id':'LOCAL-WORKER','source':'Measured local test workload','synthetic':False,'metrics':[{'name':'duration_ms','unit':'ms'},{'name':'error_count','unit':'count'}],'hypotheses':HYPOTHESES,'readings':[],'events':[]})
   sid=uuid.uuid4().hex;self.session=sid;self.mode='normal';self.stop_event=threading.Event()
   with db.connect() as c:c.execute('INSERT INTO live_sessions(id,dataset_id,created,state,mode,last_error) VALUES(?,?,?,?,?,?)',(sid,did,now(),'warming','normal',None))
   self.thread=threading.Thread(target=self._run,args=(sid,did),daemon=True);self.thread.start();return self.status()
 def set_mode(self,mode):
  if mode not in ('normal','delay','timeout'):raise ValueError('Mode must be normal, delay or timeout.')
  with self.lock:
   s=self.status()
   if s.get('state')!='running':raise ValueError('Wait for baseline collection to finish and the session to be running.')
   self.mode=mode
   with db.connect() as c:
    c.execute('UPDATE live_sessions SET mode=? WHERE id=?',(mode,self.session))
    c.execute('INSERT INTO live_actions VALUES(?,?,?,?)',(uuid.uuid4().hex,self.session,now(),mode))
   return self.status()
 def stop(self):
  self.stop_event.set();thread=self.thread
  if thread:thread.join(timeout=8)
  return self.status()
 def status(self):
  with db.connect() as c:
   s=c.execute('SELECT * FROM live_sessions ORDER BY created DESC LIMIT 1').fetchone()
   if not s:return {'state':'not_started','mode':'normal','baseline_count':0,'current_count':0,'report':None,'rows':[],'events':[]}
   s=dict(s);did=s['dataset_id']
   counts={r['period']:r['n'] for r in c.execute('SELECT period,count(*) n FROM readings WHERE dataset_id=? GROUP BY period',(did,))}
   s['baseline_count']=counts.get('baseline',0);s['current_count']=counts.get('current',0)
   s['rows']=[dict(r) for r in c.execute('SELECT * FROM reading_values WHERE dataset_id=? ORDER BY timestamp DESC LIMIT 25',(did,))]
   s['events']=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM events WHERE dataset_id=? ORDER BY rowid DESC LIMIT 10',(did,))]
   last=c.execute('SELECT result FROM investigations WHERE dataset_id=? ORDER BY created DESC LIMIT 1',(did,)).fetchone();s['report']=json.loads(last['result']) if last else None
   return s
 def _measure(self,mode,sequence,rng):
  # The fixed service budget and small jitter are part of a controlled test workload.
  # Values written below are measured with a monotonic timer, not precomputed metrics.
  started=time.perf_counter();time.sleep(.025+rng.uniform(0,.008));signals=[];errors=0
  with db.connect() as c:c.execute('SELECT COUNT(*) FROM datasets').fetchone()
  signals.append(('DB_QUERY_OK','The local SELECT query completed successfully.'))
  if mode=='delay':
   signals.append(('DELAY_ENTERED','Worker entered the controlled 300 ms delay stage.'))
   before=time.perf_counter();time.sleep(.3)
   signals.append(('DELAY_COMPLETED',f'Delay stage completed in {(time.perf_counter()-before)*1000:.2f} ms.'))
  elif mode=='timeout':
   try:
    time.sleep(.12);raise TimeoutError('Controlled timeout in test dependency stub')
   except TimeoutError as e:
    errors=1;signals.extend([('UPSTREAM_TIMEOUT',str(e)),('REQUEST_FAILED','Local test operation ended with a timeout.')])
  if mode=='normal':signals.extend([('WORKER_NORMAL','Worker completed without an injected delay.'),('REQUEST_SUCCEEDED','Local test operation succeeded.')])
  return {'duration_ms':round((time.perf_counter()-started)*1000,3),'error_count':errors},signals
 def _tick(self,sid,did,sequence,period,mode,rng):
  values,signals=self._measure(mode,sequence,rng);ts=now();rid=f'LIVE-{sequence:06}'
  with db.connect() as c:
   c.execute('INSERT INTO readings VALUES(?,?,?,?,?)',(did,rid,ts,period,json.dumps(values)))
   if period=='current':
    for i,(category,message) in enumerate(signals):
     eid=f'{rid}-E{i}';e={'id':eid,'timestamp':ts,'asset_id':'LOCAL-WORKER','reading_id':rid,'category':category,'message':message,'source':'Instrumented local worker'}
     c.execute('INSERT INTO events VALUES(?,?,?)',(did,eid,json.dumps(e)))
  return rid
 def analyze(self,did):
  d=db.get(did);base=[r for r in d['readings'] if r['period']=='baseline'];current=[r for r in d['readings'] if r['period']=='current'][-10:]
  if len(base)<60 or len(current)<5:return None
  d['readings']=base+current;ids={r['id'] for r in current};d['events']=[e for e in d['events'] if e.get('reading_id') in ids]
  report=investigate(d);report.update(live=True,data_origin='Measured local test workload; deliberately controlled faults',window_size=len(current),last_reading_id=current[-1]['id'])
  return db.save_result(did,report)
 def _run(self,sid,did):
  rng=random.Random(42);sequence=0
  try:
   # Collect actual normal measurements now, rather than generating past timestamps.
   for sequence in range(60):
    if self.stop_event.is_set():return
    self._tick(sid,did,sequence,'baseline','normal',rng)
    if self.stop_event.wait(.12):return
   with db.connect() as c:c.execute("UPDATE live_sessions SET state='running' WHERE id=?",(sid,))
   sequence=60
   while not self.stop_event.is_set():
    with self.lock:mode=self.mode
    self._tick(sid,did,sequence,'current',mode,rng);self.analyze(did);sequence+=1
    if self.stop_event.wait(2):break
  except Exception as exc:
   with db.connect() as c:c.execute("UPDATE live_sessions SET state='error',last_error=? WHERE id=?",(str(exc)[:500],sid))
  finally:
   with db.connect() as c:c.execute("UPDATE live_sessions SET state='stopped' WHERE id=? AND state!='error'",(sid,))

runner=LiveRunner()

import sqlite3,json,uuid,os
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime,timezone
DB=Path(os.getenv('ROOTLENS_DB',str(Path(__file__).parent/'storage'/'rootlens.db')))
@contextmanager
def connect():
 DB.parent.mkdir(parents=True,exist_ok=True)
 c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
 try:
  with c:yield c
 finally:c.close()

def init():
 with connect() as c:
  c.execute('PRAGMA journal_mode=WAL')
  c.executescript('''CREATE TABLE IF NOT EXISTS datasets(id TEXT PRIMARY KEY,name TEXT,asset_id TEXT,created TEXT,source TEXT,synthetic INTEGER,metrics TEXT,hypotheses TEXT);
CREATE TABLE IF NOT EXISTS readings(dataset_id TEXT REFERENCES datasets(id),id TEXT,timestamp TEXT,period TEXT,values_json TEXT,PRIMARY KEY(dataset_id,id));
CREATE TABLE IF NOT EXISTS events(dataset_id TEXT REFERENCES datasets(id),id TEXT,payload TEXT,PRIMARY KEY(dataset_id,id));
CREATE TABLE IF NOT EXISTS investigations(id TEXT PRIMARY KEY,dataset_id TEXT REFERENCES datasets(id),created TEXT,status TEXT,result TEXT);
CREATE INDEX IF NOT EXISTS readings_dataset ON readings(dataset_id,period,timestamp);
CREATE TABLE IF NOT EXISTS live_sessions(id TEXT PRIMARY KEY,dataset_id TEXT REFERENCES datasets(id),created TEXT,state TEXT,mode TEXT,last_error TEXT);
CREATE TABLE IF NOT EXISTS live_actions(id TEXT PRIMARY KEY,session_id TEXT REFERENCES live_sessions(id),timestamp TEXT,mode TEXT);
CREATE VIEW IF NOT EXISTS reading_values AS SELECT dataset_id,id,timestamp,period,
 json_extract(values_json,'$.duration_ms') AS duration_ms,
 json_extract(values_json,'$.error_count') AS error_count,values_json FROM readings;''')

def insert(d):
 did=uuid.uuid4().hex
 with connect() as c:
  c.execute('INSERT INTO datasets VALUES(?,?,?,?,?,?,?,?)',(did,d['name'],d['asset_id'],datetime.now(timezone.utc).isoformat(),d['source'],int(d['synthetic']),json.dumps(d['metrics']),json.dumps(d['hypotheses'])))
  c.executemany('INSERT INTO readings VALUES(?,?,?,?,?)',[(did,r['id'],r['timestamp'],r['period'],json.dumps(r['values'])) for r in d['readings']])
  c.executemany('INSERT INTO events VALUES(?,?,?)',[(did,e['id'],json.dumps(e)) for e in d['events']])
 return did

def get(did):
 with connect() as c:
  row=c.execute('SELECT * FROM datasets WHERE id=?',(did,)).fetchone()
  if not row:return None
  d=dict(row);d['metrics']=json.loads(d['metrics']);d['hypotheses']=json.loads(d['hypotheses']);d['synthetic']=bool(d['synthetic'])
  d['readings']=[{'id':r['id'],'timestamp':r['timestamp'],'period':r['period'],'values':json.loads(r['values_json'])} for r in c.execute('SELECT * FROM readings WHERE dataset_id=? ORDER BY timestamp',(did,))]
  d['events']=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM events WHERE dataset_id=?',(did,))];return d

def datasets():
 with connect() as c:return [dict(r) for r in c.execute('SELECT d.*,(SELECT count(*) FROM readings r WHERE r.dataset_id=d.id) AS reading_count,(SELECT count(*) FROM events e WHERE e.dataset_id=d.id) AS event_count FROM datasets d ORDER BY created DESC LIMIT 100')]

def save_result(did,r):
 rid=uuid.uuid4().hex;r={**r,'id':rid,'dataset_id':did,'created':datetime.now(timezone.utc).isoformat()}
 with connect() as c:c.execute('INSERT INTO investigations VALUES(?,?,?,?,?)',(rid,did,r['created'],r['status'],json.dumps(r)))
 return r

def history():
 with connect() as c:return [dict(r) for r in c.execute('SELECT i.id,i.dataset_id,i.created,i.status,d.name,d.asset_id FROM investigations i JOIN datasets d ON d.id=i.dataset_id ORDER BY i.created DESC LIMIT 100')]

def result(rid):
 with connect() as c:
  r=c.execute('SELECT result FROM investigations WHERE id=?',(rid,)).fetchone();return json.loads(r['result']) if r else None

EXPLORER_QUERIES={
 'readings': "SELECT id,timestamp,period,duration_ms,error_count FROM reading_values WHERE dataset_id=? ORDER BY timestamp DESC LIMIT 50",
 'baseline': "SELECT id,timestamp,period,duration_ms,error_count FROM reading_values WHERE dataset_id=? AND period='baseline' ORDER BY timestamp DESC LIMIT 60",
 'events': "SELECT id,json_extract(payload,'$.timestamp') AS timestamp,json_extract(payload,'$.category') AS category,json_extract(payload,'$.message') AS message FROM events WHERE dataset_id=? ORDER BY rowid DESC LIMIT 50",
 'investigations': "SELECT id,created,status,json_extract(result,'$.flagged_count') AS flagged_count,json_extract(result,'$.current_count') AS current_count FROM investigations WHERE dataset_id=? ORDER BY created DESC LIMIT 30"
}
def explore(view,did=None):
 if view not in EXPLORER_QUERIES:raise ValueError('Unknown database view.')
 with connect() as c:
  if did is None:
   latest=c.execute('SELECT dataset_id FROM live_sessions ORDER BY created DESC LIMIT 1').fetchone();did=latest[0] if latest else ''
  rows=[dict(r) for r in c.execute(EXPLORER_QUERIES[view],(did,))]
  total=c.execute('SELECT COUNT(*) FROM readings WHERE dataset_id=?',(did,)).fetchone()[0]
  return {'database_path':str(DB.resolve()),'engine':'SQLite','journal_mode':c.execute('PRAGMA journal_mode').fetchone()[0],'dataset_id':did,'query':EXPLORER_QUERIES[view],'parameters':[did],'rows':rows,'total_readings':total}

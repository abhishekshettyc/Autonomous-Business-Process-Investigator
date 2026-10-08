"""Optional ~1 minute full background-worker rehearsal, using a temporary database."""
import sys,tempfile,time,subprocess,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import database as db
from app import app
from fastapi.testclient import TestClient

def wait_for(client,predicate,timeout,label):
 deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  s=client.get('/api/live/status').json()
  if s.get('state')=='error':raise AssertionError(s.get('last_error'))
  if predicate(s):print(label,flush=True);return s
  time.sleep(.5)
 raise AssertionError(f'{label} timed out. Last result: {s.get("report",{}).get("status") if s.get("report") else s["state"]}')

with tempfile.TemporaryDirectory() as tmp:
 db.DB=Path(tmp)/'live-demo.db'
 with TestClient(app) as client:
  assert client.post('/api/live/start').status_code==200
  wait_for(client,lambda s:s['state']=='running',20,'60 baseline measurements collected and persisted')
  wait_for(client,lambda s:s.get('report') and not s['report']['anomaly'],30,'Normal live window analyzed')
  client.post('/api/live/mode/delay').raise_for_status()
  wait_for(client,lambda s:s.get('report') and s['report']['status']=='Leading hypothesis' and s['report']['rankings'][0]['id']=='delay',40,'Controlled live delay detected and explained')
  client.post('/api/live/mode/normal').raise_for_status()
  s=wait_for(client,lambda s:s.get('report') and not s['report']['anomaly'],40,'Recovery detected from new measurements')
  r=client.post('/api/live/stop').json();assert r['state']=='stopped'
  before=client.get('/api/database').json()['total_readings'];time.sleep(.3);assert client.get('/api/database').json()['total_readings']==before
  print('Stop confirmed; persisted readings:',before,flush=True)
 env=dict(os.environ,ROOTLENS_DB=str(db.DB));script=Path(__file__).resolve().parents[1]/'db_console.py'
 result=subprocess.run([sys.executable,str(script),'--file',str(script.parent/'demo_queries.sql')],env=env,capture_output=True,text=True)
 assert result.returncode==0,result.stderr
 print('Independent read-only SQL console queries passed.',flush=True)

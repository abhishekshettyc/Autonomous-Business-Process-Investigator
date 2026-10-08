import sys,tempfile,unittest,random,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import database as db
from live import LiveRunner,HYPOTHESES,now
from fastapi.testclient import TestClient
from app import app
class LiveTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();db.DB=Path(self.temp.name)/'live.db';db.init();self.runner=LiveRunner()
  self.did=db.insert({'name':'Live test','asset_id':'LOCAL-WORKER','source':'Measured local test workload','synthetic':False,'metrics':[{'name':'duration_ms','unit':'ms'},{'name':'error_count','unit':'count'}],'hypotheses':HYPOTHESES,'readings':[],'events':[]})
  self.rng=random.Random(42)
 def tearDown(self):self.runner.stop();self.temp.cleanup()
 def ticks(self,start,count,period,mode):
  for n in range(start,start+count):self.runner._tick('test',self.did,n,period,mode,self.rng)
 def test_measured_fault_and_recovery(self):
  self.ticks(0,60,'baseline','normal');self.ticks(60,10,'current','normal');before=self.runner.analyze(self.did)
  self.assertFalse(before['anomaly'])
  self.ticks(70,10,'current','delay');r=self.runner.analyze(self.did)
  self.assertTrue(r['anomaly']);self.assertEqual(r['rankings'][0]['id'],'delay');self.assertEqual(r['status'],'Leading hypothesis')
  self.assertTrue(all(row['values']['duration_ms']>=300 for row in db.get(self.did)['readings'][-10:]))
  self.ticks(80,10,'current','normal');r=self.runner.analyze(self.did);self.assertFalse(r['anomaly'])
  self.assertEqual(len(db.get(self.did)['readings']),90);self.assertEqual(r['last_reading_id'],'LIVE-000089')
  self.ticks(90,10,'current','timeout');r=self.runner.analyze(self.did);self.assertEqual(r['rankings'][0]['id'],'timeout');self.assertEqual(r['status'],'Leading hypothesis')
 def test_insufficient_current_waits(self):
  self.ticks(0,60,'baseline','normal');self.ticks(60,4,'current','normal');self.assertIsNone(self.runner.analyze(self.did))
 def test_control_idempotence_and_stop(self):
  first=self.runner.start();second=self.runner.start();self.assertEqual(first['id'],second['id'])
  with self.assertRaises(ValueError):self.runner.set_mode('delay')
  self.runner.stop();self.assertEqual(self.runner.status()['state'],'stopped')
 def test_readonly_explorer(self):
  self.ticks(0,2,'baseline','normal');r=db.explore('readings',self.did)
  self.assertEqual(r['total_readings'],2);self.assertEqual(r['engine'],'SQLite');self.assertEqual(r['journal_mode'],'wal');self.assertTrue(Path(r['database_path']).exists())
  with self.assertRaises(ValueError):db.explore('DROP TABLE readings')
 def test_new_endpoints(self):
  with TestClient(app) as c:
   self.assertEqual(c.get('/api/live/status').status_code,200)
   self.assertEqual(c.get('/api/database').status_code,200)
   self.assertEqual(c.get('/api/database?view=invalid').status_code,422)
   self.assertEqual(c.post('/api/live/mode/bad').status_code,422)
if __name__=='__main__':unittest.main()

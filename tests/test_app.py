import sys,json,tempfile,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import database as db
from core import validate,investigate
from demo import make
from app import app
from fastapi.testclient import TestClient
class DetectorTests(unittest.TestCase):
 def test_scenarios(self):
  for s,expected in [('capacity','capacity'),('dependency','dependency'),('hardware','hardware')]:
   with self.subTest(s=s):
    r=investigate(validate(make(s)));self.assertTrue(r['anomaly']);self.assertEqual(r['rankings'][0]['id'],expected);self.assertEqual(r['status'],'Leading hypothesis')
 def test_abstain(self):
  for s in ['ambiguous','unknown']:self.assertEqual(investigate(validate(make(s)))['status'],'Needs more evidence')
 def test_healthy(self):self.assertFalse(investigate(validate(make('healthy')))['anomaly'])
 def test_unseen_seeds(self):
  for seed in [13,99,213]:
   self.assertFalse(investigate(validate(make('healthy',seed)))['anomaly'])
   self.assertTrue(investigate(validate(make('capacity',seed)))['anomaly'])
 def test_no_leakage(self):
  d=make();d['readings'][250]['period']='baseline'
  with self.assertRaises(ValueError):validate(d)
 def test_reject_missing_nonfinite_duplicate(self):
  for mutation in [lambda d:d['readings'][0]['values'].pop('latency_ms'),lambda d:d['readings'][0]['values'].update(latency_ms=float('nan')),lambda d:d['readings'][1].update(id=d['readings'][0]['id'])]:
   d=make();mutation(d)
   with self.assertRaises(ValueError):validate(d)
 def test_duplicate_evidence_no_score_inflation(self):
  d=make();r=investigate(validate(d));e=copy.deepcopy(d['events'][0]);e['id']='EXTRA';d['events'].append(e);self.assertEqual(r['rankings'][0]['score'],investigate(validate(d))['rankings'][0]['score'])
 def test_unrelated_and_old_events_ignored(self):
  r=investigate(validate(make('capacity')));self.assertFalse(next(e for e in r['evidence'] if e['category']=='UPSTREAM_ERROR')['relevant'])
  r=investigate(validate(make('ambiguous')));self.assertFalse(next(e for e in r['evidence'] if e['asset_id']=='OTHER-ASSET')['relevant'])
 def test_units_required(self):
  d=make();d['metrics'][0]['unit']=''
  with self.assertRaises(ValueError):validate(d)
class APITests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();db.DB=Path(self.tmp.name)/'test.db';self.client=TestClient(app);self.client.__enter__()
 def tearDown(self):self.client.__exit__(None,None,None);self.tmp.cleanup()
 def test_storage_investigation_and_reopen(self):
  response=self.client.post('/api/datasets',json=make());self.assertEqual(response.status_code,200);did=response.json()['id']
  self.assertEqual(len(db.get(did)['readings']),280)
  r=self.client.post(f'/api/datasets/{did}/investigate').json();self.assertEqual(r['status'],'Leading hypothesis')
  db.init();self.assertEqual(self.client.get('/api/investigations/'+r['id']).json(),r);self.assertEqual(len(self.client.get('/api/history').json()),1)
 def test_invalid_no_partial_write(self):
  d=make();d['readings'][0]['values']={};self.assertEqual(self.client.post('/api/datasets',json=d).status_code,422);self.assertEqual(db.datasets(),[])
 def test_csv(self):
  p=Path(__file__).resolve().parents[1]/'samples';body={'name':'CSV import','asset_id':'OPS-01','csv':(p/'readings.csv').read_text(),'events':(p/'events.jsonl').read_text(),'units':json.loads((p/'units.json').read_text())}
  self.assertEqual(self.client.post('/api/import-csv',json=body).status_code,200)
 def test_routes(self):
  for path in ['/','/static/ui.js','/static/style.css','/api/health','/docs']:self.assertEqual(self.client.get(path).status_code,200)
  self.assertEqual(self.client.get('/api/datasets/nonexistent').status_code,404)
 def test_oversize(self):self.assertEqual(self.client.post('/api/datasets',content=b' '*8000001).status_code,413)
if __name__=='__main__':unittest.main()

import random,json,csv
from pathlib import Path
from datetime import datetime,timedelta,timezone
from core import DEFAULT_HYPOTHESES
SCENARIOS={'capacity':'Resource bottleneck','dependency':'Dependency degradation','ambiguous':'Conflicting signals','hardware':'Device telemetry warning','unknown':'Anomaly without logs','healthy':'Stable operation'}
def make(scenario='capacity',seed=42):
 if scenario not in SCENARIOS:raise ValueError('Unknown demo scenario')
 rng=random.Random(seed);start=datetime(2026,10,8,8,0,tzinfo=timezone.utc);rows=[];events=[]
 specs=[{'name':'latency_ms','unit':'ms'},{'name':'queue_depth','unit':'items'},{'name':'error_rate','unit':'%'},{'name':'temperature_c','unit':'°C'}]
 for i in range(280):
  vals={'latency_ms':round(rng.gauss(120,8),2),'queue_depth':max(0,round(rng.gauss(12,2),2)),'error_rate':round(max(0,rng.gauss(1,.2)),3),'temperature_c':round(rng.gauss(45,1),2)}
  if i>=240 and scenario!='healthy':
   if scenario in ('capacity','ambiguous','unknown'):vals.update(latency_ms=round(rng.gauss(450,25),2),queue_depth=round(rng.gauss(80,5),2))
   if scenario=='dependency':vals.update(latency_ms=round(rng.gauss(550,25),2),error_rate=round(rng.gauss(20,2),2))
   if scenario=='hardware':vals['temperature_c']=round(rng.gauss(90,2),2)
  rows.append({'id':f'R{i:04}','timestamp':(start+timedelta(minutes=i)).isoformat(),'period':'baseline' if i<240 else 'current','values':vals})
 def event(cat,i,reading=True,asset='OPS-01'):
  events.append({'id':f'E{len(events)+1:03}','timestamp':rows[i]['timestamp'],'asset_id':asset,'reading_id':rows[i]['id'] if reading else None,'category':cat,'message':cat.replace('_',' ').capitalize()+' observed by the existing monitoring system.','source':'Synthetic event log'})
 if scenario=='capacity':event('RESOURCE_PRESSURE',245);event('QUEUE_BUILDUP',250);event('DEPENDENCY_HEALTHY',251);event('UPSTREAM_ERROR',30)
 if scenario=='dependency':event('DEPENDENCY_TIMEOUT',245);event('UPSTREAM_ERROR',250);event('RESOURCE_HEALTHY',251)
 if scenario=='ambiguous':
  for cat,i in [('RESOURCE_PRESSURE',245),('QUEUE_BUILDUP',248),('DEPENDENCY_TIMEOUT',250),('UPSTREAM_ERROR',255)]:event(cat,i)
  event('THERMAL_ALARM',260,False,'OTHER-ASSET')
 if scenario=='hardware':event('THERMAL_ALARM',245);event('DEVICE_FAULT',250);event('DEPENDENCY_HEALTHY',252)
 return {'name':SCENARIOS[scenario],'asset_id':'OPS-01','source':'Built-in simulation','synthetic':True,'metrics':specs,'readings':rows,'events':events,'hypotheses':DEFAULT_HYPOTHESES}
if __name__=='__main__':
 out=Path(__file__).parent/'samples';out.mkdir(exist_ok=True)
 for s in SCENARIOS:(out/f'{s}.json').write_text(json.dumps(make(s),indent=2))
 d=make('capacity');names=[m['name'] for m in d['metrics']]
 with (out/'readings.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['id','timestamp','period']+names);w.writeheader()
  for r in d['readings']:w.writerow({k:r[k] for k in ['id','timestamp','period']}|r['values'])
 (out/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in d['events']))
 (out/'units.json').write_text(json.dumps({m['name']:m['unit'] for m in d['metrics']},indent=2))

"""Example software integration: upload an explicit file to a local RootLens server."""
import argparse,json,urllib.request
p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--port',type=int,default=8000);a=p.parse_args()
base=f'http://127.0.0.1:{a.port}'
with open(a.file,encoding='utf-8') as f:payload=json.load(f)
def post(path,data):
 req=urllib.request.Request(base+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=120) as r:return json.load(r)
r=post('/api/datasets',payload);result=post('/api/datasets/'+r['id']+'/investigate',{})
print(json.dumps({'dataset_id':r['id'],'investigation_id':result['id'],'status':result['status'],'summary':result['summary']},indent=2))

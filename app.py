from pathlib import Path
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
import database as db
from core import validate,investigate,from_csv
from demo import make,SCENARIOS
from live import runner
ROOT=Path(__file__).parent
@asynccontextmanager
async def lifespan(app):
 db.init();runner.initialize()
 try:yield
 finally:runner.stop()
app=FastAPI(title='RootLens Investigation API',version='2.1',lifespan=lifespan)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
@app.middleware('http')
async def limit_body(request,call_next):
 # Read a bounded stream before JSON parsing, including chunked requests.
 if request.method=='POST':
  body=bytearray()
  async for chunk in request.stream():
   body.extend(chunk)
   if len(body)>8_000_000:return JSONResponse({'detail':'Maximum request size is 8 MB.'},status_code=413)
  request._body=bytes(body)
 response=await call_next(request)
 response.headers['X-Content-Type-Options']='nosniff'
 response.headers['Cache-Control']='no-store'
 return response
@app.exception_handler(ValueError)
async def invalid(request,exc):return JSONResponse({'detail':str(exc)},status_code=422)
@app.get('/')
def index():return FileResponse(ROOT/'static'/'index.html')
@app.get('/api/health')
def health():return {'status':'ok','database':'SQLite','detector':'Isolation Forest'}
@app.get('/api/datasets')
def datasets():return db.datasets()
@app.get('/api/history')
def history():return db.history()
@app.get('/api/demo/{scenario}')
def demo(scenario:str):
 if scenario not in SCENARIOS:raise HTTPException(404,'Unknown scenario')
 return make(scenario)
@app.post('/api/datasets')
async def ingest(request:Request):
 d=validate(await request.json());did=await run_in_threadpool(db.insert,d)
 return {'id':did,'reading_count':len(d['readings']),'event_count':len(d['events']),'message':'Validated and stored atomically in SQL.'}
@app.post('/api/import-csv')
async def import_csv(request:Request):
 b=await request.json()
 if not isinstance(b,dict) or any(not isinstance(b.get(k),str) for k in ['name','asset_id','csv','events']) or not isinstance(b.get('units'),dict):raise ValueError('Provide name, asset_id, csv, events strings and units object.')
 d=validate(from_csv(b['name'],b['asset_id'],b['csv'],b['events'],b['units']));did=await run_in_threadpool(db.insert,d)
 return {'id':did,'reading_count':len(d['readings']),'event_count':len(d['events'])}
@app.get('/api/datasets/{did}')
def dataset(did:str):
 d=db.get(did)
 if d is None:raise HTTPException(404,'Dataset not found')
 return d
@app.post('/api/datasets/{did}/investigate')
def run(did:str):
 d=db.get(did)
 if d is None:raise HTTPException(404,'Dataset not found')
 return db.save_result(did,investigate(d))
@app.get('/api/investigations/{rid}')
def result(rid:str):
 r=db.result(rid)
 if r is None:raise HTTPException(404,'Investigation not found')
 return r
@app.get('/api/live/status')
def live_status():return runner.status()
@app.post('/api/live/start')
def live_start():return runner.start()
@app.post('/api/live/stop')
def live_stop():return runner.stop()
@app.post('/api/live/mode/{mode}')
def live_mode(mode:str):return runner.set_mode(mode)
@app.get('/api/database')
def database_view(view:str='readings',dataset_id:str|None=None):return db.explore(view,dataset_id)

if __name__=='__main__':
 import argparse,uvicorn
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8000);args=parser.parse_args()
 uvicorn.run(app,host='127.0.0.1',port=args.port)

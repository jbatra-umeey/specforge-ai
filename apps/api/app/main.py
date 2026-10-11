import os
from fastapi import FastAPI, Depends, HTTPException
from contextlib import asynccontextmanager
from .config import validate_config, env
from .storage import get_store
from .live import router
from .security import require_role
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .specs import Specification,Evidence,assess
from .security import authorize
from .demos import CASES,run_demo
from .graph import build_graph
@asynccontextmanager
async def lifespan(app):
    validate_config()
    db = get_store()
    if env('SPECFORGE_ENV') != 'production': db.migrate()
    db.check_schema()
    yield
app=FastAPI(title='SpecForge AI API',version='0.2.0',lifespan=lifespan)
app.include_router(router)
allowed=os.getenv('CORS_ORIGINS','http://localhost:3000').split(',')
app.add_middleware(CORSMiddleware,allow_origins=allowed,allow_methods=['GET','POST'],allow_headers=['Authorization','X-API-Key','Content-Type','Idempotency-Key'])
@app.get('/health')
def health():return {'status':'ok','version':'0.2.0'}
@app.get('/api/demos',dependencies=[Depends(require_role('viewer'))])
def demos():return [{'id':key,'name':value[0]} for key,value in CASES.items()]
@app.post('/api/demos/{key}/run',dependencies=[Depends(require_role('viewer'))])
def demo_run(key:str):
    try:return run_demo(key)
    except KeyError:raise HTTPException(status_code=404,detail='Unknown demo')
class Assessment(BaseModel):
    specification:Specification
    evidence:list[Evidence]
@app.post('/api/specs/evaluate',dependencies=[Depends(require_role('viewer'))])
def evaluate(body:Assessment):return assess(body.specification,body.evidence)
class GraphRequest(BaseModel):
    spec_valid:bool
    implementation_ready:bool
    tests_passed:bool
    approved:bool=False
@app.post('/api/workflows/transition',dependencies=[Depends(require_role('viewer'))])
def workflow(req:GraphRequest):
    try:return build_graph().invoke({**req.model_dump(),'stage':'requested'})
    except RuntimeError as exc:raise HTTPException(status_code=503,detail=str(exc))

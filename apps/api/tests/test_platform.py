import os,tempfile
from pathlib import Path
os.environ['SPECFORGE_API_KEY']='test-token'
from fastapi.testclient import TestClient
from app.main import app
from app.demos import CASES
from app.specs import Specification,Requirement,Evidence,assess
from app.react import Agent
from app.tools import ToolRegistry
from app.graph import build_graph
client=TestClient(app)
HEADERS={'X-API-Key':'test-token'}
def test_auth():
    assert client.get('/api/demos').status_code==401
    assert client.get('/api/demos',headers=HEADERS).status_code==200
def test_health():assert client.get('/health').json()['status']=='ok'
def test_five_demos():
    for key in CASES:
        response=client.post('/api/demos/'+key+'/run',headers=HEADERS)
        assert response.status_code==200
        result=response.json()
        assert result['status']=='completed'
        assert result['evaluation']['coverage']==1
        assert result['mode']=='deterministic_fixture'
def test_reject_duplicate_requirements():
    try:
        Specification(name='Example',version='1.0.0',goal='An adequately written goal',requirements=[Requirement(id='REQ-001',statement='A detailed requirement',acceptance=['Measurably verified']),Requirement(id='REQ-001',statement='Another detailed requirement',acceptance=['Measurably verified'])])
        assert False
    except ValueError:pass
def test_negative_evaluation():
    s=Specification(name='Example',version='1.0.0',goal='An adequately written goal',requirements=[Requirement(id='REQ-001',statement='A detailed requirement',acceptance=['Measurably verified'])])
    assert not assess(s,[Evidence(requirement_id='REQ-001',test_name='failure',passed=False,details='failure')])['passed']
def test_tool_security():
    with tempfile.TemporaryDirectory() as d:
        t=ToolRegistry(Path(d))
        try:t.write_file('foo.txt','content');assert False
        except PermissionError:pass
        try:t.read_file('../escape.txt');assert False
        except ValueError:pass
        t.write_file('foo.txt','content',approved=True)
        assert t.read_file('foo.txt')=='content'
def test_agent_budget_and_denial():
    a=Agent({'echo':lambda msg:msg},max_steps=2)
    assert a.execute('x',lambda goal,steps:{'action':'echo','args':{'msg':'ok'}}).status=='budget_exceeded'
    assert a.execute('x',lambda goal,steps:{'action':'shell'}).status=='blocked'
def test_graph_gate():
    import pytest
    pytest.importorskip("langgraph")
    g=build_graph()
    s=g.invoke({'spec_valid':True,'implementation_ready':True,'tests_passed':True,'approved':False,'stage':'requested'})
    assert s['stage']=='waiting_approval'
    s=g.invoke({'spec_valid':False,'implementation_ready':True,'tests_passed':True,'approved':True,'stage':'requested'})
    assert s['stage']=='rejected'

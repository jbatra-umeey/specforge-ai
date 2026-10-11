import json,time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import httpx,jwt,pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from app.main import app
from app import live,security
from app.config import validate_config
from app.integrations import Integrations,ProposedAction,IntegrationError,UncertainWrite
from app.planner import ModelClient,ModelError,plan_live
from app.security import Principal
from app.storage import Store,get_store
@pytest.fixture(autouse=True)
def settings(monkeypatch,tmp_path):
    for k,v in {'AUTH_MODE':'development','SPECFORGE_ENV':'test','SPECFORGE_API_KEY':'test-token','DATABASE_URL':'sqlite:///'+str(tmp_path/'test.db'),'INTEGRATION_TENANT_ID':'local','GITHUB_ALLOWED_REPOS':'acme/demo','GITHUB_TOKEN':'test-github-token','JIRA_ALLOWED_PROJECTS':'DEMO','JIRA_BASE_URL':'https://jira.example.test','JIRA_EMAIL':'test@example.test','JIRA_API_TOKEN':'test-jira-token','LLM_API_KEY':'test-model-token','LLM_MODEL':'test-model','LLM_BASE_URL':'https://model.example.test/v1'}.items():monkeypatch.setenv(k,v)
    get_store().migrate();app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
H={'X-API-Key':'test-token','Idempotency-Key':'test-request-001'}
P=Principal('local-developer','local',frozenset({'viewer','operator','approver'}))
ACTION={'kind':'github_issue','target':'acme/demo','title':'Implement subscription API','body':'Add authenticated create and read endpoints.'}
PLAN={'summary':'Implement subscription API with explicit acceptance tests.','steps':[{'title':'Implement API','acceptance':['Unauthorized requests return 401.']}],'proposed_actions':[ACTION]}
def completion(d):return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(d)}}],'usage':{'total_tokens':30}}
def test_live_read_plan_approve_persist_and_idempotency(monkeypatch):
    calls=[]
    def upstream(r):
        calls.append((r.method,str(r.url)))
        if r.url.host=='model.example.test':
            payload=json.loads(r.content);assert payload['model']=='test-model' and payload['response_format']['type']=='json_object'
            if len(payload['messages'])==2:return httpx.Response(200,json=completion({'action':'read_github_issue','target':'acme/demo','issue':'12'}))
            assert 'Untrusted tool data' in payload['messages'][-1]['content']
            return httpx.Response(200,json=completion({'action':'finish','plan':PLAN}))
        assert r.headers['authorization']=='Bearer test-github-token'
        if r.method=='GET':return httpx.Response(200,json={'title':'Subscription feature','body':'Source issue'})
        assert json.loads(r.content)['title']==ACTION['title']
        return httpx.Response(201,json={'number':13,'html_url':'https://github.com/acme/demo/issues/13'})
    transport=httpx.MockTransport(upstream)
    app.dependency_overrides[live.model_client]=lambda:ModelClient(transport)
    monkeypatch.setattr(live,'Integrations',lambda tenant:Integrations(tenant,transport))
    with TestClient(app) as c:
        body={'goal':'Read acme/demo issue 12 and propose an implementation issue.'}
        r=c.post('/api/runs',headers=H,json=body);assert r.status_code==200
        run=r.json();assert run['status']=='planned';assert len(calls)==3
        assert c.post('/api/runs',headers=H,json=body).json()['id']==run['id'];assert len(calls)==3
        assert c.post('/api/runs',headers=H,json={'goal':'A different goal with same request key'}).status_code==409
        a=run['actions'][0];path=f"/api/runs/{run['id']}/actions/{a['id']}/execute"
        assert c.post(path,headers=H,json={'digest':'0'*64}).status_code==409
        assert c.post(path,headers=H,json={'digest':a['digest']}).json()['actions'][0]['status']=='succeeded'
        assert c.post(path,headers=H,json={'digest':a['digest']}).status_code==409;assert len(calls)==4
        assert c.get('/api/runs',headers=H).json()[0]['id']==run['id']
    reopened=Store(str(get_store().engine.url));reopened.check_schema()
    assert reopened.get(P,run['id'])['actions'][0]['result']['number']==13
    other=Principal('other','other',frozenset());assert reopened.get(other,run['id']) is None;assert reopened.list(other)==[]
@pytest.fixture
def oidc(monkeypatch):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    for k,v in {'AUTH_MODE':'oidc','OIDC_ISSUER':'https://identity.example.test','OIDC_JWKS_URL':'https://identity.example.test/keys','OIDC_AUDIENCE':'specforge-api'}.items():monkeypatch.setenv(k,v)
    monkeypatch.setattr(security,'jwks_client',lambda _:SimpleNamespace(get_signing_key_from_jwt=lambda _:SimpleNamespace(key=key.public_key())))
    def token(**overrides):
        p={'iss':'https://identity.example.test','aud':'specforge-api','sub':'alice','tenant_id':'tenant-a','roles':['viewer','operator'],'iat':int(time.time()),'exp':int(time.time())+300};p.update(overrides)
        return {'Authorization':'Bearer '+jwt.encode(p,key,algorithm='RS256',headers={'kid':'test'})}
    return token
@pytest.mark.parametrize('overrides',[{'exp':1},{'aud':'wrong'},{'iss':'https://wrong.test'},{'tenant_id':''},{'roles':'approver'},{'iat':4102444800}])
def test_invalid_oidc_tokens_rejected(oidc,overrides):assert TestClient(app).get('/api/me',headers=oidc(**overrides)).status_code==401
def test_oidc_roles_tenants_and_no_key_fallback(oidc):
    c=TestClient(app);assert c.get('/api/me',headers=oidc()).json()['tenant']=='tenant-a';assert c.get('/api/me',headers=H).status_code==401
    assert c.post('/api/runs',headers={**oidc(roles=['viewer']),'Idempotency-Key':'abcdefgh'},json={'goal':'Create a concrete implementation plan'}).status_code==403
    row,_=get_store().create_run(P,'tenant-private-key','A private local tenant plan')
    assert c.get('/api/runs/'+row['id'],headers=oidc()).status_code==404
    assert c.post('/api/runs/x/actions/y/execute',headers=oidc(),json={'digest':'0'*64}).status_code==403
def test_production_rejects_development_auth(monkeypatch):
    monkeypatch.setenv('SPECFORGE_ENV','production')
    with pytest.raises(ValueError,match='OIDC'):validate_config()
    assert TestClient(app).get('/api/me',headers=H).status_code==503
def test_production_rejects_sqlite(oidc,monkeypatch):
    monkeypatch.setenv('SPECFORGE_ENV','production')
    with pytest.raises(ValueError,match='PostgreSQL'):validate_config()
@pytest.mark.parametrize('target',['other/repo','../secrets','acme/demo/../../other'])
def test_integration_target_allowlist(target):
    with pytest.raises(IntegrationError):Integrations('local').read('read_github_issue',target,'1')
def test_integration_tenant_binding():
    with pytest.raises(IntegrationError):Integrations('another').allow('github','acme/demo')
def test_jira_and_draft_pr_payloads():
    sent=[]
    def handler(r):sent.append(r);return httpx.Response(201,json={'id':'1','key':'DEMO-1'})
    a=Integrations('local',httpx.MockTransport(handler))
    a.execute(ProposedAction(kind='jira_issue',target='DEMO',title='Example issue',body='Acceptance details'))
    assert json.loads(sent[-1].content)['fields']['description']['version']==1;assert sent[-1].url.path=='/rest/api/3/issue'
    a.execute(ProposedAction(kind='github_pull_request',target='acme/demo',title='Example change',body='Details',head='feature',base='main'))
    assert json.loads(sent[-1].content)['draft'] is True
    a.read('read_jira_issue','DEMO','DEMO-1');assert sent[-1].url.path=='/rest/api/3/issue/DEMO-1'
def test_ambiguous_write_not_retried():
    count=[]
    def handler(r):count.append(1);raise httpx.ReadTimeout('timeout',request=r)
    with pytest.raises(UncertainWrite):Integrations('local',httpx.MockTransport(handler)).execute(ProposedAction(**ACTION))
    assert len(count)==1
@pytest.mark.parametrize('response',[httpx.Response(429,json={'error':'limited'}),httpx.Response(200,json={'choices':[]}),httpx.Response(200,json=completion({'action':'shell'}))])
def test_model_fails_closed(response):
    with pytest.raises(ModelError):ModelClient(httpx.MockTransport(lambda _:response)).decide([])
def test_no_mock_fallback_without_credentials(monkeypatch):
    monkeypatch.delenv('LLM_API_KEY')
    r=TestClient(app).post('/api/runs',headers=H,json={'goal':'Create a concrete implementation plan'}).json()
    assert r['status']=='failed' and r['actions']==[] and 'not configured' in r['result']['error']
def test_read_loop_is_bounded():
    model=ModelClient(httpx.MockTransport(lambda _:httpx.Response(200,json=completion({'action':'read_github_issue','target':'acme/demo','issue':'1'}))))
    i=Integrations('local',httpx.MockTransport(lambda _:httpx.Response(200,json={'title':'Test'})));steps=[]
    with pytest.raises(ModelError,match='budget'):plan_live('An endless read loop',model,i,steps.append,max_steps=2)
    assert len(steps)==2
def test_atomic_claim_allows_one_execution():
    db=get_store();row,_=db.create_run(P,'claim-test-key','An implementation plan for concurrency');db.finish(P,row['id'],'planned',{},[ACTION]);a=db.get(P,row['id'])['actions'][0]
    def claim(_):
        try:db.claim_action(P,row['id'],a['id'],a['digest']);return True
        except ValueError:return False
    with ThreadPoolExecutor(2) as pool:assert sum(pool.map(claim,range(2)))==1

def test_forged_signature_rejected(oidc):
    headers=oidc();token=headers['Authorization'][7:]
    claims=jwt.decode(token,options={'verify_signature':False})
    wrong=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    forged=jwt.encode(claims,wrong,algorithm='RS256',headers={'kid':'test'})
    assert TestClient(app).get('/api/me',headers={'Authorization':'Bearer '+forged}).status_code==401

def test_hmac_algorithm_confusion_rejected(oidc):
    claims=jwt.decode(oidc()['Authorization'][7:],options={'verify_signature':False})
    forged=jwt.encode(claims,'invalid-shared-secret-which-is-long-enough',algorithm='HS256')
    assert TestClient(app).get('/api/me',headers={'Authorization':'Bearer '+forged}).status_code==401

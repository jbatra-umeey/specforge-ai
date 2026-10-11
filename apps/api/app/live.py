from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from .security import Principal, require_role
from .storage import get_store
from .planner import ModelClient, ModelError, plan_live
from .integrations import Integrations, IntegrationError, UncertainWrite, ProposedAction
router = APIRouter(prefix='/api')
def model_client(): return ModelClient()
class Goal(BaseModel): goal: str = Field(min_length=12, max_length=12000)
class Approval(BaseModel): digest: str = Field(pattern=r'^[a-f0-9]{64}$')
@router.get('/me')
def me(p: Principal = Depends(require_role('viewer'))): return {'subject': p.subject, 'tenant': p.tenant, 'roles': sorted(p.roles)}
@router.get('/runs')
def history(p: Principal = Depends(require_role('viewer'))): return get_store().list(p)
@router.get('/runs/{rid}')
def detail(rid: str, p: Principal = Depends(require_role('viewer'))):
    run = get_store().get(p, rid)
    if not run: raise HTTPException(404, 'Run not found')
    return run
@router.post('/runs')
def create(body: Goal, idempotency_key: str = Header(min_length=8, max_length=128),
           p: Principal = Depends(require_role('operator')), model = Depends(model_client)):
    db = get_store()
    try: row, created = db.create_run(p, idempotency_key, body.goal)
    except ValueError as e: raise HTTPException(409, str(e))
    if created:
        try:
            result = plan_live(body.goal, model, Integrations(p.tenant), lambda step: db.record_step(p, row['id'], step))
            db.finish(p, row['id'], 'planned', result, result['plan']['proposed_actions'])
        except (ModelError, IntegrationError, ValueError) as e:
            db.finish(p, row['id'], 'failed', {'error': str(e), 'mode': 'live_model'})
        except Exception:
            db.finish(p, row['id'], 'failed', {'error': 'Unexpected planning failure; inspect server diagnostics', 'mode': 'live_model'})
    return db.get(p, row['id'])
@router.post('/runs/{rid}/actions/{aid}/execute')
def execute(rid: str, aid: str, body: Approval, p: Principal = Depends(require_role('approver'))):
    db = get_store()
    try: action = db.claim_action(p, rid, aid, body.digest)
    except KeyError: raise HTTPException(404, 'Action not found')
    except ValueError as e: raise HTTPException(409, str(e))
    try:
        result = Integrations(p.tenant).execute(ProposedAction.model_validate(action['payload']))
        status = 'succeeded'
    except UncertainWrite as e: status, result = 'unknown', {'error': str(e)}
    except (IntegrationError, ValueError) as e: status, result = 'failed', {'error': str(e)}
    except Exception: status, result = 'unknown', {'error': 'Unexpected failure; reconcile remotely before any retry'}
    db.finish_action(p, rid, aid, status, result)
    return db.get(p, rid)

"""Executable deterministic scenario fixtures, not real deployments or GitHub operations."""
from .specs import Specification,Requirement,Evidence,assess
from .react import Agent
CASES={
 'feature':('Autonomous feature delivery','Create authenticated subscription API', ['contract defined','implementation reviewed','tests passing']),
 'regression':('Self-healing regression','Fix failing billing calculation', ['failure reproduced','patch verified','regression passing']),
 'drift':('Specification drift','Align API response with declared schema', ['drift identified','contract updated','compatibility verified']),
 'incident':('Incident response','Identify introduced latency regression', ['metric threshold exceeded','candidate cause linked','remediation tested']),
 'release':('Secure release','Gate a vulnerable dependency update', ['scanner finding reviewed','dependency updated','security tests passing'])}
def run_demo(key):
    if key not in CASES:raise KeyError(key)
    title,goal,criteria=CASES[key]
    spec=Specification(name=title,version='1.0.0',goal=goal,requirements=[Requirement(id=f'REQ-{i:03}',statement='System shall demonstrate '+c+' in the controlled fixture.',acceptance=['Fixture returns verified outcome for '+c]) for i,c in enumerate(criteria,1)])
    checks={r.id:True for r in spec.requirements}
    def verify(requirement_id:str):return {'passed':checks[requirement_id],'requirement_id':requirement_id}
    def planner(goal,steps):
        if len(steps)<len(spec.requirements):
            return {'reason':'Verify next acceptance criterion','action':'verify','args':{'requirement_id':spec.requirements[len(steps)].id}}
        return {'action':'finish','success':all('passed' in s.observation and 'True' in s.observation for s in steps)}
    run=Agent({'verify':verify}).execute(goal,planner)
    evidence=[Evidence(requirement_id=r.id,test_name='fixture_'+r.id,passed=True,details='Deterministic in-process check') for r in spec.requirements]
    return {'id':key,'name':title,'mode':'deterministic_fixture','status':run.status,'spec':spec.model_dump(),'trace':[s.__dict__ for s in run.steps],'evaluation':assess(spec,evidence),'warning':'This fixture does not deploy, change GitHub, invoke a live model, or exercise external systems.'}

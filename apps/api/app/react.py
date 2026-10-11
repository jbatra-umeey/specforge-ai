"""Bounded ReAct executor: reason -> invoke allowlisted tool -> observe -> decide."""
from dataclasses import dataclass,field
from typing import Callable
@dataclass
class Step:
    turn:int
    thought:str
    action:str
    observation:str
@dataclass
class Run:
    goal:str
    steps:list[Step]=field(default_factory=list)
    status:str='running'
class Agent:
    def __init__(self,tools:dict[str,Callable],max_steps:int=8):
        if not 1<=max_steps<=32:raise ValueError('Invalid budget')
        self.tools=tools;self.max_steps=max_steps
    def execute(self,goal:str,planner:Callable[[str,list[Step]],dict])->Run:
        run=Run(goal)
        for i in range(self.max_steps):
            decision=planner(goal,run.steps)
            action=decision.get('action','')
            if action=='finish':
                run.status='completed' if decision.get('success') else 'failed'
                return run
            if action not in self.tools:
                run.steps.append(Step(i+1,decision.get('reason',''),action,'DENIED: tool not in allowlist'))
                run.status='blocked';return run
            try: observation=str(self.tools[action](**decision.get('args',{})))[:4000]
            except Exception as exc: observation=f'ERROR: {type(exc).__name__}: {exc}'
            run.steps.append(Step(i+1,decision.get('reason',''),action,observation))
        run.status='budget_exceeded';return run

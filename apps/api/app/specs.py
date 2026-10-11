"""Deterministic specification contract; no fabricated test or delivery outcomes."""
from pydantic import BaseModel, Field, model_validator
from typing import Literal
import re
class Requirement(BaseModel):
    id: str = Field(pattern=r'^REQ-[0-9]{3,}$')
    statement: str = Field(min_length=15)
    acceptance: list[str] = Field(min_length=1)
    priority: Literal['must','should','could']='must'
    @model_validator(mode='after')
    def concrete(self):
        if any(len(a.strip()) < 10 for a in self.acceptance): raise ValueError('Acceptance criteria must be concrete')
        return self
class Specification(BaseModel):
    name: str = Field(min_length=3)
    version: str = Field(pattern=r'^\d+\.\d+\.\d+$')
    goal: str = Field(min_length=12)
    requirements: list[Requirement] = Field(min_length=1)
    @model_validator(mode='after')
    def unique(self):
        ids=[r.id for r in self.requirements]
        if len(ids)!=len(set(ids)): raise ValueError('Duplicate requirement identifiers')
        return self
class Evidence(BaseModel):
    requirement_id: str
    test_name: str
    passed: bool
    details: str

def assess(spec:Specification, evidence:list[Evidence]):
    ids={r.id for r in spec.requirements}
    matched={e.requirement_id for e in evidence if e.passed and e.requirement_id in ids}
    unknown=[e.requirement_id for e in evidence if e.requirement_id not in ids]
    failed=[e.test_name for e in evidence if not e.passed]
    return {'requirements':len(ids),'verified':len(matched),'coverage':round(len(matched)/len(ids),4),'passed':len(matched)==len(ids) and not failed and not unknown,'unknown_evidence':unknown,'failed_tests':failed}

"""Explicit LangGraph state graph; node outputs are validated domain steps."""
from typing import TypedDict
try:
    from langgraph.graph import StateGraph, END
except ImportError:
    StateGraph=END=None
class WorkflowState(TypedDict):
    spec_valid:bool
    implementation_ready:bool
    tests_passed:bool
    approved:bool
    stage:str

def build_graph():
    if StateGraph is None:raise RuntimeError('Install langgraph to use workflow graph')
    g=StateGraph(WorkflowState)
    g.add_node('validate',lambda s:{'stage':'specified' if s['spec_valid'] else 'rejected'})
    g.add_node('implement',lambda s:{'stage':'implemented' if s['implementation_ready'] else 'blocked'})
    g.add_node('verify',lambda s:{'stage':'verified' if s['tests_passed'] else 'failed_tests'})
    g.add_node('release',lambda s:{'stage':'approved' if s['approved'] else 'waiting_approval'})
    g.set_entry_point('validate')
    g.add_conditional_edges('validate',lambda s:s['spec_valid'],{True:'implement',False:END})
    g.add_conditional_edges('implement',lambda s:s['implementation_ready'],{True:'verify',False:END})
    g.add_conditional_edges('verify',lambda s:s['tests_passed'],{True:'release',False:END})
    g.add_edge('release',END)
    return g.compile()

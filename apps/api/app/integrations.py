"""Real REST adapters. Reads are allowlisted; writes require API approval."""
import re
from typing import Literal
import httpx
from pydantic import BaseModel, Field, ConfigDict, model_validator
from .config import env, secure_url
class ProposedAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['github_issue', 'github_pull_request', 'jira_issue']
    target: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    head: str | None = Field(default=None, max_length=200)
    base: str | None = Field(default=None, max_length=200)
    @model_validator(mode='after')
    def valid(self):
        if self.kind == 'github_pull_request' and (not self.head or not self.base or self.head == self.base):
            raise ValueError('Pull requests need distinct existing head and base branches')
        return self
class IntegrationError(RuntimeError): pass
class UncertainWrite(IntegrationError): pass
class Integrations:
    def __init__(self, tenant, transport=None): self.tenant, self.transport = tenant, transport
    def allow(self, provider, target):
        if self.tenant != env('INTEGRATION_TENANT_ID'): raise IntegrationError('Integration credentials are not configured for this tenant')
        name = 'GITHUB_ALLOWED_REPOS' if provider == 'github' else 'JIRA_ALLOWED_PROJECTS'
        allowed = {x.strip() for x in env(name).split(',') if x.strip()}
        pattern = r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+' if provider == 'github' else r'[A-Z][A-Z0-9_]*'
        if not re.fullmatch(pattern, target) or target not in allowed: raise IntegrationError('Target is not allowlisted')
    def request(self, provider, method, path, payload=None):
        if provider == 'github':
            token = env('GITHUB_TOKEN')
            if not token: raise IntegrationError('GitHub token is not configured')
            base = 'https://api.github.com'
            headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
            auth = None
        else:
            base = secure_url('JIRA_BASE_URL')
            if not env('JIRA_EMAIL') or not env('JIRA_API_TOKEN'): raise IntegrationError('Jira credentials are not configured')
            headers = {'Accept': 'application/json'}
            auth = (env('JIRA_EMAIL'), env('JIRA_API_TOKEN'))
        try:
            with httpx.Client(timeout=20, follow_redirects=False, transport=self.transport) as client:
                r = client.request(method, base + path, json=payload, headers=headers, auth=auth)
                if r.status_code >= 500 and method != 'GET': raise UncertainWrite('Provider error; reconcile remotely before retrying')
                if not 200 <= r.status_code < 300: raise IntegrationError(f'{provider} returned HTTP {r.status_code}')
                if len(r.content) > 1000000: raise IntegrationError('Provider response exceeds limit')
                return r.json()
        except httpx.RequestError:
            if method != 'GET': raise UncertainWrite('Write outcome unknown; reconcile with the provider')
            raise IntegrationError('Provider connection failed')
        except ValueError:
            if method != 'GET': raise UncertainWrite('Invalid provider response; reconcile with the provider')
            raise IntegrationError('Invalid provider response')
    def read(self, kind, target, issue):
        if kind == 'read_github_issue':
            self.allow('github', target)
            if not re.fullmatch(r'[1-9][0-9]{0,9}', str(issue)): raise IntegrationError('Invalid GitHub issue number')
            d = self.request('github', 'GET', f'/repos/{target}/issues/{issue}')
            return {'title': str(d.get('title', ''))[:200], 'body': str(d.get('body', ''))[:12000], 'url': d.get('html_url')}
        if kind != 'read_jira_issue': raise IntegrationError('Unknown read tool')
        self.allow('jira', target)
        if not re.fullmatch(re.escape(target) + r'-[1-9][0-9]{0,9}', str(issue)): raise IntegrationError('Invalid Jira issue key')
        d = self.request('jira', 'GET', f'/rest/api/3/issue/{issue}?fields=summary,description,status')
        return {'key': d.get('key'), 'fields': d.get('fields', {})}
    def validate_action(self, action): self.allow('jira' if action.kind == 'jira_issue' else 'github', action.target)
    def execute(self, action: ProposedAction):
        self.validate_action(action)
        if action.kind == 'github_issue':
            d = self.request('github', 'POST', f'/repos/{action.target}/issues', {'title': action.title, 'body': action.body})
        elif action.kind == 'github_pull_request':
            d = self.request('github', 'POST', f'/repos/{action.target}/pulls', {'title': action.title, 'body': action.body, 'head': action.head, 'base': action.base, 'draft': True})
        else:
            d = self.request('jira', 'POST', '/rest/api/3/issue', {'fields': {'project': {'key': action.target}, 'summary': action.title,
                'issuetype': {'name': env('JIRA_ISSUE_TYPE', 'Task')}, 'description': {'type': 'doc', 'version': 1,
                'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': action.body}]}]}}})
        return {k: d[k] for k in ('id', 'number', 'key', 'html_url', 'self') if k in d}

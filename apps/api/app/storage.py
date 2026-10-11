"""Tenant-scoped persistent runs and atomically claimed external actions."""
from datetime import datetime, timezone
from functools import lru_cache
from uuid import uuid4
import hashlib, json
from sqlalchemy import create_engine, MetaData, Table, Column, String, Text, Integer, JSON, UniqueConstraint, select, insert, update
from sqlalchemy.exc import IntegrityError
from .config import env
metadata = MetaData()
versions = Table('schema_versions', metadata, Column('version', Integer, primary_key=True))
runs = Table('runs', metadata,
    Column('id', String(36), primary_key=True), Column('tenant', String(128), nullable=False, index=True),
    Column('subject', String(256), nullable=False), Column('request_key', String(128), nullable=False),
    Column('goal', Text, nullable=False), Column('status', String(32), nullable=False),
    Column('result', JSON, nullable=False), Column('created_at', String(40), nullable=False),
    UniqueConstraint('tenant', 'subject', 'request_key'))
actions = Table('actions', metadata,
    Column('id', String(36), primary_key=True), Column('run_id', String(36), nullable=False, index=True),
    Column('tenant', String(128), nullable=False), Column('payload', JSON, nullable=False),
    Column('digest', String(64), nullable=False), Column('status', String(32), nullable=False),
    Column('approved_by', String(256)), Column('result', JSON, nullable=False))
events = Table('audit_events', metadata,
    Column('id', String(36), primary_key=True), Column('run_id', String(36), nullable=False, index=True),
    Column('tenant', String(128), nullable=False), Column('subject', String(256), nullable=False),
    Column('kind', String(64), nullable=False), Column('data', JSON, nullable=False), Column('created_at', String(40), nullable=False))
def now(): return datetime.now(timezone.utc).isoformat()
def digest(payload): return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

class Store:
    def __init__(self, url):
        self.engine = create_engine(url, pool_pre_ping=True, connect_args={'check_same_thread': False} if url.startswith('sqlite') else {})
    def migrate(self):
        # Baseline v1; run as a deployment job before serving production traffic.
        metadata.create_all(self.engine)
        try:
            with self.engine.begin() as c:
                if c.execute(select(versions.c.version)).scalar_one_or_none() is None: c.execute(insert(versions).values(version=1))
        except IntegrityError: pass
    def check_schema(self):
        with self.engine.connect() as c:
            if c.execute(select(versions.c.version)).scalar_one() != 1: raise RuntimeError('Unsupported database schema')
    def audit(self, c, p, rid, kind, data):
        c.execute(insert(events).values(id=str(uuid4()), run_id=rid, tenant=p.tenant, subject=p.subject, kind=kind, data=data, created_at=now()))
    def create_run(self, p, key, goal):
        row = dict(id=str(uuid4()), tenant=p.tenant, subject=p.subject, request_key=key, goal=goal, status='running', result={}, created_at=now())
        try:
            with self.engine.begin() as c:
                c.execute(insert(runs).values(**row)); self.audit(c, p, row['id'], 'run.created', {})
            return row, True
        except IntegrityError:
            with self.engine.connect() as c:
                old = dict(c.execute(select(runs).where(runs.c.tenant == p.tenant, runs.c.subject == p.subject, runs.c.request_key == key)).mappings().one())
            if old['goal'] != goal: raise ValueError('Idempotency key reused with a different goal')
            return old, False
    def record_step(self, p, rid, data):
        with self.engine.begin() as c: self.audit(c, p, rid, 'planner.step', data)
    def finish(self, p, rid, status, result, proposals=()):
        with self.engine.begin() as c:
            c.execute(update(runs).where(runs.c.id == rid, runs.c.tenant == p.tenant).values(status=status, result=result))
            for payload in proposals:
                c.execute(insert(actions).values(id=str(uuid4()), run_id=rid, tenant=p.tenant, payload=payload, digest=digest(payload), status='pending', result={}))
            self.audit(c, p, rid, 'run.' + status, {})
    def get(self, p, rid):
        with self.engine.connect() as c:
            row = c.execute(select(runs).where(runs.c.id == rid, runs.c.tenant == p.tenant)).mappings().first()
            if not row: return None
            result = dict(row)
            result['actions'] = [dict(r) for r in c.execute(select(actions).where(actions.c.run_id == rid, actions.c.tenant == p.tenant)).mappings()]
            result['events'] = [dict(r) for r in c.execute(select(events).where(events.c.run_id == rid, events.c.tenant == p.tenant).order_by(events.c.created_at)).mappings()]
            return result
    def list(self, p):
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(select(runs).where(runs.c.tenant == p.tenant).order_by(runs.c.created_at.desc()).limit(50)).mappings()]
    def claim_action(self, p, rid, aid, expected_digest):
        with self.engine.begin() as c:
            row = c.execute(select(actions).where(actions.c.id == aid, actions.c.run_id == rid, actions.c.tenant == p.tenant)).mappings().first()
            if not row: raise KeyError('Action not found')
            if row['digest'] != expected_digest: raise ValueError('Approval digest does not match the reviewed action')
            changed = c.execute(update(actions).where(actions.c.id == aid, actions.c.tenant == p.tenant, actions.c.status == 'pending').values(status='executing', approved_by=p.subject))
            if changed.rowcount != 1: raise ValueError('Action already claimed; do not replay uncertain operations')
            self.audit(c, p, rid, 'action.approved', {'action_id': aid, 'digest': expected_digest})
            return dict(row)
    def finish_action(self, p, rid, aid, status, result):
        with self.engine.begin() as c:
            c.execute(update(actions).where(actions.c.id == aid, actions.c.tenant == p.tenant).values(status=status, result=result))
            self.audit(c, p, rid, 'action.' + status, {'action_id': aid})
@lru_cache(maxsize=8)
def store_for(url): return Store(url)
def get_store(): return store_for(env('DATABASE_URL', 'sqlite:///./specforge.db'))

"""Server-owned configuration; clients cannot choose upstream hosts or credentials."""
import os
from urllib.parse import urlparse

def env(name, default=''): return os.getenv(name, default).strip()

def secure_url(name, default=''):
    value = env(name, default).rstrip('/')
    p = urlparse(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise ValueError(f'{name} must be an HTTPS URL without credentials, query or fragment')
    return value

def validate_config():
    mode = env('AUTH_MODE', 'development')
    if mode not in {'development', 'oidc'}: raise ValueError('Invalid AUTH_MODE')
    if mode == 'oidc':
        secure_url('OIDC_ISSUER'); secure_url('OIDC_JWKS_URL')
        if not env('OIDC_AUDIENCE'): raise ValueError('OIDC_AUDIENCE is required')
    if env('SPECFORGE_ENV', 'development') == 'production':
        if mode != 'oidc': raise ValueError('Production requires OIDC')
        if not env('DATABASE_URL').startswith('postgresql+psycopg://'): raise ValueError('Production requires PostgreSQL')
        if any(not x.startswith('https://') or '*' in x for x in env('CORS_ORIGINS').split(',')):
            raise ValueError('Production requires explicit HTTPS CORS origins')
    if env('LLM_API_KEY'):
        secure_url('LLM_BASE_URL', 'https://api.openai.com/v1')
        if not env('LLM_MODEL'): raise ValueError('Set an explicitly selected LLM_MODEL')

import secrets
from dataclasses import dataclass
from functools import lru_cache
import jwt
from fastapi import Header, HTTPException, Depends
from .config import env, secure_url

@dataclass(frozen=True)
class Principal:
    subject: str
    tenant: str
    roles: frozenset[str]

@lru_cache(maxsize=8)
def jwks_client(url): return jwt.PyJWKClient(url, cache_jwk_set=True, lifespan=300, timeout=5)

def authorize(authorization: str | None = Header(default=None), x_api_key: str | None = Header(default=None)):
    mode = env('AUTH_MODE', 'development')
    if mode == 'development':
        if env('SPECFORGE_ENV') == 'production': raise HTTPException(503, 'Production authentication is not configured')
        configured = env('SPECFORGE_API_KEY')
        if not configured: raise HTTPException(503, 'API key not configured')
        if not x_api_key or not secrets.compare_digest(x_api_key, configured): raise HTTPException(401, 'Unauthorized')
        return Principal('local-developer', 'local', frozenset({'viewer', 'operator', 'approver'}))
    if mode != 'oidc' or not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Bearer access token required', headers={'WWW-Authenticate': 'Bearer'})
    token = authorization[7:]
    if len(token) > 16384: raise HTTPException(401, 'Invalid access token')
    try:
        secure_url('OIDC_ISSUER')
        issuer = env('OIDC_ISSUER')
        key = jwks_client(secure_url('OIDC_JWKS_URL')).get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=['RS256'], audience=env('OIDC_AUDIENCE'), issuer=issuer,
            options={'require': ['exp', 'iat', 'sub', 'iss', 'aud']}, leeway=15)
        tenant = claims.get(env('OIDC_TENANT_CLAIM', 'tenant_id'))
        roles = claims.get(env('OIDC_ROLES_CLAIM', 'roles'), [])
        if not isinstance(tenant, str) or not tenant or len(tenant) > 128: raise ValueError('Invalid tenant')
        if not isinstance(claims['sub'], str) or not claims['sub'] or len(claims['sub']) > 256: raise ValueError('Invalid subject')
        if not isinstance(roles, list) or not all(isinstance(x, str) for x in roles): raise ValueError('Invalid roles')
        return Principal(claims['sub'], tenant, frozenset(roles))
    except (jwt.PyJWTError, ValueError, OSError):
        raise HTTPException(401, 'Invalid or expired access token', headers={'WWW-Authenticate': 'Bearer'})

def require_role(role):
    def dependency(principal: Principal = Depends(authorize)):
        if role not in principal.roles: raise HTTPException(403, f'{role} role required')
        return principal
    return dependency

def require_approval(approved: bool):
    if not approved: raise PermissionError('Human approval required for write operations')

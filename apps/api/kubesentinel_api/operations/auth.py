"""Pinned RS256 issuer/audience validation. Role checks and mutation limits live on the API."""

import hashlib
import hmac
from functools import lru_cache
from typing import Annotated
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel
from redis import Redis
from redis.exceptions import RedisError

from kubesentinel_api.config import get_settings
from kubesentinel_api.database import get_redis


class Principal(BaseModel):
    subject: str
    name: str
    roles: list[str]
    authentication: str


@lru_cache(maxsize=4)
def jwks(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_jwk_set=True, lifespan=300, timeout=3)


def principal(authorization: Annotated[str | None, Header()] = None) -> Principal:
    settings = get_settings()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer credentials required")
    token = authorization.removeprefix("Bearer ")
    if len(token) > 16000:
        raise HTTPException(401, "Invalid credentials")
    if settings.ops_auth_mode == "development":
        if settings.app_env != "local":
            raise HTTPException(503, "Development authentication is forbidden outside local")
        for secret, roles, subject in [
            (
                settings.ops_dev_token.get_secret_value(),
                ["viewer", "operator", "approver", "admin"],
                "local-admin",
            ),
            (settings.ops_dev_viewer_token.get_secret_value(), ["viewer"], "local-viewer"),
        ]:
            if secret and hmac.compare_digest(token.encode(), secret.encode()):
                return Principal(
                    subject=subject,
                    name=subject.replace("-", " ").title(),
                    roles=roles,
                    authentication="development",
                )
        raise HTTPException(401, "Enter a configured local development token")
    if (
        settings.ops_auth_mode != "oidc"
        or not settings.ops_oidc_issuer
        or not settings.ops_oidc_jwks_url
    ):
        raise HTTPException(503, "Operations authentication requires OIDC configuration")
    if any(
        urlsplit(url).scheme != "https" or not urlsplit(url).hostname
        for url in (settings.ops_oidc_issuer, settings.ops_oidc_jwks_url)
    ):
        raise HTTPException(503, "Operations OIDC issuer and JWKS require HTTPS")
    try:
        key = jwks(settings.ops_oidc_jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=settings.ops_oidc_audience,
            issuer=settings.ops_oidc_issuer,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            leeway=10,
        )
        subject = claims["sub"]
        if not isinstance(subject, str) or not 1 <= len(subject) <= 256:
            raise ValueError("Invalid subject")
        supplied = claims.get(settings.ops_oidc_roles_claim, [])
        roles = (
            [r for r in supplied if r in {"viewer", "operator", "approver", "admin"}]
            if isinstance(supplied, list)
            else []
        )
        return Principal(
            subject=subject,
            name=str(claims.get("name", subject))[:128],
            roles=roles,
            authentication="oidc",
        )
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as error:
        raise HTTPException(401, "Token validation failed") from error


def viewer(user: Annotated[Principal, Depends(principal)]) -> Principal:
    if not set(user.roles).intersection({"viewer", "operator", "approver", "admin"}):
        raise HTTPException(403, "Viewer role required")
    return user


def authorize(user: Principal, role: str) -> None:
    if role not in user.roles and "admin" not in user.roles:
        raise HTTPException(403, f"{role.title()} role required")


def mutation_limit(user: Principal, cache: Redis) -> None:
    key = "ops:mutations:" + hashlib.sha256(user.subject.encode()).hexdigest()
    try:
        count = cache.eval(
            "local n=redis.call('INCR',KEYS[1]); "
            "if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n",
            1,
            key,
        )
        if int(count) > 20:
            raise HTTPException(429, "Mutation rate limit exceeded", headers={"Retry-After": "60"})
    except (RedisError, TypeError, ValueError) as error:
        raise HTTPException(503, "Mutation limits unavailable; changes are disabled") from error


def bridge(authorization: Annotated[str | None, Header()] = None) -> None:
    secret = get_settings().ops_bridge_token.get_secret_value()
    if not secret or not hmac.compare_digest(
        (authorization or "").encode(), f"Bearer {secret}".encode()
    ):
        raise HTTPException(401, "Invalid bridge credentials")


User = Annotated[Principal, Depends(viewer)]
Cache = Annotated[Redis, Depends(get_redis)]

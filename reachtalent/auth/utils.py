import functools
from dataclasses import dataclass

import jwt
import sqlalchemy as sa
from flask import request, current_app, abort, g

from . import tokens
from .models import db, User, Role
from ..core.models import Client
from ..logger import make_logger

logger = make_logger('reachtalent.auth')


@dataclass
class AuthState:
    token: str | None = None
    payload: dict | None = None
    reason: str | None = None
    user: User | None = None
    client: Client | None = None
    role: Role | None = None


def _parse_auth_token_state() -> AuthState:
    auth_state = AuthState(token=request.cookies.get('AuthToken'))

    if header_client_id := request.headers.get('X-Client-ID'):
        try:
            header_client_id = int(header_client_id)
        except ValueError as exc:
            header_client_id = None
            logger.debug(f"Invalid X-Client-ID header value: `{request.headers['X-Client-ID']}` {exc}")

    if auth_state.token:
        try:
            auth_state.payload = tokens.decode(current_app, auth_state.token)
            if auth_state.payload.get('use') != 'auth':
                raise Exception("Invalid token use code `%s`", auth_state.payload.get('use'))
            if not auth_state.payload.get('sub'):
                raise Exception("Missing token sub")
            auth_state.user = db.session.get(User, auth_state.payload['sub'])

            default_client_id = auth_state.payload.get('rti', {}).get('default_client_id')

            client_roles = {
                cr.client_id: cr
                for cr in auth_state.user.client_roles
            }

            active_client_role = next(iter(client_roles)) if client_roles else None
            if header_client_id in client_roles:
                active_client_role = client_roles[header_client_id]
            elif default_client_id in client_roles:
                active_client_role = client_roles[default_client_id]

            if active_client_role:
                auth_state.client = active_client_role.client
                auth_state.role = active_client_role.role

            if auth_state.role is None:
                auth_state.role = Role.query.filter_by(
                    name='Default',
                    client_id=sa.null()).one()

        except jwt.exceptions.ExpiredSignatureError as exc:
            logger.debug("authentication failure due to: %s", exc)
            auth_state.reason = "Token Expired"
        except Exception as exc:
            logger.info("authentication failure due to: %s", exc)
            auth_state.reason = "Invalid Token"
    else:
        auth_state.reason = "Authentication Required"

    return auth_state


def auth_middleware():
    g.auth_state = _parse_auth_token_state()


def authenticated(_func):
    @functools.wraps(_func)
    def wrapped(*args, **kwargs):
        if g.auth_state.reason:
            abort(401, g.auth_state.reason)

        return _func(user=g.auth_state.user, *args, **kwargs)

    return wrapped


def _check_permission(role: Role, required_permission: str):
    # TODO: Enable field level interpolation
    return required_permission in role.perms


def _enforce_permission(role: Role, required_permission: str):
    if _check_permission(role, required_permission):
        return True
    abort(403, "Permission required.")


def requires(permission: str):
    def wrapper(_func):
        @functools.wraps(_func)
        def inner(user, *args, **kwargs):
            _enforce_permission(g.auth_state.role, permission)
            return _func(user, *args, **kwargs)

        return inner

    return wrapper


def has_permission(permission: str) -> bool:
    return _check_permission(g.auth_state.role, permission)

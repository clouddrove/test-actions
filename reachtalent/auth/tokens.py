from datetime import datetime, timedelta

import jwt
from flask import Flask

from .models import User


def make_token(app: Flask,
               use: str,
               sub=None,
               rti_payload: dict = None,
               expires_in: timedelta = timedelta(minutes=5)) -> str:
    """
    Base `jwt.encode` wrapper, used to centralize jwt secret access and standardize JWT payload structure.

    :param app: the flask app, needed to access the JWT_SECRET
    :param use: str value identifying the purpose of the token i.e. auth, passreset
    :param sub: optional, but will be the standardized user id field
    :param rti_payload: any extra data that will be encoded to the `rti` field
    :param expires_in: By default expires in 5 minutes, but other
    :return: str, The encoded JWT
    """

    payload = {
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + expires_in,
        'iss': 'rti',
        'use': use,
        'rti': rti_payload,
    }
    if sub:
        payload['sub'] = sub
    return jwt.encode(payload, key=app.config['JWT_SECRET'], algorithm='HS256')


def make_auth_token(app: Flask, user: User, client_id: int | None = None) -> str:
    client_roles = {
        cr.client_id: f'{cr.client.name} ({cr.role.name})'
        for cr in user.client_roles
    }

    rti_payload = {
        'name': user.name,
        'email': user.email,
        'email_verified': user.email_verified,
        'roles': client_roles,
    }

    if not client_id and client_roles:
        client_id = next(iter(client_roles))

    if client_id:
        rti_payload['default_client_id'] = client_id

    return make_token(
        app,
        use='auth',
        sub=user.id,
        rti_payload=rti_payload)


def make_email_verify_token(app: Flask, user: User):
    return make_token(
        app,
        use='passreset',
        sub=user.id,
        rti_payload={
            'email': user.email,
        },
        expires_in=timedelta(days=1)
    )


def decode(app: Flask, token: str) -> dict:
    return jwt.decode(token, key=app.config['JWT_SECRET'], algorithms=['HS256'])

import re

import jwt
from flask import Flask
from marshmallow import fields, validate, validates, ValidationError

from .utils import AuthState
from ..extensions import marshmallow as ma
from ..logger import make_logger

logger = make_logger('reachtalent.auth')


class LoginRequest(ma.Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True)


class LoginResponse(ma.Schema):
    pass


lowercase = re.compile('[a-z]')
uppercase = re.compile('[A-Z]')
digit = re.compile('[0-9]')


def validate_password_complexity(passwd: str):
    char_class_check = [
        lowercase,
        uppercase,
        digit,
    ]
    for chk in char_class_check:
        if not chk.search(passwd):
            raise ValidationError("Password does not meet complexity requirements")


class SignupRequest(ma.Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True,
                             validate=validate.And(
                                 validate.Length(min=8, max=200),
                                 validate_password_complexity,
                             ))
    name = fields.String(required=True,
                         validate=validate.Length(min=3))


class SignupResponse(ma.Schema):
    pass


class EmailVerifyRequest(ma.Schema):
    token = fields.String(required=True)

    def __init__(self, *args, app: Flask = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.jwt_secret = getattr(app, 'config', {}).get('JWT_SECRET')

    @validates('token')
    def validate_password_reset_token(self, value):
        try:
            payload = jwt.decode(value, key=self.jwt_secret, algorithms=['HS256'])
        except jwt.exceptions.ExpiredSignatureError:
            raise ValidationError("Token is expired")
        except Exception as exc:
            logger.warning("Invalid token received for password reset: `%s` `%s`", value, exc)
            raise ValidationError("Invalid token")

        if payload.get('use') != 'passreset':
            raise ValidationError("Invalid token")

        return value


class EmailVerifyResponse(ma.Schema):
    pass


class SendForgotPasswordRequest(ma.Schema):
    email = fields.Email(required=True)


class SendInviteRequest(ma.Schema):
    email = fields.Email(required=True)


class SendInviteResponse(ma.Schema):
    invite_sent = fields.Boolean(required=True, default=False)


class SendForgotPasswordResponse(ma.Schema):
    pass


class ResetPasswordRequest(ma.Schema):
    password = fields.String(required=True,
                             validate=validate.And(
                                 validate.Length(min=8, max=200),
                                 validate_password_complexity,
                             ))
    token = fields.String(required=True)

    def __init__(self, *args, app: Flask = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.jwt_secret = getattr(app, 'config', {}).get('JWT_SECRET')

    @validates('token')
    def validate_password_reset_token(self, value):
        try:
            payload = jwt.decode(value, key=self.jwt_secret, algorithms=['HS256'])
        except jwt.exceptions.ExpiredSignatureError:
            raise ValidationError("Token is expired")
        except Exception as exc:
            logger.warning("Invalid token received for password reset: `%s` `%s`", value, exc)
            raise ValidationError("Invalid token")

        if payload.get('use') != 'passreset':
            raise ValidationError("Invalid token")

        return value


class ResetPasswordResponse(ma.Schema):
    pass


class AuthSessionRequest(ma.Schema):
    client_id = fields.Integer(required=False)

    def __init__(self, *args, auth_state: AuthState | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_state = auth_state or AuthState(payload={})

    @validates('client_id')
    def validate_client_id(self, value):
        if value is not None:
            roles = self.auth_state.payload.get('rti', {}).get('roles', {})
            if str(value) not in roles:
                raise ValidationError(
                    "User not associated with requested client.")
        return value


class AuthSessionResponse(ma.Schema):
    pass


class PermissionSchema(ma.Schema):
    name = fields.String()
    entity = fields.String()
    field = fields.String()
    action = fields.String()


class GetPermissionResponse(ma.Schema):
    role = fields.String()
    permissions = fields.List(fields.Nested(PermissionSchema()))

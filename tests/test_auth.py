import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from time import sleep

import jwt
import pytest
from sqlalchemy import select

from reachtalent.auth import tokens
from reachtalent.auth.commands import _sync_data
from reachtalent.auth.models import User
from reachtalent.auth.permissions import generate_base_roles, generate_rti_roles
from reachtalent.database import db
from reachtalent.extensions import mail
from reachtalent.schema import ErrorResponse
from .conftest import assert_login_as, params, set_auth_token


def assert_error_resp(response, expected_code, expected_description, expected_errors):
    assert response.status_code == expected_code, "Invalid HTTP Status code"

    try:
        resp_data = ErrorResponse().loads(response.data)
    except Exception as exc:
        pytest.fail(f"Error response failed validation: {exc}", pytrace=False)

    assert resp_data['code'] == expected_code, "Invalid error code"
    assert resp_data['name'] == 'Bad Request', "Invalid error name"
    assert resp_data.get('description') == expected_description, "Invalid error description"
    assert resp_data.get('errors') == expected_errors, "Invalid errors"


class TestLogin:
    invalid_testdata = [
        ({}, None, {'email': ['Missing data for required field.'], 'password': ['Missing data for required field.']}),
        ({'email': 'mario@example.com'}, None, {'password': ['Missing data for required field.']}),
        ({'email': 'unknown@example.com', 'password': 'not hashed'}, 'Invalid credentials', None),
        ({'email': 'mario@example.com', 'password': 'incorrect'}, 'Invalid credentials', None),
    ]

    @pytest.mark.parametrize('payload,expected_description,expected_errors', invalid_testdata)
    def test_invalid_requests(self, client, payload, expected_description, expected_errors):
        response = client.post('/api/auth/login',
                               json=payload,
                               headers={'Content-Type': 'application/json'})
        assert_error_resp(response, 400, expected_description, expected_errors)

    valid_testdata = [
        ({'email': 'mario@example.com', 'password': 'not hashed'}, 1, True),
        ({'email': 'joe@example.com', 'password': 'password1'}, 2, False),
    ]

    @pytest.mark.parametrize('payload,expected_uid,expected_email_verified', valid_testdata)
    def test_login(self, app, client, payload, expected_uid, expected_email_verified):
        # 200 OK
        response = client.post('/api/auth/login',
                               json=payload,
                               headers={'Content-Type': 'application/json'})
        assert response.status_code == 200
        assert response.data == b"{}"

        assert_login_as(
            response, payload['email'],
            user_id=expected_uid,
            email_verified=expected_email_verified
        )
        with app.app_context():
            user = db.session.get(User, 1)
            assert user.auth_provider_id == 1


class TestSignup:
    invalid_testdata = [
        # Submit with no data
        ({}, None,
         {'email': ['Missing data for required field.'],
          'name': ['Missing data for required field.'],
          'password': ['Missing data for required field.']}),
        # Submit with just email
        ({'email': 'mario@example.com'}, None,
         {'name': ['Missing data for required field.'],
          'password': ['Missing data for required field.']}),
        # Submit with just password
        ({'password': 'Not Hashed1'}, None,
         {'email': ['Missing data for required field.'],
          'name': ['Missing data for required field.']}),
        # Submit with just name
        ({'name': 'Mario'}, None,
         {'email': ['Missing data for required field.'],
          'password': ['Missing data for required field.']}),
        # Email invalid
        ({'email': 'not a valid email',
          'password': 'Some Password 1!', 'name': 'Mario'}, None,
         {'email': ['Not a valid email address.']}),
        # Password too short
        ({'email': 'mario@example.com',
          'password': 'short', 'name': 'Mario'}, None,
         {'password': ['Length must be between 8 and 200.',
                       'Password does not meet complexity requirements']}),
        # Password missing complexity
        ({'email': 'mario@example.com',
          'password': 'shortshort', 'name': 'Mario'}, None,
         {'password': ['Password does not meet complexity requirements']}),
    ]

    @pytest.mark.parametrize('payload,expected_description,expected_errors', invalid_testdata)
    def test_signup_invalid(self, client, payload, expected_description, expected_errors):
        response = client.post('/api/auth/signup',
                               json=payload,
                               headers={'Content-Type': 'application/json'})
        assert_error_resp(response, 400, expected_description, expected_errors)

    def test_signup_existing_email(self, client, app):
        with mail.record_messages() as outbox:
            response = client.post('/api/auth/signup',
                                   json={
                                       'email': 'mario@example.com',
                                       'password': 'Some Password 1!',
                                       'name': 'Not Mario',
                                   },
                                   headers={'Content-Type': 'application/json'})
            assert response.status_code == 202
            assert len(outbox) == 1
            assert outbox[0].subject == "Attempted Sign-up to Reach Talent"
            assert outbox[0].recipients == ['mario@example.com']
            assert 'Dear Mario Mario,\n' in outbox[0].body
            assert 'https://reachtalent.com/forgot_password' in outbox[0].body
            assert 'Dear Mario Mario,' in outbox[0].html
            assert 'https://reachtalent.com/forgot_password' in outbox[0].html

        with app.app_context():
            users = db.session.execute(
                User.select_by_email('mario@example.com')
            ).scalars().all()

        assert len(users) == 1
        assert response.data == b'{}'

    def test_signup_valid(self, client, app):
        with mail.record_messages() as outbox:
            response = client.post('/api/auth/signup',
                                   json={
                                       'email': 'jsmith@example.com',
                                       'password': 'Some Password 1!',
                                       'name': 'John Smith',
                                   },
                                   headers={'Content-Type': 'application/json'})
            assert len(outbox) == 1
            assert outbox[0].subject == "Welcome to Reach Talent"
            assert outbox[0].recipients == ['jsmith@example.com']
            assert 'Dear John Smith,\n' in outbox[0].body
            assert 'https://reachtalent.com/verify_email?token=' in outbox[0].body

            assert 'Dear John Smith,' in outbox[0].html
            assert 'https://reachtalent.com/verify_email?token=' in outbox[0].html

        assert response.status_code == 202

        with app.app_context():
            users = db.session.execute(
                select(User).where(User.email == 'jsmith@example.com')
            ).scalars().all()

        assert len(users) == 1
        assert response.data == b'{}'


@dataclass
class EmailVerifyTC:
    payload: dict
    expected_resp: bytes


class TestEmailVerify:

    @pytest.mark.parametrize(*params({
        "Empty Payload": EmailVerifyTC(
            {},
            b'{"code": 400, "errors": {"token": ["Missing data for required field."]}, "name": "Bad Request"}'),
        "Invalid Signature": EmailVerifyTC(
            {'token': jwt.encode({}, key='foobar2', algorithm='HS256')},
            b'{"code": 400, "errors": {"token": ["Invalid token"]}, "name": "Bad Request"}', ),
        "Expired Token": EmailVerifyTC(
            {'token': jwt.encode({'exp': datetime.utcnow() - timedelta(minutes=10)}, key='foobar', algorithm='HS256')},
            b'{"code": 400, "errors": {"token": ["Token is expired"]}, "name": "Bad Request"}'),
        "Invalid token use": EmailVerifyTC(
            {
                'token': jwt.encode({
                    'exp': datetime.utcnow() + timedelta(minutes=5),
                    'use': 'unknown',
                }, key='foobar', algorithm='HS256')
            },
            b'{"code": 400, "errors": {"token": ["Invalid token"]}, "name": "Bad Request"}', ),
        "User not Found": EmailVerifyTC({
            'token': jwt.encode({
                'exp': datetime.utcnow() + timedelta(days=1),
                'sub': 1,
                'use': 'passreset',
                'rti': {
                    'email': 'invalidemail',
                },
            }, key='foobar', algorithm='HS256')},
            b'{"code": 400, "description": "Unable to verify email", "name": "Bad Request"}',
        ),
        "UserID mismatch": EmailVerifyTC(
            {
                'token': jwt.encode({
                    'exp': datetime.utcnow() + timedelta(days=1),
                    'sub': 1,
                    'use': 'passreset',
                    'rti': {
                        'email': 'joe@example.com',
                    }
                }, key='foobar', algorithm='HS256')
            },
            b'{"code": 400, "description": "Unable to verify email", "name": "Bad Request"}'
        ),
    }))
    def test_invalid_email_verify(self, client, app, payload, expected_resp):
        resp = client.post("/api/auth/email_verify", json=payload)

        assert resp.status_code == 400
        assert resp.data == expected_resp

    def test_valid_email_verify(self, client, app):
        random_email = f'{str(uuid.uuid4())}@example.com'
        user = None
        with app.app_context():
            user = User(email=random_email, name='Test User')
            db.session.add(user)
            db.session.commit()
            assert not user.email_verified
            db.session.expunge(user)
            # Give some time for modified_date to change
            sleep(1)

            resp = client.post("/api/auth/email_verify",
                               json={'token': tokens.make_email_verify_token(app, user)})

        assert resp.status_code == 200
        assert resp.data == b'{}'

        with app.app_context():
            db_user = db.session.get(User, user.id)
        assert db_user.email_verified, "User should now be email_verified=True"
        assert db_user.created_date == user.created_date, "Created timestamp should not change"
        assert db_user.modified_date > user.modified_date, "Modified timestamp should be newer"

    def test_email_already_verified(self, client, app):
        user = None
        with app.app_context():
            user = db.session.get(User, 1)
            db.session.expunge(user)

            assert user.email_verified

        resp = client.post("/api/auth/email_verify",
                           json={'token': tokens.make_email_verify_token(app, user)})

        assert resp.status_code == 200
        assert resp.data == b'{}'

        with app.app_context():
            db_user = db.session.get(User, 1)
        assert db_user.email_verified
        assert db_user.modified_date == user.modified_date, "Already verified user should not be updated"


@dataclass
class SendForgotPasswordTC:
    email: str | None = None
    expect_email_send: bool = False
    expected_errors: dict | None = None


@pytest.mark.parametrize(*params({
    'email must be provided': SendForgotPasswordTC(
        expected_errors={'email': ['Missing data for required field.']}),
    'email must be valid': SendForgotPasswordTC(
        'invalid', expected_errors={'email': ['Not a valid email address.']}),
    'dont send email if user does not exist': SendForgotPasswordTC('unknown@unknown.com', False),
    'valid': SendForgotPasswordTC('mario@example.com', True)
}))
def test_send_forgot_password(client, app, email, expect_email_send, expected_errors):
    payload = {}
    if email is not None:
        payload['email'] = email
    with mail.record_messages() as outbox:
        response = client.post('/api/auth/forgot_password/send',
                               json=payload,
                               headers={'Content-Type': 'application/json'})
        if expect_email_send:
            assert len(outbox) == 1
            assert outbox[0].subject == "Password Reset for Reach Talent System"
            assert outbox[0].recipients == [email]
            assert 'Dear Mario Mario,\n' in outbox[0].body
            assert 'https://reachtalent.com/reset_password?token=' in outbox[0].body

            assert 'Dear Mario Mario,' in outbox[0].html
            assert 'https://reachtalent.com/reset_password?token=' in outbox[0].html

        else:
            assert len(outbox) == 0

    if expected_errors:
        assert_error_resp(response, 400, None, expected_errors)
    else:
        assert response.status_code == 202
        assert response.data == b'{}'


@dataclass
class ResetForgotPasswordTC:
    password: str | None = None
    token: dict | str | None = None
    expected_description: str | None = None
    expected_errors: dict | None = None
    expect_password_reset: bool = False


@pytest.mark.parametrize(*params({
    'password must be provided': ResetForgotPasswordTC(
        token={},
        expected_errors={'password': ['Missing data for required field.']},
    ),
    'token must be provided': ResetForgotPasswordTC(
        password='NotAGoodPassword123!',
        expected_errors={'token': ['Missing data for required field.']},
    ),
    'password must meet criteria': ResetForgotPasswordTC(
        password='bad password',
        token={},
        expected_errors={'password': ['Password does not meet complexity requirements']},
    ),
    'token must be valid': ResetForgotPasswordTC(
        password='NotAGoodPassword123!',
        token='asdf',
        expected_errors={'token': ['Invalid token']},
    ),
    'token must have use=passreset': ResetForgotPasswordTC(
        password='NotAGoodPassword123!',
        token={'use': 'just4fun'},
        expected_errors={'token': ['Invalid token']},
    ),
    'token sub must match': ResetForgotPasswordTC(
        password='NotAGoodPassword123!',
        token={'sub': 1},
        expected_description='Unable to reset password.',
    ),
    'user must have email': ResetForgotPasswordTC(
        password='NotAGoodPassword123!',
        token={'rti': {'email': 'shouldnotmatch'}},
        expected_description='Unable to reset password.',
    ),
    'token must not be expired': ResetForgotPasswordTC(
        password='NotAGoodPassword123!',
        token={'exp': datetime.utcnow() - timedelta(minutes=15)},
        expected_errors={'token': ['Token is expired']},
    ),
    'valid': ResetForgotPasswordTC(
        password='NotAGoodPassword123!',
        token={},
        expect_password_reset=True,
    ),
}))
def test_forgot_password_reset(
        client, app,
        password, token,
        expected_description,
        expected_errors,
        expect_password_reset):
    with app.app_context():
        user_before = User.query.filter_by(email='joe@example.com').one()
        db.session.expunge(user_before)

    payload = {}

    if password is not None:
        payload['password'] = password

    if isinstance(token, str):
        payload['token'] = token
    elif isinstance(token, dict):
        token_payload = {
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(minutes=5),
            'iss': 'rti',
            'use': 'passreset',
            'rti': {'email': 'joe@example.com'},
            'sub': 2,
        }
        token_payload.update(token)
        payload['token'] = jwt.encode(token_payload, key='foobar', algorithm='HS256')

    response = client.post('/api/auth/forgot_password/reset',
                           json=payload,
                           headers={'Content-Type': 'application/json'})

    with app.app_context():
        user_after = User.query.filter_by(email='joe@example.com').one()
        db.session.expunge(user_after)

    if expected_description or expected_errors:
        assert_error_resp(response, 400, expected_description, expected_errors)
    else:
        assert response.status_code == 200
        assert response.data == b'{}'

    if expect_password_reset:
        assert user_before.password != user_after.password, "Password should be changed"
    else:
        assert user_before.password == user_after.password, "Password should not be changed"


def test_auth_index(client, app):
    client.set_cookie('localhost', 'AuthToken', tokens.make_auth_token(
        app, User(id=1, email='mario@example.com', name='Mario Mario')))
    response = client.get('/api')
    assert response.data == b'Welcome, Mario Mario'


@dataclass
class AuthPermissionsTC:
    token_payload: dict | str | None = None
    headers: dict | None = None
    exp_status: int = 200
    exp_resp: dict = None


def make_perm_test_data():
    role_to_perm_list = {}
    for role, perms in dict(**generate_base_roles(), **generate_rti_roles()).items():
        perm_list = []
        for perm in perms:
            _ent, _field, _action = perm.split('.')
            perm_list.append({
                'name': perm,
                'entity': _ent,
                'field': _field,
                'action': _action,
            })
        role_to_perm_list[role] = sorted(perm_list, key=lambda r: r['name'])
    return role_to_perm_list


base_role_permissions = make_perm_test_data()


@pytest.mark.parametrize(*params({
    'unauthorized should be rejected': AuthPermissionsTC(
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Authentication Required',
        }),
    'token expired': AuthPermissionsTC(
        token_payload={'exp': datetime.utcnow() - timedelta(minutes=10)},
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Token Expired',
        }
    ),
    'token must have use=auth': AuthPermissionsTC(
        token_payload={'use': 'giggles'},
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Invalid Token',
        }
    ),
    'default role is empty': AuthPermissionsTC(
        token_payload={},  # empty dict means use default
        exp_resp={
            'role': 'Default',
            'permissions': []
        }
    ),
    'worker role has limited permissions': AuthPermissionsTC(
        token_payload={'sub': 104},
        exp_resp={
            'role': 'Worker',
            'permissions': [
                {
                    'name': 'Requisition.*.view',
                    'entity': 'Requisition',
                    'field': '*',
                    'action': 'view',
                }
            ]
        }
    ),
    'hiring manager has limited permissions': AuthPermissionsTC(
        token_payload={'sub': 103},
        exp_resp={
            'role': 'Hiring Manager',
            'permissions': base_role_permissions['Hiring Manager']
        }
    ),
    'client admin role has limited permissions': AuthPermissionsTC(
        token_payload={'sub': 102},
        exp_resp={
            'role': 'Admin',
            'permissions': base_role_permissions['Admin'],
        }
    ),
    'permissions respects X-Client-ID header': AuthPermissionsTC(
        token_payload={'sub': 102},
        headers={'X-Client-ID': '3'},
        exp_resp={
            'role': 'Hiring Manager',
            'permissions': base_role_permissions['Hiring Manager'],
        },
    ),
    'permissions respects X-Client-ID header (lower case)': AuthPermissionsTC(
        token_payload={'sub': 102},
        headers={'x-client-id': '3'},
        exp_resp={
            'role': 'Hiring Manager',
            'permissions': base_role_permissions['Hiring Manager'],
        },
    ),
    'permissions uses default client id when X-Client-ID header is invalid': AuthPermissionsTC(
        token_payload={'sub': 102},
        headers={'x-client-id': 'abc'},
        exp_resp={
            'role': 'Admin',
            'permissions': base_role_permissions['Admin'],
        },
    ),
    'rti admin role has all permissions': AuthPermissionsTC(
        token_payload={'sub': 101},
        exp_resp={
            'role': 'RTI Admin',
            'permissions': base_role_permissions['RTI Admin'],
        }
    ),
}))
def test_auth_permissions(client, app, token_payload, headers, exp_status, exp_resp):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/auth/permissions', headers=headers)
    assert response.json == exp_resp
    assert response.status_code == exp_status


@dataclass
class SendInviteTC:
    exp_resp: dict
    token_payload: dict = None
    payload: dict = None
    exp_status: int = 200
    exp_path_link: str = None


@pytest.mark.parametrize(*params({
    'send invite requires authentication': SendInviteTC(
       exp_status=401,
       exp_resp={'code': 401, 'name': 'Unauthorized', 'description': 'Authentication Required'}),
    'requires create client permission': SendInviteTC(
        exp_status=403,
        exp_resp={'code': 403, 'description': 'Permission required.', 'name': 'Forbidden'},
        token_payload={'sub': 102},
    ),
    'invalid json is handled': SendInviteTC(
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'description': 'Invalid request body.',
        },
        token_payload={'sub': 101},
    ),
    'email is required': SendInviteTC(
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'email': ['Missing data for required field.']},
        },
        token_payload={'sub': 101},
        payload={},
    ),
    'no user found for email returns 404': SendInviteTC(
        exp_status=404,
        exp_resp={'code': 404, 'name': 'Not Found', 'description': 'User not found.'},
        token_payload={'sub': 101},
        payload={'email': f'{uuid.uuid4()}@{uuid.uuid4()}.com'},
    ),
    'user with pass and verified email does not receive email': SendInviteTC(
        exp_status=200,
        exp_resp={'invite_sent': False},
        token_payload={'sub': 101},
        payload={'email': 'mario@example.com'},
    ),
    'user with pass but not verified email receives email with email verify link': SendInviteTC(
        exp_status=200,
        exp_resp={'invite_sent': True},
        token_payload={'sub': 101},
        payload={'email': 'pass-not-verified@invite.com'},
        exp_path_link='verify_email',
    ),
    'user without pass or verified email receives email with password reset link': SendInviteTC(
        exp_status=200,
        exp_resp={'invite_sent': True},
        token_payload={'sub': 101},
        payload={'email': 'no-pass-not-verified@invite.com'},
        exp_path_link='reset_password',
    ),
}))
def test_send_invite(client, app, token_payload, payload, exp_status, exp_resp, exp_path_link):
    set_auth_token(app, client, token_payload)
    with mail.record_messages() as outbox:
        response = client.post('/api/auth/invite', json=payload)
        assert (response.status_code, response.json) == (exp_status, exp_resp)
        email_sent = False
        msg = None
        if len(outbox):
            msg = outbox[0]
            email_sent = True
        if 'email_sent' in exp_resp:
            assert email_sent == exp_resp['email_sent']
        if exp_path_link:
            assert msg.subject == "Welcome to Reach Talent"
            assert msg.recipients == [payload['email']]
            exp_link = f'https://reachtalent.com/{exp_path_link}'
            assert (exp_link in msg.body)
            assert (exp_link in msg.html)


@dataclass
class AssertLoginParams:
    email: str
    email_verified: bool | None = None
    user_id: int | None = None
    name: str | None = None
    client_id: int | None = None


@dataclass
class AuthSessionTC:
    token_payload: dict | str | None = None
    data: dict | None = None
    exp_status: int = 200
    exp_resp: dict = field(default_factory=dict)
    exp_login_as: AssertLoginParams | None = None


@pytest.mark.parametrize(*params({
    'unauthorized should be rejected': AuthSessionTC(
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Authentication Required',
        }),
    'token expired': AuthSessionTC(
        token_payload={'exp': datetime.utcnow() - timedelta(minutes=10)},
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Token Expired',
        }
    ),
    'token must have use=auth': AuthSessionTC(
        token_payload={'use': 'giggles'},
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Invalid Token',
        }
    ),
    'user must be associated with requested client_id': AuthSessionTC(
        token_payload={'sub': 101},
        data={'client_id': 2},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': "Bad Request",
            'errors': {
                'client_id': ['User not associated with requested client.'],
            },
        },
    ),
    'valid - switch client_id': AuthSessionTC(
        token_payload={'sub': 102},
        data={'client_id': 3},
        exp_login_as=AssertLoginParams(
            'admin@example.com',
            name='Client Admin',
            email_verified=False,
            client_id=3),
    ),
    'valid - default client_id': AuthSessionTC(
        token_payload={'sub': 102},
        exp_login_as=AssertLoginParams(
            'admin@example.com',
            name='Client Admin',
            email_verified=False,
            client_id=2),
    ),
}))
def test_auth_session(
        client, app,
        token_payload, data,
        exp_status, exp_resp, exp_login_as):
    set_auth_token(app, client, token_payload)
    response = client.post('/api/auth/session', json=data)
    assert (response.status_code, response.json) == (exp_status, exp_resp)

    if exp_login_as:
        assert_login_as(response, **asdict(AssertLoginParams(*exp_login_as)))
    else:
        assert response.headers.get('Set-Cookie') == None


@dataclass
class SyncDataTC:
    args: list[str]
    exp_exit_code: int = 0
    exp_stderr: bytes = None
    exp_stdout: str = ''


@pytest.mark.parametrize(*params({
    'help info': SyncDataTC(
        args=['auth', 'sync_data', '--help'],
        exp_stdout="""Usage: reachtalent.app auth sync_data [OPTIONS]

Options:
  --dry-run  Show what changes would be made
  --help     Show this message and exit.
"""),
    'dry run': SyncDataTC(
        args=['auth', 'sync_data', '--dry-run'],
        exp_stdout='RTI Client ID=1\n',
    ),
    'non-dry-run': SyncDataTC(
        args=['auth', 'sync_data'],
        exp_stdout='RTI Client ID=1\n',
    ),
}))
def test_sync_data_cli(
        app,
        runner,
        args: list[str],
        exp_exit_code: int, exp_stderr: bytes | None, exp_stdout: str):
    with app.app_context():
        result = runner.invoke(args=args)
        assert (result.exit_code,
                result.stderr_bytes,
                result.stdout) == (exp_exit_code, exp_stderr, exp_stdout)

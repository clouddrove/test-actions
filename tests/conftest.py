import os
import tempfile
from dataclasses import fields, astuple
from datetime import datetime, timedelta, date

import jwt
import pytest
import sqlalchemy as sa
from flask import Response
from werkzeug.http import parse_cookie

from reachtalent import create_app
from reachtalent.auth import tokens
from reachtalent.auth.commands import _sync_data
from reachtalent.auth.models import (
    User, AuthProvider, Role,
)
from reachtalent.auth.views import AUTH_PROVIDERS
from reachtalent.config import Config
from reachtalent.core.commands.update_data import _update_category_data
from reachtalent.core.models import (
    Assignment, AssignmentState, Contract, ContractTerm, ContractTermDefinition,
    Client, ClientUser, Department, Requisition, States, Worker,
)
from reachtalent.extensions import db


@pytest.fixture(scope='session')
def app():
    db_fd, db_path = tempfile.mkstemp()

    test_app = create_app(Config(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        SERVER_NAME='reachtalent.com',
        PREFERRED_URL_SCHEME='https',
        GOOGLE_OAUTH_CLIENT_ID='_google_client_id',
        LINKEDIN_OAUTH_CLIENT_ID='_linkedin_client_id',
        FACEBOOK_OAUTH_CLIENT_ID='_facebook_client_id',
        APPLE_OAUTH_CLIENT_ID='_apple_client_id',
    ))

    with test_app.app_context():
        db.create_all()

        # Create Roles and Permissions
        _sync_data(dry_run=True)  # Need to run dry-run on empty db for coverage
        _sync_data(dry_run=False)
        _update_category_data(True, False)

        client_rti = Client.query.filter_by(name=Client.RTI_CLIENT_NAME).one()
        db.session.add(Department(name='Default', client=client_rti))

        client_example = Client(name='Example')
        db.session.add(client_example)
        department_example = Department(number='1000', name='Example', client=client_example)
        db.session.add(department_example)

        client_other = Client(name='Other')
        db.session.add(client_other)
        db.session.add(Department(name='Other', client=client_other))

        roles = {
            role.name: role
            for role in Role.query.filter_by(client_id=sa.null()).all()
        }

        roles['RTI Admin'] = Role.query.filter_by(
            client_id=client_rti.id, name='RTI Admin').one()

        # Test User
        db.session.add(User(
            id=1,
            email="mario@example.com",
            email_verified=True,
            password="not hashed",
            name="Mario Mario",
        ))
        db.session.add(User(
            id=2,
            email="joe@example.com",
            password="password1",
            name="Joe Smith",
        ))
        db.session.add(User(
            id=3,
            email="no-pass-not-verified@invite.com",
            name="Nopass Notverified",
        ))
        db.session.add(User(
            id=4,
            email="pass-not-verified@invite.com",
            password="password1",
            name="Haspass Notverified",
        ))

        user_rti_admin = User(
            id=101,
            email="admin@reachtalent.com",
            password="password1",
            name="RTI Admin User",
        )
        db.session.add(user_rti_admin)
        db.session.add(ClientUser(
            client=client_rti,
            user=user_rti_admin,
            role=roles['RTI Admin'],
        ))

        user_client_admin = User(
            id=102,
            email="admin@example.com",
            password="password1",
            name="Client Admin",
        )
        db.session.add(user_client_admin)
        db.session.add(ClientUser(
            client=client_example,
            user=user_client_admin,
            role=roles['Admin']))
        db.session.add(ClientUser(
            client=client_other,
            user=user_client_admin,
            role=roles['Hiring Manager'],
        ))

        user_hiring_manager = User(
            id=103,
            email="hm@example.com",
            password="password1",
            name="Hiring Manager",
        )
        db.session.add(user_hiring_manager)
        db.session.add(ClientUser(
            client=client_example,
            user=user_hiring_manager,
            role=roles['Hiring Manager'],
        ))

        user_worker = User(
            id=104,
            email="candidate@example.com",
            password="password1",
            name="Candidate",
        )
        db.session.add(user_worker)
        db.session.add(ClientUser(
            client=client_example,
            user=user_worker,
            role=roles['Worker'],
        ))

        # Test Workers
        requisition_deleted = Requisition(state=States.DELETED, client=client_example)
        db.session.add(requisition_deleted)

        user_bill = User(
            name='Bill Wurtz',
            email='bill@wurtz.com',
        )
        db.session.add(user_bill)

        worker_bill = Worker(user=user_bill)
        db.session.add(worker_bill)

        requisition_deleted.presented_workers.append(worker_bill)

        user_bob = User(
            name='Bob Loblaw',
            email='bobloblaw@lawblog.law',
        )
        db.session.add(user_bob)

        worker_bob = Worker(user=user_bob, phone_number='+1 805 555 5555')
        db.session.add(worker_bob)

        user_other = User(
            id=107,
            email="admin-other@example.com",
            password="password1",
            name="Other Client Admin",
        )
        db.session.add(user_other)
        db.session.add(ClientUser(
            client=client_other,
            user=user_other,
            role=roles['Admin'],
        ))

        assign_bob = Assignment(
            requisition=requisition_deleted,
            worker=worker_bob)
        db.session.add(assign_bob)

        requisition_active = Requisition(state=States.ACTIVE, client=client_example)
        db.session.add(requisition_active)

        active_assignment = Assignment(
            requisition=requisition_active,
            status=AssignmentState.ACTIVE,
            worker=worker_bob,
            pay_rate=30.75,
            bill_rate=15.25,
            department=department_example,
            tentative_start_date=date(2024, 6, 30),
        )
        db.session.add(active_assignment)

        requisition_rti = Requisition(state=States.ACTIVE, client=client_rti)
        db.session.add(requisition_rti)

        assignment_rti = Assignment(
            requisition=requisition_rti,
            status=AssignmentState.PENDING_START,
            worker=worker_bob,
            pay_rate=12.34,
            bill_rate=18.00,
        )
        db.session.add(assignment_rti)

        requisition_for_reject = Requisition(client=client_other)
        db.session.add(requisition_for_reject)

        worker_hm = Worker(user=user_hiring_manager)
        db.session.add(worker_hm)
        requisition_rti.presented_workers = [worker_hm]

        for pk, name in AUTH_PROVIDERS.items():
            db.session.add(AuthProvider(id=pk, name=name))

        db.session.commit()

        yesterday = datetime.utcnow() + timedelta(hours=-24)
        contract = Contract(client=client_example, effective_start_date=yesterday)
        db.session.add(contract)

        defs = {
            ctd.ref: ctd
            for ctd in db.session.execute(sa.select(ContractTermDefinition)).scalars()
        }

        terms = {
            'markup_jobclass_it_pct': 0.05,
            'markup_jobclass_engineering_flat': 15,
        }
        for ref, val in terms.items():
            ctd = defs[ref]
            db.session.add(ContractTerm(contract=contract, contract_term_definition=ctd, val_numeric=val))

        rti_contract = Contract(client=client_rti, effective_start_date=yesterday)
        db.session.add(rti_contract)
        for ref, ctd in defs.items():
            if ref.endswith('_flat'):
                db.session.add(ContractTerm(contract=rti_contract, contract_term_definition=ctd, val_numeric=1))
        db.session.commit()
    yield test_app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope='module')
def cli_app():
    db_fd, db_path = tempfile.mkstemp()

    _app = create_app(Config(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        SERVER_NAME='reachtalent.com',
        PREFERRED_URL_SCHEME='https',
        GOOGLE_OAUTH_CLIENT_ID='_google_client_id',
        LINKEDIN_OAUTH_CLIENT_ID='_linkedin_client_id',
        FACEBOOK_OAUTH_CLIENT_ID='_facebook_client_id',
        APPLE_OAUTH_CLIENT_ID='_apple_client_id',
    ))

    with _app.app_context():
        db.create_all()
    yield _app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


def assert_login_as(
        resp: Response,
        email: str,
        email_verified: bool | None = None,
        user_id: int | None = None,
        name: str | None = None,
        client_id: int | None = None,
):
    cookies = resp.headers.getlist('Set-Cookie')
    cookie = next(
        (cookie for cookie in cookies if 'AuthToken' in cookie),
        None
    )

    assert cookie is not None, "Expected `Set-Cookie AuthToken=...` header is missing"

    cookie_attrs = parse_cookie(cookie)

    assert 'Secure' in cookie_attrs
    assert cookie_attrs['Path'] == '/'
    assert 'HttpOnly' not in cookie_attrs
    assert cookie_attrs['SameSite'] == 'Strict'

    # assert jwt payload
    payload = jwt.decode(cookie_attrs['AuthToken'], key='foobar', algorithms=['HS256'])

    assert payload['use'] == 'auth'
    assert payload['rti']['email'] == email

    if user_id is not None:
        assert payload['sub'] == user_id

    if email_verified is not None:
        assert payload['rti']['email_verified'] == email_verified

    if name is not None:
        assert payload['rti']['name'] == name

    if client_id is not None:
        assert payload['rti']['default_client_id'] == client_id


def params(test_cases) -> (str, list[tuple]):
    test_case_params = []
    param_keys = ''
    for key, value in test_cases.items():
        if not param_keys:
            param_keys = ','.join(f.name for f in fields(value))
        test_case_params.append(pytest.param(*astuple(value), id=key))
    return param_keys, test_case_params


def set_auth_token(app, test_client, token_payload):
    token = None
    user = None
    default_payload = {
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(minutes=5),
        'iss': 'rsi',
        'use': 'auth',
        'sub': 1,
        'rti': {
            'name': 'Mario Mario',
            'email': 'mario@example.com',
            'email_verified': True,
            'client_id': 2,
        },
    }
    if isinstance(token_payload, dict):
        if len(token_payload) == 1 and token_payload.get('sub'):
            with app.app_context():
                user = db.session.get(User, token_payload['sub'])
                token = tokens.make_auth_token(app, user)
        else:
            payload = {**default_payload, **token_payload}
            if payload.get('sub'):
                with app.app_context():
                    user = db.session.get(User, payload['sub'])
            token = jwt.encode(
                payload,
                key='foobar',
                algorithm='HS256',
            )

    if token is not None:
        test_client.set_cookie('localhost', 'AuthToken', token)

    return user


@pytest.fixture
def db_transaction(app):
    with app.app_context():
        engines = db.engines

    cleanup = []

    for key, engine in engines.items():
        c = engine.connect()
        t = c.begin()
        engines[key] = c
        cleanup.append((key, engine, c, t))

    yield db

    for key, engine, c, t in cleanup:
        t.rollback()
        c.close()
        engines[key] = engine

from dataclasses import dataclass
from datetime import datetime, timedelta
import json

import pytest
from sqlalchemy import select
from sqlalchemy.sql import func

from reachtalent.core import schema
from reachtalent.core.models import (
    Department, Position, PurchaseOrder,
    Requisition, Schedule, WorkerEnvironment, Location, States
)
from reachtalent.extensions import db
from .conftest import params, set_auth_token


@dataclass
class CreateTC:
    token_payload: dict | str | None = None
    payload: dict = None
    exp_status: int = 200
    exp_resp: dict = None


@dataclass
class UpdateTC:
    id: int
    exp_resp: dict
    token_payload: dict = None
    payload: dict = None
    exp_status: int = 200


@dataclass
class ListTC:
    token_payload: dict | str
    exp_resp: dict
    query_string: dict = None
    exp_status: int = 200


@dataclass
class CreateDepartmentTC:
    token_payload: dict | str
    payload: dict = None
    exp_status: int = 200
    exp_resp: dict = None
    exp_created: bool = True


DEPARTMENTS = {
    2: {'client_id': 2, 'id': 2, 'name': 'Example', 'number': '1000'},
}

POSITIONS = {
    1: {
        'id': 1,
        'client_id': 2,
        'departments': [DEPARTMENTS[2]],
        'job_description': 'Carry-out tasks in a efficient manner.',
        'is_remote': True,
        'pay_rate_max': 100.66,
        'pay_rate_min': 15.25,
        'requirements': ['Medical License in California.',
                         'Enjoys sunny weather.'],
        'title': 'Production Assistant',
        'worker_environment': {
            'id': 1,
            'client_id': 2,
            'description': 'Worker must be able to lift 60 lbs.',
            'name': 'Lift Requirement',
        },
        'job_classification': {'id': 1, 'label': 'IT'},
    },
    2: {
        'id': 2,
        'client_id': 2,
        'departments': [{'client_id': 2, 'id': 2, 'name': 'Example', 'number': '1000'}],
        'title': 'Production Assistant',
        'job_description': 'Carry-out tasks in a efficient manner.',
        'pay_rate_max': None,
        'pay_rate_min': None,
        'requirements': None,
        'is_remote': False,
        'job_classification': {'id': 1, 'label': 'IT'},
        'worker_environment': {
            'id': 1,
            'client_id': 2,
            'name': 'Lift Requirement',
            'description': 'Worker must be able to lift 60 lbs.',
        },
    },
    3: {},
    4: {
        'id': 4,
        'client_id': 2,
        'departments': [{'client_id': 2, 'id': 2, 'name': 'Example', 'number': '1000'}],
        'job_description': 'Carry-out tasks in a efficient manner.',
        'job_classification': {'id': 1, 'label': 'IT'},
        'title': 'Production Assistant',
        'pay_rate_max': None,
        'pay_rate_min': None,
        'requirements': None,
        'is_remote': False,
        'worker_environment': {
            'id': 1,
            'client_id': 2,
            'name': 'Lift Requirement',
            'description': 'Worker must be able to lift 60 lbs.',
        },
    },
}


def list_categories():
    return [
        {
            'id': 1,
            'description': 'Employee pay categorization for Fair Labor '
                           'Standards Act requirements.',
            'key': 'pay_scheme',
            'label': 'Pay Scheme',
        },
        {
            'id': 2,
            'description': 'Employee pay categorization for Fair Labor '
                           'Standards Act requirements.',
            'key': 'requisition_type',
            'label': 'Requisition Type',
        },
        {
            'id': 3,
            'description': 'Reason that the assignment has ended.',
            'key': 'assignment_end_reason',
            'label': 'Assignment End Reason',
        },
    ]


@pytest.mark.parametrize(*params({
    'RTI Admin can list categories': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 1},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_categories(),
        },
    ),
    'Client Admin can list categories': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_categories(),
        },
    ),
    'Hiring Manager can list categories': ListTC(
        token_payload={'sub': 103},
        query_string={'client_id': 2},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_categories(),
        },
    ),
    'Default cannot list categories': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_category_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/categories', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


def list_category_items(filter_id=None, filter_key=None):
    items = [
        {
            'id': 1,
            'category_id': 1,
            'description': 'Employees exempt from Fair Labor Standards Act '
                           'overtime requirements.',
            'key': 'exempt',
            'label': 'Exempt',
        },
        {
            'id': 2,
            'category_id': 1,
            'description': 'Employees exempt from Fair Labor Standards Act '
                           'overtime requirements.',
            'key': 'nonexempt',
            'label': 'Non-Exempt',
        },
        {
            'id': 3,
            'category_id': 1,
            'description': 'Employees who primarily work on Software and are '
                           'exempt from Fair Labor Standards Act requirements '
                           'but still have overtime benefits.',
            'key': 'cpe',
            'label': 'Computer Professional Exempt',
        },
        {
            'id': 4,
            'category_id': 2,
            'description': 'Employees working full time.',
            'key': 'full_time',
            'label': 'Full Time',
        },
        {
            'id': 5,
            'category_id': 2,
            'description': 'Employees working on part time schedules.',
            'key': 'part_time',
            'label': 'Part-Time'},
        {
            'id': 6,
            'category_id': 2,
            'description': 'Employees working on contractual terms',
            'key': '1099',
            'label': '1099',
        },
        {
            'id': 7,
            'category_id': 3,
            'description': 'Worker decides to leave position.',
            'key': 'voluntary',
            'label': 'Voluntary Assignment End',
        },
        {
            'id': 8,
            'category_id': 3,
            'description': 'Employer decides to remove worker from position.',
            'key': 'involuntary',
            'label': 'Involuntary Assignment End',
        },
        {
            'id': 9,
            'category_id': 3,
            'description': 'Assignment is complete.',
            'key': 'completed',
            'label': 'Assignment Completed',
        },
    ]
    if filter_id is not None:
        items = [it for it in items if it['category_id'] == filter_id]
    if filter_key is not None:
        _id = {
            cat['key']: cat['id']
            for cat in list_categories()
        }[filter_key]

        items = [it for it in items if it['category_id'] == _id]
    return items


@pytest.mark.parametrize(*params({
    'RTI Admin can list category_items': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 1},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_category_items(),
        },
    ),
    'list category_items can be filtered by category_id': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 1, 'category_id': 1},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_category_items(filter_id=1),
        },
    ),
    'list category_items can be filtered by category_key': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 1, 'category_key': 'assignment_end_reason'},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_category_items(filter_key='assignment_end_reason'),
        },
    ),
    'Client Admin can list category_items': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_category_items(),
        },
    ),
    'Hiring Manager can list category_items': ListTC(
        token_payload={'sub': 103},
        query_string={'client_id': 2},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_category_items(),
        },
    ),
    'Default cannot list category_items': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_category_item_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/category_items', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'department name must be unique': CreateDepartmentTC(
        token_payload={'sub': 102},
        payload={
            'number': '1001',
            'name': 'Example',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'name': ['Department name must be unique.'],
            },
        },
        exp_created=False,
    ),
    'department number must be unique': CreateDepartmentTC(
        token_payload={'sub': 102},
        payload={
            'number': '1000',
            'name': 'Example 2',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'number': ['Department number must be unique.'],
            },
        },
        exp_created=False,
    ),
    'Create department requires name': CreateDepartmentTC(
        token_payload={'sub': 102},
        payload={},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'name': ['Missing data for required field.'],
            },
        },
        exp_created=False,
    ),
    'Client Admin cannot create department for other client': CreateDepartmentTC(
        token_payload={'sub': 102},
        payload={'client_id': 1, 'name': 'Unique Department'},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'client_id': ['Invalid client.'],
            },
        },
        exp_created=False,
    ),
    'RTI Admin can create department for other client': CreateDepartmentTC(
        token_payload={'sub': 101},
        payload={'client_id': 2, 'name': 'Unique Department'},
        exp_resp={
            'id': 4,
            'client_id': 2,
            'name': 'Unique Department',
            'number': None,
        },
    ),
    'RTI Admin must provide client_id': CreateDepartmentTC(
        token_payload={'sub': 101},
        payload={'name': 'Unique Department'},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'client_id': ['Missing data for required field.'],
            },
        },
        exp_created=False,
    ),
    'Client Admin can create department': CreateDepartmentTC(
        token_payload={'sub': 102},
        payload={'name': 'Second Department'},
        exp_resp={
            'id': 4,
            'client_id': 2,
            'name': 'Second Department',
            'number': None,
        },
    ),
    'Hiring Manager cannot create department': CreateDepartmentTC(
        token_payload={'sub': 103},
        payload={'name': 'Second Department'},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
        exp_created=False,
    ),
    'Default cannot create department': CreateDepartmentTC(
        token_payload={'sub': 1},
        payload={'name': 'Default Users Department'},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
        exp_created=False,
    ),
}))
def test_department_create(
        app, client,
        token_payload, payload,
        exp_status, exp_resp, exp_created):
    with app.app_context():
        last_id, last_created_date = db.session.execute(
            select(
                func.max(Department.id),
                func.max(Department.created_date)
            )).first()

    set_auth_token(app, client, token_payload)
    response = client.post('/api/departments', json=payload)
    assert (response.status_code, response.json) == (exp_status, exp_resp)

    created_obj = None
    with app.app_context():
        new_last_id, new_last_created_date = db.session.execute(
            select(
                func.max(Department.id),
                func.max(Department.created_date)
            )).first()
        if exp_status == 200 and 'id' in response.json:
            created_obj = db.session.get(Department, response.json['id'])

    if exp_created:
        assert (last_id, last_created_date) != (new_last_id, new_last_created_date)
        assert created_obj.created_uid == token_payload['sub']
        assert created_obj.modified_uid == token_payload['sub']

        # Clean up
        # TODO: Wrap tests in db transaction
        with app.app_context():
            db.session.delete(created_obj)
            db.session.commit()
    else:
        assert (last_id, last_created_date) == (new_last_id, new_last_created_date)


@pytest.mark.parametrize(*params({
    'RTI Admin can list departments': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 1},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': [
                {'id': 1, 'client_id': 1, 'name': 'Default', 'number': None},
            ],
        },
    ),
    'Client Admin can list departments': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': [
                {
                    'id': 2,
                    'client_id': 2,
                    'name': 'Example',
                    'number': '1000',
                },
            ],
        },
    ),
    'Hiring Manager can list departments': ListTC(
        token_payload={'sub': 103},
        query_string={'client_id': 2},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': [
                {
                    'id': 2,
                    'client_id': 2,
                    'name': 'Example',
                    'number': '1000',
                },
            ],
        },
    ),
    'Default cannot list departments': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_department_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/departments', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'unauthorized should be rejected': CreateTC(
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Authentication Required',
        }),
    'default role may not create cost_center': CreateTC(
        token_payload={},  # empty dict means use default
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'candidate role may not create cost_center': CreateTC(
        token_payload={'sub': 104},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'hiring manager cannot create cost_center': CreateTC(
        token_payload={'sub': 103},
        exp_status=403,
        exp_resp={'code': 403, 'description': 'Permission required.', 'name': 'Forbidden'},
    ),
    'client admin requires fields': CreateTC(
        token_payload={'sub': 102},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'name': ['Missing data for required field.']},
        },
    ),
    'client admin cannot create position for other client': CreateTC(
        token_payload={'sub': 102},
        payload={'client_id': 1, 'name': 'R&D'},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'client admin can create purchase order': CreateTC(
        token_payload={'sub': 102},
        payload={
            'client_id': 2,
            'name': 'R&D',
            'description': 'Research and Development',
        },
        exp_resp={
            'id': 1,
            'client_id': 2,
            'name': 'R&D',
            'description': 'Research and Development',
        },
    ),
    'rti admin must supply client_id': CreateTC(
        token_payload={'sub': 101},
        payload={'name': 'OpEx'},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Missing data for required field.']},
        },
    ),
    'rti admin can create purchase order for other client': CreateTC(
        token_payload={'sub': 101},
        payload={
            'client_id': 2,
            'name': 'OpEx',
            'description': 'Operating Expense',
        },
        exp_resp={
            'id': 2,
            'client_id': 2,
            'name': 'OpEx',
            'description': 'Operating Expense',
        },
    ),
    'rti admin can create purchase order': CreateTC(
        token_payload={'sub': 101},
        payload={
            'client_id': 1,
            'name': 'OpEx',
            'description': 'Operating Expense',
        },
        exp_resp={
            'id': 3,
            'client_id': 1,
            'name': 'OpEx',
            'description': 'Operating Expense',
        },
    ),
}))
def test_cost_center_create(client, app, token_payload, payload, exp_status, exp_resp):
    set_auth_token(app, client, token_payload)
    response = client.post('/api/cost_centers', json=payload)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


def list_cost_center_items():
    return [
        {
            'id': 1,
            'client_id': 2,
            'description': 'Research and Development',
            'name': 'R&D',
        },
        {
            'id': 2,
            'client_id': 2,
            'name': 'OpEx',
            'description': 'Operating Expense',
        },
        {
            'id': 3,
            'client_id': 1,
            'name': 'OpEx',
            'description': 'Operating Expense',
        },
    ]


@pytest.mark.parametrize(*params({
    'RTI Admin can list all cost_center': ListTC(
        token_payload={'sub': 101},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_cost_center_items(),
        },
    ),
    'RTI Admin can filter cost_center by client_id': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 1},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_cost_center_items()[2:],
        },
    ),
    'Client Admin can list cost_center': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_cost_center_items()[:2],
        },
    ),
    'Hiring Manager can list cost_center': ListTC(
        token_payload={'sub': 103},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_cost_center_items()[:2],
        },
    ),
    'Default cannot list cost_center': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_cost_center_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/cost_centers', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'unauthorized should be rejected': CreateTC(
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Authentication Required',
        }),
    'default role may not create cost_center': CreateTC(
        token_payload={},  # empty dict means use default
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'candidate role may not create cost_center': CreateTC(
        token_payload={'sub': 104},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'hiring manager cannot create cost_center': CreateTC(
        token_payload={'sub': 103},
        exp_status=403,
        exp_resp={'code': 403, 'description': 'Permission required.', 'name': 'Forbidden'},
    ),
    'client admin requires fields': CreateTC(
        token_payload={'sub': 102},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'name': ['Missing data for required field.']},
        },
    ),
    'client admin cannot create position for other client': CreateTC(
        token_payload={'sub': 102},
        payload={'client_id': 1, 'name': 'R&D'},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'client admin can create purchase order': CreateTC(
        token_payload={'sub': 102},
        payload={
            'client_id': 2,
            'name': 'R&D',
            'description': 'Research and Development',
        },
        exp_resp={
            'id': 1,
            'client_id': 2,
            'name': 'R&D',
            'description': 'Research and Development',
        },
    ),
    'rti admin must supply client_id': CreateTC(
        token_payload={'sub': 101},
        payload={'name': 'OpEx'},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Missing data for required field.']},
        },
    ),
    'rti admin can create purchase order for other client': CreateTC(
        token_payload={'sub': 101},
        payload={
            'client_id': 2,
            'name': 'OpEx',
            'description': 'Operating Expense',
        },
        exp_resp={
            'id': 2,
            'client_id': 2,
            'name': 'OpEx',
            'description': 'Operating Expense',
        },
    ),
    'rti admin can create purchase order': CreateTC(
        token_payload={'sub': 101},
        payload={
            'client_id': 1,
            'name': 'OpEx',
            'description': 'Operating Expense',
        },
        exp_resp={
            'id': 3,
            'client_id': 1,
            'name': 'OpEx',
            'description': 'Operating Expense',
        },
    ),
}))
def test_cost_center_create(client, app, token_payload, payload, exp_status, exp_resp):
    set_auth_token(app, client, token_payload)
    response = client.post('/api/cost_centers', json=payload)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


def list_cost_center_items():
    return [
        {
            'id': 1,
            'client_id': 2,
            'description': 'Research and Development',
            'name': 'R&D',
        },
        {
            'id': 2,
            'client_id': 2,
            'name': 'OpEx',
            'description': 'Operating Expense',
        },
        {
            'id': 3,
            'client_id': 1,
            'name': 'OpEx',
            'description': 'Operating Expense',
        },
    ]


@pytest.mark.parametrize(*params({
    'RTI Admin can list all cost_center': ListTC(
        token_payload={'sub': 101},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_cost_center_items(),
        },
    ),
    'RTI Admin can filter cost_center by client_id': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 1},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_cost_center_items()[2:],
        },
    ),
    'Client Admin can list cost_center': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_cost_center_items()[:2],
        },
    ),
    'Hiring Manager can list cost_center': ListTC(
        token_payload={'sub': 103},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_cost_center_items()[:2],
        },
    ),
    'Default cannot list cost_center': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_cost_center_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/cost_centers', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


def list_staff_items():
    return [
        {
            'id': 2,
            'title': None,
            'phone_number': None,
            'role': {'name': 'Admin'},
            'user': {
                'id': 102,
                'name': 'Client Admin',
                'email': 'admin@example.com',
            },
        },
        {
            'id': 4,
            'title': None,
            'phone_number': None,
            'role': {'name': 'Hiring Manager'},
            'user': {
                'id': 103,
                'name': 'Hiring Manager',
                'email': 'hm@example.com',
            },
        },
        {
            'id': 5,
            'title': None,
            'phone_number': None,
            'role': {'name': 'Worker'},
            'user': {
                'id': 104,
                'name': 'Candidate',
                'email': 'candidate@example.com',
            },
        },
    ]


@pytest.mark.parametrize(*params({
    'RTI Admin can list staff': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 1},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': [
                {
                    'id': 1,
                    'title': None,
                    'phone_number': None,
                    'role': {'name': 'RTI Admin'},
                    'user': {
                        'id': 101,
                        'name': 'RTI Admin User',
                        'email': 'admin@reachtalent.com',
                    },
                },
            ],
        },
    ),
    'Client Admin can list staff': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_staff_items(),
        },
    ),
    'Hiring Manager can list staff': ListTC(
        token_payload={'sub': 103},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_staff_items(),
        },
    ),
    'Default cannot list staff': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_staff_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/staff', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'RTI Admin can query contract_terms': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 2},
        exp_resp={'markup_jobclass_engineering_flat': 15.0, 'markup_jobclass_it_pct': 0.05},
    ),
    'RTI Admin can query contract_terms in past': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 2, 'effective_date': '2020-01-01'},
        exp_resp={},
    ),
    'RTI Admin can query contract_terms by term_prefix': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 2, 'term_prefix': 'markup_jobclass_engineering_'},
        exp_resp={'markup_jobclass_engineering_flat': 15.0},
    ),
    'Default cannot list job_classifications': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_query_contract_terms(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/contract_terms', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


def list_job_class_items():
    return [
        {
            'id': 1,
            'label': 'IT',
        },
        {
            'id': 2,
            'label': 'Engineering',
        },
        {
            'id': 3,
            'label': 'Light Industrial',
        },
        {
            'id': 4,
            'label': 'Heavy Industrial',
        },
        {
            'id': 5,
            'label': 'Administrative',
        },
        {
            'id': 6,
            'label': 'Accounting',
        },
        {
            'id': 7,
            'label': 'Creative',
        },
        {
            'id': 8,
            'label': 'Legal',
        },
        {
            'id': 9,
            'label': 'Driver',
        },
        {
            'id': 10,
            'label': 'Events',
        },
        {
            'id': 11,
            'label': 'Sales',
        },
    ]


@pytest.mark.parametrize(*params({
    'RTI Admin can list job_classifications': ListTC(
        token_payload={'sub': 101},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_job_class_items(),
        },
    ),
    'RTI Admin can list job_classifications for client': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 2},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_job_class_items()[:2],
        },
    ),
    'Client without contract has no job_classifications': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 3},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 0, 'page_size': 25},
            'items': [],
        },
    ),
    'Client Admin can list job_classifications': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_job_class_items()[:2],
        },
    ),
    'Hiring Manager can list job_classifications': ListTC(
        token_payload={'sub': 103},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_job_class_items()[:2],
        },
    ),
    'Default cannot list job_classifications': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_job_class_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/job_classifications', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'unauthorized should be rejected': CreateTC(
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Authentication Required',
        }),
    'default role may not create purchase_order': CreateTC(
        token_payload={},  # empty dict means use default
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'candidate role may not create purchase_order': CreateTC(
        token_payload={'sub': 104},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'hiring manager cannot create purchase_order': CreateTC(
        token_payload={'sub': 103},
        exp_status=403,
        exp_resp={'code': 403, 'description': 'Permission required.', 'name': 'Forbidden'},
    ),
    'client admin requires fields': CreateTC(
        token_payload={'sub': 102},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'ext_ref': ['Missing data for required field.']},
        },
    ),
    'client admin cannot create position for other client': CreateTC(
        token_payload={'sub': 102},
        payload={'client_id': 1, 'ext_ref': 'purchase-order-number'},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'client admin cannot assign department from other client': CreateTC(
        token_payload={'sub': 102},
        payload={
            'client_id': 2,
            'ext_ref': 'purchase-order-number',
            'department_ids': [1],
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'department_ids': ['Invalid department.']},
        },
    ),
    'client admin can create purchase order': CreateTC(
        token_payload={'sub': 102},
        payload={'client_id': 2, 'ext_ref': 'purchase-order-number'},
        exp_resp={
            'id': 1,
            'client_id': 2,
            'ext_ref': 'purchase-order-number',
            'departments': [],
        },
    ),
    'rti admin must supply client_id': CreateTC(
        token_payload={'sub': 101},
        payload={'ext_ref': 'purchase-order-number'},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Missing data for required field.']},
        },
    ),
    'rti admin can create purchase order': CreateTC(
        token_payload={'sub': 101},
        payload={'client_id': 1, 'ext_ref': 'purchase-order-number'},
        exp_resp={
            'id': 2,
            'client_id': 1,
            'ext_ref': 'purchase-order-number',
            'departments': [],
        },
    ),
    'rti admin can create purchase order for other client': CreateTC(
        token_payload={'sub': 101},
        payload={
            'client_id': 2,
            'ext_ref': 'purchase-order-number',
            'department_ids': [2],
        },
        exp_resp={
            'id': 3,
            'client_id': 2,
            'ext_ref': 'purchase-order-number',
            'departments': [{'client_id': 2, 'id': 2, 'name': 'Example', 'number': '1000'}],
        },
    ),
}))
def test_purchase_order_create(client, app, token_payload, payload, exp_status, exp_resp):
    set_auth_token(app, client, token_payload)
    response = client.post('/api/purchase_orders', json=payload)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'RTI Admin can list purchase_order': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 1},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': [
                {
                    'client_id': 1,
                    'departments': [],
                    'ext_ref': 'purchase-order-number',
                    'id': 2,
                },
            ],
        },
    ),
    'Client Admin can list purchase_order': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': [
                {
                    'client_id': 2,
                    'departments': [],
                    'ext_ref': 'purchase-order-number',
                    'id': 1,
                },
                {
                    'client_id': 2,
                    'departments': [{'client_id': 2, 'id': 2, 'name': 'Example', 'number': '1000'}],
                    'ext_ref': 'purchase-order-number',
                    'id': 3,
                },
            ],
        },
    ),
    'Hiring Manager can list purchase_order': ListTC(
        token_payload={'sub': 103},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': [
                {
                    'client_id': 2,
                    'departments': [],
                    'ext_ref': 'purchase-order-number',
                    'id': 1,
                },
                {
                    'client_id': 2,
                    'departments': [{'client_id': 2, 'id': 2, 'name': 'Example', 'number': '1000'}],
                    'ext_ref': 'purchase-order-number',
                    'id': 3,
                },
            ],
        },
    ),
    'Default cannot list purchase_order': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_purchase_order_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/purchase_orders', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'unauthorized should be rejected': UpdateTC(
        id=1,
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Authentication Required',
        }),
    'default role may not update purchase orders': UpdateTC(
        id=1,
        token_payload={},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'candidate role may not update purchase orders': UpdateTC(
        id=1,
        token_payload={'sub': 104},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'hiring manager cannot update purchase orders': UpdateTC(
        id=1,
        token_payload={'sub': 103},
        exp_status=403,
        exp_resp={'code': 403, 'description': 'Permission required.', 'name': 'Forbidden'},
    ),
    'client admin requires fields': UpdateTC(
        id=1,
        token_payload={'sub': 102},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'ext_ref': ['Missing data for required field.']},
        },
    ),
    'client admin cannot update purchase orders for other client': UpdateTC(
        id=2,
        token_payload={'sub': 102},
        payload={'ext_ref': 'purchase-order-number', 'department_ids': [2]},
        exp_status=404,
        exp_resp={
            'code': 404,
            'name': 'Not Found',
            'description': 'Resource not found.',
        },
    ),
    'client admin cannot supply invalid client_id': UpdateTC(
        id=1,
        token_payload={'sub': 102},
        payload={
            'client_id': 1,
            'ext_ref': 'purchase-order-number',
            'department_ids': [1],
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'client admin cannot assign department from other client': UpdateTC(
        id=1,
        token_payload={'sub': 102},
        payload={
            'ext_ref': 'purchase-order-number',
            'department_ids': [1],
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'department_ids': ['Invalid department.']},
        },
    ),
    'client admin can update purchase order': UpdateTC(
        id=1,
        token_payload={'sub': 102},
        payload={'client_id': 2, 'ext_ref': 'purchase-order-number2'},
        exp_resp={
            'id': 1,
            'client_id': 2,
            'ext_ref': 'purchase-order-number2',
            'departments': [],
        },
    ),
    'client admin can add departments': UpdateTC(
        id=1,
        token_payload={'sub': 102},
        payload={'ext_ref': 'purchase-order-number3', 'department_ids': [2]},
        exp_resp={
            'id': 1,
            'client_id': 2,
            'ext_ref': 'purchase-order-number3',
            'departments': [{'client_id': 2, 'id': 2, 'name': 'Example', 'number': '1000'}],
        },
    ),
    'client admin can remove departments': UpdateTC(
        id=1,
        token_payload={'sub': 102},
        payload={'ext_ref': 'purchase-order-number3', 'department_ids': []},
        exp_resp={
            'id': 1,
            'client_id': 2,
            'ext_ref': 'purchase-order-number3',
            'departments': [],
        },
    ),
    'object doesnt exist 404s': UpdateTC(
        id=9999,
        token_payload={'sub': 101},
        payload={'client_id': 1, 'ext_ref': 'purchase-order-number'},
        exp_status=404,
        exp_resp={
            'code': 404,
            'name': 'Not Found',
            'description': 'Resource not found.',
        },
    ),
    'rti admin can update purchase order': UpdateTC(
        id=2,
        token_payload={'sub': 101},
        payload={'client_id': 1, 'ext_ref': 'purchase-order-number2', 'department_ids': [1]},
        exp_resp={
            'id': 2,
            'client_id': 1,
            'ext_ref': 'purchase-order-number2',
            'departments': [{'client_id': 1, 'id': 1, 'name': 'Default', 'number': None}],
        },
    ),
    'rti admin cannot add incorrect department': UpdateTC(
        id=1,
        token_payload={'sub': 101},
        payload={
            'client_id': 2,
            'ext_ref': 'purchase-order-number',
            'department_ids': [3],
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'department_ids': ['Invalid department.']}
        },
    ),
    'rti admin cannot update purchase client': UpdateTC(
        id=3,
        token_payload={'sub': 101},
        payload={
            'client_id': 3,
            'ext_ref': 'purchase-order-number',
            'department_ids': [3],
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']}
        },
    ),
    'rti admin can update purchase order for other client': UpdateTC(
        id=3,
        token_payload={'sub': 101},
        payload={
            'client_id': 2,
            'ext_ref': 'purchase-order-number',
            'department_ids': [2],
        },
        exp_resp={
            'id': 3,
            'client_id': 2,
            'ext_ref': 'purchase-order-number',
            'departments': [{'client_id': 2, 'id': 2, 'name': 'Example', 'number': '1000'}],
        },
    ),
}))
def test_purchase_order_update(client, app, token_payload, id, payload, exp_status, exp_resp):
    set_auth_token(app, client, token_payload)
    response = client.post(f'/api/purchase_orders/{id}', json=payload)
    assert (response.status_code, response.json) == (exp_status, exp_resp)
    if exp_status == 200:
        with app.app_context():
            obj = db.session.get(PurchaseOrder, id)
            assert schema.PurchaseOrder().dump(obj) == response.json
            assert obj.modified_uid == token_payload['sub']


def list_requisition_type_items():
    return [
        {
            'id': 4,
            'name': 'full_time',
            'display_name': 'Full Time',
        },
        {
            'id': 5,
            'name': 'part_time',
            'display_name': 'Part-Time',
        },
        {
            'id': 6,
            'name': '1099',
            'display_name': '1099',
        },
    ]


@pytest.mark.parametrize(*params({
    'RTI Admin can list requisition_types': ListTC(
        token_payload={'sub': 101},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_requisition_type_items(),
        },
    ),
    'Client Admin can list requisition_types': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_requisition_type_items(),
        },
    ),
    'Hiring Manager can list requisition_types': ListTC(
        token_payload={'sub': 103},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_requisition_type_items(),
        },
    ),
    'Default cannot list requisition_types': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_requisition_type_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/requisition_types', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


def list_pay_scheme_items():
    return [
        {
            'id': 1,
            'name': 'exempt',
            'display_name': 'Exempt',
        },
        {
            'id': 2,
            'name': 'nonexempt',
            'display_name': 'Non-Exempt',
        },
        {
            'id': 3,
            'name': 'cpe',
            'display_name': 'Computer Professional Exempt',
        },
    ]


@pytest.mark.parametrize(*params({
    'RTI Admin can list pay_schemes': ListTC(
        token_payload={'sub': 101},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_pay_scheme_items(),
        },
    ),
    'Client Admin can list pay_schemes': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_pay_scheme_items(),
        },
    ),
    'Hiring Manager can list pay_schemes': ListTC(
        token_payload={'sub': 103},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_pay_scheme_items(),
        },
    ),
    'Default cannot list pay_schemes': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_pay_scheme_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/pay_schemes', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'unauthorized should be rejected': CreateTC(
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Authentication Required',
        }),
    'default role may not create worker_environments': CreateTC(
        token_payload={},  # empty dict means use default
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'candidate role may not create worker_environments': CreateTC(
        token_payload={'sub': 104},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'hiring manager can create worker_environments': CreateTC(
        token_payload={'sub': 103},
        payload={
            'name': 'Lift Requirement',
            'description': 'Worker must be able to lift 60 lbs.',
        },
        exp_status=200,
        exp_resp={
            'id': 1,
            'client_id': 2,
            'name': 'Lift Requirement',
            'description': 'Worker must be able to lift 60 lbs.',
        },
    ),
    'client admin requires fields': CreateTC(
        token_payload={'sub': 102},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'name': ['Missing data for required field.'],
                'description': ['Missing data for required field.'],
            },
        },
    ),
    'client admin cannot create worker_environment for other client': CreateTC(
        token_payload={'sub': 102},
        payload={
            'client_id': 1,
            'name': 'Lift Requirement',
            'description': 'Worker must be able to lift 60 lbs.',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'client admin can create worker_environment': CreateTC(
        token_payload={'sub': 102},
        payload={
            'name': 'Hazardous Material',
            'description': 'Worker may be exposed to hazardous material',
        },
        exp_resp={
            'id': 2,
            'client_id': 2,
            'name': 'Hazardous Material',
            'description': 'Worker may be exposed to hazardous material',
        },
    ),
    'rti admin must supply client_id': CreateTC(
        token_payload={'sub': 101},
        payload={
            'name': 'Lift Requirement',
            'description': 'Worker must be able to lift 60 lbs.',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Missing data for required field.']},
        },
    ),
    'rti admin can create worker_environment': CreateTC(
        token_payload={'sub': 101},
        payload={
            'client_id': 1,
            'name': 'Lift Requirement',
            'description': 'Worker must be able to lift 60 lbs.',
        },
        exp_resp={
            'id': 3,
            'client_id': 1,
            'name': 'Lift Requirement',
            'description': 'Worker must be able to lift 60 lbs.',
        },
    ),
    'rti admin can create worker_environment for other client': CreateTC(
        token_payload={'sub': 101},
        payload={
            'client_id': 2,
            'name': 'None',
            'description': 'No explicit requirements.',
        },
        exp_resp={
            'id': 4,
            'client_id': 2,
            'name': 'None',
            'description': 'No explicit requirements.',
        },
    ),
}))
def test_worker_environments_create(client, app, token_payload, payload, exp_status, exp_resp):
    user = set_auth_token(app, client, token_payload)
    response = client.post('/api/worker_environments', json=payload)
    assert (response.status_code, response.json) == (exp_status, exp_resp)

    if response.status_code == 200:
        with app.app_context():
            obj = db.session.get(WorkerEnvironment, response.json['id'])
            assert obj.created_uid == user.id
            assert obj.modified_uid == user.id
            assert schema.WorkerEnvironment().dump(obj) == response.json


def list_worker_environment_items():
    return [
        {
            'id': 1,
            'client_id': 2,
            'name': 'Lift Requirement',
            'description': 'Worker must be able to lift 60 lbs.',
        },
        {
            'id': 2,
            'client_id': 2,
            'name': 'Hazardous Material',
            'description': 'Worker may be exposed to hazardous material',
        },
        {
            'id': 4,
            'client_id': 2,
            'name': 'None',
            'description': 'No explicit requirements.',
        },
    ]


@pytest.mark.parametrize(*params({
    'RTI Admin can list worker_environments': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 2},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_worker_environment_items(),
        },
    ),
    'Client Admin may not list worker_environments for other client': ListTC(
        token_payload={'sub': 102},
        query_string={'client_id': 3},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'Client Admin can list worker_environments': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_worker_environment_items(),
        },
    ),
    'Hiring Manager can list worker_environments': ListTC(
        token_payload={'sub': 103},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_worker_environment_items(),
        },
    ),
    'Default cannot list worker_environments': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_worker_environment_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/worker_environments', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


def list_position_items():
    return [
        POSITIONS[1],
        POSITIONS[2],
        POSITIONS[4],
    ]


@pytest.mark.parametrize(*params({
    'unauthorized should be rejected': CreateTC(
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Authentication Required',
        }),
    'default role may not create positions': CreateTC(
        token_payload={},  # empty dict means use default
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'candidate role may not create positions': CreateTC(
        token_payload={'sub': 104},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'hiring manager can create positions': CreateTC(
        token_payload={'sub': 103},
        payload={
            'department_ids': [2],
            'worker_environment_id': 1,
            'job_classification_id': 1,
            'title': 'Production Assistant',
            'job_description': 'Carry-out tasks in a efficient manner.',
            'requirements': [
                'Medical License in California.',
                'Enjoys sunny weather.',
            ],
            'pay_rate_min': 15.25,
            'pay_rate_max': 100.66,
            'is_remote': True,
        },
        exp_status=200,
        exp_resp=list_position_items()[0],
    ),
    'client admin requires fields': CreateTC(
        token_payload={'sub': 102},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'department_ids': ['Missing data for required field.'],
                'title': ['Missing data for required field.'],
                'job_description': ['Missing data for required field.'],
                'worker_environment_id': ['Missing data for required field.'],
                'job_classification_id': ['Missing data for required field.'],
            },
        },
    ),
    'client admin cannot create position for other client': CreateTC(
        token_payload={'sub': 102},
        payload={
            'client_id': 1,
            'department_ids': [2],
            'worker_environment_id': 1,
            'job_classification_id': 1,
            'title': 'Production Assistant',
            'job_description': 'Carry-out tasks in a efficient manner.'
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'client admin can create position': CreateTC(
        token_payload={'sub': 102},
        payload={
            'department_ids': [2],
            'worker_environment_id': 1,
            'job_classification_id': 1,
            'title': 'Production Assistant',
            'job_description': 'Carry-out tasks in a efficient manner.'
        },
        exp_resp=list_position_items()[1],
    ),
    'rti admin must supply client_id': CreateTC(
        token_payload={'sub': 101},
        payload={
            'department_ids': [2],
            'worker_environment_id': 1,
            'job_classification_id': 1,
            'title': 'Production Assistant',
            'job_description': 'Carry-out tasks in a efficient manner.'
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Missing data for required field.']},
        },
    ),
    'rti admin can create position': CreateTC(
        token_payload={'sub': 101},
        payload={
            'client_id': 1,
            'department_ids': [1],
            'worker_environment_id': 3,
            'job_classification_id': 1,
            'title': 'Production Assistant',
            'job_description': 'Carry-out tasks in a efficient manner.'
        },
        exp_resp={
            'id': 3,
            'client_id': 1,
            'departments': [{'client_id': 1, 'id': 1, 'name': 'Default', 'number': None}],
            'title': 'Production Assistant',
            'job_description': 'Carry-out tasks in a efficient manner.',
            'pay_rate_max': None,
            'pay_rate_min': None,
            'requirements': None,
            'is_remote': False,
            'job_classification': {'id': 1, 'label': 'IT'},
            'worker_environment': {
                'id': 3,
                'client_id': 1,
                'name': 'Lift Requirement',
                'description': 'Worker must be able to lift 60 lbs.',
            },
        },
    ),
    'rti admin can create position for other client': CreateTC(
        token_payload={'sub': 101},
        payload={
            'client_id': 2,
            'department_ids': [2],
            'worker_environment_id': 1,
            'job_classification_id': 1,
            'title': 'Production Assistant',
            'job_description': 'Carry-out tasks in a efficient manner.'
        },
        exp_resp=list_position_items()[2],
    ),
}))
def test_positions_create(client, app, token_payload, payload, exp_status, exp_resp):
    user = set_auth_token(app, client, token_payload)
    response = client.post('/api/positions', json=payload)
    assert (response.status_code, response.json) == (exp_status, exp_resp)

    if response.status_code == 200:
        with app.app_context():
            obj = db.session.get(Position, response.json['id'])
            assert obj.created_uid == user.id
            assert obj.modified_uid == user.id
            assert json.loads(schema.Position().dumps(obj)) == response.json


@pytest.mark.parametrize(*params({
    'RTI Admin can list positions': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 2},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_position_items(),
        },
    ),
    'Client Admin may not list positions for other client': ListTC(
        token_payload={'sub': 102},
        query_string={'client_id': 3},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'Client Admin can list positions': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_position_items(),
        },
    ),
    'Hiring Manager can list positions': ListTC(
        token_payload={'sub': 103},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_position_items(),
        },
    ),
    'Default cannot list positions': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_position_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/positions', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'unauthorized should be rejected': CreateTC(
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Authentication Required',
        }),
    'default role may not create schedules': CreateTC(
        token_payload={},  # empty dict means use default
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'candidate role may not create schedules': CreateTC(
        token_payload={'sub': 104},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'hiring manager can create schedules': CreateTC(
        token_payload={'sub': 103},
        payload={
            'name': 'Standard',
            'description': 'Monday through Friday, 9AM to 6PM',
        },
        exp_status=200,
        exp_resp={
            'id': 1,
            'client_id': 2,
            'name': 'Standard',
            'description': 'Monday through Friday, 9AM to 6PM',
        },
    ),
    'client admin requires fields': CreateTC(
        token_payload={'sub': 102},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'name': ['Missing data for required field.'],
                'description': ['Missing data for required field.'],
            },
        },
    ),
    'client admin cannot create schedule for other client': CreateTC(
        token_payload={'sub': 102},
        payload={
            'client_id': 1,
            'name': 'Standard',
            'description': 'Monday through Friday, 9AM to 6PM',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'client admin can create schedule': CreateTC(
        token_payload={'sub': 102},
        payload={
            'name': 'Night Crew',
            'description': 'Sunday through Thursday, 8PM to 4AM',
        },
        exp_resp={
            'id': 2,
            'client_id': 2,
            'name': 'Night Crew',
            'description': 'Sunday through Thursday, 8PM to 4AM',
        },
    ),
    'rti admin must supply client_id': CreateTC(
        token_payload={'sub': 101},
        payload={
            'name': 'Night Crew',
            'description': 'Sunday through Thursday, 8PM to 4AM',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Missing data for required field.']},
        },
    ),
    'rti admin can create schedule': CreateTC(
        token_payload={'sub': 101},
        payload={
            'client_id': 1,
            'name': 'Night Crew',
            'description': 'Sunday through Thursday, 8PM to 4AM',
        },
        exp_resp={
            'id': 3,
            'client_id': 1,
            'name': 'Night Crew',
            'description': 'Sunday through Thursday, 8PM to 4AM',
        },
    ),
    'rti admin can create schedule for other client': CreateTC(
        token_payload={'sub': 101},
        payload={
            'client_id': 2,
            'name': 'Weekend Overnight',
            'description': 'Friday 5PM through Monday 9AM',
        },
        exp_resp={
            'id': 4,
            'client_id': 2,
            'name': 'Weekend Overnight',
            'description': 'Friday 5PM through Monday 9AM',
        },
    ),
}))
def test_schedules_create(client, app, token_payload, payload, exp_status, exp_resp):
    user = set_auth_token(app, client, token_payload)
    response = client.post('/api/schedules', json=payload)
    assert (response.status_code, response.json) == (exp_status, exp_resp)

    if response.status_code == 200:
        with app.app_context():
            obj = db.session.get(Schedule, response.json['id'])
            assert obj.created_uid == user.id
            assert obj.modified_uid == user.id
            assert schema.Schedule().dump(obj) == response.json


def list_schedule_items():
    return [
        {
            'id': 1,
            'client_id': 2,
            'name': 'Standard',
            'description': 'Monday through Friday, 9AM to 6PM',
        },
        {
            'id': 2,
            'client_id': 2,
            'name': 'Night Crew',
            'description': 'Sunday through Thursday, 8PM to 4AM',
        },
        {
            'id': 4,
            'client_id': 2,
            'name': 'Weekend Overnight',
            'description': 'Friday 5PM through Monday 9AM',
        },
    ]


@pytest.mark.parametrize(*params({
    'RTI Admin can list schedules': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 2},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_schedule_items(),
        },
    ),
    'Client Admin may not list schedules for other client': ListTC(
        token_payload={'sub': 102},
        query_string={'client_id': 3},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'Client Admin can list schedules': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_schedule_items(),
        },
    ),
    'Hiring Manager can list schedules': ListTC(
        token_payload={'sub': 103},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_schedule_items(),
        },
    ),
    'Default cannot list schedules': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_schedule_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/schedules', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'unauthorized should be rejected': CreateTC(
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Authentication Required',
        }),
    'default role may not create locations': CreateTC(
        token_payload={},  # empty dict means use default
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'candidate role may not create locations': CreateTC(
        token_payload={'sub': 104},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'hiring manager can create locations': CreateTC(
        token_payload={'sub': 103},
        payload={
            'name': 'HQ',
            'description': 'Central Office - Head Quarters',
            'street': '2555 Garden Road, Suite H',
            'city': 'Monterey',
            'state': 'CA',
            'zip': '93940',
            'country': 'US',
        },
        exp_status=200,
        exp_resp={
            'id': 1,
            'client_id': 2,
            'name': 'HQ',
            'description': 'Central Office - Head Quarters',
            'street': '2555 Garden Road, Suite H',
            'city': 'Monterey',
            'state': 'CA',
            'zip': '93940',
            'country': 'US',
        },
    ),
    'client admin requires fields': CreateTC(
        token_payload={'sub': 102},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'name': ['Missing data for required field.'],
                'description': ['Missing data for required field.'],
                'street': ['Missing data for required field.'],
                'city': ['Missing data for required field.'],
                'state': ['Missing data for required field.'],
                'zip': ['Missing data for required field.'],
                'country': ['Missing data for required field.'],
            },
        },
    ),
    'client admin cannot create location for other client': CreateTC(
        token_payload={'sub': 102},
        payload={
            'client_id': 1,
            'name': 'HQ',
            'description': 'Central Office - Head Quarters',
            'street': '2555 Garden Road, Suite H',
            'city': 'Monterey',
            'state': 'CA',
            'zip': '93940',
            'country': 'US',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'client admin can create location': CreateTC(
        token_payload={'sub': 102},
        payload={
            'name': 'One Culver',
            'description': 'Los Angeles Area Office - Co-working space',
            'street': '10000 Washington Blvd',
            'city': 'Culver City',
            'state': 'CA',
            'zip': '90232',
            'country': 'US',
        },
        exp_resp={
            'id': 2,
            'client_id': 2,
            'name': 'One Culver',
            'description': 'Los Angeles Area Office - Co-working space',
            'street': '10000 Washington Blvd',
            'city': 'Culver City',
            'state': 'CA',
            'zip': '90232',
            'country': 'US',
        },
    ),
    'rti admin must supply client_id': CreateTC(
        token_payload={'sub': 101},
        payload={
            'name': 'HQ',
            'description': 'Central Office - Head Quarters',
            'street': '2555 Garden Road, Suite H',
            'city': 'Monterey',
            'state': 'CA',
            'zip': '93940',
            'country': 'US',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Missing data for required field.']},
        },
    ),
    'rti admin can create location': CreateTC(
        token_payload={'sub': 101},
        payload={
            'client_id': 1,
            'name': 'HQ',
            'description': 'Central Office - Head Quarters',
            'street': '2555 Garden Road, Suite H',
            'city': 'Monterey',
            'state': 'CA',
            'zip': '93940',
            'country': 'US',
        },
        exp_resp={
            'id': 3,
            'client_id': 1,
            'name': 'HQ',
            'description': 'Central Office - Head Quarters',
            'street': '2555 Garden Road, Suite H',
            'city': 'Monterey',
            'state': 'CA',
            'zip': '93940',
            'country': 'US',
        },
    ),
    'rti admin can create location for other client': CreateTC(
        token_payload={'sub': 101},
        payload={
            'client_id': 2,
            'name': 'Denver',
            'description': 'MTN Time Zone Location',
            'street': '1234 Main St.',
            'city': 'Denver',
            'state': 'CA',
            'zip': '34512',
            'country': 'US',
        },
        exp_resp={
            'id': 4,
            'client_id': 2,
            'name': 'Denver',
            'description': 'MTN Time Zone Location',
            'street': '1234 Main St.',
            'city': 'Denver',
            'state': 'CA',
            'zip': '34512',
            'country': 'US',
        },
    ),
}))
def test_locations_create(client, app, token_payload, payload, exp_status, exp_resp):
    user = set_auth_token(app, client, token_payload)
    response = client.post('/api/locations', json=payload)
    assert (response.status_code, response.json) == (exp_status, exp_resp)

    if response.status_code == 200:
        with app.app_context():
            obj = db.session.get(Location, response.json['id'])
            assert obj.created_uid == user.id
            assert obj.modified_uid == user.id
            assert schema.Location().dump(obj) == response.json


def list_location_items():
    return [
        {
            'id': 1,
            'client_id': 2,
            'name': 'HQ',
            'description': 'Central Office - Head Quarters',
            'street': '2555 Garden Road, Suite H',
            'city': 'Monterey',
            'state': 'CA',
            'zip': '93940',
            'country': 'US',
        },
        {
            'id': 2,
            'client_id': 2,
            'name': 'One Culver',
            'description': 'Los Angeles Area Office - Co-working space',
            'street': '10000 Washington Blvd',
            'city': 'Culver City',
            'state': 'CA',
            'zip': '90232',
            'country': 'US',
        },
        {
            'id': 4,
            'client_id': 2,
            'name': 'Denver',
            'description': 'MTN Time Zone Location',
            'street': '1234 Main St.',
            'city': 'Denver',
            'state': 'CA',
            'country': 'US',
            'zip': '34512',
        },
    ]


@pytest.mark.parametrize(*params({
    'RTI Admin can list locations': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 2},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_location_items(),
        },
    ),
    'Client Admin may not list locations for other client': ListTC(
        token_payload={'sub': 102},
        query_string={'client_id': 3},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'Client Admin can list locations': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_location_items(),
        },
    ),
    'Hiring Manager can list locations': ListTC(
        token_payload={'sub': 103},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_location_items(),
        },
    ),
    'Default cannot list locations': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_location_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/locations', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


def list_available_worker_items():
    return [
        {
            'id': 1,
            'phone_number': None,
            'user': {
                'id': 105,
                'name': 'Bill Wurtz',
                'email': 'bill@wurtz.com',
            },
        },
        {
            'id': 2,
            'phone_number': '+1 805 555 5555',
            'user': {
                'id': 106,
                'name': 'Bob Loblaw',
                'email': 'bobloblaw@lawblog.law',
            },
        },
    ]


@pytest.mark.parametrize(*params({
    'RTI Admin can list available_workers': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 2},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_available_worker_items(),
        },
    ),
    'Client Admin may not list available_workers for other client': ListTC(
        token_payload={'sub': 102},
        query_string={'client_id': 3},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'Client Admin can list available_workers': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_available_worker_items(),
        },
    ),
    'Hiring Manager can list available_workers': ListTC(
        token_payload={'sub': 103},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_available_worker_items(),
        },
    ),
    'exclude workers for requisition': ListTC(
        token_payload={'sub': 103},
        query_string={'for_requisition_id': 2},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': [list_available_worker_items()[0]],
        },
    ),
    'Default cannot list available_workers': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_available_worker_list(
        app, client,
        token_payload, query_string,
        exp_status, exp_resp
):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/available_workers', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


def list_requisition_items():
    return [
        {
            'id': 2,
            'additional_information': '',
            'approval_state': 'PENDING',
            'approvals': [],
            'assignments': [{'actual_end_date': None,
                             'actual_start_date': None,
                             'bill_rate': 15.25,
                             'cancel_notes': None,
                             'cost_center': None,
                             'department': {'client_id': 2,
                                            'id': 2,
                                            'name': 'Example',
                                            'number': '1000'},
                             'end_notes': None,
                             'end_reason': None,
                             'id': 2,
                             'pay_rate': 30.75,
                             'replaced_by_assignment_id': None,
                             'requisition_id': 2,
                             'status': 'ACTIVE',
                             'system_start_date': None,
                             'tentative_end_date': None,
                             'tentative_start_date': '2024-06-30',
                             'timesheets_web_punchable': True,
                             'timesheets_worker_editable': False,
                             'worker': {'id': 2,
                                        'phone_number': '+1 805 555 5555',
                                        'user': {'email': 'bobloblaw@lawblog.law',
                                                 'id': 106,
                                                 'name': 'Bob Loblaw'}}}],
            'client_id': 2,
            'department': None,
            'employee_info': None,
            'estimated_end_date': None,
            'location': None,
            'num_assignments': 1,
            'pay_rate': None,
            'pay_scheme': None,
            'position': None,
            'presented_workers': [],
            'purchase_order': None,
            'requisition_type': None,
            'schedule': None,
            'start_date': None,
            'supervisor': None,
            'timecard_approver': None,
        },
        {
            'id': 5,
            'additional_information': '',
            'approval_state': 'PENDING',
            'approvals': [],
            'assignments': [],
            'client_id': 2,
            'department': DEPARTMENTS[2],
            'employee_info': None,
            'estimated_end_date': '2023-12-31',
            'num_assignments': 1,
            'pay_rate': 18.5,
            'pay_scheme': {
                'id': 1,
                'display_name': 'Exempt',
                'name': 'exempt',
            },
            'position': POSITIONS[1],
            'presented_workers': [],
            'purchase_order': None,
            'requisition_type': {
                'id': 4,
                'display_name': 'Full Time',
                'name': 'full_time',
            },
            'schedule': {
                'id': 1,
                'client_id': 2,
                'description': 'Monday through Friday, 9AM to 6PM',
                'name': 'Standard',
            },
            'start_date': '2023-12-01',
            'supervisor': {
                'id': 103,
                'email': 'hm@example.com',
                'name': 'Hiring Manager',
            },
            'timecard_approver': {
                'id': 103,
                'email': 'hm@example.com',
                'name': 'Hiring Manager',
            },
            'location': {
                'id': 1,
                'city': 'Monterey',
                'client_id': 2,
                'country': 'US',
                'description': 'Central Office - Head Quarters',
                'name': 'HQ',
                'state': 'CA',
                'street': '2555 Garden Road, Suite H',
                'zip': '93940',
            },
        },
        {
            'id': 6,
            'additional_information': '',
            'approval_state': 'PENDING',
            'approvals': [],
            'assignments': [],
            'client_id': 2,
            'department': DEPARTMENTS[2],
            'employee_info': None,
            'estimated_end_date': '2023-12-31',
            'num_assignments': 1,
            'pay_rate': 18.5,
            'pay_scheme': {
                'id': 1,
                'display_name': 'Exempt',
                'name': 'exempt',
            },
            'position': POSITIONS[1],
            'presented_workers': list_available_worker_items(),
            'purchase_order': {
                'id': 1,
                'client_id': 2,
                'departments': [],
                'ext_ref': 'purchase-order-number3',
            },
            'requisition_type': {
                'id': 4,
                'display_name': 'Full Time',
                'name': 'full_time',
            },
            'schedule': {
                'id': 1,
                'client_id': 2,
                'description': 'Monday through Friday, 9AM to 6PM',
                'name': 'Standard',
            },
            'start_date': '2023-12-01',
            'supervisor': {
                'id': 102,
                'email': 'admin@example.com',
                'name': 'Client Admin',
            },
            'timecard_approver': {
                'id': 102,
                'email': 'admin@example.com',
                'name': 'Client Admin',
            },
            'location': {
                'id': 1,
                'city': 'Monterey',
                'client_id': 2,
                'country': 'US',
                'description': 'Central Office - Head Quarters',
                'name': 'HQ',
                'state': 'CA',
                'street': '2555 Garden Road, Suite H',
                'zip': '93940',
            },
        },
        {
            'id': 7,
            'additional_information': 'Urgent need!',
            'approval_state': 'PENDING',
            'approvals': [],
            'assignments': [],
            'client_id': 2,
            'department': DEPARTMENTS[2],
            'employee_info': {
                'additional_information': 'Established work relationship.',
                'associate_name': 'Danny Trejo',
                'email': 'dtrejo@example.com',
                'preferred_name': 'Machete'},
            'estimated_end_date': '2023-12-31',
            'num_assignments': 1,
            'pay_rate': 18.5,
            'pay_scheme': {
                'id': 1,
                'display_name': 'Exempt',
                'name': 'exempt',
            },
            'position': POSITIONS[1],
            'presented_workers': [],
            'purchase_order': {
                'id': 1,
                'client_id': 2,
                'departments': [],
                'ext_ref': 'purchase-order-number3',
            },
            'requisition_type': {
                'id': 4,
                'display_name': 'Full Time',
                'name': 'full_time',
            },
            'schedule': {
                'id': 1,
                'client_id': 2,
                'description': 'Monday through Friday, 9AM to 6PM',
                'name': 'Standard',
            },
            'start_date': '2023-12-01',
            'supervisor': {
                'id': 102,
                'email': 'admin@example.com',
                'name': 'Client Admin',
            },
            'timecard_approver': {
                'id': 102,
                'email': 'admin@example.com',
                'name': 'Client Admin',
            },
            'location': {
                'id': 1,
                'city': 'Monterey',
                'client_id': 2,
                'country': 'US',
                'description': 'Central Office - Head Quarters',
                'name': 'HQ',
                'state': 'CA',
                'street': '2555 Garden Road, Suite H',
                'zip': '93940',
            },
        },
    ]


@pytest.mark.parametrize(*params({
    'unauthorized should be rejected': CreateTC(
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Authentication Required',
        }),
    'token expired': CreateTC(
        token_payload={'exp': datetime.utcnow() - timedelta(minutes=10)},
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Token Expired',
        }
    ),
    'token must have use=auth': CreateTC(
        token_payload={'use': 'giggles'},
        exp_status=401,
        exp_resp={
            'code': 401,
            'name': "Unauthorized",
            'description': 'Invalid Token',
        }
    ),
    'default role may not create requisitions': CreateTC(
        token_payload={},  # empty dict means use default
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'candidate role may not create requisitions': CreateTC(
        token_payload={'sub': 104},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'hiring manager can create requisitions': CreateTC(
        token_payload={'sub': 103},
        payload={
            'purchase_order_id': None,
            'position_id': 1,
            'department_id': 2,
            'location_id': 1,
            'requisition_type_id': 4,
            'pay_scheme_id': 1,
            'schedule_id': 1,
            'num_assignments': 1,
            'pay_rate': 18.50,
            'start_date': '2023-12-01',
            'estimated_end_date': '2023-12-31',
            'supervisor_user_id': None,
            'timecard_approver_user_id': None,
        },
        exp_resp=list_requisition_items()[1]
    ),
    'fields are required': CreateTC(
        token_payload={'sub': 102},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'department_id': ['Missing data for required field.'],
                'estimated_end_date': ['Missing data for required field.'],
                'num_assignments': ['Missing data for required field.'],
                'pay_rate': ['Missing data for required field.'],
                'pay_scheme_id': ['Missing data for required field.'],
                'position_id': ['Missing data for required field.'],
                'requisition_type_id': ['Missing data for required field.'],
                'schedule_id': ['Missing data for required field.'],
                'start_date': ['Missing data for required field.'],
                'location_id': ['Missing data for required field.']},
        },
    ),
    'client admin cannot create requisitions for other client': CreateTC(
        token_payload={'sub': 102},
        payload={
            'client_id': 1,
            'purchase_order_id': 1,
            'position_id': 1,
            'department_id': 2,
            'location_id': 1,
            'requisition_type_id': 4,
            'pay_scheme_id': 1,
            'schedule_id': 1,
            'num_assignments': 1,
            'pay_rate': 18.50,
            'start_date': '2023-12-01',
            'estimated_end_date': '2023-12-31',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'client admin cannot use entities from other clients': CreateTC(
        token_payload={'sub': 102},
        payload={
            'purchase_order_id': 2,
            'position_id': 3,
            'department_id': 1,
            'location_id': 3,
            'supervisor_user_id': 1,
            'timecard_approver_user_id': 1,
            'present_worker_ids': [3],
            'requisition_type_id': 9999,
            'pay_scheme_id': 9999,
            'schedule_id': 3,
            'num_assignments': 1,
            'pay_rate': 18.50,
            'start_date': '2023-12-01',
            'estimated_end_date': '2023-12-31',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'purchase_order_id': ['Invalid purchase_order_id.'],
                'position_id': ['Invalid position_id.'],
                'department_id': ['Invalid department_id.'],
                'supervisor_user_id': ['Invalid supervisor_user_id.'],
                'timecard_approver_user_id': ['Invalid timecard_approver_user_id.'],
                'location_id': ['Invalid location_id.'],
                'requisition_type_id': ['Invalid requisition_type_id.'],
                'pay_scheme_id': ['Invalid pay_scheme_id.'],
                'schedule_id': ['Invalid schedule_id.'],
                'present_worker_ids': ['Invalid worker_id.'],
            },
        },
    ),
    'client admin can create requisitions': CreateTC(
        token_payload={'sub': 102},
        payload={
            'purchase_order_id': 1,
            'position_id': 1,
            'department_id': 2,
            'location_id': 1,
            'requisition_type_id': 4,
            'pay_scheme_id': 1,
            'schedule_id': 1,
            'num_assignments': 1,
            'present_worker_ids': [1, 2],
            'pay_rate': 18.50,
            'start_date': '2023-12-01',
            'estimated_end_date': '2023-12-31',
        },
        exp_resp=list_requisition_items()[2]
    ),
    'rti admin requires client_id, supervisor_user_id, timecard_approver_id': CreateTC(
        token_payload={'sub': 101},
        payload={
            'position_id': 1,
            'department_id': 2,
            'location_id': 1,
            'requisition_type_id': 4,
            'pay_scheme_id': 1,
            'schedule_id': 1,
            'num_assignments': 1,
            'pay_rate': 18.50,
            'start_date': '2023-12-01',
            'estimated_end_date': '2023-12-31',
            'timecard_approver_user_id': None,
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'client_id': ['Missing data for required field.'],
                'supervisor_user_id': ['Missing data for required field.'],
                'timecard_approver_user_id': ['Missing data for required field.'],
            },
        },
    ),
    'rti admin can create requisitions': CreateTC(
        token_payload={'sub': 101},
        payload={
            'client_id': 2,
            'purchase_order_id': 1,
            'position_id': 1,
            'department_id': 2,
            'location_id': 1,
            'requisition_type_id': 4,
            'pay_scheme_id': 1,
            'schedule_id': 1,
            'supervisor_user_id': 102,
            'timecard_approver_user_id': 102,
            'num_assignments': 1,
            'pay_rate': 18.50,
            'start_date': '2023-12-01',
            'estimated_end_date': '2023-12-31',
            'additional_information': "Urgent need!",
            'employee_info': {
                'associate_name': 'Danny Trejo',
                'preferred_name': 'Machete',
                'email': 'dtrejo@example.com',
                'additional_information': 'Established work relationship.',
            }
        },
        exp_resp=list_requisition_items()[3]
    ),
}))
def test_requisition_create(client, app, token_payload, payload, exp_status, exp_resp):
    set_auth_token(app, client, token_payload)
    response = client.post('/api/requisitions', json=payload)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'RTI Admin can list requisitions': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 2},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_requisition_items(),
        },
    ),
    'Client Admin may not list requisitions for other client': ListTC(
        token_payload={'sub': 102},
        query_string={'client_id': 3},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'Client Admin can list requisitions': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_requisition_items(),
        },
    ),
    'Hiring Manager can list requisitions': ListTC(
        token_payload={'sub': 103},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_requisition_items(),
        },
    ),
    'Default cannot list requisitions': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_requisition_list(client, app, token_payload, query_string, exp_status, exp_resp):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/requisitions', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


@dataclass
class GetTC:
    token_payload: dict | str
    id: int
    exp_resp: dict
    exp_status: int = 200


@pytest.mark.parametrize(*params({
    'RTI Admin get requisition': GetTC(
        token_payload={'sub': 101},
        id=5,
        exp_resp=list_requisition_items()[1],
    ),
    'Client Admin may not get requisition for other client': GetTC(
        token_payload={'sub': 102},
        id=3,
        exp_status=404,
        exp_resp={
            'code': 404,
            'name': 'Not Found',
            'description': 'Resource not found.',
        },
    ),
    'may not get deleted requisition': GetTC(
        token_payload={'sub': 102},
        id=1,
        exp_status=404,
        exp_resp={
            'code': 404,
            'name': 'Not Found',
            'description': 'Resource not found.',
        },
    ),
    'Client Admin can get requisition': GetTC(
        token_payload={'sub': 102},
        id=6,
        exp_resp=list_requisition_items()[2],
    ),
    'Hiring Manager can get requisition': GetTC(
        token_payload={'sub': 103},
        id=7,
        exp_resp=list_requisition_items()[3],
    ),
    'Default cannot get requisitions': GetTC(
        token_payload={'sub': 1},
        id=2,
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_requisition_detail(client, app, token_payload, id, exp_status, exp_resp):
    set_auth_token(app, client, token_payload)
    response = client.get(f'/api/requisitions/{id}')
    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'default role may not update requisitions': UpdateTC(
        token_payload={},  # empty dict means use default
        id=2,
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'cant update deleted requisitions': UpdateTC(
        token_payload={'sub': 103},
        id=1,
        payload={
            'purchase_order_id': 1,
            'position_id': 1,
            'department_id': 2,
            'location_id': 1,
            'requisition_type_id': 4,
            'pay_scheme_id': 1,
            'schedule_id': 1,
            'num_assignments': 1,
            'pay_rate': 18.50,
            'start_date': '2023-12-01',
            'estimated_end_date': '2023-12-31',
        },
        exp_status=404,
        exp_resp={
            'code': 404,
            'name': 'Not Found',
            'description': 'Resource not found.',
        }
    ),
    'hiring manager can update requisitions': UpdateTC(
        token_payload={'sub': 103},
        id=2,
        payload={
            'position_id': 1,
            'department_id': 2,
            'location_id': 1,
            'requisition_type_id': 4,
            'pay_scheme_id': 1,
            'schedule_id': 1,
            'num_assignments': 1,
            'pay_rate': 18.50,
            'start_date': '2023-12-01',
            'estimated_end_date': '2023-12-31',
        },
        exp_resp={
            'id': 2,
            'additional_information': '',
            'approval_state': 'PENDING',
            'approvals': [],
            'assignments': [{'actual_end_date': None,
                             'actual_start_date': None,
                             'bill_rate': 15.25,
                             'cancel_notes': None,
                             'cost_center': None,
                             'department': {'client_id': 2,
                                            'id': 2,
                                            'name': 'Example',
                                            'number': '1000'},
                             'end_notes': None,
                             'end_reason': None,
                             'id': 2,
                             'pay_rate': 30.75,
                             'replaced_by_assignment_id': None,
                             'requisition_id': 2,
                             'status': 'ACTIVE',
                             'system_start_date': None,
                             'tentative_end_date': None,
                             'tentative_start_date': '2024-06-30',
                             'timesheets_web_punchable': True,
                             'timesheets_worker_editable': False,
                             'worker': {'id': 2,
                                        'phone_number': '+1 805 555 5555',
                                        'user': {'email': 'bobloblaw@lawblog.law',
                                                 'id': 106,
                                                 'name': 'Bob Loblaw'}}}],
            'client_id': 2,
            'department': DEPARTMENTS[2],
            'employee_info': None,
            'estimated_end_date': '2023-12-31',
            'num_assignments': 1,
            'pay_rate': 18.5,
            'pay_scheme': {'display_name': 'Exempt', 'id': 1, 'name': 'exempt'},
            'position': POSITIONS[1],
            'purchase_order': None,
            'requisition_type': {
                'id': 4,
                'display_name': 'Full Time',
                'name': 'full_time',
            },
            'schedule': {
                'id': 1,
                'client_id': 2,
                'description': 'Monday through Friday, 9AM to 6PM',
                'name': 'Standard',
            },
            'start_date': '2023-12-01',
            'supervisor': {
                'id': 103,
                'name': 'Hiring Manager',
                'email': 'hm@example.com',
            },
            'timecard_approver': {
                'id': 103,
                'name': 'Hiring Manager',
                'email': 'hm@example.com',
            },
            'location': {
                'id': 1,
                'client_id': 2,
                'name': 'HQ',
                'description': 'Central Office - Head Quarters',
                'street': '2555 Garden Road, Suite H',
                'city': 'Monterey',
                'state': 'CA',
                'zip': '93940',
                'country': 'US',
            },
            'presented_workers': [],
        },
    ),
    'fields are required': UpdateTC(
        token_payload={'sub': 102},
        id=3,
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'department_id': ['Missing data for required field.'],
                'estimated_end_date': ['Missing data for required field.'],
                'num_assignments': ['Missing data for required field.'],
                'pay_rate': ['Missing data for required field.'],
                'pay_scheme_id': ['Missing data for required field.'],
                'position_id': ['Missing data for required field.'],
                'requisition_type_id': ['Missing data for required field.'],
                'schedule_id': ['Missing data for required field.'],
                'start_date': ['Missing data for required field.'],
                'location_id': ['Missing data for required field.']},
        },
    ),
    'client admin cannot update requisitions for other client': UpdateTC(
        token_payload={'sub': 102},
        id=99,
        payload={
            'client_id': 1,
            'purchase_order_id': 1,
            'position_id': 1,
            'department_id': 2,
            'location_id': 1,
            'requisition_type_id': 4,
            'pay_scheme_id': 1,
            'schedule_id': 1,
            'num_assignments': 1,
            'pay_rate': 18.50,
            'start_date': '2023-12-01',
            'estimated_end_date': '2023-12-31',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'client admin cannot use entities from other clients': UpdateTC(
        token_payload={'sub': 102},
        id=3,
        payload={
            'purchase_order_id': 2,
            'position_id': 3,
            'department_id': 1,
            'location_id': 3,
            'supervisor_user_id': 1,
            'timecard_approver_user_id': 1,
            'present_worker_ids': [3],
            'requisition_type_id': 9999,
            'pay_scheme_id': 9999,
            'schedule_id': 3,
            'num_assignments': 1,
            'pay_rate': 18.50,
            'start_date': '2023-12-01',
            'estimated_end_date': '2023-12-31',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'purchase_order_id': ['Invalid purchase_order_id.'],
                'position_id': ['Invalid position_id.'],
                'department_id': ['Invalid department_id.'],
                'supervisor_user_id': ['Invalid supervisor_user_id.'],
                'timecard_approver_user_id': ['Invalid timecard_approver_user_id.'],
                'location_id': ['Invalid location_id.'],
                'requisition_type_id': ['Invalid requisition_type_id.'],
                'pay_scheme_id': ['Invalid pay_scheme_id.'],
                'schedule_id': ['Invalid schedule_id.'],
                'present_worker_ids': ['Invalid worker_id.'],
            },
        },
    ),
    'client admin can update requisitions': UpdateTC(
        token_payload={'sub': 102},
        id=5,
        payload={
            'purchase_order_id': 1,
            'position_id': 1,
            'department_id': 2,
            'location_id': 1,
            'requisition_type_id': 4,
            'pay_scheme_id': 1,
            'schedule_id': 1,
            'num_assignments': 1,
            'present_worker_ids': [1, 2],
            'pay_rate': 18.50,
            'start_date': '2023-12-01',
            'estimated_end_date': '2023-12-31',
        },
        exp_resp={
            'id': 5,
            'additional_information': '',
            'approval_state': 'PENDING',
            'approvals': [],
            'assignments': [],
            'client_id': 2,
            'department': DEPARTMENTS[2],
            'employee_info': None,
            'estimated_end_date': '2023-12-31',
            'num_assignments': 1,
            'pay_rate': 18.5,
            'pay_scheme': {'display_name': 'Exempt', 'id': 1, 'name': 'exempt'},
            'position': POSITIONS[1],
            'purchase_order': {
                'id': 1,
                'client_id': 2,
                'departments': [],
                'ext_ref': 'purchase-order-number3',
            },
            'requisition_type': {
                'id': 4,
                'display_name': 'Full Time',
                'name': 'full_time',
            },
            'schedule': {
                'id': 1,
                'client_id': 2,
                'description': 'Monday through Friday, 9AM to 6PM',
                'name': 'Standard',
            },
            'start_date': '2023-12-01',
            'supervisor': {
                'id': 102,
                'name': 'Client Admin',
                'email': 'admin@example.com',
            },
            'timecard_approver': {
                'id': 102,
                'name': 'Client Admin',
                'email': 'admin@example.com',
            },
            'location': {
                'id': 1,
                'client_id': 2,
                'name': 'HQ',
                'description': 'Central Office - Head Quarters',
                'street': '2555 Garden Road, Suite H',
                'city': 'Monterey',
                'state': 'CA',
                'zip': '93940',
                'country': 'US',
            },
            'presented_workers': list_available_worker_items(),
        },
    ),
    'rti admin requires client_id, supervisor_user_id, and timecard_approver_user_id': UpdateTC(
        token_payload={'sub': 101},
        id=6,
        payload={
            'purchase_order_id': 1,
            'position_id': 1,
            'department_id': 2,
            'location_id': 1,
            'requisition_type_id': 4,
            'pay_scheme_id': 1,
            'schedule_id': 1,
            'num_assignments': 1,
            'pay_rate': 18.50,
            'start_date': '2023-12-01',
            'estimated_end_date': '2023-12-31',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'client_id': ['Missing data for required field.'],
                'supervisor_user_id': ['Missing data for required field.'],
                'timecard_approver_user_id': ['Missing data for required field.'],
            },
        },
    ),
    'rti admin can update requisitions': UpdateTC(
        token_payload={'sub': 101},
        id=7,
        payload={
            'client_id': 2,
            'purchase_order_id': 1,
            'position_id': 1,
            'department_id': 2,
            'location_id': 1,
            'requisition_type_id': 4,
            'pay_scheme_id': 1,
            'schedule_id': 1,
            'supervisor_user_id': 102,
            'timecard_approver_user_id': 102,
            'num_assignments': 1,
            'pay_rate': 18.50,
            'start_date': '2023-12-01',
            'estimated_end_date': '2023-12-31',
            'additional_information': 'Overwrite',
            'employee_info': {
                'additional_information': 'Received verbal aggreement.',
                'associate_name': 'Danny Trejo',
                'email': 'dtrejo@example.com',
                'preferred_name': 'Machete',
            },
        },
        exp_resp={
            'id': 7,
            'additional_information': 'Overwrite',
            'approval_state': 'PENDING',
            'approvals': [],
            'assignments': [],
            'client_id': 2,
            'department': DEPARTMENTS[2],
            'employee_info': {
                'additional_information': 'Received verbal aggreement.',
                'associate_name': 'Danny Trejo',
                'email': 'dtrejo@example.com',
                'preferred_name': 'Machete',
            },
            'estimated_end_date': '2023-12-31',
            'num_assignments': 1,
            'pay_rate': 18.5,
            'pay_scheme': {'display_name': 'Exempt', 'id': 1, 'name': 'exempt'},
            'position': POSITIONS[1],
            'purchase_order': {
                'id': 1,
                'client_id': 2,
                'departments': [],
                'ext_ref': 'purchase-order-number3',
            },
            'requisition_type': {
                'id': 4,
                'display_name': 'Full Time',
                'name': 'full_time',
            },
            'schedule': {
                'id': 1,
                'client_id': 2,
                'description': 'Monday through Friday, 9AM to 6PM',
                'name': 'Standard',
            },
            'start_date': '2023-12-01',
            'supervisor': {
                'id': 102,
                'name': 'Client Admin',
                'email': 'admin@example.com',
            },
            'timecard_approver': {
                'id': 102,
                'name': 'Client Admin',
                'email': 'admin@example.com',
            },
            'location': {
                'id': 1,
                'client_id': 2,
                'name': 'HQ',
                'description': 'Central Office - Head Quarters',
                'street': '2555 Garden Road, Suite H',
                'city': 'Monterey',
                'state': 'CA',
                'zip': '93940',
                'country': 'US',
            },
            'presented_workers': [],
        },
    ),
}))
def test_requisition_update(client, app, token_payload, id, payload, exp_status, exp_resp):
    user = set_auth_token(app, client, token_payload)
    response = client.post(f'/api/requisitions/{id}', json=payload)
    assert (response.status_code, response.json) == (exp_status, exp_resp)
    if exp_status == '200':
        with app.app_context():
            obj = db.session.get(Requisition, id)
            assert obj.modified_uid == user.id
            assert schema.Requisition.dump(obj) == exp_resp


@dataclass
class DeleteTC:
    token_payload: dict | str
    id: int
    exp_resp: dict
    exp_status: int = 200


@pytest.mark.parametrize(*params({
    'Default cannot delete requisitions': DeleteTC(
        token_payload={'sub': 1},
        id=5,
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'Hiring Manager cannot delete requisitions': DeleteTC(
        token_payload={'sub': 103},
        id=1,
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'Client Admin may not delete requisition for other client': DeleteTC(
        token_payload={'sub': 102},
        id=3,
        exp_status=404,
        exp_resp={
            'code': 404,
            'name': 'Not Found',
            'description': 'Resource not found.',
        },
    ),
    'Client Admin can delete requisition': DeleteTC(
        token_payload={'sub': 102},
        id=2,
        exp_resp={},
    ),
    'RTI Admin can delete requisition': DeleteTC(
        token_payload={'sub': 101},
        id=7,
        exp_resp={},
    ),
}))
def test_requisition_delete(client, app, token_payload, id, exp_status, exp_resp):
    user = set_auth_token(app, client, token_payload)
    response = client.delete(f'/api/requisitions/{id}')
    assert (response.status_code, response.json) == (exp_status, exp_resp)
    if exp_status == 200:
        with app.app_context():
            obj = db.session.get(Requisition, id)
        assert obj.modified_uid == user.id
        assert obj.state == States.DELETED


@dataclass
class ApproveTC:
    token_payload: dict | str
    id: int
    payload: dict
    exp_resp: dict
    exp_status: int = 200
    exp_requisition: dict = None


REQUISITION_5_PRE_APPROVAL = {
    'id': 5,
    'additional_information': '',
    'approval_state': 'PENDING',
    'approvals': [],
    'assignments': [],
    'client_id': 2,
    'department': DEPARTMENTS[2],
    'employee_info': None,
    'estimated_end_date': '2023-12-31',
    'num_assignments': 1,
    'pay_rate': 18.5,
    'pay_scheme': {
        'id': 1,
        'display_name': 'Exempt',
        'name': 'exempt',
    },
    'position': POSITIONS[1],
    'presented_workers': [
        {'id': 1, 'phone_number': None,
         'user': {'email': 'bill@wurtz.com', 'id': 105, 'name': 'Bill Wurtz'}},
        {'id': 2, 'phone_number': '+1 805 555 5555',
         'user': {'email': 'bobloblaw@lawblog.law', 'id': 106, 'name': 'Bob Loblaw'}}
    ],
    'purchase_order': {
        'id': 1,
        'client_id': 2,
        'departments': [],
        'ext_ref': 'purchase-order-number3',
    },
    'requisition_type': {
        'id': 4,
        'display_name': 'Full Time',
        'name': 'full_time',
    },
    'schedule': {
        'id': 1,
        'client_id': 2,
        'description': 'Monday through Friday, 9AM to 6PM',
        'name': 'Standard',
    },
    'start_date': '2023-12-01',
    'supervisor': {'email': 'admin@example.com', 'id': 102, 'name': 'Client Admin'},
    'timecard_approver': {'email': 'admin@example.com', 'id': 102, 'name': 'Client Admin'},
    'location': {
        'id': 1,
        'city': 'Monterey',
        'client_id': 2,
        'country': 'US',
        'description': 'Central Office - Head Quarters',
        'name': 'HQ',
        'state': 'CA',
        'street': '2555 Garden Road, Suite H',
        'zip': '93940',
    },
}

REQUISITION_5_POST_APPROVAL = {
    'id': 5,
    'additional_information': '',
    'approval_state': 'APPROVED',
    'approvals': [
        {
            'decision': 'APPROVE',
            'approver_uid': 102,
            # 'datetime'
        },
    ],
    'assignments': [
        {
            'actual_end_date': None,
            'actual_start_date': None,
            'bill_rate': 19.43,
            'cancel_notes': None,
            'cost_center': None,
            'department': {'client_id': 2,
                           'id': 2,
                           'name': 'Example',
                           'number': '1000'},
            'end_notes': None,
            'end_reason': None,
            'id': 4,
            'pay_rate': 18.5,
            'replaced_by_assignment_id': None,
            'requisition_id': 5,
            'status': 'OPEN',
            'system_start_date': None,
            'tentative_end_date': '2023-12-31',
            'tentative_start_date': '2023-12-01',
            'timesheets_web_punchable': True,
            'timesheets_worker_editable': False,
            'worker': None}],
    'client_id': 2,
    'department': DEPARTMENTS[2],
    'employee_info': None,
    'estimated_end_date': '2023-12-31',
    'num_assignments': 1,
    'pay_rate': 18.5,
    'pay_scheme': {
        'id': 1,
        'display_name': 'Exempt',
        'name': 'exempt',
    },
    'position': POSITIONS[1],
    'presented_workers': [
        {'id': 1, 'phone_number': None,
         'user': {'email': 'bill@wurtz.com', 'id': 105, 'name': 'Bill Wurtz'}},
        {'id': 2, 'phone_number': '+1 805 555 5555',
         'user': {'email': 'bobloblaw@lawblog.law', 'id': 106, 'name': 'Bob Loblaw'}}
    ],
    'purchase_order': {
        'id': 1,
        'client_id': 2,
        'departments': [],
        'ext_ref': 'purchase-order-number3',
    },
    'requisition_type': {
        'id': 4,
        'display_name': 'Full Time',
        'name': 'full_time',
    },
    'schedule': {
        'id': 1,
        'client_id': 2,
        'description': 'Monday through Friday, 9AM to 6PM',
        'name': 'Standard',
    },
    'start_date': '2023-12-01',
    'supervisor': {'email': 'admin@example.com', 'id': 102, 'name': 'Client Admin'},
    'timecard_approver': {'email': 'admin@example.com', 'id': 102, 'name': 'Client Admin'},
    'location': {
        'id': 1,
        'city': 'Monterey',
        'client_id': 2,
        'country': 'US',
        'description': 'Central Office - Head Quarters',
        'name': 'HQ',
        'state': 'CA',
        'street': '2555 Garden Road, Suite H',
        'zip': '93940',
    },
}

REQUISITION_6_POST_APPROVAL = {
    'id': 6,
    'additional_information': '',
    'approval_state': 'APPROVED',
    'approvals': [
        {
            'decision': 'APPROVE',
            'approver_uid': 101,
            # 'datetime' extracted and validated independently
        },
    ],
    'assignments': [{'actual_end_date': None,
                     'actual_start_date': None,
                     'bill_rate': 19.43,
                     'cancel_notes': None,
                     'cost_center': None,
                     'department': {'client_id': 2,
                                    'id': 2,
                                    'name': 'Example',
                                    'number': '1000'},
                     'end_notes': None,
                     'end_reason': None,
                     'id': 5,
                     'pay_rate': 18.5,
                     'replaced_by_assignment_id': None,
                     'requisition_id': 6,
                     'status': 'OPEN',
                     'system_start_date': None,
                     'tentative_end_date': '2023-12-31',
                     'tentative_start_date': '2023-12-01',
                     'timesheets_web_punchable': True,
                     'timesheets_worker_editable': False,
                     'worker': None}],
    'client_id': 2,
    'department': DEPARTMENTS[2],
    'employee_info': None,
    'estimated_end_date': '2023-12-31',
    'num_assignments': 1,
    'pay_rate': 18.5,
    'pay_scheme': {
        'id': 1,
        'display_name': 'Exempt',
        'name': 'exempt',
    },
    'position': POSITIONS[1],
    'presented_workers': [
        {'id': 1, 'phone_number': None,
         'user': {'email': 'bill@wurtz.com', 'id': 105, 'name': 'Bill Wurtz'}},
        {'id': 2, 'phone_number': '+1 805 555 5555',
         'user': {'email': 'bobloblaw@lawblog.law', 'id': 106, 'name': 'Bob Loblaw'}}
    ],
    'purchase_order': {
        'id': 1,
        'client_id': 2,
        'departments': [],
        'ext_ref': 'purchase-order-number3',
    },
    'requisition_type': {
        'id': 4,
        'display_name': 'Full Time',
        'name': 'full_time',
    },
    'schedule': {
        'id': 1,
        'client_id': 2,
        'description': 'Monday through Friday, 9AM to 6PM',
        'name': 'Standard',
    },
    'start_date': '2023-12-01',
    'supervisor': {'email': 'admin@example.com', 'id': 102, 'name': 'Client Admin'},
    'timecard_approver': {'email': 'admin@example.com', 'id': 102, 'name': 'Client Admin'},
    'location': {
        'id': 1,
        'city': 'Monterey',
        'client_id': 2,
        'country': 'US',
        'description': 'Central Office - Head Quarters',
        'name': 'HQ',
        'state': 'CA',
        'street': '2555 Garden Road, Suite H',
        'zip': '93940',
    },
}

REQUISITION_4_POST_REJECTION = {
    'additional_information': '',
    'approval_state': 'REJECTED',
    'approvals': [{'approver_uid': 107, 'decision': 'REJECT', 'reason': 'Not in budget'}],
    'assignments': [],
    'client_id': 3,
    'department': None,
    'employee_info': None,
    'estimated_end_date': None,
    'id': 4,
    'location': None,
    'num_assignments': 1,
    'pay_rate': None,
    'pay_scheme': None,
    'position': None,
    'presented_workers': [],
    'purchase_order': None,
    'requisition_type': None,
    'schedule': None,
    'start_date': None,
    'supervisor': None,
    'timecard_approver': None,
}


@pytest.mark.parametrize(*params({
    'Default cannot approve requisitions': ApproveTC(
        token_payload={'sub': 1},
        id=5,
        payload={'decision': 'APPROVE'},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
        exp_requisition=REQUISITION_5_PRE_APPROVAL,
    ),
    'Hiring Manager cannot approve requisitions': ApproveTC(
        token_payload={'sub': 103},
        id=5,
        payload={'decision': 'APPROVE'},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
        exp_requisition=REQUISITION_5_PRE_APPROVAL,
    ),
    'Client Admin may not approve requisition for other client': ApproveTC(
        token_payload={'sub': 102},
        id=4,
        payload={'decision': 'APPROVE'},
        exp_status=404,
        exp_resp={
            'code': 404,
            'name': 'Not Found',
            'description': 'Resource not found.',
        },
        exp_requisition={
            'id': 4,
            'additional_information': '',
            'approval_state': 'PENDING',
            'approvals': [],
            'assignments': [],
            'client_id': 3,
            'department': None,
            'employee_info': None,
            'estimated_end_date': None,
            'location': None,
            'num_assignments': 1,
            'pay_rate': None,
            'pay_scheme': None,
            'position': None,
            'presented_workers': [],
            'purchase_order': None,
            'requisition_type': None,
            'schedule': None,
            'start_date': None,
            'supervisor': None,
            'timecard_approver': None,
        },
    ),
    'Reason is required when rejecting': ApproveTC(
        token_payload={'sub': 102},
        id=5,
        payload={'decision': 'REJECT'},
        exp_status=400,
        exp_resp={
            'code': 400,
            'errors': {'reason': 'Reason is required upon rejection.'},
            'name': 'Bad Request',
        },
        exp_requisition=REQUISITION_5_PRE_APPROVAL,
    ),
    'Client Admin can approve requisition': ApproveTC(
        token_payload={'sub': 102},
        id=5,
        payload={'decision': 'APPROVE'},
        exp_resp={'approver_uid': 102, 'decision': 'APPROVE'},
        exp_requisition=REQUISITION_5_POST_APPROVAL,
    ),
    'Client Admin cannot change approval decision': ApproveTC(
        token_payload={'sub': 102},
        id=5,
        payload={'decision': 'REJECT', 'reason': 'Not in budget', },
        exp_status=400,
        exp_resp={
            'code': 400,
            'errors': {'_schema': ['Approval decision cannot be modified']},
            'name': 'Bad Request',
        },
        exp_requisition=REQUISITION_5_POST_APPROVAL,
    ),
    'Client Admin can reject requisition': ApproveTC(
        token_payload={'sub': 107},
        id=4,
        payload={'decision': 'REJECT', 'reason': 'Not in budget'},
        exp_status=200,
        exp_resp={'approver_uid': 107, 'decision': 'REJECT', 'reason': 'Not in budget'},
        exp_requisition=REQUISITION_4_POST_REJECTION,
    ),
    'RTI Admin can approve requisition': ApproveTC(
        token_payload={'sub': 101},
        id=6,
        payload={'decision': 'APPROVE'},
        exp_resp={'approver_uid': 101, 'decision': 'APPROVE'},
        exp_requisition=REQUISITION_6_POST_APPROVAL,
    ),
}))
def test_requisition_approve(
        client, app, token_payload, id, payload,
        exp_status, exp_resp, exp_requisition
):
    user = set_auth_token(app, client, token_payload)
    response = client.post(f'/api/requisitions/{id}/approval', json=payload)

    # pop datetime off valid responses which will change on each test run
    resp_data = response.json
    resp_approved_datetime = resp_data.pop('datetime', None)

    assert (response.status_code, resp_data) == (exp_status, exp_resp)

    with app.app_context():
        req = db.session.get(Requisition, id)
        actual_requisition = json.loads(schema.Requisition().dumps(req))
        stored_approved_datetime = None
        if approvals := actual_requisition.get('approvals', []):
            stored_approved_datetime = (approvals[0] or {}).pop('datetime', None)
        if exp_status == 200:
            assert (req.modified_uid, stored_approved_datetime) == (user.id, resp_approved_datetime)
        assert (actual_requisition == exp_requisition)


REQUISITION_5_POST_APPROVAL_RESET = {**REQUISITION_5_PRE_APPROVAL, **{
    'assignments': [{'actual_end_date': None,
                     'actual_start_date': None,
                     'bill_rate': 19.43,
                     'cancel_notes': None,
                     'cost_center': None,
                     'department': {'client_id': 2,
                                    'id': 2,
                                    'name': 'Example',
                                    'number': '1000'},
                     'end_notes': None,
                     'end_reason': None,
                     'id': 4,
                     'pay_rate': 18.5,
                     'replaced_by_assignment_id': None,
                     'requisition_id': 5,
                     'status': 'OPEN',
                     'system_start_date': None,
                     'tentative_end_date': '2023-12-31',
                     'tentative_start_date': '2023-12-01',
                     'timesheets_web_punchable': True,
                     'timesheets_worker_editable': False,
                     'worker': None}],
}}


def test_requisition_approval_reset_after_update(client, app):
    user = set_auth_token(app, client, {'sub': 101})
    # Update requisition
    response = client.post(
        f'/api/requisitions/5',
        json={
            'client_id': 2,
            'purchase_order_id': 1,
            'position_id': 1,
            'department_id': 2,
            'location_id': 1,
            'requisition_type_id': 4,
            'pay_scheme_id': 1,
            'schedule_id': 1,
            'num_assignments': 1,
            'present_worker_ids': [1, 2],
            'pay_rate': 18.50,
            'start_date': '2023-12-01',
            'estimated_end_date': '2023-12-31',
            'supervisor_user_id': 102,
            'timecard_approver_user_id': 102,
        },
    )

    assert (response.status_code, response.json) == (200, REQUISITION_5_POST_APPROVAL_RESET)

    # pop datetime off valid responses which will change on each test run

    with app.app_context():
        req = db.session.get(Requisition, 5)
        actual_requisition = json.loads(schema.Requisition().dumps(req))
        assert (req.modified_uid, actual_requisition) == (101, REQUISITION_5_POST_APPROVAL_RESET)


def list_worker_items():
    return [
        {
            'id': 2,
            'phone_number': '+1 805 555 5555',
            'user': {
                'id': 106,
                'email': 'bobloblaw@lawblog.law',
                'name': 'Bob Loblaw',
            },
        },
    ]


ASSIGNMENT_2 = {
    'actual_end_date': None,
    'actual_start_date': None,
    'bill_rate': 15.25,
    'cancel_notes': None,
    'cost_center': None,
    'department': {'client_id': 2, 'id': 2, 'name': 'Example', 'number': '1000'},
    'end_notes': None,
    'end_reason': None,
    'id': 2,
    'pay_rate': 30.75,
    'replaced_by_assignment_id': None,
    'requisition_id': 2,
    'status': 'ACTIVE',
    'system_start_date': None,
    'tentative_end_date': None,
    'tentative_start_date': '2024-06-30',
    'timesheets_web_punchable': True,
    'timesheets_worker_editable': False,
    'worker': {
        'id': 2,
        'phone_number': '+1 805 555 5555',
        'user': {'email': 'bobloblaw@lawblog.law', 'id': 106, 'name': 'Bob Loblaw'},
    },
}


def list_assignment_items():
    return [
        {
            'id': 4,
            'actual_end_date': None,
            'actual_start_date': None,
            'bill_rate': 19.43,
            'cancel_notes': None,
            'cost_center': None,
            'department': {'client_id': 2, 'id': 2, 'name': 'Example', 'number': '1000'},
            'end_notes': None,
            'end_reason': None,
            'pay_rate': 18.5,
            'replaced_by_assignment_id': None,
            'requisition_id': 5,
            'status': 'ACTIVE',
            'system_start_date': None,
            'tentative_end_date': '2023-12-31',
            'tentative_start_date': '2024-06-30',
            'timesheets_web_punchable': True,
            'timesheets_worker_editable': False,
            'worker': {
                'id': 1,
                'phone_number': None,
                'user': {
                    'id': 105,
                    'email': 'bill@wurtz.com',
                    'name': 'Bill Wurtz',
                },
            },
        },
        {
            'id': 5,
            'actual_end_date': None,
            'actual_start_date': None,
            'bill_rate': 19.43,
            'cancel_notes': None,
            'cost_center': None,
            'department': {'client_id': 2,
                           'id': 2,
                           'name': 'Example',
                           'number': '1000'},
            'end_notes': None,
            'end_reason': None,
            'pay_rate': 18.5,
            'replaced_by_assignment_id': None,
            'requisition_id': 6,
            'status': 'OPEN',
            'system_start_date': None,
            'tentative_end_date': '2023-12-31',
            'tentative_start_date': '2023-12-01',
            'timesheets_web_punchable': True,
            'timesheets_worker_editable': False,
            'worker': None,
        }
    ]


@pytest.mark.parametrize(*params({
    'Default cannot update assignments': UpdateTC(
        token_payload={'sub': 1},
        id=2,
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'fields are required': UpdateTC(
        token_payload={'sub': 103},
        id=2,
        payload={},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'department_id': ['Missing data for required field.'],
                'tentative_start_date': ['Missing data for required field.'],
            },
        },
    ),
    'Hiring Manager can update assignment': UpdateTC(
        token_payload={'sub': 103},
        id=2,
        payload={
            'department_id': 2,
            'worker_id': 2,
            'tentative_start_date': '2024-06-30',
        },
        exp_resp=ASSIGNMENT_2,
    ),
    'Client Admin may not update assignment for other client': UpdateTC(
        token_payload={'sub': 102},
        id=3,
        exp_status=404,
        exp_resp={
            'code': 404,
            'name': 'Not Found',
            'description': 'Resource not found.',
        },
    ),
    'Client Admin can update assignment': UpdateTC(
        token_payload={'sub': 102},
        id=2,
        payload={
            'department_id': 2,
            'worker_id': 2,
            'tentative_start_date': '2024-06-30',
        },
        exp_resp=ASSIGNMENT_2,
    ),
    'RTI Admin update assignment': UpdateTC(
        token_payload={'sub': 101},
        id=2,
        payload={
            'department_id': 2,
            'worker_id': 2,
            'tentative_start_date': '2024-06-30',
        },
        exp_resp=ASSIGNMENT_2,
    ),
    'Setting worker_id changes open assignment to active': UpdateTC(
        token_payload={'sub': 102},
        id=4,
        payload={
            'department_id': 2,
            'tentative_start_date': '2024-06-30',
            'worker_id': 1,
            'pay_rate': '18.50',
        },
        exp_resp=list_assignment_items()[0]
    )
}))
def test_assignment_update(client, app, token_payload, payload, id, exp_status, exp_resp):
    set_auth_token(app, client, token_payload)
    response = client.post(f'/api/assignments/{id}', json=payload)

    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'RTI Admin can list assignments': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 2},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_assignment_items(),
        },
    ),
    'filter by requisition': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 2, 'requisition_id': 6},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': [list_assignment_items()[1]],
        },
    ),
    'filter by worker': ListTC(
        token_payload={'sub': 101},
        query_string={'client_id': 2, 'worker_id': 1},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': [list_assignment_items()[0]],
        },
    ),
    'Client Admin may not list assignments for other client': ListTC(
        token_payload={'sub': 102},
        query_string={'client_id': 3},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'client_id': ['Invalid client.']},
        },
    ),
    'Client Admin can list assignments': ListTC(
        token_payload={'sub': 102},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_assignment_items(),
        },
    ),
    'Hiring Manager can list assignments': ListTC(
        token_payload={'sub': 103},
        exp_resp={
            'pagination': {'page': 1, 'total_pages': 1, 'page_size': 25},
            'items': list_assignment_items(),
        },
    ),
    'Default cannot list assignments': ListTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_assignment_list(client, app, token_payload, query_string, exp_status, exp_resp):
    set_auth_token(app, client, token_payload)
    response = client.get('/api/assignments', query_string=query_string)
    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'RTI Admin get assignment': GetTC(
        token_payload={'sub': 101},
        id=4,
        exp_resp=list_assignment_items()[0],
    ),
    'Client Admin may not get assignment for other client': GetTC(
        token_payload={'sub': 102},
        id=3,
        exp_status=404,
        exp_resp={
            'code': 404,
            'name': 'Not Found',
            'description': 'Resource not found.',
        },
    ),
    'Client Admin can get assignment': GetTC(
        token_payload={'sub': 102},
        id=4,
        exp_resp=list_assignment_items()[0],
    ),
    'Hiring Manager can get assignment': GetTC(
        token_payload={'sub': 103},
        id=4,
        exp_resp=list_assignment_items()[0],
    ),
    'Default cannot get assignments': GetTC(
        token_payload={'sub': 1},
        id=4,
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_assignment_detail(client, app, token_payload, id, exp_status, exp_resp):
    set_auth_token(app, client, token_payload)
    response = client.get(f'/api/assignments/{id}')

    assert (response.status_code, response.json) == (exp_status, exp_resp)


@dataclass
class AssignmentDeleteTC:
    token_payload: dict | str
    id: int
    exp_resp: dict
    payload: dict = None
    exp_status: int = 200


@pytest.mark.parametrize(*params({
    'Default cannot delete assignments': AssignmentDeleteTC(
        token_payload={'sub': 1},
        id=1,
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'fields are required': AssignmentDeleteTC(
        token_payload={'sub': 103},
        id=1,
        payload={},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'delete_type': ['Missing data for required field.']},
        },
    ),
    'Hiring Manager can delete assignment': AssignmentDeleteTC(
        token_payload={'sub': 103},
        id=5,
        payload={
            'delete_type': 'END',
            'end_reason': 'voluntary',
        },
        exp_resp={},
    ),
    'Client Admin may not delete assignment for other client': AssignmentDeleteTC(
        token_payload={'sub': 102},
        id=3,
        payload={
            'delete_type': 'END',
            'end_reason': 'voluntary',
        },
        exp_status=404,
        exp_resp={
            'code': 404,
            'name': 'Not Found',
            'description': 'Resource not found.',
        },
    ),
    'Client Admin can delete assignment': AssignmentDeleteTC(
        token_payload={'sub': 102},
        id=2,
        payload={
            'delete_type': 'END',
            'end_reason': 'involuntary',
            'end_date': '2023-12-25',
            'notes': 'Insubordination',
        },
        exp_resp={},
    ),
    'RTI Admin delete assignment': AssignmentDeleteTC(
        token_payload={'sub': 101},
        id=3,
        payload={
            'delete_type': 'CANCEL',
        },
        exp_resp={},
    ),
}))
def test_assignment_delete(client, app, token_payload, id, payload, exp_status, exp_resp):
    set_auth_token(app, client, token_payload)
    response = client.delete(f'/api/assignments/{id}', json=payload)

    assert (response.status_code, response.json) == (exp_status, exp_resp)


ASSIGNMENT_2_REPLACED = {
    'id': 6,
    'actual_end_date': None,
    'actual_start_date': None,
    'bill_rate': 15.25,
    'cancel_notes': None,
    'cost_center': None,
    'department': {'client_id': 2, 'id': 2, 'name': 'Example', 'number': '1000'},
    'end_notes': None,
    'end_reason': None,
    'pay_rate': 30.75,
    'replaced_by_assignment_id': None,
    'requisition_id': 2,
    'status': 'ACTIVE',
    'system_start_date': None,
    'tentative_end_date': None,
    'tentative_start_date': '2024-08-01',
    'timesheets_web_punchable': True,
    'timesheets_worker_editable': False,
    'worker': {
        'id': 1,
        'phone_number': None,
        'user': {'email': 'bill@wurtz.com', 'id': 105, 'name': 'Bill Wurtz'},
    },
}

ASSIGNMENT_5_REPLACED = {
    'id': 7,
    'actual_end_date': None,
    'actual_start_date': None,
    'bill_rate': 20.21,
    'cancel_notes': None,
    'cost_center': None,
    'department': {'client_id': 2, 'id': 2, 'name': 'Example', 'number': '1000'},
    'end_notes': None,
    'end_reason': None,
    'pay_rate': 19.25,
    'replaced_by_assignment_id': None,
    'requisition_id': 6,
    'status': 'ACTIVE',
    'system_start_date': None,
    'tentative_end_date': None,
    'tentative_start_date': '2024-09-12',
    'timesheets_web_punchable': True,
    'timesheets_worker_editable': False,
    'worker': {
        'id': 1,
        'phone_number': None,
        'user': {'email': 'bill@wurtz.com', 'id': 105, 'name': 'Bill Wurtz'},
    },
}

ASSIGNMENT_3_REPLACED = {
    'id': 8,
    'actual_end_date': None,
    'actual_start_date': None,
    'bill_rate': 18.0,
    'cancel_notes': None,
    'cost_center': None,
    'department': {'client_id': 1, 'id': 1, 'name': 'Default', 'number': None},
    'end_notes': None,
    'end_reason': None,
    'pay_rate': 12.34,
    'replaced_by_assignment_id': None,
    'requisition_id': 3,
    'status': 'ACTIVE',
    'system_start_date': None,
    'tentative_end_date': None,
    'tentative_start_date': '2024-07-13',
    'timesheets_web_punchable': True,
    'timesheets_worker_editable': False,
    'worker': {
        'id': 3,
        'phone_number': None,
        'user': {'email': 'hm@example.com', 'id': 103, 'name': 'Hiring Manager'},
    },
}


@pytest.mark.parametrize(*params({
    'Default cannot create assignments': CreateTC(
        token_payload={'sub': 1},
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
    'fields are required': CreateTC(
        token_payload={'sub': 103},
        payload={},
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'replaces_assignment_id': ['Missing data for required field.'],
                'worker_id': ['Missing data for required field.'],
                'tentative_start_date': ['Missing data for required field.'],
            },
        },
    ),
    'replaced assignment must be canceled or ended': CreateTC(
        token_payload={'sub': 103},
        payload={
            'replaces_assignment_id': 4,
            'worker_id': 2,
            'tentative_start_date': '2024-06-30',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'replaces_assignment_id': ['Replaced assignment must be canceled or ended.']},
        },
    ),
    'Hiring Manager can create assignment': CreateTC(
        token_payload={'sub': 103},
        payload={
            'replaces_assignment_id': 2,
            'worker_id': 1,
            'tentative_start_date': '2024-08-01',
        },
        exp_resp=ASSIGNMENT_2_REPLACED,
    ),
    'Client Admin may not create assignment for other client': CreateTC(
        token_payload={'sub': 102},
        payload={
            'replaces_assignment_id': 3,
            'worker_id': 1,
            'tentative_start_date': '2024-08-01',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {'replaces_assignment_id': ['Invalid replaces_assignment_id.']},
        }
    ),
    'assignment relationship ids must be valid': CreateTC(
        token_payload={'sub': 102},
        payload={
            'replaces_assignment_id': 5,
            'cost_center_id': 99,
            'worker_id': 99,
            'department_id': 3,
            'tentative_start_date': '2024-09-12',
            'pay_rate': 19.25,
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'cost_center_id': ['Invalid cost_center_id.'],
                'department_id': ['Invalid department_id.'],
                'worker_id': ['Invalid worker_id.'],
            }
        },
    ),
    'Client Admin can create assignment': CreateTC(
        token_payload={'sub': 102},
        payload={
            'replaces_assignment_id': 5,
            'worker_id': 1,
            'department_id': 2,
            'tentative_start_date': '2024-09-12',
            'pay_rate': 19.25,
        },
        exp_resp=ASSIGNMENT_5_REPLACED,
    ),
    'replaced requisition must not already be replaced': CreateTC(
        token_payload={'sub': 102},
        payload={
            'replaces_assignment_id': 5,
            'worker_id': 1,
            'department_id': 2,
            'tentative_start_date': '2024-09-12',
            'pay_rate': 19.25,
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'replaces_assignment_id': ['Replaced assignment must not be previously replaced.'],
            }
        }
    ),
    'worker_id must not already be assigned to the requisition': CreateTC(
        token_payload={'sub': 101},
        payload={
            'replaces_assignment_id': 3,
            'worker_id': 2,
            'department_id': 1,
            'tentative_start_date': '2024-07-13',
        },
        exp_status=400,
        exp_resp={
            'code': 400,
            'name': 'Bad Request',
            'errors': {
                'worker_id': ['Invalid worker_id.'],
            }
        },
    ),
    'RTI Admin create assignment': CreateTC(
        token_payload={'sub': 101},
        payload={
            'replaces_assignment_id': 3,
            'worker_id': 3,
            'department_id': 1,
            'tentative_start_date': '2024-07-13',
        },
        exp_resp=ASSIGNMENT_3_REPLACED,
    ),
}))
def test_assignment_create(client, app, token_payload, payload, exp_status, exp_resp):
    set_auth_token(app, client, token_payload)
    response = client.post(f'/api/assignments', json=payload)

    assert (response.status_code, response.json) == (exp_status, exp_resp)


@pytest.mark.parametrize(*params({
    'RTI Admin get worker': GetTC(
        token_payload={'sub': 101},
        id=2,
        exp_resp=list_worker_items()[0],
    ),
    'Client Admin may not get worker for other client': GetTC(
        token_payload={'sub': 102},
        id=99,
        exp_status=404,
        exp_resp={
            'code': 404,
            'name': 'Not Found',
            'description': 'Resource not found.',
        },
    ),
    'Client Admin can get worker': GetTC(
        token_payload={'sub': 102},
        id=2,
        exp_resp=list_worker_items()[0],
    ),
    'Hiring Manager can get worker': GetTC(
        token_payload={'sub': 103},
        id=2,
        exp_resp=list_worker_items()[0],
    ),
    'Default cannot get workers': GetTC(
        token_payload={'sub': 1},
        id=2,
        exp_status=403,
        exp_resp={
            'code': 403,
            'name': 'Forbidden',
            'description': 'Permission required.',
        },
    ),
}))
def test_worker_detail(client, app, token_payload, id, exp_status, exp_resp):
    set_auth_token(app, client, token_payload)
    response = client.get(f'/api/workers/{id}')
    assert (response.status_code, response.json) == (exp_status, exp_resp)

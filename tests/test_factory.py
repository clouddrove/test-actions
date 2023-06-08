import json
from dataclasses import dataclass
from typing import Callable

import pytest
import yaml
from openapi_spec_validator import validate_spec

from reachtalent import create_app
from reachtalent.config import Config
from .conftest import params


def test_config():
    assert not create_app().testing, "By default app.testing should be false"
    assert create_app(
        Config(TESTING=True)).testing, "When `test_config=Config(TESTING=True)` then app.testing should be true"


def test_index(client):
    response = client.get('/api')
    assert response.data == b'Welcome, Stranger'


def nested_get(doc: dict, path: str, separator: str = '/'):
    parts = path.split(separator)

    if parts[0] == '#':
        parts = parts[1:]

    node = doc
    for needle in parts:
        if not isinstance(node, dict):
            break
        node = node.get(needle)
    return node


def strict_validate_openapi_spec(spec: dict):
    assert spec
    validate_spec(spec)
    assert sorted(list(spec['paths'].keys())) == [
        '/api/assignments',
        '/api/assignments/{id}',
        '/api/auth/email_verify',
        '/api/auth/forgot_password/reset',
        '/api/auth/forgot_password/send',
        '/api/auth/invite',
        '/api/auth/login',
        '/api/auth/permissions',
        '/api/auth/session',
        '/api/auth/signup',
        '/api/available_workers',
        '/api/categories',
        '/api/category_items',
        '/api/contract_terms',
        '/api/cost_centers',
        '/api/departments',
        '/api/job_classifications',
        '/api/locations',
        '/api/pay_schemes',
        '/api/positions',
        '/api/purchase_orders',
        '/api/purchase_orders/{id}',
        '/api/requisition_types',
        '/api/requisitions',
        '/api/requisitions/{id}',
        '/api/requisitions/{id}/approval',
        '/api/schedules',
        '/api/staff',
        '/api/worker_environments',
        '/api/workers/{id}',
    ]
    assert spec['tags'] == [
        {'name': 'auth'},
        {'name': 'category'},
        {'name': 'department'},
        {'name': 'cost_center'},
        {'name': 'staff'},
        {'name': 'purchase_order'},
        {'name': 'contract_terms'},
        {'name': 'job_classification'},
        {'name': 'position'},
        {'name': 'requisition_type'},
        {'name': 'pay_scheme'},
        {'name': 'schedule'},
        {'name': 'worker'},
        {'name': 'worker_environment'},
        {'name': 'location'},
        {'name': 'requisition'},
        {'name': 'assignment'},
    ]
    for path, operations in spec['paths'].items():
        assert operations != {}, f"{path} in spec should not be empty"
        for method, operation in operations.items():
            # if the operation has a requestBody, assert that the request
            # body $ref is defined in the spec.
            if request_body_ref := nested_get(
                    operation,
                    'requestBody.content.application/json.schema.$ref', '.'):
                msg = f'{method.upper()} {path}: {request_body_ref} should be defined'
                assert nested_get(spec, request_body_ref) is not None, msg


@dataclass
class OpenAPITC:
    fmt: str
    loader: Callable[[str], dict] | None = None
    exp_status: int = 200


@pytest.mark.parametrize(*params({
    'openapi.yaml should be 200 and be valid': OpenAPITC(fmt='yaml', loader=yaml.safe_load),
    'openapi.json should be 200 and be valid': OpenAPITC(fmt='json', loader=json.loads),
    'openapi.txt should be 404': OpenAPITC(fmt='txt', exp_status=404),
}))
def test_openapi_formats(client, fmt: str, exp_status: int, loader: Callable[[str], dict] | None):
    resp = client.get(f'/api/openapi.{fmt}')
    assert resp.status_code == exp_status
    if loader:
        openapi_spec = loader(resp.data)
        strict_validate_openapi_spec(openapi_spec)


@dataclass
class OpenAPICliTC:
    args: list[str]
    exp_exit_code: int = 0
    exp_stderr: bytes | None = None
    exp_stdout: str | None = None
    loader: Callable[[str], dict] | None = None


@pytest.mark.parametrize(*params(
    {
        'help output': OpenAPICliTC(
            args=['openapi', '--help'],
            exp_stdout="""Usage: reachtalent.app openapi [OPTIONS]

Options:
  --format [yaml|json]  OpenAPI Spec format
  --help                Show this message and exit.
""",
        ),
        'yaml as default': OpenAPICliTC(
            args=['openapi'],
            loader=yaml.safe_load,
        ),
        'yaml as requested': OpenAPICliTC(
            args=['openapi', '--format', 'yaml'],
            loader=yaml.safe_load,
        ),
        'json as request': OpenAPICliTC(
            args=['openapi', '--format', 'json'],
            loader=json.loads,
        )
    }
))
def test_openapi_cli(runner, args, exp_exit_code, exp_stdout, exp_stderr, loader):
    res = runner.invoke(args=args)
    assert (res.exit_code, res.stderr_bytes) == (exp_exit_code, exp_stderr)
    if exp_stdout is not None:
        assert res.stdout == exp_stdout
    if loader:
        spec = loader(res.stdout)
        strict_validate_openapi_spec(spec)



from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import typing
import urllib.parse
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select
from googleapiclient.errors import HttpError

from .conftest import params
from reachtalent import database
from reachtalent.extensions import db
from reachtalent.core.commands import (update_data, sync_client, odoo_push)
from reachtalent.auth import models as auth_models
from reachtalent.core.models import CategoryItem, ImportLog, ImportSource, Worker


@dataclass
class CliTC:
    args: list[str]
    exp_exit_code: int = 0
    exp_stderr: bytes | None = None
    exp_stdout: str | None = None


expected_full_log = (
    'INSERT new ContractTermDefinition(ref=markup_jobclass_events_pct, type=percent, label=Events Markup (Percent), description=Percent Markup on Positions classified as Events)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_events_flat, type=decimal, label=Events Markup (Flat), description=Flat Markup on Positions classified as Events)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_it_pct, type=percent, label=IT Markup (Percent), description=Percent Markup on Positions classified as IT)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_it_flat, type=decimal, label=IT Markup (Flat), description=Flat Markup on Positions classified as IT)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_engineering_pct, type=percent, label=Engineering Markup (Percent), description=Percent Markup on Positions classified as Engineering)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_engineering_flat, type=decimal, label=Engineering Markup (Flat), description=Flat Markup on Positions classified as Engineering)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_light_industrial_pct, type=percent, label=Light Industrial Markup (Percent), description=Percent Markup on Positions classified as Light Industrial)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_light_industrial_flat, type=percent, label=Light Industrial Markup (Flat), description=Percent Markup on Positions classified as Light Industrial)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_heavy_industrial_pct, type=percent, label=Heavy Industrial Markup (Percent), description=Percent Markup on Positions classified as Heavy Industrial)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_heavy_industrial_flat, type=decimal, label=Heavy Industrial Markup (Flat), description=Flat Markup on Positions classified as Heavy Industrial)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_administrative_pct, type=percent, label=Administrative Markup (Percent), description=Percent Markup on Positions classified as Light Administrative)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_administrative_flat, type=decimal, label=Administrative Markup (Flat), description=Flat Markup on Positions classified as Administrative)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_accounting_pct, type=percent, label=Accounting Markup (Percent), description=Percent Markup on Positions classified as Accounting)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_accounting_flat, type=decimal, label=Accounting Markup (Flat), description=Flat Markup on Positions classified as Accounting)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_creative_pct, type=percent, label=Creative Markup (Percent), description=Percent Markup on Positions classified as Creative)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_creative_flat, type=decimal, label=Creative Markup (Flat), description=Flat Markup on Positions classified as Creative)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_legal_pct, type=percent, label=Legal Markup (Percent), description=Percent Markup on Positions classified as Legal)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_legal_flat, type=decimal, label=Legal Markup (Flat), description=Flat Markup on Positions classified as Legal)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_driver_pct, type=percent, label=Driver Markup (Percent), description=Percent Markup on Positions classified as Driver)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_driver_flat, type=decimal, label=Driver Markup (Flat), description=Flat Markup on Positions classified as Driver)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_sales_pct, type=percent, label=Sales Markup (Percent), description=Percent Markup on Positions classified as Sales)\n'
    'INSERT new ContractTermDefinition(ref=markup_jobclass_sales_flat, type=decimal, label=Sales Markup (Flat), description=Flat Markup on Positions classified as Sales)\n'
    'model ContractTermDefinition: 22 inserts, 0 updates\n'
    'INSERT new JobClassification(contract_term_prefix=markup_jobclass_it_, label=IT, description=Tech Support and Administration)\n'
    'INSERT new JobClassification(contract_term_prefix=markup_jobclass_engineering_, label=Engineering, description=Software Development)\n'
    'INSERT new JobClassification(contract_term_prefix=markup_jobclass_light_industrial_, label=Light Industrial, description=Factories and construction)\n'
    'INSERT new JobClassification(contract_term_prefix=markup_jobclass_heavy_industrial_, label=Heavy Industrial, description=Heavy machine operation)\n'
    'INSERT new JobClassification(contract_term_prefix=markup_jobclass_administrative_, label=Administrative, description=Back Office, Human Resources)\n'
    'INSERT new JobClassification(contract_term_prefix=markup_jobclass_accounting_, label=Accounting, description=Financial and accounting staff)\n'
    'INSERT new JobClassification(contract_term_prefix=markup_jobclass_creative_, label=Creative, description=Art Department staff)\n'
    'INSERT new JobClassification(contract_term_prefix=markup_jobclass_legal_, label=Legal, description=Paralegal and Attorneys)\n'
    'INSERT new JobClassification(contract_term_prefix=markup_jobclass_driver_, label=Driver, description=Commercial Drivers and chauffeurs)\n'
    'INSERT new JobClassification(contract_term_prefix=markup_jobclass_events_, label=Events, description=Event support staff)\n'
    'INSERT new JobClassification(contract_term_prefix=markup_jobclass_sales_, label=Sales, description=Salesmen)\n'
    'model JobClassification: 11 inserts, 0 updates\n'
    'INSERT new Supplier(name=reachtalent, description=Reach Talent, Inc.)\n'
    'model Supplier: 1 inserts, 0 updates\n'
    'INSERT new CategoryItem(category=pay_scheme, key=exempt, label=Exempt, description=Employees exempt from Fair Labor Standards Act overtime requirements.)\n'
    'INSERT new CategoryItem(category=pay_scheme, key=nonexempt, label=Non-Exempt, description=Employees exempt from Fair Labor Standards Act overtime requirements.)\n'
    'INSERT new CategoryItem(category=pay_scheme, key=cpe, label=Computer Professional Exempt, description=Employees who primarily work on Software and are exempt from Fair Labor Standards Act requirements but still have overtime benefits.)\n'
    'category pay_scheme: 4 inserts, 0 updates\n'
    'INSERT new CategoryItem(category=requisition_type, key=full_time, label=Full Time, description=Employees working full time.)\n'
    'INSERT new CategoryItem(category=requisition_type, key=part_time, label=Part-Time, description=Employees working on part time schedules.)\n'
    'INSERT new CategoryItem(category=requisition_type, key=1099, label=1099, description=Employees working on contractual terms)\n'
    'category requisition_type: 4 inserts, 0 updates\n'
    'INSERT new CategoryItem(category=assignment_end_reason, key=voluntary, label=Voluntary Assignment End, description=Worker decides to leave position.)\n'
    'INSERT new CategoryItem(category=assignment_end_reason, key=involuntary, label=Involuntary Assignment End, description=Employer decides to remove worker from position.)\n'
    'INSERT new CategoryItem(category=assignment_end_reason, key=completed, label=Assignment Completed, description=Assignment is complete.)\n'
    'category assignment_end_reason: 4 inserts, 0 updates\n'
)


@pytest.mark.parametrize(*params(
    {
        'help output': CliTC(
            args=['core', 'update-data', '--help'],
            exp_stdout="""Usage: reachtalent.app core update-data [OPTIONS]

Options:
  --force-update
  -x, --dry-run   Show what changes would be made
  --help          Show this message and exit.
""",
        ),
        'empty dry run': CliTC(
            args=['core', 'update-data', '-x'],
            exp_stdout=expected_full_log,
        ),
        'normal run': CliTC(
            args=['core', 'update-data'],
            exp_stdout=expected_full_log,
        ),
        'populated dry run': CliTC(
            args=['core', 'update-data', '--dry-run'],
            exp_stdout="""model ContractTermDefinition: 0 inserts, 0 updates
model JobClassification: 0 inserts, 0 updates
model Supplier: 0 inserts, 0 updates
category pay_scheme: 0 inserts, 0 updates
category requisition_type: 0 inserts, 0 updates
category assignment_end_reason: 0 inserts, 0 updates
""",
        )
    }
))
def test_update_data(cli_app, runner, args, exp_exit_code, exp_stdout, exp_stderr):
    with cli_app.app_context():
        res = runner.invoke(args=args)
        assert (res.exit_code, res.stderr_bytes) == (exp_exit_code, exp_stderr), getattr(
            res, 'exception', 'Unexpected exit code or err output')
        if exp_stdout is not None:
            assert res.stdout == exp_stdout


@dataclass
class MockDataUpdateTC:
    args: list[str]
    exp_exit_code: int = 0
    exp_stderr: bytes | None = None
    exp_stdout: str | None = None
    mock_yaml_data: dict | None = None
    exp_items_in_db: dict | None = None


def swapped_data():
    return {
        'pay_scheme.yaml': {
            'label': 'Pay Scheme',
            'category_id': 2,
            'description': 'Employee pay categorization for Fair Labor Standards Act requirements.',
            'items': {
                'exempt': {
                    'label': 'Exempt',
                    'description': 'Employees exempt from Fair Labor Standards Act overtime requirements.'
                },
                'nonexempt': {
                    'label': 'Non-Exempt',
                    'description': 'Employees exempt from Fair Labor Standards Act overtime requirements.'},
                'cpe': {
                    'label': 'Computer Professional Exempt',
                    'description': 'Employees who primarily work on Software and are exempt from Fair Labor '
                                   'Standards Act requirements but still have overtime benefits.',
                },
            },
        },
        'requisition_type.yaml': {
            'label': 'Requisition Type',
            'category_id': 1,
            'description': 'Employee pay categorization for Fair Labor Standards Act requirements.',
            'items': {
                'full_time': {'label': 'Full Time', 'description': 'Employees working full time.'},
                'part_time': {'label': 'Part-Time', 'description': 'Employees working on part time schedules.'},
                '1099': {'label': '1099', 'description': 'Employees working on contractual terms'},
            },
        },
    }


@pytest.mark.parametrize(*params(
    {
        'category missing category_id': MockDataUpdateTC(
            args=['core', 'update-data', '-x'],
            exp_exit_code=1,
            exp_stdout="Error: foo.yaml missing 'category_id'\n",
            mock_yaml_data={'foo.yaml': {'label': 'Foo'}},
        ),
        'category id conflict': MockDataUpdateTC(
            args=['core', 'update-data', '-x'],
            exp_exit_code=1,
            exp_stdout="Error: Category Conflict: category_id 1 found for both b and a\n",
            mock_yaml_data={'a.yaml': {'category_id': 1}, 'b.yaml': {'category_id': 1}},
        ),
        'test updates': MockDataUpdateTC(
            args=['core', 'update-data', '-x'],
            exp_stdout=(
                    'UPDATE Supplier(name=reachtalent) with description=Widgets Inc.\n'
                    'model Supplier: 0 inserts, 1 updates\n'
                    "UPDATE CategoryItem(category=pay_scheme, key=exempt) with "
                    "{'label': 'Ex', 'description': 'Employees exempt'}\n"
                    "UPDATE CategoryItem(category=pay_scheme, key=nonexempt) with "
                    "{'label': 'Non', 'description': 'Employees not exempt'}\n"
                    "UPDATE CategoryItem(category=pay_scheme, key=cpe) with {'label': 'CPE'}\n"
                    'category pay_scheme: 0 inserts, 4 updates\n'),
            mock_yaml_data={
                'suppliers.yaml': {
                    'model': 'Supplier',
                    'key_field': 'name',
                    'items': {'reachtalent': {'description': 'Widgets Inc.'}},
                },
                'pay_scheme.yaml': {
                    'label': 'Pay Scheme',
                    'category_id': 1,
                    'description': 'Simple Description',
                    'items': {
                        'exempt': {'label': 'Ex', 'description': 'Employees exempt'},
                        'nonexempt': {'label': 'Non', 'description': 'Employees not exempt'},
                        'cpe': {'label': 'CPE'},
                    },
                }
            },
        ),
        'test category conflict in db without force flag': MockDataUpdateTC(
            args=['core', 'update-data', '-x'],
            exp_exit_code=1,
            exp_stdout='Error: Unable to insert Category(id=1, key=requisition_type) found id conflict in db.\n',
            mock_yaml_data=swapped_data(),
            exp_items_in_db={
                1: {1: 'exempt', 2: 'nonexempt', 3: 'cpe'},
                2: {4: 'full_time', 5: 'part_time', 6: '1099'},
                3: {7: 'voluntary', 8: 'involuntary', 9: 'completed'}
            },
        ),
        'test category conflict in db with force flag': MockDataUpdateTC(
            args=['core', 'update-data', '--force-update'],
            exp_stdout=(
                'category requisition_type: 0 inserts, 0 updates\n'
                'category pay_scheme: 0 inserts, 0 updates\n'
            ),
            mock_yaml_data=swapped_data(),
            exp_items_in_db={
                1: {4: 'full_time', 5: 'part_time', 6: '1099'},
                2: {1: 'exempt', 2: 'nonexempt', 3: 'cpe'},
                3: {7: 'voluntary', 8: 'involuntary', 9: 'completed'},
            },
        ),
    }
))
def test_update_category_data(cli_app, monkeypatch, runner, args, exp_exit_code, exp_stdout, exp_stderr, mock_yaml_data, exp_items_in_db):
    with monkeypatch.context() as m, cli_app.app_context():
        m.setattr(update_data, '_get_yaml_data', lambda: mock_yaml_data)
        res = runner.invoke(args=args)
        assert (res.exit_code, res.stderr_bytes) == (exp_exit_code, exp_stderr)
        if exp_stdout is not None:
            assert res.stdout == exp_stdout
        if exp_items_in_db is not None:

            act_items_in_db = {}
            for obj in db.session.execute(select(CategoryItem)).scalars():
                cat_items = act_items_in_db.setdefault(obj.category_id, {})
                cat_items[obj.id] = obj.key

            assert act_items_in_db == exp_items_in_db


@dataclass
class ImportClientTC:
    args: list[str]
    exp_exit_code: int = 0
    exp_stderr: bytes = None
    exp_stdout: str = ''
    exp_import_log: ImportLog = None


SHEET_ID = '1JnGFg-c9NBdf0bDq767bwS5-bW2MDGfSZ38EwYF7cyk'


@dataclass
class Resp:
    status: int
    reason: str


test_dir = Path(__file__).absolute().parent
googlesheets_path = test_dir / "testdata" / "googlesheets.json"

__SPREADSHEETS__ = None


def _mock_get_spreadsheet(sheet_id: str, ranges: list[str]) -> typing.Mapping[str, list[dict]]:
    global __SPREADSHEETS__
    if __SPREADSHEETS__ is None:
        with googlesheets_path.open('r') as gsheets_file:
            __SPREADSHEETS__ = json.load(gsheets_file)
    qs = '&'.join([f'ranges={urllib.parse.quote_plus(name)}' for name in ranges] + ['alt=json'])
    uri = f'https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values:batchGet?{qs}'
    if sheet_id in __SPREADSHEETS__:
        mock_response = __SPREADSHEETS__[sheet_id].copy()
        value_ranges_by_name = {
            vr['range'].split('!')[0].strip("'"): vr
            for vr in mock_response['valueRanges']
        }
        mock_value_ranges = []
        for name in ranges:
            if vr := value_ranges_by_name.get(name):
                mock_value_ranges.append(vr)
            else:
                raise HttpError(
                    Resp(status=400, reason=f'Unable to parse to parse range: {name}'),
                    b'{"error": {"code": 400, "message": "Unable to parse range: "' +
                    bytes(name, 'utf8') +
                    b'", "status": "INVALID_ARGUMENT"}}',
                    uri=uri,
                )
        mock_response['valueRanges'] = mock_value_ranges
        return __SPREADSHEETS__[sheet_id]
    raise HttpError(
        Resp(status=404, reason='Requested entity was not found.'),
        b'{"error": {"code": 404, "message": "Requested entity was not found.", "status": "NOT_FOUND"}}',
        uri=uri)


SYNC_CLIENT_OUTPUT = (
    'Creating new Client(ExampleSyncClient)\n'
    'Creating 8 locations...\n'
    'Creating 5 cost_centers...\n'
    'Creating 1 staff...\n'
    'Creating 74 users...\n'
    'Creating 2 departments...\n'
    'Creating 6 positions...\n'
    'Creating 2 schedules...\n'
    'Creating 73 workers...\n'
    'Creating 4 requisitions...\n'
    'Creating 73 assignments...\n'
)
SYNC_CLIENT_OUTPUT_DRY = SYNC_CLIENT_OUTPUT + '**DRY RUN CHANGES NOT COMMITTED**\n'
SYNC_UNDO_OUTPUT = (
    'Deleted 73 rows from Assignment...\n'
    'Deleted 4 rows from Requisition...\n'
    'Deleted 73 rows from Worker...\n'
    'Deleted 2 rows from Department...\n'
    'Deleted 1 rows from ClientUser...\n'
    'Deleted 74 rows from User...\n'
    'Deleted 6 rows from Position...\n'
    'Deleted 2 rows from Schedule...\n'
    'Deleted 8 rows from Location...\n'
    'Deleted 5 rows from CostCenter...\n'
    'Deleted 1 rows from Client...\n'
)
SYNC_UNDO_OUTPUT_DRY = SYNC_UNDO_OUTPUT + '**DRY RUN CHANGES NOT COMMITTED**\n'


@pytest.mark.parametrize(*params({
    'help info': ImportClientTC(
        args=['core', 'sync-client', '--help'],
        exp_stdout="""Usage: reachtalent.app core sync-client [OPTIONS] SHEET_ID

  Create Client and client entities (Worker, Staff, Departments, etc.) from a
  Google spreadsheet.

Options:
  -c, --client-id TEXT  ID of existing Client NOTE: This argument is mutually
                        exclusive with  arguments: [name].
  -n, --name TEXT       Name for the Client (existing or new) NOTE: This
                        argument is mutually exclusive with  arguments:
                        [client_id].
  -x, --dry-run         Show what changes would be made
  --help                Show this message and exit.
"""),
    'undo help info': ImportClientTC(
        args=['core', 'sync-undo', '--help'],
        exp_stdout="""Usage: reachtalent.app core sync-undo [OPTIONS] IMPORT_ID

  Delete records created by a previous sync-client import.

Options:
  -c, --client-id TEXT  ID of existing Client NOTE: This argument is mutually
                        exclusive with  arguments: [name].
  -n, --name TEXT       Name for the Client (existing or new) NOTE: This
                        argument is mutually exclusive with  arguments:
                        [client_id].
  -x, --dry-run         Show what changes would be made
  --help                Show this message and exit.
"""),
    'sheet_id is required': ImportClientTC(
        args=['core', 'sync-client'],
        exp_exit_code=2,
        exp_stdout="""Usage: reachtalent.app core sync-client [OPTIONS] SHEET_ID
Try 'reachtalent.app core sync-client --help' for help.

Error: Missing argument 'SHEET_ID'.
""",
    ),
    'client-id or name must be supplied': ImportClientTC(
        args=['core', 'sync-client', 'bad-id'],
        exp_exit_code=2,
        exp_stdout="""Usage: reachtalent.app core sync-client [OPTIONS] SHEET_ID
Try 'reachtalent.app core sync-client --help' for help.

Error: Illegal usage: One of `client_id` or `name` must be supplied.
""",
    ),
    'client-id and name are mutually exclusive': ImportClientTC(
        args=['core', 'sync-client', '--client-id', '1', '--name', 'ExampleClient', 'bad-id'],
        exp_exit_code=2,
        exp_stdout='Error: Illegal usage: `client_id` is mutually exclusive with arguments `name`.\n',
    ),
    'invalid sheet_id': ImportClientTC(
        args=['core', 'sync-client', '--name', 'ExampleSyncClient', 'bad-id'],
        exp_exit_code=1,
        exp_stdout='Sheet `bad-id` was not found.\n',
    ),
    'invalid client_id': ImportClientTC(
        args=['core', 'sync-client', '--client-id', '99', SHEET_ID],
        exp_exit_code=1,
        exp_stdout='Error: No client found for client_id `99`\n',
    ),
    'dry run': ImportClientTC(
        args=['core', 'sync-client', '--dry-run', '--name', 'ExampleSyncClient', SHEET_ID],
        exp_stdout=SYNC_CLIENT_OUTPUT_DRY,
    ),
    'sync valid': ImportClientTC(
        args=['core', 'sync-client', '--name', 'ExampleSyncClient', SHEET_ID],
        exp_stdout=SYNC_CLIENT_OUTPUT,
        exp_import_log=ImportLog(
            id=1,
            source=ImportSource.GOOGLE_SHEET,
            ext_ref=SHEET_ID,
            client_id=None,
            client_name='ExampleSyncClient',
            summary=SYNC_CLIENT_OUTPUT[:-1],
        ),
    ),
    'sync undo: handle invalid import id': ImportClientTC(
        args=['core', 'sync-undo', '--name', 'ExampleSyncClient', '1999'],
        exp_exit_code=1,
        exp_stdout='Error: Import ID 1999 not found\n',
    ),
    'sync undo name must match': ImportClientTC(
        args=['core', 'sync-undo', '--name', 'Other Client', '1'],
        exp_exit_code=1,
        exp_stdout="Error: Import ID 1 doesn't match name: Other Client != ExampleSyncClient\n",
    ),
    'sync undo dry': ImportClientTC(
        args=['core', 'sync-undo', '--name', 'ExampleSyncClient', '--dry-run', '1'],
        exp_stdout=SYNC_UNDO_OUTPUT_DRY,
    ),
    'sync undo': ImportClientTC(
        args=['core', 'sync-undo', '--name', 'ExampleSyncClient', '1'],
        exp_stdout=SYNC_UNDO_OUTPUT,
    ),
    'sync undo again': ImportClientTC(
        args=['core', 'sync-undo', '--name', 'ExampleSyncClient', '1'],
        exp_stdout=(
                'Deleted 0 rows from Assignment...\n'
                'Deleted 0 rows from Requisition...\n'
                'Deleted 0 rows from Worker...\n'
                'Deleted 0 rows from Department...\n'
                'Deleted 0 rows from ClientUser...\n'
                'Deleted 0 rows from User...\n'
                'Deleted 0 rows from Position...\n'
                'Deleted 0 rows from Schedule...\n'
                'Deleted 0 rows from Location...\n'
                'Deleted 0 rows from CostCenter...\n'
                'Deleted 0 rows from Client...\n'
        ),
    ),
    'sync again': ImportClientTC(
        args=['core', 'sync-client', '--name', 'ExampleSyncClient', SHEET_ID],
        exp_stdout=SYNC_CLIENT_OUTPUT,
        exp_import_log=ImportLog(
            id=2,
            source=ImportSource.GOOGLE_SHEET,
            ext_ref=SHEET_ID,
            client_id=None,
            client_name='ExampleSyncClient',
            summary=SYNC_CLIENT_OUTPUT[:-1],
        ),
    ),
}))
def test_sync_data_cli(
        app,
        runner,
        monkeypatch,
        args: list[str],
        exp_exit_code: int,
        exp_stderr: bytes | None,
        exp_stdout: str,
        exp_import_log: ImportLog,
):
    with monkeypatch.context() as m, app.app_context():
        m.setattr(sync_client, '_get_spreadsheet', _mock_get_spreadsheet)
        result = runner.invoke(args=args)
        assert (result.exit_code,
                result.stderr_bytes,
                result.stdout) == (exp_exit_code, exp_stderr, exp_stdout)
        if exp_import_log:
            import_log = db.session.get(ImportLog, exp_import_log.id)
            assert (import_log.ext_ref,
                    import_log.source,
                    import_log.client_id,
                    import_log.client_name,
                    import_log.summary,
                    ) == (
                exp_import_log.ext_ref,
                exp_import_log.source,
                exp_import_log.client_id,
                exp_import_log.client_name,
                exp_import_log.summary,
            )


def odoo_push_mocks_setup(monkeypatch):
    # Mock time delta in messages
    monkeypatch.setattr(odoo_push, 'time_since', lambda t: 0.001)

    mock_common = MagicMock()
    mock_common.versions.__return_value__ = {
        'server_version': '15.0+e',
        'server_version_info': [15, 0, 0, 'final', 0, 'e'],
        'server_serie': '15.0',
        'protocol_version': 1,
    }
    mock_common.authenticate.__return_value__ = 6

    def mock_execute_kw(db, uid, password, model, method, args=None, kwargs=None):
        if method == 'create':
            return [_ for _ in range(1, len(args[0]) + 1)]
        else:
            return True

    mock_models = MagicMock()
    mock_models.execute_kw = mock_execute_kw

    def mock_server_proxy(url: str):
        if url.endswith('/xmlrpc/2/common'):
            return mock_common
        if url.endswith('/xmlrpc/2/object'):
            return mock_models

    monkeypatch.setattr(odoo_push.xmlrpc.client, 'ServerProxy', mock_server_proxy)


DEFAULT_ODOO_PUSH_STDOUT = (
    'Create User Batch #1:... 25 res.partner created in 0.001 seconds.\n'
    'Create User Batch #2:... 25 res.partner created in 0.001 seconds.\n'
    'Create User Batch #3:... 25 res.partner created in 0.001 seconds.\n'
    'Create User Batch #4:... 1 res.partner created in 0.001 seconds.\n'
    'Users pushed: 0 record updated, 76 records created.\n'
    'Create Worker Batch #1:... created 25 hr.employees in 0.001 seconds.\n'
    'Create Worker Batch #2:... created 25 hr.employees in 0.001 seconds.\n'
    'Create Worker Batch #3:... created 25 hr.employees in 0.001 seconds.\n'
    'Create Worker Batch #4:... created 1 hr.employees in 0.001 seconds.\n'
    'Workers pushed: 0 records updated, 76 records created.\n'
)

@pytest.mark.parametrize(*params({
    'help info': CliTC(
        args=['core', 'odoo-push', '--help'],
        exp_stdout="""Usage: reachtalent.app core odoo-push [OPTIONS]

  Sync items from reachtalent to Odoo.

Options:
  -x, --dry-run               Show what changes would be made
  --batch-size INTEGER RANGE  How many records to send in each xmlrpc command
                              [default: 25; 1<=x<=100]
  --help                      Show this message and exit.
"""),
    'dry run': CliTC(
        args=['core', 'odoo-push', '--dry-run'],
        exp_stdout=DEFAULT_ODOO_PUSH_STDOUT + '**DRY RUN CHANGES NOT COMMITTED**\n',
    ),
    'batch size must be 1 or greater': CliTC(
        args=['core', 'odoo-push', '--batch-size', '0'],
        exp_exit_code=2,
        exp_stdout=(
            'Usage: reachtalent.app core odoo-push [OPTIONS]\n'
            "Try 'reachtalent.app core odoo-push --help' for help.\n"
            '\n'
            "Error: Invalid value for '--batch-size': 0 is not in the range 1<=x<=100.\n"
        ),
    ),
    'batch size must be 100 or less': CliTC(
        args=['core', 'odoo-push', '--batch-size', '101'],
        exp_exit_code=2,
        exp_stdout=(
            'Usage: reachtalent.app core odoo-push [OPTIONS]\n'
            "Try 'reachtalent.app core odoo-push --help' for help.\n"
            '\n'
            "Error: Invalid value for '--batch-size': 101 is not in the range 1<=x<=100.\n"
        ),
    ),
    'valid': CliTC(
        args=['core', 'odoo-push'],
        exp_stdout=DEFAULT_ODOO_PUSH_STDOUT,
    ),
}))
def test_odoo_push_cmd(
        app,
        runner,
        monkeypatch,
        args: list[str],
        exp_exit_code: int,
        exp_stderr: bytes | None,
        exp_stdout: str):
    with app.app_context(), monkeypatch.context() as m:
        odoo_push_mocks_setup(m)

        result = runner.invoke(args=args)
        assert (result.exit_code,
                result.stderr_bytes,
                result.stdout) == (exp_exit_code, exp_stderr, exp_stdout)


@dataclass
class OdooPushUpdateTC:
    args: list[str]
    data_manipulation: typing.Callable
    exp_exit_code: int = 0
    exp_stderr: bytes | None = None
    exp_stdout: str | None = None


def update_obj(model_class: typing.Type[database.Base], id: str | int, data: dict):
    obj = db.session.get(model_class, id)
    for field, val in data.items():
        setattr(obj, field, val)
    if getattr(obj, 'last_sync_date', None):
        obj.last_sync_date = datetime(2023, 1, 1)
    db.session.add(obj)
    db.session.commit()


@pytest.mark.parametrize(*params(
    {
        'users update dry run': OdooPushUpdateTC(
            args=['core', 'odoo-push', '--dry-run'],
            data_manipulation=lambda: update_obj(
                auth_models.User, 111, {'email': 'a-new-email@example.com'}),
            exp_stdout=(
                'Updating User(111):... updated in 0.001 seconds.\n'
                'Users pushed: 1 record updated, 0 records created.\n'
                'Workers pushed: 0 records updated, 0 records created.\n'
                '**DRY RUN CHANGES NOT COMMITTED**\n'
            ),
        ),
        'users update': OdooPushUpdateTC(
            args=['core', 'odoo-push'],
            data_manipulation=lambda: update_obj(
                auth_models.User, 111, {'email': 'a-new-email@example.com'}),
            exp_stdout=(
                'Updating User(111):... updated in 0.001 seconds.\n'
                'Users pushed: 1 record updated, 0 records created.\n'
                'Workers pushed: 0 records updated, 0 records created.\n'
            ),
        ),
        'workers update dry run': OdooPushUpdateTC(
            args=['core', 'odoo-push', '-x'],
            data_manipulation=lambda: update_obj(
                Worker, 4, {'phone_number': '555 555 55555'}),
            exp_stdout=(
                'Users pushed: 0 record updated, 0 records created.\n'
                'Updating Worker(4):... updated in 0.001 seconds.\n'
                'Workers pushed: 1 records updated, 0 records created.\n'
                '**DRY RUN CHANGES NOT COMMITTED**\n'
            ),
        ),
        'workers update': OdooPushUpdateTC(
            args=['core', 'odoo-push'],
            data_manipulation=lambda: update_obj(
                Worker, 4, {'phone_number': '555 555 55555'}),
            exp_stdout=(
                'Users pushed: 0 record updated, 0 records created.\n'
                'Updating Worker(4):... updated in 0.001 seconds.\n'
                'Workers pushed: 1 records updated, 0 records created.\n'
            ),
        ),
    }
))
def test_odoo_push_cmd_updates(
        app,
        runner,
        monkeypatch,
        db_transaction,
        args: list[str],
        data_manipulation: typing.Callable,
        exp_exit_code: int,
        exp_stderr: bytes | None,
        exp_stdout: str
):
    with app.app_context(), monkeypatch.context() as m:
        odoo_push_mocks_setup(m)

        # Do Data Manipulation
        data_manipulation()

        # Run sync again to verify updates
        result = runner.invoke(args=args)
        assert (result.exit_code,
                result.stderr_bytes,
                result.stdout) == (exp_exit_code, exp_stderr, exp_stdout)
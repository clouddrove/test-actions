from datetime import date, datetime
from decimal import InvalidOperation, Decimal
import json
from pathlib import Path
from traceback import format_exc
import typing

import click
from flask import current_app
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

from ...extensions import db
from ...auth.models import User, Role
from ..models import (
    Assignment, AssignmentState, Category, CategoryItem, Client, ClientUser,
    CostCenter, Department, department_location, department_position,
    ImportLog, ImportSource, JobClassification, Location, Requisition, 
    Position, Schedule, Worker
)

SheetData = typing.NewType('SheetData', typing.Mapping[str, list[dict]])


SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


def _get_credentials(client_id: str, client_secret: str) -> Credentials:
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    token_path = Path('token.json')
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(
                client_config={
                    'installed': {
                        'client_id': client_id,
                        'client_secret': client_secret,
                        "project_id": "crafty-raceway-376517",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "redirect_uris": ["http://localhost"]
                    },
                }, scopes=SCOPES)
            creds = flow.run_local_server(bind_addr="0.0.0.0", port=18000)
        # Save the credentials for the next run
        token_path.write_text(creds.to_json())
    return creds


def _get_spreadsheet(sheet_id: str, ranges: list[str]) -> dict:
    creds = _get_credentials(
        current_app.config['SYNC_CLIENT_OAUTH_CLIENT_ID'],
        current_app.config['SYNC_CLIENT_OAUTH_CLIENT_SECRET'])
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    return sheet.values().batchGet(spreadsheetId=sheet_id,
                                   ranges=ranges).execute()


def get_sheet_data(sheet_id: str) -> SheetData:
    ranges = ['Worker Roster', 'Client Users', 'Locations', 'Client Departments', 'Job Title', 'Cost Codes']
    try:
        result = _get_spreadsheet(sheet_id, ranges)
    except HttpError as err:
        if err.status_code == 404:
            echo(f"Sheet `{sheet_id}` was not found.")
        else:
            echo(err)
        raise

    return transform_sheet_to_data_dict(result)


def values_to_dict_rows(values: list[list[str]]) -> list[dict]:
    sheet_header, col_header, raw_rows = values[0], tuple(map(str.strip, values[1])), values[2:]
    rows = []
    col_count = len(col_header)
    for raw_row in raw_rows:
        if (extra_cells := col_count - len(raw_row)) > 0:
            raw_row.extend([''] * extra_cells)
        rows.append(dict(zip(col_header, raw_row)))
    return rows


def transform_sheet_to_data_dict(result) -> SheetData:
    out = {}
    for value_range in result.get('valueRanges', [{}, {}, {}, {}]):
        sheet_name = value_range['range'].split("!")[0].strip(" '")
        out[sheet_name] = values_to_dict_rows(value_range.get('values', []))
    return out


def _parse_decimal(val_str: str) -> Decimal | None:
    val = None
    if _val := val_str.strip(' $'):
        try:
            val = Decimal(_val)
        except InvalidOperation as exc:
            pass
    return val


def _sync_locations(import_id: int, ctx: dict, data: SheetData):
    locations = {}
    for row in data['Locations']:
        loc = Location(
            import_id=import_id,
            client=ctx['client'],
            name=row['Location'],
            street=row['Street'],
            city=row['City'],
            state=row['State'],
            zip=row['Zip Code'],
            country='US',
        )
        db.session.add(loc)
        locations[loc.name] = loc

    ctx['locations'] = locations


def _sync_cost_centers(import_id: int, ctx: dict, data: SheetData):
    cost_centers = {}
    for row in data['Cost Codes']:
        code = CostCenter(
            import_id=import_id,
            client=ctx['client'],
            name=row['Project Name'],
            description=row['Cost Code #'],
        )
        db.session.add(code)
        cost_centers[code.name] = code
    ctx['cost_centers'] = cost_centers


def _sync_staff(import_id: int, ctx: dict, data: SheetData):
    users = {}
    staff = {}
    staff_departments = []
    _reports_to = []
    roles = {
        role.name: role
        for role in db.session.execute(
            select(Role).filter(Role.client_id == None)
        ).scalars()
    }

    for row in data['Client Users']:
        # Get or Create User
        user = db.session.execute(select(User).filter_by(email=row['Manager Email'])).scalar_one_or_none()
        if not user:
            user = User(
                import_id=import_id,
                email=row['Manager Email'],
                name=row['Manager Name'],
            )
            db.session.add(user)
        users[user.email] = users

        # Parse Cost Center value
        cost_center = None
        cost_center_val = row['Cost Center (if applicable)'].strip()
        if cost_center_val and cost_center_val != 'NA':
            cost_center = ctx['cost_centers'].get(cost_center_val)

        # Parse Access Level
        role = roles.get(row['Access Level'])

        cu = ClientUser(
            import_id=import_id,
            client=ctx['client'],
            user=user,
            title=row['Title'],
            phone_number=row['Manager Phone Number'],
            cost_center=cost_center,
            role=role,
        )
        staff[user.email] = cu

        # Deferred relationships
        staff_departments.append((cu, row['Department(s)']))
        if row['Report to'].strip():
            _reports_to.append((cu, row['Report to']))

    for cu, report_to_raw in _reports_to:
        cu.reports_to = _find_staff(ctx, report_to_raw)

    ctx['staff'] = staff
    ctx['users'] = users
    ctx['_staff_departments'] = staff_departments


def _find_staff(ctx: dict, pseudo_id: str) -> ClientUser | None:
    for email, cu in ctx.get('staff', {}).items():
        if pseudo_id in (email, cu.user.name):
            return cu
    return None


def _find_dept(ctx: dict, pseudo_id: str) -> Department | None:
    for name, dep in ctx.get('departments', {}).items():
        if pseudo_id in (name, dep.number):
            return dep
    return None


def _sync_departments(import_id: int, ctx: dict, data: SheetData):
    departments = {}
    for row in data['Client Departments']:
        # Parse department number
        dept_number = None
        if (dept_number_raw := row['Dept Number']) and dept_number_raw.lower() not in ('na', 'n/a'):
            dept_number = dept_number_raw

        owner = _find_staff(ctx, row['Dept Owner'])
        fpna_approver = _find_staff(ctx, row['FP&A Approver'])

        locations = []
        locations_raw = row['Location(s)'].split(',')
        for loc_raw in locations_raw:
            if loc := ctx['locations'].get(loc_raw):
                locations.append(loc)

        dep = Department(
            import_id=import_id,
            client=ctx['client'],
            number=dept_number,
            name=row['Dept Name'],
            owner=owner,
            accounting_approver=fpna_approver,
            locations=locations,
        )
        db.session.add(dep)
        departments[dep.name] = dep

    ctx['departments'] = departments

    for cu, staff_departments_raw in ctx['_staff_departments']:
        _departments = []
        for dep_raw in staff_departments_raw.split(','):
            if dep := _find_dept(ctx, dep_raw.strip()):
                _departments.append(dep)


def _sync_positions(import_id: int, ctx: dict, data: SheetData):
    positions = {}

    job_classifications = {
        jc.label.lower(): jc
        for jc in db.session.execute(
            select(JobClassification)
        ).scalars()
    }

    for row in data['Job Title']:
        departments = []
        for dep_raw in row['Dept Number(s)'].split(','):
            if dep := _find_dept(ctx, dep_raw.strip()):
                departments.append(dep)

        pos = Position(
            import_id=import_id,
            client=ctx['client'],
            departments=departments,
            title=row['Job Title'].strip(),
            job_description=row['Job Description'],
            job_classification=job_classifications.get(row['Job Classification'].lower()),
            requirements=row['Job Requirements'].split('\n'),
            pay_rate_min=_parse_decimal(row['Pay Rate Min']),
            pay_rate_max=_parse_decimal(row['Pay Rate Max']),
        )
        db.session.add(pos)
        positions[pos.title] = pos

    ctx['positions'] = positions


def _find_or_create_requisition(
        import_id: int, ctx: dict, requisitions: dict,
        dept: Department,
        location: Location,
        position: Position,
        schedule: str,
        supervisor: User,
        timecard_approver: User,
        pay_scheme: CategoryItem,
        req_type: CategoryItem,
        pay_rate: Decimal,
        start_date: date,
        end_date: date,

) -> Requisition:
    req_key = '-'.join([
        dept.name,
        location.name,
        position.title,
        schedule,
        supervisor.email,
        timecard_approver.email,
        pay_scheme.key,
        req_type.key,
        str(pay_rate)
    ]).lower()

    schedules = ctx.setdefault('schedules', {})
    if not (sched := schedules.get(schedule)):
        sched = Schedule(
            client=ctx['client'],
            name=schedule,
            import_id=import_id,
        )
        db.session.add(sched)
        schedules[schedule] = sched

    req = requisitions.get(req_key)
    if not req:
        req = Requisition(
            import_id=import_id,
            client=ctx['client'],
            department=dept,
            location=location,
            position=position,
            schedule=sched,
            supervisor=supervisor,
            timecard_approver=timecard_approver,
            requisition_type=req_type,
            pay_scheme=pay_scheme,
            num_assignments=1,
            pay_rate=pay_rate,
            start_date=start_date,
            estimated_end_date=end_date,
        )
        requisitions[req_key] = req
    else:
        req.num_assignments += 1

    return req


def _parse_date(val_str: str) -> date | None:
    val = None
    if val_str and val_str.lower() not in ('na', 'n/a'):
        try:
            val = datetime.strptime(val_str, "%m/%d/%Y").date()
        except ValueError as exc:
            pass
    return val


def _sync_workers(import_id: int, ctx: dict, data: SheetData):
    users = {}
    workers = {}
    requisitions = {}
    assignments = {}

    pay_schemes = {
        obj.label: obj
        for obj in db.session.execute(
            select(CategoryItem).
            join(Category).
            filter(Category.key == 'pay_scheme')).scalars()
    }

    req_types = {
        obj.label: obj
        for obj in db.session.execute(
            select(CategoryItem).
            join(Category).
            filter(Category.key == 'requisition_type')).scalars()
    }

    for row in data['Worker Roster']:
        email = row["Worker's email"].lower()
        user = db.session.execute(select(User).filter_by(email=email)).scalar_one_or_none()
        if not user:
            user = User(
                import_id=import_id,
                name=row['Worker name'],
                email=email,
            )
            users[email] = user
            db.session.add(user)

        worker = Worker(
            import_id=import_id,
            user=user,
            supplier_id=1,  # Hardcoded to RTI
            phone_number=row["Worker's phone number"],

        )

        workers[email] = worker
        db.session.add(worker)

        dept = _find_dept(ctx, row['Department'])
        loc = ctx['locations'][row['Job location']]
        position = ctx['positions'][row['Job title']]
        manager = ctx['staff'][row["Manager email"]]

        # Calculate Pay Rate
        weekly_rate = _parse_decimal(row['Salary Weekly Rate'])
        if weekly_rate:
            pay_rate = weekly_rate / 40
        else:
            pay_rate = _parse_decimal(row['Pay rate'])

        # Calculate Bill Rate
        weekly_bill_rate = _parse_decimal(row['Salary Weekly Bill Rate'])
        if weekly_bill_rate:
            bill_rate = weekly_rate / 40
        else:
            bill_rate = _parse_decimal(row['Bill Rate'])

        # Calculate start date
        tentative_start_date = _parse_date(row['Start Date'])
        start_date = None
        if tentative_start_date < date.today():
            start_date = tentative_start_date

        # Calculate end date
        tentative_end_date = _parse_date(row['Estimated End Date'])

        req = _find_or_create_requisition(
            import_id, ctx, requisitions,
            dept=dept,
            location=loc,
            position=position,
            schedule=row['Schedule'] or 'Default',
            supervisor=manager.user,
            timecard_approver=manager.user,
            pay_scheme=pay_schemes[row['Pay Scheme']],
            req_type=req_types[row['Req Type']],
            pay_rate=pay_rate,
            start_date=start_date or tentative_start_date,
            end_date=tentative_end_date,
        )

        # Parse status
        status = AssignmentState.PENDING_START
        if row['Active'].lower() in ('t', 'true', '1', 'y', 'yes'):
            status = AssignmentState.ACTIVE

        assignment = Assignment(
            import_id=import_id,
            status=status,
            requisition=req,
            worker=worker,
            department=_find_dept(ctx, row['Department']),
            cost_center=ctx['cost_centers'].get(row['Cost Center (if applicable)']),
            pay_rate=pay_rate,
            bill_rate=bill_rate,
            tentative_start_date=tentative_start_date,
            actual_start_date=start_date,
            tentative_end_date=tentative_end_date,
        )
        db.session.add(assignment)
        assignments[email] = assignment

    ctx['users'].update(users)
    ctx['workers'] = workers
    ctx['requisitions'] = requisitions
    ctx['assignments'] = assignments


def sync_undo(import_id: int, name: str, client_id: int, dry_run: bool):
    _models = [
        Assignment,
        Requisition,
        Worker,
        Department,
        ClientUser,
        User,
        Position,
        Schedule,
        Location,
        CostCenter,
        Client,
    ]

    try:
        import_log = db.session.get(ImportLog, import_id)
        if not import_log:
            raise click.ClickException(f"Import ID {import_id} not found")
        if name and import_log.client_name != name:
            raise click.ClickException(
                f"Import ID {import_id} doesn't match name: {name} != {import_log.client_name}")
        elif client_id and import_log.client_id != import_log.client_id:
            raise click.ClickException(
                f"Import ID {import_id} doesn't match client_id: {client_id} != {import_log.client_id}")
        for model in _models:
            if model is Department:
                department_ids = db.session.scalars(
                    db.session.query(Department.id).filter(Department.import_id == import_log.id)
                ).all()
                db.session.query(department_location).filter(
                    department_location.c.department_id.in_(department_ids)).delete()
                db.session.query(department_position).filter(
                    department_position.c.department_id.in_(department_ids)).delete()
            count = db.session.query(model).filter(model.import_id == import_log.id).delete()

            echo(f"Deleted {count} rows from {model().__class__.__name__}...")
    except Exception as exc:
        raise

    if not dry_run:
        db.session.commit()
    else:
        click.echo("**DRY RUN CHANGES NOT COMMITTED**")


class MutuallyExclusiveOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop('mutually_exclusive', []))
        _help = kwargs.get('help', '')
        if self.mutually_exclusive:
            ex_str = ', '.join(self.mutually_exclusive)
            kwargs['help'] = _help + (
                ' NOTE: This argument is mutually exclusive with '
                ' arguments: [' + ex_str + '].'
            )
        super(MutuallyExclusiveOption, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise click.UsageError(
                "Illegal usage: `{}` is mutually exclusive with "
                "arguments `{}`.".format(
                    self.name,
                    ', '.join(self.mutually_exclusive)
                )
            )

        return super(MutuallyExclusiveOption, self).handle_parse_result(
            ctx,
            opts,
            args
        )


def get_or_create_client(import_id: int, name: str, client_id: int) -> Client:
    if client_id:
        return db.session.get(Client, client_id)

    try:
        client = db.session.execute(select(Client).filter_by(name=name)).scalar_one()
    except NoResultFound:
        client = Client(import_id=import_id, name=name)
    return client


IMPORT_SESSION_LOG = []


def echo(message):
    global IMPORT_SESSION_LOG
    IMPORT_SESSION_LOG.append(message)
    click.echo(message=message)


@click.command('sync-client')
@click.argument('sheet_id')
@click.option('--client-id', '-c',
              help='ID of existing Client',
              cls=MutuallyExclusiveOption,
              mutually_exclusive=["name"])
@click.option('--name', '-n',
              help='Name for the Client (existing or new)',
              cls=MutuallyExclusiveOption,
              mutually_exclusive=['client_id'])
@click.option('--dry-run', '-x', is_flag=True, default=False,
              help='Show what changes would be made')
def sync_client_cmd(sheet_id: str, name: str, client_id: int, dry_run: bool = False):
    """
    Create Client and client entities (Worker, Staff, Departments, etc.) from
    a Google spreadsheet.
    """
    global IMPORT_SESSION_LOG
    IMPORT_SESSION_LOG = []
    if not name and not client_id:
        raise click.UsageError("Illegal usage: One of `client_id` or `name` must be supplied.")

    try:
        data = get_sheet_data(sheet_id)

        import_log = ImportLog(
            source=ImportSource.GOOGLE_SHEET,
            ext_ref=sheet_id,
            client_id=client_id,
            client_name=name,
        )
        db.session.add(import_log)
        db.session.flush()

        client = get_or_create_client(import_log.id, name, client_id)

        if not client:
            raise click.ClickException(f"No client found for client_id `{client_id}`")

        if client.id:
            echo(f"Using existing Client(id={client.id}, name='{client.name}')")
        else:
            echo(f"Creating new Client({client.name})")

        context = {
            'client': client,
        }

        _sync_locations(import_log.id, context, data)
        _sync_cost_centers(import_log.id, context, data)
        _sync_staff(import_log.id, context, data)
        _sync_departments(import_log.id, context, data)
        _sync_positions(import_log.id, context, data)
        _sync_workers(import_log.id, context, data)

        for obj_name, mapping in context.items():
            if obj_name not in ('client', '_staff_departments'):
                echo(f"Creating {len(mapping)} {obj_name}...")
        
        # Record import log
        import_log.summary = '\n'.join(IMPORT_SESSION_LOG)
        
        if not dry_run:
            db.session.commit()
        else:
            click.echo("**DRY RUN CHANGES NOT COMMITTED**")

    except (HttpError, click.ClickException) as exc:
        raise
    except Exception as exc:
        echo(f"Unexpected error: {exc}\n{format_exc()}")
        raise


@click.command('sync-undo')
@click.argument('import_id', type=int)
@click.option('--client-id', '-c',
              help='ID of existing Client',
              cls=MutuallyExclusiveOption,
              mutually_exclusive=["name"])
@click.option('--name', '-n',
              help='Name for the Client (existing or new)',
              cls=MutuallyExclusiveOption,
              mutually_exclusive=['client_id'])
@click.option('--dry-run', '-x', is_flag=True, default=False,
              help='Show what changes would be made')
def sync_undo_cmd(import_id: int, name: str, client_id: int, dry_run: bool):
    """
    Delete records created by a previous sync-client import.
    """
    return sync_undo(import_id, name, client_id, dry_run)


project_dir = Path(__file__).absolute().parent.parent.parent.parent
test_google_sheet_path = project_dir / "tests" / "testdata" / "googlesheets.json"


@click.command('dump-census-sheet')
@click.argument('sheet_id')
def dump_census_sheet_cmd(sheet_id: str):
    """
    This function is mainly used for developing and testing the sync_client command.
    """
    gsheet_json = {}
    if test_google_sheet_path.exists():
        with test_google_sheet_path.open('r') as fp:
            gsheet_json = json.load(fp)

    creds = _get_credentials(
        current_app.config['SYNC_CLIENT_OAUTH_CLIENT_ID'],
        current_app.config['SYNC_CLIENT_OAUTH_CLIENT_SECRET'])
    service = build('sheets', 'v4', credentials=creds)

    spreadsheets_client = service.spreadsheets()

    # Get Sheet Metadata
    spreadsheet = spreadsheets_client.get(spreadsheetId=sheet_id).execute()

    # Get Sheet ranges (i.e. sheet titles)
    ranges = [
        sheet['properties'].get('title', f'Sheet{i+1}')
        for i, sheet in enumerate(spreadsheet.get('sheets', []))
    ]

    # Get sheet data from ranges
    data = spreadsheets_client.values().batchGet(
        spreadsheetId=sheet_id, ranges=ranges).execute()

    # Update gsheet_json and write to disk
    gsheet_json[sheet_id] = data
    with test_google_sheet_path.open('w') as fp:
        json.dump(gsheet_json, fp, indent=2)
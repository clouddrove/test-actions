from time import time
from datetime import datetime, timedelta
from traceback import format_exc
import itertools
import typing
import xmlrpc.client

import click
from flask import current_app
import sqlalchemy as sa

from .. import models
from ...extensions import db
from ...logger import make_logger


logger = make_logger('reachtalent.cmd.odoo_push')
DEFAULT_BATCH_SIZE = 25
MIN_BATCH_SIZE, MAX_BATCH_SIZE = 1, 100
ODOO_PUSH_SESSION_LOG = []
T = typing.TypeVar('T')


def batch_by_n(iterable: typing.Iterable[T], size: int) -> typing.Iterator[list[T]]:
    source_iter = iter(iterable)
    try:
        while True:
            batch_iter = itertools.islice(source_iter, size)
            yield itertools.chain([next(batch_iter)], batch_iter)
    except StopIteration:
        return


class Odoo:

    def __init__(self, url, db, username, password):
        self.url = url
        self.db = db
        self.username = username
        self.password = password

        logger.info('Odoo : Initiating Connection: %s', self.url)

        self.common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(self.url))
        self.version = self.common.version()
        self.uid = self.common.authenticate(self.db, self.username, self.password, {})

        logger.info('Odoo : Authenticated as user %s', username)

        self.models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url))

    def has_permissions(self, model, permissions):

        if permissions is None:
            permissions = []

        chk_has_permissions = self.models.execute_kw(self.db, self.uid, self.password,
                                                     model, 'check_access_rights',
                                                     permissions, {'raise_exception': False})

        logger.debug('Odoo : Permissions check: %s %s : %s', model, str(permissions), chk_has_permissions)

        return chk_has_permissions

    def search(self, model, search_filters, search_params=None):

        results = self.models.execute_kw(self.db, self.uid, self.password,
                                         model, 'search', search_filters, search_params)

        return results

    def search_read(self, model, search_filters, search_params=None):

        results = self.models.execute_kw(self.db, self.uid, self.password,
                                         model, 'search_read', search_filters, search_params)

        # TODO : ERG Research Odoo's API and get rid of this loop to clean data.
        #        Query appears to be returning more than just an id for related data, looks like a list with name value
        #        There should be a setting in "search_params" to avoid this. Example:
        #        From res_country_state : {'id': 1385, 'country_id': [63, 'Ecuador'], 'name': 'Bolivar', 'code': '02'}
        #        Adding a filter for this, assuming first item in the "list" will always be the id
        new_results = []

        for row in results:
            new_row = {}
            for key, val in row.items():
                if isinstance(val, list):
                    new_row[key] = val[0]
                else:
                    new_row[key] = val
            new_results.append(new_row)
            results = new_results

        return results

    def create_batch(self, model: str, data_list: list[dict]) -> (str, list[int]):
        new_record_ids = []
        status = None

        # Check if cache has enough records to create the batch
        try:
            new_record_ids = self.models.execute_kw(self.db, self.uid, self.password, model, 'create', [data_list])
        except:
            raise

        if new_record_ids:
            status = 'success'
            logger.debug('ODOO : create : SUCCESSFUL - %s new record(s) created', len(new_record_ids))
        else:
            status = 'error'
            logger.warning('ODOO : create : FAILED')

        return status, new_record_ids

    def update(self, model: str, id: str | int, vals: dict) -> bool:
        return self.models.execute_kw(self.db, self.uid, self.password, model, 'write', [id, vals])


def users_to_create() -> typing.Iterable[models.User]:
    """
    Returns sqlalchemy query of Users that have a Worker record and have not
    been synced to Odoo.
    """
    return db.session.execute(
        sa.select(models.User)
        .join(models.Worker, models.Worker.user_id == models.User.id)
        .filter(
            models.User.ext_ref == '',
        )
    ).scalars()


def users_to_update() -> typing.Iterable[models.User]:
    return db.session.execute(
        sa.select(models.User)
        .join(models.Worker, models.Worker.user_id == models.User.id)
        .filter(
            models.User.ext_ref != '',
            sa.or_(
                models.User.modified_date > models.User.last_sync_date,
                models.Worker.modified_date > models.User.last_sync_date,
            )
        )
    ).scalars()


def user_to_res_partner(user: models.User) -> dict:
    payload = {
        'name': user.name,
        'email': user.email,
        'phone': user.worker.phone_number,
    }
    return payload


def workers_to_create() -> typing.Iterable[models.Worker]:
    return db.session.execute(
        sa.select(models.Worker)
        .join(models.User, models.Worker.user_id == models.User.id)
        .filter(
            models.Worker.ext_ref == '',
        )
    ).scalars()


def workers_to_update() -> typing.Iterable[models.Worker]:
    return db.session.execute(
        sa.select(models.Worker)
        .join(models.User, models.Worker.user_id == models.User.id)
        .filter(
            models.Worker.ext_ref != '',
            models.User.ext_ref != '',
            sa.or_(
                models.Worker.modified_date > models.Worker.last_sync_date,
                models.User.modified_date > models.Worker.last_sync_date,
            ),
        )
    ).scalars()


def worker_to_hr_employee(worker: models.Worker) -> dict:
    payload = {
        'name': worker.user.name,
    }
    if worker.user.ext_ref != '':
        payload['address_home_id'] = int(worker.user.ext_ref)
    return payload


def time_since(t: time) -> float:
    return time() - t


def push_users(odoo: Odoo | None, batch_size: int, dry_run: bool) -> (int, int):
    _updated, _created = 0, 0

    # Update existing res.partner
    for user in users_to_update():
        sync_dt = datetime.utcnow()
        echo(f'Updating User({user.id}):...', nl=False)
        t1 = time()

        hr_employee = user_to_res_partner(user)

        if not dry_run:
            odoo.update('res.partner', int(user.ext_ref), hr_employee)
            user.modified_date = user.modified_date - timedelta(microseconds=1)
            user.last_sync_date = sync_dt
            db.session.add(user)
            db.session.commit()

        _updated += 1
        echo(f' updated in {time_since(t1):.3f} seconds.')

    new_users = users_to_create()

    batch_num = 0
    for _batch in batch_by_n(new_users, batch_size):
        sync_dt = datetime.utcnow()
        batch_num += 1
        echo(f'Create User Batch #{batch_num}:...', nl=False)

        t1 = time()

        batch = [obj for obj in _batch]

        new_res_partners = [user_to_res_partner(user) for user in batch]
        batch_created = len(batch)

        if not dry_run:
            status, new_ids = odoo.create_batch('res.partner', new_res_partners)

            if status == 'error':
                raise click.ClickException('No ids returned from create_batch')

            batch_created = len(new_ids)

            for ix, new_id in enumerate(new_ids):
                batch[ix].ext_ref = new_id
                batch[ix].last_sync_date = sync_dt
                db.session.add(batch[ix])
            db.session.commit()

        echo(f' {batch_created} res.partner created in {time_since(t1):.3f} seconds.')
        _created += batch_created

    return _updated, _created


def push_workers(odoo: Odoo | None, batch_size: int, dry_run: bool) -> (int, int):
    _updated, _created = 0, 0

    # Update existing Workers
    for worker in workers_to_update():
        sync_dt = datetime.utcnow()
        echo(f'Updating Worker({worker.id}):...', nl=False)
        t1 = time()

        hr_employee = worker_to_hr_employee(worker)
        if not dry_run:
            odoo.update('hr.employee', int(worker.ext_ref), hr_employee)
            worker.modified_date = worker.modified_date - timedelta(microseconds=1)
            worker.last_sync_date = sync_dt
            db.session.add(worker)
            db.session.commit()

        _updated += 1
        echo(f' updated in {time_since(t1):.3f} seconds.')

    # Create New Workers
    new_workers = workers_to_create()

    batch_num = 0
    for _batch in batch_by_n(new_workers, batch_size):
        sync_dt = datetime.utcnow()
        batch_num += 1
        echo(f'Create Worker Batch #{batch_num}:...', nl=False)
        t1 = time()

        # create indexable list batch from islice
        batch = [worker for worker in _batch]

        batch_created = len(batch)
        new_hr_employees = [worker_to_hr_employee(worker) for worker in batch]

        if not dry_run:
            status, new_ids = odoo.create_batch('hr.employee', new_hr_employees)

            batch_created = len(new_ids)
            for ix, new_id in enumerate(new_ids):
                batch[ix].ext_ref = new_id
                batch[ix].last_sync_date = sync_dt
                db.session.add(batch[ix])
            db.session.commit()

        echo(f' created {batch_created} hr.employees in {time_since(t1):.3f} seconds.')

        _created += batch_created

    return _updated, _created


def echo(message, nl: bool = True):
    global ODOO_PUSH_SESSION_LOG
    if not nl and ODOO_PUSH_SESSION_LOG:
        ODOO_PUSH_SESSION_LOG[-1] = ODOO_PUSH_SESSION_LOG[-1] + message
    ODOO_PUSH_SESSION_LOG.append(message)
    click.echo(message=message, nl=nl)


def _odoo_push(batch_size: int = DEFAULT_BATCH_SIZE, dry_run: bool = True):
    global ODOO_PUSH_SESSION_LOG
    ODOO_PUSH_SESSION_LOG = []  # Reset odoo push session log

    odoo = None
    try:
        if not dry_run:
            odoo = Odoo(
                url=current_app.config['ODOO_URL'],
                db=current_app.config['ODOO_DB'],
                username=current_app.config['ODOO_USERNAME'],
                password=current_app.config['ODOO_PASSWORD'],
            )

        users_updated, users_created = push_users(odoo, batch_size=batch_size, dry_run=dry_run)
        echo(f'Users pushed: {users_updated} record updated, {users_created} records created.')

        workers_updated, workers_created = push_workers(odoo, batch_size=batch_size, dry_run=dry_run)
        echo(f'Workers pushed: {workers_updated} records updated, {workers_created} records created.')
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(f'Unhandled Exception: {format_exc()}')

    if not dry_run:
        db.session.commit()
    else:
        click.echo("**DRY RUN CHANGES NOT COMMITTED**")


@click.command('odoo-push')
@click.option('--dry-run', '-x', is_flag=True, default=False,
              help='Show what changes would be made')
@click.option('--batch-size',
              default=DEFAULT_BATCH_SIZE,
              show_default=True,
              type=click.IntRange(MIN_BATCH_SIZE, MAX_BATCH_SIZE),
              help='How many records to send in each xmlrpc command')
def odoo_push_cmd(dry_run: bool = False, batch_size: int = DEFAULT_BATCH_SIZE):
    """
    Sync items from reachtalent to Odoo.
    """
    return _odoo_push(batch_size, dry_run)


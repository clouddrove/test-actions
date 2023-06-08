import click
import sqlalchemy as sa
from sqlalchemy.orm.exc import NoResultFound

from . import permissions
from .models import db, Permission, Role
from ..core.models import Client


def _upsert_rti_client(dry_run: bool) -> Client:
    try:
        rti_client = Client.query. \
            filter_by(name=Client.RTI_CLIENT_NAME).one()
    except NoResultFound:
        rti_client = Client(name=Client.RTI_CLIENT_NAME)

    if dry_run:
        if rti_client.id is None:
            click.echo(f'INSERT RTI Client')
            rti_client.id = 1  # Give RTI an ID for dry-run insert example.
    else:
        if rti_client.id is None:
            db.session.add(rti_client)
            db.session.flush()
    click.echo(f'RTI Client ID={rti_client.id}')

    return rti_client


def _upsert_permissions(perms: list[str], dry_run: bool) -> dict[str, Permission]:
    permissions_in_database = {
        perm.name: perm
        for perm in Permission.query.all()}
    new_permissions = []
    for perm_name in perms:
        if perm_name in permissions_in_database:
            continue
        ent, field, act = perm_name.split('.')
        perm = Permission(name=perm_name, entity=ent, field=field, action=act)
        new_permissions.append(perm)

    if dry_run:
        if new_permissions:
            click.echo('\n'.join(
                f'INSERT new Permission {perm}'
                for perm in new_permissions
            ))
    else:
        for perm in new_permissions:
            click.echo(f'INSERT new Permission {perm}')
            db.session.add(perm)
        db.session.flush()

    for perm in new_permissions:
        permissions_in_database[perm.name] = perm
    return permissions_in_database


def _upsert_roles(
        client_id: int | None,
        permissions_in_db: dict[str, Permission],
        roles: dict[str, list[str]],
        dry_run: bool):
    role_query = Role.query.filter_by(client_id=sa.null())
    if client_id:
        role_query = Role.query.filter_by(client_id=client_id)

    roles_in_db = {role.name: role for role in role_query}

    new_roles = []

    new_role_perms = []
    role_perms_to_remove = []

    for role_name, perms in roles.items():
        if not (role := roles_in_db.get(role_name)):
            role = Role(name=role_name, client_id=client_id)
            new_roles.append(role)
            new_role_perms.extend([
                (role, permissions_in_db[p])
                for p in perms
            ])
        else:
            existing_perms = set([p.name for p in role.permissions])
            missing_perms = set(perms) - existing_perms
            extra_perms = existing_perms - set(perms)

            new_role_perms.extend([
                (role, permissions_in_db[p])
                for p in missing_perms
            ])
            role_perms_to_remove.extend([
                (role, permissions_in_db[p])
                for p in extra_perms
            ])

    if dry_run:
        if new_roles:
            click.echo('\n'.join(
                f'INSERT new Role {role}' for role in new_roles
            ))
        if new_role_perms:
            click.echo('\n'.join(
                f'INSERT new RolePerm ({role}, {perm})'
                for role, perm in new_role_perms
            ))
        if role_perms_to_remove:
            click.echo('\n'.join(
                f'DELETE RolePerm ({role}, {perm})'
                for role, perm in role_perms_to_remove
            ))
    else:
        for role in new_roles:
            click.echo(f'INSERT new Role {role}')
            db.session.add(role)
        db.session.flush()

        for role, perm in new_role_perms:
            f'INSERT new RolePerm ({role}, {perm})'
            role.permissions.append(perm)
        db.session.flush()

        for role, perm in role_perms_to_remove:
            click.echo(f'DELETE RolePerm ({role}, {perm})')
            role.permissions.remove(perm)
        db.session.flush()


def _sync_data(dry_run=False):
    perms = permissions.generate_permissions()
    rti_roles = permissions.generate_rti_roles()
    base_roles = permissions.generate_base_roles()

    # Upsert RTI Client
    rti_client = _upsert_rti_client(dry_run)

    # Upsert Permissions
    permissions_in_db = _upsert_permissions(perms, dry_run)

    # Upsert RTI Roles
    _upsert_roles(rti_client.id or 1, permissions_in_db, rti_roles, dry_run)

    # Upsert User Roles
    _upsert_roles(None, permissions_in_db, base_roles, dry_run)

    if not dry_run:
        db.session.commit()


@click.command()
@click.option('--dry-run', is_flag=True, default=False,
              help='Show what changes would be made')
def sync_data(dry_run):
    return _sync_data(dry_run=dry_run)

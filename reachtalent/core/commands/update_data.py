from pathlib import Path
import uuid

import click
from sqlalchemy import select, update
import yaml

from ...extensions import db
from .. import models


LARGE_INT = 1000000


def _obj_diff(obj, data: dict[str,str]) -> object | None:
    changed = False
    for field, value in data.items():
        if getattr(obj, field, None) != value:
            changed = True
            setattr(obj, field, value)
    if changed:
        return obj
    return None


def _migrate_category_id(category, new_id):
    old_id = category.id

    # Clone the existing category with the new id
    temp_category = models.Category(
        id=new_id,
        key=category.key,
        label=category.label,
        description=category.description,
    )

    # Update the 'key' field so it doesn't conflict
    category.key = category.key + str(uuid.uuid4())
    db.session.add(category)
    db.session.flush()

    db.session.add(temp_category)
    db.session.flush()

    # Update the CategoryItems to the new ID
    db.session.execute(
        update(models.CategoryItem).
        where(models.CategoryItem.category_id == old_id).
        values(category_id=new_id)
    )
    db.session.delete(category)
    db.session.flush()

    # Return the new migrated category
    return temp_category


def _upsert_categorical_data(key: str, data: dict[str, str|int|dict], force_update: bool = False):
    category = None
    inserts, updates = 0, 0
    _id: int = data['category_id']
    category_data = {
        'label': data.get('label', key.title().replace('_', ' ')),
        'description': data.get('description'),
    }

    category_by_key = db.session.execute(select(models.Category).filter_by(key=key)).scalar_one_or_none()
    category_by_id = db.session.execute(select(models.Category).filter_by(id=_id)).scalar_one_or_none()

    items_in_db = {
        obj.key: obj
        for obj in db.session.execute(
            select(models.CategoryItem).
            join(models.Category).
            filter(models.Category.key == key)).scalars()
    }

    if category_by_id and category_by_id.key != key:
        if not force_update:
            raise click.ClickException(f"Unable to insert Category(id={_id}, key={key}) found id conflict in db.")
        _migrate_category_id(category_by_id, LARGE_INT + _id)
    if category_by_key and category_by_key.id == _id:
        category = category_by_key
    elif category_by_key is not None and category_by_key.id != _id:
        if not force_update:
            raise click.ClickException(f"Unable to insert Category(id={_id}, key={key}) found id conflict in db.")
        category = _migrate_category_id(category_by_key, _id)
    else:
        inserts += 1
        category = models.Category(
            id=_id,
            key=key,
            label=category_data['label'],
            description=category_data['description'])
        db.session.add(category)

    if _obj_diff(category, category_data):
        updates += 1
        db.session.add(category)

    for item_key, item_data in data.get('items', {}).items():
        existing = items_in_db.get(item_key)
        if not existing:
            inserts += 1
            obj = models.CategoryItem(key=item_key, category=category, **item_data)
            click.echo(f'INSERT new CategoryItem(category={category.key}, '
                       f'key={obj.key}, label={obj.label}, '
                       f'description={obj.description})')
            db.session.add(obj)
        elif updated_obj := _obj_diff(existing, item_data):
            updates += 1
            click.echo(f'UPDATE CategoryItem(category={category.key}, '
                       f'key={existing.key}) with {item_data}')
            db.session.add(updated_obj)
    return inserts, updates


def _upsert_model_data(model, data) -> (int, int):
    inserts, updates = 0, 0
    model_name = data['model']
    key_field = data['key_field']
    items_in_db = {
        getattr(obj, key_field): obj
        for obj in db.session.execute(select(model)).scalars()
    }

    for item_key, item_data in data.get('items', {}).items():
        existing = items_in_db.get(item_key)
        fields = ', '.join(f'{k}={v}' for k, v in item_data.items())
        if not existing:
            inserts += 1
            obj = model(**{**item_data, **{key_field: item_key}})
            click.echo(f'INSERT new {model_name}('
                       f'{key_field}={item_key}, {fields})')
            db.session.add(obj)
        elif updated_obj := _obj_diff(existing, item_data):
            updates += 1
            click.echo(f'UPDATE {model_name}({key_field}={item_key}) with {fields}')
            db.session.add(updated_obj)

    return inserts, updates


def _get_yaml_data() -> dict[str,dict]:
    category_data_dir = Path(__file__).parent.parent / "categorical_data"
    yaml_data = {}
    for yaml_path in category_data_dir.glob("*.yaml"):
        yaml_data[yaml_path.name] = yaml.safe_load(yaml_path.open('r'))
    return yaml_data


def _update_category_data(force_update: bool, dry_run: bool):
    category_data = {}
    for yaml_path, data in sorted(_get_yaml_data().items()):
        if data.get('model'):
            _model = getattr(models, data.get('model'))
            _ins, _upd = _upsert_model_data(_model, data)
            click.echo(f"model {data.get('model')}: {_ins} inserts, {_upd} updates")
        else:
            _key = yaml_path.rsplit('.')[0]
            if (_id := data.get('category_id')) is None:
                raise click.ClickException(f"{yaml_path} missing 'category_id'")
            if _id in category_data:
                category_a = _key
                category_b = category_data[_id]['key']
                raise click.ClickException(
                    f"Category Conflict: category_id {_id} found for both {category_a} and {category_b}")
            category_data[_id] = {
                'key': _key,
                'data': data,
            }

    for _id, params in sorted(category_data.items()):
        _ins, _upd = _upsert_categorical_data(force_update=force_update, **params)
        click.echo(f"category {params['key']}: {_ins} inserts, {_upd} updates")

    if not dry_run:
        db.session.commit()


@click.command('update-data')
@click.option('--force-update', is_flag=True, default=False)
@click.option('--dry-run', '-x', is_flag=True, default=False,
              help='Show what changes would be made')
def update_data_cmd(force_update: bool, dry_run: bool):
    if force_update and dry_run:
        raise click.ClickException("--dry-run and --force-update flags cannot be used together")
    try:
        return _update_category_data(force_update, dry_run)
    except Exception as exc:
        raise
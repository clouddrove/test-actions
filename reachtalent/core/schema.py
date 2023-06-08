from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum, auto
from typing import Any

import simplejson
from flask import g
from marshmallow import (
    fields, validate, validates, validates_schema, ValidationError,
    pre_load, pre_dump
)
from sqlalchemy import select
from sqlalchemy.orm.exc import NoResultFound

from . import models
from ..auth.utils import has_permission
from ..extensions import db
from ..extensions import marshmallow as ma


def _current_user_id():
    return g.auth_state.user.id


def _default_client_id():
    if has_permission('Client.*.manage'):
        return None
    return g.auth_state.client.id


def validate_client_id(value):
    if has_permission('Client.*.manage'):
        if value is None:
            raise ValidationError("Missing data for required field.")
    else:
        if value is None:
            value = g.auth_state.client.id
        elif value != g.auth_state.client.id:
            raise ValidationError("Invalid client.")

    return value


class Pagination(ma.Schema):
    page = fields.Integer(load_default=1)
    total_pages = fields.Integer()
    page_size = fields.Integer(load_default=25)


class ClientFilter(ma.Schema):
    client_id = fields.Integer(
        load_default=_default_client_id,
        validate=validate_client_id)


class PaginationClientFilter(Pagination, ClientFilter):
    pass


class AvailableWorkersFilter(Pagination, ClientFilter):
    for_requisition_id = fields.Integer()


class RequisitionFilter(ma.Schema):
    requisition_id = fields.Integer()


class WorkerFilter(ma.Schema):
    worker_id = fields.Integer()


class PaginationClientWorkerRequisitionFilter(Pagination, ClientFilter, RequisitionFilter, WorkerFilter):
    pass


def _today():
    return datetime.utcnow().date()


class Category(ma.Schema):
    id = fields.Integer()
    key = fields.String()
    label = fields.String()
    description = fields.String()


class ListCategoryResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(Category()))


class CategoryItemPaginatedFilter(Pagination):
    category_id = fields.Integer()
    category_key = fields.String()


class CategoryItem(ma.Schema):
    id = fields.Integer()
    category_id = fields.Integer()
    key = fields.String()
    label = fields.String()
    description = fields.String()


class ListCategoryItemResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(CategoryItem()))


class ContractTermsQuery(ClientFilter):
    effective_date = fields.Date(load_default=_today)
    term_prefix = fields.String()


class Department(ma.Schema):
    id = fields.Integer(dump_only=True)
    client_id = fields.Integer(
        load_default=_default_client_id,
        validate=validate_client_id)
    number = fields.String()
    name = fields.String(required=True)

    # owner = fields.Nested(ClientUser(), dump_only=True)
    # accounting_approver = fields.Nested(ClientUser(), dump_only=True)

    @validates_schema
    def validate_schema(self, data, **kwargs):
        client_id = data.get('client_id')
        number = data.get('number')
        name = data.get('name')

        dept_names = set()
        dept_numbers = set()
        client_departments = select(models.Department).filter_by(client_id=client_id)
        for dept in db.session.execute(client_departments).scalars():
            dept_names.add(dept.name)
            if dept.number:
                dept_numbers.add(dept.number)
        errors = {}
        if name in dept_names:
            errors['name'] = ['Department name must be unique.']
        if number and number in dept_numbers:
            errors['number'] = ['Department number must be unique.']
        if errors:
            raise ValidationError(errors)
        return data


class ListDepartmentResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(Department()))


class CostCenter(ma.Schema):
    id = fields.Integer(dump_only=True)
    client_id = fields.Integer(
        load_default=_default_client_id,
        validate=validate_client_id)
    name = fields.String(required=True)
    description = fields.String()


class ListCostCenterResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(CostCenter()))


class Role(ma.Schema):
    name = fields.String()


class User(ma.Schema):
    id = fields.Integer()
    name = fields.String()
    email = fields.String()


class Staff(ma.Schema):
    id = fields.Integer(dump_only=True)

    phone_number = fields.String()
    title = fields.String()

    role = fields.Nested(Role(), dump_only=True)
    user = fields.Nested(User(), dump_only=True)

    # cost_center = fields.Nested(CostCenter(), dump_only=True)
    # departments = fields.List(fields.Nested(Department()), dump_only=True)
    # reports_to = fields.Nested("Staff")


class ListStaffResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(Staff()))


def _validate_department_ids(client_id: int, department_ids: list[int]) -> list["models.Department"]:
    departments_by_id = {
        d.id: d
        for d in models.Department.query.filter_by(client_id=client_id).all()
    }
    invalid_departments = []
    departments = []
    for d_id in department_ids:
        if d_id not in departments_by_id:
            invalid_departments.append(d_id)
        else:
            departments.append(departments_by_id[d_id])
    if invalid_departments:
        raise ValidationError({'department_ids': ['Invalid department.']})
    return departments


class PurchaseOrder(ma.Schema):
    id = fields.Integer(dump_only=True)
    client_id = fields.Integer(
        load_default=_default_client_id,
        validate=validate_client_id)
    ext_ref = fields.String(required=True)
    department_ids = fields.List(fields.Integer(), load_only=True)
    departments = fields.List(
        fields.Nested(Department()), dump_only=True)

    @validates_schema
    def validate_department_ids(self, data, **kwargs):
        client_id = data.get('client_id', g.auth_state.client.id)
        data['departments'] = _validate_department_ids(client_id, data.pop('department_ids', []))
        return data


class ListPurchaseOrderResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(PurchaseOrder()))


class JobClassification(ma.Schema):
    id = fields.Integer(dump_only=True)
    label = fields.String()


class ListJobClassificationResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(JobClassification()))


class WorkerEnvironment(ma.Schema):
    id = fields.Integer(dump_only=True)

    client_id = fields.Integer(
        load_default=_default_client_id,
        validate=validate_client_id)

    name = fields.String(required=True)
    description = fields.String(required=True)


class Position(ma.Schema):
    class Meta:
        render_module = simplejson

    id = fields.Integer(dump_only=True)

    client_id = fields.Integer(
        load_default=_default_client_id,
        validate=validate_client_id)

    department_ids = fields.List(fields.Integer(), load_only=True, required=True)
    worker_environment_id = fields.Integer(load_only=True, required=True)
    job_classification_id = fields.Integer(load_only=True, required=True)

    title = fields.String(required=True)
    job_description = fields.String(required=True)
    requirements = fields.List(fields.String())
    pay_rate_min = fields.Decimal(places=2)
    pay_rate_max = fields.Decimal(places=2)
    is_remote = fields.Boolean(load_default=False)

    departments = fields.List(
        fields.Nested(Department()), dump_only=True)
    worker_environment = fields.Nested(WorkerEnvironment(), dump_only=True)
    job_classification = fields.Nested(JobClassification(), dump_only=True)

    @validates_schema
    def validate_ids(self, data, **kwargs):
        errors = {}

        client_id = data.get('client_id')
        department_ids = data.pop('department_ids', [])
        worker_environment_id = data.get('worker_environment_id')
        job_classification_id = data.get('job_classification_id')

        if not client_id:
            errors['client_id'] = ['Missing data for required field.']
        if not department_ids:
            errors['department_ids'] = ['Missing data for required field.']
        if not worker_environment_id:
            errors['worker_environment_id'] = ['Missing data for required field.']
        if not job_classification_id:
            errors['job_classification_id'] = ['Missing data for required field.']

        # Require all values before validation relations
        if errors:
            raise ValidationError(errors)

        data['departments'] = _validate_department_ids(client_id, department_ids)

        try:
            worker_environment = models.WorkerEnvironment.query. \
                filter_by(id=worker_environment_id, client_id=client_id).one()
        except Exception as exc:
            errors['worker_environment_id'] = ['Invalid worker_environment.']

        try:
            job_classification = db.session.execute(
                models.JobClassification.
                contracted_job_class_query(client_id).
                filter_by(id=job_classification_id)
            ).one()
        except Exception as exc:
            errors['job_classification_id'] = ['Invalid job_classification.']

        if errors:
            raise ValidationError(errors)

        return data


class ListPositionResponse(ma.Schema):
    class Meta:
        render_module = simplejson

    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(Position()))


class RequisitionType(ma.Schema):
    id = fields.Integer()
    key = fields.String(data_key='name')
    label = fields.String(data_key='display_name')


class ListRequisitionTypeResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(RequisitionType()))


class Schedule(ma.Schema):
    id = fields.Integer(dump_only=True)

    client_id = fields.Integer(
        load_default=_default_client_id,
        validate=validate_client_id)

    name = fields.String(required=True)
    description = fields.String(required=True)


class ListScheduleResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(Schedule()))


class Worker(ma.Schema):
    id = fields.Integer(dump_only=True)
    phone_number = fields.String()
    user = fields.Nested(User())


class ListWorkerResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(Worker()))


class ListWorkerEnvironmentResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(WorkerEnvironment()))


class Location(ma.Schema):
    id = fields.Integer(dump_only=True)

    client_id = fields.Integer(
        load_default=_default_client_id,
        validate=validate_client_id)

    name = fields.String(required=True)
    description = fields.String(required=True)
    street = fields.String(required=True)
    city = fields.String(required=True)
    state = fields.String(required=True)
    zip = fields.String(required=True)
    country = fields.String(required=True)


class ListLocationResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(Location()))


class PayScheme(ma.Schema):
    id = fields.Integer(dump_only=True)
    key = fields.String(data_key='name')
    label = fields.String(data_key='display_name')


class ListPaySchemeResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(PayScheme()))


def _default_self_user_id():
    if has_permission('Client.*.manage'):
        return None
    return g.auth_state.user.id


@dataclass
class Rel:
    model: Any
    column: str = 'id'
    value: Any = None
    required: bool = True  # should be determined from schema
    universal: bool = False  # should use client_id in lookup
    category: str | None = None


class Approval(ma.Schema):
    approver_uid = fields.Integer(dump_only=True, load_default=_current_user_id)
    datetime = fields.DateTime(dump_only=True, load_default=lambda x: datetime.utcnow())

    decision = fields.Enum(models.ApprovalDecision, required=True)
    reason = fields.String(required=False)

    @validates_schema
    def require_reason_upon_reject(self, data, **kwargs):
        if data.get('decision') == models.ApprovalDecision.REJECT:
            if not data.get('reason', '').strip():
                raise ValidationError({'reason': 'Reason is required upon rejection.'})

    @pre_dump
    def pre_dump(self, data, **kwargs):
        _decision = data.get('decision')
        _datetime = data.get('datetime')
        if isinstance(_decision, str) and not isinstance(_decision, models.ApprovalDecision):
            data['decision'] = getattr(models.ApprovalDecision, _decision)

        if isinstance(_datetime, str):
            data['datetime'] = datetime.fromisoformat(_datetime)
        return data


class Assignment(ma.Schema):
    id = fields.Integer(dump_only=True)
    status = fields.Enum(models.AssignmentState, dump_only=True)
    requisition_id = fields.Integer(dump_only=True)
    replaced_by_assignment_id = fields.Integer(dump_only=True)
    bill_rate = fields.Decimal(dump_only=True)

    # Inputs
    cost_center_id = fields.Integer(load_only=True)
    worker_id = fields.Integer(load_only=True)
    department_id = fields.Integer(load_only=True, required=True)
    pay_rate = fields.Decimal()
    tentative_start_date = fields.Date(required=True)
    actual_start_date = fields.Date()
    system_start_date = fields.Date()
    tentative_end_date = fields.Date()
    actual_end_date = fields.Date()
    end_notes = fields.String()
    cancel_notes = fields.String()
    timesheets_worker_editable = fields.Boolean()
    timesheets_web_punchable = fields.Boolean()
    end_reason_id = fields.Integer(load_only=True)

    # Relationship Outputs
    end_reason = fields.String(dump_only=True)  # Pluck?
    department = fields.Nested(Department(), dump_only=True)
    worker = fields.Nested(Worker(), dump_only=True)
    cost_center = fields.Nested(CostCenter(), dump_only=True)
    ended_by_user = fields.Nested(User(), dump_only=True)
    canceled_by_user = fields.Nested(User(), dump_only=True)

    def __init__(self, instance: models.Assignment=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance

    class Meta:
        render_module = simplejson
        ordered = True

    @validates_schema
    def validate_schema(self, data, **kwargs):
        relationships = {
            'cost_center_id': Rel(model=models.CostCenter, required=False),
            'department_id': Rel(model=models.Department, required=False),
            'end_reason_id': Rel(model=models.CategoryItem, universal=True, category='assignment_end_reason', required=False),
        }

        errors = {}

        for key, rel in relationships.items():
            if val := data.get(key):
                rel.value = val
            elif rel.required:
                errors[key] = ['Missing data for required field.']
        if errors:
            raise ValidationError(errors)

        for key, rel in relationships.items():
            # Skip lookup if value is not supplied and relationship is not required
            if rel.value is None and not rel.required:
                continue

            try:
                params = {rel.column: rel.value}
                if not rel.universal:
                    params['client_id'] = self.instance.requisition.client_id
                if rel.category:
                    item = db.session.execute(select(models.CategoryItem).join(models.Category).filter(
                        models.Category.key == rel.category,
                        models.CategoryItem.id == rel.value
                    )).scalar_one_or_none()
                    if item is None:
                        errors[key] = [f'Invalid {key}.']
                else:
                    _ = rel.model.query.filter_by(**params).one()
            except NoResultFound:
                errors[key] = [f'Invalid {key}.']

        # Manual validate worker_id
        worker_id = data.get('worker_id')
        if self.instance.worker_id == worker_id:
            pass  # either both None or both same id
        elif self.instance.worker_id and worker_id:
            errors.setdefault('worker_id', []).append('Assignment worker_id may not be changed once set.')
        else:
            try:
                db.session.execute(
                    models.Worker.available_workers_query(
                        self.instance.requisition.client_id,
                        for_requisition_id=self.instance.requisition_id).
                    filter(models.Worker.id == worker_id)).one()
            except NoResultFound:
                errors.setdefault('worker_id', []).append('Invalid worker_id.')

        if errors:
            raise ValidationError(errors)

        return data


class Requisition(ma.Schema):
    id = fields.Integer(dump_only=True)

    # Relationship Inputs
    client_id = fields.Integer(
        load_default=_default_client_id,
        validate=validate_client_id)

    purchase_order_id = fields.Integer(load_only=True, allow_none=True)
    position_id = fields.Integer(load_only=True, required=True)
    department_id = fields.Integer(load_only=True, required=True)
    supervisor_user_id = fields.Integer(load_only=True, load_default=_default_self_user_id)
    timecard_approver_user_id = fields.Integer(load_only=True, load_default=_default_self_user_id)
    location_id = fields.Integer(load_only=True, required=True)
    requisition_type_id = fields.Integer(load_only=True, required=True)
    pay_scheme_id = fields.Integer(load_only=True, required=True)
    schedule_id = fields.Integer(load_only=True, required=True)
    present_worker_ids = fields.List(fields.Integer(), load_only=True)

    approval_state = fields.Enum(models.ApprovalState, dump_only=True)
    approvals = fields.List(fields.Nested(Approval()), dump_only=True)

    num_assignments = fields.Integer(required=True)
    pay_rate = fields.Decimal(required=True)
    start_date = fields.Date(required=True)
    estimated_end_date = fields.Date(required=True)
    additional_information = fields.String()
    employee_info = fields.Dict()

    # Relationship Outputs
    purchase_order = fields.Nested(PurchaseOrder(), dump_only=True)
    position = fields.Nested(Position(), dump_only=True)
    department = fields.Nested(Department(), dump_only=True)
    supervisor = fields.Nested(User(), dump_only=True)
    timecard_approver = fields.Nested(User(), dump_only=True)
    location = fields.Nested(Location(), dump_only=True)
    requisition_type = fields.Nested(RequisitionType(), dump_only=True)
    pay_scheme = fields.Nested(PayScheme(), dump_only=True)
    schedule = fields.Nested(Schedule(), dump_only=True)
    presented_workers = fields.List(fields.Nested(Worker()), dump_only=True)
    assignments = fields.List(fields.Nested(Assignment()), dump_only=True)

    class Meta:
        render_module = simplejson
        ordered = True

    @pre_load
    def pre_load(self, data, *args, **kwargs):
        d2 = {
            key: value for key, value in data.items()
            if value is not None
        }
        return d2

    @validates_schema
    def validate_relationships(self, data, **kwargs):
        # TODO: Generic-ize relationship validation
        relationships = {
            'client_id': Rel(model=models.Client, universal=True),
            'purchase_order_id': Rel(model=models.PurchaseOrder, required=False),
            'position_id': Rel(model=models.Position),
            'department_id': Rel(model=models.Department),
            'supervisor_user_id': Rel(model=models.ClientUser, column='user_id'),
            'timecard_approver_user_id': Rel(model=models.ClientUser, column='user_id'),
            'location_id': Rel(model=models.Location),
            'requisition_type_id': Rel(model=models.CategoryItem, universal=True, category='requisition_type'),
            'pay_scheme_id': Rel(model=models.CategoryItem, universal=True, category='pay_scheme'),
            'schedule_id': Rel(model=models.Schedule),
        }

        errors = {}

        for key, rel in relationships.items():
            if val := data.get(key):
                rel.value = val
            elif rel.required:
                errors[key] = ['Missing data for required field.']
        if errors:
            raise ValidationError(errors)

        for key, rel in relationships.items():
            # Skip lookup if value is not supplied and relationship is not required
            if rel.value is None and not rel.required:
                continue

            try:
                params = {rel.column: rel.value}
                if not rel.universal:
                    params['client_id'] = relationships['client_id'].value
                if rel.category:
                    item = db.session.execute(select(models.CategoryItem).join(models.Category).filter(
                        models.Category.key == rel.category,
                        models.CategoryItem.id == rel.value
                    )).scalar_one_or_none()
                    if item is None:
                        errors[key] = [f'Invalid {key}.']
                else:
                    _ = rel.model.query.filter_by(**params).one()
            except NoResultFound as exc:
                errors[key] = [f'Invalid {key}.']

        # Manually Validate present_worker_ids
        present_worker_ids = data.pop('present_worker_ids', [])
        if present_worker_ids:
            present_workers = db.session.execute(
                models.Worker.available_workers_query(data['client_id']).
                filter(models.Worker.id.in_(present_worker_ids))
            ).scalars().all()
            if len(present_workers) != len(present_worker_ids):
                errors['present_worker_ids'] = ['Invalid worker_id.']
            else:
                data['presented_workers'] = present_workers

        if errors:
            raise ValidationError(errors)

        return data


class ListRequisitionResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(Requisition()))

    class Meta:
        render_module = simplejson
        ordered = True


class ReplaceAssignmentRequest(ma.Schema):
    replaces_assignment_id = fields.Integer(required=True)
    cost_center_id = fields.Integer(required=False)
    worker_id = fields.Integer(required=True)
    department_id = fields.Integer(required=False)
    pay_rate = fields.Decimal(required=False)
    tentative_start_date = fields.Date(required=True)
    actual_start_date = fields.Date()
    system_start_date = fields.Date()
    tentative_end_date = fields.Date()
    actual_end_date = fields.Date()
    timesheets_worker_editable = fields.Boolean()
    timesheets_web_punchable = fields.Boolean()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.replaced_assignment: models.Assignment | None = None

    @validates("replaces_assignment_id")
    def validate_replaces_assignment_id(self, replaces_assignment_id):
        try:
            replaced_assignment: models.Assignment = db.session.get(models.Assignment, replaces_assignment_id)
            if not (
                    has_permission('Assignment.*.manage') or
                    replaced_assignment.requisition.client_id == g.auth_state.client.id):
                raise ValidationError('Invalid replaces_assignment_id.')
            if replaced_assignment.status not in (models.AssignmentState.CANCELED, models.AssignmentState.ENDED):
                raise ValidationError('Replaced assignment must be canceled or ended.')
            if replaced_assignment.replaced_by_assignment_id:
                raise ValidationError('Replaced assignment must not be previously replaced.')
        except NoResultFound:
            raise ValidationError('Invalid replaces_assignment_id.')
        self.replaced_assignment = replaced_assignment

    @validates_schema
    def validate_schema(self, data, *args, **kwargs):
        if data.pop('replaces_assignment_id', None):
            data['replaced_assignment'] = self.replaced_assignment

        data['requisition'] = self.replaced_assignment.requisition

        # Fill defaults from replaced assignment:
        if not data.get('pay_rate'):
            data['pay_rate'] = self.replaced_assignment.pay_rate

        if not data.get('bill_rate'):
            bill_rate = self.replaced_assignment.bill_rate
            if not bill_rate or not models.equivalent(data['pay_rate'], self.replaced_assignment.pay_rate):
                bill_rate = self.replaced_assignment.requisition.position.calculate_bill_rate(data.get('pay_rate'))
            data['bill_rate'] = bill_rate

        if not data.get('department_id'):
            data['department_id'] = self.replaced_assignment.department_id

        # Validate Relationship values
        relationships = {
            'cost_center_id': Rel(model=models.CostCenter, required=False),
            'department_id': Rel(model=models.Department, required=False),
        }

        errors = {}

        for key, rel in relationships.items():
            if val := data.get(key):
                rel.value = val
            elif rel.required:
                errors[key] = ['Missing data for required field.']
        if errors:
            raise ValidationError(errors)

        client_id = self.replaced_assignment.requisition.client_id
        for key, rel in relationships.items():
            # Skip lookup if value is not supplied and relationship is not required
            if rel.value is None and not rel.required:
                continue

            try:
                params = {rel.column: rel.value}
                if not rel.universal:
                    params['client_id'] = client_id

                if rel.category:
                    item = db.session.execute(select(models.CategoryItem).join(models.Category).filter(
                        models.Category.key == rel.category,
                        models.CategoryItem.id == rel.value
                    )).scalar_one_or_none()
                    if item is None:
                        errors[key] = [f'Invalid {key}.']
                else:
                    _ = rel.model.query.filter_by(**params).one()
            except NoResultFound:
                errors[key] = [f'Invalid {key}.']

        # Manual validate worker_id
        if worker_id := data.get('worker_id'):
            try:
                db.session.execute(
                    models.Worker.available_workers_query(
                        client_id,
                        for_requisition_id=self.replaced_assignment.requisition_id).
                    filter(models.Worker.id == worker_id)).one()
            except NoResultFound:
                errors.setdefault('worker_id', []).append('Invalid worker_id.')

        if errors:
            raise ValidationError(errors)

        # TODO: Establish proper initial state of assignment when replacing
        data['status'] = 'ACTIVE'

        return data


class DeleteAssignmentType(StrEnum):
    END = auto()
    CANCEL = auto()


class DeleteAssignmentRequest(ma.Schema):
    delete_type = fields.Enum(DeleteAssignmentType, required=True)
    end_reason = fields.String(validate=validate.OneOf(["voluntary", "involuntary", "completed"]))
    end_date = fields.Date(load_default=_today)
    notes = fields.String()

    @validates_schema
    def validates_schema(self, data, *args, **kwargs):
        errors = {}
        if data['delete_type'] == DeleteAssignmentType.END:
            end_reason_str = data.get('end_reason')
            if not end_reason_str:
                errors['end_reason'] = ['Missing data for required field.']
                raise ValidationError(errors)
            end_reason_category = db.session.execute(select(models.Category).filter_by(key='assignment_end_reason')).scalar_one()
            end_reasons = {
                ci.key: ci for ci in end_reason_category.items
            }
            data['end_reason'] = end_reasons[end_reason_str]


class ListAssignmentResponse(ma.Schema):
    pagination = fields.Nested(Pagination())
    items = fields.List(fields.Nested(Assignment()))

    class Meta:
        render_module = simplejson
        ordered = True


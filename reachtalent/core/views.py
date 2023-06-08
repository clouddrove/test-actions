from datetime import datetime
import typing

from flask import Blueprint, Response, abort, g, request
from marshmallow import ValidationError
import simplejson
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from webargs.flaskparser import parser, use_args

from . import commands
from . import schema
from .models import (
    Assignment, AssignmentState, ApprovalDecision, ApprovalState, Category,
    CategoryItem, ClientUser, Contract, CostCenter, Department,
    JobClassification, Position, PurchaseOrder, Requisition, Schedule, States,
    Worker, WorkerEnvironment, Location
)
from ..auth.models import User
from ..auth.utils import authenticated, requires, has_permission
from ..extensions import db
from ..database import Base
from ..logger import make_logger

blueprint = Blueprint("core", __name__)

logger = make_logger('reachtalent.core')

RESOURCE_NOT_FOUND = "Resource not found."


@parser.error_handler
def handle_request_parsing_error(err, req, schema, *, error_status_code, error_headers):
    # Unwrap location from use_args error handler
    if 'json' in err.messages:
        err.messages = err.messages['json']
    elif 'querystring' in err.messages:
        err.messages = err.messages['querystring']
    abort(400, err)


def validate_inject_client_id(data: dict, entity: str):
    # TODO: Move this into marshmallow schema
    client_id = data.get('client_id')

    # enforce client_id permissions
    if has_permission(f'{entity}.*.manage'):
        if client_id is None:
            abort(400, ValidationError("Missing data for required field.", "client_id"))
    else:
        if client_id is not None and client_id != g.auth_state.client.id:
            abort(400, ValidationError("Invalid client.", "client_id"))

    data.setdefault('client_id', g.auth_state.client.id)


def add_audit_fields(data: dict, user: User):
    # TODO: Find more elegant way to do this.
    data['created_uid'] = user.id
    data['modified_uid'] = user.id


def prepare_for_save(model: type, data: dict, user: User):
    validate_inject_client_id(data, model.__name__)
    add_audit_fields(data, user)
    return model(**data)


def get_obj(model: typing.Type[Base], id: int):
    query = model.query.filter_by(id=id)

    if hasattr(model, 'state'):
        query = query.filter(model.state != States.DELETED)

    if not has_permission('Client.*.manage'):
        query = model.filter_by_client(query, g.auth_state.client.id)

    return query.one_or_404(RESOURCE_NOT_FOUND)


@blueprint.get('/categories')
@authenticated
@requires("Category.*.view")
@use_args(schema.Pagination(), location='querystring')
def list_categories(user: User, params: dict):
    """ List Categories
    ---
    get:
      operationId: listCategories
      tags:
        - category
      summary: List Categories
      description: List Categories
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListCategoryResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    # Replace RequisitionType with Category
    query = select(Category).order_by(Category.id)
    paginated = db.paginate(
        query,
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListCategoryResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.get('/category_items')
@authenticated
@requires("CategoryItem.*.view")
@use_args(schema.CategoryItemPaginatedFilter(), location='querystring')
def list_category_items(user: User, params: dict):
    """ List CategoryItems
    ---
    get:
      operationId: listCategoryItems
      tags:
        - category
      summary: List CategoryItems
      description: List CategoryItems
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
        - in: query
          name: category_id
          required: false
          schema:
            type: integer
        - in: query
          name: category_key
          required: false
          schema:
            type: string
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListCategoryItemResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    # Replace RequisitionType with Category
    query = select(CategoryItem)

    if params.get('category_id'):
        query = query.filter(CategoryItem.category_id == params['category_id'])
    if params.get('category_key'):
        query = query.join(Category, Category.id == CategoryItem.category_id)
        query = query.filter(Category.key == params.get('category_key'))

    query = query.order_by(CategoryItem.id)
    paginated = db.paginate(
        query,
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListCategoryItemResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.post('/departments')
@authenticated
@requires("Department.*.create")
@use_args(schema.Department(), location='json')
def create_department(user: User, data: dict):
    """Create a new Department
    ---
    post:
      operationId: createDepartment
      tags:
        - department
      summary: Create a new Department
      description: Create a new Department
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema: Department
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: Department
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    department = prepare_for_save(Department, data, user)

    resp_json = ''
    try:
        db.session.add(department)
        db.session.commit()
        resp_json = schema.Department().dumps(department)
    except IntegrityError as exc:
        logger.warning("Integrity error inserting department: %s %s", data, exc)
        abort(400, ValidationError("Department name must be unique.", "name"))

    return Response(resp_json, content_type='application/json')


@blueprint.get('/departments')
@authenticated
@requires("Department.*.view")
@use_args(schema.PaginationClientFilter(), location='querystring')
def list_departments(user: User, params: dict):
    """ List Departments
    ---
    get:
      operationId: listDepartments
      tags:
        - department
      summary: List Departments
      description: List Departments
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
        - in: query
          name: client_id
          required: false
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListDepartmentResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    query = select(Department).order_by('id')
    if params['client_id'] is not None:
        query = query.filter_by(client_id=params['client_id'])
    paginated = db.paginate(
        query,
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListDepartmentResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.post('/cost_centers')
@authenticated
@requires("CostCenter.*.create")
@use_args(schema.CostCenter(), location='json')
def create_cost_center(user: User, data: dict):
    """Create a new Cost Center
    ---
    post:
      operationId: createCostCenter
      tags:
        - cost_center
      summary: Create a new CostCenter
      description: Create a new CostCenter
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema: CostCenter
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: CostCenter
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    cost_center = prepare_for_save(CostCenter, data, user)

    resp_json = ''
    try:
        db.session.add(cost_center)
        db.session.commit()
        resp_json = schema.CostCenter().dumps(cost_center)
    except IntegrityError as exc:
        logger.warning("Integrity error inserting cost_center: %s %s", data, exc)
        abort(400, ValidationError("CostCenter name must be unique.", "name"))

    return Response(resp_json, content_type='application/json')


@blueprint.get('/cost_centers')
@authenticated
@requires("CostCenter.*.view")
@use_args(schema.PaginationClientFilter(), location='querystring')
def list_cost_centers(user: User, params: dict):
    """ List Cost Centers
    ---
    get:
      operationId: listCostCenters
      tags:
        - cost_center
      summary: List Cost Centers
      description: List Cost Centers
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
        - in: query
          name: client_id
          required: false
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListCostCenterResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    query = select(CostCenter).order_by('id')
    if params['client_id'] is not None:
        query = query.filter_by(client_id=params['client_id'])
    paginated = db.paginate(
        query,
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListCostCenterResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.get('/staff')
@authenticated
@requires("Staff.*.view")
@use_args(schema.PaginationClientFilter(), location='querystring')
def list_client_user(user: User, params: dict):
    """ List Client Staff
    ---
    get:
      operationId: listClientStaff
      tags:
        - staff
      summary: List Client Staff
      description: List Client Staff
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
        - in: query
          name: client_id
          required: false
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListStaffResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    query = select(ClientUser).order_by('user_id')
    if params['client_id'] is not None:
        query = query.filter_by(client_id=params['client_id'])
    paginated = db.paginate(
        query,
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListStaffResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.post('/purchase_orders')
@authenticated
@requires("PurchaseOrder.*.create")
@use_args(schema.PurchaseOrder(), location='json')
def create_purchase_order(user: User, data: dict):
    """Create a new PurchaseOrder
    ---
    post:
      operationId: createPurchaseOrder
      tags:
        - purchase_order
      summary: Create a new PurchaseOrder
      description: Create a new PurchaseOrder
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema: PurchaseOrder
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: PurchaseOrder
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    purchase_order = prepare_for_save(PurchaseOrder, data, user)
    try:
        db.session.add(purchase_order)
        db.session.commit()
        resp_json = schema.PurchaseOrder().dumps(purchase_order),
    except Exception as exc:
        logger.warning("Unexpected error: %s %s", data, exc)
        raise
    return Response(
        resp_json,
        content_type='application/json',
    )


@blueprint.get('/purchase_orders')
@authenticated
@requires("PurchaseOrder.*.view")
@use_args(schema.PaginationClientFilter(), location='querystring')
def list_purchase_orders(user: User, params: dict):
    """List Departments
    ---
    get:
      operationId: listPurchaseOrders
      tags:
        - purchase_order
      summary: List PurchaseOrders
      description: List PurchaseOrders
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
        - in: query
          name: client_id
          required: false
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListPurchaseOrderResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    query = select(PurchaseOrder).order_by('id')
    if params['client_id'] is not None:
        query = query.filter_by(client_id=params['client_id'])
    paginated = db.paginate(query,
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListPurchaseOrderResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.get('/contract_terms')
@authenticated
@requires("ContractTerm.*.view")
@use_args(schema.ContractTermsQuery(), location='querystring')
def query_contract_terms(user: User, params: dict):
    """Query Contract Terms
    ---
    get:
      operationId: queryContractTerms
      tags:
        - contract_terms
      summary: Query Contract Terms
      description: Get a map of effective contract terms for the given client_id and default to today.
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: client_id
          required: false
          schema:
            type: integer
        - in: query
          name: effective_date
          required: false
          schema:
            type: string
            format: date
            example: "2021-01-30"
        - in: query
          name: term_prefix
          required: false
          schema:
            type: string
            example: "markup_jobclass_"
      responses:
        200:
          description: Success
          content:
            application/json:
              schema:
                type: object
                additionalProperties:
                  type: string
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """

    return Response(
        simplejson.dumps(Contract.query_contract_terms(
            params['client_id'],
            effective_date=params['effective_date'],
            term_prefix=params.get('term_prefix'))),
        content_type='application/json')


@blueprint.get('/job_classifications')
@authenticated
@requires("JobClassification.*.view")
@use_args(schema.PaginationClientFilter(), location='querystring')
def list_job_classifications(user: User, params: dict):
    """List Job Classifications
    ---
    get:
      operationId: listJobClassifications
      tags:
        - job_classification
      summary: List JobClassifications
      description: List Job Classifications
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
        - in: query
          name: client_id
          required: false
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListJobClassificationResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    query = select(JobClassification).order_by('id')

    if params['client_id'] is not None:
        query = JobClassification.contracted_job_class_query(params['client_id'])

    paginated = db.paginate(
        query,
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListJobClassificationResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.post('/purchase_orders/<int:id>')
@authenticated
@requires("PurchaseOrder.*.edit")
@use_args(schema.PurchaseOrder(), location='json')
def update_purchase_order(user: User, data: dict, id: int):
    """Update a PurchaseOrder
    ---
    post:
      operationId: updatePurchaseOrder
      tags:
        - purchase_order
      summary: Update a PurchaseOrder
      description: Update a PurchaseOrder
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: path
          name: id
          required: true
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema: PurchaseOrder
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: PurchaseOrder
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    obj = get_obj(PurchaseOrder, id)

    # client_id may not be changed after obj creation
    if obj.client_id != data['client_id']:
        abort(400, ValidationError("Invalid client.", "client_id"))
    data.pop('client_id', None)

    data['modified_uid'] = user.id

    # TODO: generic-ize relationship handling
    departments_in_req = set(data.pop('departments', []))
    departments_in_db = set(obj.departments)
    departments_to_remove = departments_in_db - departments_in_req
    departments_to_add = departments_in_req - departments_in_db
    for dep in departments_to_remove:
        obj.departments.remove(dep)
    for dep in departments_to_add:
        obj.departments.append(dep)

    for key, value in data.items():
        setattr(obj, key, value)

    db.session.commit()

    return Response(
        schema.PurchaseOrder().dumps(obj),
        content_type="application/json",
    )


@blueprint.post('/positions')
@authenticated
@requires('Position.*.create')
@use_args(schema.Position(), location='json')
def create_position(user: User, data: dict):
    """Create a new Position
    ---
    post:
      operationId: createPosition
      tags:
        - position
      summary: Create a new Position
      description: Create a new Position
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema: Position
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: Position
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    obj = prepare_for_save(Position, data, user)
    try:
        db.session.add(obj)
        db.session.commit()
        resp_json = schema.Position().dumps(obj),
    except Exception as exc:
        logger.warning("Unexpected error: %s %s", data, exc)
        raise
    return Response(
        resp_json,
        content_type='application/json',
    )


@blueprint.get('/positions')
@authenticated
@requires("Position.*.view")
@use_args(schema.PaginationClientFilter(), location='querystring')
def list_positions(user: User, params: dict):
    """ List Positions
    ---
    get:
      operationId: listPositions
      tags:
        - position
      summary: List Positions
      description: List Positions
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
        - in: query
          name: client_id
          required: false
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListPositionResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    query = select(Position).order_by('id')
    if params['client_id'] is not None:
        query = query.filter_by(client_id=params['client_id'])
    paginated = db.paginate(
        query,
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListPositionResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.get('/requisition_types')
@authenticated
@requires("RequisitionType.*.view")
@use_args(schema.Pagination(), location='querystring')
def list_requisition_types(user: User, params: dict):
    """ List RequisitionTypes
    ---
    get:
      operationId: listRequisitionTypes
      tags:
        - requisition_type
      summary: List RequisitionTypes
      description: List RequisitionTypes
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListRequisitionTypeResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    # Replace RequisitionType with Category
    query = select(CategoryItem).join(Category).\
        filter(Category.key == 'requisition_type').order_by(CategoryItem.id)
    paginated = db.paginate(
        query,
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListRequisitionTypeResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.get('/pay_schemes')
@authenticated
@requires("PayScheme.*.view")
@use_args(schema.Pagination(), location='querystring')
def list_pay_schemes(user: User, params: dict):
    """ List PaySchemes
    ---
    get:
      operationId: listPaySchemes
      tags:
        - pay_scheme
      summary: List PaySchemes
      description: List PaySchemes
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListPaySchemeResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    query = select(CategoryItem).join(Category). \
        filter(Category.key == 'pay_scheme').order_by(CategoryItem.id)
    paginated = db.paginate(
        query,
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListPaySchemeResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.post('/schedules')
@authenticated
@requires("Schedule.*.create")
@use_args(schema.Schedule(), location='json')
def create_schedule(user: User, data: dict):
    """Create a new Schedule
    ---
    post:
      operationId: createSchedule
      tags:
        - schedule
      summary: Create a new Schedule
      description: Create a new Schedule
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema: Schedule
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: Schedule
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    obj = prepare_for_save(Schedule, data, user)
    try:
        db.session.add(obj)
        db.session.commit()
        resp_json = schema.Schedule().dumps(obj),
    except Exception as exc:
        logger.warning("Unexpected error: %s %s", data, exc)
        raise
    return Response(
        resp_json,
        content_type='application/json',
    )


@blueprint.get('/schedules')
@authenticated
@requires("Schedule.*.view")
@use_args(schema.PaginationClientFilter(), location='querystring')
def list_schedules(user: User, params: dict):
    """ List Schedules
    ---
    get:
      operationId: listSchedules
      tags:
        - schedule
      summary: List Schedules
      description: List Schedules
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
        - in: query
          name: client_id
          required: false
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListScheduleResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    query = select(Schedule).order_by('id')
    if params['client_id'] is not None:
        query = query.filter_by(client_id=params['client_id'])
    paginated = db.paginate(
        query,
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListScheduleResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.get('/available_workers')
@authenticated
@requires("Worker.*.view")
@use_args(schema.AvailableWorkersFilter(), location='querystring')
def list_available_workers(user: User, params: dict):
    """ List Available Workers
    ---
    get:
      operationId: listAvailableWorkers
      tags:
        - worker
      summary: List Available Workers
      description: List workers available to the client. These will be any worker assigned or presented to any of the client's existing requisitions.
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
        - in: query
          name: client_id
          required: false
          schema:
            type: integer
        - in: query
          name: for_requisition_id
          description: Exclude workers assigned to this requisition_id.
          required: false
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListWorkerResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """

    paginated = db.paginate(
        Worker.available_workers_query(
            params['client_id'],
            for_requisition_id=params.get('for_requisition_id')),
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListWorkerResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.get('/workers/<int:id>')
@authenticated
@requires("Worker.*.view")
def get_worker(user: User, id: int):
    """ Get Worker Detail
    ---
    get:
      operationId: getWorkerDetail
      tags:
        - worker
      summary: Get Worker Detail
      description: Get Worker Detail
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: path
          name: id
          required: true
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: Worker
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """

    query = Worker.query.filter_by(id=id)

    if not has_permission('Client.*.manage'):
        query = query.join(Assignment, Assignment.worker_id == Worker.id)
        query = query.join(Requisition, Requisition.id == Assignment.requisition_id)
        query = query.filter(Requisition.client_id == g.auth_state.client.id)

    obj = query.one_or_404(RESOURCE_NOT_FOUND)

    return Response(
        schema.Worker().dumps(obj),
        content_type='application/json')


@blueprint.post('/worker_environments')
@authenticated
@requires("WorkerEnvironment.*.create")
@use_args(schema.WorkerEnvironment(), location='json')
def create_worker_environment(user: User, data: dict):
    """Create a new Worker Environment
    ---
    post:
      operationId: createWorkerEnvironment
      tags:
        - worker_environment
      summary: Create a new Worker Environment
      description: Create a new Worker Environment
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema: WorkerEnvironment
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: WorkerEnvironment
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    obj = prepare_for_save(WorkerEnvironment, data, user)
    try:
        db.session.add(obj)
        db.session.commit()
        resp_json = schema.WorkerEnvironment().dumps(obj),
    except IntegrityError as exc:
        logger.warning("Integrity error inserting worker_environment: %s %s", data, exc)
        abort(400, ValidationError("Worker Environment name must be unique.", "name"))
    except Exception as exc:
        logger.warning("Unexpected error: %s %s", data, exc)
        raise

    return Response(
        resp_json,
        content_type='application/json',
    )


@blueprint.get('/worker_environments')
@authenticated
@requires("WorkerEnvironment.*.view")
@use_args(schema.PaginationClientFilter(), location='querystring')
def list_worker_environments(user: User, params: dict):
    """ List Work Environments
    ---
    get:
      operationId: listWorkerEnvironments
      tags:
        - worker_environment
      summary: List Worker Environments
      description: List Worker Environments
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
        - in: query
          name: client_id
          required: false
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListWorkerEnvironmentResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    query = select(WorkerEnvironment).order_by('id')
    if params['client_id'] is not None:
        query = query.filter_by(client_id=params['client_id'])
    paginated = db.paginate(
        query,
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListWorkerEnvironmentResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.post('/locations')
@authenticated
@requires("Location.*.create")
@use_args(schema.Location(), location='json')
def create_location(user: User, data: dict):
    """Create a new Location
    ---
    post:
      operationId: createLocation
      tags:
        - location
      summary: Create a new Location
      description: Create a new Location
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema: Location
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: Location
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    obj = prepare_for_save(Location, data, user)
    try:
        db.session.add(obj)
        db.session.commit()
        resp_json = schema.Location().dumps(obj),
    except IntegrityError as exc:
        logger.warning("Integrity error inserting location: %s %s", data, exc)
        abort(400, ValidationError("Location name must be unique.", "name"))
        raise  # abort actually raises, this is just for linting.
    except Exception as exc:
        logger.warning("Unexpected error: %s %s", data, exc)
        raise
    return Response(
        resp_json,
        content_type='application/json',
    )


@blueprint.get('/locations')
@authenticated
@requires("Location.*.view")
@use_args(schema.PaginationClientFilter(), location='querystring')
def list_location(user: User, params: dict):
    """ List Locations
    ---
    get:
      operationId: listLocations
      tags:
        - location
      summary: List Locations
      description: List Locations
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
        - in: query
          name: client_id
          required: false
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListLocationResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    query = select(Location).order_by('id')
    if params['client_id'] is not None:
        query = query.filter_by(client_id=params['client_id'])
    paginated = db.paginate(
        query,
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListLocationResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.post('/requisitions')
@authenticated
@requires("Requisition.*.create")
@use_args(schema.Requisition(), location='json')
def create_requisition(user: User, data: dict):
    """Create a New Requisition
    ---
    post:
      operationId: createRequisition
      tags:
       - requisition
      summary: Create a New Requisition
      description: Create a New Requisition
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema: Requisition
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: Requisition
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """

    obj = prepare_for_save(Requisition, data, user)
    try:
        db.session.add(obj)
        db.session.commit()
        resp_json = schema.Requisition().dumps(obj),
    except Exception as exc:
        logger.warning("Unexpected error: %s %s", data, exc)
        raise
    return Response(
        resp_json,
        content_type='application/json',
    )


@blueprint.get('/requisitions')
@authenticated
@requires("Requisition.*.view")
@use_args(schema.PaginationClientFilter(), location='querystring')
def list_requisition(user: User, params: dict):
    """ List Requisitions
    ---
    get:
      operationId: listRequisitions
      tags:
        - requisition
      summary: List Requisitions
      description: List Requisitions
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
        - in: query
          name: client_id
          required: false
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListRequisitionResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    paginated = db.paginate(
        select(Requisition).
        filter_by(client_id=params['client_id']).
        filter(Requisition.state != States.DELETED).
        order_by('id'),
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListRequisitionResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


@blueprint.get('/requisitions/<int:id>')
@authenticated
@requires("Requisition.*.view")
def get_requisition(user: User, id: int):
    """ Get Requisition Detail
    ---
    get:
      operationId: getRequisitionDetail
      tags:
        - requisition
      summary: Get Requisition Detail
      description: Get Requisition Detail
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: path
          name: id
          required: true
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: Requisition
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    obj = get_obj(Requisition, id)

    return Response(
        schema.Requisition().dumps(obj),
        content_type='application/json')


@blueprint.post('/requisitions/<int:id>')
@authenticated
@requires("Requisition.*.edit")
@use_args(schema.Requisition, location='json')
def update_requisition(user: User, data: dict, id: int):
    """Update a Requisition
    ---
    post:
      operationId: updateRequisition
      tags:
        - requisition
      summary: Update a Requisition
      description: Update a Requisition
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: path
          name: id
          required: true
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema: Requisition
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: Requisition
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    obj = get_obj(Requisition, id)

    # client_id may not be changed after obj creation
    if obj.client_id != data['client_id']:
        abort(400, ValidationError("Invalid client.", "client_id"))

    data.pop('client_id', None)

    data['modified_uid'] = user.id

    # TODO: generic-ize relationship handling

    present_workers_in_req = set(data.pop('presented_workers', []))
    present_workers_in_db = set(obj.presented_workers)
    present_workers_to_add = present_workers_in_req - present_workers_in_db
    for worker in present_workers_to_add:
        obj.presented_workers.append(worker)

    for key, value in data.items():
        setattr(obj, key, value)

    # Reset approval state back to pending with no approval logs
    obj.approval_state = ApprovalState.PENDING
    obj.approvals = []

    db.session.commit()

    return Response(
        schema.Requisition().dumps(obj),
        content_type="application/json",
    )


@blueprint.delete('/requisitions/<int:id>')
@authenticated
@requires("Requisition.*.delete")
def delete_requisition(user: User, id: int):
    """Delete a Requisition
    ---
    delete:
      operationId: deleteRequisition
      tags:
        - requisition
      summary: Delete a Requisition
      description: Delete a Requisition
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: path
          name: id
          required: true
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: EmptyResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    query = Requisition.query.filter_by(id=id)

    if not has_permission('PurchaseOrder.*.manage'):
        query = query.filter_by(client_id=g.auth_state.client.id)

    obj = query.one_or_404("Resource not found.")

    obj.delete(user)
    db.session.commit()

    return Response('{}', content_type='application/json')


@blueprint.post('/requisitions/<int:id>/approval')
@authenticated
@requires("Approval.*.create")
@use_args(schema.Approval, location='json')
def create_requisition_approval(user: User, data: dict, id: int):
    """Submit an Approval Decision
    ---
    post:
      operationId: submitRequisitionApproval
      tags:
       - requisition
      summary: Approve or Reject Requisition
      description: Pending requisitions may be approved or rejected by qualified users.
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: path
          name: id
          required: true
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema: Approval
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: Approval
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    data['approver_uid'] = user.id
    data['datetime'] = datetime.utcnow()

    obj: Requisition = get_obj(Requisition, id)

    if obj.approval_state != ApprovalState.PENDING:
        abort(400, ValidationError('Approval decision cannot be modified'))

    try:
        if data.get('decision') == ApprovalDecision.APPROVE:
            obj.approval_state = ApprovalState.APPROVED
            obj.approve()
        else:
            obj.approval_state = ApprovalState.REJECTED
        obj.modified_uid = user.id
        obj.approvals = [simplejson.loads(schema.Approval().dumps(data))]
        db.session.add(obj)
        db.session.commit()
    except Exception as exc:
        logger.warning(f'Requisition approval exception: {id} {data} {exc}')
        raise
    return Response(
        schema.Approval().dumps(data),
        content_type='application/json',
    )


@blueprint.get('/assignments')
@authenticated
@requires("Assignment.*.view")
@use_args(schema.PaginationClientWorkerRequisitionFilter(), location='querystring')
def list_assignment(user: User, params: dict):
    """ List Assignments
    ---
    get:
      operationId: listAssignments
      tags:
        - assignment
      summary: List Assignments
      description: List Assignments
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: query
          name: page
          required: false
          schema:
            type: integer
            default: 1
        - in: query
          name: page_size
          required: false
          schema:
            type: integer
            default: 25
        - in: query
          name: client_id
          required: false
          schema:
            type: integer
        - in: query
          name: requisition_id
          required: false
          schema:
            type: integer
        - in: query
          name: worker_id
          required: false
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: ListAssignmentResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    query = (
        select(Assignment).
        join(Requisition, Assignment.requisition_id == Requisition.id).
        filter_by(client_id=params['client_id']).
        filter(Requisition.state != States.DELETED)
    )

    if params.get('requisition_id'):
        query = query.filter(Assignment.requisition_id == params['requisition_id'])

    if params.get('worker_id'):
        query = query.filter(Assignment.worker_id == params['worker_id'])

    paginated = db.paginate(
        query.order_by('id'),
        page=params['page'],
        per_page=params['page_size'],
    )

    return Response(
        schema.ListAssignmentResponse().dumps({
            'pagination': {
                'page': paginated.page,
                'total_pages': paginated.pages,
                'page_size': paginated.per_page,
            },
            'items': paginated.items,
        }),
        content_type='application/json')


blueprint.cli.add_command(commands.odoo_push_cmd)
@blueprint.get('/assignments/<int:id>')
@authenticated
@requires("Assignment.*.view")
def get_assignment_detail(user: User, id: int):
    """ Get Assignment Detail
    ---
    get:
      operationId: getAssignmentDetail
      tags:
        - assignment
      summary: Get Assignment Detail
      description: Get Assignment Detail
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: path
          name: id
          required: true
          schema:
            type: integer
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: Assignment
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    obj = get_obj(Assignment, id)

    return Response(
        schema.Assignment().dumps(obj),
        content_type='application/json')


@blueprint.post('/assignments/<int:id>')
@authenticated
@requires("Assignment.*.edit")
def update_assignment(user: User, id: int):
    """ Update an Assignment
    ---
    post:
      operationId: updateAssignment
      tags:
        - assignment
      summary: Update an Assignment
      description: Update an Assignment
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: path
          name: id
          required: true
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema: Assignment
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: Assignment
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """

    obj = get_obj(Assignment, id)
    raw_data = None
    try:
        raw_data = request.get_data(cache=False, as_text=True)
        data = schema.Assignment(instance=obj).loads(raw_data)
    except simplejson.JSONDecodeError as err:
        logger.debug(f"Invalid login request: `{raw_data}` `{err}")
        abort(400, "Invalid request.")
    except ValidationError as err:
        logger.debug(f"Invalid login request: `{request.data}` `{err.normalized_messages()}`")
        abort(400, err)

    data['modified_uid'] = user.id

    obj.update(data)

    db.session.commit()

    return Response(
        schema.Assignment().dumps(obj),
        content_type="application/json",
    )


@blueprint.post('/assignments')
@authenticated
@requires("Assignment.*.create")
@use_args(schema.ReplaceAssignmentRequest, location='json')
def create_assignment(user: User, data: dict):
    """Create an Assignment
    ---
    post:
      operationId: createAssignment
      tags:
       - assignment
      summary: Create or Replace Assignment
      description: Create or Replace an Assigment
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema: ReplaceAssignmentRequest
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: Assignment
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    data['created_uid'] = user.id
    data['modified_uid'] = user.id

    replaced_assignment = data.pop('replaced_assignment')

    obj = Assignment(**data)
    db.session.add(obj)

    db.session.flush()
    replaced_assignment.replaced_by_assignment_id = obj.id

    db.session.commit()

    return Response(
        schema.Assignment().dumps(obj),
        content_type='application/json')


@blueprint.delete('/assignments/<int:id>')
@authenticated
@requires("Assignment.*.delete")
@use_args(schema.DeleteAssignmentRequest, location='json')
def delete_assignment(user: User, data: dict, id: int):
    """Delete an Assignment
    ---
    delete:
      operationId: deleteAssignment
      tags:
        - assignment
      summary: End or Cancel an Assignment
      description: End or Cancel an Assignment
      parameters:
        - in: header
          name: X-Client-ID
          required: false
          schema:
            type: integer
        - in: path
          name: id
          required: true
          schema:
            type: integer
      requestBody:
        required: true
        content:
          application/json:
            schema: DeleteAssignmentRequest
      responses:
        200:
          description: Success
          content:
            application/json:
              schema: EmptyResponse
        default:
          description: Error
          content:
            application/json:
              schema: ErrorResponse
    """
    assignment = get_obj(Assignment, id)

    if assignment.status in (AssignmentState.ENDED, AssignmentState.CANCELED):
        abort(400, "Assignment already ended or canceled.")

    if data['delete_type'] == schema.DeleteAssignmentType.END:
        assignment.status = AssignmentState.ENDED
        assignment.ended_by_uid = user.id
        assignment.end_reason = data['end_reason']
        assignment.end_notes = data.get('notes')
        assignment.actual_end_date = data['end_date']

    elif data['delete_type'] == schema.DeleteAssignmentType.CANCEL:
        assignment.status = AssignmentState.CANCELED
        assignment.canceled_by_uid = user.id
        assignment.cancel_notes = data.get('notes')
        assignment.actual_end_date = data['end_date']

    else:
        # Shouldn't be possible
        logger.warning(f"Unexpected assignment delete type: {data}")
        abort(400, "Invalid request.")

    db.session.add(assignment)
    db.session.commit()

    return Response('{}', content_type='application/json')


blueprint.cli.add_command(commands.update_data_cmd)
blueprint.cli.add_command(commands.sync_client_cmd)
blueprint.cli.add_command(commands.sync_undo_cmd)
blueprint.cli.add_command(commands.dump_census_sheet_cmd)

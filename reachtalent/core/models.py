from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum, auto

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Mapped
from sqlalchemy.sql.expression import Select

from ..auth.models import User, Role
from ..auth.permissions import register_entity
from ..database import db, Column, Base


purchase_order_department = db.Table(
    "purchase_order_department",
    db.Model.metadata,
    Column("purchase_order_id", db.ForeignKey("purchase_order.id"), primary_key=True),
    Column("department_id", db.ForeignKey("department.id"), primary_key=True)
)

department_position = db.Table(
    "department_position",
    db.Model.metadata,
    Column("department_id", db.ForeignKey("department.id"), primary_key=True),
    Column("position_id", db.ForeignKey("position.id"), primary_key=True),
)

department_location = db.Table(
    "department_location",
    db.Model.metadata,
    Column("department_id", db.ForeignKey("department.id"), primary_key=True),
    Column("location_id", db.ForeignKey("location.id"), primary_key=True),
)


@register_entity
class Category(Base):
    id: Mapped[int] = Column(db.Integer, primary_key=True)
    key: Mapped[str] = Column(db.String, unique=True)
    label: Mapped[str] = Column(db.String)
    description: Mapped[str] = Column(db.String)

    items: Mapped[list["CategoryItem"]] = db.relationship("CategoryItem")


@register_entity
class CategoryItem(Base):
    __table_args__ = (
        db.UniqueConstraint("category_id", "key"),
    )
    id: Mapped[int] = Column(db.Integer, primary_key=True)
    category_id: Mapped[int] = Column(db.Integer, db.ForeignKey("category.id"))
    category: Mapped["Category"] = db.relationship("Category", back_populates="items")

    key: Mapped[str] = Column(db.String, comment="String ID for a category item. May not change once set.")
    label: Mapped[str] = Column(db.String, comment="Short label for displaying category item. May change.")
    description: Mapped[str] = Column(db.String, comment="Optional longer description of the category item meaning.")


class ClientUserDepartment(Base):
    __table_args__ = (
        db.UniqueConstraint("client_user_id", "department_id"),
    )
    id: Mapped[int] = Column(db.Integer, primary_key=True)

    client_user_id: Mapped[int] = Column(db.Integer, db.ForeignKey("client_user.id"))
    department_id: Mapped[int] = Column(db.Integer, db.ForeignKey("department.id"))


@register_entity
class Client(Base):
    RTI_CLIENT_NAME = "Reach Talent Inc."

    id: Mapped[int] = Column(db.Integer, primary_key=True)
    name: Mapped[str] = Column(db.String, unique=True)

    client_users: Mapped[list["ClientUser"]] = db.relationship("ClientUser")
    departments: Mapped[list["Department"]] = db.relationship("Department")
    schedules: Mapped[list["Schedule"]] = db.relationship("Schedule")
    purchase_orders: Mapped[list["PurchaseOrder"]] = db.relationship("PurchaseOrder")
    positions: Mapped[list["Position"]] = db.relationship("Position")
    requisitions: Mapped[list["Requisition"]] = db.relationship("Requisition")
    worker_environments: Mapped[list["WorkerEnvironment"]] = db.relationship("WorkerEnvironment")
    locations: Mapped[list["Location"]] = db.relationship("Location")


class ContractTermType(StrEnum):
    # oneOf(Text, Currency, Percent, Integer, Date, Date / Timestamp)
    TEXT = auto()
    CURRENCY = auto()
    PERCENT = auto()
    INTEGER = auto()
    DECIMAL = auto()
    DATE = auto()
    TIMESTAMP = auto()


@register_entity
class ContractTermDefinition(Base):
    id: Mapped[int] = Column(db.Integer, primary_key=True)

    ref: Mapped[str] = Column(db.String, unique=True)  # eg. "markup_jobclass_events_pct"
    type: Mapped["ContractTermType"] = Column(db.Enum(ContractTermType))
    label: Mapped[str] = Column(db.String)  # eg. "Events Markup"
    description: Mapped[str] = Column(db.String)


@register_entity
class ContractTerm(Base):
    id: Mapped[int] = Column(db.Integer, primary_key=True)

    contract_id: Mapped[int] = Column(db.Integer, db.ForeignKey("contract.id"))
    contract: Mapped["Contract"] = db.relationship("Contract")
    contract_term_definition_id: Mapped[int] = Column(db.Integer, db.ForeignKey("contract_term_definition.id"))
    contract_term_definition: Mapped[ContractTermDefinition] = db.relationship(ContractTermDefinition)

    val_numeric: Mapped["Decimal"] = Column(db.Numeric)
    val_char: Mapped["str"] = Column(db.String)
    val_datetime: Mapped["datetime"] = Column(db.DateTime)

    def val(self):
        return self.val_numeric or self.val_char or self.val_datetime


@register_entity
class Contract(Base):
    __table_args__ = (
        db.UniqueConstraint("client_id", "effective_start_date"),
    )
    id: Mapped[int] = Column(db.Integer, primary_key=True)
    client_id: Mapped[int] = Column(db.Integer, db.ForeignKey("client.id"))
    client: Mapped[Client] = db.relationship(Client)

    effective_start_date: Mapped["date"] = Column(db.Date, nullable=False)
    effective_end_date: Mapped["date"] = Column(db.Date, nullable=True)

    @staticmethod
    def query_contract_terms(client_id: int, effective_date: date = None, term_prefix: str = None) -> dict[str, "Any"]:
        if not effective_date:
            effective_date = datetime.utcnow()

        query = (
            select(ContractTerm)
            .join(Contract)
            .join(ContractTermDefinition)
            .filter(
                Contract.client_id == client_id,
                Contract.effective_start_date <= effective_date,
                or_(Contract.effective_end_date > effective_date, Contract.effective_end_date.is_(None)))
        )
        if term_prefix:
            query = query.filter(ContractTermDefinition.ref.like(f'{term_prefix}%'))

        query = query.order_by(Contract.effective_start_date, ContractTermDefinition.id)

        effective_terms = {}
        for term in db.session.execute(query).scalars():
            effective_terms[term.contract_term_definition.ref] = term.val()

        return effective_terms


@register_entity
class JobClassification(Base):
    id: Mapped[int] = Column(db.Integer, primary_key=True)
    contract_term_prefix: Mapped[str] = Column(db.String, unique=True)
    label: Mapped[str] = Column(db.String)
    description: Mapped[str] = Column(db.String)

    @staticmethod
    def contracted_job_class_query(client_id: int):
        markup_suffixes = ['pct', 'flat']
        contract_job_class_markups = set()

        for term_ref in Contract.query_contract_terms(client_id, term_prefix='markup_jobclass_').keys():
            for sfx in markup_suffixes:
                if term_ref.endswith(sfx):
                    contract_job_class_markups.add(term_ref[:-len(sfx)])
                    break

        query = select(JobClassification).order_by('id')
        query = query.filter(JobClassification.contract_term_prefix.in_(contract_job_class_markups))
        return query


@register_entity(name='Staff')
class ClientUser(Base):
    __table_args__ = (
        db.UniqueConstraint('client_id', 'user_id'),
    )

    id: Mapped[int] = Column(db.Integer, primary_key=True)

    client_id: Mapped[int] = Column(db.Integer, db.ForeignKey("client.id"))
    client: Mapped["Client"] = db.relationship("Client", back_populates="client_users")

    user_id: Mapped[int] = Column(db.Integer, db.ForeignKey("user.id"))
    user: Mapped["User"] = db.relationship("User", foreign_keys=[user_id], back_populates="client_roles")

    role_id: Mapped[int] = Column(db.Integer, db.ForeignKey("role.id"), nullable=True)
    role: Mapped["Role"] = db.relationship("Role")

    cost_center_id: Mapped[int] = Column(db.Integer, db.ForeignKey("cost_center.id"), nullable=True)
    cost_center: Mapped["CostCenter"] = db.relationship("CostCenter")

    departments: Mapped[list["Department"]] = db.relationship("Department", secondary="client_user_department")

    reports_to_client_user_id: Mapped[int] = Column(db.Integer, db.ForeignKey("client_user.id"))
    reports_to: Mapped["ClientUser"] = db.relationship("ClientUser")

    phone_number: Mapped[str] = Column(db.String)
    title: Mapped[str] = Column(db.String)


@register_entity
class CostCenter(Base):
    __table_args__ = (
        db.UniqueConstraint("name", "client_id"),
    )
    id: Mapped[int] = Column(db.Integer, primary_key=True)
    client_id: Mapped[int] = Column(db.Integer, db.ForeignKey("client.id"))
    client: Mapped["Client"] = db.relationship("Client")

    name: Mapped[str] = Column(db.String)
    description: Mapped[str] = Column(db.String)


@register_entity
class Department(Base):
    __table_args__ = (
        db.UniqueConstraint("client_id", "name"),
        db.UniqueConstraint("number", "client_id"),
    )

    id: Mapped[int] = Column(db.Integer, primary_key=True)

    client_id: Mapped[int] = Column(db.Integer, db.ForeignKey("client.id"))
    client: Mapped["Client"] = db.relationship("Client", back_populates="departments")

    name: Mapped[str] = Column(db.String)
    number: Mapped[str] = Column(db.String)

    purchase_orders: Mapped[list["PurchaseOrder"]] = db.relationship("PurchaseOrder", secondary=purchase_order_department)
    positions: Mapped[list["Position"]] = db.relationship("Position", secondary=department_position, cascade="all, delete")

    owner_client_user_id: Mapped[int] = Column(db.Integer, db.ForeignKey("client_user.id"))
    owner: Mapped["ClientUser"] = db.relationship("ClientUser", foreign_keys=[owner_client_user_id])

    accounting_approver_client_user_id: Mapped[int] = Column(db.Integer, db.ForeignKey("client_user.id"))
    accounting_approver: Mapped["ClientUser"] = db.relationship("ClientUser", foreign_keys=[accounting_approver_client_user_id])

    locations: Mapped[list["Location"]] = db.relationship("Location", secondary=department_location, cascade="all, delete")


@register_entity
class RequisitionType(Base):
    """
    Deprecated. Use Category / CategoryItem
    """
    __BASE_DATA__ = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part-Time'),
        ('1099', '1099'),
    ]

    id: Mapped[int] = Column(db.Integer, primary_key=True)
    name: Mapped[str] = Column(db.String, unique=True)
    display_name: Mapped[str] = Column(db.String)


@register_entity
class PayScheme(Base):
    """
    Deprecated. Use Category / CategoryItem
    """
    __BASE_DATA__ = [
        ('exempt', 'Exempt'),
        ('nonexempt', 'Non-Exempt'),
        ('cpe', 'Computer Professional Exempt'),
    ]

    id: Mapped[int] = Column(db.Integer, primary_key=True)
    name: Mapped[str] = Column(db.String, unique=True)
    display_name: Mapped[str] = Column(db.String)


@register_entity
class Schedule(Base):
    __table_args__ = (
        db.UniqueConstraint("client_id", "name"),
    )

    id: Mapped[int] = Column(db.Integer, primary_key=True)

    client_id: Mapped[int] = Column(db.Integer, db.ForeignKey("client.id"))
    client: Mapped["Client"] = db.relationship("Client", back_populates="schedules")

    name: Mapped[str] = Column(db.String)
    description: Mapped[str] = Column(db.String)


@register_entity
class PurchaseOrder(Base):
    id: Mapped[int] = Column(db.Integer, primary_key=True)

    client_id: Mapped[int] = Column(db.Integer, db.ForeignKey("client.id"))
    client: Mapped["Client"] = db.relationship("Client", back_populates="purchase_orders")

    departments: Mapped[list["Department"]] = db.relationship(
        "Department", secondary=purchase_order_department, back_populates="purchase_orders")


@register_entity
class Position(Base):
    id: Mapped[int] = Column(db.Integer, primary_key=True)

    client_id: Mapped[int] = Column(db.Integer, db.ForeignKey("client.id"))
    client: Mapped["Client"] = db.relationship("Client", back_populates="positions")

    departments: Mapped[list["Department"]] = db.relationship("Department", secondary=department_position, back_populates="positions")

    title: Mapped[str] = Column(db.String)
    job_description: Mapped[str] = Column(db.String)

    job_classification_id: Mapped[int] = Column(db.Integer, db.ForeignKey("job_classification.id"))
    job_classification: Mapped["JobClassification"] = db.relationship("JobClassification")

    worker_environment_id: Mapped[int] = Column(
        db.Integer, db.ForeignKey("worker_environment.id"))
    worker_environment: Mapped["WorkerEnvironment"] = db.relationship("WorkerEnvironment")

    requirements: Mapped[list[str]] = Column(db.JSON)

    pay_rate_min: Mapped[Decimal] = Column(db.Numeric)
    pay_rate_max: Mapped[Decimal] = Column(db.Numeric)
    is_remote: Mapped[bool] = Column(db.Boolean)

    def calculate_bill_rate(self, pay_rate: Decimal, effective_date: datetime = None) -> Decimal:
        """
        calculate_bill_rate calculates the bill rate for a Position
        based on the Client's configured jobclass markup.
        """

        _terms = Contract.query_contract_terms(
            self.client_id,
            term_prefix=self.job_classification.contract_term_prefix,
            effective_date=effective_date,
        )

        percent_markup = Decimal('0.00')
        flat_markup = Decimal('0.00')

        for term_ref, term_val in _terms.items():
            if term_ref.endswith('_pct'):
                percent_markup = Decimal(term_val)
            elif term_ref.endswith('_flat'):
                flat_markup = Decimal(term_val)

        return (
                (pay_rate + flat_markup)
                * (Decimal('1.00') + percent_markup)
        ).quantize(Decimal('1.00'), rounding=ROUND_HALF_UP)


class States(StrEnum):
    PENDING = auto()
    ACTIVE = auto()
    DELETED = auto()


class StateMixin:
    state: Mapped[States] = Column(db.String, server_default=States.PENDING)

    def delete(self, user: User):
        self.state = States.DELETED
        self.modified_uid = user.id


class ApprovalState(StrEnum):
    PENDING = auto()
    APPROVED = auto()
    REJECTED = auto()


class ApprovalDecision(StrEnum):
    APPROVE = auto()
    REJECT = auto()


@register_entity
class Approval:
    pass  # TODO: placeholder for permissions


@register_entity
class Requisition(Base, StateMixin):
    id: Mapped[int] = Column(db.Integer, primary_key=True)

    approval_state: Mapped[ApprovalState] = Column(db.Enum(ApprovalState), server_default='PENDING')
    approvals: Mapped[list[dict]] = Column(db.JSON, default=list)

    created_uid: Mapped[int] = Column(
        db.Integer, db.ForeignKey("user.id"), server_default="1")
    requestor: Mapped["User"] = db.relationship(
        "User", foreign_keys=created_uid)

    client_id: Mapped[int] = Column(db.Integer, db.ForeignKey("client.id"))
    client: Mapped["Client"] = db.relationship("Client", back_populates="requisitions")

    purchase_order_id: Mapped[int] = Column(
        db.Integer, db.ForeignKey("purchase_order.id"), nullable=True)
    purchase_order = db.relationship("PurchaseOrder")

    position_id: Mapped[int] = Column(db.Integer, db.ForeignKey("position.id"))
    position: Mapped["Position"] = db.relationship("Position")

    num_assignments: Mapped[int] = Column(db.Integer, server_default="1")

    department_id: Mapped[int] = Column(
        db.Integer, db.ForeignKey("department.id"))
    department: Mapped["Department"] = db.relationship("Department")

    supervisor_user_id: Mapped[int] = Column(
        db.Integer, db.ForeignKey("user.id"))
    supervisor: Mapped["User"] = db.relationship(
        "User", foreign_keys=[supervisor_user_id])

    timecard_approver_user_id: Mapped[int] = Column(
        db.Integer, db.ForeignKey("user.id"))
    timecard_approver: Mapped["User"] = db.relationship(
        "User", foreign_keys=[timecard_approver_user_id])

    location_id: Mapped[int] = Column(db.Integer, db.ForeignKey("location.id"))
    location: Mapped["Location"] = db.relationship("Location")

    pay_rate: Mapped[Decimal] = Column(db.Numeric)

    # TODO: Calculate billrate based on Client Contract terms

    requisition_type_id: Mapped[int] = Column(
        db.Integer, db.ForeignKey("category_item.id"))

    requisition_type: Mapped["CategoryItem"] = db.relationship("CategoryItem",
                                                               primaryjoin=requisition_type_id == CategoryItem.id)

    pay_scheme_id: Mapped[int] = Column(db.Integer, db.ForeignKey("category_item.id"))

    pay_scheme: Mapped["CategoryItem"] = db.relationship("CategoryItem", primaryjoin=pay_scheme_id == CategoryItem.id)

    schedule_id: Mapped[int] = Column(db.Integer, db.ForeignKey("schedule.id"))
    schedule: Mapped["Schedule"] = db.relationship("Schedule")

    start_date: Mapped[date] = Column(db.Date)
    estimated_end_date: Mapped[date] = Column(db.Date)

    additional_information: Mapped[str] = Column(db.String, server_default="")

    # EmployeeInfo {
    #    Associate Name: str
    #    Preferred Name: str
    #    Email: str
    #    Additional Information: str
    # }
    employee_info: Mapped[dict] = Column(db.JSON)

    presented_workers: Mapped[list["Worker"]] = db.relationship(
        "Worker",
        secondary="requisition_present_worker",
    )

    assignments: Mapped[list["Assignment"]] = db.relationship("Assignment", back_populates='requisition')

    def approve(self):
        """
        Do post-approval work.
        """
        assignments_to_create = self.num_assignments - len(self.assignments)
        if assignments_to_create > 0:
            for _ in range(assignments_to_create):
                self.assignments.append(
                    Assignment(
                        status=AssignmentState.OPEN,
                        pay_rate=self.pay_rate,
                        bill_rate=self.position.calculate_bill_rate(self.pay_rate),
                        department_id=self.department_id,
                        tentative_start_date=self.start_date,
                        tentative_end_date=self.estimated_end_date,
                    )
                )


@register_entity
class WorkerEnvironment(Base):
    __table_args__ = (
        db.UniqueConstraint("client_id", "name"),
    )
    id: Mapped[int] = Column(db.Integer, primary_key=True)

    client_id: Mapped[int] = Column(db.Integer, db.ForeignKey("client.id"))
    client: Mapped["Client"] = db.relationship("Client", back_populates="worker_environments")

    name: Mapped[str] = Column(db.String)
    description: Mapped[str] = Column(db.String)


@register_entity
class Location(Base):
    __table_args__ = (
        db.UniqueConstraint("client_id", "name"),
    )
    id: Mapped[int] = Column(db.Integer, primary_key=True)

    client_id: Mapped[int] = Column(db.Integer, db.ForeignKey("client.id"))
    client: Mapped["Client"] = db.relationship("Client", back_populates="locations")

    name: Mapped[str] = Column(db.String)
    description: Mapped[str] = Column(db.String)
    street: Mapped[str] = Column(db.String)
    city: Mapped[str] = Column(db.String)
    state: Mapped[str] = Column(db.String)
    zip: Mapped[str] = Column(db.String)
    country: Mapped[str] = Column(db.String)


class Supplier(Base):
    id: Mapped[int] = Column(db.Integer, primary_key=True)
    name: Mapped[str] = Column(db.String, unique=True)
    description: Mapped[str] = Column(db.String)


@register_entity
class Worker(Base):
    id: Mapped[int] = Column(db.Integer, primary_key=True)

    user_id: Mapped[int] = Column(db.Integer, db.ForeignKey("user.id"))
    user: Mapped["User"] = db.relationship("User", uselist=False, back_populates="worker")

    supplier_id: Mapped[int] = Column(db.Integer, db.ForeignKey("supplier.id"))
    supplier: Mapped[Supplier] = db.relationship("Supplier")

    phone_number: Mapped[str] = Column(db.String)

    @staticmethod
    def available_workers_query(client_id: int, for_requisition_id: int | None = None) -> Select:
        client_presented_workers_ids = (
            select(Worker.id)
            .join(RequisitionPresentWorker, RequisitionPresentWorker.worker_id == Worker.id)
            .join(Requisition, and_(
                Requisition.id == RequisitionPresentWorker.requisition_id,
                Requisition.client_id == client_id
            ))
        )

        client_assigned_worker_ids = (
            select(Worker.id)
            .join(Assignment, Assignment.worker_id == Worker.id)
            .join(Requisition, and_(
                Requisition.id == Assignment.requisition_id,
                Requisition.client_id == client_id,
            ))
        )

        available_worker_ids = (
            client_presented_workers_ids.
            union(client_assigned_worker_ids).
            cte('available_worker_ids')
        )

        # Exclude workers already assigned to the requested requisition
        if for_requisition_id:
            requisition_assigned_workers = (
                select(Worker.id)
                .join(Assignment, and_(
                      Assignment.worker_id == Worker.id,
                      Assignment.requisition_id == for_requisition_id))
            ).cte()

            available_worker_ids = (
                select(available_worker_ids.c.id)
                .outerjoin(
                    requisition_assigned_workers,
                    available_worker_ids.c.id == requisition_assigned_workers.c.id)
                .filter(requisition_assigned_workers.c.id.is_(None))
            ).cte()

        return select(Worker).join(available_worker_ids, available_worker_ids.c.id == Worker.id)


class RequisitionPresentWorker(Base):
    """
    RequisitionPresentWorker is a model used to associate a worker to a
    requisition at the start of the acquisition process.
    """
    __table_args__ = (
        db.UniqueConstraint("requisition_id", "worker_id"),
    )

    id: Mapped[int] = Column(db.Integer, primary_key=True)

    requisition_id: Mapped[int] = Column(db.Integer, db.ForeignKey("requisition.id"))
    worker_id: Mapped[int] = Column(db.Integer, db.ForeignKey("worker.id"))


class AssignmentState(StrEnum):
    ACTIVE = auto()
    CANCELED = auto()
    OPEN = auto()
    ONBOARDING = auto()
    ONBOARDING_COMPLETE = auto()
    OFFER_MADE = auto()
    ENDED = auto()
    OFFER_AWAITING_APPROVAL = auto()
    PENDING_START = auto()


@register_entity
class Assignment(Base):
    """
    Assignment is a model that represents the binding of a worker
    to a requisition for employment.
    """
    __table_args__ = (
        db.UniqueConstraint("requisition_id", "worker_id"),
    )

    id: Mapped[int] = Column(db.Integer, primary_key=True)

    status: Mapped[AssignmentState] = Column(db.Enum(AssignmentState))

    pay_rate: Mapped[Decimal] = Column(db.Numeric)
    bill_rate: Mapped[Decimal] = Column(db.Numeric)

    department_id: Mapped[int] = Column(db.Integer, db.ForeignKey('department.id'))
    department: Mapped["Department"] = db.relationship("Department")

    replaced_by_assignment_id: Mapped[int] = Column(db.Integer, db.ForeignKey('assignment.id'))

    requisition_id: Mapped[int] = Column(db.Integer, db.ForeignKey("requisition.id"))
    requisition: Mapped["Requisition"] = db.relationship("Requisition")

    worker_id: Mapped[int] = Column(db.Integer, db.ForeignKey("worker.id"))
    worker: Mapped["Worker"] = db.relationship("Worker")

    cost_center_id: Mapped[int] = Column(db.Integer, db.ForeignKey("cost_center.id"))
    cost_center: Mapped["CostCenter"] = db.relationship("CostCenter")

    ended_by_uid: Mapped[int] = Column(db.Integer, db.ForeignKey("user.id"))
    canceled_by_uid: Mapped[int] = Column(db.Integer, db.ForeignKey("user.id"))

    tentative_start_date: Mapped[date] = Column(
        db.Date, comment='Start date proposed at the time the job offer is '
                         'made. This is often a "best guess"')
    actual_start_date: Mapped[date] = Column(
        db.Date, comment='ACTUAL start date this worker started the job (this '
                         'does not always match the date the worker was tracked '
                         'in the system)')
    system_start_date: Mapped[date] = Column(
        db.Date, comment="Date the worker's assignment started tracking in the "
                         "RTI system. This does not always match the worker's "
                         "ACTUAL start date with the position"
    )
    tentative_end_date: Mapped[date] = Column(
        db.Date, comment="Tentative Assignment end date. Does not always match ACTUAL end date."
    )
    actual_end_date: Mapped[date] = Column(
        db.Date, comment="ACTUAL end date this worker ended the job"
    )
    # Category(name='assignment_end_reason')
    end_reason_id: Mapped[int] = Column(db.Integer, db.ForeignKey('category_item.id'))
    end_reason: Mapped["CategoryItem"] = db.relationship("CategoryItem")
    end_notes: Mapped[str] = Column(db.String)
    cancel_notes: Mapped[str] = Column(db.String)
    timesheets_worker_editable: Mapped[bool] = Column(db.Boolean, server_default='0')
    timesheets_web_punchable: Mapped[bool] = Column(db.Boolean, server_default='1')

    @classmethod
    def filter_by_client(cls, query, client_id: int):
        return (query
                .join(Requisition, Requisition.id == Assignment.requisition_id)
                .filter(Requisition.client_id == client_id))

    def update(self, data: dict):
        # TODO: OPEN -> OFFER_AWAITING_APPROVAL
        # TODO: OFFER_AWAITING_APPROVAL -> OFFER_MADE
        # TODO: OFFER_MADE -> PENDING_START
        # TODO: PENDING_START -> ONBOARDING
        # TODO: ONBOARDING -> ONBOARDING_COMPLETE
        # TODO: ONBOARDING_COMPLETE -> ACTIVE
        # TODO: ACTIVE -> CANCELED
        # TODO: ACTIVE -> ENDED

        fields_by_state = {
            AssignmentState.OPEN: {
                'cost_center_id',
                'worker_id',
                'department_id',
                'pay_rate',
                'tentative_start_date',
                'actual_start_date',
                'system_start_date',
                'tentative_end_date',
                'actual_end_date',
                'timesheets_worker_editable',
                'timesheets_web_punchable',
            },
        }

        # Filter data by Assignment's current state
        allowed_fields = fields_by_state.get(self.status, set())
        _data = {
            key: value
            for key, value in data.items()
            if key in allowed_fields
        }

        # Magic fields
        if self.status == AssignmentState.OPEN:
            if data.get('worker_id'):
                data['status'] = AssignmentState.ACTIVE

        # Calculate bill_rate, if necessary
        pay_rate = data.get('pay_rate')
        if pay_rate and (not equivalent(pay_rate, self.pay_rate) or not self.bill_rate):
            data['bill_rate'] = self.requisition.position.calculate_bill_rate(pay_rate)

        for key, value in data.items():
            setattr(self, key, value)


class ImportSource(StrEnum):
    GOOGLE_SHEET = auto()


class ImportLog(Base):
    id: Mapped[int] = Column(db.Integer, primary_key=True)
    source: Mapped[ImportSource] = Column(db.Enum(ImportSource))
    client_id: Mapped[int] = Column(db.Integer)
    client_name: Mapped[str] = Column(db.String)
    summary: Mapped[str] = Column(db.String)


MONEY_DIFF_TOLERANCE = Decimal('0.005')


def equivalent(a, b) -> bool:
    dec_a = Decimal(a)
    dec_b = Decimal(b)
    diff = abs(dec_a - dec_b)
    return diff < MONEY_DIFF_TOLERANCE

__ENTITIES__ = set()
__CATEGORICAL_DATA__ = {}

ACTIONS = {
    'create',
    'view',
    'edit',
    'delete',
    'manage'
}


def _process_class(cls, name):
    if not name:
        name = cls.__name__
    if name not in __ENTITIES__:
        __ENTITIES__.add(name)
        if base_data := getattr(cls, '__BASE_DATA__', None):
            __CATEGORICAL_DATA__.setdefault(name, {
                'model': cls,
                'data': base_data,
            })
    return cls


def register_entity(cls=None, /, *, name: str = None):
    def _decorate(klass):
        return _process_class(klass, name)

    if cls is None:
        return _decorate

    return _decorate(cls)


def generate_permissions():
    return sorted([
        f"{ent}.*.{act}" for act in ACTIONS for ent in __ENTITIES__
    ])


def generate_rti_roles():
    return {
        'RTI Admin': generate_permissions(),
    }


def generate_base_roles():
    return {
        'Admin': [
            "Approval.*.create",
            "Approval.*.view",
            "Requisition.*.create",
            "Requisition.*.edit",
            "Requisition.*.delete",
            "Requisition.*.view",
            "Assignment.*.create",
            "Assignment.*.view",
            "Assignment.*.edit",
            "Assignment.*.delete",
            "RequisitionType.*.view",
            "Category.*.view",
            "CategoryItem.*.view",
            "Client.*.edit",
            "Client.*.view",
            "CostCenter.*.create",
            "CostCenter.*.view",
            "Staff.*.view",
            "Department.*.create",
            "Department.*.edit",
            "Department.*.view",
            "PayScheme.*.view",
            "JobClassification.*.view",
            "Position.*.create",
            "Position.*.view",
            "PurchaseOrder.*.create",
            "PurchaseOrder.*.edit",
            "PurchaseOrder.*.view",
            "Schedule.*.create",
            "Schedule.*.view",
            "Worker.*.view",
            "WorkerEnvironment.*.create",
            "WorkerEnvironment.*.view",
            "Location.*.create",
            "Location.*.view",
        ],
        'Hiring Manager': [
            "Approval.*.view",
            "Requisition.*.create",
            "Requisition.*.edit",
            "Requisition.*.view",
            "Assignment.*.create",
            "Assignment.*.view",
            "Assignment.*.edit",
            "Assignment.*.delete",
            "RequisitionType.*.view",
            "Category.*.view",
            "CategoryItem.*.view",
            "Client.*.view",
            "CostCenter.*.view",
            "Staff.*.view",
            "Department.*.view",
            "PayScheme.*.view",
            "JobClassification.*.view",
            "Position.*.create",
            "Position.*.view",
            "PurchaseOrder.*.view",
            "Schedule.*.create",
            "Schedule.*.view",
            "Worker.*.view",
            "WorkerEnvironment.*.create",
            "WorkerEnvironment.*.view",
            "Location.*.create",
            "Location.*.view",
        ],
        # Candidate Roles
        'Worker': [
            "Requisition.*.view",
        ],
        # Default Role w/ No-Permissions
        'Default': [],
    }

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.flask import FlaskPlugin
from marshmallow import fields

from .extensions import marshmallow as ma

spec = APISpec(
    title="ReachTalent",
    version="0.0.1",
    openapi_version="3.0.2",
    plugins=[FlaskPlugin(), MarshmallowPlugin()],
    servers=[
        {
            'url': 'https://local.reachtalent.com',
            'description': "Local Dev Server",
        }
    ],
    info={
        'description': "Reach Talent is the worlds best platform for staffing management.",
        'contact': {
            'name': 'Support',
            'email': 'support@reachtalent.com',
            'url': 'https://reachtalent.com/support',
        }
    }
)


class EmptyResponse(ma.Schema):
    pass


class ErrorResponse(ma.Schema):
    code = fields.Int(required=True)
    name = fields.String(required=True)
    description = fields.String()
    errors = fields.Dict(
        keys=fields.String(),
        values=fields.List(fields.String))

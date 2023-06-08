from typing import Optional

import click
from flask import Flask, Response, json, g, abort
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from .auth.utils import auth_middleware
from .auth.views import blueprint as auth_blueprint
from .auth.views import init as auth_init
from .config import Config, get_config
from .core.views import blueprint as core_blueprint
from .extensions import (
    db, bcrypt, migrate, marshmallow, mail
)
from .schema import spec


def create_app(test_config: Optional[Config] = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    if test_config:
        app.config.from_object(test_config)
    else:
        app.config.from_object(get_config())

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    register_extensions(app)
    register_blueprints(app)

    app.before_request(auth_middleware)

    @app.errorhandler(HTTPException)
    def handle_exception(e):
        """Return JSON instead of HTML for HTTP errors."""
        # start with the correct headers and status code from the error
        response = e.get_response()
        # replace the body with JSON
        # TODO: Use ErrorResponse obj?

        error_payload = {
            "code": e.code,
            "name": e.name,
        }
        if isinstance(e.description, ValidationError):
            error_payload['errors'] = e.description.normalized_messages()
        else:
            error_payload['description'] = e.description

        response.data = json.dumps(error_payload)
        response.content_type = "application/json"
        return response

    @app.route('/api')
    def hello():
        if g.auth_state.user:
            return f'Welcome, {g.auth_state.user.name}'
        return 'Welcome, Stranger'

    @app.cli.command('openapi')
    @click.option('--format',
                  'fmt',
                  type=click.Choice(['yaml', 'json'], case_sensitive=False),
                  default='yaml',
                  help='OpenAPI Spec format')
    def openapi(fmt: str):
        formats = {
            'yaml': spec.to_yaml,
            'json': lambda: json.dumps(spec.to_dict()),
        }
        click.echo(formats.get(fmt.lower())())

    @app.route('/api/openapi.<fmt>')
    def open_api_yaml(fmt: str):
        formats = {
            'yaml': lambda: Response(
                spec.to_yaml(),
                mimetype="text/plain",
            ),
            'json': lambda: Response(
                json.dumps(spec.to_dict()),
                mimetype="application/json",
            ),
        }
        if not (spec_responder := formats.get(fmt)):
            abort(404, "Resource not found.")
        return spec_responder()

    return app


def register_extensions(app: Flask):
    bcrypt.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    marshmallow.init_app(app)
    mail.init_app(app)


def register_blueprints(app: Flask):
    app.register_blueprint(auth_blueprint, url_prefix="/api/auth")
    app.register_blueprint(core_blueprint, url_prefix="/api")

    auth_init(app)

    with app.test_request_context():
        for name, func in app.view_functions.items():
            if not name.startswith('core.'):
                continue
            spec.path(view=func)

    spec_draft = spec.to_dict()
    tags = set(t['name'] for t in spec_draft.get('tags', []))
    for route, operations in spec_draft['paths'].items():
        for method, operation in operations.items():
            op_tags = operation.get('tags', [])
            if op_tags and op_tags[0] not in tags:
                spec.tag({'name': op_tags[0]})
                tags.add(op_tags[0])

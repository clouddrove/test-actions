import os
from dataclasses import dataclass, field, fields
from typing import Optional

from .logger import make_logger

logger = make_logger("reachtalent")


@dataclass
class Config:
    TESTING: bool = False
    DEBUG: bool = TESTING
    SECRET_KEY: str = "foobar"
    SERVER_NAME: str = None
    PREFERRED_URL_SCHEME: str = 'https'

    # Flask-SQLAlchemy config
    # https://flask-sqlalchemy.palletsprojects.com/en/3.0.x/config/
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///reachtalent.db"
    SQLALCHEMY_ENGINE_OPTIONS: dict = field(default_factory=dict)
    SQLALCHEMY_BINDS: dict = field(default_factory=dict)  # SQLALCHEMY_DATABASE_URI takes precedence
    SQLALCHEMY_ECHO: bool = False
    SQLALCHEMY_RECORD_QUERIES: bool = False
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # Flask-Mail config
    MAIL_SERVER: str = 'localhost'
    MAIL_PORT: int = 25
    MAIL_USE_TLS: bool = False
    MAIL_USE_SSL: bool = False
    MAIL_USERNAME: Optional[str] = None
    MAIL_PASSWORD: Optional[str] = None
    MAIL_DEFAULT_SENDER: Optional[str] = "no-reply@reachtalent.com"
    MAIL_MAX_EMAILS: Optional[int] = None
    MAIL_ASCII_ATTACHMENTS: bool = False

    # Flask-Dance
    GOOGLE_OAUTH_CLIENT_ID: str = None
    GOOGLE_OAUTH_CLIENT_SECRET: str = None
    LINKEDIN_OAUTH_CLIENT_ID: str = None
    LINKEDIN_OAUTH_CLIENT_SECRET: str = None
    FACEBOOK_OAUTH_CLIENT_ID: str = None
    FACEBOOK_OAUTH_CLIENT_SECRET: str = None
    APPLE_OAUTH_CLIENT_ID: str = None
    APPLE_OAUTH_CLIENT_SECRET: str = None

    # Sync-Client
    SYNC_CLIENT_OAUTH_CLIENT_ID: str = None
    SYNC_CLIENT_OAUTH_CLIENT_SECRET: str = None

    # Odoo
    ODOO_URL: str = ''
    ODOO_DB: str = ''
    ODOO_USERNAME: str = ''
    ODOO_PASSWORD: str = ''

    # ReachTalent Settings
    JWT_SECRET: str = "foobar"


def get_config():
    conf = Config()

    for conf_field in fields(conf):
        if conf_field.name in os.environ:
            default_val = getattr(conf, conf_field.name)
            raw_val = os.environ[conf_field.name]
            if default_val:
                logger.debug(f"Found field '{conf_field.name}' in env overwriting `{default_val}` with `{raw_val}`")
            setattr(conf, conf_field.name, os.environ[conf_field.name])

    logger.debug(f"get_config produced from environment: {conf} ")
    return conf

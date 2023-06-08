from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData

bcrypt = Bcrypt()
db = SQLAlchemy(
    metadata=MetaData(
        naming_convention={
            "ix": 'ix_%(column_0_label)s',
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s"
        }),
    # Prepare for SQLAlchemy 2.0 behavior with Session(future=True)
    session_options={'future': True},
)
migrate = Migrate()
marshmallow = Marshmallow()
mail = Mail()

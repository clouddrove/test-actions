from sqlalchemy import select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped

from .permissions import register_entity
from ..database import db, Column, Base
from ..extensions import bcrypt

role_permission = db.Table(
    "role_permission",
    db.Model.metadata,
    Column("role_id", db.ForeignKey("role.id"), primary_key=True),
    Column("permission_id", db.ForeignKey("permission.id"), primary_key=True),
)


@register_entity
class Permission(Base):
    __table_args__ = (
        db.UniqueConstraint('entity', 'field', 'action'),
    )

    id: Mapped[int] = Column(db.Integer, primary_key=True)
    # hybrid? calculate based on (entity . field . action)
    name: Mapped[str] = Column(db.String, unique=True)
    entity: Mapped[str] = Column(db.String)
    # field may be `*`
    field: Mapped[str] = Column(db.String)
    action: Mapped[str] = Column(db.String)

    def __str__(self) -> str:
        return f'{self.id}:{self.name}'


@register_entity
class Role(Base):
    id: Mapped[int] = Column(db.Integer, primary_key=True)
    name: Mapped[str] = Column(db.String, unique=True)
    base_role_id: Mapped[int] = Column(db.Integer,
                                       db.ForeignKey("role.id"), nullable=True)
    client_id: Mapped[str] = Column(db.Integer,
                                    db.ForeignKey("client.id"), nullable=True)

    permissions: Mapped[list["Permission"]] = db.relationship(
        "Permission", secondary=role_permission)

    def __str__(self) -> str:
        return f'{self.id}:{self.name} client:{self.client_id}'

    @property
    def perms(self):
        return [p.name for p in self.permissions]


@register_entity
class User(Base):
    id: Mapped[int] = Column(db.Integer, primary_key=True)
    email: Mapped[str] = Column(db.String, unique=True, nullable=False)
    email_verified: Mapped[bool] = Column(db.Boolean, server_default="0")
    _password: Mapped[str] = Column("password", db.String)
    name: Mapped[str] = Column(db.String)
    auth_provider_id: Mapped[int] = Column(
        db.Integer, db.ForeignKey("auth_provider.id"), nullable=True)

    client_roles: Mapped[list["ClientUser"]] = db.relationship("ClientUser")
    worker: Mapped["Worker"] = db.relationship("Worker", uselist=False)

    @hybrid_property
    def password(self):
        """Hashed password."""
        return self._password

    @password.setter
    def password(self, value):
        """Set password."""
        self._password = bcrypt.generate_password_hash(value).decode('utf8')

    def check_password(self, value):
        """Check password."""
        return bcrypt.check_password_hash(self._password, value)

    @classmethod
    def select_by_email(cls, email: str):
        return select(cls).where(cls.email == email)


@register_entity
class AuthProvider(Base):
    id: Mapped[int] = Column(db.Integer, primary_key=True)
    name: Mapped[str] = Column(db.String, unique=True)


@register_entity
class UserProfile(Base):
    __table_args__ = (
        db.UniqueConstraint('auth_provider_id', 'ext_ref'),
    )

    id: Mapped[int] = Column(db.Integer, primary_key=True)

    # unique_together (auth_provider_id, ext_ref)
    auth_provider_id: Mapped[int] = Column(db.Integer,
                                           db.ForeignKey("auth_provider.id"),
                                           nullable=False)
    provider: Mapped["AuthProvider"] = db.relationship("AuthProvider")

    user_id: Mapped[int] = Column(db.Integer,
                                  db.ForeignKey("user.id"),
                                  nullable=False)
    user: Mapped["User"] = db.relationship("User")

    json_data: Mapped[dict] = Column(db.JSON)

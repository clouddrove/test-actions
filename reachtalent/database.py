from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped
from sqlalchemy.sql import func

from .extensions import db

# Aliasing column
Column = db.Column


class Base(db.Model):
    __abstract__ = True
    import_id: Mapped[int] = Column(db.Integer, nullable=True)
    ext_ref: Mapped[str] = Column(db.String, server_default="")
    created_uid: Mapped[int] = Column(db.Integer, server_default="1")
    created_date: Mapped[datetime] = Column(db.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'))
    modified_uid: Mapped[int] = Column(db.Integer, server_default="1")
    modified_date: Mapped[datetime] = Column(db.DateTime(timezone=True), onupdate=func.now(), server_default=sa.text('CURRENT_TIMESTAMP'))
    last_sync_date: Mapped[datetime] = Column(db.DateTime(timezone=True), nullable=True)

    @classmethod
    def filter_by_client(cls, query, client_id: int):
        if hasattr(cls, 'client_id'):
            return query.filter(cls.client_id == client_id)
        else:
            raise NotImplementedError()

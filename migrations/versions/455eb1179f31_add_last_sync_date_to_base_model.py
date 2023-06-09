"""Add last_sync_date to Base model

Revision ID: 455eb1179f31
Revises: 71ead369c78c
Create Date: 2023-05-30 15:56:55.594836

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '455eb1179f31'
down_revision = '71ead369c78c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('assignment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('auth_provider', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('category', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('category_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('client', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('client_user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('client_user_department', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('contract', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('contract_term', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('contract_term_definition', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('cost_center', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('department', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('import_log', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('job_classification', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('location', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('pay_scheme', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('permission', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('position', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('purchase_order', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('requisition', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('requisition_present_worker', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('requisition_type', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('role', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('schedule', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('supplier', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('user_profile', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('worker', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('worker_environment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sync_date', sa.DateTime(timezone=True), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('worker_environment', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('worker', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('user_profile', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('supplier', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('schedule', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('role', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('requisition_type', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('requisition_present_worker', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('requisition', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('purchase_order', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('position', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('permission', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('pay_scheme', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('location', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('job_classification', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('import_log', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('department', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('cost_center', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('contract_term_definition', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('contract_term', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('contract', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('client_user_department', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('client_user', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('client', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('category_item', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('category', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('auth_provider', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    with op.batch_alter_table('assignment', schema=None) as batch_op:
        batch_op.drop_column('last_sync_date')

    # ### end Alembic commands ###

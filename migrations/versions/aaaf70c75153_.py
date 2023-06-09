"""Add AuthProvider and UserProfile models.

Revision ID: aaaf70c75153
Revises: 7803c1899519
Create Date: 2023-02-13 23:57:17.451694

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aaaf70c75153'
down_revision = '7803c1899519'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    authprovider_table = op.create_table('auth_provider',
    sa.Column('ext_ref', sa.String(), server_default='', nullable=True),
    sa.Column('created_uid', sa.Integer(), server_default='1', nullable=True),
    sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('modified_uid', sa.Integer(), server_default='1', nullable=True),
    sa.Column('modified_date', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_provider')),
    sa.UniqueConstraint('name', name=op.f('uq_auth_provider_name'))
    )

    # Insert auth_providers
    op.bulk_insert(authprovider_table,
        [
            {'id': 1, 'name': 'Local'},
            {'id': 2, 'name': 'Google'},
            {'id': 3, 'name': 'LinkedIn'},
            {'id': 4, 'name': 'Apple'},
            {'id': 5, 'name': 'Facebook'},
        ]
    )

    op.create_table('user_profile',
    sa.Column('ext_ref', sa.String(), server_default='', nullable=True),
    sa.Column('created_uid', sa.Integer(), server_default='1', nullable=True),
    sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('modified_uid', sa.Integer(), server_default='1', nullable=True),
    sa.Column('modified_date', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('auth_provider_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('json_data', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['auth_provider_id'], ['auth_provider.id'], name=op.f('fk_user_profile_auth_provider_id_auth_provider')),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_user_profile_user_id_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_profile')),
    sa.UniqueConstraint('auth_provider_id', 'ext_ref', name=op.f('uq_user_profile_auth_provider_id'))
    )
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auth_provider_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_user_auth_provider_id_auth_provider'), 'auth_provider', ['auth_provider_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_user_auth_provider_id_auth_provider'), type_='foreignkey')
        batch_op.drop_column('auth_provider_id')

    op.drop_table('user_profile')
    op.drop_table('auth_provider')
    # ### end Alembic commands ###

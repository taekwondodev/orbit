"""SSH access of an orb: the network it admits SSH from (docs/adr/0008)
and its host keys, read once from the console (docs/adr/0007).

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'


def upgrade():
    op.add_column('orbs', sa.Column('ssh_allowed_cidr', sa.String(18)))
    op.add_column('orbs', sa.Column('ssh_host_keys', sa.Text))

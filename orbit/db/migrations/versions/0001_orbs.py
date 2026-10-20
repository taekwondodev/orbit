"""La tabella orbs.

Revision ID: 0001
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None


def upgrade():
    op.create_table(
        'orbs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(255), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('vcpus', sa.Integer, nullable=False),
        sa.Column('memory_mb', sa.Integer, nullable=False),
        sa.Column('disk_gb', sa.Integer, nullable=False),
        sa.Column('image', sa.String(255), nullable=False),
        sa.Column('lease_id', sa.String(36), nullable=False),
        sa.Column('reservation_id', sa.String(36), nullable=False),
        sa.Column('stack_id', sa.String(36)),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('fault', sa.Text),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime),
        sa.Column('deleted_at', sa.DateTime),
    )
    op.create_index('ix_orbs_project_id', 'orbs', ['project_id'])

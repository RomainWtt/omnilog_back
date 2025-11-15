"""pre cleanup is_public

Revision ID: 1b14ca656198
Revises: f409c6b3de20
Create Date: 2025-11-15
"""
from alembic import op

revision = "1b14ca656198"
down_revision = "f409c6b3de20"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_public")

def downgrade():
    pass

"""max_channel: внешний канал уведомлений – бот в мессенджере MAX

Revision ID: 003
Revises: 002
Create Date: 2026-10-27 15:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '003'
down_revision: str | None = '002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # новое значение enum нельзя использовать в той же транзакции, поэтому добавляем его в autocommit-блоке
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE channel ADD VALUE IF NOT EXISTS 'max'")
    op.add_column('users', sa.Column('max_user_id', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('max_link_code', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('max_link_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(op.f('uq_users_max_link_code'), 'users', ['max_link_code'])


def downgrade() -> None:
    op.drop_constraint(op.f('uq_users_max_link_code'), 'users', type_='unique')
    op.drop_column('users', 'max_link_expires_at')
    op.drop_column('users', 'max_link_code')
    op.drop_column('users', 'max_user_id')
    op.execute("DELETE FROM notification_deliveries WHERE channel = 'max'")
    op.execute("ALTER TYPE channel RENAME TO channel_old")
    op.execute("CREATE TYPE channel AS ENUM ('in_app', 'email')")
    op.execute("ALTER TABLE notification_deliveries ALTER COLUMN channel TYPE channel USING channel::text::channel")
    op.execute("DROP TYPE channel_old")

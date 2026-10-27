"""sanction_notifications: тип уведомления о дисквалификации и отстранении

Revision ID: 004
Revises: 003
Create Date: 2026-10-27 18:00:00
"""
from collections.abc import Sequence

from alembic import op


revision: str = '004'
down_revision: str | None = '003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notificationkind ADD VALUE IF NOT EXISTS 'sanction'")


def downgrade() -> None:
    op.execute("UPDATE notifications SET kind = 'application_status' WHERE kind = 'sanction'")
    op.execute("ALTER TYPE notificationkind RENAME TO notificationkind_old")
    op.execute("CREATE TYPE notificationkind AS ENUM ('registration_open', 'application_status', 'protocol_published', 'rank_request', "
               "'judge_request', 'deadline_soon', 'rank_expiring', 'category_expiring', 'link_request')")
    op.execute("ALTER TABLE notifications ALTER COLUMN kind TYPE notificationkind USING kind::text::notificationkind")
    op.execute("DROP TYPE notificationkind_old")

"""email_channel_password_reset: убирает бота MAX, переводит внешние уведомления на почту,
добавляет восстановление пароля

Revision ID: 005
Revises: 004
Create Date: 2026-10-28 10:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '005'
down_revision: str | None = '004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- бот MAX выпилен: колонки привязки больше не нужны ---
    op.drop_constraint(op.f('uq_users_max_link_code'), 'users', type_='unique')
    op.drop_column('users', 'max_link_expires_at')
    op.drop_column('users', 'max_link_code')
    op.drop_column('users', 'max_user_id')

    # --- канал уведомлений: почта вместо MAX; у пользователя – тумблер вкл/выкл ---
    op.add_column('users', sa.Column('email_notifications_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False))

    op.execute("DELETE FROM notification_deliveries WHERE channel = 'max'")
    op.execute("ALTER TYPE channel RENAME TO channel_old")
    op.execute("CREATE TYPE channel AS ENUM ('in_app', 'email')")
    op.execute("ALTER TABLE notification_deliveries ALTER COLUMN channel TYPE channel USING channel::text::channel")
    op.execute("DROP TYPE channel_old")

    # --- восстановление пароля по ссылке из письма ---
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_password_reset_tokens_user_id_users'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_password_reset_tokens')),
        sa.UniqueConstraint('token_hash', name=op.f('uq_password_reset_tokens_token_hash')),
    )
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')

    op.execute("ALTER TYPE channel RENAME TO channel_old")
    op.execute("CREATE TYPE channel AS ENUM ('in_app', 'email', 'max')")
    op.execute("ALTER TABLE notification_deliveries ALTER COLUMN channel TYPE channel USING channel::text::channel")
    op.execute("DROP TYPE channel_old")

    op.drop_column('users', 'email_notifications_enabled')

    op.add_column('users', sa.Column('max_user_id', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('max_link_code', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('max_link_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(op.f('uq_users_max_link_code'), 'users', ['max_link_code'])

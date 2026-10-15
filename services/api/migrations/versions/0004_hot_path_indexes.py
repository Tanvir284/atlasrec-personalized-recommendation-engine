"""Composite indexes for the recommendation hot path and monitoring queries."""
from alembic import op
from sqlalchemy import inspect

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

INDEXES = (
    ("ix_events_user_profile_created", "interaction_events", ["user_id", "profile", "created_at"]),
    ("ix_products_profile_available", "products", ["profile", "available"]),
    ("ix_recommendation_requests_profile_created", "recommendation_requests", ["profile", "created_at"]),
)


def upgrade():
    inspector = inspect(op.get_bind())
    for name, table, columns in INDEXES:
        if not any(index["name"] == name for index in inspector.get_indexes(table)):
            op.create_index(name, table, columns)


def downgrade():
    inspector = inspect(op.get_bind())
    for name, table, _ in INDEXES:
        if any(index["name"] == name for index in inspector.get_indexes(table)):
            op.drop_index(name, table_name=table)

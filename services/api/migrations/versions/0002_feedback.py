"""Bind anonymous exposures and store validated ratings."""
from alembic import op
from sqlalchemy import Column, Float, String, inspect

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    for table, additions in [
        ("interaction_events", [Column("actor_key", String(72), nullable=True), Column("rating", Float(), nullable=True)]),
        ("recommendation_requests", [Column("actor_key", String(72), nullable=True)]),
    ]:
        known = {c["name"] for c in inspect(bind).get_columns(table)}
        for column in additions:
            if column.name not in known:
                op.add_column(table, column)
                op.create_index("ix_" + table + "_" + column.name, table, [column.name]) if column.name == "actor_key" else None
    constraints = inspect(bind).get_unique_constraints("interaction_events")
    exposure = next((c for c in constraints if c["name"] == "event_exposure_unique"), None)
    if exposure and "user_id" in exposure["column_names"]:
        # Request IDs already identify one actor; legacy duplicate exposures are rejected
        # by PostgreSQL rather than deleting user data during a migration.
        with op.batch_alter_table("interaction_events") as batch:
            batch.drop_constraint("event_exposure_unique", type_="unique")
            batch.create_unique_constraint("event_exposure_unique", ["request_id", "item_id", "kind"])

def downgrade():
    raise RuntimeError("Feedback schema downgrade is not supported; restore a verified database backup.")

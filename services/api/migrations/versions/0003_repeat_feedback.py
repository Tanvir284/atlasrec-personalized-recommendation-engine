"""Deduplicate exposures while allowing revised explicit feedback."""
from alembic import op
from sqlalchemy import inspect, text

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    constraints = inspect(bind).get_unique_constraints("interaction_events")
    if any(constraint["name"] == "event_exposure_unique" for constraint in constraints):
        with op.batch_alter_table("interaction_events") as batch:
            batch.drop_constraint("event_exposure_unique", type_="unique")
    indices = inspect(bind).get_indexes("interaction_events")
    if not any(index["name"] == "event_exposure_unique" for index in indices):
        predicate = text("kind IN ('view', 'impression', 'click')")
        op.create_index("event_exposure_unique", "interaction_events", ["request_id", "item_id", "kind"],
                        unique=True, postgresql_where=predicate, sqlite_where=predicate)


def downgrade():
    raise RuntimeError("Revised ratings cannot be collapsed safely; restore a verified database backup.")

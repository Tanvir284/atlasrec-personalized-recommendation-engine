"""Frozen initial schema. Later changes require a new migration."""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('dataset_versions',
        sa.Column('id', sa.String(length=64), nullable=False, primary_key=True),
        sa.Column('profile', sa.String(length=20), nullable=False, primary_key=False),
        sa.Column('manifest', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index('ix_dataset_versions_profile','dataset_versions',['profile'],unique=False)
    op.create_table('products',
        sa.Column('id', sa.String(length=64), nullable=False, primary_key=True),
        sa.Column('profile', sa.String(length=20), nullable=False, primary_key=False),
        sa.Column('title', sa.String(length=500), nullable=False, primary_key=False),
        sa.Column('description', sa.String(), nullable=False, primary_key=False),
        sa.Column('category', sa.String(length=100), nullable=False, primary_key=False),
        sa.Column('price', sa.Float(), nullable=True, primary_key=False),
        sa.Column('currency', sa.String(length=8), nullable=True, primary_key=False),
        sa.Column('image', sa.String(length=500), nullable=False, primary_key=False),
        sa.Column('available', sa.Boolean(), nullable=False, primary_key=False),
    )
    op.create_index('ix_products_category','products',['category'],unique=False)
    op.create_index('ix_products_profile','products',['profile'],unique=False)
    op.create_index('ix_products_title','products',['title'],unique=False)
    op.create_table('users',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('email', sa.String(length=254), nullable=False, primary_key=False),
        sa.Column('name', sa.String(length=80), nullable=False, primary_key=False),
        sa.Column('password_hash', sa.String(length=256), nullable=False, primary_key=False),
        sa.Column('admin', sa.Boolean(), nullable=False, primary_key=False),
        sa.Column('preferences', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('history_revision', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index('ix_users_email','users',['email'],unique=True)
    op.create_table('admin_audit',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('actor_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False, primary_key=False),
        sa.Column('action', sa.String(length=80), nullable=False, primary_key=False),
        sa.Column('details', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_table('experiment_runs',
        sa.Column('id', sa.String(length=100), nullable=False, primary_key=True),
        sa.Column('dataset_id', sa.String(length=64), sa.ForeignKey('dataset_versions.id'), nullable=False, primary_key=False),
        sa.Column('profile', sa.String(length=20), nullable=False, primary_key=False),
        sa.Column('status', sa.String(length=20), nullable=False, primary_key=False),
        sa.Column('record', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index('ix_experiment_runs_dataset_id','experiment_runs',['dataset_id'],unique=False)
    op.create_index('ix_experiment_runs_profile','experiment_runs',['profile'],unique=False)
    op.create_table('favorites',
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False, primary_key=True),
        sa.Column('item_id', sa.String(length=64), sa.ForeignKey('products.id'), nullable=False, primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_table('interaction_events',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=True, primary_key=False),
        sa.Column('item_id', sa.String(length=64), sa.ForeignKey('products.id'), nullable=False, primary_key=False),
        sa.Column('kind', sa.String(length=30), nullable=False, primary_key=False),
        sa.Column('profile', sa.String(length=20), nullable=False, primary_key=False),
        sa.Column('surface', sa.String(length=80), nullable=False, primary_key=False),
        sa.Column('request_id', sa.String(length=36), nullable=True, primary_key=False),
        sa.Column('position', sa.Integer(), nullable=True, primary_key=False),
        sa.Column('model_version', sa.String(length=100), nullable=True, primary_key=False),
        sa.Column('client_timestamp', sa.DateTime(timezone=True), nullable=True, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.UniqueConstraint("user_id","request_id","item_id","kind",name="event_exposure_unique"),
    )
    op.create_index('ix_interaction_events_item_id','interaction_events',['item_id'],unique=False)
    op.create_index('ix_interaction_events_kind','interaction_events',['kind'],unique=False)
    op.create_index('ix_interaction_events_profile','interaction_events',['profile'],unique=False)
    op.create_index('ix_interaction_events_user_id','interaction_events',['user_id'],unique=False)
    op.create_table('jobs',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False, primary_key=False),
        sa.Column('status', sa.String(length=20), nullable=False, primary_key=False),
        sa.Column('progress', sa.Float(), nullable=False, primary_key=False),
        sa.Column('config', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('result', sa.JSON(), nullable=True, primary_key=False),
        sa.Column('error', sa.String(length=1000), nullable=True, primary_key=False),
        sa.Column('attempts', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index('ix_jobs_status','jobs',['status'],unique=False)
    op.create_table('recommendation_requests',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=True, primary_key=False),
        sa.Column('model_version', sa.String(length=100), nullable=True, primary_key=False),
        sa.Column('item_ids', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('duration_ms', sa.Float(), nullable=False, primary_key=False),
        sa.Column('fallback', sa.String(length=80), nullable=True, primary_key=False),
        sa.Column('cache_hit', sa.Boolean(), nullable=False, primary_key=False),
        sa.Column('profile', sa.String(length=20), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index('ix_recommendation_requests_profile','recommendation_requests',['profile'],unique=False)
    op.create_index('ix_recommendation_requests_user_id','recommendation_requests',['user_id'],unique=False)
    op.create_table('sessions',
        sa.Column('token_hash', sa.String(length=64), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False, primary_key=False),
        sa.Column('csrf_hash', sa.String(length=64), nullable=False, primary_key=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index('ix_sessions_expires_at','sessions',['expires_at'],unique=False)
    op.create_index('ix_sessions_user_id','sessions',['user_id'],unique=False)
    op.create_table('model_versions',
        sa.Column('id', sa.String(length=100), nullable=False, primary_key=True),
        sa.Column('run_id', sa.String(length=100), sa.ForeignKey('experiment_runs.id'), nullable=False, primary_key=False),
        sa.Column('profile', sa.String(length=20), nullable=False, primary_key=False),
        sa.Column('path', sa.String(length=1024), nullable=False, primary_key=False),
        sa.Column('validated', sa.Boolean(), nullable=False, primary_key=False),
        sa.Column('active', sa.Boolean(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index('ix_model_versions_profile','model_versions',['profile'],unique=False)

def downgrade():
    op.drop_table('model_versions')
    op.drop_table('sessions')
    op.drop_table('recommendation_requests')
    op.drop_table('jobs')
    op.drop_table('interaction_events')
    op.drop_table('favorites')
    op.drop_table('experiment_runs')
    op.drop_table('admin_audit')
    op.drop_table('users')
    op.drop_table('products')
    op.drop_table('dataset_versions')

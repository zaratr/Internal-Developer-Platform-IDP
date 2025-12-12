"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2024-01-01
"""

from alembic import op
import sqlalchemy as sa


author = "auto"
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id")),
        sa.Column("config", sa.JSON(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("tags", sa.JSON(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "environments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("tier", sa.Enum("dev", "staging", "prod", name="environmenttier"), nullable=False),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id")),
        sa.Column("config", sa.JSON(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "deployments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id")),
        sa.Column("environment_id", sa.Integer(), sa.ForeignKey("environments.id")),
        sa.Column("version", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "succeeded", "failed", name="deploymentstatus"),
            server_default="pending",
        ),
        sa.Column("initiated_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "platform_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("enforced", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "action",
            sa.Enum("created", "updated", "deleted", "guardrail_blocked", name="auditaction"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("performed_by", sa.String(length=255), nullable=False),
        sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("audit_logs")
    op.drop_table("platform_policies")
    op.drop_table("deployments")
    op.drop_table("environments")
    op.drop_table("services")
    op.drop_table("teams")
    op.execute('DROP TYPE IF EXISTS auditaction;')
    op.execute('DROP TYPE IF EXISTS deploymentstatus;')
    op.execute('DROP TYPE IF EXISTS environmenttier;')

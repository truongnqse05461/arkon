"""Migrate employee departments to a many-to-many relationship.

Revision ID: 034
Revises: 033
Create Date: 2026-07-03 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_departments",
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_employee_departments_department_id",
        "employee_departments",
        ["department_id"],
    )

    # Preserve every employee's existing department before removing the
    # legacy single-department column.
    op.execute(
        """
        INSERT INTO employee_departments (employee_id, department_id)
        SELECT id, department_id
        FROM employees
        WHERE department_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )

    op.drop_index("ix_employees_department_id", table_name="employees")
    op.drop_constraint(
        "employees_department_id_fkey", "employees", type_="foreignkey"
    )
    op.drop_column("employees", "department_id")


def downgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "employees_department_id_fkey",
        "employees",
        "departments",
        ["department_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_employees_department_id", "employees", ["department_id"]
    )

    # A downgrade can only retain one of an employee's departments. Choose a
    # deterministic value so the operation remains reproducible.
    op.execute(
        """
        UPDATE employees AS employee
        SET department_id = membership.department_id
        FROM (
            SELECT employee_id, MIN(department_id::text)::uuid AS department_id
            FROM employee_departments
            GROUP BY employee_id
        ) AS membership
        WHERE employee.id = membership.employee_id
        """
    )

    op.drop_index(
        "ix_employee_departments_department_id",
        table_name="employee_departments",
    )
    op.drop_table("employee_departments")

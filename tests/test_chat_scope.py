# tests/test_chat_scope.py
"""Regression tests for the chat agent scope path after the single->multi
department migration (commit 3504060). The chat router/agent must use the
many-to-many department API (`department_ids`), not the removed singular
`Employee.department` / `employee.department_id`.
"""
import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock


def test_employee_has_no_singular_department():
    """Documents why chat.py must eager-load `employee_departments`: the
    singular relationship/column the old code referenced no longer exists."""
    from app.database.models import Employee

    assert hasattr(Employee, "employee_departments")
    assert not hasattr(Employee, "department")
    assert not hasattr(Employee, "department_id")


@pytest.mark.asyncio
async def test_get_scope_resolves_all_departments():
    """_get_scope must read the employee's M:N departments and expose them as
    the plural `department_ids`, not crash on the removed `department_id`."""
    from app.services.chat_agent import _get_scope
    from app.database.models import Employee, EmployeeDepartment

    d1, d2 = uuid.uuid4(), uuid.uuid4()
    emp = Employee(id=uuid.uuid4(), name="Tester", email="t@example.com", role="employee")
    emp.custom_role_id = None
    emp.employee_departments = [
        EmployeeDepartment(employee_id=emp.id, department_id=d1),
        EmployeeDepartment(employee_id=emp.id, department_id=d2),
    ]

    db = AsyncMock()
    proj_result = MagicMock()
    proj_result.all.return_value = []  # no project memberships
    db.execute = AsyncMock(return_value=proj_result)

    scope = await _get_scope(db, emp)

    assert set(scope["department_ids"]) == {str(d1), str(d2)}
    assert "department_id" not in scope  # old singular key must be gone


def test_make_identity_is_accepted_by_apply_scope_filter():
    """The identity chat builds for source tools must expose the fields
    apply_scope_filter reads (notably project_source_ids)."""
    from sqlalchemy import select

    from app.services.chat_agent import _make_identity
    from app.services.mcp_auth_service import apply_scope_filter
    from app.database.models import Source

    scope = {
        "is_admin": False,
        "department_ids": [str(uuid.uuid4())],
        "project_ids": [],
        "allowed_knowledge_types": ["policies"],
        "employee_id": str(uuid.uuid4()),
        "allowed_source_ids": None,
    }

    identity = _make_identity(scope)
    stmt = apply_scope_filter(select(Source), identity)  # must not raise
    assert stmt is not None

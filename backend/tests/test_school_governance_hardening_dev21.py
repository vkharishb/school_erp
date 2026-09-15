from pathlib import Path


SCHOOLS_API = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "schools.py"


def _source() -> str:
    return SCHOOLS_API.read_text(encoding="utf-8")


def test_school_lifecycle_uses_shared_platform_owner_dependency() -> None:
    source = _source()
    for fn_name in ("set_school_status", "archive_school", "restore_school"):
        start = source.index(f"async def {fn_name}(")
        next_route = source.find("\n@router.", start + 1)
        block = source[start:] if next_route == -1 else source[start:next_route]
        assert "Depends(get_current_active_superuser)" in block
        assert "if not user.is_superuser" not in block


def test_create_school_locks_organization_before_capacity_check() -> None:
    source = _source()
    helper_start = source.index("async def _lock_and_check_school_capacity(")
    create_start = source.index("async def create_school(")
    helper = source[helper_start:create_start]
    next_route = source.find("\n@router.", create_start + 1)
    create_block = source[create_start:] if next_route == -1 else source[create_start:next_route]

    lock_position = helper.index(".with_for_update()")
    count_position = helper.index("select(func.count(School.id))")
    limit_position = helper.index("if projected > limit")

    assert lock_position < count_position < limit_position
    assert "select(Organization)" in helper[:count_position]
    assert "select(OrganizationSubscription)" in helper[:count_position]
    assert "_lock_and_check_school_capacity(" in create_block

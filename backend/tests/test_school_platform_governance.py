from app.schemas.school import SchoolLifecycleAction, SchoolUpdate


def test_school_lifecycle_reason_schema():
    assert SchoolUpdate(is_active=False, reason="Governance action").reason == "Governance action"
    assert SchoolLifecycleAction(reason="Archive after lifecycle").reason == "Archive after lifecycle"

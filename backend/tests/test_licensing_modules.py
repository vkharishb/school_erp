from app.services.licensing import IMPLEMENTED_MODULES, PHASE1_MODULES
from app.services.subscriptions import effective_modules


class _Plan:
    def __init__(self, modules):
        self.enabled_modules = modules


def test_school_config_is_a_phase1_implemented_module():
    assert "school_config" in PHASE1_MODULES
    assert "school_config" in IMPLEMENTED_MODULES


def test_subscription_has_no_mandatory_core_module_injection():
    plan = _Plan(["student", "fee"])
    assert effective_modules(plan, trial=False) == ["fee", "student"]


def test_unimplemented_catalog_modules_stay_locked_until_delivered():
    plan = _Plan(["student", "communication"])
    assert effective_modules(plan, trial=False) == ["student"]

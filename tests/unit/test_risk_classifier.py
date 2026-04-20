import pytest
from src.guardrail.models import ActionPlan, ActionTarget, ActionRequester, ActionType, RiskTier
from src.guardrail.risk_classifier import RiskClassifier, ClassificationResult

_REQUESTER = ActionRequester(user_id="U1", org_role="admin", task_source="cli")


def _plan(action_type, host="server-01", scope="single", count=1, command="", **kwargs) -> ActionPlan:
    return ActionPlan(
        task_id="00000000-0000-0000-0000-000000000001",
        action_type=action_type,
        target=ActionTarget(host=host, scope=scope, count=count),
        parameters={"command": command} if command else {},
        requested_by=_REQUESTER,
        **kwargs,
    )


@pytest.fixture
def classifier():
    return RiskClassifier.from_yaml("config/guardrail_rules.yaml")


# ── YAML rules: HIGH ────────────────────────────────────────────────────────

def test_bulk_ad_deprovision_is_high(classifier):
    result = classifier.classify(_plan(ActionType.AD_DEPROVISION, scope="bulk", count=50))
    assert result.tier == RiskTier.HIGH
    assert result.method == "rules"


def test_destructive_ssh_rm_is_high(classifier):
    result = classifier.classify(_plan(ActionType.SSH_EXEC, command="rm -rf /var/logs"))
    assert result.tier == RiskTier.HIGH
    assert result.method == "rules"


def test_destructive_ssh_drop_is_high(classifier):
    result = classifier.classify(_plan(ActionType.SSH_EXEC, command="drop table users"))
    assert result.tier == RiskTier.HIGH


def test_vault_write_is_high(classifier):
    result = classifier.classify(_plan(ActionType.VAULT_WRITE))
    assert result.tier == RiskTier.HIGH
    assert result.method == "rules"


# ── YAML rules: MEDIUM ──────────────────────────────────────────────────────

def test_ssh_on_prod_host_is_medium(classifier):
    result = classifier.classify(_plan(ActionType.SSH_EXEC, host="db-prod-01", command="systemctl status"))
    assert result.tier == RiskTier.MEDIUM
    assert result.method == "rules"


def test_backup_trigger_is_medium(classifier):
    result = classifier.classify(_plan(ActionType.BACKUP_TRIGGER))
    assert result.tier == RiskTier.MEDIUM


def test_ad_provision_is_medium(classifier):
    result = classifier.classify(_plan(ActionType.AD_PROVISION))
    assert result.tier == RiskTier.MEDIUM


def test_single_ad_deprovision_is_medium(classifier):
    result = classifier.classify(_plan(ActionType.AD_DEPROVISION, scope="single"))
    assert result.tier == RiskTier.MEDIUM


def test_ldap_modify_is_medium(classifier):
    result = classifier.classify(_plan(ActionType.LDAP_MODIFY))
    assert result.tier == RiskTier.MEDIUM


# ── YAML rules: LOW ─────────────────────────────────────────────────────────

def test_vault_read_is_low(classifier):
    result = classifier.classify(_plan(ActionType.VAULT_READ))
    assert result.tier == RiskTier.LOW
    assert result.method == "rules"


def test_ssh_on_dev_host_is_low(classifier):
    result = classifier.classify(_plan(ActionType.SSH_EXEC, host="web-dev-01", command="ls /tmp"))
    assert result.tier == RiskTier.LOW


def test_ssh_on_staging_host_is_low(classifier):
    result = classifier.classify(_plan(ActionType.SSH_EXEC, host="app-staging-02", command="ps aux"))
    assert result.tier == RiskTier.LOW


# ── Heuristics ──────────────────────────────────────────────────────────────

def test_bulk_scope_heuristic_escalates_to_medium(classifier):
    # ssh_exec on a non-prod, non-dev host with no destructive command and bulk scope
    result = classifier.classify(_plan(ActionType.SSH_EXEC, host="internal-server", scope="bulk", count=20, command="df -h"))
    assert result.tier >= RiskTier.MEDIUM  # bulk + count>10 → at least MEDIUM via heuristics or rules


def test_count_over_10_heuristic_escalates(classifier):
    result = classifier.classify(_plan(ActionType.SSH_EXEC, host="internal-server", scope="bulk", count=15, command="df -h"))
    assert result.tier == RiskTier.HIGH  # bulk(MEDIUM) + count>10 escalates to HIGH


def test_prod_host_heuristic_minimum_medium(classifier):
    result = classifier.classify(_plan(ActionType.SSH_EXEC, host="internal-prod-server", command="uptime"))
    # "prod" in host → minimum MEDIUM via YAML rules (target_pattern: prod)
    assert result.tier == RiskTier.MEDIUM


def test_classification_result_has_reason(classifier):
    result = classifier.classify(_plan(ActionType.VAULT_WRITE))
    assert isinstance(result.reason, str)
    assert len(result.reason) > 0

# tests/unit/test_rules.py
import pytest
from src.router.rules import RuleEngine, RuleMatch


@pytest.fixture
def engine():
    return RuleEngine.from_yaml("config/classification_rules.yaml")


def test_local_ad_password_reset(engine):
    assert engine.classify("Reset Alice's AD password") == RuleMatch.LOCAL


def test_local_ssh(engine):
    assert engine.classify("SSH into db-prod and check disk") == RuleMatch.LOCAL


def test_local_backup(engine):
    assert engine.classify("Run backup job on server-02") == RuleMatch.LOCAL


def test_local_provision_user(engine):
    assert engine.classify("Provision new user account in AD") == RuleMatch.LOCAL


def test_local_audit_log(engine):
    assert engine.classify("Show me the audit log for user jsmith") == RuleMatch.LOCAL


def test_cloud_vpn_guide(engine):
    assert engine.classify("What's our VPN setup guide?") == RuleMatch.CLOUD


def test_cloud_wifi_issue(engine):
    assert engine.classify("My laptop can't connect to WiFi") == RuleMatch.CLOUD


def test_cloud_doc_request(engine):
    assert engine.classify("How do I submit an IT request?") == RuleMatch.CLOUD


def test_ambiguous_server_logs_returns_none(engine):
    assert engine.classify("Check server logs") is None


def test_ambiguous_onboarding_returns_none(engine):
    assert engine.classify("Help me with onboarding") is None


def test_case_insensitive_local(engine):
    assert engine.classify("RESET my AD PASSWORD") == RuleMatch.LOCAL


def test_case_insensitive_cloud(engine):
    assert engine.classify("VPN GUIDE PLEASE") == RuleMatch.CLOUD

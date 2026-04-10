# tests/unit/test_classifier.py
import pytest
from src.router.classifier import Classifier, ClassificationResult


@pytest.fixture
def classifier():
    return Classifier.from_config("config/classification_rules.yaml")


# ── Golden dataset (CI-blocking) ────────────────────────────────────────────

def test_golden_reset_ad_password(classifier):
    result = classifier.classify("Reset Alice's AD password")
    assert result.route == "local"


def test_golden_backup_job(classifier):
    result = classifier.classify("Run backup job on server-02")
    assert result.route == "local"


def test_golden_ssh(classifier):
    result = classifier.classify("SSH into db-prod and check disk")
    assert result.route == "local"


def test_golden_vpn_guide(classifier):
    result = classifier.classify("What's our VPN setup guide?")
    assert result.route == "cloud"


def test_golden_wifi_issue(classifier):
    result = classifier.classify("My laptop can't connect to WiFi")
    assert result.route == "cloud"


def test_golden_ambiguous_server_logs_is_failsafe_local(classifier):
    """Ambiguous input MUST route LOCAL — security boundary."""
    result = classifier.classify("Check server logs")
    assert result.route == "local"
    assert result.method == "failsafe"


def test_golden_ambiguous_onboarding_is_failsafe_local(classifier):
    result = classifier.classify("Help me with onboarding")
    assert result.route == "local"
    assert result.method == "failsafe"


def test_golden_secret_in_payload_still_local(classifier):
    """Classifier itself doesn't scan; payload scanner handles this upstream."""
    result = classifier.classify("password=abc123 not working")
    # 'password' triggers local credential rule
    assert result.route == "local"


# ── Method tracking ─────────────────────────────────────────────────────────

def test_rule_match_sets_rules_method(classifier):
    result = classifier.classify("SSH into server-01")
    assert result.method == "rules"


def test_failsafe_sets_failsafe_method(classifier):
    result = classifier.classify("what should i do about the thing")
    assert result.method == "failsafe"
    assert result.route == "local"


def test_classification_result_has_confidence(classifier):
    result = classifier.classify("SSH into db-prod")
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0

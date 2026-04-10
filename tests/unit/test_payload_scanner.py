# tests/unit/test_payload_scanner.py
import pytest
from src.router.payload_scanner import PayloadScanner, ScanResult


@pytest.fixture
def scanner():
    return PayloadScanner()


def test_clean_text_passes(scanner):
    assert scanner.scan("My laptop can't connect to WiFi") == ScanResult.CLEAN


def test_password_equals_detected(scanner):
    assert scanner.scan("password=abc123") == ScanResult.SENSITIVE


def test_password_json_field_detected(scanner):
    assert scanner.scan('{"password": "hunter2"}') == ScanResult.SENSITIVE


def test_api_key_detected(scanner):
    assert scanner.scan("api_key=sk-abc1234567890") == ScanResult.SENSITIVE


def test_bearer_token_detected(scanner):
    assert scanner.scan("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc.def") == ScanResult.SENSITIVE


def test_private_key_pem_detected(scanner):
    assert scanner.scan("-----BEGIN RSA PRIVATE KEY-----") == ScanResult.SENSITIVE


def test_aws_access_key_detected(scanner):
    assert scanner.scan("AKIAIOSFODNN7EXAMPLE") == ScanResult.SENSITIVE


def test_secret_colon_detected(scanner):
    assert scanner.scan("secret: mysupersecretvalue") == ScanResult.SENSITIVE


def test_empty_string_is_clean(scanner):
    assert scanner.scan("") == ScanResult.CLEAN


def test_normal_it_request_clean(scanner):
    assert scanner.scan("How do I connect to the VPN from home?") == ScanResult.CLEAN

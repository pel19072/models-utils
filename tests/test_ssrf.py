"""Tests for the shared SSRF guard (SEC-6). Uses numeric hosts so no DNS is needed."""
import pytest

from database_utils.utils.ssrf import validate_url_no_ssrf, SSRFValidationError


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8080/x",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://something.internal/",
        "http://127.0.0.1/",
        "http://10.0.0.5/admin",
        "http://192.168.1.1/",
        "http://172.16.5.4/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "",
        "not-a-url",
    ],
)
def test_blocked(url):
    with pytest.raises(SSRFValidationError):
        validate_url_no_ssrf(url)


def test_public_ip_allowed():
    assert validate_url_no_ssrf("http://8.8.8.8/") == "8.8.8.8"

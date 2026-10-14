import pytest

from filmwright.demo.guard import check_url


@pytest.mark.parametrize("url", [
    "http://localhost:3000", "http://127.0.0.1:8765/x", "https://app.localhost", "https://shop.test",
    "https://acme.example", "https://dev.myapp.io", "https://myapp-staging.io", "https://preview-42.myapp.app",
])
def test_test_environments_are_allowed(url):
    check_url(url)


@pytest.mark.parametrize("url", ["https://prod.myapp.io", "https://myapp.io", "https://www.bigcompany.com", "file:///etc"])
def test_production_looking_hosts_are_refused(url):
    with pytest.raises(SystemExit):
        check_url(url)


def test_allow_hosts_overrides():
    check_url("https://myapp.io/login", ["myapp.io"])

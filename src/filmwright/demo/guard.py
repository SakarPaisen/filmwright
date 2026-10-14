"""Environment allowlist shared by login.py and run_scenarios.py.

filmwright drives a logged-in browser and can change data, so by default it only runs against test environments:
localhost / 127.0.0.1 / *.localhost / *.test / *.example, hosts the person explicitly allows, and hostnames containing
"playground", "dev", "sandbox", "staging" or "preview". Anything that looks like production ("prod", or a bare
company domain) is refused unless it is listed under allow_hosts; record production only read-only, with a demo
account, and with the site owner's permission.
"""

from __future__ import annotations

import sys
from urllib.parse import urlparse

_TEST_WORDS = ("playground", "dev.", "-dev", "sandbox", "staging", "preview", "localhost", ".test")
_LOCAL = {"localhost", "127.0.0.1", "::1"}


def check_url(url: str, allow_hosts: list[str] | None = None) -> None:
    host = (urlparse(url).hostname or "").lower()
    allow = {h.lower() for h in (allow_hosts or [])}
    if not host:
        sys.exit(f"Refusing: '{url}' has no hostname.")
    if host in allow:
        return
    if "prod" in host:
        sys.exit(f"Refusing: '{host}' looks like production. filmwright only runs against test environments unless the host is listed under allow_hosts.")
    if host in _LOCAL or host.endswith((".localhost", ".test", ".example")):
        return
    if any(w in host for w in _TEST_WORDS):
        return
    sys.exit(
        f"Refusing: '{host}' is not a recognised test environment. If it really is one (e.g. a preview "
        f"deployment's CDN domain), list it under allow_hosts in the scenario file or pass --allow-host {host}."
    )

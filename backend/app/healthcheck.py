"""Container readiness probe with the configured public Host header."""

import urllib.request
from urllib.parse import urlsplit
from app.config import get_settings


def main():
    settings = get_settings()
    request = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/health",
        headers={"Host": urlsplit(settings.public_base_url).netloc},
    )
    # Loopback must not be sent through a host proxy configured in the environment.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=3) as response:
        if response.status != 200:
            raise SystemExit(1)


if __name__ == "__main__":
    main()

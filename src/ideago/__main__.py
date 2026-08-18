"""Entry point for running the IdeaGo server.

Usage: uv run python -m ideago
"""

import uvicorn

from ideago.api.app import create_app
from ideago.config.settings import get_settings


def _forwarded_allow_ips(settings) -> str | list[str]:  # type: ignore[no-untyped-def]
    getter = getattr(settings, "get_forwarded_allow_ips", None)
    return getter() if callable(getter) else "127.0.0.1"


def main() -> None:
    settings = get_settings()
    app = create_app()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        # Behind a reverse proxy, uvicorn only trusts X-Forwarded-* from
        # 127.0.0.1 by default. In Docker the proxy is a different container
        # with a different address, so the headers were ignored and
        # request.client.host resolved to the proxy. That silently poisoned
        # audit-log IPs and the remoteip passed to Turnstile.
        proxy_headers=getattr(settings, "trust_proxy_headers", True),
        forwarded_allow_ips=_forwarded_allow_ips(settings),
    )


if __name__ == "__main__":
    main()

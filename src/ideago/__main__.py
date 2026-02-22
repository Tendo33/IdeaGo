"""Entry point for running the IdeaGo server.

Usage: uv run python -m ideago
"""

import uvicorn

from ideago.api.app import create_app
from ideago.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    app = create_app()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()

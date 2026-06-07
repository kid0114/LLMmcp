#!/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.responses import HealthResponse
from shared.settings import get_settings

if __name__ == "__main__":
    settings = get_settings()
    response = HealthResponse(message="phase 1 services configured", service="llmmcp")
    print(response.model_dump_json())
    print(
        " ".join(
            [
                f"host={settings.host}",
                f"port={settings.port}",
                f"env={settings.environment}",
                f"http_timeout={settings.http_timeout}",
                f"browser_timeout={settings.browser_timeout}",
                f"browser_headless={settings.browser_headless}",
            ]
        )
    )

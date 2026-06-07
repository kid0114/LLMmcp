#!/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python

import sys
from importlib import import_module
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

mcp = import_module("servers.time.server").mcp


if __name__ == "__main__":
    mcp.run()

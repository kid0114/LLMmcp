#!/opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from openai_tools.web_tools import execute_openai_tool


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: run_openai_tool.py <tool_name> '<json_arguments>'", file=sys.stderr)
        return 2

    tool_name = sys.argv[1]
    try:
        arguments = json.loads(sys.argv[2])
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON arguments: {exc}", file=sys.stderr)
        return 2

    result = execute_openai_tool(tool_name, arguments)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Entry point for the genomics MCP server (`python -m sciagent.mcp_servers.genomics`)."""

from __future__ import annotations

import sys

from sciagent.mcp_servers.__main__ import main

if __name__ == "__main__":
    sys.argv.insert(1, "genomics")
    main()

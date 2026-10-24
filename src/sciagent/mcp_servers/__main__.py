"""Run an MCP server: ``python -m sciagent.mcp_servers imaging --port 8101``."""

from __future__ import annotations

import argparse

from sciagent.core.logging import configure_logging
from sciagent.mcp_servers.factory import SERVER_NAMES, build_server


def main() -> None:
    parser = argparse.ArgumentParser(prog="sciagent-mcp")
    parser.add_argument("server", choices=SERVER_NAMES)
    parser.add_argument(
        "--transport", default="streamable-http", choices=["stdio", "streamable-http"]
    )
    parser.add_argument("--host", default="0.0.0.0")  # noqa: S104 - binds inside the pod
    parser.add_argument("--port", type=int, default=8101)
    args = parser.parse_args()
    configure_logging()
    server = build_server(args.server)
    if args.transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host=args.host, port=args.port, stateless_http=True)


if __name__ == "__main__":
    main()

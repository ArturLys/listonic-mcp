"""Launch parameters and the console entry point."""

import argparse
import logging
import os
import sys

from . import __version__, tools  # noqa: F401  (importing tools registers them)
from .app import mcp, set_client
from .client import ListonicClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="listonic-mcp", description="Unofficial Listonic (grocery list) MCP server."
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "--email", default=os.environ.get("LISTONIC_EMAIL"),
        help="Listonic account email. Falls back to the LISTONIC_EMAIL env var.",
    )
    p.add_argument(
        "--password", default=os.environ.get("LISTONIC_PASSWORD"),
        help="Listonic account password. Falls back to LISTONIC_PASSWORD.",
    )
    p.add_argument(
        "--list-id", default=os.environ.get("LISTONIC_LIST_ID", ""),
        help="Pin a default list id (see get_lists). Falls back to LISTONIC_LIST_ID; "
             "empty = the account's first list.",
    )
    args, _ = p.parse_known_args()
    return args


def main() -> None:
    """Console entry point (``listonic-mcp``) and ``python server.py`` launcher."""
    args = _parse_args()
    if args.email and args.password:
        set_client(ListonicClient(args.email, args.password, args.list_id))
        status = f"account {args.email}" + (
            f", pinned list {args.list_id}" if args.list_id else ", default = first list"
        )
    else:
        status = "no credentials — tools will report this until restarted with --email/--password"
    print(f"listonic-mcp · {status}", file=sys.stderr)
    mcp.run()

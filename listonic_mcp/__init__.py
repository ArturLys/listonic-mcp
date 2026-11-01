"""listonic-mcp — unofficial Listonic (grocery list) MCP server.

Unofficial: not affiliated with Listonic. The API is reverse-engineered (see
API.md); the embedded client id/secret in client.py are the web app's own
public ones, not personal credentials.

Layout: client.py (HTTP/wire format) · app.py (FastMCP + tool conventions) ·
tools/ (one module per group of tools) · cli.py (launch params, entry point).
"""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("listonic-mcp")
except PackageNotFoundError:  # running from a source checkout, not installed
    __version__ = "0.0.0-dev"

from .cli import main  # noqa: E402  (after __version__: cli imports it)

__all__ = ["main", "__version__"]

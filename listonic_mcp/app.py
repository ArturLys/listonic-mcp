"""The shared FastMCP instance plus the conventions every tool follows.

Tool modules in ``listonic_mcp/tools/`` register themselves with the ``tool``
decorator below; nothing else in this file needs to change to add one.
"""

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .client import ListonicClient

SERVER_INSTRUCTIONS = """\
This server manages the user's real grocery lists on Listonic (a shopping-list app).

Reading a list: checked items ([x]) are things the user most likely already HAS at
home; unchecked items ([ ]) still need to be bought. Keep that in mind when meal
planning or answering "what do I need?".

Habits that make you useful here:
- Batch your changes: add_items / edit_items / delete_items all take lists — one
  call for the whole recipe, not one call per ingredient.
- Before editing or deleting, call get_items to grab current ItemIDs.
- When the user plans meals, offer to put the missing ingredients straight on the
  list — that's the whole point of having hands.
"""

NO_CREDS = (
    "listonic-mcp was started without credentials — restart it with --email and "
    "--password (or set LISTONIC_EMAIL / LISTONIC_PASSWORD). These are your normal "
    "Listonic account login details."
)

mcp = FastMCP("listonic", instructions=SERVER_INSTRUCTIONS)

# Built in cli.main() from the launch params, so importing this package never
# needs credentials (registry introspection, console entry point).
_client: ListonicClient | None = None


def set_client(client: ListonicClient | None) -> None:
    global _client
    _client = client


def get_client() -> ListonicClient:
    """The logged-in client. Raising makes FastMCP return an isError result."""
    if _client is None:
        raise RuntimeError(NO_CREDS)
    return _client


def resolve_list(list_id: str = "") -> tuple[ListonicClient, str]:
    """Client + the list to act on: ``list_id`` if given, else the default list."""
    client = get_client()
    return client, list_id.strip() or client.default_list_id()


def tool(title: str, *, read_only: bool = False, destructive: bool = False,
         idempotent: bool = False):
    """Register an MCP tool with its annotations (clients use them for confirmation UI).

    - read_only:   never changes the account.
    - destructive: removes or irreversibly changes data (items deleted, list removed).
    - idempotent:  repeating the same call has no further effect.
    Anything outward-facing (e.g. notifying another person) should additionally
    require a ``confirm: bool = False`` argument and return a preview without it.
    """
    return mcp.tool(
        title=title,
        annotations=ToolAnnotations(
            title=title,
            readOnlyHint=read_only,
            destructiveHint=False if read_only else destructive,
            idempotentHint=read_only or idempotent,
            openWorldHint=True,
        ),
    )

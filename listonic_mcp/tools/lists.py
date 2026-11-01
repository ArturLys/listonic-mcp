"""Tools that operate on whole lists."""

from ..app import get_client, tool


@tool("Get lists", read_only=True)
def get_lists() -> str:
    """All shopping lists on the account, with their ListIDs.

    Use when the user has several lists ("weekend BBQ", "pharmacy") — every other
    tool takes an optional list_id to target one; without it they use the default
    list (the pinned --list-id, or the account's first list).
    """
    client = get_client()
    all_lists = client.lists()
    if not all_lists:
        return "No lists on this account — create one in the Listonic app first."
    default = client.default_list_id()
    return "\n".join(
        f"(ListID: {l.get('Id')}) {l.get('Name', '?')}"
        + ("  ← default" if str(l.get("Id")) == default else "")
        for l in all_lists
    )

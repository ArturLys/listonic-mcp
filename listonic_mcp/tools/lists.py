"""Tools that operate on whole lists.

List-level changes take an explicit ``list_id`` (no silent fallback to the default
list): renaming or removing the wrong list is worse than asking for the id.
"""

from typing import Literal

import requests

from ..app import find_list, get_client, tool

SORT_MODES = {"categories": 0, "alphabetical": 1}


def _name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("The list name can't be empty.")
    return name


@tool("Get lists", read_only=True)
def get_lists() -> str:
    """All shopping lists on the account, with their ListIDs.

    Use when the user has several lists ("weekend BBQ", "pharmacy") — item tools
    take an optional list_id to target one; without it they use the default
    list (the pinned --list-id, or the account's first list).
    """
    client = get_client()
    all_lists = client.lists()
    if not all_lists:
        return "No lists on this account — create one with create_list."
    default = client.default_list_id()
    return "\n".join(
        f"(ListID: {l.get('Id')}) {l.get('Name', '?')}"
        + ("  ← default" if str(l.get("Id")) == default else "")
        for l in all_lists
    )


@tool("Create list")
def create_list(name: str) -> str:
    """Create a new, empty, private shopping list.

    Args:
        name: the list's name, e.g. "Weekend BBQ".
    """
    created = get_client().create_list(_name(name))
    return f"Created '{created.get('Name')}' (ListID: {created.get('Id')})."


@tool("Rename list", idempotent=True)
def rename_list(list_id: str, name: str) -> str:
    """Rename a list.

    Args:
        list_id: the list to rename (from get_lists).
        name: the new name.
    """
    client = get_client()
    old = find_list(client, list_id)
    client.update_list(list_id.strip(), Name=_name(name))
    return f"Renamed '{old.get('Name')}' to '{name.strip()}'."


@tool("Delete list", destructive=True, idempotent=True)
def delete_list(list_id: str, confirm: bool = False) -> str:
    """Remove a whole list together with its items. Without confirm=true this only
    previews what would be removed: show that to the user and get their explicit
    OK before calling again with confirm=true.

    Args:
        list_id: the list to remove (from get_lists).
        confirm: must be true to actually remove it.
    """
    client = get_client()
    target = find_list(client, list_id)
    summary = f"'{target.get('Name')}' ({target.get('ItemsCount', '?')} item(s))"
    if not confirm:
        return (f"Not deleted yet. This would remove the list {summary}. "
                "Call again with confirm=true after the user agrees.")
    client.update_list(list_id.strip(), Active=0)
    return f"Deleted the list {summary}."


@tool("Copy list")
def copy_list(
    list_id: str,
    name: str = "",
    items: Literal["all", "unpurchased", "purchased"] = "all",
) -> str:
    """Copy a list (or part of it) into a new list. Copied items start unchecked,
    ready for a new shopping run.

    Args:
        list_id: the list to copy (from get_lists).
        name: name of the copy. Empty = "<original name> - copy".
        items: which items to copy — all, only unpurchased (unchecked) or only purchased (checked).
    """
    client = get_client()
    source = find_list(client, list_id)
    wanted = {"all": None, "unpurchased": "0", "purchased": "1"}[items]
    to_copy = [
        i for i in client.items(list_id.strip())
        if wanted is None or str(i.get("Checked")) == wanted
    ]
    created = client.create_list(name.strip() or f"{source.get('Name')} - copy")
    failed = 0
    for i in to_copy:
        try:
            client.add_item(str(created.get("Id")), i.get("Name", ""), i.get("Amount", ""),
                            i.get("Unit", ""), i.get("Description", ""))
        except requests.exceptions.RequestException:
            failed += 1
    msg = (f"Copied {len(to_copy) - failed} item(s) from '{source.get('Name')}' into "
           f"'{created.get('Name')}' (ListID: {created.get('Id')}).")
    return msg + (f" {failed} item(s) failed to copy." if failed else "")


@tool("Set list sort mode", idempotent=True)
def set_sort_mode(list_id: str, mode: Literal["categories", "alphabetical"]) -> str:
    """Choose how a list is ordered in the Listonic app.

    Args:
        list_id: the list (from get_lists).
        mode: "categories" (grouped by store aisle) or "alphabetical".
    """
    client = get_client()
    target = find_list(client, list_id)
    client.update_list(list_id.strip(), SortMode=SORT_MODES[mode])
    return f"'{target.get('Name')}' is now sorted {mode}."

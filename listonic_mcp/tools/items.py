"""Tools that operate on items of a list."""

import requests
from pydantic import BaseModel, Field

from ..app import resolve_list, tool


def fmt_items(items: list[dict]) -> str:
    if not items:
        return "The list is currently empty."
    out = []
    for item in items:
        checked = "[x]" if str(item.get("Checked")) == "1" else "[ ]"
        what = " ".join(filter(None, (item.get("Amount"), item.get("Unit"), item.get("Name"))))
        line = f"{checked} (ItemID: {item.get('Id', '')}) {what}"
        if item.get("Description"):
            line += f" — {item['Description']}"
        out.append(line)
    return "\n".join(out)


@tool("Get list items", read_only=True)
def get_items(list_id: str = "") -> str:
    """Fetch the grocery list. Call this FIRST before editing/deleting, to get ItemIDs.

    Checked items ([x]) = the user most likely already HAS them at home.
    Unchecked items ([ ]) = still to buy.

    Args:
        list_id: which list (from get_lists). Empty = the default list.
    """
    client, lid = resolve_list(list_id)
    return fmt_items(client.items(lid))


class AddItemParams(BaseModel):
    name: str = Field(description="The name of the item to add")
    quantity: str = Field(default="1", description="The quantity of the item")
    unit: str = Field(default="", description="The unit (e.g. 'kg', 'liters', 'pieces')")
    note: str = Field(default="", description="Optional note shown under the item")


@tool("Add items")
def add_items(items: list[AddItemParams], list_id: str = "") -> str:
    """Add one or MANY items in a single call — batch whole recipes, don't loop.

    Args:
        items: the items to add.
        list_id: which list (from get_lists). Empty = the default list.
    """
    client, lid = resolve_list(list_id)
    results = []
    for item in items:
        if not item.name.strip():
            results.append("Failed: missing 'name'.")
            continue
        try:
            client.add_item(lid, item.name, item.quantity, item.unit, item.note)
            results.append(f"Added '{item.name}'.")
        except requests.exceptions.RequestException as e:
            results.append(f"Failed to add '{item.name}': {e}")
    return "\n".join(results)


class EditItemParams(BaseModel):
    item_id: str = Field(description="The ItemID to edit (from get_items)")
    is_checked: bool | None = Field(
        default=None, description="true = check off (user has it), false = uncheck"
    )
    name: str | None = Field(default=None, description="New name for the item")
    quantity: str | None = Field(default=None, description="New quantity")
    unit: str | None = Field(default=None, description="New unit")
    note: str | None = Field(default=None, description="New note (empty string clears it)")


@tool("Edit items", idempotent=True)
def edit_items(items: list[EditItemParams], list_id: str = "") -> str:
    """Edit one or MANY items in a single call — most often to check/uncheck while
    shopping ("got the milk").

    Args:
        items: edits to apply; only the fields you set are changed.
        list_id: which list (from get_lists). Empty = the default list.
    """
    client, lid = resolve_list(list_id)
    results = []
    for item in items:
        fields = {
            api_name: value
            for api_name, value in (
                ("Checked", None if item.is_checked is None else int(item.is_checked)),
                ("Name", item.name),
                ("Amount", item.quantity),
                ("Unit", item.unit),
                ("Description", item.note),
            )
            if value is not None
        }
        if not fields:
            results.append(f"No changes given for item {item.item_id}.")
            continue
        try:
            client.update_item(lid, item.item_id, **fields)
            results.append(f"Updated item {item.item_id}.")
        except requests.exceptions.RequestException as e:
            results.append(f"Failed to update item {item.item_id}: {e}")
    return "\n".join(results)


@tool("Delete items", destructive=True, idempotent=True)
def delete_items(item_ids: list[str], list_id: str = "") -> str:
    """Delete items entirely (not check off — that's edit_items with is_checked).

    Args:
        item_ids: ItemIDs to delete (from get_items).
        list_id: which list (from get_lists). Empty = the default list.
    """
    client, lid = resolve_list(list_id)
    if not item_ids:
        return "No item_ids given."
    client.delete_items(lid, item_ids)
    return f"Deleted {len(item_ids)} item(s)."

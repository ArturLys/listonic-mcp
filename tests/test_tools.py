import asyncio

import pytest
import requests

from conftest import FakeResponse
from listonic_mcp import app
from listonic_mcp.tools import items, lists

EXPECTED = {
    # name: (readOnly, destructive, idempotent)
    "get_lists": (True, False, True),
    "create_list": (False, False, False),
    "rename_list": (False, False, True),
    "delete_list": (False, True, True),
    "copy_list": (False, False, False),
    "set_sort_mode": (False, False, True),
    "get_items": (True, False, True),
    "add_items": (False, False, False),
    "edit_items": (False, False, True),
    "delete_items": (False, True, True),
    "check_all": (False, False, True),
    "uncheck_all": (False, False, True),
    "delete_checked": (False, True, True),
}


def test_registered_tools_carry_annotations():
    tools = {t.name: t for t in asyncio.run(app.mcp.list_tools())}
    assert set(tools) == set(EXPECTED)
    for name, (ro, destructive, idem) in EXPECTED.items():
        a = tools[name].annotations
        assert (a.readOnlyHint, a.destructiveHint, a.idempotentHint) == (ro, destructive, idem), name
        assert a.title and tools[name].description


def test_no_credentials_is_an_error_result():
    app.set_client(None)
    with pytest.raises(Exception, match="without credentials"):
        asyncio.run(app.mcp.call_tool("get_lists", {}))


def test_get_items_formats_and_uses_pinned_list(client, api):
    api.replies.append(FakeResponse(200, [
        {"Id": "1", "Name": "mleko", "Amount": "2", "Unit": "l", "Checked": 0, "Description": "3.2%"},
        {"Id": "2", "Name": "chleb", "Amount": "", "Unit": "", "Checked": 1},
    ]))
    out = items.get_items()
    assert out == "[ ] (ItemID: 1) 2 l mleko — 3.2%\n[x] (ItemID: 2) chleb"
    assert api.requests() == [("GET", "/lists/42/items", None)]


def test_explicit_list_id_overrides_default(client, api):
    items.get_items(list_id=" 7 ")
    assert api.requests()[0][1] == "/lists/7/items"


def test_default_list_falls_back_to_first_list(api):
    from listonic_mcp.client import ListonicClient
    app.set_client(ListonicClient("a", "b"))
    api.replies.append(FakeResponse(200, [{"Id": 9, "Name": "A"}, {"Id": 10, "Name": "B"}]))
    items.get_items()
    assert [r[1] for r in api.requests()][-1] == "/lists/9/items"
    app.set_client(None)


def test_add_items_sends_the_apps_payload_shape(client, api):
    out = items.add_items([items.AddItemParams(name="mleko", quantity="2", unit="l", note="UHT")])
    assert out == "Added 'mleko'."
    (method, path, body), = api.requests()
    assert (method, path) == ("POST", "/lists/42/items")
    assert body["Name"] == "mleko" and body["Amount"] == "2" and body["Unit"] == "l"
    assert body["Description"] == "UHT" and body["Checked"] == 0


def test_add_items_reports_per_item_failures(client, api):
    api.replies += [FakeResponse(500), FakeResponse(201, {})]
    out = items.add_items([items.AddItemParams(name="a"), items.AddItemParams(name="b")])
    first, second = out.splitlines()
    assert first.startswith("Failed to add 'a'") and second == "Added 'b'."


def test_add_items_rejects_blank_name(client, api):
    assert items.add_items([items.AddItemParams(name="  ")]) == "Failed: missing 'name'."
    assert api.requests() == []


def test_edit_items_sends_only_changed_fields_with_api_names(client, api):
    out = items.edit_items([
        items.EditItemParams(item_id="5", is_checked=True),
        items.EditItemParams(item_id="6", quantity="3", unit="kg", note=""),
        items.EditItemParams(item_id="7"),
    ])
    assert api.requests() == [
        ("PATCH", "/lists/42/items/5", {"Checked": 1}),
        ("PATCH", "/lists/42/items/6", {"Amount": "3", "Unit": "kg", "Description": ""}),
    ]
    assert out.splitlines()[-1] == "No changes given for item 7."


def test_uncheck_sends_zero_not_omitted(client, api):
    items.edit_items([items.EditItemParams(item_id="5", is_checked=False)])
    assert api.requests() == [("PATCH", "/lists/42/items/5", {"Checked": 0})]


def test_delete_items_is_one_batched_request(client, api):
    assert items.delete_items(["1", "2", "3"]) == "Deleted 3 item(s)."
    assert api.requests() == [("DELETE", "/lists/42/multipleitems", ["1", "2", "3"])]


def test_delete_items_error_propagates(client, api):
    api.replies.append(FakeResponse(403))
    with pytest.raises(requests.HTTPError):
        items.delete_items(["1"])


def test_get_lists_marks_default(client, api):
    api.replies.append(FakeResponse(200, [{"Id": 41, "Name": "BBQ"}, {"Id": 42, "Name": "Home"}]))
    assert lists.get_lists() == "(ListID: 41) BBQ\n(ListID: 42) Home  ← default"


# -- list-level tools ---------------------------------------------------------

LISTS = [{"Id": 41, "Name": "BBQ", "ItemsCount": 3, "SortOrder": 1},
         {"Id": 42, "Name": "Home", "ItemsCount": 0, "SortOrder": 4}]


def test_create_list_orders_after_existing_lists(client, api):
    api.replies += [FakeResponse(200, LISTS), FakeResponse(201, {"Id": "99", "Name": "Party"})]
    assert lists.create_list(" Party ") == "Created 'Party' (ListID: 99)."
    _, (method, path, body) = api.requests()
    assert (method, path) == ("POST", "/lists")
    assert body == {"Name": "Party", "Active": 1, "SortMode": 0, "SortOrder": 5, "Shares": [], "Items": []}


def test_blank_list_name_is_rejected(client, api):
    with pytest.raises(ValueError, match="empty"):
        lists.create_list("  ")
    assert api.requests() == []


def test_rename_list(client, api):
    api.replies.append(FakeResponse(200, LISTS))
    assert lists.rename_list("41", "Garden party") == "Renamed 'BBQ' to 'Garden party'."
    assert api.requests()[-1] == ("PATCH", "/lists/41", {"Name": "Garden party"})


def test_unknown_list_id_is_a_clear_error_and_writes_nothing(client, api):
    api.replies.append(FakeResponse(200, LISTS))
    with pytest.raises(ValueError, match="No list with ListID '7'"):
        lists.rename_list("7", "x")
    assert [r[0] for r in api.requests()] == ["GET"]


def test_delete_list_only_previews_without_confirm(client, api):
    api.replies.append(FakeResponse(200, LISTS))
    out = lists.delete_list("41")
    assert "Not deleted yet" in out and "'BBQ' (3 items)" in out
    assert [r[0] for r in api.requests()] == ["GET"]


def test_delete_list_with_confirm_deactivates_it(client, api):
    api.replies.append(FakeResponse(200, LISTS))
    assert lists.delete_list("41", confirm=True) == "Deleted the list 'BBQ' (3 items)."
    assert api.requests()[-1] == ("PATCH", "/lists/41", {"Active": 0})


def test_set_sort_mode(client, api):
    api.replies.append(FakeResponse(200, LISTS))
    assert lists.set_sort_mode("42", "alphabetical") == "'Home' is now sorted alphabetical."
    assert api.requests()[-1] == ("PATCH", "/lists/42", {"SortMode": 1})


def test_set_sort_mode_rejects_unsupported_mode_at_the_schema():
    with pytest.raises(Exception):
        asyncio.run(app.mcp.call_tool("set_sort_mode", {"list_id": "1", "mode": "custom"}))


def test_copy_list_copies_selected_items_unchecked(client, api):
    api.replies += [
        FakeResponse(200, LISTS),                                            # _find_list
        FakeResponse(200, [                                                  # source items
            {"Id": "1", "Name": "mleko", "Amount": "2", "Unit": "l", "Checked": 0, "Description": "UHT"},
            {"Id": "2", "Name": "chleb", "Amount": "1", "Unit": "", "Checked": 1},
        ]),
        FakeResponse(200, LISTS),                                            # create_list ordering
        FakeResponse(201, {"Id": "99", "Name": "BBQ - copy"}),               # create_list
    ]
    out = lists.copy_list("41", items="unpurchased")
    assert out == "Copied 1 item(s) from 'BBQ' into 'BBQ - copy' (ListID: 99)."
    *_, (method, path, body) = api.requests()
    assert (method, path) == ("POST", "/lists/99/items")
    assert (body["Name"], body["Amount"], body["Unit"], body["Description"], body["Checked"]) == ("mleko", "2", "l", "UHT", 0)


def test_copy_list_reports_failed_items(client, api):
    api.replies += [
        FakeResponse(200, LISTS), FakeResponse(200, [{"Id": "1", "Name": "a", "Checked": 0}]),
        FakeResponse(200, LISTS), FakeResponse(201, {"Id": "99", "Name": "Copy"}), FakeResponse(500),
    ]
    out = lists.copy_list("41", name="Copy")
    assert out.endswith("1 item(s) failed to copy.") and out.startswith("Copied 0 item(s)")


# -- bulk item tools ----------------------------------------------------------

def test_check_all_and_uncheck_all_use_checkall_direction(client, api):
    assert items.check_all() == "All items checked off."
    assert items.uncheck_all(list_id="7") == "All items unchecked."
    assert api.requests() == [
        ("POST", "/lists/42/items/checkall?direction=true", None),
        ("POST", "/lists/7/items/checkall?direction=false", None),
    ]


MIXED = [{"Id": "1", "Name": "mleko", "Checked": 0}, {"Id": "2", "Name": "chleb", "Checked": 1},
         {"Id": 3, "Name": "ser", "Checked": 1}]


def test_delete_checked_previews_without_confirm(client, api):
    api.replies.append(FakeResponse(200, MIXED))
    out = items.delete_checked()
    assert "Not deleted yet" in out and "2 checked" in out and "chleb" in out and "mleko" not in out
    assert [r[0] for r in api.requests()] == ["GET"]


def test_delete_checked_with_confirm_deletes_only_checked_in_one_request(client, api):
    api.replies.append(FakeResponse(200, MIXED))
    assert items.delete_checked(confirm=True) == "Deleted 2 checked item(s)."
    assert api.requests()[-1] == ("DELETE", "/lists/42/multipleitems", ["2", "3"])


def test_delete_checked_with_nothing_checked_is_a_noop(client, api):
    api.replies.append(FakeResponse(200, [MIXED[0]]))
    assert items.delete_checked(confirm=True) == "No checked items to delete."
    assert [r[0] for r in api.requests()] == ["GET"]

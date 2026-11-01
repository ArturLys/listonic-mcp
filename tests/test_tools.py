import asyncio

import pytest
import requests

from conftest import FakeResponse
from listonic_mcp import app
from listonic_mcp.tools import items, lists

EXPECTED = {
    # name: (readOnly, destructive, idempotent)
    "get_lists": (True, False, True),
    "get_items": (True, False, True),
    "add_items": (False, False, False),
    "edit_items": (False, False, True),
    "delete_items": (False, True, True),
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

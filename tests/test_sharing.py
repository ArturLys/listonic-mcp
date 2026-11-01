import pytest

from conftest import FakeResponse
from listonic_mcp.tools import sharing

LISTS = [{"Id": 41, "Name": "BBQ", "ItemsCount": 3}]
JANE = {"Email": "jane@example.com", "DisplayName": "Jane Doe", "Username": "google_x", "Id": "1"}
MEMBER = {"Email": "jane@example.com", "Display": "Jane Doe", "Username": "google_x"}


def test_get_friends_lists_name_and_email(client, api):
    api.replies.append(FakeResponse(200, [JANE]))
    assert sharing.get_friends() == "Jane Doe <jane@example.com>"


def test_get_list_members_private_and_shared(client, api):
    api.replies += [FakeResponse(200, LISTS), FakeResponse(200, {"Shares": []})]
    assert sharing.get_list_members("41") == "'BBQ' is private — not shared with anyone."
    api.replies += [FakeResponse(200, LISTS), FakeResponse(200, {"Shares": [MEMBER]})]
    assert sharing.get_list_members("41").endswith("Jane Doe <jane@example.com>")


def test_share_list_previews_without_confirm_and_writes_nothing(client, api):
    api.replies += [FakeResponse(200, LISTS), FakeResponse(200, [JANE]), FakeResponse(200, {"Shares": []})]
    out = sharing.share_list("41", "jane doe")
    assert "Not shared yet" in out and "who will be notified" in out and "jane@example.com" in out
    assert all(r[0] == "GET" for r in api.requests())


def test_share_list_with_confirm_posts_the_share(client, api):
    api.replies += [FakeResponse(200, LISTS), FakeResponse(200, [JANE]), FakeResponse(200, {"Shares": []}),
                    FakeResponse(201, {})]
    out = sharing.share_list("41", "Jane Doe", confirm=True)
    assert out == "Shared 'BBQ' with Jane Doe <jane@example.com>."
    method, path, body = api.requests()[-1]
    assert (method, path) == ("POST", "/lists/41/shares")
    assert body["Email"] == "jane@example.com" and body["Display"] == "Jane Doe" and body["Username"] == ""


def test_share_list_by_unknown_email_and_already_shared(client, api):
    api.replies += [FakeResponse(200, LISTS), FakeResponse(200, []), FakeResponse(200, {"Shares": []}),
                    FakeResponse(201, {})]
    assert sharing.share_list("41", "new@example.com", confirm=True) == "Shared 'BBQ' with new@example.com."
    api.replies += [FakeResponse(200, LISTS), FakeResponse(200, [JANE]), FakeResponse(200, {"Shares": [MEMBER]})]
    assert "already shared" in sharing.share_list("41", "jane@example.com", confirm=True)
    assert [r[0] for r in api.requests()].count("POST") == 1


def test_share_list_rejects_non_email_stranger(client, api):
    api.replies += [FakeResponse(200, LISTS), FakeResponse(200, [])]
    with pytest.raises(ValueError, match="not a known contact"):
        sharing.share_list("41", "Bob", confirm=True)


def test_unshare_previews_then_deletes_by_username(client, api):
    api.replies += [FakeResponse(200, LISTS), FakeResponse(200, {"Shares": [MEMBER]})]
    assert "would lose access" in sharing.unshare_list("41", "jane@example.com")
    assert all(r[0] == "GET" for r in api.requests())
    api.replies += [FakeResponse(200, LISTS), FakeResponse(200, {"Shares": [MEMBER]}), FakeResponse(200, None)]
    assert sharing.unshare_list("41", "Jane Doe", confirm=True) == "Removed Jane Doe <jane@example.com> from 'BBQ'."
    assert api.requests()[-1] == ("DELETE", "/lists/41/shares/google_x", None)


def test_unshare_unknown_member_is_an_error(client, api):
    api.replies += [FakeResponse(200, LISTS), FakeResponse(200, {"Shares": [MEMBER]})]
    with pytest.raises(ValueError, match="not a member"):
        sharing.unshare_list("41", "nobody@example.com", confirm=True)


def test_create_share_link(client, api):
    api.replies += [FakeResponse(200, LISTS), FakeResponse(200, "https://button.listonic.com/share/abc")]
    assert sharing.create_share_link("41") == "Share link for 'BBQ': https://button.listonic.com/share/abc"
    assert api.requests()[-1] == ("POST", "/linkshares/41", None)


def test_members_exclude_the_owner_and_removed_people(client, api):
    """Real API: Shares also lists the owner (Owner=1) and ex-members (Deleted=1)."""
    owner = {"Email": "me@example.com", "Display": "Me", "Username": "me", "Owner": 1}
    gone = {"Email": "old@example.com", "Display": "Old", "Username": "old", "Deleted": 1}
    api.replies += [FakeResponse(200, LISTS), FakeResponse(200, {"Shares": [owner]})]
    assert sharing.get_list_members("41") == "'BBQ' is private — not shared with anyone."
    api.replies += [FakeResponse(200, LISTS), FakeResponse(200, {"Shares": [owner, gone, MEMBER]})]
    out = sharing.get_list_members("41")
    assert "Jane" in out and "Me" not in out and "Old" not in out

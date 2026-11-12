import pytest
import requests

from conftest import FakeResponse
from listonic_mcp.client import ListonicClient


def test_logs_in_lazily_and_reuses_token(api):
    c = ListonicClient("me@example.com", "pw")
    c.request("GET", "/lists")
    c.request("GET", "/lists")
    logins = [x for x in api.calls if "loginextended" in x["url"]]
    assert len(logins) == 1
    assert api.calls[-1]["headers"] == {"Authorization": "Bearer tok"}


def test_401_triggers_one_relogin_and_retry(api):
    c = ListonicClient("me@example.com", "pw")
    api.replies += [FakeResponse(401), FakeResponse(200, [{"Id": 1}])]
    assert c.request("GET", "/lists").json() == [{"Id": 1}]
    assert len([x for x in api.calls if "loginextended" in x["url"]]) == 2


def test_second_401_is_raised_not_looped(api):
    c = ListonicClient("me@example.com", "pw")
    api.replies += [FakeResponse(401), FakeResponse(401)]
    with pytest.raises(requests.HTTPError):
        c.request("GET", "/lists")
    assert len([x for x in api.calls if x["method"] != "POST" or "loginextended" not in x["url"]]) == 2


def test_no_lists_is_a_clear_error(api):
    c = ListonicClient("me@example.com", "pw")
    api.replies.append(FakeResponse(200, []))
    with pytest.raises(RuntimeError, match="No lists"):
        c.default_list_id()

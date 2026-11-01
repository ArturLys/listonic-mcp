"""HTTP client for the reverse-engineered Listonic API (see API.md).

Knows the wire format (field names, endpoints) and nothing about MCP: tools stay
thin and call typed methods here, so a new API method is added in one place.
"""

import base64

import requests

API_BASE = "https://api.listonic.com/api"
# Listonic's own web-app client credentials (embedded in their public JS bundle,
# shared by every web user) — NOT a personal secret. See API.md.
CLIENT_ID = "listonicv2"
CLIENT_SECRET = "fjdfsoj9874jdfhjkh34jkhffdfff"
TIMEOUT = 10


class ListonicClient:
    """Password login, bearer auth, one automatic re-login on 401 (tokens last ~24h)."""

    def __init__(self, email: str, password: str, list_id: str | None = None):
        self.email = email
        self.password = password
        self._pinned_list_id = list_id or None
        self._default_list_id: str | None = None
        self._token: str | None = None

    # -- transport ---------------------------------------------------------

    def _login(self) -> str:
        b64 = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        resp = requests.post(
            f"{API_BASE}/loginextended?provider=password&autoMerge=1&autoDestruct=1",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "clientauthorization": f"Bearer {b64}",
            },
            data={
                "username": self.email,
                "password": self.password,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": "https://listonicv2api.jestemkucharzem.pl",
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise RuntimeError("Listonic login response carried no access_token.")
        self._token = token
        return token

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Authenticated request; on 401 (expired token) re-logins once and retries."""
        for attempt in (1, 2):
            token = self._token or self._login()
            resp = requests.request(
                method, f"{API_BASE}{path}",
                headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT, **kwargs,
            )
            if resp.status_code == 401 and attempt == 1:
                self._token = None
                continue
            resp.raise_for_status()
            return resp
        raise AssertionError("unreachable")

    # -- lists -------------------------------------------------------------

    def lists(self) -> list[dict]:
        resp = self.request("GET", "/lists?includeShares=false&archive=false&includeItems=false")
        return resp.json() or []

    def create_list(self, name: str) -> dict:
        """New empty list, ordered after the existing ones (the app sends max+1)."""
        body = {
            "Name": name, "Active": 1, "SortMode": 0,
            "SortOrder": max((l.get("SortOrder") or 0 for l in self.lists()), default=-1) + 1,
            "Shares": [], "Items": [],
        }
        return self.request("POST", "/lists", json=body).json()

    def update_list(self, list_id: str, **fields) -> None:
        """Partial update: Name, SortMode (0 categories, 1 alphabetical) or Active (0 = removed)."""
        self.request("PATCH", f"/lists/{list_id}", json=fields)

    def default_list_id(self) -> str:
        """The pinned --list-id if given, else the account's first list."""
        if self._pinned_list_id:
            return self._pinned_list_id
        if self._default_list_id is None:
            all_lists = self.lists()
            if not all_lists:
                raise RuntimeError("No lists on this Listonic account — create one in the app first.")
            self._default_list_id = str(all_lists[0].get("Id"))
        return self._default_list_id

    # -- items -------------------------------------------------------------

    def items(self, list_id: str) -> list[dict]:
        return self.request("GET", f"/lists/{list_id}/items").json() or []

    def add_item(self, list_id: str, name: str, amount: str = "", unit: str = "",
                 description: str = "") -> dict:
        # Same body shape the official app sends (PascalCase, full envelope).
        body = {
            "Name": name, "Description": description, "Amount": amount, "Unit": unit,
            "SortOrder": 0, "Price": 0.0, "CreatorUsername": "",
            "Checked": 0, "Deleted": 0, "Url": "",
        }
        return self.request("POST", f"/lists/{list_id}/items", json=body).json()

    def update_item(self, list_id: str, item_id: str, **fields) -> None:
        """Partial update. Fields use the API's names: Name, Amount, Unit, Description, Checked."""
        self.request("PATCH", f"/lists/{list_id}/items/{item_id}", json=fields)

    def check_all(self, list_id: str, checked: bool) -> None:
        """Check (True) or uncheck (False) every item on the list."""
        direction = "true" if checked else "false"
        self.request("POST", f"/lists/{list_id}/items/checkall?direction={direction}")

    def delete_items(self, list_id: str, item_ids: list[str]) -> None:
        """One request for any number of items (what the app does for 'delete purchased')."""
        self.request("DELETE", f"/lists/{list_id}/multipleitems", json=list(item_ids))

    # -- sharing -----------------------------------------------------------

    def friends(self) -> list[dict]:
        return self.request("GET", "/friends").json() or []

    def list_shares(self, list_id: str) -> list[dict]:
        """People the list is shared with (the list's ``Shares``)."""
        resp = self.request("GET", f"/lists/{list_id}?includeShares=true").json() or {}
        return resp.get("Shares") or []

    def share_list(self, list_id: str, email: str, display: str = "") -> dict:
        """Invite a person to the list; Listonic notifies them."""
        body = {"Waiting": 0, "Email": email, "Username": "", "Display": display,
                "Owner": 0, "ImageUrl": "", "Deleted": 0, "Url": ""}
        return self.request("POST", f"/lists/{list_id}/shares", json=body).json()

    def unshare_list(self, list_id: str, username: str) -> None:
        self.request("DELETE", f"/lists/{list_id}/shares/{username}")

    def create_share_link(self, list_id: str) -> str:
        return self.request("POST", f"/linkshares/{list_id}").json()

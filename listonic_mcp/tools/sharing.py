"""Tools for sharing lists with other people.

Sharing and unsharing affect another person, so both preview until ``confirm=true``.
Every tool takes an explicit ``list_id`` (no silent default list).
"""

from ..app import find_list, get_client, tool


def _who(person: dict) -> str:
    name = person.get("DisplayName") or person.get("Display") or ""
    email = person.get("Email") or ""
    return f"{name} <{email}>" if name and email else name or email or "?"


def _match(people: list[dict], who: str) -> dict | None:
    """A person by email or display name (case-insensitive)."""
    who = who.strip().casefold()
    for p in people:
        if who in ((p.get("Email") or "").casefold(),
                   (p.get("DisplayName") or p.get("Display") or "").casefold()):
            return p
    return None


@tool("Get friends", read_only=True)
def get_friends() -> str:
    """People the user has shared lists with before — the contacts share_list can
    use by name or email."""
    friends = get_client().friends()
    if not friends:
        return "No contacts yet — share a list by email with share_list."
    return "\n".join(_who(f) for f in friends)


@tool("Get list members", read_only=True)
def get_list_members(list_id: str) -> str:
    """Who a list is shared with.

    Args:
        list_id: the list (from get_lists).
    """
    client = get_client()
    target = find_list(client, list_id)
    members = client.list_shares(list_id.strip())
    if not members:
        return f"'{target.get('Name')}' is private — not shared with anyone."
    return f"'{target.get('Name')}' is shared with:\n" + "\n".join(_who(m) for m in members)


@tool("Share list")
def share_list(list_id: str, who: str, confirm: bool = False) -> str:
    """Share a list with another person, who is notified by Listonic. Without
    confirm=true this only previews who would get access: show that to the user and
    get their explicit OK before calling again with confirm=true.

    Args:
        list_id: the list to share (from get_lists).
        who: the person's email, or the name of a contact from get_friends.
        confirm: must be true to actually share.
    """
    client = get_client()
    target = find_list(client, list_id)
    friend = _match(client.friends(), who)
    email = (friend or {}).get("Email") or who.strip()
    if "@" not in email:
        raise ValueError(f"{who!r} is not a known contact and not an email address — see get_friends.")
    person = friend or {"Email": email}
    if _match(client.list_shares(list_id.strip()), email):
        return f"'{target.get('Name')}' is already shared with {_who(person)}."
    if not confirm:
        return (f"Not shared yet. This would share '{target.get('Name')}' with {_who(person)}, "
                "who will be notified. Call again with confirm=true after the user agrees.")
    client.share_list(list_id.strip(), email, (friend or {}).get("DisplayName", ""))
    return f"Shared '{target.get('Name')}' with {_who(person)}."


@tool("Unshare list", destructive=True, idempotent=True)
def unshare_list(list_id: str, who: str, confirm: bool = False) -> str:
    """Stop sharing a list with a person: they lose access to it. Without
    confirm=true this only previews: show it to the user and get their explicit OK
    before calling again with confirm=true.

    Args:
        list_id: the list (from get_lists).
        who: the member's email or name (see get_list_members).
        confirm: must be true to actually remove them.
    """
    client = get_client()
    target = find_list(client, list_id)
    member = _match(client.list_shares(list_id.strip()), who)
    if member is None:
        raise ValueError(f"{who!r} is not a member of '{target.get('Name')}' — see get_list_members.")
    if not member.get("Username"):
        raise ValueError(f"Listonic returned no username for {_who(member)}; can't remove them.")
    if not confirm:
        return (f"Not removed yet. {_who(member)} would lose access to '{target.get('Name')}'. "
                "Call again with confirm=true after the user agrees.")
    client.unshare_list(list_id.strip(), member["Username"])
    return f"Removed {_who(member)} from '{target.get('Name')}'."


@tool("Create share link")
def create_share_link(list_id: str) -> str:
    """Create a link that gives access to the list to anyone who opens it. Nobody is
    notified; hand the link to the user, don't post it anywhere yourself.

    Args:
        list_id: the list (from get_lists).
    """
    client = get_client()
    target = find_list(client, list_id)
    return f"Share link for '{target.get('Name')}': {client.create_share_link(list_id.strip())}"

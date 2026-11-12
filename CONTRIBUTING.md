# Contributing

Unofficial MCP server for Listonic. The API is reverse-engineered; `API.md` is the
source of truth for endpoints and field names (PascalCase on the wire).

## Layout

- `listonic_mcp/client.py` — HTTP and wire format. One typed method per API call; the
  only place that knows field names.
- `listonic_mcp/app.py` — the `mcp` instance, the `@tool` decorator, `resolve_list`
  (item tools) and `find_list` (list-level tools).
- `listonic_mcp/tools/*.py` — one module per group of tools (`lists`, `items`,
  `sharing`). A new module must be imported in `tools/__init__.py`; a test checks that a
  fresh server registers every tool.
- `listonic_mcp/cli.py` — launch parameters and entry point.
- `tests/` — pytest with a fake `requests`; no network and no credentials needed.

## Development

```sh
uv venv && uv pip install -e . --group dev
.venv/bin/pytest
```

## Adding a tool

1. Add the API call to `client.py` as a method (wire names live only there).
2. Add the tool in the matching `tools/` module with `@tool("Title", ...)`:
   - `read_only=True` for anything that never changes the account;
   - `destructive=True` when data is removed or irreversibly changed;
   - `idempotent=True` when repeating the call changes nothing more.
3. Return a short curated text summary, never raw API JSON.
4. Take lists, not scalars, when the user will naturally act on many things at once
   (batch like `add_items`). Report per-item failures instead of aborting the batch.
5. Item-level tools take an optional `list_id` and resolve it with
   `resolve_list(list_id)`. Tools that change a whole list take a required `list_id`
   and look it up with `find_list` so a wrong id fails before anything is written.
6. Anything outward-facing or hard to reverse (sharing with a person, deleting a list
   or many items at once) takes `confirm: bool = False` and, without it, only returns a
   preview of what would happen. The docstring tells the model to get the user's OK
   first.
7. Add the tool to `EXPECTED` in `tests/test_tools.py` (annotations are asserted) and
   a test for its request payload; update the README tools table, and `API.md` if you
   learned something new about the API.

Errors: raise. FastMCP turns an exception into an `isError` result. Only catch
`requests.RequestException` where a batch should keep going.

Importing the package must never require credentials (registry introspection,
`listonic-mcp --version` in CI).

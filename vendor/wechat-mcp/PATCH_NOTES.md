# wechat-mcp local patches

Upstream BiboyQG/WeChat-MCP is unmaintained and broken on current WeChat UI.
Two files in `wechat_mcp/` have been locally patched to work:

- `wechat_accessibility.py`  — +~300 lines vs upstream
- `fetch_messages_by_chat_utils.py` — +~70 lines vs upstream

Patches were applied at our `~/.local/share/mcp-servers/wechat-mcp/.venv/`
and copied here. Compare against upstream by running:

    git diff origin/main -- wechat_mcp/wechat_accessibility.py

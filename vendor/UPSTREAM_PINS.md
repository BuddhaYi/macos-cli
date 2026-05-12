# Vendored projects — upstream pins

Each subproject's `.git` was removed before committing to macos-cli (to avoid
git submodule complexity). The exact upstream commit each was vendored from
is recorded below so you can `git clone <url>` fresh + `git checkout <commit>`
if you need to sync or diff against upstream.

| Project | Upstream URL | Commit at vendor time |
|---|---|---|
| macos-automator-mcp | https://github.com/steipete/macos-automator-mcp.git | `1ce1b55605303dd717b329fb9b409d4bc21c66a5` |
| magpie | https://github.com/BuddhaYi/magpie.git | `7d3e744b3d66a2f4c2b84ea76c1c816ec89d4a67` |
| opencli | https://github.com/jackwener/opencli.git | `fa9b38cd9242cc58fbbe9fbe5a102bf6836350d7` |
| twitter-cli | https://github.com/public-clis/twitter-cli.git | `7c634e0d396b1e7af9f63315b414925fe4f29ae7` |
| wechat-mcp | https://github.com/BiboyQG/WeChat-MCP.git | `cc470367ca6613b129f7e2bb742e6cc57df8c4d6` |

## Special cases

- **bird**: GitHub repo (`steipete/bird`) was **deleted**. Vendored from the npm package
  `@steipete/bird@0.8.0` (contains only compiled `dist/`, no TypeScript source).
- **wechat-mcp**: contains 2 locally patched files vs upstream:
  - `src/wechat_mcp/wechat_accessibility.py` (+~283 lines)
  - `src/wechat_mcp/fetch_messages_by_chat_utils.py` (+~89 lines)
  See `vendor/wechat-mcp/PATCH_NOTES.md` for details.

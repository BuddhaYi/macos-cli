from __future__ import annotations

from wechat_mcp.mcp_server import fetch_messages_by_chat


def main() -> None:
    print(fetch_messages_by_chat("家", last_n=30))


if __name__ == "__main__":
    main()

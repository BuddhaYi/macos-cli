from __future__ import annotations

from wechat_mcp.mcp_server import reply_to_messages_by_chat


def main() -> None:
    print(reply_to_messages_by_chat("邦邦", "Hello from tests"))


if __name__ == "__main__":
    main()

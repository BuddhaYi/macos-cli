from __future__ import annotations

from wechat_mcp.publish_moment_utils import publish_moment_without_media


def main() -> None:
    """
    Manual invocation helper for publish_moment_without_media.

    Run via:
        uv run python -m tests.test_publish_moment_test
    """
    content = "今天吃了好吃的午餐！🍜🍣🍰 "
    # Set publish=True to actually post the moment; use publish=False
    # when testing without sending.
    result = publish_moment_without_media(content, publish=False)
    print(result)


if __name__ == "__main__":
    main()

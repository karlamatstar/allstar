"""VOC MCP 표준 입출력 서버 진입점."""

from allstar.voc.mcp.tools import mcp


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

"""CI smoke test: launch a built executable as an MCP server over stdio, the way Claude Desktop does.

Usage: python packaging/smoke_mcp.py <path-to-executable>

The MCP server is built by a later part of the project. Until ``prophelper.mcp_server`` exists this script says so
and exits 0 (a skip), so CI stays green. Once it exists, the checks below run for real.
"""
import importlib.util
import os
import sys
import tempfile

EXPECTED_TOOLS: set[str] = set()  # filled in when the MCP server lands: the tool names every build must offer


def server_exists() -> bool:
    try:
        return importlib.util.find_spec("prophelper.mcp_server") is not None
    except (ImportError, ValueError):
        return False


async def main(exe: str) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = {**os.environ, "PROPHELPER_DATA_DIR": tempfile.mkdtemp()}
    params = StdioServerParameters(command=exe, args=["mcp"], env=env)
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = {t.name for t in (await s.list_tools()).tools}
            assert tools, "the MCP server offered no tools"
            assert EXPECTED_TOOLS <= tools, EXPECTED_TOOLS - tools
            assert not [n for n in tools if "delete" in n or "remove" in n], tools  # the AI never deletes
    print(f"MCP smoke test passed: {exe}")


if __name__ == "__main__":
    if not server_exists():
        print("MCP smoke test skipped: prophelper.mcp_server does not exist yet.")
        sys.exit(0)
    import anyio

    anyio.run(main, sys.argv[1])

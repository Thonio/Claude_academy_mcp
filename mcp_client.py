import asyncio
import json
import sys
from contextlib import AsyncExitStack
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from pydantic import AnyUrl


class MCPClient:
    """Thin wrapper around an MCP ClientSession talking to a server over stdio."""

    def __init__(self, command: str, args: list[str], env: Optional[dict] = None):
        self._command = command
        self._args = args
        self._env = env
        self._session: Optional[ClientSession] = None
        self._exit_stack = AsyncExitStack()

    async def connect(self):
        server_params = StdioServerParameters(
            command=self._command, args=self._args, env=self._env
        )
        read, write = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()

    def session(self) -> ClientSession:
        if self._session is None:
            raise ConnectionError("Client session not initialized. Call connect() first.")
        return self._session

    async def list_tools(self) -> list[types.Tool]:
        result = await self.session().list_tools()
        return result.tools

    async def call_tool(self, tool_name: str, tool_input: dict) -> types.CallToolResult:
        return await self.session().call_tool(tool_name, tool_input)

    async def list_prompts(self) -> list[types.Prompt]:
        result = await self.session().list_prompts()
        return result.prompts

    async def get_prompt(self, prompt_name: str, args: dict[str, str]) -> list[types.PromptMessage]:
        result = await self.session().get_prompt(prompt_name, args)
        return result.messages

    async def read_resource(self, uri: str) -> Any:
        result = await self.session().read_resource(AnyUrl(uri))
        resource = result.contents[0]
        if isinstance(resource, types.TextResourceContents):
            if resource.mimeType == "application/json":
                return json.loads(resource.text)
            return resource.text
        return resource

    async def cleanup(self):
        await self._exit_stack.aclose()
        self._session = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()


def _text(result: types.CallToolResult) -> str:
    return "\n".join(c.text for c in result.content if isinstance(c, types.TextContent))


async def demo():
    """Exercise the server directly (no Claude, no API key needed)."""
    async with MCPClient(command=sys.executable, args=["server.py"]) as client:
        print("Tools:  ", [t.name for t in await client.list_tools()])
        print("Prompts:", [p.name for p in await client.list_prompts()])
        print("Docs:   ", await client.read_resource("docs://documents"))

        print("\n-- read example.md")
        print(_text(await client.call_tool("read_doc_contents", {"doc_id": "example.md"})))

        print("\n-- create notes.md")
        print(_text(await client.call_tool(
            "create_document", {"doc_id": "notes.md", "content": "Meeting at 10am."}
        )))

        print("\n-- read notes.md")
        print(_text(await client.call_tool("read_doc_contents", {"doc_id": "notes.md"})))

        print("\n-- edit notes.md (10am -> 2pm)")
        print(_text(await client.call_tool(
            "edit_document", {"doc_id": "notes.md", "old_str": "10am", "new_str": "2pm"}
        )))

        print("\n-- read via resource docs://documents/notes.md")
        print(await client.read_resource("docs://documents/notes.md"))


if __name__ == "__main__":
    asyncio.run(demo())

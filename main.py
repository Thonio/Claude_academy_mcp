"""Chat CLI: Claude + the DocumentMCP server.

Type a message and Claude can read, edit and create documents through the MCP tools.
  @doc_id          -> attach that document's contents to your message (MCP resource)
  /format doc_id   -> run an MCP prompt (any prompt the server exposes works: /summarize ...)
  /docs            -> list document ids
  quit             -> exit
"""

import asyncio
import os
import re
import sys

import anthropic
from dotenv import load_dotenv
from mcp import types

from mcp_client import MCPClient

load_dotenv()

MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")

SYSTEM = (
    "You are a helpful assistant that manages a set of documents through tools. "
    "Use read_doc_contents, edit_document and create_document to work with them. "
    "Keep answers short."
)


def to_claude_tools(tools: list[types.Tool]) -> list[dict]:
    return [
        {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
        for t in tools
    ]


class Chat:
    def __init__(self, mcp: MCPClient):
        self.mcp = mcp
        self.claude = anthropic.Anthropic()
        self.messages: list = []

    async def _tool_results(self, content) -> list[dict]:
        results = []
        for block in content:
            if block.type != "tool_use":
                continue
            print(f"  [tool] {block.name}({block.input})")
            try:
                result = await self.mcp.call_tool(block.name, block.input)
                text = "\n".join(
                    c.text for c in result.content if isinstance(c, types.TextContent)
                )
                results.append({
                    "type": "tool_result", "tool_use_id": block.id,
                    "content": text, "is_error": result.isError,
                })
            except Exception as e:
                results.append({
                    "type": "tool_result", "tool_use_id": block.id,
                    "content": f"Error: {e}", "is_error": True,
                })
        return results

    async def run(self, user_content) -> str:
        """Send a user turn and loop until Claude stops calling tools."""
        self.messages.append({"role": "user", "content": user_content})
        tools = to_claude_tools(await self.mcp.list_tools())

        while True:
            response = self.claude.beta.messages.create(
                model=MODEL,
                max_tokens=16000,
                system=SYSTEM,
                messages=self.messages,
                tools=tools,
                output_config={"effort": "medium"},
                # On a safety refusal, the API retries on a fallback model automatically.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            # Append the full content (not just text) so the history stays valid.
            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "refusal":
                return "[Claude declined this request]"
            if response.stop_reason != "tool_use":
                return "".join(b.text for b in response.content if b.type == "text")

            self.messages.append(
                {"role": "user", "content": await self._tool_results(response.content)}
            )

    async def handle(self, line: str) -> str:
        if line == "/docs":
            return ", ".join(await self.mcp.read_resource("docs://documents"))

        if line.startswith("/"):
            name, _, doc_id = line[1:].partition(" ")
            prompt_msgs = await self.mcp.get_prompt(name, {"doc_id": doc_id.strip()})
            text = "\n".join(
                m.content.text for m in prompt_msgs if isinstance(m.content, types.TextContent)
            )
            return await self.run(text)

        # Attach any @mentioned documents as context.
        attached = []
        for doc_id in re.findall(r"@([\w.\-]+)", line):
            try:
                body = await self.mcp.read_resource(f"docs://documents/{doc_id}")
                attached.append(f'<document id="{doc_id}">\n{body}\n</document>')
            except Exception:
                pass  # unknown id: leave the mention as plain text
        if attached:
            line = "\n".join(attached) + "\n\n" + line
        return await self.run(line)


async def main():
    async with MCPClient(command=sys.executable, args=["server.py"]) as mcp:
        chat = Chat(mcp)
        print(__doc__)
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            if line in ("quit", "exit"):
                break
            try:
                print(await chat.handle(line))
            except TypeError as e:
                if "authentication" not in str(e):
                    raise
                print("No Claude credentials found: set ANTHROPIC_API_KEY (see README).")
            except anthropic.AuthenticationError:
                print("Authentication failed: set ANTHROPIC_API_KEY (see README).")
            except anthropic.APIStatusError as e:
                print(f"API error {e.status_code}: {e.message}")
            except anthropic.APIConnectionError:
                print("Network error: could not reach the Claude API.")


if __name__ == "__main__":
    asyncio.run(main())

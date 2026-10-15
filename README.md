# Document MCP — server + client

A small MCP (Model Context Protocol) project, based on the Anthropic Academy MCP course.

- **`server.py`** — an MCP server (`DocumentMCP`) that holds a set of documents and lets a client **read**, **edit** and **create** them.
- **`mcp_client.py`** — an MCP client class (`MCPClient`) that starts the server over stdio and calls it. Run it on its own for a demo that doesn't need an API key.
- **`main.py`** — a chat CLI where Claude uses the server's tools to work on the documents for you.

## What the server exposes

| Kind | Name | What it does |
|---|---|---|
| Tool | `read_doc_contents(doc_id)` | Returns a document's text |
| Tool | `edit_document(doc_id, old_str, new_str)` | Replaces `old_str` with `new_str` in a document |
| Tool | `create_document(doc_id, content)` | Creates a new document (fails if the id exists) |
| Resource | `docs://documents` | JSON list of all document ids |
| Resource | `docs://documents/{doc_id}` | A document's text |
| Prompt | `format(doc_id)` | Asks Claude to rewrite the doc in Markdown |
| Prompt | `summarize(doc_id)` | Asks Claude to summarize the doc |

Documents are kept **in memory**: the server starts with 7 sample docs (`deposition.md`, `report.pdf`, `financials.docx`, `outlook.pdf`, `plan.md`, `spec.txt`, `example.md`). Changes and new docs last only while the server is running, which is as long as the client runs.

### Example document: `example.md`

`example.md` is a longer, multi-line sample you can use to try reading, editing and formatting:

```markdown
# Condenser Tower Inspection - Example

Inspection date: 2026-10-01
Inspector: J. Doe

## Findings
- The 20m tower shows minor corrosion on the north face.
- Fan motor vibration is within normal limits.
- Water treatment logs are complete.

## Next steps
1. Repaint the north face before winter.
2. Re-inspect the fan motor in 6 months.
```

Ways to read it:

| From | How |
|---|---|
| Python client | `await client.call_tool("read_doc_contents", {"doc_id": "example.md"})` |
| Python client (resource) | `await client.read_resource("docs://documents/example.md")` |
| Chat (Claude calls the tool) | `> What are the next steps in example.md?` |
| Chat (attach as context) | `> Summarize @example.md` |
| Chat (server prompt) | `> /summarize example.md` |

## Setup

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

To use the Claude chat (`main.py`), add an Anthropic API key. Put it in a `.env` file at the project root (it's git-ignored):

```
ANTHROPIC_API_KEY=sk-ant-...
# optional, defaults to claude-opus-5-5
# CLAUDE_MODEL=claude-sonnet-5-5
```

## Usage

### 1. Client demo (no API key needed)

```bash
python mcp_client.py
```

This starts the server, lists its tools, prompts and docs, reads `example.md`, then creates `notes.md`, reads it, edits it and reads it back:

```
Tools:   ['read_doc_contents', 'edit_document', 'create_document']
Prompts: ['format', 'summarize']
Docs:    ['deposition.md', 'report.pdf', ..., 'example.md']

-- read example.md
# Condenser Tower Inspection - Example
...

-- create notes.md
Document notes.md created.
-- read notes.md
Meeting at 10am.
-- edit notes.md (10am -> 2pm)
Document notes.md updated.
-- read via resource docs://documents/notes.md
Meeting at 2pm.
```

### 2. Chat with Claude

```bash
python main.py
```

Then type requests in plain language. Claude decides which tools to call, and each call is printed as `[tool] ...`.

```
> What does report.pdf say?
> Change "20m" to "25m" in report.pdf
> Create a doc called todo.md with a 3-item checklist for the condenser tower inspection
```

Commands you can use in the chat:

| Input | Effect |
|---|---|
| `@doc_id` | Attaches that document's contents to your message (read through the MCP resource), e.g. `Summarize @plan.md` |
| `/format doc_id` | Runs the server's `format` prompt, e.g. `/format plan.md` |
| `/summarize doc_id` | Runs the server's `summarize` prompt |
| `/docs` | Lists the document ids |
| `quit` | Exits |

The chat calls the model with `fallbacks="default"`. If the model declines a request for safety reasons, the API retries it on a fallback model automatically.

### 3. Inspect the server with MCP Inspector

```bash
mcp dev server.py
```

This opens the MCP Inspector in your browser, where you can call each tool, resource and prompt by hand.

### 4. Use the server from Claude Desktop / Claude Code

Point any MCP host at the server. In Claude Code, for example:

```bash
claude mcp add documents -- /absolute/path/to/.venv/bin/python /absolute/path/to/server.py
```

## Using `MCPClient` in your own code

```python
import asyncio, sys
from mcp_client import MCPClient

async def main():
    async with MCPClient(command=sys.executable, args=["server.py"]) as client:
        await client.call_tool("create_document", {"doc_id": "a.md", "content": "hello"})
        print(await client.read_resource("docs://documents/a.md"))

asyncio.run(main())
```

Methods: `list_tools()`, `call_tool(name, input)`, `list_prompts()`, `get_prompt(name, args)`, `read_resource(uri)`.

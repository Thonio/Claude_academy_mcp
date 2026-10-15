from pydantic import Field
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base

mcp = FastMCP("DocumentMCP", log_level="ERROR")

docs = {
    "deposition.md": "This deposition covers the testimony of Angela Smith, P.E.",
    "report.pdf": "The report details the state of a 20m condenser tower.",
    "financials.docx": "These financials outline the project's budget and expenditures",
    "outlook.pdf": "This document presents the projected future performance of the system",
    "plan.md": "The plan outlines the steps for the project's implementation.",
    "spec.txt": "These specifications define the technical requirements for the equipment",
    "example.md": """# Condenser Tower Inspection - Example

Inspection date: 2026-10-01
Inspector: J. Doe

## Findings
- The 20m tower shows minor corrosion on the north face.
- Fan motor vibration is within normal limits.
- Water treatment logs are complete.

## Next steps
1. Repaint the north face before winter.
2. Re-inspect the fan motor in 6 months.
""",
}


# ---------------------------------------------------------------- Tools


@mcp.tool(
    name="read_doc_contents",
    description="Read the contents of a document and return it as a string.",
)
def read_document(
    doc_id: str = Field(description="Id of the document to read"),
):
    if doc_id not in docs:
        raise ValueError(f"Doc with id {doc_id} not found")

    return docs[doc_id]


@mcp.tool(
    name="edit_document",
    description="Edit a document by replacing a string in the documents content with a new string.",
)
def edit_document(
    doc_id: str = Field(description="Id of the document that will be edited"),
    old_str: str = Field(
        description="The text to replace. Must match exactly, including whitespace."
    ),
    new_str: str = Field(
        description="The new text to insert in place of the old text."
    ),
):
    if doc_id not in docs:
        raise ValueError(f"Doc with id {doc_id} not found")
    if old_str not in docs[doc_id]:
        raise ValueError(f"Text '{old_str}' not found in doc {doc_id}")

    docs[doc_id] = docs[doc_id].replace(old_str, new_str)
    return f"Document {doc_id} updated."


@mcp.tool(
    name="create_document",
    description="Create a new document with the given id and content. Fails if the id already exists.",
)
def create_document(
    doc_id: str = Field(description="Id (file name) of the new document, e.g. 'notes.md'"),
    content: str = Field(description="The initial content of the document"),
):
    if doc_id in docs:
        raise ValueError(f"Doc with id {doc_id} already exists")

    docs[doc_id] = content
    return f"Document {doc_id} created."


# ---------------------------------------------------------------- Resources


@mcp.resource("docs://documents", mime_type="application/json")
def list_docs() -> list[str]:
    return list(docs.keys())


@mcp.resource("docs://documents/{doc_id}", mime_type="text/plain")
def fetch_doc(doc_id: str) -> str:
    if doc_id not in docs:
        raise ValueError(f"Doc with id {doc_id} not found")

    return docs[doc_id]


# ---------------------------------------------------------------- Prompts


@mcp.prompt(
    name="format",
    description="Rewrites the contents of the document in Markdown format.",
)
def format_document(
    doc_id: str = Field(description="Id of the document to format"),
) -> list[base.Message]:
    prompt = f"""
Your goal is to reformat a document to be written with markdown syntax.

The id of the document you need to reformat is:
<document_id>
{doc_id}
</document_id>

Add in headers, bullet points, tables, etc as necessary. Feel free to add in extra text, but don't change the meaning of the report.
Use the 'edit_document' tool to edit the document. After the document has been edited, respond with the final version of the doc. Don't explain your changes.
"""
    return [base.UserMessage(prompt)]


@mcp.prompt(
    name="summarize",
    description="Summarizes the contents of a document.",
)
def summarize_document(
    doc_id: str = Field(description="Id of the document to summarize"),
) -> list[base.Message]:
    prompt = f"""
Read the document with id '{doc_id}' using the 'read_doc_contents' tool and write a short summary of it (2-3 sentences).
"""
    return [base.UserMessage(prompt)]


if __name__ == "__main__":
    mcp.run(transport="stdio")

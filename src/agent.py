import json
import os

from llm import ask
from tools import TOOLS, DOCUMENTS

_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_dir, "..")
with open(os.path.join(_root, "prompts", "system.md")) as f:
    SYSTEM = f.read()

TOOL_INFO = {
    "list_headings": "list_headings(doc_id) – Returns section headings and page numbers from the PDF table of contents.",
    "search_keyword": "search_keyword(doc_id, keyword) – Searches all pages for a keyword, returns page numbers where found.",
    "get_page": "get_page(doc_id, page_number) – Returns the full text of a specific page.",
    "load_pdf": "load_pdf(file_path) – Opens a PDF file and returns a doc_id for use with other tools.",
    "list_documents": "list_documents() – Returns titles and metadata for all loaded documents.",
}

tool_desc = "\n".join(
    TOOL_INFO.get(name, name) for name in TOOLS
)
SYSTEM = SYSTEM.replace("[[TOOLS]]", tool_desc)

MAX_BUDGET = 6


def _parse_json(raw):
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]).strip()
    return json.loads(text)


def _grounding_check(pages, pages_read):
    return all(p in pages_read for p in pages)


def answer_question(question, doc_id):
    calls_used = 0
    pages_read = set()
    history = []
    seen = set()
    trace = []

    doc = DOCUMENTS.get(doc_id)
    page_count = doc.page_count if doc else 0

    while calls_used < MAX_BUDGET:
        prompt = f"Question: {question}\nDocument: {doc_id}\n"
        if history:
            prompt += "\n".join(history) + "\n"
        prompt += f"\nCalls left: {MAX_BUDGET - calls_used}"

        raw = ask(prompt, SYSTEM)

        reply = None
        parse_retries = 0
        while parse_retries < 2:
            try:
                reply = _parse_json(raw)
                break
            except (json.JSONDecodeError, ValueError):
                parse_retries += 1
                history.append("Reply with ONLY JSON.")
                prompt = f"Question: {question}\nDocument: {doc_id}\n"
                prompt += "\n".join(history) + "\n"
                prompt += f"\nCalls left: {MAX_BUDGET - calls_used}"
                raw = ask(prompt, SYSTEM)

        if reply is None:
            return {
                "answer": "Failed to parse LLM response as JSON.",
                "pages": [],
                "status": "error",
                "calls_used": calls_used,
                "trace": trace,
            }

        # --- Final answer ---
        if "final" in reply:
            answer = reply["final"]
            pages = reply.get("pages", [])
            status = "done" if _grounding_check(pages, pages_read) else "insufficient"
            trace.append({"type": "final", "answer": answer, "pages": pages, "status": status})
            return {
                "answer": answer,
                "pages": pages,
                "status": status,
                "calls_used": calls_used,
                "trace": trace,
            }

        # --- Tool call ---
        if "tool" not in reply:
            history.append("Reply with ONLY JSON containing 'tool' or 'final'.")
            continue

        tool_name = reply["tool"]
        args = reply.get("args", {})

        # Validate: tool exists
        if tool_name not in TOOLS:
            msg = f"Rejected: unknown tool '{tool_name}'"
            history.append(msg)
            trace.append({"type": "rejected", "tool": tool_name, "reason": "unknown tool"})
            continue

        # Validate: args
        rejected = False
        reason = ""

        if tool_name == "get_page":
            page = args.get("page_number")
            if not isinstance(page, int) or page < 1 or page > page_count:
                rejected = True
                reason = f"page_number must be int between 1 and {page_count}"
        elif tool_name == "search_keyword":
            kw = args.get("keyword", "")
            if not isinstance(kw, str) or not kw.strip():
                rejected = True
                reason = "keyword must be a non-empty string"

        if rejected:
            msg = f"Rejected {tool_name}: {reason}"
            history.append(msg)
            trace.append({"type": "rejected", "tool": tool_name, "args": args, "reason": reason})
            continue

        # Validate: duplicate
        call_key = (tool_name, json.dumps(args, sort_keys=True))
        if call_key in seen:
            msg = f"Rejected {tool_name}({args}): duplicate call"
            history.append(msg)
            trace.append({"type": "rejected", "tool": tool_name, "args": args, "reason": "duplicate"})
            continue

        # Execute
        try:
            if tool_name == "list_documents":
                result = TOOLS[tool_name]()
            else:
                tool_args = {"doc_id": doc_id, **args}
                result = TOOLS[tool_name](**tool_args)
        except Exception as e:
            result = f"Error: {e}"

        trace.append({"type": "tool_call", "tool": tool_name, "args": args, "result": result})

        if tool_name == "get_page" and not str(result).startswith("Error"):
            pages_read.add(args["page_number"])

        history.append(f"Tool {tool_name}({args}) → {result}")
        seen.add(call_key)
        calls_used += 1

    # Budget exhausted — force a final answer
    prompt = f"Question: {question}\nDocument: {doc_id}\n"
    prompt += "\n".join(history)
    prompt += "\nNo tool calls left, you must now give a final answer."

    raw = ask(prompt, SYSTEM)

    try:
        reply = _parse_json(raw)
        answer = reply.get("final", raw.strip())
        pages = reply.get("pages", [])
    except (json.JSONDecodeError, ValueError):
        answer = raw.strip()
        pages = []

    status = "done" if _grounding_check(pages, pages_read) else "insufficient"
    trace.append({"type": "final", "answer": answer, "pages": pages, "status": status, "budget_exhausted": True})

    return {
        "answer": answer,
        "pages": pages,
        "status": status,
        "calls_used": calls_used,
        "trace": trace,
    }

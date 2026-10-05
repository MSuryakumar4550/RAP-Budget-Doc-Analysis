import fitz  # type: ignore
import json
import os
import re
import time
import unicodedata
from pathlib import Path

_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
LOG_FILE = _ROOT / "logs" / "run.jsonl"
LOG_FILE.parent.mkdir(exist_ok=True)

DOCUMENTS = {}
DOC_NAMES = {}


def _normalize(text):
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r'\s+', ' ', text).lower().strip()
    return text


def log_tool_call(tool_name, args, result):
    event = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tool": tool_name,
        "args": args,
        "result": result,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(event, default=str) + "\n")

def load_pdf(file_path, original_name=None):
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        raise ValueError(f"Could not open PDF: {e}")

    doc_id = f"doc_{len(DOCUMENTS) + 1}"
    DOCUMENTS[doc_id] = doc
    DOC_NAMES[doc_id] = original_name or os.path.basename(file_path)
    log_tool_call("load_pdf", {"file_path": file_path}, doc_id)
    return doc_id

def list_headings(doc_id):
    if doc_id not in DOCUMENTS:
        raise ValueError("Invalid doc_id")
    
    doc = DOCUMENTS[doc_id]
    toc = doc.get_toc()
    
    if not toc:
        return None
        
    headings = {}
    for item in toc:
        if len(item) >= 3:
            title = str(item[1]).strip()
            page = int(item[2])
            headings[title] = {"page": page}
            
    # Check if page 1 or 2 (index 0 or 1) contains "Table of Contents" text
    for i in range(min(2, doc.page_count)):
        page_text = doc.load_page(i).get_text()
        page_text = re.sub(r'\s+', ' ', page_text).strip().lower()
        if "table of contents" in page_text:
            headings["_note"] = "Found 'Table of Contents' text on page 1 or 2"
            break

    log_tool_call("list_headings", {"doc_id": doc_id}, headings)
    return headings

def search_keyword(doc_id, keyword):
    if doc_id not in DOCUMENTS:
        raise ValueError("Invalid doc_id")
        
    doc = DOCUMENTS[doc_id]
    keyword = _normalize(keyword)

    found_pages = set()
    for i in range(doc.page_count):
        page_text = doc.load_page(i).get_text()
        page_text = _normalize(page_text)
        if keyword in page_text:
            found_pages.add(i + 1)
            
    result = sorted(list(found_pages))
    log_tool_call("search_keyword", {"doc_id": doc_id, "keyword": keyword}, result)
    return result

def get_page(doc_id, page_number):
    if doc_id not in DOCUMENTS:
        raise ValueError("Invalid doc_id")
        
    doc = DOCUMENTS[doc_id]
    
    if not isinstance(page_number, int) or not (1 <= page_number <= doc.page_count):
        raise ValueError(f"Page number {page_number} is out of range (1 - {doc.page_count}).")
        
    page_text = doc.load_page(page_number - 1).get_text()

    result = f"<document_page n={page_number}>{page_text}</document_page>"
    log_tool_call("get_page", {"doc_id": doc_id, "page_number": page_number}, result)
    return result


def list_documents():
    result = []
    for doc_id, doc in DOCUMENTS.items():
        result.append({
            "doc_id": doc_id,
            "title": DOC_NAMES.get(doc_id, doc.name),
            "pages": doc.page_count,
        })
    log_tool_call("list_documents", {}, result)
    return result


TOOLS = {
    "list_headings": list_headings,
    "search_keyword": search_keyword,
    "get_page": get_page,
    "list_documents": list_documents,
}

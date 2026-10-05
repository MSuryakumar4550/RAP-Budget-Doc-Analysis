import io
import json
import os
import re
import time
import unicodedata
from pathlib import Path

try:
    import pymupdf as fitz  # type: ignore
    HAS_PYMUPDF = True
except ImportError:
    try:
        import fitz  # type: ignore
        HAS_PYMUPDF = True
    except ImportError:
        HAS_PYMUPDF = False

if not HAS_PYMUPDF:
    from PyPDF2 import PdfReader

_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
LOG_FILE = _ROOT / "logs" / "run.jsonl"
LOG_FILE.parent.mkdir(exist_ok=True)

DOCUMENTS = {}
DOC_NAMES = {}
_next_id = 1


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


# --- PDF extraction (once at upload) ---

def _extract_with_pymupdf(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_count = len(doc)
    title = doc.metadata.get("title", "") if doc.metadata else ""

    pages = {}
    for i in range(page_count):
        pages[i + 1] = doc[i].get_text()

    headings = []
    toc = doc.get_toc()
    if toc:
        for level, heading_title, page_num in toc:
            headings.append({"title": heading_title, "page": page_num, "level": level})

    doc.close()
    return pages, headings, title, page_count


def _extract_with_pypdf2(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)
    title = ""
    if reader.metadata and reader.metadata.title:
        title = reader.metadata.title

    pages = {}
    for i, page in enumerate(reader.pages):
        pages[i + 1] = page.extract_text() or ""

    headings = []
    try:
        if reader.outline:
            _parse_outline(reader.outline, headings, reader, level=1)
    except Exception:
        pass

    return pages, headings, title, page_count


def _parse_outline(outline, headings, reader, level):
    for item in outline:
        if isinstance(item, list):
            _parse_outline(item, headings, reader, level + 1)
        else:
            try:
                page_num = reader.get_destination_page_number(item) + 1
            except Exception:
                page_num = 1
            headings.append({"title": item.title, "page": page_num, "level": level})


def _extract_headings_from_text(pages):
    headings = []
    section_pattern = re.compile(r'^(\d+(?:\.\d+)*)\s+(.+)$', re.MULTILINE)

    for page_num, text in sorted(pages.items()):
        for match in section_pattern.finditer(text):
            numbering = match.group(1)
            heading_title = match.group(2).strip()
            if len(heading_title) > 100:
                continue
            level = numbering.count('.') + 1
            headings.append({
                "title": f"{numbering} {heading_title}",
                "page": page_num,
                "level": level,
            })

    return headings


# --- Tool functions ---

def load_pdf(file_path, original_name=None):
    global _next_id

    with open(file_path, "rb") as f:
        pdf_bytes = f.read()

    if HAS_PYMUPDF:
        pages, headings, title, page_count = _extract_with_pymupdf(pdf_bytes)
    else:
        pages, headings, title, page_count = _extract_with_pypdf2(pdf_bytes)

    if not headings:
        headings = _extract_headings_from_text(pages)

    if not title:
        name = original_name or os.path.basename(file_path)
        title = name.replace(".pdf", "").replace("_", " ")

    doc_id = f"doc_{_next_id}"
    _next_id += 1

    DOCUMENTS[doc_id] = {
        "pages": pages,
        "headings": headings,
        "title": title,
        "page_count": page_count,
    }
    DOC_NAMES[doc_id] = original_name or os.path.basename(file_path)

    log_tool_call("load_pdf", {"file_path": file_path}, doc_id)
    return doc_id


def list_headings(doc_id):
    if doc_id not in DOCUMENTS:
        raise ValueError("Invalid doc_id")

    doc = DOCUMENTS[doc_id]
    headings = doc["headings"]

    if not headings:
        return None

    result = {}
    for h in headings:
        result[h["title"]] = {"page": h["page"]}

    log_tool_call("list_headings", {"doc_id": doc_id}, result)
    return result


def search_keyword(doc_id, keyword):
    if doc_id not in DOCUMENTS:
        raise ValueError("Invalid doc_id")

    doc = DOCUMENTS[doc_id]
    keyword = _normalize(keyword)

    found_pages = set()
    for page_num, text in doc["pages"].items():
        if keyword in _normalize(text):
            found_pages.add(page_num)

    result = sorted(list(found_pages))
    log_tool_call("search_keyword", {"doc_id": doc_id, "keyword": keyword}, result)
    return result


def get_page(doc_id, page_number):
    if doc_id not in DOCUMENTS:
        raise ValueError("Invalid doc_id")

    doc = DOCUMENTS[doc_id]

    if not isinstance(page_number, int) or not (1 <= page_number <= doc["page_count"]):
        raise ValueError(f"Page number {page_number} is out of range (1 - {doc['page_count']}).")

    page_text = doc["pages"].get(page_number, "")

    result = f"<document_page n={page_number}>{page_text}</document_page>"
    log_tool_call("get_page", {"doc_id": doc_id, "page_number": page_number}, result)
    return result


def list_documents():
    result = []
    for doc_id, doc in DOCUMENTS.items():
        result.append({
            "doc_id": doc_id,
            "title": DOC_NAMES.get(doc_id, doc["title"]),
            "pages": doc["page_count"],
        })
    log_tool_call("list_documents", {}, result)
    return result


TOOLS = {
    "list_headings": list_headings,
    "search_keyword": search_keyword,
    "get_page": get_page,
    "list_documents": list_documents,
}

# PDF Document-Answering Agent

A budgeted, tool-calling agent that answers questions from PDF documents using Google Gemini. Built for the RAP Hackathon 2026.

## Tech Stack

| Component | Technology |
|---|---|
| Frontend + Backend | Streamlit |
| LLM | Google Gemini API (gemini-2.5-flash) |
| PDF Parsing | PyMuPDF (primary), PyPDF2 (fallback) |
| Agent Logic | Plain Python (no frameworks) |
| Config | python-dotenv |

## Project Structure

```
hack-rap/
├── .env                        # API keys (NEVER commit)
├── .gitignore
├── README.md
├── requirements.txt
├── memo.md                     # Architecture explanation
├── decisions_log.txt
│
├── src/
│   ├── tools.py                # 4 PDF tools + logging wrapper
│   ├── agent.py                # Agent harness (loop, budget, validation)
│   ├── llm.py                  # Gemini integration with fallback models
│   └── app.py                  # Streamlit chat interface
│
├── prompts/
│   └── system.md               # LLM strategy and safety rules
│
├── tests/
│   └── test_questions.py       # Automated test cases
│
├── logs/
│   └── run.jsonl               # Tool call trace (created at runtime)
│
└── data/
    └── sample.pdf              # Sample PDFs for testing
```

## Prerequisites

- Python 3.10+
- Google Gemini API key ([Get one here](https://aistudio.google.com/apikey))

## Setup and Installation

```bash
# 1. Navigate to project
cd hack-rap

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file with your API key
```

Create a `.env` file in the `hack-rap/` root:

```
GEMINI_API_KEY=your-actual-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
```

## How to Run

### Run the Streamlit App

```bash
cd hack-rap
python -m streamlit run src/app.py
```

A browser tab opens at `http://localhost:8501`. Then:

1. Upload one or more PDFs using the sidebar
2. Type a question in the text box
3. Click **Ask**
4. View the answer, status, pages cited, and tool call trace

### Run Automated Tests

```bash
cd hack-rap
python tests/test_questions.py data/sample.pdf
```

With multiple PDFs:

```bash
python tests/test_questions.py data/doc1.pdf data/doc2.pdf
```

### Test Individual Components

```bash
cd hack-rap
python
```

```python
import sys
sys.path.insert(0, "src")

# Test PDF parsing
from tools import load_pdf, list_headings, search_keyword, get_page
doc_id = load_pdf("data/sample.pdf")
print(list_headings(doc_id))
print(search_keyword(doc_id, "introduction"))
print(get_page(doc_id, 1)[:200])

# Test LLM connection
from llm import ask
print(ask("What is 2+2? Reply as JSON with key 'answer'"))

# Test full agent
from agent import answer_question
result = answer_question("What is this document about?", [doc_id])
print(result["answer"])
```

## Tool Interface

The agent accesses PDF content through exactly 4 tools:

| Tool | Signature | Returns |
|---|---|---|
| `list_documents` | `list_documents()` | Titles, doc_ids, page counts for all loaded PDFs |
| `list_headings` | `list_headings(doc_id)` | Table of contents / section headings with page numbers |
| `search_keyword` | `search_keyword(doc_id, keyword)` | Page numbers where keyword appears |
| `get_page` | `get_page(doc_id, page_number)` | Full text of one specific page |

**Budget:** 6 tool calls per question. No RAG, no embeddings, no vector database.

## Key Features

- **Multi-document support** — Upload multiple PDFs, agent searches across all of them
- **Budget enforcement** — Hard 6-call limit tracked in code, not by the LLM
- **Grounding check** — Every cited page must have been actually read
- **Duplicate detection** — Repeated tool calls are blocked without spending budget
- **Input validation** — Invalid page numbers, empty keywords rejected before execution
- **Prompt injection protection** — PDF text wrapped in data tags, safety rules in system prompt
- **PyPDF2 fallback** — Works even if PyMuPDF is not installed
- **Regex heading detection** — Finds section headings even without a table of contents
- **Unicode normalization** — Handles PDF ligatures (e.g., "ﬁ" matches "fi")
- **Full audit logging** — Every tool call timestamped in `logs/run.jsonl`

## Constraints Met

| Constraint | Status |
|---|---|
| No RAG / embeddings / vector DB | Met |
| All reading through 4 tool interface | Met |
| 6 tool calls per question max | Met |
| Agent can say "insufficient information" | Met |
| No agentic frameworks (LangChain, etc.) | Met |

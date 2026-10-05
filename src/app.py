import json
import os
import tempfile
from pathlib import Path

import streamlit as st
from tools import load_pdf, DOCUMENTS
from agent import answer_question

_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
LOG_FILE = _ROOT / "logs" / "run.jsonl"


def read_logs():
    if not LOG_FILE.exists():
        return []
    logs = []
    with open(LOG_FILE, "r") as f:
        for line in f:
            logs.append(json.loads(line))
    return logs

st.set_page_config(page_title="PDF Document-Answering Agent")
st.title("PDF Document-Answering Agent")

# --- Sidebar: PDF upload ---
with st.sidebar:
    st.header("Upload PDF")
    uploaded = st.file_uploader("Choose a PDF file", type=["pdf"])

    if uploaded and "doc_id" not in st.session_state:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name
        try:
            doc_id = load_pdf(tmp_path)
            st.session_state["doc_id"] = doc_id
            st.session_state["pdf_name"] = uploaded.name
            st.session_state["tmp_path"] = tmp_path
        except Exception as e:
            st.error(f"Failed to load PDF: {e}")

    if "doc_id" in st.session_state and st.session_state["doc_id"] not in DOCUMENTS:
        tmp_path = st.session_state.get("tmp_path")
        if tmp_path and os.path.exists(tmp_path):
            new_doc_id = load_pdf(tmp_path)
            st.session_state["doc_id"] = new_doc_id

    if "doc_id" in st.session_state:
        st.success(f"Loaded: {st.session_state['pdf_name']}")

    if st.button("Clear chat"):
        tmp_path = st.session_state.get("tmp_path")
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- Main area: Chat ---
if "history" not in st.session_state:
    st.session_state["history"] = []

question = st.text_input("Ask a question about the PDF", placeholder="Ask a question about the PDF")
ask_clicked = st.button("Ask")

if ask_clicked and question:
    if "doc_id" not in st.session_state:
        st.warning("Upload a PDF first.")
    else:
        with st.spinner("Thinking..."):
            result = answer_question(question, st.session_state["doc_id"])
        st.session_state["history"].append({"question": question, "result": result})

# --- Display results ---
for i, entry in enumerate(reversed(st.session_state["history"])):
    q = entry["question"]
    r = entry["result"]

    st.markdown(f"**Q: {q}**")
    st.markdown(f"{r['answer']}")
    st.markdown(f"**Status:** {r['status']}")

    if r["pages"]:
        st.markdown(f"**Pages read:** {', '.join(str(p) for p in r['pages'])}")
    else:
        st.markdown("**Pages read:** none")

    st.markdown(f"**Calls used:** {r['calls_used']} out of 6")

    with st.expander("Full trace"):
        for step in r["trace"]:
            if step["type"] == "tool_call":
                st.markdown(f"**{step['tool']}**({step['args']})")
                st.text(str(step["result"])[:2000])
            elif step["type"] == "rejected":
                st.markdown(f"**Rejected:** {step['tool']} — {step['reason']}")
            elif step["type"] == "final":
                st.markdown(f"**Final answer** (status: {step['status']})")

    if i < len(st.session_state["history"]) - 1:
        st.divider()

# --- Full log from run.jsonl ---
with st.expander("Full trace (tool calls)"):
    logs = read_logs()
    for log in logs:
        st.json(log)
    st.caption(f"Total tool calls: {len(logs)} out of 6")

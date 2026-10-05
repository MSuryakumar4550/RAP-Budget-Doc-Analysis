import json
import os
import tempfile
from pathlib import Path

import streamlit as st
from tools import load_pdf, DOCUMENTS, DOC_NAMES
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

if "docs" not in st.session_state:
    st.session_state["docs"] = {}
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

# --- Sidebar ---
with st.sidebar:
    st.header("Documents")

    uploaded = st.file_uploader(
        "Upload PDF",
        type=["pdf"],
        key=f"uploader_{st.session_state['uploader_key']}",
    )

    if uploaded:
        already_loaded = any(
            info["name"] == uploaded.name for info in st.session_state["docs"].values()
        )
        if not already_loaded:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            try:
                doc_id = load_pdf(tmp_path, original_name=uploaded.name)
                st.session_state["docs"][doc_id] = {
                    "name": uploaded.name,
                    "tmp_path": tmp_path,
                }
                st.session_state["uploader_key"] += 1
                st.rerun()
            except Exception as e:
                st.error(f"Failed to load: {e}")

    # Reload docs lost from DOCUMENTS on Streamlit rerun
    for doc_id, info in list(st.session_state["docs"].items()):
        if doc_id not in DOCUMENTS:
            tmp_path = info.get("tmp_path")
            if tmp_path and os.path.exists(tmp_path):
                new_doc_id = load_pdf(tmp_path, original_name=info.get("name"))
                st.session_state["docs"][new_doc_id] = info
                if new_doc_id != doc_id:
                    del st.session_state["docs"][doc_id]

    # Document list
    if st.session_state["docs"]:
        for doc_id in list(st.session_state["docs"].keys()):
            info = st.session_state["docs"].get(doc_id)
            if not info:
                continue
            col1, col2 = st.columns([4, 1])
            with col1:
                st.caption(info["name"])
            with col2:
                if st.button("✕", key=f"rm_{doc_id}"):
                    tmp_path = info.get("tmp_path")
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                    DOCUMENTS.pop(doc_id, None)
                    DOC_NAMES.pop(doc_id, None)
                    del st.session_state["docs"][doc_id]
                    st.rerun()

        if st.button("Clear All"):
            for did, info in list(st.session_state["docs"].items()):
                tmp_path = info.get("tmp_path")
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                DOCUMENTS.pop(did, None)
                DOC_NAMES.pop(did, None)
            st.session_state["docs"] = {}
            st.session_state["history"] = []
            st.session_state["uploader_key"] += 1
            if LOG_FILE.exists():
                LOG_FILE.unlink()
            st.rerun()

# --- Main area: Chat ---
if "history" not in st.session_state:
    st.session_state["history"] = []

question = st.text_input(
    "Ask a question about your PDFs",
    placeholder="Ask a question about your PDFs",
)
ask_clicked = st.button("Ask")

if ask_clicked and question:
    if not st.session_state["docs"]:
        st.warning("Upload at least one PDF first.")
    else:
        doc_ids = list(st.session_state["docs"].keys())
        with st.spinner("Thinking..."):
            result = answer_question(question, doc_ids)
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

# PDF Document-Answering Agent

A Streamlit app that answers questions about PDF documents using Gemini and a tool-calling agent loop.

## Quick Start

```bash
cd hack-rap
pip install -r requirements.txt
```

Create a `.env` file:
```
GEMINI_API_KEY=your-key-here
```

Run the app:
```bash
streamlit run src/app.py
```

Run tests:
```bash
python tests/test_questions.py data/sample.pdf
```

## Project Structure

- `src/` — Source code (llm, tools, agent, app)
- `prompts/` — System prompt for the LLM
- `tests/` — Test cases
- `logs/` — Tool call trace (created at runtime)
- `data/` — Sample PDFs for testing

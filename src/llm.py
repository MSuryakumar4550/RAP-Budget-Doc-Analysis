import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from google import genai

_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_dir, "..")
load_dotenv(os.path.join(_root, ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

GEMINI_MODELS = [
    GEMINI_MODEL,
    "gemini-2.5-flash",
    "gemini-3.5-flash",
]
# Remove duplicates while preserving order
GEMINI_MODELS = list(dict.fromkeys(GEMINI_MODELS))

client = genai.Client(api_key=GEMINI_API_KEY)


def ask(prompt, system=""):
    config = genai.types.GenerateContentConfig(
        system_instruction=system or None,
        temperature=0.2,
        response_mime_type="application/json",
    )

    for model in GEMINI_MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            return response.text
        except Exception as e:
            if "429" in str(e) and model != GEMINI_MODELS[-1]:
                continue
            raise

    raise RuntimeError("All models exhausted")

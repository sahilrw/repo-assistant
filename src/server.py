"""FastAPI backend. Serves the static frontend and streams ingest status + answers."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import rag, store
from src.ingest import ingest_steps

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

GENERIC_QUESTIONS = [
    "What does this repository do?",
    "Where is the main entry point?",
    "How is the project structured?",
    "What are the core modules and their roles?",
]

app = FastAPI(title="repo-assistant")


class IngestRequest(BaseModel):
    url: str


class AskRequest(BaseModel):
    question: str


@app.post("/api/ingest")
def api_ingest(req: IngestRequest):
    def stream():
        url = (req.url or "").strip()
        if not url:
            yield "> paste a public github repo url first\n"
            return
        try:
            for status in ingest_steps(url):
                yield status + "\n"
        except Exception as e:
            yield f"> error · {e}\n"

    return StreamingResponse(stream(), media_type="text/plain")


@app.post("/api/ask")
def api_ask(req: AskRequest):
    question = (req.question or "").strip()

    def stream():
        if not question:
            return
        try:
            for token in rag.answer_stream(question):
                yield token
        except Exception as e:
            yield f"\n\n[error: {e}]"

    return StreamingResponse(stream(), media_type="text/plain")


@app.get("/api/suggestions")
def api_suggestions():
    try:
        questions = rag.suggest_questions(4) if store.all_paths() else []
    except Exception:
        questions = []
    if not questions:
        questions = GENERIC_QUESTIONS
    return {"questions": questions}


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

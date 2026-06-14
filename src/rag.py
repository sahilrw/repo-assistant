"""Retrieve relevant chunks and answer the question, grounded in them with file citations."""

from src import store
from src import llm

SYSTEM_PROMPT = (
    "You are an expert repository assistant. Your job is to answer questions about the codebase "
    "using ONLY the provided context blocks below. \n\n"
    "Guidelines:\n"
    "1. For every claim or code reference you make, cite its source path and line range inline "
    "exactly as formatted in the context brackets (e.g., [src/foo.py:42-58]).\n"
    "2. Be concise and technically precise. Answer directly from the context — do NOT add "
    "meta-commentary about not being able to see the full repository or source tree.\n"
    "3. If the context does not contain the answer, say so in one short sentence and stop. "
    "Do not make anything up."
)

def retrieve(question: str) -> list:
    candidates = store.search(question, k=20)
    return store.rerank(question, candidates, top_n=5)

def suggest_questions(n: int = 4) -> list:
    paths = store.all_paths()[:80]
    if not paths:
        return []
    system = (
        "Given a repository's file list, write questions a developer would actually ask to understand it. "
        "Favor concrete 'how does X work' or 'where is Y implemented' questions tied to specific files or "
        "features you can infer from the names. Avoid vague meta questions like 'what does this repo do'. "
        "Return exactly the requested number, one per line, no numbering or preamble, each under 12 words."
    )
    user = "Repository files:\n" + "\n".join(paths) + f"\n\nSuggest {n} questions."
    text = llm.ask(system, [{"role": "user", "content": user}])
    questions = [line.strip().lstrip("-•0123456789. ").strip() for line in text.splitlines() if line.strip()]
    return questions[:n]

def _format_context(chunks) -> str:
    blocks = []
    for _, text, metadata in chunks:
        path = metadata.get("path", "unknown_file")
        start = metadata.get("start_line", 1)
        end = metadata.get("end_line", start)
        loc = f"{path}:{start}" if end <= start else f"{path}:{start}-{end}"
        blocks.append(f"[{loc}]\n{text.strip()}")
    return "\n\n".join(blocks)

def answer(question: str) -> str:
    context_str = _format_context(retrieve(question))
    user_content = f"Context:\n{context_str}\n\nQuestion: {question}"
    return llm.ask(SYSTEM_PROMPT, [{"role": "user", "content": user_content}])

def answer_stream(question: str):
    context_str = _format_context(retrieve(question))
    user_content = f"Context:\n{context_str}\n\nQuestion: {question}"
    yield from llm.stream(SYSTEM_PROMPT, [{"role": "user", "content": user_content}])
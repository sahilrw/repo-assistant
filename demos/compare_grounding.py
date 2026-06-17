"""Grounded (RAG) vs ungrounded (raw model) comparison.

Shows why retrieval matters: the same Claude model answering a repo-specific question
with no retrieval (guesses or refuses) next to the grounded answer with file citations.

Ingest a repo first (via the app), then run from the repo root:
    python demos/compare_grounding.py "how does retrieval work?"
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import rag

def main():
    question = sys.argv[1] if len(sys.argv) > 1 else "How is this project structured, and what are its main modules?"
    print(f"Q: {question}\n")
    print("=== ungrounded (raw model, no retrieval) ===")
    print(rag.answer_raw(question))
    print("\n=== grounded (RAG, cited to files) ===")
    print(rag.answer(question))

if __name__ == "__main__":
    main()
